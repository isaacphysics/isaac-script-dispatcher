import base64
import os
import time
import jwt
import requests
import subprocess
import dateutil.parser
from urllib.parse import urlparse, parse_qsl

from constants import *
from db_logic import get_token, save_token


# --- Authentication ---

def generate_jwt(app_id, private_key):
    payload = {
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
        "iss": app_id,
    }
    token = jwt.encode(payload, private_key, algorithm="RS256")
    return token


def get_installation_token(json_web_token, installation_id):
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {json_web_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    response = requests.post(url, headers=headers)

    if response.status_code == 201:
        return response.json()
    else:
        raise Exception(f"Failed to get installation token. Status code: {response.status_code}, Response: {response.text}")


# Has the side effect of updating the origin of the repos to use the new token - this is required for pushing changes
# and pulling from the repo
def get_github_token(logger=(lambda x: None)):
    # First check the DB to see if we have a valid token, or if it will expire soon (within 5 mins) - if so, generate a new one
    logger("Getting token")
    db_token = get_token()
    logger(f"Got token from DB: {db_token}")
    if db_token is None or float(db_token[2]) < time.time() + 300:
        # Get contents of PEM file
        with open(KEY_PATH, "r") as f:
            private_key = f.read()
        json_web_token = generate_jwt(os.getenv("GITHUB_APP_IDENTIFIER"), private_key)
        token = get_installation_token(json_web_token, os.getenv("GITHUB_INSTALLATION_ID"))
        save_token(token["token"], time.time(), dateutil.parser.isoparse(token["expires_at"]).timestamp())
        logger(f"Got new token: {token}")
        # Go though each repo and update the origin using the new token
        update_repo_origin(PHY_DATA_PATH, CONTENT_REPO_PATH_MAP["phy"], token["token"])
        update_repo_origin(CS_DATA_PATH, CONTENT_REPO_PATH_MAP["ada"], token["token"])
        return token["token"]
    else:
        return db_token[0]


# --- Issue management ---

def download_and_save_file(url, file_to_save_to, logger=lambda x: None):
    logger(f"Downloading file from {url} and storing in {file_to_save_to}")

    # Check that the url is at docs.google.com
    if "https://docs.google.com" not in url:
        raise Exception(f"URL is not a Google Docs URL: {url}")

    url_parts = list(urlparse(url))
    query = dict(parse_qsl(url_parts[4]))
    logger(f"Got query params: {query}")
    # Make sure single and output are in query
    if "single" not in query or query["single"] != "true" or "output" not in query and query["output"] != "csv":
        raise Exception(f"The Google Docs URL is not a CSV file, or doesn't have `single` set to `true`: {url}")

    response = requests.get(url)
    if response.status_code == 200:
        with open(file_to_save_to, "wb") as f:
            f.write(response.content)
    else:
        raise Exception(f"Failed to download file. Status code: {response.status_code}, Response: {response.text}")


def add_reaction_to_issue(token, issue_number, reaction):
    url = f"https://api.github.com/repos/{REPO_PATH}/issues/{issue_number}/reactions"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = {"content": reaction}

    return requests.post(url, headers=headers, json=data)


def add_comment_to_issue(token, issue_number, comment):
    url = f"https://api.github.com/repos/{REPO_PATH}/issues/{issue_number}/comments"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = {"body": comment}
    return requests.post(url, headers=headers, json=data)


def upload_file_to_github(token, job_id, file_path, repo_path_name):
    # Read file contents (base64 encoded)
    with open(file_path, "rb") as f:
        file_contents = f.read()

    url = f"https://api.github.com/repos/{REPO_PATH}/contents/outputs/{repo_path_name}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = {
        "message": f"Output files for job {job_id}",
        "content": base64.b64encode(file_contents).decode(),
        "branch": "master",
        "committer": {"name": BOT_USERNAME, "email": BOT_EMAIL}
    }

    return requests.put(url, headers=headers, json=data)


def create_pull_request(token, branch_name, subject, issue_number):
    url = f"https://api.github.com/repos/{CONTENT_REPO_PATH_MAP[subject]}/pulls"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = {
        "title": f"[Script] Output for issue {issue_number}",
        "head": branch_name,
        "base": "master",
        "body": f"This pull request was automatically generated.\n\n"
                f"These changes were requested in the issue: https://github.com/isaacphysics/isaac-dispatched-scripts/issues/{issue_number}\n\n"
                f"`Job id: {branch_name}`",
    }
    return requests.post(url, headers=headers, json=data)


# --- Content repository management ---

def update_repo_origin(repo_path, repo_url, token):
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "remote", "set-url",
             "origin", f"https://{BOT_USERNAME}:{token}@github.com/{repo_url}.git"],
            capture_output=True,
            check=True,
            text=True,
        )
        return {"success": True, "message": result.stdout}
    except subprocess.CalledProcessError as e:
        return {"success": False, "message": e.stderr}


def update_repo(repo_path, logger=lambda x: None):
    try:
        # First diff the local repo against the remote to see if there are any changes
        logger(f"Checking for changes in repo: {repo_path}")
        result = subprocess.run(
            ["git", "-C", repo_path, "diff", "master", "origin/master"],
            capture_output=True,
            check=True,
            text=True,
        )
        if result.stdout == "":
            logger(f"No changes in repo: {repo_path}")
            return {"success": True, "message": "No changes"}

        logger(f"Changes in repo: {repo_path}, pulling... (changes: {result.stdout[:100]}{'' if len(result.stdout) < 100 else '...'})")
        # Pull changes from remote, only from master with depth 1
        result = subprocess.run(
            ["git", "-C", repo_path, "pull", "origin", "master", "--depth=1"],
            capture_output=True,
            check=True,
            text=True,
        )
        # # If there are changes, fetch them
        # subprocess.run(
        #     ["git", "-C", repo_path, "fetch", "origin", "master"],
        #     capture_output=True,
        #     check=True,
        #     text=True,
        # )
        # # Then merge them
        # result = subprocess.run(
        #     ["git", "-C", repo_path, "merge", "origin/master"],
        #     capture_output=True,
        #     check=True,
        #     text=True,
        # )
        return {"success": True, "message": result.stdout}
    except subprocess.CalledProcessError as e:
        return {"success": False, "message": e.stderr}


def clone_if_needed(repo_path, repo_url, token, logger=lambda x: None):
    # First check if the repo dir already exists
    if not os.path.exists(repo_path):
        logger(f"Cloning repo: {repo_url}...")
        mycwd = os.getcwd()
        # If not, cd into "./data"
        os.chdir(DATA_PATH)
        # Clone the repo
        result = subprocess.run(
            ["git", "clone", f"https://{BOT_USERNAME}:{token}@github.com/{repo_url}.git"],
            capture_output=True,
            check=True,
            text=True,
        )
        # Change back to the original directory
        os.chdir(mycwd)
        logger(f"Cloned repo: {repo_url}!")
        return {"success": True, "message": result.stdout}
    else:
        return {"success": True, "message": "Repo already exists"}


def pull_repos(token, logger=lambda x: None):
    clone_if_needed(PHY_DATA_PATH, CONTENT_REPO_PATH_MAP["phy"], token, logger=logger)
    logger(f"Checking out master in {PHY_DATA_PATH}...")
    checkout_master(PHY_DATA_PATH)
    update_repo(PHY_DATA_PATH, logger=logger)
    clone_if_needed(CS_DATA_PATH, CONTENT_REPO_PATH_MAP["ada"], token, logger=logger)
    logger(f"Checking out master in {CS_DATA_PATH}...")
    checkout_master(CS_DATA_PATH)
    update_repo(CS_DATA_PATH, logger=logger)


def checkout_master(repo_path):
    # Check if master is already checked out
    result = subprocess.run(
        ["git", "-C", repo_path, "branch", "--show-current"],
        capture_output=True,
        check=True,
        text=True,
    )
    if str(result.stdout).strip("\n ") != "master":
        return subprocess.run(
            ["git", "-C", repo_path, "checkout", "master"],
            capture_output=True,
            check=True,
            text=True,
        )


def new_branch_and_push_changes(repo_path, branch_name):
    try:
        # First, set git config username and email
        subprocess.run(
            ["git", "-C", repo_path, "config", "user.name", BOT_USERNAME],
            capture_output=True,
            check=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", repo_path, "config", "user.email", BOT_EMAIL],
            capture_output=True,
            check=True,
            text=True,
        )

        # Check if there are any changes with diff-index
        result = subprocess.run(
            ["git", "-C", repo_path, "diff-index", "--quiet", "HEAD"],
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode == 0:
            # No changes, so we can just return
            return {"status": PushChangesStatus.NO_CHANGES, "message": "No changes to commit"}

        # Create new branch
        subprocess.run(
            ["git", "-C", repo_path, "checkout", "-b", branch_name],
            capture_output=True,
            check=True,
            text=True,
        )

        # Add all files
        subprocess.run(
            ["git", "-C", repo_path, "add", "-A"],
            capture_output=True,
            check=True,
            text=True,
        )

        # Commit
        subprocess.run(
            ["git", "-C", repo_path, "commit", "-m", f"Update for {branch_name}"],
            capture_output=True,
            check=True,
            text=True,
        )

        # Push branch (create it if it doesn't exist)
        result = subprocess.run(
            ["git", "-C", repo_path, "push", "--set-upstream", "origin", branch_name],
            capture_output=True,
            check=True,
            text=True,
        )

        # Checkout master again
        checkout_master(repo_path)

        # Delete local branch
        subprocess.run(
            ["git", "-C", repo_path, "branch", "-D", branch_name],
            capture_output=True,
            check=True,
            text=True,
        )

        return {"status": PushChangesStatus.SUCCESS, "message": result.stdout}
    except Exception as e:
        return {"status": PushChangesStatus.FAILED, "message": str(e)}
