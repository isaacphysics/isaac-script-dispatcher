import hashlib
import hmac
import logging
import os
import re

import requests
from flask import Flask, request, jsonify
from werkzeug.exceptions import HTTPException, default_exceptions

from script_manager import SCRIPTS
from db_logic import enqueue_job, get_job_info, get_job_count, get_job_ids_by_status, get_job_by_issue_number, \
    reset_job, update_job_status
from constants import *

app = Flask(__name__)


# --- Validation ---

def validate_job_id(job_id: str):
    # UUID v4 regex, see https://stackoverflow.com/a/13653180
    return job_id and re.match("[0-9a-f]{8}\-[0-9a-f]{4}\-4[0-9a-f]{3}\-[89ab][0-9a-f]{3}\-[0-9a-f]{12}", job_id)


def validate_script_name(script_name: str):
    return script_name and re.match("[a-z_]", script_name)


def verify_signature(payload, signature):
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    if not secret:
        raise Exception("GITHUB_WEBHOOK_SECRET is not set!")
    computed_signature = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed_signature, signature)


# --- API endpoints ---

@app.route('/status/<job_id>', methods=['GET'])
def status(job_id):
    if not validate_job_id(job_id):
        return jsonify({"error": "Invalid job_id"}), 400

    job_info = get_job_info(job_id)

    app.logger.info(job_info)

    if not job_info:
        return jsonify({"error": "Cannot locate job with that job_id"}), 404

    try:
        response = {
            "type": job_info["job_type"],
            "status": job_info["status"]
        }
    except KeyError:
        return jsonify({"error": "Invalid job type"}), 500

    # Add result if job is finished, or error if job failed
    if job_info["status"] == JobRunStatus.FINISHED:
        response["result"] = job_info["result"]
        # Add output file path if it exists
        if "output_file" in job_info and job_info["output_file"]:
            response["output_file"] = job_info["output_file"]
    elif job_info["status"] == JobRunStatus.FAILED and "error" in job_info and job_info["error"]:
        response["error"] = job_info["error"]

    # Add timestamps and durations if they exist
    for key in ["enqueued_at", "executed_at"]:
        if key in job_info and job_info[key]:
            response[key] = str(job_info[key])
    for key in ["wait_duration", "run_duration"]:
        if key in job_info and job_info[key]:
            response[key] = str(job_info[key]) + "s"

    return jsonify(response)


@app.route('/queue-status', methods=['GET'])
def queue_status():
    return jsonify({
        "queue_size": get_job_count(),
        "pending_jobs": get_job_ids_by_status(JobRunStatus.PENDING),
        "running_jobs": get_job_ids_by_status(JobRunStatus.RUNNING),
        "finished_jobs": get_job_ids_by_status(JobRunStatus.FINISHED),
        "failed_jobs": get_job_ids_by_status(JobRunStatus.FAILED),
    })


@app.route('/list-scripts', methods=['GET'])
def list_scripts():
    return jsonify(SCRIPTS)


@app.route('/log', methods=['POST'])
def log():
    if not request.is_json:
        return jsonify({"error": "Invalid request format"}), 400
    json = request.get_json()
    # Log whatever is in the `message` field
    app.logger.info(json["message"])
    return jsonify({"message": "Logged"})

# --- Webhook endpoint ---
# The only one that really matters, the rest are just for testing and admin purposes. This should be the only one
# that's exposed to the internet.

@app.route('/github-callback', methods=['POST'])
def webhook():
    # Verify signature to ensure it's from GitHub
    request_signature = request.headers.get("X-Hub-Signature-256")
    if not request_signature or not verify_signature(request.data, request_signature):
        return jsonify({"error": "Invalid signature"}), 200

    if not request.is_json:
        return jsonify({"error": "Invalid request format"}), 200

    json = request.get_json()
    if "issue" not in json:
        return jsonify({"error": "Invalid request format"}), 200

    # Debug logging
    # app.logger.info(json)

    if json["action"] == "opened":
        # Extract script name from issue body
        # Find the word that comes after "### Script name\n"
        script_name = re.search(r"#*\s?Script name\n*(.*)", json["issue"]["body"]).group(1)
        site = re.search(r"#*\s?Site\n*(.*)", json["issue"]["body"]).group(1)
        create_pr = re.search(r"#*\s?Create PR\n*(.*)", json["issue"]["body"]).group(1) == "Yes"
        app.logger.info(f"New issue opened: {json['issue']['number']}, script name: {script_name}, site: {site}")
        enqueue_job(JobType.ISSUE, data={
            "issue_number": json["issue"]["number"],
            "issue_status": "opened",
            "create_pull_request": create_pr,
            "script_name": script_name,
            "subject": "ada" if site == "Ada CS" else "phy",
            "arguments": [],  # Is incrementally built up by the user over a few jobs in a "conversation" with the bot (if arguments are needed)
        })
    elif json["action"] == "created":
        # Ignore comments that this bot
        if json["comment"]["user"]["login"] == "isaac-script-dispatcher[bot]":
            return jsonify({"message": "Ignoring comment from this bot"}), 200

        # Find the job that corresponds to this issue
        job = get_job_by_issue_number(json["issue"]["number"])

        # Check if the comment is a command
        command_search = re.search(r"^Please (.*)$", json["comment"]["body"])
        if command_search:
            command = command_search.group(1).lower()
            if command in ["run", "rerun", "restart", "re-run", "re-start"]:
                if job:
                    # Reset the job
                    app.logger.info(f"Rerunning issue {json['issue']['number']}, new job id {job['id']}. Script name: {job['script_name']}, subject: {job['subject']}")
                    reset_job(job["id"], data={
                        "issue_number": json["issue"]["number"],
                        "issue_status": "reset",
                        "create_pull_request": job["create_pull_request"],
                        "script_name": job["script_name"],
                        "subject": job["subject"],
                        "arguments": []
                    })
                else:
                    script_name = re.search(r"#*\s?Script name\n*(.*)", json["issue"]["body"]).group(1)
                    site = re.search(r"#*\s?Site\n*(.*)", json["issue"]["body"]).group(1)
                    create_pr = re.search(r"#*\s?Create PR\n*(.*)", json["issue"]["body"]).group(1) == "Yes"
                    app.logger.info(f"Recreating issue {json['issue']['number']}. Script name: {script_name}, subject: {site}")
                    enqueue_job(JobType.ISSUE, data={
                        "issue_number": json["issue"]["number"],
                        "issue_status": "reset",
                        "create_pull_request": create_pr,
                        "script_name": script_name,
                        "subject": "ada" if site == "Ada CS" else "phy",
                        "arguments": []
                    })
            return jsonify({"message": "Webhook received, command processed"}), 200

        if not job:
            return jsonify({"error": "Cannot find job with that issue number"}), 200

        # FIXME should check for injection attacks here (see line 36 job_queue.py)

        # Must be an argument...
        app.logger.info(f"Adding argument to job {job['id']}. Argument: {json['comment']['body']}")

        # Get script info
        script_info = SCRIPTS[job["script_name"]]
        argument_index = len(job["arguments"])
        if argument_index >= len(script_info["arguments"]):
            return jsonify({"error": "Too many arguments"}), 200

        # Validation is done in the worker, so we don't need to do it here
        argument = json["comment"]["body"].strip("`\t\n ")

        # Update the job, adding the argument to the list of arguments
        update_job_status(job["id"], JobRunStatus.PENDING, data={
            "arguments": job["arguments"] + [argument],
            "issue_status": "comment"
        })

    return jsonify({"message": "Webhook received"}), 200


# --- Error handling ---

def _make_json_error(ex):
    """
    Convert all outgoing errors into JSON format.
    """
    status_code = ex.code if isinstance(ex, HTTPException) else 500
    response = jsonify(message=str(ex), code=status_code, error=type(ex).__name__)
    response.status_code = status_code
    return response


# Make sure all outgoing error messages are in JSON format.
# This will only work provided debug=False - otherwise the debugger hijacks them!
for code in default_exceptions.keys():
    app.register_error_handler(code, _make_json_error)


# --- Main ---

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

if __name__ != '__main__':
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
