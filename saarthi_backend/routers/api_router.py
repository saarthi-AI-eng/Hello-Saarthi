"""Single API router: auth, user, chat, course, video, quiz, note, notification, data, admin, code."""

from fastapi import APIRouter

from saarthi_backend.routers.admin_router import router as admin_router
from saarthi_backend.routers.auth_router import router as auth_router
from saarthi_backend.routers.chat_router import router as chat_router
from saarthi_backend.routers.code_router import router as code_router
from saarthi_backend.routers.course_router import router as course_router
from saarthi_backend.routers.data_router import router as data_router
from saarthi_backend.routers.note_router import router as note_router
from saarthi_backend.routers.notification_router import router as notification_router
from saarthi_backend.routers.quiz_router import router as quiz_router
from saarthi_backend.routers.teacher_router import router as teacher_router
from saarthi_backend.routers.user_router import router as user_router
from saarthi_backend.routers.video_router import router as video_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(chat_router)
api_router.include_router(code_router)
api_router.include_router(user_router)
api_router.include_router(course_router)
api_router.include_router(video_router)
api_router.include_router(quiz_router)
api_router.include_router(note_router)
api_router.include_router(notification_router)
api_router.include_router(data_router)
api_router.include_router(teacher_router)
api_router.include_router(admin_router)
