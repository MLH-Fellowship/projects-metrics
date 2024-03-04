import os
import subprocess

def collect_commits(url, fellow):
    commits = []
    working_dir = os.getcwd()

    if url == "":
        # URL is blank
        return commits
    try:
        os.makedirs("repos")
    except Exception as e:
        os.chdir(working_dir)
    

    os.chdir("repos")
    os.system(f"git clone {url} repo >/dev/null 2>&1")
    try:
        os.chdir("repo")
    except:
        # Repo invalid
        os.chdir(working_dir)
        return commits

    raw_output = subprocess.check_output("git log --author=" + fellow + " --all --stat | awk '{print}'", shell=True).rstrip()
    output = raw_output.decode('utf-8')
    lines = output.split('\n')

    sha = ""
    email = ""
    date = ""
    message = ""
    additions = 0
    deletions = 0
    files_changed = 0
    count = 0
    
    for line in lines:
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
                if 'file' in item:
                    files_changed = int(items[i - 1])
                if 'insertion' in item:
                    additions = int(items[i - 1])
                if 'deletion' in item:
                    deletions = int(items[i - 1])
            commits.append({
                "sha": sha,
                "email": email,
                "date": date,
                "message": message,
                "additions": additions,
                "deletions": deletions,
                "files_changed": files_changed
            })
            sha = ""
            email = ""
            date = ""
            message = ""
            additions = 0
            deletions = 0
            files_changed = 0
            count = 0
        count += 1
    if len(commits) > 0:
        print(f"Returning {len(commits)} commits")
    os.chdir("../")
    os.system("rm -rf repo")
    os.chdir("../")
    os.system("rm -rf repos")
    return commits
