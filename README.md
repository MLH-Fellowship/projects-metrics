# Project Metrics

Python scripts to automatically pull Git data from GitHub and GitLab about Fellowship Projects and store them in a database.

## How Does It Work?

- Pull Requests and Issues are pulled using the GitHub and GitLab APIs. The GitHub API is using the Search API to search for a users PRs and then filters by repository after the request. GitLab is able to make a request to the specific repository for just that users Merge Requests.
- Commits are pulled by cloning the repository locally and running a `git log` command for commits made by the fellows email address. This will miss commits made under different email addresses.
- There are a number of `time.sleep(X)` in the code to prevent rate limiting to both the GitHub API as well as the Google Sheets API.
- Duplicates are checked against IDs. IDs can be commit shas, or unique IDs set by GitHub and GitLab. GitHub UIDs are not accessible on the website, only via the API so doesn't work for private repositories.

### `git_metrics.py`
Collects everything for fellows and projects during a specific fellowship batch and also starts the Orientation Data process. 

### `orientation_data.py`
Collects everything for fellows on their Orientation Project in Week 1 and 2 during a specific fellowship batch

### `cli.py`
All the logic for collecting commits by cloning the repository locally and running `git log` is in here.

### `helpers.py`
Tasks that both `git_metrics.py` and `orientation_data.py` need are centralized in here. This includes:
- Gets fellows from the Google Sheet (which gets them from Salesforce)
- Gets projects from the Google Sheet (which gets them from Salesforce)
- Adding new activity to the Google Sheet / DB. This includes checking for duplicates and calculating the number of lines added, deleted and changed for PRs via an additional request
- Standardizing the date format between Commits, GitHub API, and the GitLab API.

## Setup 

Ensure Project Repos and Term dates are in this [sheet](https://docs.google.com/spreadsheets/d/12quNi2TYuRK40woals-ABPT5NcsmhBmC_dHNU9rX1Do/edit#gid=0)

### Cron setup

```
crontab -e
```

Run every 4 hours
```
0 */4 * * * /bin/bash -c "/root/projects-metrics/gs_daily.sh"
```

