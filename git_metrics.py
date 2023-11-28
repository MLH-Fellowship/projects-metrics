from dotenv import load_dotenv
from pprint import pprint
import requests
import time
import datetime
import pytz
import os
import helpers
import gspread
import cli
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()

fellows = {}
projects = {}


utc = pytz.utc

# Connect to Google Sheets
scope = ['https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive"]

credentials = ServiceAccountCredentials.from_json_keyfile_name("gs_credentials.json", scope)
client = gspread.authorize(credentials)

sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/12quNi2TYuRK40woals-ABPT5NcsmhBmC_dHNU9rX1Do")

activities_data_sh = sheet.worksheet("activities_data")

BASE_URL = "https://api.github.com"

COMMITS_URL = "commits?q=author:"
ISSUES_URL = "issues?q=author:"
ISSUE_URL = "issues?assignee"

PROGRAM_DATE_START_YEAR = 2023 #int(os.getenv("PROGRAM_DATE_YEAR"))
PROGRAM_DATE_END_YEAR = 2023 #int(os.getenv("PROGRAM_DATE_YEAR"))
PROGRAM_DATE_START_MONTH = 9 #int(os.getenv("PROGRAM_DATE_START_MONTH"))
PROGRAM_DATE_END_MONTH = 12 #int(os.getenv("PROGRAM_DATE_END_MONTH")
PROGRAM_DATE_START_DAY = 1 #int(os.getenv("PROGRAM_DATE_START_DAY"))
PROGRAM_DATE_END_DAY = 30 #int(os.getenv("PROGRAM_DATE_END_DAY"))

BATCH_START = datetime.datetime(PROGRAM_DATE_START_YEAR, PROGRAM_DATE_START_MONTH, PROGRAM_DATE_START_DAY)
BATCH_END = datetime.datetime(PROGRAM_DATE_END_YEAR, PROGRAM_DATE_END_MONTH, PROGRAM_DATE_END_DAY)
GITHUB_DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
GITHUB_COMMIT_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"
CLI_COMMIT_DATE_FORMAT = "%a %b %d %H:%M:%S %Y %z"
GITLAB_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
utc = pytz.utc

def collect_data():
    for fellow in fellows:
        print(f"Fetching data for: {fellow} - {fellows[fellow]['project']}")

        if fellows[fellow]['project'] not in projects:
            print(f"No Project Match for {fellow}. Skipping")
            continue
        fellow_projects = projects[fellows[fellow]['project']]

        if len(fellow_projects['urls']) < 1:
            print(f"No URLs for {fellows[fellow]['project']}. Skipping")
            continue

        
        print("Getting PRs/Issues")
        #issues_response = make_gh_request(ISSUES_URL, fellows[fellow]['github_username'])
        #if issues_response != None and "items" in issues_response:
        #    find_issues_prs(issues_response, fellow_projects['urls'], fellow)
        #time.sleep(5)

        print("Getting commits")
        for url in fellow_projects['urls']:
            commits = cli.collect_commits(url, fellow)
            for commit in commits:
                local_date = datetime.datetime.strptime(commit['date'], CLI_COMMIT_DATE_FORMAT).replace(tzinfo=utc)
                if local_date > BATCH_START.replace(tzinfo=utc) and local_date < BATCH_END.replace(tzinfo=utc):
                    print(f"Adding {commit['sha']} to db")
                    helpers.add_to_db(email=fellow, github_id=fellows[fellow]['github_userid'], github_username=fellows[fellow]['github_username'], 
                                    project=fellows[fellow]['project'], id=commit['sha'], url=f"{url}/commit/{commit['sha']}", activity_type="Commit", message=commit['message'], number="Null", 
                                    created_at=commit['date'], additions=commit['additions'], deletions=commit['deletions'], files_changed=commit['files_changed'])

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

        time.sleep(10) # Limited to 30 requests a minute / 1 request every 2 seconds.


def make_gh_request(request_type, user, org=None, project=None):
    r = None
    try:
        if request_type == ISSUES_URL:
            r = requests.get(f"{BASE_URL}/search/{request_type}{user} created:<{PROGRAM_DATE_END_YEAR}-{'{:0>{}}'.format(PROGRAM_DATE_END_MONTH, 2)}-{'{:0>{}}'.format(PROGRAM_DATE_END_DAY, 2)}&per_page=100", auth=(os.getenv("GITHUB_USERNAME"), os.getenv("GITHUB_ACCESS_TOKEN")))
        elif request_type == COMMITS_URL:
            r = requests.get(f"{BASE_URL}/search/{request_type}{user}created:<{PROGRAM_DATE_END_YEAR}-{'{:0>{}}'.format(PROGRAM_DATE_END_MONTH, 2)}-{'{:0>{}}'.format(PROGRAM_DATE_END_DAY, 2)}&per_page=100&&sort=author-date", auth=(os.getenv("GITHUB_USERNAME"), os.getenv("GITHUB_ACCESS_TOKEN")))
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
    if "items" in response:
        print(f"Total PRs/Issues: {len(response['items'])}")
        for item in response['items']:
            url = '/'.join(item['html_url'].split('/')[:5]).lower()
            
            # Check dates are within Batch Dates
            local_date = datetime.datetime.strptime(item['created_at'], GITHUB_DATE_FORMAT)
            if local_date >= BATCH_START and local_date <= BATCH_END:
                # Check PR is in the project
                if url in projects and "pull_request" in item:
                    helpers.add_to_db(email=fellow, github_id=fellows[fellow]['github_userid'], github_username=fellows[fellow]['github_username'],
                                    project=fellows[fellow]['project'], id=item['id'], url=item['html_url'], activity_type="Pull Request", message=item['title'], 
                                    number=item['number'], created_at=item['created_at'], closed_at=item['closed_at'], merged_at=item['pull_request']['merged_at'])
                    
                # Check Issue is in the project
                elif url in projects and "pull_request" not in item:
                    helpers.add_to_db(email=fellow, github_id=fellows[fellow]['github_userid'], github_username=fellows[fellow]['github_username'],
                                    project=fellows[fellow]['project'], id=item['id'], url=item['html_url'], activity_type="Issue", message=item['title'], 
                                    number=item['number'], created_at=item['created_at'], closed_at=item['closed_at'])
    else:
        print(response)

def find_commits(response, projects, fellow):
    if "items" in response:
        for item in response['items']:
            url = item['repository']['html_url']
            
            local_date = (datetime.datetime.strptime(item['commit']['author']['date'], GITHUB_COMMIT_DATE_FORMAT)).replace(tzinfo=utc)
            if local_date >= BATCH_START.replace(tzinfo=utc) and local_date <= BATCH_END.replace(tzinfo=utc):
                if url in projects:
                    helpers.add_to_db(email=fellow, github_id=fellows[fellow]['github_userid'], github_username=fellows[fellow]['github_username'], 
                                    project=fellows[fellow]['project'], id=item['sha'], url=item['html_url'], activity_type="Commit", message=item['commit']['message'], 
                                    number="Null", created_at=item['commit']['author']['date'])
    else:
        print(response)

def find_assigned_issues(response, fellow):
    if "errors" in response:
        return
    for issue in response:
        local_date = datetime.datetime.strptime(issue['created_at'], GITHUB_DATE_FORMAT)
        if local_date >= BATCH_START and local_date <= BATCH_END:
            helpers.add_to_db(email=fellow, github_id=fellows[fellow]['github_userid'], github_username=fellows[fellow]['github_username'], 
                              project=fellows[fellow]['project'], id=issue['id'], url=issue['html_url'], activity_type="Issue", message=issue['title'], 
                              number=issue['number'], created_at=issue['created_at'], closed_at=issue['closed_at'])

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

def find_merge_requests(response, fellow):
    for mr in response:
        local_date = datetime.datetime.strptime(mr['created_at'], GITLAB_DATE_FORMAT)
        if local_date >= BATCH_START and local_date <= BATCH_END:
            helpers.add_to_db(email=fellow, github_id=fellows[fellow]['github_userid'], github_username=fellows[fellow]['gitlab_username'], 
                              project=fellows[fellow]['project'], id=mr['iid'], url=mr['web_url'], activity_type="Pull Request", message=mr['title'], 
                              number=mr['iid'], created_at=mr['created_at'], closed_at=mr['closed_at'], merged_at=mr['merged_at'])


def find_gl_issues(response, fellow):
    for issue in response:
        local_date = datetime.datetime.strptime(issue['created_at'], GITLAB_DATE_FORMAT)
        if local_date >= BATCH_START and local_date <= BATCH_END:
            helpers.add_to_db(email=fellow, github_id=fellows[fellow]['github_userid'], 
                              github_username=fellows[fellow]['gitlab_username'], project=fellows[fellow]['project'], 
                              id=issue['iid'], url=issue['web_url'], activity_type="Issue", message=issue['title'], number=issue['iid'],
                              created_at=issue['created_at'], closed_at=issue['closed_at'])

def find_gl_commits(response, fellow):
    for commit in response:
         if datetime.datetime.strptime(commit['created_at'], GITLAB_DATE_FORMAT) >= BATCH_START and datetime.datetime.strptime(commit['created_at'], GITLAB_DATE_FORMAT) <= BATCH_END:
             pass


if __name__ == "__main__":
    term = "23.FAL.A"
    fellows = helpers.get_fellows(term)
    projects = helpers.get_projects(term)
    collect_data()
    fellows.clear()
    projects.clear()
    term = "23.FAL.B"
    fellows = helpers.get_fellows(term)
    projects = helpers.get_projects(term)
    collect_data()
    print(f"{term} Completed")
