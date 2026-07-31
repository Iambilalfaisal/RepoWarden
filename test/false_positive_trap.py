import sqlite3
import subprocess


def get_user_safe(conn: sqlite3.Connection, username: str):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    return cursor.fetchone()


def list_directory_safe(path: str) -> str:
    result = subprocess.run(["ls", "-la", path], capture_output=True, text=True, check=True)
    return result.stdout
