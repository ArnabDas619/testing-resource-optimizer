"""
src/database.py
---------------
Unified SQLite manager for staffing.db.
Handles auto-migration on startup and provides clean CRUD helpers.
"""
import sqlite3
import pandas as pd
import os
from datetime import datetime

DB_PATH = "staffing.db"

# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------
_DDL = """
CREATE TABLE IF NOT EXISTS testers (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT    NOT NULL,
    experience_years    INTEGER NOT NULL DEFAULT 0,
    skills              TEXT    NOT NULL DEFAULT '',   -- comma-separated
    proficiency         TEXT    NOT NULL DEFAULT 'Mid', -- Low / Mid / High
    available_hours     INTEGER NOT NULL DEFAULT 40
);

CREATE TABLE IF NOT EXISTS tasks (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    sprint_commitment   TEXT,
    status              TEXT    DEFAULT 'Not Started',
    task_description    TEXT    NOT NULL,
    required_skills     TEXT    DEFAULT '',   -- comma-separated, filled by LLM
    effort_hours        REAL    DEFAULT 8.0
);

CREATE TABLE IF NOT EXISTS assignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         INTEGER REFERENCES tasks(id),
    tester_id       INTEGER REFERENCES testers(id),
    allocated_hours REAL    DEFAULT 0.0,
    start_day       INTEGER DEFAULT 0,
    end_day         INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS corrections (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id             INTEGER REFERENCES tasks(id),
    task_description    TEXT,
    required_skills_original  TEXT,
    original_tester     TEXT,
    corrected_tester    TEXT,
    pm_notes            TEXT,
    created_at          TEXT    DEFAULT (datetime('now'))
);
"""


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist (idempotent / safe migration)."""
    conn = _get_conn()
    conn.executescript(_DDL)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Testers
# ---------------------------------------------------------------------------
def load_testers_df() -> pd.DataFrame:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM testers", conn)
    conn.close()
    return df


def save_testers_from_df(df: pd.DataFrame):
    """Replace testers table from a DataFrame. Normalises column names."""
    init_db()
    # Normalise column names  →  DB column names
    rename_map = {
        "Name": "name",
        "Experience": "experience_years",
        "Experience Years": "experience_years",
        "Skills": "skills",
        "Proficiency": "proficiency",
        "Available Hours": "available_hours",
        # Legacy aliases
        "Type": "skills",
    }
    df = df.copy().rename(columns=rename_map)
    # Keep only recognised columns
    allowed = {"id", "name", "experience_years", "skills", "proficiency", "available_hours"}
    df = df[[c for c in df.columns if c in allowed]]
    # Fill defaults
    if "experience_years" not in df.columns:
        df["experience_years"] = 0
    if "skills" not in df.columns:
        df["skills"] = ""
    if "proficiency" not in df.columns:
        df["proficiency"] = "Mid"
    if "available_hours" not in df.columns:
        df["available_hours"] = 40

    conn = _get_conn()
    
    if "id" not in df.columns:
        # Bulk insert (e.g. from CSV import)
        conn.execute("DELETE FROM testers")
        for _, row in df.iterrows():
            conn.execute(
                "INSERT INTO testers (name, experience_years, skills, proficiency, available_hours) VALUES (?, ?, ?, ?, ?)",
                (row["name"], row["experience_years"], row["skills"], row["proficiency"], row["available_hours"])
            )
    else:
        # Dynamic update (e.g. from data editor)
        existing_ids = {r["id"] for r in conn.execute("SELECT id FROM testers")}
        df_ids = set(df["id"].dropna().astype(int)) if not df.empty else set()
        
        to_delete = existing_ids - df_ids
        if to_delete:
            conn.execute(f"DELETE FROM testers WHERE id IN ({','.join(map(str, to_delete))})")
            
        for _, row in df.iterrows():
            row_id = row.get("id")
            if pd.isna(row_id):
                conn.execute(
                    "INSERT INTO testers (name, experience_years, skills, proficiency, available_hours) VALUES (?, ?, ?, ?, ?)",
                    (row["name"], row["experience_years"], row["skills"], row["proficiency"], row["available_hours"])
                )
            else:
                conn.execute(
                    "UPDATE testers SET name=?, experience_years=?, skills=?, proficiency=?, available_hours=? WHERE id=?",
                    (row["name"], row["experience_years"], row["skills"], row["proficiency"], row["available_hours"], int(row_id))
                )
    
    conn.commit()
    conn.close()


def clear_testers():
    init_db()
    conn = _get_conn()
    conn.execute("DELETE FROM testers")
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------
def save_tasks_from_df(df: pd.DataFrame):
    """Upsert tasks from classified backlog DataFrame."""
    init_db()
    rename_map = {
        "Sprint Commitment": "sprint_commitment",
        "Status": "status",
        "Task Description": "task_description",
        "Required Skills": "required_skills",
        "Effort Hours": "effort_hours",
    }
    df = df.copy().rename(columns=rename_map)
    allowed = {"sprint_commitment", "status", "task_description", "required_skills", "effort_hours"}
    df = df[[c for c in df.columns if c in allowed]]
    
    conn = _get_conn()
    conn.execute("DELETE FROM tasks")
    for _, row in df.iterrows():
        conn.execute(
            "INSERT INTO tasks (sprint_commitment, status, task_description, required_skills, effort_hours) VALUES (?, ?, ?, ?, ?)",
            (
                row.get("sprint_commitment", ""),
                row.get("status", "Not Started"),
                row.get("task_description", ""),
                row.get("required_skills", ""),
                row.get("effort_hours", 8.0)
            )
        )
    conn.commit()
    conn.close()


def load_tasks_df() -> pd.DataFrame:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM tasks", conn)
    conn.close()
    return df


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------
def save_assignments(assignments: list[dict]):
    """Persist a list of assignment dicts from the optimizer."""
    init_db()
    conn = _get_conn()
    conn.execute("DELETE FROM assignments")
    for a in assignments:
        conn.execute(
            "INSERT INTO assignments (task_id, tester_id, allocated_hours, start_day, end_day) "
            "VALUES (?, ?, ?, ?, ?)",
            (a.get("task_id"), a.get("tester_id"), a.get("allocated_hours", 0),
             a.get("start_day", 0), a.get("end_day", 0))
        )
    conn.commit()
    conn.close()


def load_assignments_df() -> pd.DataFrame:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT a.id, t.task_description, te.name AS tester_name,
               a.allocated_hours, a.start_day, a.end_day
        FROM assignments a
        JOIN tasks t    ON a.task_id   = t.id
        JOIN testers te ON a.tester_id = te.id
    """, conn)
    conn.close()
    return df


# ---------------------------------------------------------------------------
# Corrections
# ---------------------------------------------------------------------------
def save_correction(task_id: int, task_description: str, required_skills_original: str,
                    original_tester: str, corrected_tester: str, pm_notes: str = ""):
    init_db()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO corrections "
        "(task_id, task_description, required_skills_original, original_tester, corrected_tester, pm_notes) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (task_id, task_description, required_skills_original,
         original_tester, corrected_tester, pm_notes)
    )
    conn.commit()
    conn.close()


def load_corrections_df() -> pd.DataFrame:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM corrections ORDER BY created_at DESC", conn)
    conn.close()
    return df


def get_recent_corrections(n: int = 5) -> list[dict]:
    """Returns the N most-recent corrections as dicts for few-shot prompting."""
    df = load_corrections_df()
    return df.head(n).to_dict(orient="records")
