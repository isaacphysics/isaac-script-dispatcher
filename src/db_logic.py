import json
import sqlite3
import time
import uuid

from constants import *


def generate_unique_job_id():
    conn = sqlite3.connect(JOB_DB_PATH)
    existing_uuids = map(lambda x: x[0], conn.execute('SELECT id FROM job_queue').fetchall())
    new_uuid = str(uuid.uuid4())
    while new_uuid in existing_uuids:
        new_uuid = str(uuid.uuid4())
    return new_uuid


def translate_job_to_dict(row):
    if not row:
        return None
    job_dict = dict()
    for k, v in dict(row).items():
        if k == "job_data" and v is not None:
            job_data = json.loads(v)
            for k2, v2 in job_data.items():
                job_dict[k2] = v2
        else:
            job_dict[k] = v
    return job_dict


def init_db():
    conn = sqlite3.connect(JOB_DB_PATH)
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS job_queue (
        id TEXT PRIMARY KEY,
        job_type TEXT NOT NULL,
        job_data JSON DEFAULT NULL,
        status TEXT NOT NULL,
        enqueued_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        executed_at DATETIME DEFAULT NULL,
        run_duration DATETIME DEFAULT NULL,
        wait_duration DATETIME DEFAULT NULL
    )
    ''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS app_token (
        token TEXT PRIMARY KEY,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        expires_at DATETIME DEFAULT NULL
    )
    ''')
    conn.commit()
    conn.close()


def enqueue_job(job_type, data=None):
    job_id = generate_unique_job_id()
    conn = sqlite3.connect(JOB_DB_PATH)
    c = conn.cursor()
    if data is None:
        c.execute('''
        INSERT INTO job_queue (id, job_type, status)
        VALUES (?, ?, ?, ?)
        ''', (job_id, job_type, JobRunStatus.PENDING))
    else:
        c.execute('''
        INSERT INTO job_queue (id, job_type, status, job_data)
        VALUES (?, ?, ?, ?)
        ''', (job_id, job_type, JobRunStatus.PENDING, json.dumps(data)))
    conn.commit()
    conn.close()
    return job_id


def update_job_status(job_id, new_status, data=None, logger=lambda x: None):
    if new_status == JobRunStatus.FAILED:
        logger(f"Job {job_id} failed: {data['error'] if data and 'error' in data else '[no error message]'}")

    if new_status == JobRunStatus.RUNNING:
        raise ValueError("Cannot set job status to RUNNING. Use get_next_job instead.")
    else:
        conn = sqlite3.connect(JOB_DB_PATH)
        c = conn.cursor()
        c.execute('''
                UPDATE job_queue
                SET status = ?, run_duration = ROUND((JULIANDAY(CURRENT_TIMESTAMP) - JULIANDAY(executed_at)) * 86400.0), job_data = json_patch(COALESCE(job_data, json('{}')), json(?))
                WHERE id = ?
                ''', (new_status, json.dumps(data if data else {}), job_id))
        conn.commit()
        conn.close()


def reset_job(job_id, data=None):
    conn = sqlite3.connect(JOB_DB_PATH)
    c = conn.cursor()
    c.execute('''
    UPDATE job_queue
    SET status = ?,  executed_at = NULL, run_duration = NULL, wait_duration = NULL, job_data = json(?), enqueued_at = CURRENT_TIMESTAMP
    WHERE id = ?
    ''', (JobRunStatus.PENDING, json.dumps(data if data else {}), job_id))
    conn.commit()
    conn.close()
    return job_id


def get_job_info(job_id):
    conn = sqlite3.connect(JOB_DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
    SELECT id, job_type, job_data, status, enqueued_at, executed_at, run_duration, wait_duration
    FROM job_queue
    WHERE id = ?
    ''', (job_id,))
    result = c.fetchone()
    conn.close()
    return translate_job_to_dict(result)


def get_job_by_issue_number(issue_number):
    conn = sqlite3.connect(JOB_DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
    SELECT id, job_type, job_data, status, enqueued_at, executed_at, run_duration, wait_duration
    FROM job_queue
    WHERE job_type = 'ISSUE' AND json_extract(job_data, '$.issue_number') = ? AND status != 'FINISHED'
    ''', (issue_number,))
    result = c.fetchone()
    conn.close()
    return translate_job_to_dict(result)


def get_next_job():
    conn = sqlite3.connect(JOB_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.isolation_level = 'EXCLUSIVE'

    for attempt in range(GET_NEXT_JOB_RETRIES):
        try:
            c = conn.cursor()
            c.execute(f"SELECT * FROM job_queue WHERE status = '{JobRunStatus.PENDING}' ORDER BY enqueued_at ASC LIMIT 1")
            job = c.fetchone()

            if job is not None:
                job_id = job['id']
                c.execute(f'''
                UPDATE job_queue 
                SET status = '{JobRunStatus.RUNNING}', wait_duration = ROUND((JULIANDAY(CURRENT_TIMESTAMP) - JULIANDAY(enqueued_at)) * 86400.0), executed_at = CURRENT_TIMESTAMP WHERE id = ?
                ''', (job_id,))
                conn.commit()
                conn.close()
                return translate_job_to_dict(job)

            break
        except sqlite3.OperationalError as e:
            if str(e) == "database is locked":
                print(f"Attempt {attempt + 1}: Database is locked. Retrying in {GET_NEXT_JOB_RETRY_DELAY} seconds...")
                time.sleep(GET_NEXT_JOB_RETRY_DELAY)
            else:
                raise e
    else:
        print("Failed to get the next job after multiple attempts.")
    conn.close()


def get_job_ids_by_status(status):
    conn = sqlite3.connect(JOB_DB_PATH)
    c = conn.cursor()
    c.execute('''
    SELECT id
    FROM job_queue
    WHERE status = ?
    ''', (status,))
    result = c.fetchall()
    conn.close()
    return [r[0] for r in result]


def get_job_count():
    conn = sqlite3.connect(JOB_DB_PATH)
    c = conn.cursor()
    c.execute('''
    SELECT COUNT(id)
    FROM job_queue
    ''')
    result = c.fetchone()
    conn.close()
    return result[0]


# --- Token management ---

def save_token(token, created_at, expires_at):
    conn = sqlite3.connect(JOB_DB_PATH)
    c = conn.cursor()
    c.execute('''
    DELETE FROM app_token
    ''')
    c.execute('''
    INSERT INTO app_token (token, created_at, expires_at)
    VALUES (?, ?, ?)
    ''', (token, created_at, expires_at))
    conn.commit()
    conn.close()


def get_token():
    conn = sqlite3.connect(JOB_DB_PATH)
    c = conn.cursor()
    c.execute('''
    SELECT token, created_at, expires_at
    FROM app_token
    ''')
    result = c.fetchone()
    conn.close()
    return result
