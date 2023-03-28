from constants import *
import subprocess

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
