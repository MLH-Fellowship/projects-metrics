# Project Metrics

A script to automatically pull the data from GitHub about Fellowship Projects and store them in a database.

## Cron setup

```
crontab -e
```

Run daily at 8am GMT
```
0 8 * * * python3 script.py
```