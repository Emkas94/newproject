from dataclasses import dataclass
from typing import List, Optional
import sqlite3


def row_to_user(row: sqlite3.Row):
    return {"id": row["id"], "username": row["username"]}


def row_to_chat(row: sqlite3.Row):
    return {"id": row["id"], "name": row["name"], "is_group": bool(row["is_group"])}


def row_to_message(row: sqlite3.Row):
    return {
        "id": row["id"],
        "chat_id": row["chat_id"],
        "sender_id": row["sender_id"],
        "content": row["content"],
        "attachment_name": row["attachment_name"],
        "attachment_path": row["attachment_path"],
        "created_at": row["created_at"],
    }
