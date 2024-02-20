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
import cli

load_dotenv()

# Connect to Google Sheets
scope = ['https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive"]

credentials = ServiceAccountCredentials.from_json_keyfile_name("gs_credentials.json", scope)
client = gspread.authorize(credentials)

sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/12quNi2TYuRK40woals-ABPT5NcsmhBmC_dHNU9rX1Do")

fellows_sh = sheet.worksheet("Enrolled Fellows")
orientation_projects = sheet.worksheet("Orientation Projects")
orientation_data = sheet.worksheet("Orientation Data")

def get_orientation_projects(term):
    projects = {}
    for row in orientation_projects.get_all_records():
        if row['Term'] == term:
            if row['Project Name'] not in projects:
                projects[row['Project Name']] = {
                    "urls": [],
                    "term": row['Term']
                }
            projects[row['Project Name']]['urls'].append(row['Repo Link'])
    print(f"Total Projects: {len(projects)}")
    return projects

def collect_orientation_data(fellows, projects):
    for fellow in fellows:
        print(f"Fetching data for: {fellows[fellow]['github_username']}")
        for project in projects:
        
            # PRs
            print("Collecting PRs and Issues....")
            issues_response = git_metrics.make_gh_request(git_metrics.ISSUES_URL, fellows[fellow]['github_username'])
            if issues_response != None and "items" in issues_response:
                for item in issues_response["items"]:
                    url = '/'.join(item['html_url'].split('/')[:5])
                    # Check PR is in the project
                    if url in projects[project]['urls'] and "pull_request" in item and check_no_duplicates(item['html_url'], item['id'], item['closed_at'], item['pull_request']['merged_at']): # if it's a PR
                        print(f"Adding to db - {item['html_url']}")
                        orientation_data.append_row([fellow,
                                                        fellows[fellow]['term'],
                                                        fellows[fellow]['pod'],
                                                        fellows[fellow]['github_username'],
                                                        item['id'],
                                                        item['html_url'],
                                                        "Pull Request", 
                                                        item['title'],
                                                        item['number'],
                                                        helpers.standardize_datetime(item['created_at'], "Pull Request"),
                                                        helpers.standardize_datetime(item['closed_at'], "Pull Request"),
                                                        helpers.standardize_datetime(item['pull_request']['merged_at'], "Pull Request")])
                    # Check Issue is in the project
                    elif url in projects[project]['urls'] and "pull_request" not in item and check_no_duplicates(item['html_url'], item['id'], item['closed_at']): #if it's an Issue
                        print(f"Adding to db - {item['html_url']}")
                        orientation_data.append_row([fellow,
                                                        fellows[fellow]['term'],
                                                        fellows[fellow]['pod'],
                                                        fellows[fellow]['github_username'],
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
            print("Collecting commits....")
            for url in projects[project]['urls']:
                commits = cli.collect_commits(url, fellow)
                for commit in commits:
                    if check_no_duplicates(f"{url}/commit/{commit['sha']}", commit['sha']):
                        print(f"Adding to db - {url}/commit/{commit['sha']}")
                        orientation_data.append_row([fellow,
                                                        fellows[fellow]['term'],
                                                        fellows[fellow]['pod'],
                                                        fellows[fellow]['github_username'],
                                                        commit['sha'],
                                                        f"{url}/commit/{commit['sha']}",
                                                        "Commit",
                                                        commit['message'],
                                                        "Null",
                                                        helpers.standardize_datetime(commit['date'], "Commit"),
                                                        "Null",
                                                        "Null"])
                    else:
                        print(f"Duplicate, skipping - {url}/commit/{commit['sha']}")

            # Issues
            print("Collecting issues....")
            for url in projects[project]['urls']:
                if "https://github" in url:
                    org = url.split('/')[3]
                    repo_name = url.split('/')[4]
                    gh_issue_response = git_metrics.make_gh_request(git_metrics.ISSUE_URL, fellows[fellow]['github_username'], org=org, project=repo_name)
                    
                    for issue in gh_issue_response:
                        if check_no_duplicates(issue['html_url'], issue['id'], issue['closed_at']):
                            print(f"Adding to db - {issue['html_url']}")
                            orientation_data.append_row([fellow,
                                                            fellows[fellow]['term'],
                                                            fellows[fellow]['pod'],
                                                            fellows[fellow]['github_username'],
                                                            issue['id'],
                                                            issue['html_url'],
                                                            "Issue", 
                                                            issue['title'],
                                                            issue['number'],
                                                            helpers.standardize_datetime(issue['created_at'], "Issue"),
                                                            issue['closed_at'],
                                                            "Null"])
                        else:
                            print(f"Duplicate, skipping - {issue['html_url']}")

def check_no_duplicates(url, id, closed_date="Null", merged_date="Null"):
    values = orientation_data.get("E2:E")
    time.sleep(5)
    for row, item in enumerate(values):
        if str(item[0].strip()) == str(id):
            if closed_date != "Null" and closed_date != None:
                date = helpers.standardize_datetime(closed_date, "Pull Request")
                orientation_data.update_acell(f"K{row + 2}", date)                
            if merged_date != "Null" and merged_date != None:
                date = helpers.standardize_datetime(merged_date, "Pull Request")
                orientation_data.update_acell(f"L{row + 2}", date)
                get_pr_changed_lines(url, row)
            return False
    return True

def get_pr_changed_lines(url, row):
    if "https://github" in url:
        org = url.split('/')[3]
        repo_name = url.split('/')[4]
        pull_id = int(url.split('/')[6])
        pull_response = requests.get(f"{git_metrics.BASE_URL}/repos/{org}/{repo_name}/pulls/{pull_id}", auth=(os.getenv("GH_USERNAME"), os.getenv("GH_ACCESS_TOKEN"))).json()
        if pull_response:
            orientation_data.update_acell(f"M{row + 2}", pull_response['additions'])
            orientation_data.update_acell(f"N{row + 2}", pull_response['deletions'])
            orientation_data.update_acell(f"O{row + 2}", pull_response['changed_files'])
