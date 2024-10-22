from dotenv import load_dotenv
from pprint import pprint
import requests
import time
import datetime
import pytz
import os
import helpers
import orientation_metrics
import gspread
import cli
from oauth2client.service_account import ServiceAccountCredentials
import traceback

load_dotenv()

class GitMetrics:
    BASE_URL = "https://api.github.com"

    COMMITS_URL = "commits?q=author:"
    ISSUES_URL = "issues?q=author:"
    ISSUE_URL = "issues?assignee"

    GITHUB_DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
    GITHUB_COMMIT_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"
    CLI_COMMIT_DATE_FORMAT = "%a %b %d %H:%M:%S %Y %z"
    GITLAB_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

    def __init__(self, term):
        self.term = term
        self.fellows = helpers.get_fellows(term)
        self.projects = helpers.get_projects(term)
        self.project_data = []

        self.scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        self.credentials = ServiceAccountCredentials.from_json_keyfile_name("gs_credentials.json", self.scope)
        self.client = gspread.authorize(self.credentials)
        self.sheet = self.client.open_by_url("https://docs.google.com/spreadsheets/d/12quNi2TYuRK40woals-ABPT5NcsmhBmC_dHNU9rX1Do")
        self.activities_data_sh = self.sheet.worksheet("activities_data")

        self.utc = pytz.utc
        dates_sh = self.sheet.worksheet('Fellowship Terms')
        for row in dates_sh.get_all_records():

            if str(row['Dot_Notation__c']).strip() == term:
                start_date = str(row['Start_Date__c']).split('-')
                end_date = str(row['End_Date__c']).split('-')
            
                self.program_date_start_year = int(start_date[0])
                self.program_date_end_year = int(end_date[0])
                self.program_date_start_month = int(start_date[1])
                self.program_date_end_month = int(end_date[1])
                self.program_date_start_day = int(start_date[2])
                self.program_date_end_day = int(end_date[2])
                self.batch_start = datetime.datetime(self.program_date_start_year, self.program_date_start_month, self.program_date_start_day)
                self.batch_end = datetime.datetime(self.program_date_end_year, self.program_date_end_month, self.program_date_end_day)

    def collect_data(self):
        try:
            for fellow in self.fellows:
                print(f"Fetching data for: {self.fellows[fellow]['github_username']} | {self.fellows[fellow]['project']}")

                if self.fellows[fellow]['project'] not in self.projects:
                    print(f"No Project Match for {self.fellows[fellow]['github_username']}. Skipping")
                    continue
                fellow_projects = self.projects[self.fellows[fellow]['project']]

                if len(fellow_projects['urls']) < 1:
                    print(f"No URLs for {self.fellows[fellow]['project']}. Skipping")
                    continue
                
                # Getting PRs/Issues
                issues_response = self.make_gh_request(self.ISSUES_URL, self.fellows[fellow]['github_username'])
                if issues_response != None and "items" in issues_response:
                    self.find_issues_prs(issues_response, fellow_projects['urls'], fellow)

                # Getting commits
                cli_urls = []
                for url in fellow_projects['urls']:
                    commits = cli.collect_commits(url, fellow)
                    for commit in commits:
                        local_date = datetime.datetime.strptime(commit['date'], self.CLI_COMMIT_DATE_FORMAT).replace(tzinfo=self.utc)
                        if local_date > self.batch_start.replace(tzinfo=self.utc) and local_date < self.batch_end.replace(tzinfo=self.utc):
                            cli_urls.append(f"{url}/commit/{commit['sha']}")
                            row = helpers.add_to_db(email=fellow, github_id=self.fellows[fellow]['github_userid'], github_username=self.fellows[fellow]['github_username'], 
                                            project=self.fellows[fellow]['project'], id=commit['sha'], url=f"{url}/commit/{commit['sha']}", activity_type="Commit", message=commit['message'], number="Null", 
                                            created_at=commit['date'], additions=commit['additions'], deletions=commit['deletions'], files_changed=commit['files_changed'])
                            if len(row) > 0:
                                self.project_data.append(row)

                # Run commit check again using API for commits not collected using email. Using GitHub username to collect onwards
                commits_response = self.make_gh_request(self.COMMITS_URL, self.fellows[fellow]['github_username'])
                if commits_response != None and "items" in commits_response:
                    self.find_commits(commits_response, fellow_projects['urls'], fellow, cli_urls)
                cli_urls.clear()

                # Getting Issues
                for url in fellow_projects['urls']:
                    if "https://github" in url:
                        org = url.split('/')[3]
                        repo_name = url.split('/')[4]
                        gh_issue_response = self.make_gh_request(self.ISSUE_URL, self.fellows[fellow]['github_username'], org=org, project=repo_name)
                        self.find_assigned_issues(gh_issue_response, fellow)

                # Getting GitLab Merge Requests
                if len(fellow_projects['gitlab_ids']) > 0:
                    for gitlab_id in fellow_projects['gitlab_ids']:
                        mr_response = self.make_gl_request("merge_request", self.fellows[fellow]['gitlab_username'], gitlab_id)
                        if mr_response:
                            self.find_merge_requests(mr_response, fellow)
                        issue_response = self.make_gl_request("issue", self.fellows[fellow]['gitlab_username'], gitlab_id)
                        if issue_response:
                            self.find_gl_issues(issue_response, fellow)
        except Exception as e:
            print(e)             
            pprint(self.fellows)
            traceback.print_exc()
        print(f"Total rows to add: {len(self.project_data)}")               
        self.activities_data_sh.append_rows(self.project_data)
        self.project_data.clear()

    def make_gh_request(self, request_type, user, org=None, project=None):
        r = None
        try:
            if request_type == self.ISSUES_URL:
                r = requests.get(f"{self.BASE_URL}/search/{request_type}{user} created:{self.program_date_start_year}-{'{:0>{}}'.format(self.program_date_start_month, 2)}-{'{:0>{}}'.format(self.program_date_start_day, 2)}..{self.program_date_end_year}-{'{:0>{}}'.format(self.program_date_end_month, 2)}-{'{:0>{}}'.format(self.program_date_end_day, 2)}&per_page=100&&sort=created",
                                auth=(os.getenv("GH_USERNAME"), os.getenv("GH_ACCESS_TOKEN")))
            elif request_type == self.COMMITS_URL:
                r = requests.get(f"{self.BASE_URL}/search/{request_type}{user} created:{self.program_date_start_year}-{'{:0>{}}'.format(self.program_date_start_month, 2)}-{'{:0>{}}'.format(self.program_date_start_day, 2)}..{self.program_date_end_year}-{'{:0>{}}'.format(self.program_date_end_month, 2)}-{'{:0>{}}'.format(self.program_date_end_day, 2)}&per_page=100&&sort=author-date",
                                auth=(os.getenv("GH_USERNAME"), os.getenv("GH_ACCESS_TOKEN")))
            elif request_type == self.ISSUE_URL:
                r = requests.get(f"{self.BASE_URL}/repos/{org}/{project}/{self.ISSUE_URL}={user}", auth=(os.getenv("GH_USERNAME"), os.getenv("GH_ACCESS_TOKEN")))
            return r.json()  
        except:
            pprint(r.json())
            return None
    
    def make_gl_request(self, request_type, user, project_id):
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

    def find_issues_prs(self, response, projects, fellow):
        if "items" in response:
            print(f"Total PRs/Issues fetched: {len(response['items'])}")
            for item in response['items']:
                url = '/'.join(item['html_url'].split('/')[:5]).lower()
                
                # Check dates are within Batch Dates
                if url in projects:
                    local_date = datetime.datetime.strptime(item['created_at'], self.GITHUB_DATE_FORMAT)

                    if local_date >= self.batch_start and local_date <= self.batch_end: 
                        # Check PR is in the project
                        if "pull_request" in item:
                            row = helpers.add_to_db(email=fellow, github_id=self.fellows[fellow]['github_userid'], github_username=self.fellows[fellow]['github_username'],
                                            project=self.fellows[fellow]['project'], id=item['id'], url=item['html_url'], activity_type="Pull Request", message=item['title'], 
                                            number=item['number'], created_at=item['created_at'], closed_at=item['closed_at'], merged_at=item['pull_request']['merged_at'])
                            if len(row) > 0:
                                self.project_data.append(row)
                            
                        # Check Issue is in the project
                        elif "pull_request" not in item:
                            row = helpers.add_to_db(email=fellow, github_id=self.fellows[fellow]['github_userid'], github_username=self.fellows[fellow]['github_username'],
                                            project=self.fellows[fellow]['project'], id=item['id'], url=item['html_url'], activity_type="Issue", message=item['title'], 
                                            number=item['number'], created_at=item['created_at'], closed_at=item['closed_at'])
                            if len(row) > 0:
                                self.project_data.append(row)
        else:
            print(response)

    def find_commits(self, response, projects, fellow, cli_urls):
        if "items" in response:
            print(f"Total Commits fetched via API: {len(response['items'])}")
            for item in response['items']:
                url = item['repository']['html_url']
                
                local_date = (datetime.datetime.strptime(item['commit']['author']['date'], self.GITHUB_COMMIT_DATE_FORMAT)).replace(tzinfo=self.utc)
                if local_date >= self.batch_start.replace(tzinfo=self.utc) and local_date <= self.batch_end.replace(tzinfo=self.utc):
                    if url in projects and url not in cli_urls:
                        row = helpers.add_to_db(email=fellow, github_id=self.fellows[fellow]['github_userid'], github_username=self.fellows[fellow]['github_username'], 
                                        project=self.fellows[fellow]['project'], id=item['sha'], url=item['html_url'], activity_type="Commit", message=item['commit']['message'], 
                                        number="Null", created_at=item['commit']['author']['date'])
                        if len(row) > 0:
                            self.project_data.append(row)
        else:
            print(response)

    def find_assigned_issues(self, response, fellow):
        if "errors" in response:
            return
        for issue in response:
            local_date = datetime.datetime.strptime(issue['created_at'], self.GITHUB_DATE_FORMAT)
            if local_date >= self.batch_start and local_date <= self.batch_end:
                row = helpers.add_to_db(email=fellow, github_id=self.fellows[fellow]['github_userid'], github_username=self.fellows[fellow]['github_username'], 
                                project=self.fellows[fellow]['project'], id=issue['id'], url=issue['html_url'], activity_type="Issue", message=issue['title'], 
                                number=issue['number'], created_at=issue['created_at'], closed_at=issue['closed_at'])
                if len(row) > 0:
                    self.project_data.append(row)

    def find_merge_requests(self, response, fellow):
        for mr in response:
            local_date = datetime.datetime.strptime(mr['created_at'], self.GITLAB_DATE_FORMAT)
            if local_date >= self.batch_start and local_date <= self.batch_end:
                row = helpers.add_to_db(email=fellow, github_id=self.fellows[fellow]['github_userid'], github_username=self.fellows[fellow]['gitlab_username'], 
                                project=self.fellows[fellow]['project'], id=mr['iid'], url=mr['web_url'], activity_type="Pull Request", message=mr['title'], 
                                number=mr['iid'], created_at=mr['created_at'], closed_at=mr['closed_at'], merged_at=mr['merged_at'])
                if len(row) > 0:
                    self.project_data.append(row)

    def find_gl_issues(self, response, fellow):
        for issue in response:
            local_date = datetime.datetime.strptime(issue['created_at'], self.GITLAB_DATE_FORMAT)
            if local_date >= self.batch_start and local_date <= self.batch_end:
                row = helpers.add_to_db(email=fellow, github_id=self.fellows[fellow]['github_userid'], 
                                github_username=self.fellows[fellow]['gitlab_username'], project=self.fellows[fellow]['project'], 
                                id=issue['iid'], url=issue['web_url'], activity_type="Issue", message=issue['title'], number=issue['iid'],
                                created_at=issue['created_at'], closed_at=issue['closed_at'])
                if len(row) > 0:
                    self.project_data.append(row)


if __name__ == "__main__":
    terms = helpers.get_terms()
    print(f"Collecting data for {str(terms)}")
    for term in terms:
        program_metrics = GitMetrics(term)
        program_metrics.collect_data()

        now = datetime.datetime.now()
        if now < program_metrics.batch_start + datetime.timedelta(days=21):
            print(f"Collecting Orientation Metrics for {term}")
            program_orientation_metrics = orientation_metrics.OrientationMetrics(term)
            program_orientation_metrics.collect_data()
            print(f"Orientation Data completed for {term}")
