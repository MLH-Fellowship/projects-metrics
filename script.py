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
import pandas as pd

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
fellows_sh = sheet.worksheet("Enrolled Fellows (22.FAL)")
projects_sh = sheet.worksheet("22.FAL Project Repos")

#
for row in fellows_sh.get_all_records():
    fellows[row['Application: Fellow Email Address']] = {
        "github_username": row['GitHub Handle'],
        "project": row['Fellowship Project']
    }

for row in projects_sh.get_all_records():
    if row['Project Name'] in projects:
        projects[row['Project Name']].append(row['Repo Link'])
    else:
        projects[row['Project Name']] = [row['Repo Link']]

BASE_URL = "https://api.github.com/search/"

COMMITS_URL = "commits?q=author:"
ISSUES_URL = "issues?q=author:"

BATCH_START = datetime.datetime(2022, 9, 19)
BATCH_END = datetime.datetime(2022, 12, 10)
GITHUB_DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
GITHUB_COMMIT_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"
utc = pytz.utc

def make_request(request_type, user):
    r = None
    if request_type == ISSUES_URL:
        r = requests.get(BASE_URL + request_type + user + "&per_page=100", auth=(os.getenv("GITHUB_USERNAME"), os.getenv("GITHUB_ACCESS_TOKEN")))
    elif request_type == COMMITS_URL:
        r = requests.get(BASE_URL + request_type + user + "&per_page=100&&sort=author-date", auth=(os.getenv("GITHUB_USERNAME"), os.getenv("GITHUB_ACCESS_TOKEN")))

    return r.json()    

def find_issues_prs(response, projects, fellow):
    if "items" not in response:
        pprint(response)
    for item in response["items"]:
        url = '/'.join(item['html_url'].split('/')[:5])
        
        # Check dates are within Batch Dates
        if datetime.datetime.strptime(item['created_at'], GITHUB_DATE_FORMAT) >= BATCH_START and datetime.datetime.strptime(item['created_at'], GITHUB_DATE_FORMAT) <= BATCH_END:
            # Check PR is in the project
            if url in projects and "pull_request" in item: # if it's a PR
                
                activities_data_sh.append_row([fellow,
                                                fellows[fellow]['github_username'],
                                                fellows[fellow]['project'],
                                                item['html_url'],
                                                "Pull Request", 
                                                item['title'],
                                                item['number'],
                                                item['created_at'],
                                                item['closed_at'],
                                                item['pull_request']['merged_at']])
            # Check Issue is in the project
            elif url in projects and "pull_request" not in item: #if it's an Issue
                
                activities_data_sh.append_row([fellow,
                                                fellows[fellow]['github_username'],
                                                fellows[fellow]['project'],
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
            if url in projects:
                activities_data_sh.append_row([fellow,
                                                fellows[fellow]['github_username'],
                                                fellows[fellow]['project'],
                                                item['html_url'],
                                                "Commit", 
                                                item['commit']['message'],
                                                "Null",
                                                item['commit']['author']['date'],
                                                "Null",
                                                "Null"])

# Get info per fellow
for fellow in fellows:
    print(fellow)
    
    if fellows[fellow]['project'] not in projects:
        continue
    
    fellow_projects = projects[fellows[fellow]['project']]
    
    issues_response = make_request(ISSUES_URL, fellows[fellow]['github_username'])
    find_issues_prs(issues_response, fellow_projects, fellow)
    time.sleep(2)
    commits_response = make_request(COMMITS_URL, fellows[fellow]['github_username'])
    find_commits(commits_response, fellow_projects, fellow)

    time.sleep(5) # Limited to 30 requests a minute / 1 request every 2 seconds.
