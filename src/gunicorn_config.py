from job_queue import init_worker_process
from db_logic import init_db

bind = "0.0.0.0:5000"
workers = 4  # Not including the job runner process


def on_starting(server):
    # Initialize the database before starting the server
    print("[STARTUP] Initialising job queue database...")
    init_db()
    print("[STARTUP] Job queue database initialised.")
    print("[STARTUP] Starting job queue processing thread...")
    init_worker_process()
    print("[STARTUP] Job queue processing thread started.")
