import gspread
import time
from datetime import datetime
from pytz import timezone
from oauth2client.service_account import ServiceAccountCredentials

commit_format = "%a %b %d %H:%M:%S %Y %z"
pr_format = "%Y-%m-%dT%H:%M:%S%z"
new_format = "%Y-%m-%d %H:%M:%S%z"

example = '2023-02-21T18:40:42.806Z'

scope = ['https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive"]

credentials = ServiceAccountCredentials.from_json_keyfile_name(
    "gs_credentials.json", scope)
client = gspread.authorize(credentials)
sheet = client.open_by_url(
    "https://docs.google.com/spreadsheets/d/12quNi2TYuRK40woals-ABPT5NcsmhBmC_dHNU9rX1Do")

activities_data_sh = sheet.worksheet("activities_data")
values = activities_data_sh.get("K2:K")
counter = 0
for row, item in enumerate(values):
    if len(item) == 0:
        continue
    print(f"Before (Row: {row + 2}): {item[0]}")
    date = item[0]
    chunks = date.split(" ")


    new_date = ""
    if len(chunks) == 0 or item[0] == "Null":
        print("Skip")
        continue
    elif date.find(".") != -1:
        new_date = date.replace(date[date.find("."):date.find(".") + 4], "")
        if new_date.find("Z") == -1:
            temp = new_date.replace("T", " ")
            new_date = str(datetime.strptime(temp, new_format).astimezone(timezone('GMT')))
        else:
            new_date = str(datetime.strptime(new_date, pr_format))
    elif len(chunks) == 1:
        new_date = str(datetime.strptime(date, pr_format))
    elif len(chunks) == 2:
        new_date = str(datetime.strptime(date, new_format).astimezone(timezone('GMT')))
    elif len(chunks) == 6:
        new_date = str(datetime.strptime(date, commit_format).astimezone(timezone('GMT')))

    activities_data_sh.update_acell(f"K{row + 2}", new_date)
    print(f"After (Row: {row + 2}): {new_date}")
    counter += 1
    if counter == 50:
        print("Pause to avoid rate limiting")
        time.sleep(100) 
        counter = 0
