import logging
import os
import re

from flask import Flask, request, jsonify, send_file
from werkzeug.exceptions import HTTPException, default_exceptions

from script_manager import get_all_script_info
from db_logic import enqueue_job, get_job_info, get_job_count, get_job_ids_by_status
from constants import *

app = Flask(__name__)

# --- Validation ---


def validate_job_id(job_id: str):
    # UUID v4 regex, see https://stackoverflow.com/a/13653180
    return job_id and re.match("[0-9a-f]{8}\-[0-9a-f]{4}\-4[0-9a-f]{3}\-[89ab][0-9a-f]{3}\-[0-9a-f]{12}", job_id)


def validate_script_name(script_name: str):
    return script_name and re.match("[a-z_]", script_name)


# --- API endpoints ---

@app.route('/enqueue', methods=['POST'])
def enqueue():
    if not request.is_json:
        return jsonify({"error": "Invalid request format"}), 400

    data = request.get_json()
    script_name = data.get("script_name")

    if not validate_script_name(script_name):
        return jsonify({"error": "Script name is malformed"}), 400

    job_id = enqueue_job(JobType.SCRIPT, script_name)

    return jsonify({"message": "Script job added to queue", "job_id": job_id})


@app.route('/status/<job_id>', methods=['GET'])
def status(job_id):
    if not validate_job_id(job_id):
        return jsonify({"error": "Invalid job_id"}), 400

    job_info = get_job_info(job_id)

    app.logger.info(job_info)

    if not job_info:
        return jsonify({"error": "Cannot locate job with that job_id"}), 404

    if job_info["job_type"] == JobType.SCRIPT:
        response = {
            "type": job_info["job_type"],
            "status": job_info["status"],
            "script_name": job_info["script_name"]
        }
    elif job_info["job_type"] == JobType.REFRESH:
        response = {
            "type": job_info["job_type"],
            "status": job_info["status"]
        }
    else:
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


@app.route('/download/<job_id>', methods=['GET'])
def download(job_id):
    if not validate_job_id(job_id):
        return jsonify({"error": "Invalid job_id"}), 400

    job_info = get_job_info(job_id)

    if not job_info:
        return jsonify({"error": "Cannot locate job with that job_id"}), 404
    if job_info["job_type"] != JobType.SCRIPT:
        return jsonify({"error": "Job is not a script job"}), 400
    if job_info["status"] != JobRunStatus.FAILED:
        return jsonify({"error": "Script job has failed, cannot download output"}), 500
    if job_info["status"] != JobRunStatus.FINISHED:
        return jsonify({"error": "Script job is not yet finished"}), 400
    if job_info["output_file"] is None:
        return jsonify({"error": "Script job has no output file"}), 400

    return send_file(os.path.join(OUTPUT_PATH, job_info["output_file"]), mimetype='text/csv', download_name=f'{job_id}.csv', as_attachment=True)


@app.route('/refresh', methods=['POST'])
def refresh_repos():
    job_id = enqueue_job(JobType.REFRESH)
    return jsonify({"message": "Content repository refresh added to queue", "job_id": job_id})


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
    return jsonify(get_all_script_info(app.logger))


# --- Error handling ---

def _make_json_error(ex):
    """Return JSON error pages, not HTML!
       Using a method suggested in http://flask.pocoo.org/snippets/83/, convert
       all outgoing errors into JSON format.
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
