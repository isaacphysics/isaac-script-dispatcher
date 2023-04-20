import json
import os
import signal
import subprocess
import time
from multiprocessing import Process

from db_logic import get_next_job, update_job_status
from constants import *
from github import pull_repos, get_github_token, add_reaction_to_issue, add_comment_to_issue, upload_file_to_github
from script_manager import SCRIPTS


# Method to append to debug log file, creating it if it doesn't exist. A fairly robust way to debug the worker process.
def log_to_file(message):
    with open("debug.log", "a") as f:
        f.write(message + "\n")


def run_python_script(script_name, job_id, subject, args):
    if not os.path.exists(f"{SCRIPTS_PATH}/{script_name}_script.py"):
        return {"error": f"Script `{script_name}` does not exist"}

    try:
        result = subprocess.run(
            [
                "python", f"{SCRIPTS_PATH}/{script_name}_script.py", "-j", job_id, "--subject", subject, *args
            ],
            capture_output=True,
            check=True,
            text=True,
        )
        return {"result": result.stdout}
    except subprocess.CalledProcessError as e:
        return {"error": e.stderr}
    except Exception as e:
        return {"error": str(e)}


def run_script_and_close_issue(job, job_id, token):
    # First pair argument names with values
    args = [i for j in zip(map(lambda x: f"--{x['param']}", SCRIPTS[job["script_name"]]["arguments"]), job["arguments"]) for i in j]
    result = run_python_script(job["script_name"], job_id, job["subject"], args)
    if "error" in result:
        if comment(token, job_id, job["issue_number"],
                   f"### Error running script:\n\n> {result['error']}\n\nPlease contact the team for assistance, quoting the job ID: {job_id}"):
            update_job_status(job_id, JobRunStatus.FAILED, result)
    else:
        try:
            # Upload each output file to GitHub and get the URLs
            urls = []
            for f in os.listdir(f"{OUTPUT_PATH}/{job_id}"):
                response = upload_file_to_github(token, job_id, f"{OUTPUT_PATH}/{job_id}/{f}", f"{job_id}/{f}")
                response_json = response.json()
                if not response.status_code == 201 or "html_url" not in response_json["content"]:
                    if comment(token, job_id, job["issue_number"],
                               f"### Error running script:\n\n> {response.text}\n\nPlease contact the team for assistance, quoting the job ID: {job_id}"):
                        update_job_status(job_id, JobRunStatus.FAILED,
                                          {"error": f"Failed to upload file: {response.text}"})
                urls.append({"file": f, "url": response_json["content"]["html_url"]})

            # Add output to issue, and add a links to each output file
            output = f"\n\n```\n{result['result']}\n```" if result["result"] else ""
            download_urls = "\n\n" + "\n".join([f"- [{url['file']}]({url['url']})" for url in urls])
            if comment(token, job_id, job["issue_number"], f"### Output{output}{download_urls}"):
                update_job_status(job_id, JobRunStatus.FINISHED, result)
        except Exception as e:
            if comment(token, job_id, job["issue_number"],
                       f"### Error generating output files:\n\n> {str(e)}\n\nPlease contact the team for assistance, quoting the job ID: {job_id}.\n\nScript output:\n\n```{result['result']}```"):
                update_job_status(job_id, JobRunStatus.FAILED, {"error": str(e)})


def comment(token, job_id, issue_number, message):
    response = add_comment_to_issue(token, issue_number, message)
    if not response.status_code == 201:
        update_job_status(job_id, JobRunStatus.FAILED, {"error": f"Failed to add comment: {response.text}"})
        return False
    return True


def ask_for_script_arguments(job, job_id, script_info, token):
    # Check which argument we need to ask for next
    next_arg_index = len(job["arguments"])
    next_arg = script_info["arguments"][next_arg_index]
    next_arg_message = f"""
### Script argument: {next_arg['title']}

{next_arg['description']}

Example:
```
{next_arg['example']}
```

Please reply to this comment with the argument, or delete this issue to cancel the job.
"""

    # Add a comment to the issue asking for the next argument
    if comment(token, job_id, job["issue_number"], next_arg_message):
        update_job_status(job_id, JobRunStatus.PAUSED, {"argument_index": next_arg_index})


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

    # Add a reaction to the issue to show that we've seen it (if it's new)
    if job["issue_status"] == "opened":
        response = add_reaction_to_issue(token, job["issue_number"], "rocket")
        if not response.status_code == 201:
            update_job_status(job_id, JobRunStatus.FAILED, {"error": f"Failed to add initial reaction: {response.text}"})
            return

    # Check if the script exists and the subject is valid
    if job["script_name"] not in SCRIPTS or job["subject"] not in ["phy", "ada"]:
        if comment(token, job_id, job["issue_number"], f"### Error running script:\n\n> Invalid script name or subject.\n\nPlease delete this issue and contact the team for assistance, quoting the job ID: {job_id}"):
            update_job_status(job_id, JobRunStatus.FAILED, {"error": "Invalid script name or subject"})
        return

    script_info = SCRIPTS[job["script_name"]]

    # Accumulate arguments for the script, if needed
    if len(job["arguments"]) < len(script_info["arguments"]):
        ask_for_script_arguments(job, job_id, script_info, token)
    else:
        # Run the script
        run_script_and_close_issue(job, job_id, token)


JOB_HANDLERS = {
    JobType.ISSUE: github_issue_confirm_job
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
