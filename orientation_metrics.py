from pprint import pprint
import requests
import time
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import git_metrics
import helpers
import cli


class OrientationMetrics(git_metrics.GitMetrics):

    def __init__(self, term):
        super().__init__(term)
        self.orientation_projects = self.sheet.worksheet("Orientation Projects")
        self.orientation_data = self.sheet.worksheet("Orientation Data")
        self.fellows_sh = self.sheet.worksheet("Enrolled Fellows")
        self.projects = self.get_orientation_projects()

    def get_orientation_projects(self):
        projects = {}
        for row in self.orientation_projects.get_all_records():
            if row['Term'] == self.term:
                if row['Project Name'] not in projects:
                    projects[row['Project Name']] = {
                        "urls": [],
                        "term": row['Term']
                    }
                projects[row['Project Name']]['urls'].append(row['Repo Link'])
        print(f"Total Projects: {len(self.projects)}")
        return projects

    def collect_data(self):
        for fellow in self.fellows:
            print(f"Fetching data for: {self.fellows[fellow]['github_username']}")
            for project in self.projects:
            
                # PRs
                issues_response = self.make_gh_request(self.ISSUES_URL, self.fellows[fellow]['github_username'])
                if issues_response != None and "items" in issues_response:
                    for item in issues_response["items"]:
                        url = '/'.join(item['html_url'].split('/')[:5])
                        # Check PR is in the project
                        if url in self.projects[project]['urls'] and "pull_request" in item and self.check_no_duplicates(item['html_url'], item['id'], item['closed_at'], item['pull_request']['merged_at']): # if it's a PR
                            print(f"Adding to db - {item['html_url']}")
                            self.project_data.append([fellow,
                                                          self.fellows[fellow]['term'],
                                                          self.fellows[fellow]['pod'],
                                                          self.fellows[fellow]['github_username'],
                                                          item['id'],
                                                          item['html_url'],
                                                          "Pull Request", 
                                                          item['title'],
                                                          item['number'],
                                                          helpers.standardize_datetime(item['created_at'], "Pull Request"),
                                                          helpers.standardize_datetime(item['closed_at'], "Pull Request"),
                                                          helpers.standardize_datetime(item['pull_request']['merged_at'], "Pull Request")])
                        # Check Issue is in the project
                        elif url in self.projects[project]['urls'] and "pull_request" not in item and self.check_no_duplicates(item['html_url'], item['id'], item['closed_at']): #if it's an Issue
                            print(f"Adding to db - {item['html_url']}")
                            self.project_data.append([fellow,
                                                      self.fellows[fellow]['term'],
                                                      self.fellows[fellow]['pod'],
                                                      self.fellows[fellow]['github_username'],
                                                      item['id'],
                                                      item['html_url'],
                                                      "Issue", 
                                                      item['title'],
                                                      item['number'],
                                                      helpers.standardize_datetime(item['created_at'], "Issue"),
                                                      helpers.standardize_datetime(item['closed_at'], "Issue"),
                                                      "Null"])
                else:
                    print("No PRs/Issues fetched")
                    
                # Commits
                for url in self.projects[project]['urls']:
                    commits = cli.collect_commits(url, fellow)
                    for commit in commits:
                        if self.check_no_duplicates(f"{url}/commit/{commit['sha']}", commit['sha']):
                            print(f"Adding to db - {url}/commit/{commit['sha']}")
                            self.project_data.append([fellow,
                                                      self.fellows[fellow]['term'],
                                                      self.fellows[fellow]['pod'],
                                                      self.fellows[fellow]['github_username'],
                                                      commit['sha'],
                                                      f"{url}/commit/{commit['sha']}",
                                                      "Commit",
                                                      commit['message'],
                                                      "Null",
                                                      helpers.standardize_datetime(commit['date'], "Commit"),
                                                      "Null",
                                                      "Null"])

                # Get commits via API to fill in any blanks
                commits_response = self.make_gh_request(self.COMMITS_URL, self.fellows[fellow]['github_username'])
                if commits_response != None and "items" in commits_response:
                    for item in commits_response['items']:
                        url = item['repository']['html_url']
                        if url in self.projects:
                            if self.check_no_duplicates(url, item['sha']):
                                print(f"Adding to db - {url}")
                                self.project_data.append([fellow,
                                                          self.fellows[fellow]['term'],
                                                          self.fellows[fellow]['pod'],
                                                          self.fellows[fellow]['github_username'],
                                                          item['sha'],
                                                          url,
                                                          "Commit",
                                                          item['commit']['message'],
                                                          "Null",
                                                          helpers.standardize_datetime(issue['created_at'], "Commit"),
                                                          "Null",
                                                          "Null"])

                # Issues
                for url in self.projects[project]['urls']:
                    if "https://github" in url:
                        org = url.split('/')[3]
                        repo_name = url.split('/')[4]
                        gh_issue_response = self.make_gh_request(self.ISSUE_URL, self.fellows[fellow]['github_username'], org=org, project=repo_name)
                        
                        for issue in gh_issue_response:
                            if self.check_no_duplicates(issue['html_url'], issue['id'], issue['closed_at']):
                                print(f"Adding to db - {issue['html_url']}")
                                row = [fellow,
                                       self.fellows[fellow]['term'],
                                       self.fellows[fellow]['pod'],
                                       self.fellows[fellow]['github_username'],
                                       issue['id'],
                                       issue['html_url'],
                                       "Issue", 
                                       issue['title'],
                                       issue['number'],
                                       helpers.standardize_datetime(issue['created_at'], "Issue"),
                                       issue['closed_at'],
                                       "Null"]
                                if len(row) > 0:
                                    self.project_data.append(row)

        self.orientation_data.append_rows(self.project_data)
        self.project_data.clear()

    def check_no_duplicates(self, url, id, closed_date="Null", merged_date="Null"):
        values = self.orientation_data.get("E2:E")
        time.sleep(5)
        for row, item in enumerate(values):
            if str(item[0].strip()) == str(id):
                if closed_date != "Null" and closed_date != None:
                    date = helpers.standardize_datetime(closed_date, "Pull Request")
                    self.orientation_data.update_acell(f"K{row + 2}", date)                
                if merged_date != "Null" and merged_date != None:
                    date = helpers.standardize_datetime(merged_date, "Pull Request")
                    self.orientation_data.update_acell(f"L{row + 2}", date)
                    if "https://github" in url:
                        org = url.split('/')[3]
                        repo_name = url.split('/')[4]
                        pull_id = int(url.split('/')[6])
                        pull_response = requests.get(f"{self.BASE_URL}/repos/{org}/{repo_name}/pulls/{pull_id}", auth=(os.getenv("GH_USERNAME"), os.getenv("GH_ACCESS_TOKEN"))).json()
                        if pull_response:
                            self.orientation_data.update_acell(f"M{row + 2}", pull_response['additions'])
                            self.orientation_data.update_acell(f"N{row + 2}", pull_response['deletions'])
                            self.orientation_data.update_acell(f"O{row + 2}", pull_response['changed_files'])
                return False
        return True
