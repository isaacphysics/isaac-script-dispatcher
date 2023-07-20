import os
import shutil
import signal
import subprocess
import time
from multiprocessing import Process

import requests

from db_logic import get_next_job, update_job_status
from constants import *
from git_logic import new_branch_and_push_changes, pull_repos, get_github_token, add_reaction_to_issue, \
    add_comment_to_issue, upload_file_to_github, create_pull_request, download_and_save_file, clone_if_needed
from script_manager import SCRIPTS, GOOGLE_DOC_PUBLISH_HOW_TO


def logger(message):
    # Post log message to localhost:5000/log
    requests.post("http://localhost:5000/log", json={"message": f"[WORKER] {message}"})


# Comment on the GitHub issue, failing the job and returning False if the comment fails to post
def comment(token, job_id, issue_number, message):
    logger(f"Commenting on issue {issue_number} with message: {message[:100]}" + ("..." if len(message) > 100 else ""))
    response = add_comment_to_issue(token, issue_number, message)
    if not response.status_code == 201:
        update_job_status(job_id, JobRunStatus.FAILED, {"error": f"Failed to add comment: {response.text}"}, logger=logger)
        return False
    return True


def run_python_script(script_name, job_id, subject, args):
    if not os.path.exists(f"{SCRIPT_DISPATCHER_SCRIPTS_SUBDIR}/{script_name}_script.py"):
        return {"error": f"Script `{script_name}` does not exist"}

    try:
        result = subprocess.run(
            [
                "python", f"{SCRIPT_DISPATCHER_SCRIPTS_SUBDIR}/{script_name}_script.py", "-j", job_id, "--subject", subject, *args
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


# TODO This should validate and sanitise the arguments before running the script
def get_arguments(job_id, arg_infos, args):
    logger(f"Formatting and validating arguments for job {job_id}")
    input_dir_created = False
    arg_list = []
    for i, (arg_info, arg) in enumerate(zip(arg_infos, args)):
        if arg_info["type"] == "file":
            if not input_dir_created:
                os.makedirs(f"{INPUT_PATH}/{job_id}", exist_ok=True)
                input_dir_created = True
            file_name = f"{INPUT_PATH}/{job_id}/arg_{i}.{arg_info['file_type']}"
            download_and_save_file(arg, file_name, logger=logger)
            arg_list.append(f"--{arg_info['param']}")
            arg_list.append(file_name)
        else:
            arg_list.append(f"--{arg_info['param']}")
            arg_list.append(arg)
    return arg_list


def run_script_and_close_issue(job, job_id, token):
    script_info = SCRIPTS[job["script_name"]]

    args = get_arguments(job_id, script_info["arguments"], job["arguments"])
    logger(f"Running script `{job['script_name']}` with args: {args}")
    result = run_python_script(job["script_name"], job_id, job["subject"], args)
    if "error" in result:
        if comment(token, job_id, job["issue_number"],
                   f"### Error running script:\n\n> {result['error']}\n\nPlease contact the team for assistance, quoting the job ID: {job_id}"):
            update_job_status(job_id, JobRunStatus.FAILED, result, logger=logger)
        return

    logger(f"Script `{job['script_name']}` finished successfully")
    try:
        urls = []
        if script_info["type"] == "read":
            logger(f"Upload output files to GitHub for job {job_id} (if any)")
            # Upload each output file to GitHub and get the URLs
            if os.path.exists(f"{OUTPUT_PATH}/{job_id}"):
                for f in os.listdir(f"{OUTPUT_PATH}/{job_id}"):
                    response = upload_file_to_github(token, job_id, f"{OUTPUT_PATH}/{job_id}/{f}", f"{job_id}/{f}")
                    response_json = response.json()
                    if not response.status_code == 201 or "html_url" not in response_json["content"]:
                        if comment(token, job_id, job["issue_number"],
                                   f"### Error running script:\n\n> {response.text}\n\nPlease contact the team for assistance, quoting the job ID: {job_id}"):
                            update_job_status(job_id, JobRunStatus.FAILED,
                                              {"error": f"Failed to upload file: {response.text}"}, logger=logger)
                        return
                    urls.append({"file": f, "url": response_json["content"]["html_url"]})

        changes_link_text = ""
        if script_info["type"] == "write":
            logger(f"Committing and pushing changes to GitHub for job {job_id}...")
            # Make a new branch and commit the changes, push to GitHub, and create a pull request
            changes_result = new_branch_and_push_changes(DATA_PATH_MAP[job["subject"]], job_id)
            if changes_result["status"] == PushChangesStatus.FAILED:
                if comment(token, job_id, job["issue_number"],
                           f"### Error creating pull request:\n\n> {changes_result['message']}\n\nPlease contact the team for assistance, quoting the job ID: {job_id}"):
                    update_job_status(job_id, JobRunStatus.FAILED, {"error": changes_result["message"]}, logger=logger)
                return
            elif changes_result["status"] == PushChangesStatus.SUCCESS:
                # Check if we should create a pull request
                if "create_pull_request" in job and job["create_pull_request"]:
                    logger(f"Creating pull request for job {job_id}...")
                    pr_result = create_pull_request(token, job_id, job["subject"], job["issue_number"])
                    pr_result_json = pr_result.json()
                    if "_links" not in pr_result_json or "html" not in pr_result_json["_links"] or "href" not in pr_result_json["_links"]["html"]:
                        if comment(token, job_id, job["issue_number"],
                                   f"### Error creating pull request:\n\nPlease contact the team for assistance, quoting the job ID: {job_id}"):
                            update_job_status(job_id, JobRunStatus.FAILED, {"error": f"Failed to create pull request: response {pr_result_json}"}, logger=logger)
                        return
                    changes_link_text = f"\n\n### Changes\n\nPlease review and merge changes made by the script [here]({pr_result_json['_links']['html']['href']})."
                else:
                    repo_url = CONTENT_REPO_PATH_MAP[job["subject"]]
                    changes_link_text = f"\n\n### Changes\n\nChanges were made on branch {job_id}. Compare changes [here](https://github.com/{repo_url}/compare/master..{job_id})."
            else:
                changes_link_text = "\n\n### Changes\n\nNo changes were made by the script."

        logger(f"Adding output to issue for job {job_id}...")
        # Add output to issue, and add a links to each output file
        output = f"\n\n```\n{result['result']}\n```" if result["result"] else ""
        download_urls = "\n\n" + "\n".join([f"- [{url['file']}]({url['url']})" for url in urls])
        if comment(token, job_id, job["issue_number"], f"### Output{output}{download_urls}{changes_link_text}"):
            update_job_status(job_id, JobRunStatus.FINISHED, result, logger=logger)
    except Exception as e:
        if comment(token, job_id, job["issue_number"],
                   f"### Error generating output files:\n\n> {str(e)}\n\nPlease contact the team for assistance, quoting the job ID: {job_id}.\n\nScript output:\n\n```{result['result']}```"):
            update_job_status(job_id, JobRunStatus.FAILED, {"error": str(e)}, logger=logger)


def ask_for_script_arguments(job, job_id, script_info, token):
    # Check which argument we need to ask for next
    next_arg_index = len(job["arguments"])
    next_arg = script_info["arguments"][next_arg_index]
    next_arg_message = ""
    if next_arg["type"] == "file":
        next_arg_message = f"""
### Script argument: {next_arg['title']}

{next_arg['description']}

Example:
```
{next_arg['example']}
```

Please reply to this comment with a link to a published Google Sheet, or delete this issue to cancel the job.

{GOOGLE_DOC_PUBLISH_HOW_TO}
"""
    elif next_arg["type"] == "text":
        next_arg_message = f"""
### Script argument: {next_arg['title']}

{next_arg['description']}

Example:
```
{next_arg['example']}
```

Please reply to this comment with the argument, or delete this issue to cancel the job.
"""
    else:
        message = f"### Error extracting script arguments:\n\nSomething went wrong. Please contact the team for assistance, quoting the job ID: {job_id}"
        if comment(token, job_id, job["issue_number"], message):
            update_job_status(job_id, JobRunStatus.FAILED, {"error": f"Wrong argument type in arg object: {next_arg}"}, logger=logger)

    # Add a comment to the issue asking for the next argument
    if comment(token, job_id, job["issue_number"], next_arg_message):
        update_job_status(job_id, JobRunStatus.PAUSED, {"argument_index": next_arg_index}, logger=logger)


class GracefulKiller:
    kill_now = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self):
        self.kill_now = True


# --- Job handlers ---

def github_issue_confirm_job(job_id, job):
    # Get a GitHub token
    token = get_github_token(logger=logger)

    # First make sure that the content repos are up to date
    try:
        logger(f"Updating content repos...")
        pull_repos(token, logger=logger)
    except Exception as e:
        if comment(token, job_id, job["issue_number"], f"### Error pulling content repos:\n\n> {str(e)}\n\nPlease contact the team for assistance, quoting the job ID: {job_id}"):
            update_job_status(job_id, JobRunStatus.FAILED, {"error": str(e)}, logger=logger)
        return

    # Add a reaction to the issue to show that we've seen it (if it's new)
    # TODO maybe should do this using a different job type (one for new issues, one for existing issues)
    if job["issue_status"] == "opened":
        logger(f"Adding initial reaction to issue for job {job_id}...")
        response = add_reaction_to_issue(token, job["issue_number"], "rocket")
        if not response.status_code == 201:
            update_job_status(job_id, JobRunStatus.FAILED, {"error": f"Failed to add initial reaction: {response.text}"}, logger=logger)
            return

    # Check if the script exists and the subject is valid
    if job["script_name"] not in SCRIPTS or job["subject"] not in ["phy", "ada"]:
        if comment(token, job_id, job["issue_number"], f"### Error running script:\n\n> Invalid script name or subject.\n\nPlease delete this issue and contact the team for assistance, quoting the job ID: {job_id}"):
            update_job_status(job_id, JobRunStatus.FAILED, {"error": "Invalid script name or subject"}, logger=logger)
        return

    script_info = SCRIPTS[job["script_name"]]

    # Accumulate arguments for the script, if needed
    if len(job["arguments"]) < len(script_info["arguments"]):
        logger("Script arguments needed.")
        ask_for_script_arguments(job, job_id, script_info, token)
    else:
        # Run the script
        logger("Script arguments complete, running script.")
        run_script_and_close_issue(job, job_id, token)
        # Remove input files
        logger("Script finished, removing any input files.")
        input_dir = f"{INPUT_PATH}/{job_id}"
        if os.path.exists(input_dir):
            shutil.rmtree(input_dir)


JOB_HANDLERS = {
    JobType.ISSUE: github_issue_confirm_job
}


# --- Main worker loop ---

def process_job_queue():
    killer = GracefulKiller()
    logger("Starting up...")
    # Get a GitHub token and pull the script and content repos on startup
    token = get_github_token(logger=logger)
    pull_repos(token, logger=logger)
    logger("Starting job queue processing loop.")
    while not killer.kill_now:
        # Get the next job from the queue, sleeping if there are none
        job = get_next_job()
        if not job:
            # log_to_file("No jobs in queue, sleeping.")
            time.sleep(NO_JOB_SLEEP_TIME)
            continue

        job_id = job["id"]

        logger(f"Job ID {job_id}: Processing job {job}.")

        # Check we have a handler for the job type
        if job["job_type"] not in JOB_HANDLERS:
            update_job_status(job_id, JobRunStatus.FAILED, {"error": f"Unknown job type {job['job_type']}"})
            continue

        # Run the handler for this job type
        try:
            JOB_HANDLERS[job["job_type"]](job_id, job)
        except Exception as e:
            logger(f"Error while running job handler: {e}")
            update_job_status(job_id, JobRunStatus.FAILED, {"error": str(e)})
            continue


def init_worker_process():
    queue_process = Process(target=process_job_queue, daemon=False)
    queue_process.start()
