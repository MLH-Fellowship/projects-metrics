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

load_dotenv()

# Connect to Google Sheets
scope = ['https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive"]

credentials = ServiceAccountCredentials.from_json_keyfile_name("gs_credentials.json", scope)
client = gspread.authorize(credentials)

sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/12quNi2TYuRK40woals-ABPT5NcsmhBmC_dHNU9rX1Do")

activities_data_sh = sheet.worksheet("activities_data")
fellows_sh = sheet.worksheet("Enrolled Fellows (22.FAL,23.SPR)")
projects_sh = sheet.worksheet("Project Repos (22.FAL,23.SPR)")

def update_stats(additions, deletions, files_changed):
    activities_data_sh.update_acell(f"M{row + 2}", additions)
    time.sleep(1)
    activities_data_sh.update_acell(f"N{row + 2}", deletions)
    time.sleep(1)
    activities_data_sh.update_acell(f"O{row + 2}", files_changed)
    time.sleep(1)

if __name__ == "__main__":
    data = activities_data_sh.get("F2:G")
    for row, item in enumerate(data):
        print(item)
        if "https://github" in item[0]:
            org = item[0].strip().split('/')[3]
            repo_name = item[0].strip().split('/')[4]
            id = item[0].strip().split('/')[6]
            if item[1] == 'Pull Request':
                pull_response = requests.get(f"https://api.github.com/repos/{org}/{repo_name}/pulls/{int(id)}", auth=(os.getenv("GITHUB_USERNAME"), os.getenv("GITHUB_ACCESS_TOKEN"))).json()
                if pull_response:
                    update_stats(pull_response['additions'], pull_response['deletions'], pull_response['changed_files'])
            elif item[1] == 'Commit':
                commit_response = requests.get(f"https://api.github.com/repos/{org}/{repo_name}/commits/{id}", auth=(os.getenv("GITHUB_USERNAME"), os.getenv("GITHUB_ACCESS_TOKEN"))).json()
                if commit_response:
                    update_stats(commit_response['stats']['additions'], commit_response['stats']['deletions'], len(commit_response['files'])) 
            time.sleep(3)
