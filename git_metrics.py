from dotenv import load_dotenv
from pprint import pprint
import requests
import time
import datetime
import pytz
import os
import helpers
import orientation_data
import gspread
import cli
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()

fellows = {}
projects = {}

utc = pytz.utc

# Placeholder values
program_date_start_year = 2024
program_date_end_year = 2500
program_date_start_month = 1
program_date_end_month = 12
program_date_start_day = 1
program_date_end_day = 20

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

def setup_dates(term):
    dates_sh = sheet.worksheet('Fellowship Terms')

    for row in dates_sh.get_all_records():

        if str(row['Dot_Notation__c']).strip() == term:
            start_date = str(row['Start_Date__c']).split('-')
            end_date = str(row['End_Date__c']).split('-')
            
            global program_date_start_year
            global program_date_end_year
            global program_date_start_month
            global program_date_end_month
            global program_date_start_day
            global program_date_end_day
            global batch_start
            global batch_end

            program_date_start_year = int(start_date[0])
            program_date_end_year = int(end_date[0])
            program_date_start_month = int(start_date[1])
            program_date_end_month = int(end_date[1])
            program_date_start_day = int(start_date[2])
            program_date_end_day = int(end_date[2])

            batch_start = datetime.datetime(program_date_start_year, program_date_start_month, program_date_start_day)
            batch_end = datetime.datetime(program_date_end_year, program_date_end_month, program_date_end_day)
            return True
    return False
            
GITHUB_DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
GITHUB_COMMIT_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"
CLI_COMMIT_DATE_FORMAT = "%a %b %d %H:%M:%S %Y %z"
GITLAB_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
utc = pytz.utc

def collect_data():
    for fellow in fellows:
        print(f"Fetching data for: {fellows[fellow]['github_username']} | {fellows[fellow]['project']}")

        if fellows[fellow]['project'] not in projects:
            print(f"No Project Match for {fellows[fellow]['github_username']}. Skipping")
            continue
        fellow_projects = projects[fellows[fellow]['project']]

        if len(fellow_projects['urls']) < 1:
            print(f"No URLs for {fellows[fellow]['project']}. Skipping")
            continue

        
        print("Getting PRs/Issues")
        issues_response = make_gh_request(ISSUES_URL, fellows[fellow]['github_username'])
        if issues_response != None and "items" in issues_response:
            find_issues_prs(issues_response, fellow_projects['urls'], fellow)

        print("Getting commits")
        for url in fellow_projects['urls']:
            commits = cli.collect_commits(url, fellow)
            for commit in commits:
                local_date = datetime.datetime.strptime(commit['date'], CLI_COMMIT_DATE_FORMAT).replace(tzinfo=utc)
                if local_date > batch_start.replace(tzinfo=utc) and local_date < batch_end.replace(tzinfo=utc):
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

        if len(fellow_projects['gitlab_ids']) > 0:
            for gitlab_id in fellow_projects['gitlab_ids']:
                mr_response = make_gl_request("merge_request", fellows[fellow]['gitlab_username'], gitlab_id)
                if mr_response:
                    find_merge_requests(mr_response, fellow)
                issue_response = make_gl_request("issue", fellows[fellow]['gitlab_username'], gitlab_id)
                if issue_response:
                    find_gl_issues(issue_response, fellow)

def make_gh_request(request_type, user, org=None, project=None):
    r = None
    try:
        if request_type == ISSUES_URL:
            r = requests.get(f"{BASE_URL}/search/{request_type}{user} created:{program_date_start_year}-{'{:0>{}}'.format(program_date_start_month, 2)}-{'{:0>{}}'.format(program_date_start_day, 2)}..{program_date_end_year}-{'{:0>{}}'.format(program_date_end_month, 2)}-{'{:0>{}}'.format(program_date_end_day, 2)}&per_page=100&&sort=created",
                             auth=(os.getenv("GH_USERNAME"), os.getenv("GH_ACCESS_TOKEN")))
        elif request_type == COMMITS_URL:
            r = requests.get(f"{BASE_URL}/search/{request_type}{user} created:{program_date_start_year}-{'{:0>{}}'.format(program_date_start_month, 2)}-{'{:0>{}}'.format(program_date_start_day, 2)}..{program_date_end_year}-{'{:0>{}}'.format(program_date_end_month, 2)}-{'{:0>{}}'.format(program_date_end_day, 2)}&per_page=100&&sort=author-date",
                             auth=(os.getenv("GH_USERNAME"), os.getenv("GH_ACCESS_TOKEN")))
        elif request_type == ISSUE_URL:
            r = requests.get(f"{BASE_URL}/repos/{org}/{project}/{ISSUE_URL}={user}", auth=(os.getenv("GH_USERNAME"), os.getenv("GH_ACCESS_TOKEN")))
        return r.json()  
    except:
        pprint(r.json())
        return None
    
def make_gl_request(request_type, user, project_id):
    r = None
    try:
        if request_type == "merge_request":
            r = requests.get(f"https://gitlab.com/api/v4/projects/{project_id}/merge_requests?author_username={user}", headers={'PRIVATE-TOKEN': os.getenv("GL_ACCESS_TOKEN")})
        elif request_type == "issue":
            r = requests.get(f"https://gitlab.com/api/v4/projects/{project_id}/issues?assignee_username={user}", headers={'PRIVATE-TOKEN': os.getenv("GL_ACCESS_TOKEN")})
        elif request_type == "commit":
            r = requests.get(f"https://gitlab.com/api/v4/projects/{project_id}/commits", headers={'PRIVATE-TOKEN': os.getenv("GL_ACCESS_TOKEN")})
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
            if url in projects:
                local_date = datetime.datetime.strptime(item['created_at'], GITHUB_DATE_FORMAT)

                if local_date >= batch_start and local_date <= batch_end:
                    print(f"Date within range - proceeding with {url}")
                    
                    # Check PR is in the project
                    if "pull_request" in item:
                        helpers.add_to_db(email=fellow, github_id=fellows[fellow]['github_userid'], github_username=fellows[fellow]['github_username'],
                                        project=fellows[fellow]['project'], id=item['id'], url=item['html_url'], activity_type="Pull Request", message=item['title'], 
                                        number=item['number'], created_at=item['created_at'], closed_at=item['closed_at'], merged_at=item['pull_request']['merged_at'])
                        
                    # Check Issue is in the project
                    elif "pull_request" not in item:
                        helpers.add_to_db(email=fellow, github_id=fellows[fellow]['github_userid'], github_username=fellows[fellow]['github_username'],
                                        project=fellows[fellow]['project'], id=item['id'], url=item['html_url'], activity_type="Issue", message=item['title'], 
                                        number=item['number'], created_at=item['created_at'], closed_at=item['closed_at'])
                else:
                    print("Date not within batch")
    else:
        print(response)

def find_commits(response, projects, fellow):
    if "items" in response:
        for item in response['items']:
            url = item['repository']['html_url']
            
            local_date = (datetime.datetime.strptime(item['commit']['author']['date'], GITHUB_COMMIT_DATE_FORMAT)).replace(tzinfo=utc)
            if local_date >= batch_start.replace(tzinfo=utc) and local_date <= batch_end.replace(tzinfo=utc):
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
        if local_date >= batch_start and local_date <= batch_end:
            helpers.add_to_db(email=fellow, github_id=fellows[fellow]['github_userid'], github_username=fellows[fellow]['github_username'], 
                              project=fellows[fellow]['project'], id=issue['id'], url=issue['html_url'], activity_type="Issue", message=issue['title'], 
                              number=issue['number'], created_at=issue['created_at'], closed_at=issue['closed_at'])

def get_pr_changed_lines(url, row):
    if "https://github" in url:
        org = url.split('/')[3]
        repo_name = url.split('/')[4]
        pull_id = int(url.split('/')[6])
        pull_response = requests.get(f"{BASE_URL}/repos/{org}/{repo_name}/pulls/{pull_id}", auth=(os.getenv("GH_USERNAME"), os.getenv("GH_ACCESS_TOKEN"))).json()
        if pull_response:
            activities_data_sh.update_acell(f"M{row + 2}", pull_response['additions'])
            activities_data_sh.update_acell(f"N{row + 2}", pull_response['deletions'])
            activities_data_sh.update_acell(f"O{row + 2}", pull_response['changed_files'])

def find_merge_requests(response, fellow):
    for mr in response:
        local_date = datetime.datetime.strptime(mr['created_at'], GITLAB_DATE_FORMAT)
        if local_date >= batch_start and local_date <= batch_end:
            helpers.add_to_db(email=fellow, github_id=fellows[fellow]['github_userid'], github_username=fellows[fellow]['gitlab_username'], 
                              project=fellows[fellow]['project'], id=mr['iid'], url=mr['web_url'], activity_type="Pull Request", message=mr['title'], 
                              number=mr['iid'], created_at=mr['created_at'], closed_at=mr['closed_at'], merged_at=mr['merged_at'])


def find_gl_issues(response, fellow):
    for issue in response:
        local_date = datetime.datetime.strptime(issue['created_at'], GITLAB_DATE_FORMAT)
        if local_date >= batch_start and local_date <= batch_end:
            helpers.add_to_db(email=fellow, github_id=fellows[fellow]['github_userid'], 
                              github_username=fellows[fellow]['gitlab_username'], project=fellows[fellow]['project'], 
                              id=issue['iid'], url=issue['web_url'], activity_type="Issue", message=issue['title'], number=issue['iid'],
                              created_at=issue['created_at'], closed_at=issue['closed_at'])

def find_gl_commits(response, fellow):
    for commit in response:
         if datetime.datetime.strptime(commit['created_at'], GITLAB_DATE_FORMAT) >= batch_start and datetime.datetime.strptime(commit['created_at'], GITLAB_DATE_FORMAT) <= batch_end:
             pass


if __name__ == "__main__":
    terms = helpers.get_terms()
    print(f"Collecting data for {str(terms)}")
    for term in terms:
        fellows.clear()
        projects.clear()

        if setup_dates(term):
            fellows = helpers.get_fellows(term)
            projects = helpers.get_projects(term)
            collect_data()
            print(f"{term} Completed")
            now = datetime.datetime.now()

            if now < now + datetime.timedelta(days=21):
                print(f"Collecting Orientation Data for {term}")
                projects.clear()
                projects = orientation_data.get_orientation_projects(term)
                orientation_data.collect_orientation_data(fellows, projects)
                print(f"Orientation Data completed for {term}")

        else:
            print(f"Error with dates in Salesforce for {term}")
