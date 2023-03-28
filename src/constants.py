"""
Configuration constants for the scripts runner.
"""
class JobType:
    SCRIPT = "SCRIPT"
    REFRESH = "REFRESH"

class JobRunStatus:
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    FAILED = "FAILED"

SCRIPTS_PATH = r"./scripts"
PHY_DATA_PATH = r"./data/phy"
CS_DATA_PATH = r"./data/cs"
OUTPUT_PATH = r"./output"

JOB_DB_PATH = r"job_queue.db"

NO_JOB_SLEEP_TIME = 5

GET_NEXT_JOB_RETRIES = 10
GET_NEXT_JOB_RETRY_DELAY = 1
