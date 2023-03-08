from dotenv import load_dotenv
import json
from pprint import pprint
import requests
import time
import datetime
import pytz
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()

fellows = {}
projects = {}

# Connect to Google Sheets
scope = ['https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive"]

credentials = ServiceAccountCredentials.from_json_keyfile_name("gs_credentials.json", scope)
client = gspread.authorize(credentials)

sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/12quNi2TYuRK40woals-ABPT5NcsmhBmC_dHNU9rX1Do")

activities_data_sh = sheet.worksheet("activities_data")
fellows_sh = sheet.worksheet("Enrolled Fellows (22.FAL,23.SPR)")
projects_sh = sheet.worksheet("Project Repos (22.FAL,23.SPR)")

# Get fellows
for row in fellows_sh.get_all_records():
    if row['Term'] == os.getenv("FW_TERM"):
        fellows[row['Application: Fellow Email Address']] = {
            "github_username": row['GitHub Handle'],
            "project": row['Fellowship Project'],
            "gitlab_username": row['Application: GitLab Handle'],
            "github_userid": "Null"#requests.get(f"https://api.github.com/users/{row['GitHub Handle']}", auth=(os.getenv("GITHUB_USERNAME"), os.getenv("GITHUB_ACCESS_TOKEN"))).json()['id']
        }
    #time.sleep(5)

# Get projects
for row in projects_sh.get_all_records():
    if row['Term'] == os.getenv("FW_TERM"):
        if row['Project Name'] not in projects:
            projects[row['Project Name']] = {
                "urls": [],
                "gitlab_ids": []
            }
        projects[row['Project Name']]['urls'].append(row['Repo Link'])
        if row['GitLab Project ID'] != "":
            projects[row['Project Name']]['gitlab_ids'].append(row['GitLab Project ID'])

BASE_URL = "https://api.github.com"

COMMITS_URL = "commits?q=author:"
ISSUES_URL = "issues?q=author:"
ISSUE_URL = "issues?assignee"

BATCH_START = datetime.datetime(2023, 1, 30)
BATCH_END = datetime.datetime(2023, 4, 22)
GITHUB_DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
GITHUB_COMMIT_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"
GITLAB_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
utc = pytz.utc

def make_gh_request(request_type, user, org=None, project=None):
    r = None
    try:
        if request_type == ISSUES_URL:
            r = requests.get(f"{BASE_URL}/search/{request_type}{user}&per_page=100", auth=(os.getenv("GITHUB_USERNAME"), os.getenv("GITHUB_ACCESS_TOKEN")))
        elif request_type == COMMITS_URL:
            r = requests.get(f"{BASE_URL}/search/{request_type}{user}&per_page=100&&sort=author-date", auth=(os.getenv("GITHUB_USERNAME"), os.getenv("GITHUB_ACCESS_TOKEN")))
        elif request_type == ISSUE_URL:
            r = requests.get(f"{BASE_URL}/repos/{org}/{project}/{ISSUE_URL}={user}", auth=(os.getenv("GITHUB_USERNAME"), os.getenv("GITHUB_ACCESS_TOKEN")))
        return r.json()  
    except:
        pprint(r.json())
        return None
    
def make_gl_request(request_type, user, project_id):
    r = None
    try:
        if request_type == "merge_request":
            r = requests.get(f"https://gitlab.com/api/v4/projects/{project_id}/merge_requests?author_username={user}", headers={'PRIVATE-TOKEN': os.getenv("GITLAB_ACCESS_TOKEN")})
        elif request_type == "issue":
            r = requests.get(f"https://gitlab.com/api/v4/projects/{project_id}/issues?assignee_username={user}", headers={'PRIVATE-TOKEN': os.getenv("GITLAB_ACCESS_TOKEN")})
        elif request_type == "commit":
            r = requests.get(f"https://gitlab.com/api/v4/projects/{project_id}/commits", headers={'PRIVATE-TOKEN': os.getenv("GITLAB_ACCESS_TOKEN")})
        return r.json()
    except:
        pprint(r.json())
        return None

def find_issues_prs(response, projects, fellow):
    if "items" not in response:
        pprint(response)
    for item in response["items"]:
        url = '/'.join(item['html_url'].split('/')[:5])
        
        # Check dates are within Batch Dates
        if datetime.datetime.strptime(item['created_at'], GITHUB_DATE_FORMAT) >= BATCH_START and datetime.datetime.strptime(item['created_at'], GITHUB_DATE_FORMAT) <= BATCH_END:
            # Check PR is in the project
            if url in projects and "pull_request" in item and check_no_duplicates(item['html_url'], item['closed_at'], item['pull_request']['merged_at']): # if it's a PR
                
                activities_data_sh.append_row([fellow,
                                                fellows[fellow]['github_userid'],
                                                fellows[fellow]['github_username'],
                                                fellows[fellow]['project'],
                                                item['id'],
                                                item['html_url'],
                                                "Pull Request", 
                                                item['title'],
                                                item['number'],
                                                item['created_at'],
                                                item['closed_at'],
                                                item['pull_request']['merged_at']])
            # Check Issue is in the project
            elif url in projects and "pull_request" not in item and check_no_duplicates(item['html_url'], item['closed_at']): #if it's an Issue
                
                activities_data_sh.append_row([fellow,
                                                fellows[fellow]['github_userid'],
                                                fellows[fellow]['github_username'],
                                                fellows[fellow]['project'],
                                                item['id'],
                                                item['html_url'],
                                                "Issue", 
                                                item['title'],
                                                item['number'],
                                                item['created_at'],
                                                item['closed_at'],
                                                "Null"])

# this needs to identify forks
def find_commits(response, projects, fellow):
    for item in response['items']:
        url = item['repository']['html_url']
        
        if (datetime.datetime.strptime(item['commit']['author']['date'], GITHUB_COMMIT_DATE_FORMAT)).replace(tzinfo=utc) >= BATCH_START.replace(tzinfo=utc) and datetime.datetime.strptime(item['commit']['author']['date'], GITHUB_COMMIT_DATE_FORMAT).replace(tzinfo=utc) <= BATCH_END.replace(tzinfo=utc):
            if url in projects and check_no_duplicates(item['html_url']):
                activities_data_sh.append_row([fellow,
                                                fellows[fellow]['github_userid'],
                                                fellows[fellow]['github_username'],
                                                fellows[fellow]['project'],
                                                item['sha'],
                                                item['html_url'],
                                                "Commit", 
                                                item['commit']['message'],
                                                "Null",
                                                item['commit']['author']['date'],
                                                "Null",
                                                "Null"])

def find_assigned_issues(response, fellow):
    for issue in response:
        if datetime.datetime.strptime(issue['created_at'], GITHUB_DATE_FORMAT) >= BATCH_START and datetime.datetime.strptime(issue['created_at'], GITHUB_DATE_FORMAT) <= BATCH_END:
            if check_no_duplicates(issue['html_url'], issue['closed_at']):
                activities_data_sh.append_row([fellow,
                                                fellows[fellow]['github_userid'],
                                                fellows[fellow]['github_username'],
                                                fellows[fellow]['project'],
                                                issue['id'],
                                                issue['html_url'],
                                                "Issue", 
                                                issue['title'],
                                                issue['number'],
                                                issue['created_at'],
                                                issue['closed_at'],
                                                "Null"])


def get_pr_changed_lines(url, row):
    if "https://github" in url:
        org = url.split('/')[3]
        repo_name = url.split('/')[4]
        pull_id = int(url.split('/')[6])
        pull_response = requests.get(f"{BASE_URL}/repos/{org}/{repo_name}/pulls/{pull_id}", auth=(os.getenv("GITHUB_USERNAME"), os.getenv("GITHUB_ACCESS_TOKEN"))).json()
        if pull_response:
            activities_data_sh.update_acell(f"M{row + 2}", pull_response['additions'])
            activities_data_sh.update_acell(f"N{row + 2}", pull_response['deletions'])
            activities_data_sh.update_acell(f"O{row + 2}", pull_response['changed_files'])


def check_no_duplicates(url, closed_date="Null", merged_date="Null"):
    values = activities_data_sh.get("F2:F")
    for row, item in enumerate(values):
        if item[0].strip() == url:
            if closed_date != "Null" and closed_date != None:
                activities_data_sh.update_acell(f"K{row + 2}", closed_date)                
            if merged_date != "Null" and merged_date != None:
                activities_data_sh.update_acell(f"L{row + 2}", merged_date)
                get_pr_changed_lines(url, row)
            time.sleep(0.1)

            return False
    return True


def find_merge_requests(response, fellow):
    for mr in response:
        if datetime.datetime.strptime(mr['created_at'], GITLAB_DATE_FORMAT) >= BATCH_START and datetime.datetime.strptime(mr['created_at'], GITLAB_DATE_FORMAT) <= BATCH_END:
            if check_no_duplicates(mr['web_url'], mr['closed_at'], mr['merged_at']):
                activities_data_sh.append_row([fellow,
                                            fellows[fellow]['github_userid'],
                                            fellows[fellow]['gitlab_username'],
                                            fellows[fellow]['project'],
                                            mr['iid'],
                                            mr['web_url'],
                                            "Pull Request",
                                            mr['title'],
                                            mr['iid'],
                                            mr['created_at'],
                                            mr['closed_at'],
                                            mr['merged_at']]),

def find_gl_issues(response, fellow):
    for issue in response:
        if datetime.datetime.strptime(issue['created_at'], GITLAB_DATE_FORMAT) >= BATCH_START and datetime.datetime.strptime(issue['created_at'], GITLAB_DATE_FORMAT) <= BATCH_END:
            if check_no_duplicates(issue['web_url'], issue['closed_at']):
                activities_data_sh.append_row([fellow,
                                            fellows[fellow]['github_userid'],
                                            fellows[fellow]['gitlab_username'],
                                            fellows[fellow]['project'],
                                            issue['iid'],
                                            issue['web_url'],
                                            "Issue",
                                            issue['title'],
                                            issue['iid'],
                                            issue['created_at'],
                                            issue['closed_at'],
                                            "Null"]),

def find_gl_commits(response, fellow):
    for commit in response:
         if datetime.datetime.strptime(commit['created_at'], GITLAB_DATE_FORMAT) >= BATCH_START and datetime.datetime.strptime(commit['created_at'], GITLAB_DATE_FORMAT) <= BATCH_END:
             pass

# Get info per fellow
for fellow in fellows:
    print(f"Fetching data for: {fellow} - {fellows[fellow]['project']}")

    if fellows[fellow]['project'] not in projects:
        continue
    
    fellow_projects = projects[fellows[fellow]['project']]
    
    issues_response = make_gh_request(ISSUES_URL, fellows[fellow]['github_username'])
    if issues_response != None:
        find_issues_prs(issues_response, fellow_projects['urls'], fellow)
    time.sleep(5)
    commits_response = make_gh_request(COMMITS_URL, fellows[fellow]['github_username'])
    if commits_response != None:
        find_commits(commits_response, fellow_projects['urls'], fellow)

    for url in fellow_projects['urls']:
        if "https://github" in url:
            org = url.split('/')[3]
            repo_name = url.split('/')[4]
            gh_issue_response = make_gh_request(ISSUE_URL, fellows[fellow]['github_username'], org=org, project=repo_name)
            find_assigned_issues(gh_issue_response, fellow)
            time.sleep(5)


    if len(fellow_projects['gitlab_ids']) > 0:
        for gitlab_id in fellow_projects['gitlab_ids']:
            mr_response = make_gl_request("merge_request", fellows[fellow]['gitlab_username'], gitlab_id)
            if mr_response:
                find_merge_requests(mr_response, fellow)
            issue_response = make_gl_request("issue", fellows[fellow]['gitlab_username'], gitlab_id)
            if issue_response:
                find_gl_issues(issue_response, fellow)

    time.sleep(5) # Limited to 30 requests a minute / 1 request every 2 seconds.
