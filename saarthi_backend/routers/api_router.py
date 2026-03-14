"""Single API router: all /api routes (auth, chat, users, courses, videos, quizzes, notes, notifications)."""

from fastapi import APIRouter

from saarthi_backend.routers.auth_router import router as auth_router
from saarthi_backend.routers.chat_router import router as chat_router
from saarthi_backend.routers.courses_router import router as courses_router
from saarthi_backend.routers.notes_router import router as notes_router
from saarthi_backend.routers.notifications_router import router as notifications_router
from saarthi_backend.routers.quizzes_router import router as quizzes_router
from saarthi_backend.routers.search_router import router as search_router
from saarthi_backend.routers.upload_router import router as upload_router
from saarthi_backend.routers.user_router import router as user_router
from saarthi_backend.routers.videos_router import router as videos_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(chat_router)
api_router.include_router(user_router)
api_router.include_router(search_router)
api_router.include_router(upload_router)
api_router.include_router(courses_router)
api_router.include_router(videos_router)
api_router.include_router(quizzes_router)
api_router.include_router(notes_router)
api_router.include_router(notifications_router)
