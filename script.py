from dotenv import load_dotenv
import json
from pprint import pprint
import requests
import time

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

BATCH_START = "2022-09-19T00:00:00Z" #22.FAL Start

def make_request(request_type, user):
    r = requests.get(BASE_URL + request_type + user + "&per_page=100")
    return r.json()    

def find_issues_prs(response, projects, fellow):
    for item in response["items"]:
        url = '/'.join(item['html_url'].split('/')[:5])
        #if item['created_at'] # Figure out data

        if url in projects and "pull_request" in item: # if it's a PR
            fellows[fellow]["prs"].append({
                "title": item['title'],
                "url": item['html_url'],
                "created_at": item['created_at'],
                "closed_at": item['closed_at'],
                "merged_at": item['pull_request']['merged_at']
            })
        elif url in projects and "pull_request" not in item: #if it's a PR
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
        if url in projects:
            fellows[fellow]['commits'].append({
                "title": item['title'],
                "url": item['html_url'],
                "created_at": item['commit']['author']['date']
            })


# issues/prs
for fellow in fellows:
    response = make_request(ISSUES_URL, fellows[fellow]['github_username'])
    fellow_projects = projects[fellows[fellow]['project']]
    find_issues_prs(response, fellow_projects, fellow)
    
    #response = make_request(COMMITS_URL, fellows[fellow]['github_username'])
    #find_commits(response, fellow_projects, fellow)

    pprint(fellows[fellow])
    break
    time.sleep(5)


