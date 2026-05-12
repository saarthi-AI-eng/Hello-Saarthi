# Routers: auth, user, chat, code, course, video, quiz, note, notification, data, admin
from saarthi_backend.routers.api_router import api_router
from saarthi_backend.routers.auth_router import router as auth_router
from saarthi_backend.routers.chat_router import router as chat_router
from saarthi_backend.routers.code_router import router as code_router
from saarthi_backend.routers.course_router import router as course_router
from saarthi_backend.routers.note_router import router as note_router
from saarthi_backend.routers.notification_router import router as notification_router
from saarthi_backend.routers.quiz_router import router as quiz_router
from saarthi_backend.routers.user_router import router as user_router
from saarthi_backend.routers.video_router import router as video_router

__all__ = [
    "api_router",
    "auth_router",
    "chat_router",
    "code_router",
    "user_router",
    "course_router",
    "video_router",
    "quiz_router",
    "note_router",
    "notification_router",
]
