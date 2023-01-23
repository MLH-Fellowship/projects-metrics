from dotenv import load_dotenv
import json
from pprint import pprint
import requests
import time
import datetime
import pytz
import os

load_dotenv()

fellows = {}
projects = {}

with open('fellows.csv') as f:
    lines = f.readlines()
    for line in lines:
        fellow = line.strip().split(",")
        fellows[fellow[0]] = {
            "github_username": fellow[1],
            "project": fellow[2],
            "prs": [],
            "issues": [],
            "commits": []
        }

with open('repos.json') as f:
    projects = json.load(f)

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
    for item in response["items"]:
        url = '/'.join(item['html_url'].split('/')[:5])
        
        # Check dates are within Batch Dates
        if datetime.datetime.strptime(item['created_at'], GITHUB_DATE_FORMAT) >= BATCH_START and datetime.datetime.strptime(item['created_at'], GITHUB_DATE_FORMAT) <= BATCH_END:
            # Check PR is in the project
            if url in projects and "pull_request" in item: # if it's a PR
                fellows[fellow]["prs"].append({
                    "title": item['title'],
                    "url": item['html_url'],
                    "created_at": item['created_at'],
                    "closed_at": item['closed_at'],
                    "merged_at": item['pull_request']['merged_at']
                })
            # Check Issue is in the project
            elif url in projects and "pull_request" not in item: #if it's an Issue
                fellows[fellow]["issues"].append({
                    "title": item['title'],
                    "url": item['html_url'],
                    "created_at": item['created_at'],
                    "closed_at": item['closed_at'],
                })

# this needs to identify forks
def find_commits(response, projects, fellow):
    for item in response['items']:
        url = item['repository']['html_url']

        if (datetime.datetime.strptime(item['commit']['author']['date'], GITHUB_COMMIT_DATE_FORMAT)).replace(tzinfo=utc) >= BATCH_START.replace(tzinfo=utc) and datetime.datetime.strptime(item['commit']['author']['date'], GITHUB_COMMIT_DATE_FORMAT).replace(tzinfo=utc) <= BATCH_END.replace(tzinfo=utc):
            if url in projects:
                fellows[fellow]['commits'].append({
                    "commit_message": item['commit']['message'],
                    "url": item['repository']['html_url'],
                    "created_at": item['commit']['author']['date']
                })


# Get info per fellow
for fellow in fellows:
    fellow_projects = projects[fellows[fellow]['project']]
    
    issues_response = make_request(ISSUES_URL, fellows[fellow]['github_username'])
    find_issues_prs(issues_response, fellow_projects, fellow)
    
    commits_response = make_request(COMMITS_URL, fellows[fellow]['github_username'])
    find_commits(commits_response, fellow_projects, fellow)

    pprint(fellows[fellow])

    # Add fellow to database, checking for duplicate data

    break
    time.sleep(5)


