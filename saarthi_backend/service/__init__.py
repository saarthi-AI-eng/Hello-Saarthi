# Services: 8 only (auth, user, chat, course, video, quiz, note, notification)
from . import auth_service
from . import chat_service
from . import course_service
from . import notification_service
from . import note_service
from . import quiz_service
from . import user_service
from . import video_service

__all__ = [
    "auth_service",
    "chat_service",
    "course_service",
    "notification_service",
    "note_service",
    "quiz_service",
    "user_service",
    "video_service",
]
