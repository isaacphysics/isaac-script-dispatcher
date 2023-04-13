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
