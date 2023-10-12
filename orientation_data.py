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
import git_metrics
import helpers

load_dotenv()

fellows = {}
projects = {}

# Connect to Google Sheets
scope = ['https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive"]

credentials = ServiceAccountCredentials.from_json_keyfile_name("gs_credentials.json", scope)
client = gspread.authorize(credentials)

sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/12quNi2TYuRK40woals-ABPT5NcsmhBmC_dHNU9rX1Do")

fellows_sh = sheet.worksheet("Enrolled Fellows")
orientation_projects = sheet.worksheet("Orientation Projects")
orientation_data = sheet.worksheet("Orientation Data")

def collect_orientation_data():
    for fellow in fellows:
        for project in projects:
        
            # PRs
            issues_response = git_metrics.make_gh_request(git_metrics.ISSUES_URL, fellows[fellow]['github_username'])
            if issues_response != None and "items" in issues_response:
                if "items" not in issues_response:
                    pprint(issues_response)
                for item in issues_response["items"]:
                    url = '/'.join(item['html_url'].split('/')[:5])
                                
                    # Check PR is in the project
                    if url in projects[project]['urls'] and "pull_request" in item and check_no_duplicates(item['html_url'], item['closed_at'], item['pull_request']['merged_at']): # if it's a PR
                        
                        orientation_data.append_row([fellow,
                                                        fellows[fellow]['term'],
                                                        fellows[fellow]['pod'],
                                                        fellows[fellow]['github_username'],
                                                        item['id'],
                                                        item['html_url'],
                                                        "Pull Request", 
                                                        item['title'],
                                                        item['number'],
                                                        item['created_at'],
                                                        item['closed_at'],
                                                        item['pull_request']['merged_at']])
                    # Check Issue is in the project
                    elif url in projects[project]['urls'] and "pull_request" not in item and check_no_duplicates(item['html_url'], item['closed_at']): #if it's an Issue
                        
                        orientation_data.append_row([fellow,
                                                        fellows[fellow]['term'],
                                                        fellows[fellow]['pod'],
                                                        fellows[fellow]['github_username'],
                                                        item['id'],
                                                        item['html_url'],
                                                        "Issue", 
                                                        item['title'],
                                                        item['number'],
                                                        item['created_at'],
                                                        item['closed_at'],
                                                        "Null"])


                time.sleep(5)
                
                # Commits
                commits_response = git_metrics.make_gh_request(git_metrics.COMMITS_URL, fellows[fellow]['github_username'])
                if commits_response != None and "items" in issues_response:
                    pprint(commits_response)
                    for item in commits_response['items']:
                        url = item['repository']['html_url']
            
                        if url in projects[project]['urls'] and check_no_duplicates(item['html_url']):
                            orientation_data.append_row([fellow,
                                                            fellows[fellow]['term'],
                                                            fellows[fellow]['pod'],
                                                            fellows[fellow]['github_username'],
                                                            item['sha'],
                                                            item['html_url'],
                                                            "Commit", 
                                                            item['commit']['message'],
                                                            "Null",
                                                            item['commit']['author']['date'],
                                                            "Null",
                                                            "Null"])
                time.sleep(5)
            
            
            for url in projects[project]['urls']:
                if "https://github" in url:
                    org = url.split('/')[3]
                    repo_name = url.split('/')[4]
                    gh_issue_response = git_metrics.make_gh_request(git_metrics.ISSUE_URL, fellows[fellow]['github_username'], org=org, project=repo_name)
                    
                    for issue in gh_issue_response:
                        if check_no_duplicates(issue['html_url'], issue['closed_at']):
                            orientation_data.append_row([fellow,
                                                            fellows[fellow]['term'],
                                                            fellows[fellow]['pod'],
                                                            fellows[fellow]['github_username'],
                                                            issue['id'],
                                                            issue['html_url'],
                                                            "Issue", 
                                                            issue['title'],
                                                            issue['number'],
                                                            issue['created_at'],
                                                            issue['closed_at'],
                                                            "Null"])
                    time.sleep(5)
            
def check_no_duplicates(url, closed_date="Null", merged_date="Null"):
    values = orientation_data.get("F2:F")
    for row, item in enumerate(values):
        if item[0].strip() == url:
            if closed_date != "Null" and closed_date != None:
                orientation_data.update_acell(f"K{row + 2}", closed_date)                
            if merged_date != "Null" and merged_date != None:
                orientation_data.update_acell(f"L{row + 2}", merged_date)
                get_pr_changed_lines(url, row)
            time.sleep(0.1)

            return False
    return True

def get_pr_changed_lines(url, row):
    if "https://github" in url:
        org = url.split('/')[3]
        repo_name = url.split('/')[4]
        pull_id = int(url.split('/')[6])
        pull_response = requests.get(f"{git_metrics.BASE_URL}/repos/{org}/{repo_name}/pulls/{pull_id}", auth=(os.getenv("GITHUB_USERNAME"), os.getenv("GITHUB_ACCESS_TOKEN"))).json()
        if pull_response:
            orientation_data.update_acell(f"M{row + 2}", pull_response['additions'])
            orientation_data.update_acell(f"N{row + 2}", pull_response['deletions'])
            orientation_data.update_acell(f"O{row + 2}", pull_response['changed_files'])

if __name__ == "__main__":
    term = "23.FAL.B"
    helpers.get_fellows(term)
    helpers.get_projects(term)
    collect_orientation_data()
    print(f"Orientation Data Completed for {term}")