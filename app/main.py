import os
import secrets
from pathlib import Path
from typing import List

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import get_db, init_db
from . import schemas

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Modern Chat (offline friendly)")
init_db()


def fetch_user(conn, user_id: int):
    cur = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return cur.fetchone()


def fetch_chat(conn, chat_id: int):
    cur = conn.execute("SELECT * FROM chats WHERE id = ?", (chat_id,))
    return cur.fetchone()


def fetch_message(conn, message_id: int):
    cur = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,))
    return cur.fetchone()


def fetch_bot(conn, bot_id: int):
    cur = conn.execute("SELECT * FROM bots WHERE id = ?", (bot_id,))
    return cur.fetchone()


def require_admin(conn, admin_id: int):
    admin = fetch_user(conn, admin_id)
    if not admin:
        raise HTTPException(status_code=404, detail="Admin user not found")
    if not admin["is_admin"]:
        raise HTTPException(status_code=403, detail="User is not an admin")
    return admin


@app.post("/users")
def create_user(user: schemas.UserCreate, db=Depends(get_db)):
    existing = db.execute("SELECT id FROM users WHERE username = ?", (user.username,)).fetchone()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    cur = db.execute(
        "INSERT INTO users (username, is_admin) VALUES (?, ?)",
        (user.username, int(user.is_admin)),
    )
    db.commit()
    return {"id": cur.lastrowid, "username": user.username, "is_admin": bool(user.is_admin)}


@app.get("/users")
def list_users(db=Depends(get_db)):
    cur = db.execute("SELECT id, username, is_admin FROM users ORDER BY id")
    return [dict(row) for row in cur.fetchall()]


def _ensure_username_available(db, base_username: str) -> str:
    candidate = base_username
    suffix = 1
    while db.execute("SELECT 1 FROM users WHERE username = ?", (candidate,)).fetchone():
        candidate = f"{base_username}{suffix}"
        suffix += 1
    return candidate


@app.post("/bots")
def create_bot(bot: schemas.BotCreate, db=Depends(get_db)):
    data = bot

    owner = fetch_user(db, data.owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail="owner user not found")

    base_username = f"{data.name}_bot".replace(" ", "_")
    bot_username = _ensure_username_available(db, base_username)
    user_cur = db.execute("INSERT INTO users (username) VALUES (?)", (bot_username,))
    bot_user_id = user_cur.lastrowid
    token = secrets.token_hex(16)
    bot_cur = db.execute(
        "INSERT INTO bots (name, user_id, owner_user_id, token) VALUES (?, ?, ?, ?)",
        (data.name, bot_user_id, data.owner_id, token),
    )
    db.commit()
    return {
        "id": bot_cur.lastrowid,
        "name": data.name,
        "username": bot_username,
        "token": token,
        "owner_id": data.owner_id,
    }


@app.post("/chats")
def create_chat(chat: schemas.ChatCreate, db=Depends(get_db)):
    if not chat.participant_ids:
        raise HTTPException(status_code=400, detail="At least one participant required")

    users = db.execute(
        f"SELECT id, username FROM users WHERE id IN ({','.join('?'*len(chat.participant_ids))})",
        chat.participant_ids,
    ).fetchall()
    if len(users) != len(set(chat.participant_ids)):
        raise HTTPException(status_code=404, detail="One or more participants not found")

    name = chat.name or ("Group Chat" if chat.is_group else " & ".join(sorted([u["username"] for u in users])))
    cur = db.execute("INSERT INTO chats (name, is_group) VALUES (?, ?)", (name, int(chat.is_group)))
    chat_id = cur.lastrowid
    for user_row in users:
        db.execute("INSERT INTO chat_participants (chat_id, user_id) VALUES (?, ?)", (chat_id, user_row["id"]))
    db.commit()
    participant_payload = [{"user": {"id": u["id"], "username": u["username"]}} for u in users]
    return {"id": chat_id, "name": name, "is_group": chat.is_group, "participants": participant_payload}


@app.get("/users/{user_id}/chats")
def list_user_chats(user_id: int, db=Depends(get_db)):
    user = fetch_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    rows = db.execute(
        """
        SELECT c.id, c.name, c.is_group,
               group_concat(u.username, ',') as usernames,
               group_concat(u.id, ',') as user_ids,
               CASE WHEN fc.user_id IS NULL THEN 0 ELSE 1 END as is_favorite
        FROM chats c
        JOIN chat_participants cp ON cp.chat_id = c.id
        LEFT JOIN favorite_chats fc ON fc.chat_id = c.id AND fc.user_id = ?
        JOIN users u ON u.id = cp.user_id
        WHERE c.id IN (
            SELECT chat_id FROM chat_participants WHERE user_id = ?
        )
        GROUP BY c.id
        ORDER BY c.id
        """,
        (user_id, user_id),
    ).fetchall()
    result = []
    for row in rows:
        usernames = row["usernames"].split(",") if row["usernames"] else []
        user_ids = [int(x) for x in row["user_ids"].split(",")] if row["user_ids"] else []
        participants = [
            {"user": {"id": uid, "username": uname}}
            for uid, uname in zip(user_ids, usernames)
        ]
        result.append({
            "id": row["id"],
            "name": row["name"],
            "is_group": bool(row["is_group"]),
            "participants": participants,
            "is_favorite": bool(row["is_favorite"]),
        })
    return result


@app.post("/chats/{chat_id}/bots/{bot_id}")
def add_bot_to_chat(chat_id: int, bot_id: int, owner_id: int, db=Depends(get_db)):
    chat = fetch_chat(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    bot = fetch_bot(db, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    if bot["owner_user_id"] != owner_id:
        raise HTTPException(status_code=403, detail="Only the bot owner can add it to chats")

    owner_in_chat = db.execute(
        "SELECT 1 FROM chat_participants WHERE chat_id = ? AND user_id = ?",
        (chat_id, owner_id),
    ).fetchone()
    if not owner_in_chat:
        raise HTTPException(status_code=403, detail="Owner must be part of the chat")

    existing = db.execute(
        "SELECT 1 FROM chat_participants WHERE chat_id = ? AND user_id = ?",
        (chat_id, bot["user_id"]),
    ).fetchone()
    if existing:
        return {"status": "already_added"}

    db.execute(
        "INSERT INTO chat_participants (chat_id, user_id) VALUES (?, ?)",
        (chat_id, bot["user_id"]),
    )
    db.commit()
    return {"status": "added", "chat_id": chat_id, "bot_id": bot_id}


@app.get("/chats/{chat_id}/messages")
def list_messages(chat_id: int, user_id: int | None = None, db=Depends(get_db)):
    chat = fetch_chat(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    favorite_select = "0 as is_favorite"
    favorite_join = ""
    params: list[int] = [chat_id]

    if user_id is not None:
        user = fetch_user(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        participant = db.execute(
            "SELECT 1 FROM chat_participants WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id),
        ).fetchone()
        if not participant:
            raise HTTPException(status_code=403, detail="User is not part of this chat")
        favorite_select = "CASE WHEN fm.user_id IS NULL THEN 0 ELSE 1 END as is_favorite"
        favorite_join = "LEFT JOIN favorite_messages fm ON fm.message_id = m.id AND fm.user_id = ?"
        params = [user_id, chat_id]

    query = f"""
        SELECT m.*, u.username as sender_username, {favorite_select}
        FROM messages m
        JOIN users u ON u.id = m.sender_id
        {favorite_join}
        WHERE m.chat_id = ?
        ORDER BY m.created_at ASC, m.id ASC
    """
    cur = db.execute(query, params)

    messages = []
    for row in cur.fetchall():
        messages.append(
            {
                "id": row["id"],
                "chat_id": row["chat_id"],
                "sender": {"id": row["sender_id"], "username": row["sender_username"]},
                "content": row["content"],
                "attachment_name": row["attachment_name"],
                "created_at": row["created_at"],
                "is_favorite": bool(row["is_favorite"]),
            }
        )
    return messages


@app.get("/admin/chats/{chat_id}/logs")
def admin_chat_logs(chat_id: int, admin_id: int, db=Depends(get_db)):
    require_admin(db, admin_id)
    chat = fetch_chat(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    rows = db.execute(
        """
        SELECT m.id, m.content, m.created_at, m.attachment_name, u.username as sender_username, u.id as sender_id
        FROM messages m
        JOIN users u ON u.id = m.sender_id
        WHERE m.chat_id = ?
        ORDER BY m.created_at ASC
        """,
        (chat_id,),
    ).fetchall()

    logs = []
    for row in rows:
        logs.append(
            {
                "id": row["id"],
                "chat_id": chat_id,
                "sender": {"id": row["sender_id"], "username": row["sender_username"]},
                "content": row["content"],
                "attachment_name": row["attachment_name"],
                "created_at": row["created_at"],
            }
        )

    return {"chat": {"id": chat["id"], "name": chat["name"]}, "messages": logs}


@app.post("/favorites/chats")
def favorite_chat(data: schemas.FavoriteChat, db=Depends(get_db)):
    user = fetch_user(db, data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    chat = fetch_chat(db, data.chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    participant = db.execute(
        "SELECT 1 FROM chat_participants WHERE chat_id = ? AND user_id = ?",
        (data.chat_id, data.user_id),
    ).fetchone()
    if not participant:
        raise HTTPException(status_code=403, detail="User is not part of this chat")

    db.execute(
        "INSERT OR IGNORE INTO favorite_chats (user_id, chat_id) VALUES (?, ?)",
        (data.user_id, data.chat_id),
    )
    db.commit()
    return {"status": "favorited", "chat_id": data.chat_id, "user_id": data.user_id}


@app.delete("/favorites/chats")
def unfavorite_chat(user_id: int, chat_id: int, db=Depends(get_db)):
    deleted = db.execute(
        "DELETE FROM favorite_chats WHERE user_id = ? AND chat_id = ?",
        (user_id, chat_id),
    )
    db.commit()
    return {"status": "removed" if deleted.rowcount else "not_found", "chat_id": chat_id}


@app.post("/favorites/messages")
def favorite_message(data: schemas.FavoriteMessage, db=Depends(get_db)):
    user = fetch_user(db, data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    message = fetch_message(db, data.message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    participant = db.execute(
        "SELECT 1 FROM chat_participants WHERE chat_id = ? AND user_id = ?",
        (message["chat_id"], data.user_id),
    ).fetchone()
    if not participant:
        raise HTTPException(status_code=403, detail="User is not part of this chat")

    db.execute(
        "INSERT OR IGNORE INTO favorite_messages (user_id, message_id) VALUES (?, ?)",
        (data.user_id, data.message_id),
    )
    db.commit()
    return {"status": "favorited", "message_id": data.message_id, "user_id": data.user_id}


@app.delete("/favorites/messages")
def unfavorite_message(user_id: int, message_id: int, db=Depends(get_db)):
    deleted = db.execute(
        "DELETE FROM favorite_messages WHERE user_id = ? AND message_id = ?",
        (user_id, message_id),
    )
    db.commit()
    return {"status": "removed" if deleted.rowcount else "not_found", "message_id": message_id}


@app.get("/users/{user_id}/favorites")
def list_favorites(user_id: int, db=Depends(get_db)):
    user = fetch_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    chat_rows = db.execute(
        """
        SELECT c.id, c.name, c.is_group,
               group_concat(u.username, ',') as usernames,
               group_concat(u.id, ',') as user_ids
        FROM favorite_chats fc
        JOIN chats c ON c.id = fc.chat_id
        LEFT JOIN chat_participants cp ON cp.chat_id = c.id
        LEFT JOIN users u ON u.id = cp.user_id
        WHERE fc.user_id = ?
        GROUP BY c.id
        ORDER BY c.id
        """,
        (user_id,),
    ).fetchall()

    favorite_chats = []
    for row in chat_rows:
        usernames = row["usernames"].split(",") if row["usernames"] else []
        user_ids = [int(x) for x in row["user_ids"].split(",")] if row["user_ids"] else []
        participants = [
            {"user": {"id": uid, "username": uname}}
            for uid, uname in zip(user_ids, usernames)
        ]
        favorite_chats.append(
            {
                "id": row["id"],
                "name": row["name"],
                "is_group": bool(row["is_group"]),
                "participants": participants,
            }
        )

    message_rows = db.execute(
        """
        SELECT m.id, m.chat_id, m.content, m.attachment_name, m.created_at,
               u.username as sender_username, u.id as sender_id
        FROM favorite_messages fm
        JOIN messages m ON m.id = fm.message_id
        JOIN users u ON u.id = m.sender_id
        WHERE fm.user_id = ?
        ORDER BY m.created_at ASC, m.id ASC
        """,
        (user_id,),
    ).fetchall()

    favorite_messages = []
    for row in message_rows:
        favorite_messages.append(
            {
                "id": row["id"],
                "chat_id": row["chat_id"],
                "sender": {"id": row["sender_id"], "username": row["sender_username"]},
                "content": row["content"],
                "attachment_name": row["attachment_name"],
                "created_at": row["created_at"],
            }
        )

    return {"chats": favorite_chats, "messages": favorite_messages}


@app.post("/chats/{chat_id}/messages")
def send_message(
    chat_id: int,
    sender_id: int,
    content: str | None = None,
    file: UploadFile | None = File(None),
    db=Depends(get_db),
):
    chat = fetch_chat(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    participant = db.execute(
        "SELECT 1 FROM chat_participants WHERE chat_id = ? AND user_id = ?",
        (chat_id, sender_id),
    ).fetchone()
    if not participant:
        raise HTTPException(status_code=403, detail="Sender is not part of this chat")

    attachment_path = None
    attachment_name = None
    if file:
        safe_name = os.path.basename(file.filename)
        unique_prefix = secrets.token_hex(8)
        destination = UPLOAD_DIR / f"{unique_prefix}_{safe_name}"
        with destination.open("wb") as buffer:
            buffer.write(file.file.read())
        attachment_path = str(destination)
        attachment_name = safe_name

    if not content and not attachment_path:
        raise HTTPException(status_code=400, detail="Message must have text or a file")

    cur = db.execute(
        "INSERT INTO messages (chat_id, sender_id, content, attachment_path, attachment_name) VALUES (?, ?, ?, ?, ?)",
        (chat_id, sender_id, content, attachment_path, attachment_name),
    )
    db.commit()
    message_id = cur.lastrowid
    sender = db.execute("SELECT username FROM users WHERE id = ?", (sender_id,)).fetchone()
    return {
        "id": message_id,
        "chat_id": chat_id,
        "sender": {"id": sender_id, "username": sender["username"] if sender else ""},
        "content": content,
        "attachment_name": attachment_name,
        "created_at": db.execute("SELECT created_at FROM messages WHERE id = ?", (message_id,)).fetchone()["created_at"],
    }


@app.delete("/admin/messages/{message_id}")
def delete_message(message_id: int, admin_id: int, db=Depends(get_db)):
    require_admin(db, admin_id)
    message = db.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    if message["attachment_path"]:
        path = Path(message["attachment_path"])
        if path.exists():
            path.unlink()

    db.execute("DELETE FROM messages WHERE id = ?", (message_id,))
    db.commit()
    return {"status": "deleted", "message_id": message_id}


def _require_bot(db, bot_id: int, token: str):
    bot = fetch_bot(db, bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    if bot["token"] != token:
        raise HTTPException(status_code=403, detail="Invalid bot token")
    return bot


@app.post("/bots/{bot_id}/messages")
def send_bot_message(bot_id: int, token: str, chat_id: int, content: str, db=Depends(get_db)):
    bot = _require_bot(db, bot_id, token)

    try:
        data = schemas.BotSend.from_dict({"chat_id": chat_id, "content": content})
    except schemas.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    chat = fetch_chat(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    participant = db.execute(
        "SELECT 1 FROM chat_participants WHERE chat_id = ? AND user_id = ?",
        (data.chat_id, bot["user_id"]),
    ).fetchone()
    if not participant:
        raise HTTPException(status_code=403, detail="Bot is not part of this chat")

    cur = db.execute(
        "INSERT INTO messages (chat_id, sender_id, content) VALUES (?, ?, ?)",
        (data.chat_id, bot["user_id"], data.content),
    )
    db.commit()
    message_id = cur.lastrowid
    created_at = db.execute("SELECT created_at FROM messages WHERE id = ?", (message_id,)).fetchone()["created_at"]
    return {
        "id": message_id,
        "chat_id": data.chat_id,
        "sender": {"id": bot["user_id"], "username": "bot"},
        "content": data.content,
        "attachment_name": None,
        "created_at": created_at,
    }


@app.post("/bots/{bot_id}/updates")
def bot_updates(bot_id: int, token: str, since_id: int = 0, db=Depends(get_db)):
    bot = _require_bot(db, bot_id, token)

    rows = db.execute(
        """
        SELECT m.*, u.username as sender_username
        FROM messages m
        JOIN chat_participants cp ON cp.chat_id = m.chat_id
        JOIN users u ON u.id = m.sender_id
        WHERE cp.user_id = ? AND m.id > ?
        ORDER BY m.id ASC
        """,
        (bot["user_id"], since_id),
    ).fetchall()

    updates = []
    for row in rows:
        updates.append(
            {
                "id": row["id"],
                "chat_id": row["chat_id"],
                "sender": {"id": row["sender_id"], "username": row["sender_username"]},
                "content": row["content"],
                "attachment_name": row["attachment_name"],
                "created_at": row["created_at"],
            }
        )
    return {"updates": updates, "last_id": updates[-1]["id"] if updates else since_id}


@app.get("/messages/{message_id}/file")
def download_file(message_id: int, db=Depends(get_db)):
    message = db.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    if not message["attachment_path"]:
        raise HTTPException(status_code=404, detail="No attachment for this message")
    if not Path(message["attachment_path"]).exists():
        raise HTTPException(status_code=404, detail="File not found on server")
    return FileResponse(message["attachment_path"], filename=message["attachment_name"])


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    index_path = Path("static/index.html")
    if not index_path.exists():
        return {"message": "Chat app"}
    return FileResponse(index_path)
