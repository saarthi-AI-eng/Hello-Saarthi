# Routers
from saarthi_backend.routers.api_router import api_router
from saarthi_backend.routers.auth_router import router as auth_router
from saarthi_backend.routers.chat_router import router as chat_router
from saarthi_backend.routers.courses_router import router as courses_router
from saarthi_backend.routers.notes_router import router as notes_router
from saarthi_backend.routers.notifications_router import router as notifications_router
from saarthi_backend.routers.quizzes_router import router as quizzes_router
from saarthi_backend.routers.user_router import router as user_router
from saarthi_backend.routers.videos_router import router as videos_router

__all__ = [
    "api_router",
    "auth_router",
    "chat_router",
    "user_router",
    "courses_router",
    "videos_router",
    "quizzes_router",
    "notes_router",
    "notifications_router",
]
