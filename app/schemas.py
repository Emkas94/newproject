from dataclasses import dataclass
from typing import List, Optional


class ValidationError(ValueError):
    pass


@dataclass
class UserCreate:
    username: str
    is_admin: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "UserCreate":
        username = (data.get("username") or "").strip()
        if len(username) < 3 or len(username) > 50:
            raise ValidationError("Username must be between 3 and 50 characters")
        is_admin = bool(data.get("is_admin", False))
        return cls(username=username, is_admin=is_admin)


@dataclass
class UserOut:
    id: int
    username: str


@dataclass
class ChatCreate:
    name: Optional[str]
    participant_ids: List[int]
    is_group: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "ChatCreate":
        participants = data.get("participant_ids") or []
        if not isinstance(participants, list) or not participants:
            raise ValidationError("participant_ids must contain at least one user")
        participant_ids = []
        for item in participants:
            try:
                participant_ids.append(int(item))
            except Exception:
                raise ValidationError("participant_ids must be integers")
        name = data.get("name")
        is_group = bool(data.get("is_group", False))
        return cls(name=name, participant_ids=participant_ids, is_group=is_group)


@dataclass
class MessageCreate:
    sender_id: int
    content: Optional[str] = None

    @classmethod
    def from_form(cls, form: dict) -> "MessageCreate":
        sender_id = form.get("sender_id")
        if sender_id is None:
            raise ValidationError("sender_id is required")
        try:
            sender_id = int(sender_id)
        except Exception:
            raise ValidationError("sender_id must be an integer")
        content = form.get("content")
        return cls(sender_id=sender_id, content=content)


@dataclass
class BotCreate:
    owner_id: int
    name: str

    @classmethod
    def from_dict(cls, data: dict) -> "BotCreate":
        owner_id = data.get("owner_id")
        if owner_id is None:
            raise ValidationError("owner_id is required")
        try:
            owner_id = int(owner_id)
        except Exception:
            raise ValidationError("owner_id must be an integer")

        name = (data.get("name") or "").strip()
        if len(name) < 2 or len(name) > 50:
            raise ValidationError("name must be between 2 and 50 characters")
        return cls(owner_id=owner_id, name=name)


@dataclass
class BotSend:
    chat_id: int
    content: str

    @classmethod
    def from_dict(cls, data: dict) -> "BotSend":
        chat_id = data.get("chat_id")
        if chat_id is None:
            raise ValidationError("chat_id is required")
        try:
            chat_id = int(chat_id)
        except Exception:
            raise ValidationError("chat_id must be an integer")

        content = (data.get("content") or "").strip()
        if not content:
            raise ValidationError("content is required for bot messages")
        return cls(chat_id=chat_id, content=content)


@dataclass
class FavoriteChat:
    user_id: int
    chat_id: int

    @classmethod
    def from_dict(cls, data: dict) -> "FavoriteChat":
        if "user_id" not in data or "chat_id" not in data:
            raise ValidationError("user_id and chat_id are required")
        try:
            user_id = int(data.get("user_id"))
            chat_id = int(data.get("chat_id"))
        except Exception:
            raise ValidationError("user_id and chat_id must be integers")
        return cls(user_id=user_id, chat_id=chat_id)


@dataclass
class FavoriteMessage:
    user_id: int
    message_id: int

    @classmethod
    def from_dict(cls, data: dict) -> "FavoriteMessage":
        if "user_id" not in data or "message_id" not in data:
            raise ValidationError("user_id and message_id are required")
        try:
            user_id = int(data.get("user_id"))
            message_id = int(data.get("message_id"))
        except Exception:
            raise ValidationError("user_id and message_id must be integers")
        return cls(user_id=user_id, message_id=message_id)
