import base64
import os
import time
import jwt
import requests
import subprocess
import dateutil.parser

from constants import *
from db_logic import get_token, save_token


# --- Authentication ---

def generate_jwt(app_id, private_key):
    payload = {
        "iat": int(time.time()),
        "exp": int(time.time()) + 600,
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


def get_github_token(logger=(lambda x: None)):
    # First check the DB to see if we have a valid token, or if it will expire soon - if so, generate a new one
    logger("Getting token")
    db_token = get_token()
    logger(f"Got token from DB: {db_token}")
    if db_token is None or float(db_token[2]) < time.time() + 60:
        # Get contents of PEM file
        with open(KEY_PATH, "r") as f:
            private_key = f.read()
        json_web_token = generate_jwt(os.getenv("GITHUB_APP_IDENTIFIER"), private_key)
        token = get_installation_token(json_web_token, os.getenv("GITHUB_INSTALLATION_ID"))
        save_token(token["token"], time.time(), dateutil.parser.isoparse(token["expires_at"]).timestamp())
        logger(f"Got new token: {token}")
        return token["token"]
    else:
        return db_token[0]


# --- Issue management ---

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
    # FIXME don't use my (Chris P's) email address
    data = {
        "message": f"Output file for job {job_id}",
        "content": base64.b64encode(file_contents).decode(),
        "branch": "master",
        "committer": {"name": "isaac-script-dispatcher", "email": "33040507+chrisjpurdy@users.noreply.github.com"}
    }

    return requests.put(url, headers=headers, json=data)


def create_pull_request(token, branch_name, subject):
    url = f"https://api.github.com/repos/{CONTENT_REPO_PATH_MAP[subject]}/pulls"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = {
        "title": f"Update for {branch_name}",
        "head": branch_name,
        "base": "master",
        "body": f"isaac-script-dispatcher[bot] automatically generated this pull request. Job id: {branch_name}.",
    }
    return requests.post(url, headers=headers, json=data)

# --- Content repository management ---

def update_repo(repo_path):
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "pull"],
            capture_output=True,
            check=True,
            text=True,
        )
        return {"success": True, "message": result.stdout}
    except subprocess.CalledProcessError as e:
        return {"success": False, "message": e.stderr}


def pull_repos():
    update_repo(SCRIPTS_PATH)
    update_repo(PHY_DATA_PATH)
    update_repo(CS_DATA_PATH)


def new_branch_and_push_changes(repo_path, branch_name):
    try:
        # First, set git config username and email
        subprocess.run(
            ["git", "-C", repo_path, "config", "user.name", "chrisjpurdy"],
            capture_output=True,
            check=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", repo_path, "config", "user.email", "33040507+chrisjpurdy@users.noreply.github.com"],
            capture_output=True,
            check=True,
            text=True,
        )
        # Create new branch
        subprocess.run(
            ["git", "-C", repo_path, "checkout", "-b", branch_name],
            capture_output=True,
            check=True,
            text=True,
        )
        # Add all files
        subprocess.run(
            ["git", "-C", repo_path, "add", "."],
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
        return {"success": True, "message": result.stdout}
    except subprocess.CalledProcessError as e:
        return {"success": False, "message": e.stderr}


def checkout_branch(repo_path, branch_name):
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "checkout", branch_name],
            capture_output=True,
            check=True,
            text=True,
        )
        return {"success": True, "message": result.stdout}
    except subprocess.CalledProcessError as e:
        return {"success": False, "message": e.stderr}
