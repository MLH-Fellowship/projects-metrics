import gspread
import pprint
from oauth2client.service_account import ServiceAccountCredentials

scope = ['https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive"]

credentials = ServiceAccountCredentials.from_json_keyfile_name("gs_credentials.json", scope)
client = gspread.authorize(credentials)
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/12quNi2TYuRK40woals-ABPT5NcsmhBmC_dHNU9rX1Do")

def get_duplicates():
    duplicates = {}

    activities_data_sh = sheet.worksheet("activities_data")
    values = activities_data_sh.get("E2:E")
    for row, item in enumerate(values):
        if len(item) > 0:
            value = str(item[0].strip())
            if value not in duplicates:
                duplicates[value] = []
            duplicates[value].append(row)
    
    for item in list(duplicates):
        if len(duplicates[item]) == 1:
            duplicates.pop(item)
    
    

    pprint.pprint(duplicates)
    print(f"Total duplicates: {len(duplicates)}")
get_duplicates()