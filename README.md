# Project Metrics

A script to automatically pull the data from GitHub about Fellowship Projects and store them in a database.

## Setup 

### Fellows CSV

Columns go:
- Email Address
- GitHub Username
- Partner (to match with `repos.json` formatting)

### Repos JSON

JSON format that has a key (which is the partner name that matches the one in `fellows.csv`) to an array of projects URLs on GitHub

### Cron setup

```
crontab -e
```

Run daily at 8am GMT
```
0 8 * * * python3 script.py
```