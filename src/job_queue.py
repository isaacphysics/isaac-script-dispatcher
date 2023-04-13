import os
import signal
import subprocess
import time
from multiprocessing import Process

import requests

from db_logic import get_next_job, update_job_status
from constants import *
from github import pull_repos, get_github_token


# Method to append to debug log file, creating it if it doesn't exist. A fairly robust way to debug the worker process.
def log_to_file(message):
    with open("debug.log", "a") as f:
        f.write(message + "\n")


class GracefulKiller:
    kill_now = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self):
        self.kill_now = True


# --- Job handlers ---

def github_issue_confirm_job(job_id, job):
    token = get_github_token()  # Can give param logger=log_to_file to debug
    # log_to_file(f"Job ID {job_id}: Got token! {token}")
    # log_to_file(f"Job ID {job_id}: Issue number: {job['issue_number']}")
    url = f"https://api.github.com/repos/{REPO_PATH}/issues/{job['issue_number']}/reactions"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = {"content": "eyes"}

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 201:
        # log_to_file(f"Job ID {job_id}: Successfully added reaction to issue {job['issue_number']}")
        update_job_status(job_id, JobRunStatus.FINISHED, {"result": "Reaction added"})
    else:
        # log_to_file(f"Job ID {job_id}: Failed to add reaction to issue {job['issue_number']}")
        update_job_status(job_id, JobRunStatus.FAILED, {"error": f"Failed to add reaction: {response.text}"})


def refresh_job(job_id, job):
    # log_to_file(f"Job ID {job_id}: Refreshing content repositories.")
    pull_repos()
    update_job_status(job_id, JobRunStatus.FINISHED, {"result": "Refreshed the content repositories"})


def script_job(job_id, job):
    script_name = job["script_name"]
    # log_to_file(f"Job ID {job_id}: Running script {script_name}.")

    # Ensure the script exists
    if not os.path.exists(f"{SCRIPTS_PATH}/{script_name}_script.py"):
        update_job_status(job_id, JobRunStatus.FAILED, {"error": f"Script {script_name} does not exist"})
        return

    # Ensure the specified arguments to the script are valid

    try:
        result = subprocess.run(
            [
                "python", f"{SCRIPTS_PATH}/{script_name}_script.py", "-j", job_id
            ],
            capture_output=True,
            check=True,
            text=True,
        )
        update_job_status(job_id, JobRunStatus.FINISHED, {"result": result.stdout, "output_file": f"{job_id}.csv"})
    except subprocess.CalledProcessError as e:
        update_job_status(job_id, JobRunStatus.FAILED, {"error": e.stderr})
    except Exception as e:
        update_job_status(job_id, JobRunStatus.FAILED, {"error": str(e)})


JOB_HANDLERS = {
    JobType.REFRESH: refresh_job,
    JobType.SCRIPT: script_job,
    JobType.NEW_ISSUE: github_issue_confirm_job
}


# --- Main worker loop ---

def process_job_queue():
    killer = GracefulKiller()
    while not killer.kill_now:
        # Get the next job from the queue, sleeping if there are none
        job = get_next_job()
        if not job:
            # log_to_file("No jobs in queue, sleeping.")
            time.sleep(NO_JOB_SLEEP_TIME)
            continue

        job_id = job["id"]

        # log_to_file(f"Job ID {job_id}: Processing job {job}.")

        # Check we have a handler for the job type
        if job["job_type"] not in JOB_HANDLERS:
            update_job_status(job_id, JobRunStatus.FAILED, {"error": f"Unknown job type {job['job_type']}"})
            continue

        # Run the handler for this job type
        try:
            JOB_HANDLERS[job["job_type"]](job_id, job)
        except Exception as e:
            update_job_status(job_id, JobRunStatus.FAILED, {"error": str(e)})
            continue


def init_worker_process():
    queue_process = Process(target=process_job_queue, daemon=False)
    queue_process.start()
