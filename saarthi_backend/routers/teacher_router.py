"""Teacher AI assistant — intent detection, course scaffolding, playlist import.

Two-step flow:
  1. POST /teacher/analyse  — AI reads file/message, returns structured preview (no DB writes)
  2. POST /teacher/execute  — teacher confirms, this calls existing course APIs to write to DB
"""

import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.deps import get_current_user, get_db
from saarthi_backend.model import User
from saarthi_backend.model.course_model import Course, Material, Assignment
from saarthi_backend.service import course_service
from saarthi_backend.service.indexing_service import index_material_background

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/teacher", tags=["teacher"])

_UPLOAD_DIR = Path("uploads")
_ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt"}
_MAX_MB = 20


# ── Schemas ───────────────────────────────────────────────────────────────────

class TopicPreview(BaseModel):
    title: str
    assignments: list[str] = []
    materials: list[str] = []


class CoursePreview(BaseModel):
    title: str
    code: str
    instructor: str
    description: str
    topics: list[TopicPreview] = []


class VideoPreview(BaseModel):
    title: str
    url: str
    youtubeId: str


class PlaylistPreview(BaseModel):
    playlistTitle: str
    videos: list[VideoPreview]
    courseId: str | None = None
    topic: str | None = None


class MaterialPreview(BaseModel):
    title: str
    description: str
    type: str  # pdf / doc / slide / link
    fileUrl: str | None = None
    courseId: str | None = None
    topic: str | None = None


class AnalyseResponse(BaseModel):
    intent: str  # create_course | add_material | playlist_import | general
    question: str | None = None   # clarifying question to ask teacher
    coursePreview: CoursePreview | None = None
    playlistPreview: PlaylistPreview | None = None
    materialPreview: MaterialPreview | None = None


class ExecuteCourseRequest(BaseModel):
    coursePreview: CoursePreview
    instructorName: str


class ExecutePlaylistRequest(BaseModel):
    playlistPreview: PlaylistPreview
    courseId: str
    topic: str | None = None


class ExecuteMaterialRequest(BaseModel):
    materialPreview: MaterialPreview
    courseId: str
    topic: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_teacher(user: User) -> None:
    if user.role not in ("admin", "teacher"):
        raise HTTPException(status_code=403, detail="Teacher or admin role required")


def _extract_youtube_id(url: str) -> str | None:
    patterns = [
        r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def _extract_playlist_id(url: str) -> str | None:
    m = re.search(r"list=([A-Za-z0-9_-]+)", url)
    return m.group(1) if m else None


def _fetch_playlist_videos_sync(playlist_id: str) -> list[dict]:
    """Fetch all video titles and IDs from a YouTube playlist via YouTube Data API v3."""
    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="YOUTUBE_API_KEY not configured")

    import requests as _requests

    videos = []
    page_token = None
    base = "https://www.googleapis.com/youtube/v3/playlistItems"

    while len(videos) < 50:
        params: dict = {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": 50,
            "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token

        resp = _requests.get(base, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("items") or []:
            snippet = item.get("snippet") or {}
            vid_id = (snippet.get("resourceId") or {}).get("videoId")
            title = snippet.get("title") or "Untitled"
            if vid_id and title != "Deleted video" and title != "Private video":
                videos.append({
                    "title": title,
                    "youtubeId": vid_id,
                    "url": f"https://www.youtube.com/watch?v={vid_id}",
                })

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return videos


def _fetch_playlist_videos_with_title_sync(playlist_id: str) -> tuple[list[dict], str]:
    """Fetch videos + playlist title in one shot."""
    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="YOUTUBE_API_KEY not configured")

    import requests as _requests

    # Fetch playlist metadata for title
    meta = _requests.get(
        "https://www.googleapis.com/youtube/v3/playlists",
        params={"part": "snippet", "id": playlist_id, "key": api_key},
        timeout=10,
    ).json()
    items = meta.get("items") or []
    playlist_title = items[0]["snippet"]["title"] if items else ""

    videos = _fetch_playlist_videos_sync(playlist_id)
    return videos, playlist_title


def _extract_pdf_text_sync(content: bytes, filename: str) -> str:
    """Extract raw text from a PDF or text file."""
    ext = Path(filename).suffix.lower()
    if ext == ".txt":
        try:
            return content.decode("utf-8", errors="ignore")[:80_000]
        except Exception:
            return ""
    if ext == ".pdf":
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=content, filetype="pdf")
            pages = []
            for page in doc:
                pages.append(page.get_text())
                if sum(len(p) for p in pages) > 80_000:
                    break
            doc.close()
            return "\n".join(pages)[:80_000]
        except Exception:
            pass
        # fallback: pdfplumber
        try:
            import io
            import pdfplumber
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                texts = []
                for page in pdf.pages[:30]:
                    t = page.extract_text() or ""
                    texts.append(t)
                    if sum(len(x) for x in texts) > 80_000:
                        break
                return "\n".join(texts)[:80_000]
        except Exception as e:
            logger.warning("PDF extraction failed: %s", e)
            return ""
    return ""


async def _ai_parse_syllabus(text: str, instructor_name: str) -> CoursePreview | None:
    """Send syllabus text to Claude/GPT and get back structured course JSON."""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

        prompt = (
            "You are helping a teacher set up their course on Saarthi.\n"
            "Extract the course structure from this syllabus and return ONLY valid JSON.\n\n"
            "Return this exact structure:\n"
            "{\n"
            '  "title": "course title",\n'
            '  "code": "short course code like EE301",\n'
            '  "description": "1-2 sentence description",\n'
            '  "topics": [\n'
            '    {\n'
            '      "title": "topic/week title",\n'
            '      "assignments": ["assignment title 1", "assignment title 2"],\n'
            '      "materials": ["material/reading title 1"]\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- topics should be grouped by week or unit, max 16 topics\n"
            "- assignments: only things explicitly mentioned as assignments/labs/projects/exams\n"
            "- materials: readings, references, lecture notes mentioned\n"
            "- If info is missing, make a reasonable inference from context\n"
            "- Return ONLY the JSON object, no explanation\n\n"
            f"SYLLABUS TEXT:\n{text[:60_000]}"
        )

        response = await client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)

        topics = []
        for t in data.get("topics") or []:
            topics.append(TopicPreview(
                title=t.get("title", ""),
                assignments=t.get("assignments") or [],
                materials=t.get("materials") or [],
            ))

        return CoursePreview(
            title=data.get("title", "Untitled Course"),
            code=data.get("code", "COURSE101"),
            instructor=instructor_name,
            description=data.get("description", ""),
            topics=topics,
        )
    except Exception as e:
        logger.exception("AI syllabus parse failed: %s", e)
        return None


async def _ai_classify_message(message: str, courses: list[dict]) -> dict[str, Any]:
    """Classify teacher message intent for text-only messages."""
    return await _ai_classify_message_with_file(message, "", courses)


async def _ai_classify_message_with_file(message: str, filename: str, courses: list[dict]) -> dict[str, Any]:
    """Classify teacher intent when a file is also present."""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

        course_list = json.dumps([{"id": c["id"], "title": c["title"]} for c in courses[:10]])
        file_context = f'\nUploaded file: "{filename}"' if filename else ""

        prompt = (
            "A teacher sent this message (and possibly a file). Classify their intent.\n\n"
            f'Teacher message: "{message}"{file_context}\n\n'
            f"Teacher's existing courses: {course_list}\n\n"
            "INTENT RULES — read carefully:\n"
            '- "create_course": teacher wants to CREATE A NEW COURSE from this file/content. '
            "Signs: they say 'new course', 'create course', 'called it X', 'make a course', "
            "or uploaded a PDF and their message implies course creation.\n"
            '- "add_material": teacher wants to ADD this file to an EXISTING course.\n'
            '- "playlist_import": message contains a YouTube playlist URL.\n'
            '- "general": just a question, no course/file action.\n\n'
            "IMPORTANT: If the teacher uploaded a PDF AND mentioned a course name or said "
            "'new course' or 'create' — that is create_course, NOT add_material.\n\n"
            "Return ONLY JSON:\n"
            "{\n"
            '  "intent": "create_course | add_material | playlist_import | general",\n'
            '  "courseName": "the name teacher wants for the new course, if mentioned, else null",\n'
            '  "courseId": "matching existing course id if add_material, else null",\n'
            '  "topic": "topic name if mentioned else null",\n'
            '  "question": "clarifying question if critical info missing, else null"\n'
            "}"
        )

        response = await client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content or "{}")
    except Exception as e:
        logger.exception("Intent classification failed: %s", e)
        return {"intent": "general"}


# ── Endpoint 1: Analyse (no DB writes) ───────────────────────────────────────

@router.post("/analyse", response_model=AnalyseResponse)
async def analyse(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    message: str = Form(default=""),
    file: UploadFile | None = File(default=None),
):
    """
    Step 1 — AI reads what the teacher sent and returns a structured preview.
    Nothing is written to the DB. Teacher reviews and confirms via /execute/*.
    """
    _require_teacher(user)

    # Fetch teacher's existing courses for context
    result = await db.execute(
        select(Course).where(Course.owner_id == user.id)
    )
    courses = [{"id": str(c.id), "title": c.title} for c in result.scalars().all()]

    # ── Case 1: File uploaded ─────────────────────────────────────────────────
    if file and file.filename:
        ext = Path(file.filename).suffix.lower()
        if ext not in _ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"File type not supported. Use: {', '.join(_ALLOWED_EXTENSIONS)}")

        content = await file.read()
        if len(content) > _MAX_MB * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"File too large (max {_MAX_MB}MB)")

        # Save file temporarily
        _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = f"{uuid.uuid4().hex}{ext}"
        dest = _UPLOAD_DIR / safe_name
        await run_in_threadpool(dest.write_bytes, content)
        file_url = f"/uploads/{safe_name}"

        # Extract text
        text = await run_in_threadpool(_extract_pdf_text_sync, content, file.filename)

        # Classify intent from message + file
        combined_msg = message or f"I uploaded {file.filename}"
        classification = await _ai_classify_message_with_file(combined_msg, file.filename or "", courses)
        intent = classification.get("intent", "add_material")

        # Any hint of course creation → scaffold full course structure
        if intent == "create_course":
            preview = await _ai_parse_syllabus(text, user.fullName or user.email)
            if preview:
                # Override title if teacher named it explicitly
                if classification.get("courseName"):
                    preview.title = classification["courseName"]
                return AnalyseResponse(
                    intent="create_course",
                    question=None,
                    coursePreview=preview,
                )

        # Generic material upload
        title = Path(file.filename).stem.replace("_", " ").replace("-", " ").title()
        mat_type = "pdf" if ext == ".pdf" else ("slide" if ext in (".ppt", ".pptx") else "doc")
        return AnalyseResponse(
            intent="add_material",
            question=classification.get("question"),
            materialPreview=MaterialPreview(
                title=title,
                description=f"Uploaded from {file.filename}",
                type=mat_type,
                fileUrl=file_url,
                courseId=classification.get("courseId"),
                topic=classification.get("topic"),
            ),
        )

    # ── Case 2: Message only ──────────────────────────────────────────────────
    if message:
        # Detect YouTube playlist URL in message
        playlist_id = _extract_playlist_id(message)
        if playlist_id:
            videos_raw, playlist_title = await run_in_threadpool(
                _fetch_playlist_videos_with_title_sync, playlist_id
            )
            videos = [
                VideoPreview(title=v["title"], url=v["url"], youtubeId=v["youtubeId"])
                for v in videos_raw
            ]
            classification = await _ai_classify_message(message, courses)
            return AnalyseResponse(
                intent="playlist_import",
                question=classification.get("question") or (
                    None if classification.get("courseId") else
                    "Which course should I add these videos to?"
                ),
                playlistPreview=PlaylistPreview(
                    playlistTitle=playlist_title or f"YouTube Playlist ({len(videos)} videos)",
                    videos=videos,
                    courseId=classification.get("courseId"),
                    topic=classification.get("topic"),
                ),
            )

        # General message — classify intent
        classification = await _ai_classify_message(message, courses)
        intent = classification.get("intent", "general")

        if intent == "general":
            return AnalyseResponse(intent="general", question=None)

        return AnalyseResponse(
            intent=intent,
            question=classification.get("question"),
        )

    return AnalyseResponse(intent="general", question=None)


# ── Endpoint 2a: Execute — create full course from preview ───────────────────

@router.post("/execute/course", status_code=201)
async def execute_create_course(
    body: ExecuteCourseRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Step 2 — Teacher confirmed the course preview. Create course + topics + assignments in DB.
    """
    _require_teacher(user)
    p = body.coursePreview

    # Create the course
    course = await course_service.create_course(
        db,
        title=p.title,
        code=p.code,
        instructor=p.instructor or body.instructorName,
        description=p.description,
        owner_id=user.id,
    )
    await db.flush()  # get course.id before creating children

    created_assignments = []
    created_materials = []

    for i, topic in enumerate(p.topics):
        for asgn_title in topic.assignments:
            asgn = Assignment(
                course_id=course.id,
                title=asgn_title,
                description="",
                topic=topic.title,
                points=100,
                due_date="",
            )
            db.add(asgn)
            created_assignments.append(asgn_title)

        for mat_title in topic.materials:
            mat = Material(
                course_id=course.id,
                title=mat_title,
                type="link",
                url="",
                description="",
                topic=topic.title,
            )
            db.add(mat)
            created_materials.append(mat_title)

    await db.commit()

    return {
        "courseId": str(course.id),
        "title": course.title,
        "topicsCreated": len(p.topics),
        "assignmentsCreated": len(created_assignments),
        "materialsCreated": len(created_materials),
    }


# ── Endpoint 2b: Execute — bulk import YouTube playlist ─────────────────────

@router.post("/execute/playlist", status_code=201)
async def execute_playlist_import(
    body: ExecutePlaylistRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Step 2 — Teacher confirmed the playlist. Add all videos as materials + auto-index transcripts.
    """
    _require_teacher(user)

    course_id = int(body.courseId)
    course = await course_service.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if course.owner_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not your course")

    added = []
    for v in body.playlistPreview.videos:
        embed_url = f"https://www.youtube.com/embed/{v.youtubeId}"
        mat = Material(
            course_id=course_id,
            title=v.title,
            type="link",
            url=v.url,
            description="",
            topic=body.topic or "",
        )
        db.add(mat)
        await db.flush()

        # Auto-index transcript in background
        from saarthi_backend.service.indexing_service import auto_index_youtube_video
        auto_index_youtube_video(mat.id, v.title, v.url, embed_url)
        added.append(v.title)

    await db.commit()
    return {"videosAdded": len(added), "titles": added}


# ── Endpoint 2c: Execute — add single material to course ────────────────────

@router.post("/execute/material", status_code=201)
async def execute_add_material(
    body: ExecuteMaterialRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Step 2 — Teacher confirmed the material. Add to course and trigger FAISS indexing.
    """
    _require_teacher(user)

    course_id = int(body.courseId)
    course = await course_service.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if course.owner_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Not your course")

    p = body.materialPreview
    mat = Material(
        course_id=course_id,
        title=p.title,
        type=p.type,
        url=p.fileUrl or "",
        description=p.description,
        topic=body.topic or p.topic or "",
    )
    db.add(mat)
    await db.flush()

    # Trigger FAISS indexing if it's a local file
    if p.fileUrl and p.fileUrl.startswith("/uploads/"):
        file_path = Path("uploads") / Path(p.fileUrl).name
        if file_path.exists():
            import asyncio
            asyncio.create_task(
                run_in_threadpool(
                    index_material_background,
                    str(file_path),
                    course_id,
                    mat.id,
                    p.title,
                )
            )

    await db.commit()
    return {"materialId": str(mat.id), "title": mat.title, "courseId": str(course_id)}


# ── Endpoint 3: Teacher's courses list (for chat context) ───────────────────

@router.get("/courses")
async def teacher_courses(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Return teacher's own courses for populating chat context."""
    _require_teacher(user)
    result = await db.execute(
        select(Course).where(Course.owner_id == user.id).order_by(Course.created_at.desc())
    )
    courses = result.scalars().all()
    return [{"id": str(c.id), "title": c.title, "code": c.code} for c in courses]
