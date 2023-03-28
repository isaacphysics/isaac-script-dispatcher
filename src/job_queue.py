import os
import signal
import subprocess
import time
from multiprocessing import Process

from db_logic import get_next_job, update_job_status
from constants import *
from repos import pull_repos

# -- Main worker loop --


class GracefulKiller:
    kill_now = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self):
        self.kill_now = True


def process_job_queue():
    killer = GracefulKiller()
    while not killer.kill_now:
        # Get the next job from the queue, sleeping if there are none
        job = get_next_job()
        if not job:
            time.sleep(NO_JOB_SLEEP_TIME)
            continue

        job_id = job["id"]

        if job["job_type"] == JobType.REFRESH:
            # app.logger.info(f"Job ID {job_id}: Refreshing content repositories.")
            pull_repos()
            update_job_status(job_id, JobRunStatus.FINISHED, {"result": "Refreshed the content repositories"})
        elif job["job_type"] == JobType.SCRIPT:
            script_name = job["script_name"]
            # app.logger.info(f"Job ID {job_id}: Running script {script_name}.")

            # Ensure the script exists
            if not os.path.exists(f"{SCRIPTS_PATH}/{script_name}_script.py"):
                update_job_status(job_id, JobRunStatus.FAILED, {"error": f"Script {script_name} does not exist"})
                continue

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


def init_worker_process():
    queue_process = Process(target=process_job_queue, daemon=False)
    queue_process.start()
