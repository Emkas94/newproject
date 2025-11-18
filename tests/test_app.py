from pathlib import Path
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.db import reset_database
from app.main import app


client = TestClient(app)


def setup_function():
    reset_database()


def create_user(username: str, is_admin: bool = False):
    response = client.post("/users", json={"username": username, "is_admin": is_admin})
    assert response.status_code == 200
    return response.json()


def test_create_users_and_chat():
    alice = create_user("alice")
    bob = create_user("bob")

    resp = client.post(
        "/chats",
        json={"participant_ids": [alice["id"], bob["id"]], "is_group": False},
    )
    assert resp.status_code == 200
    chat = resp.json()
    assert chat["is_group"] is False

    user_chats = client.get(f"/users/{alice['id']}/chats")
    assert user_chats.status_code == 200
    assert len(user_chats.json()) == 1


def test_send_text_message():
    alice = create_user("alice")
    bob = create_user("bob")

    chat_resp = client.post(
        "/chats",
        json={"participant_ids": [alice["id"], bob["id"]], "is_group": False},
    )
    chat_id = chat_resp.json()["id"]

    message_resp = client.post(
        f"/chats/{chat_id}/messages",
        data={"sender_id": alice["id"], "content": "Привет, мир! 🚀"},
    )
    assert message_resp.status_code == 200
    message = message_resp.json()
    assert message["content"].startswith("Привет")

    messages_resp = client.get(f"/chats/{chat_id}/messages")
    assert messages_resp.status_code == 200
    messages = messages_resp.json()
    assert len(messages) == 1
    assert messages[0]["sender"]["username"] == "alice"


def test_file_upload_message(tmp_path):
    alice = create_user("alice")
    bob = create_user("bob")
    chat_resp = client.post(
        "/chats",
        json={"participant_ids": [alice["id"], bob["id"]], "is_group": True, "name": "Project"},
    )
    chat_id = chat_resp.json()["id"]

    file_path = tmp_path / "note.txt"
    file_path.write_text("attachment")

    with file_path.open("rb") as f:
        message_resp = client.post(
            f"/chats/{chat_id}/messages",
            data={"sender_id": bob["id"], "content": "Документ"},
            files={"file": (file_path.name, f, "text/plain")},
        )
    assert message_resp.status_code == 200
    message = message_resp.json()
    assert message["attachment_name"] == "note.txt"

    download_resp = client.get(f"/messages/{message['id']}/file")
    assert download_resp.status_code == 200
    assert download_resp.content == b"attachment"


def test_duplicate_filenames_are_preserved_and_unique(tmp_path):
    # Clean uploads directory to ensure deterministic content
    upload_dir = Path("uploads")
    if upload_dir.exists():
        for f in upload_dir.iterdir():
            if f.is_file():
                f.unlink()

    alice = create_user("alice")
    bob = create_user("bob")

    chat_id = client.post(
        "/chats",
        json={"participant_ids": [alice["id"], bob["id"]], "is_group": True, "name": "Docs"},
    ).json()["id"]

    file1 = tmp_path / "report.txt"
    file2 = tmp_path / "report.txt.copy"
    file1.write_text("first-version")
    file2.write_text("second-version")

    with file1.open("rb") as f1:
        resp1 = client.post(
            f"/chats/{chat_id}/messages",
            data={"sender_id": alice["id"], "content": "v1"},
            files={"file": ("report.txt", f1, "text/plain")},
        )
    assert resp1.status_code == 200
    message1 = resp1.json()

    with file2.open("rb") as f2:
        resp2 = client.post(
            f"/chats/{chat_id}/messages",
            data={"sender_id": bob["id"], "content": "v2"},
            files={"file": ("report.txt", f2, "text/plain")},
        )
    assert resp2.status_code == 200
    message2 = resp2.json()

    assert message1["attachment_name"] == "report.txt"
    assert message2["attachment_name"] == "report.txt"
    assert message1["id"] != message2["id"]

    download1 = client.get(f"/messages/{message1['id']}/file")
    download2 = client.get(f"/messages/{message2['id']}/file")
    assert download1.content == b"first-version"
    assert download2.content == b"second-version"


def test_bot_flow():
    owner = create_user("owner")
    teammate = create_user("teammate")

    chat_resp = client.post(
        "/chats",
        json={"participant_ids": [owner["id"], teammate["id"]], "is_group": True, "name": "Squad"},
    )
    chat_id = chat_resp.json()["id"]

    bot_resp = client.post("/bots", json={"owner_id": owner["id"], "name": "Helper"})
    assert bot_resp.status_code == 200
    bot_data = bot_resp.json()

    add_resp = client.post(
        f"/chats/{chat_id}/bots/{bot_data['id']}",
        json={"owner_id": owner["id"]},
    )
    assert add_resp.status_code == 200
    assert add_resp.json()["status"] in {"added", "already_added"}

    user_msg = client.post(
        f"/chats/{chat_id}/messages",
        data={"sender_id": owner["id"], "content": "ping"},
    )
    assert user_msg.status_code == 200

    bot_msg = client.post(
        f"/bots/{bot_data['id']}/messages",
        json={"token": bot_data["token"], "chat_id": chat_id, "content": "pong"},
    )
    assert bot_msg.status_code == 200

    updates = client.post(
        f"/bots/{bot_data['id']}/updates",
        json={"token": bot_data["token"], "since_id": 0},
    )
    assert updates.status_code == 200
    payload = updates.json()
    assert payload["last_id"] >= 2
    contents = [item["content"] for item in payload["updates"]]
    assert "ping" in contents and "pong" in contents


def test_admin_can_read_logs_and_delete_messages():
    admin = create_user("admin", is_admin=True)
    alice = create_user("alice")
    bob = create_user("bob")

    chat_resp = client.post(
        "/chats",
        json={"participant_ids": [alice["id"], bob["id"]], "is_group": False},
    )
    chat_id = chat_resp.json()["id"]

    msg_resp = client.post(
        f"/chats/{chat_id}/messages",
        data={"sender_id": alice["id"], "content": "secret"},
    )
    assert msg_resp.status_code == 200
    message_id = msg_resp.json()["id"]

    non_admin_logs = client.get(f"/admin/chats/{chat_id}/logs", params={"admin_id": alice["id"]})
    assert non_admin_logs.status_code == 403

    logs_resp = client.get(f"/admin/chats/{chat_id}/logs", params={"admin_id": admin["id"]})
    assert logs_resp.status_code == 200
    logs = logs_resp.json()["messages"]
    assert len(logs) == 1 and logs[0]["id"] == message_id

    delete_resp = client.delete(f"/admin/messages/{message_id}", params={"admin_id": admin["id"]})
    assert delete_resp.status_code == 200
    after_logs = client.get(f"/admin/chats/{chat_id}/logs", params={"admin_id": admin["id"]}).json()["messages"]
    assert after_logs == []
    user_view = client.get(f"/chats/{chat_id}/messages").json()
    assert user_view == []


def test_favorites_for_chats_and_messages():
    alice = create_user("alice")
    bob = create_user("bob")

    chat_id = client.post(
        "/chats",
        json={"participant_ids": [alice["id"], bob["id"]], "is_group": True, "name": "Favs"},
    ).json()["id"]

    message_resp = client.post(
        f"/chats/{chat_id}/messages",
        data={"sender_id": alice["id"], "content": "hello"},
    )
    message_id = message_resp.json()["id"]

    fav_chat = client.post("/favorites/chats", json={"user_id": alice["id"], "chat_id": chat_id})
    assert fav_chat.status_code == 200
    assert fav_chat.json()["status"] == "favorited"

    fav_msg = client.post(
        "/favorites/messages",
        json={"user_id": alice["id"], "message_id": message_id},
    )
    assert fav_msg.status_code == 200
    assert fav_msg.json()["status"] == "favorited"

    favorites = client.get(f"/users/{alice['id']}/favorites").json()
    assert any(c["id"] == chat_id for c in favorites["chats"])
    assert any(m["id"] == message_id for m in favorites["messages"])

    messages_for_user = client.get(f"/chats/{chat_id}/messages", params={"user_id": alice["id"]}).json()
    assert messages_for_user[0]["is_favorite"] is True

    remove_chat = client.delete(
        "/favorites/chats", params={"user_id": alice["id"], "chat_id": chat_id}
    )
    assert remove_chat.json()["status"] == "removed"
    remove_message = client.delete(
        "/favorites/messages", params={"user_id": alice["id"], "message_id": message_id}
    )
    assert remove_message.json()["status"] == "removed"
