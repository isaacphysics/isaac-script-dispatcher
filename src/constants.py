"""
Configuration constants for the scripts runner, and related enums.
"""
class JobType:
    ISSUE = "ISSUE"
    ISSUE_COMMENT = "ISSUE_COMMENT"

class JobRunStatus:
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FINISHED = "FINISHED"
    FAILED = "FAILED"

class PushChangesStatus:
    NO_CHANGES = "NO_CHANGES"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

SCRIPTS_PATH = r"./data/isaac-scripts"
SCRIPT_DISPATCHER_SCRIPTS_SUBDIR = f"{SCRIPTS_PATH}/script-dispatcher"
DATA_PATH = r"./data"
PHY_DATA_PATH = r"./data/rutherford-content"
CS_DATA_PATH = r"./data/ada-content"
DATA_PATH_MAP = {
    "phy": PHY_DATA_PATH,
    "ada": CS_DATA_PATH,
}
OUTPUT_PATH = r"./output"
INPUT_PATH = r"./input"
KEY_PATH = r"./key.pem"

JOB_DB_PATH = r"job_queue.db"

REPO_PATH = r"isaacphysics/isaac-dispatched-scripts"
CONTENT_REPO_PATH_MAP = {
    "phy": r"isaacphysics/rutherford-content",
    "ada": r"isaacphysics/ada-content"
}
SCRIPTS_REPO_PATH = r"isaacphysics/isaac-scripts"

BOT_USERNAME = "isaac-script-dispatcher[bot]"
BOT_EMAIL = "129531963+isaac-script-dispatcher[bot]@users.noreply.github.com"

NO_JOB_SLEEP_TIME = 5

GET_NEXT_JOB_RETRIES = 10
GET_NEXT_JOB_RETRY_DELAY = 1
