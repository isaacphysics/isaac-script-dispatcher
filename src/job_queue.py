import os
import signal
import subprocess
import time
from multiprocessing import Process

from db_logic import get_next_job, update_job_status
from constants import *
from github import pull_repos, get_github_token, add_reaction_to_issue, add_comment_to_issue, upload_file_to_github


# Method to append to debug log file, creating it if it doesn't exist. A fairly robust way to debug the worker process.
def log_to_file(message):
    with open("debug.log", "a") as f:
        f.write(message + "\n")


def run_script(script_name, job_id):
    if not os.path.exists(f"{SCRIPTS_PATH}/{script_name}_script.py"):
        return {"error": f"Script `{script_name}` does not exist"}

    try:
        result = subprocess.run(
            [
                "python", f"{SCRIPTS_PATH}/{script_name}_script.py", "-j", job_id
            ],
            capture_output=True,
            check=True,
            text=True,
        )
        return {"result": result.stdout, "output_file": f"{job_id}.csv"}
    except subprocess.CalledProcessError as e:
        return {"error": e.stderr}
    except Exception as e:
        return {"error": str(e)}


def comment(token, job_id, issue_number, message):
    response = add_comment_to_issue(token, issue_number, message)
    if not response.status_code == 201:
        update_job_status(job_id, JobRunStatus.FAILED, {"error": f"Failed to add comment: {response.text}"})
        return False
    return True


class GracefulKiller:
    kill_now = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self):
        self.kill_now = True


# --- Job handlers ---

def github_issue_confirm_job(job_id, job):
    # First make sure that the content repos are up to date
    pull_repos()

    # Get a GitHub token
    token = get_github_token()  # Can give param logger=log_to_file to debug
    response = add_reaction_to_issue(token, job["issue_number"], "eyes")

    if not response.status_code == 201:
        update_job_status(job_id, JobRunStatus.FAILED, {"error": f"Failed to add initial reaction: {response.text}"})

    result = run_script(job["script_name"], job_id)
    if "error" in result:
        if comment(token, job["issue_number"], f"### Error running script:\n\n> {result['error']}\n\nPlease contact the team for assistance."):
            update_job_status(job_id, JobRunStatus.FAILED, result)
    else:
        # Upload the file to GitHub and get the URL
        response = upload_file_to_github(token, job["issue_number"], f"{OUTPUT_PATH}/{result['output_file']}")
        response_json = response.json()
        if not response.status_code == 201 or "download_url" not in response_json["content"]:
            if comment(token, job_id, job["issue_number"], f"### Error running script:\n\n> {response.text}\n\nPlease contact the team for assistance."):
                update_job_status(job_id, JobRunStatus.FAILED, {"error": f"Failed to upload file: {response.text}"})
        # Add output to issue, and add a link to the output file
        output = f"\n\n```{result['result']}```" if result["result"] else ""
        if comment(token, job_id, job["issue_number"], f"### Output{output}\n\n[Download output file]({response_json['content']['download_url']})"):
            update_job_status(job_id, JobRunStatus.FINISHED, result)


def refresh_job(job_id, job):
    # log_to_file(f"Job ID {job_id}: Refreshing content repositories.")
    pull_repos()
    update_job_status(job_id, JobRunStatus.FINISHED, {"result": "Refreshed the content repositories"})


def script_job(job_id, job):
    result = run_script(job["script_name"], job_id)
    if "error" in result:
        update_job_status(job_id, JobRunStatus.FAILED, result)
    else:
        update_job_status(job_id, JobRunStatus.FINISHED, result)


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
