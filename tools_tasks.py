"""A tiny task list stored in SQLite (data/lla.db). This is LLa's memory for to-dos."""

import sqlite3

from config import DATA_DIR

DB_PATH = DATA_DIR / "lla.db"


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "CREATE TABLE IF NOT EXISTS tasks ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, "
        "due TEXT, done INTEGER DEFAULT 0, created TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    return con


def add_task(title: str, due: str = "") -> str:
    with _db() as con:
        cur = con.execute("INSERT INTO tasks (title, due) VALUES (?, ?)", (title, due or None))
    return f"Task #{cur.lastrowid} added."


def list_tasks() -> str:
    with _db() as con:
        rows = con.execute("SELECT id, title, due FROM tasks WHERE done = 0 ORDER BY due IS NULL, due, id").fetchall()
    if not rows:
        return "No open tasks."
    return "\n".join(f"- #{i} {title}" + (f" (due {due})" if due else "") for i, title, due in rows)


def complete_task(task_id: int) -> str:
    with _db() as con:
        cur = con.execute("UPDATE tasks SET done = 1 WHERE id = ?", (int(task_id),))
    return f"Task #{task_id} marked done." if cur.rowcount else f"No task with id {task_id}."
