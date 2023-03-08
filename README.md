# Project Metrics

A script to automatically pull the data from GitHub about Fellowship Projects and store them in a database.

## Setup 

Ensure Project Repos are in this [sheet](https://docs.google.com/spreadsheets/d/12quNi2TYuRK40woals-ABPT5NcsmhBmC_dHNU9rX1Do/edit#gid=0)

### Cron setup

```
crontab -e
```

Run daily at 8am GMT
```
0 8 * * * python3 script.py
```

### `.env`

23.SPR
```
FW_TERM=23.SPR
PROGRAM_DATE_YEAR=2023
PROGRAM_DATE_START_DAY=30
PROGRAM_DATE_END_DAY=22
PROGRAM_DATE_START_MONTH=1
PROGRAM_DATE_END_MONTH=4
```

23.MAR.PREP
```
FW_TERM=23.MAR.PREP
PROGRAM_DATE_YEAR=2023
PROGRAM_DATE_START_DAY=5
PROGRAM_DATE_END_DAY=25
PROGRAM_DATE_START_MONTH=3
PROGRAM_DATE_END_MONTH=3
```