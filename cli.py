import os
import subprocess
import pprint

commits = []

def clone_repo(repo):

    try:
        os.makedirs("repos")
    except Exception as e:
        print(e)
    
    os.chdir("repos")
    os.system(f"git clone {repo} repo")
    os.chdir("repo")
    raw_output = subprocess.check_output("git log --author=will@mlh.io --all --stat | awk '{print}'", shell=True).rstrip()
    os.chdir("../")
    os.system("rm -rf repo")
    output = raw_output.decode('utf-8')
    lines = output.split('\n')
    sha = ""
    email = ""
    date = ""
    message = ""
    additions = 0
    deletions = 0
    count = 0
    for index, line in enumerate(lines):
        print(f"{index}: {line}")
        items = line.strip().split(' ')
        if items[0] == "commit":
            sha = items[1]
        if items[0] == "Author:":
            start = line.find("<") + 1
            end = line.find(">")
            email = line[start:end]
        if items[0] == "Date:":
            date = ' '.join(items[3:9])
        if count == 6:
            message = line.strip()
        if "file changed" in line or "files changed" in line:
            for i, item in enumerate(items):
                if 'insertion' in item:
                    additions = items[i - 1]
                if 'deletion' in item:
                    deletions = items[i - 1]
            commits.append({
                "sha": sha,
                "email": email,
                "date": date,
                "message": message,
                "additions": additions,
                "deletions": deletions
            })
            sha = ""
            email = ""
            date = ""
            message = ""
            additions = 0
            deletions = 0
            count = 0
        count += 1
    pprint.pprint(commits)


# clone repo
clone_repo("git@github.com:MLH-Fellowship/gh-api-sandbox.git")

# git log command

# 