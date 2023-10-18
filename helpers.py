import os
import time
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials

scope = ['https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive"]

credentials = ServiceAccountCredentials.from_json_keyfile_name("gs_credentials.json", scope)
client = gspread.authorize(credentials)
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/12quNi2TYuRK40woals-ABPT5NcsmhBmC_dHNU9rX1Do")

def get_fellows(term):
    fellows = {}
    fellows_sh = sheet.worksheet("Enrolled Fellows")

    for row in fellows_sh.get_all_records():
        if row['Term'] == term:
            fellows[row['Application: Fellow Email Address']] = {
                "github_username": row['Application: GitHub Handle'],
                "project": row['Fellowship Project'],
                "gitlab_username": row['Application: GitLab Handle'],
                "github_userid": "Null",
                "term": row['Term'],
                "pod": row['Pod Name']
            }
    print(f"Total Fellows: {len(fellows)}")
    return fellows 

def get_projects(term):
    projects = {}
    projects_sh = sheet.worksheet("Project Repos")

    for row in projects_sh.get_all_records():
        if row['Term'] == term:
            if row['Project Name'] not in projects:
                projects[row['Project Name']] = {
                    "urls": [],
                    "gitlab_ids": []
                }
            projects[row['Project Name']]['urls'].append(row['Repo Link'])
            if row['GitLab Project ID'] != "":
                projects[row['Project Name']]['gitlab_ids'].append(row['GitLab Project ID'])

    return projects

def add_to_db(email, github_id, github_username, project, id, 
              url, type, message, number, created_at, closed_at="Null", 
              merged_at="Null", additions="Null", deletions="Null", files_changed="Null"):
    activities_data_sh = sheet.worksheet("activities_data")
    if check_no_duplicates(url, closed_at, merged_at):
        print(f"Url to add: {url}")
        activities_data_sh.append_row([email,
                                       github_id,
                                       github_username,
                                       project,
                                       id,
                                       url,
                                       type,
                                       message,
                                       number,
                                       created_at,
                                       closed_at,
                                       merged_at,
                                       additions,
                                       deletions,
                                       files_changed])
    else:
        print(f"Duplicate, skipping - {url}")


def check_no_duplicates(url, closed_date="Null", merged_date="Null"):
    activities_data_sh = sheet.worksheet("activities_data")
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
def get_pr_changed_lines(url, row):
    activities_data_sh = sheet.worksheet("activities_data")
    if "https://github" in url:
        org = url.split('/')[3]
        repo_name = url.split('/')[4]
        pull_id = int(url.split('/')[6])
        pull_response = requests.get(f"https://api.github.com/repos/{org}/{repo_name}/pulls/{pull_id}", auth=(os.getenv("GITHUB_USERNAME"), os.getenv("GITHUB_ACCESS_TOKEN"))).json()
        if pull_response:
            activities_data_sh.update_acell(f"M{row + 2}", pull_response['additions'])
            activities_data_sh.update_acell(f"N{row + 2}", pull_response['deletions'])
            activities_data_sh.update_acell(f"O{row + 2}", pull_response['changed_files'])