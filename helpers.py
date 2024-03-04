import os
import time
import requests
import gspread
import datetime
from pytz import timezone
from oauth2client.service_account import ServiceAccountCredentials

scope = ['https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive"]

credentials = ServiceAccountCredentials.from_json_keyfile_name("gs_credentials.json", scope)
client = gspread.authorize(credentials)
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/12quNi2TYuRK40woals-ABPT5NcsmhBmC_dHNU9rX1Do")

program_date_format = "%Y-%m-%d"


def get_terms():
    dates_sh = sheet.worksheet('Fellowship Terms')

    terms = []
    for row in dates_sh.get_all_records():
        now = datetime.datetime.now()

        if datetime.datetime.strptime(str(row['Start_Date__c']).strip(), program_date_format) <= now and datetime.datetime.strptime(str(row['End_Date__c']).strip(), program_date_format) >= now:
            terms.append(str(row['Dot_Notation__c']).strip())
    return terms

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
            projects[row['Project Name']]['urls'].append(row['Repo Link'].lower())
            if row['GitLab Project ID'] != "":
                projects[row['Project Name']]['gitlab_ids'].append(row['GitLab Project ID'])
    return projects

def add_to_db(email, github_id, github_username, project, id, 
              url, activity_type, message, number, created_at, closed_at="Null", 
              merged_at="Null", additions="Null", deletions="Null", files_changed="Null"):
    if check_no_duplicates(url, id, closed_at, merged_at):
        row = [email,
               github_id,
               github_username,
               project,
               id,
               url,
               activity_type,
               message,
               number,
               standardize_datetime(created_at, activity_type),
               standardize_datetime(closed_at, activity_type),
               standardize_datetime(merged_at, activity_type),
               additions,
               deletions,
               files_changed]
        return row
    else:
        return []


def check_no_duplicates(url, id, closed_date="Null", merged_date="Null"):
    activities_data_sh = sheet.worksheet("activities_data")
    values = activities_data_sh.get("E2:E")
    time.sleep(5) # Prevent rate limiting
    for row, item in enumerate(values):
        if len(item) > 0 and str(item[0].strip()) == str(id):
            if closed_date != "Null" and closed_date != None:
                date = standardize_datetime(closed_date, "Pull Request")
                activities_data_sh.update_acell(f"K{row + 2}", date)                
            if merged_date != "Null" and merged_date != None:
                date = standardize_datetime(merged_date, "Pull Request")
                activities_data_sh.update_acell(f"L{row + 2}", date)
                if "https://github" in url:
                    org = url.split('/')[3]
                    repo_name = url.split('/')[4]
                    pull_id = int(url.split('/')[6])
                    pull_response = requests.get(f"https://api.github.com/repos/{org}/{repo_name}/pulls/{pull_id}", auth=(os.getenv("GH_USERNAME"), os.getenv("GH_ACCESS_TOKEN"))).json()
                    if pull_response:
                        activities_data_sh.update_acell(f"M{row + 2}", pull_response['additions'])
                        activities_data_sh.update_acell(f"N{row + 2}", pull_response['deletions'])
                        activities_data_sh.update_acell(f"O{row + 2}", pull_response['changed_files'])
            return False
    return True

def standardize_datetime(raw_datetime, actitivty_type):
    pr_format = "%Y-%m-%dT%H:%M:%S%z"
    commit_format = "%a %b %d %H:%M:%S %Y %z"

    if (actitivty_type == "Pull Request" or actitivty_type == "Issue") and raw_datetime != None and raw_datetime != "Null":
        return str(datetime.datetime.strptime(raw_datetime, pr_format))
    if actitivty_type == "Commit" and raw_datetime != None and raw_datetime != "Null":
        commit_date = datetime.datetime.strptime(raw_datetime, commit_format)
        return str(commit_date.astimezone(timezone('GMT')))
    return raw_datetime
