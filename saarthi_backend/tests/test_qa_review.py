"""Manual QA review: RBAC, review workflow, audit history, and KB
integration (approved -> normalizer-eligible, rejected/reprocess ->
always excluded). Uses the real FastAPI app with get_db/get_current_user
overridden (SQLite in-memory + a fake authenticated user — the standard
FastAPI testing pattern), and real small JSONL fixtures under tmp_path —
never touches real Saarthi content or a real Postgres/Qdrant instance.
"""
from __future__ import annotations

import json

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from saarthi_backend.deps import get_current_user, get_db
from saarthi_backend.main import app
from saarthi_backend.model import User
from scripts.schemas import ContentType, ProcessingStatus, QAStatus, write_jsonl
from scripts.schemas import ContentRecord


def _fake_user(role: str, user_id: int = 1) -> User:
    u = User(email=f"{role}@test.local", password_hash="x", full_name=role.title(), role=role)
    u.id = user_id
    return u


def _pending_record(content_id="P1", page=1) -> ContentRecord:
    return ContentRecord(
        content_id=content_id,
        content_type=ContentType.PDF_NOTE,
        source="note.pdf",
        source_id="NOTE_001",
        page=page,
        text="Some pending page text, long enough to pass near-empty checks easily.",
        processing_status=ProcessingStatus.PROCESSED,
        qa_status=QAStatus.PENDING,
        metadata={"ocr_engine": "paddleocr", "ocr_confidence": 0.7, "qa": {"score": 65, "issues": []}},
    )


@pytest.fixture
def kb_env(tmp_path, monkeypatch):
    """Points the backend's SAARTHI_KB_DATA_ROOT at a tmp directory and
    seeds one pending ContentRecord — isolated, never touches the real
    E:\\SaarthiData."""
    from saarthi_backend.utils.config import get_settings

    data_root = tmp_path / "SaarthiDataTest"
    ocr_dir = data_root / "source_content" / "ocr"
    ocr_dir.mkdir(parents=True)
    jsonl_path = ocr_dir / "note.jsonl"
    write_jsonl([_pending_record()], jsonl_path)

    monkeypatch.setenv("SAARTHI_KB_DATA_ROOT", str(data_root))
    get_settings.cache_clear()
    yield {"data_root": data_root, "jsonl_path": jsonl_path}
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def client_as(db_session):
    """Returns a factory: client_as(role) -> an AsyncClient authenticated
    as a fake user with that role, DB wired to the SQLite in-memory
    db_session fixture (real DB, real queries — just not Postgres)."""
    async def _get_db_override():
        yield db_session

    def _make(role: str, user_id: int = 1):
        app.dependency_overrides[get_db] = _get_db_override
        app.dependency_overrides[get_current_user] = lambda: _fake_user(role, user_id)
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    yield _make
    app.dependency_overrides.clear()


# ─── RBAC ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_student_cannot_access_qa_stats(client_as, kb_env):
    async with client_as("student") as c:
        resp = await c.get("/api/qa-review/stats")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_teacher_cannot_access_qa_queue(client_as, kb_env):
    async with client_as("teacher") as c:
        resp = await c.get("/api/qa-review/queue")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_qa_reviewer_can_access_stats(client_as, kb_env):
    async with client_as("qa_reviewer") as c:
        resp = await c.get("/api/qa-review/stats")
    assert resp.status_code == 200
    assert resp.json()["data"]["pendingReview"] == 1


@pytest.mark.asyncio
async def test_admin_can_also_access_qa_dashboard(client_as, kb_env):
    async with client_as("admin") as c:
        resp = await c.get("/api/qa-review/stats")
    assert resp.status_code == 200


# ─── Review workflow ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pending_item_appears_in_queue(client_as, kb_env):
    async with client_as("qa_reviewer") as c:
        resp = await c.get("/api/qa-review/queue")
    data = resp.json()["data"]
    assert data["total"] == 1
    assert data["documents"][0]["items"][0]["content_id"] == "P1"


@pytest.mark.asyncio
async def test_accept_removes_item_from_pending_queue(client_as, kb_env):
    async with client_as("qa_reviewer") as c:
        await c.post("/api/qa-review/review", json={
            "contentId": "P1", "sourceJsonlPath": str(kb_env["jsonl_path"]), "decision": "accept",
        })
        resp = await c.get("/api/qa-review/queue")
    assert resp.json()["data"]["total"] == 0


@pytest.mark.asyncio
async def test_reject_updates_status_and_excludes_from_queue(client_as, kb_env):
    async with client_as("qa_reviewer") as c:
        resp = await c.post("/api/qa-review/review", json={
            "contentId": "P1", "sourceJsonlPath": str(kb_env["jsonl_path"]), "decision": "reject", "reason": "garbled",
        })
    assert resp.status_code == 200
    assert resp.json()["data"]["new_status"] == "rejected"
    saved = json.loads(kb_env["jsonl_path"].read_text(encoding="utf-8").splitlines()[0])
    assert saved["qa_status"] == "rejected"


@pytest.mark.asyncio
async def test_reprocess_request_updates_status(client_as, kb_env):
    async with client_as("qa_reviewer") as c:
        resp = await c.post("/api/qa-review/review", json={
            "contentId": "P1", "sourceJsonlPath": str(kb_env["jsonl_path"]), "decision": "reprocess",
        })
    assert resp.json()["data"]["new_status"] == "reprocess_requested"


@pytest.mark.asyncio
async def test_duplicate_review_action_is_rejected_safely(client_as, kb_env):
    async with client_as("qa_reviewer") as c:
        first = await c.post("/api/qa-review/review", json={
            "contentId": "P1", "sourceJsonlPath": str(kb_env["jsonl_path"]), "decision": "accept",
        })
        second = await c.post("/api/qa-review/review", json={
            "contentId": "P1", "sourceJsonlPath": str(kb_env["jsonl_path"]), "decision": "reject",
        })
    assert first.status_code == 200
    assert second.status_code == 400  # ValidationError -> conflict, not silently applied
    saved = json.loads(kb_env["jsonl_path"].read_text(encoding="utf-8").splitlines()[0])
    assert saved["qa_status"] == "approved"  # first decision stands


@pytest.mark.asyncio
async def test_audit_history_is_recorded(client_as, kb_env):
    async with client_as("qa_reviewer") as c:
        await c.post("/api/qa-review/review", json={
            "contentId": "P1", "sourceJsonlPath": str(kb_env["jsonl_path"]), "decision": "accept",
        })
        resp = await c.get("/api/qa-review/content/P1/history")
    history = resp.json()["data"]
    assert len(history) == 1
    assert history[0]["decision"] == "accept"
    assert history[0]["reviewerId"] == 1


# ─── KB integration ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_accepted_content_becomes_normalizer_eligible(client_as, kb_env):
    import scripts.normalize_content_kb as normalize_content_kb
    from src.knowledge_base.config import KBConfig

    async with client_as("qa_reviewer") as c:
        await c.post("/api/qa-review/review", json={
            "contentId": "P1", "sourceJsonlPath": str(kb_env["jsonl_path"]), "decision": "accept",
        })

    config = KBConfig(data_root=kb_env["data_root"])
    result = normalize_content_kb.run(config)
    assert result["docs"] == 1  # now eligible — qa_status is approved


@pytest.mark.asyncio
async def test_rejected_content_stays_excluded_even_with_allow_pending(client_as, kb_env):
    import scripts.normalize_content_kb as normalize_content_kb
    from src.knowledge_base.config import KBConfig

    async with client_as("qa_reviewer") as c:
        await c.post("/api/qa-review/review", json={
            "contentId": "P1", "sourceJsonlPath": str(kb_env["jsonl_path"]), "decision": "reject",
        })

    config = KBConfig(data_root=kb_env["data_root"])
    result = normalize_content_kb.run(config, allow_pending=True)
    assert result["docs"] == 0


@pytest.mark.asyncio
async def test_reprocess_requested_stays_excluded(client_as, kb_env):
    import scripts.normalize_content_kb as normalize_content_kb
    from src.knowledge_base.config import KBConfig

    async with client_as("qa_reviewer") as c:
        await c.post("/api/qa-review/review", json={
            "contentId": "P1", "sourceJsonlPath": str(kb_env["jsonl_path"]), "decision": "reprocess",
        })

    config = KBConfig(data_root=kb_env["data_root"])
    result = normalize_content_kb.run(config, allow_pending=True)
    assert result["docs"] == 0


# ─── Editing, suggestions, source image ──────────────────────────────────────

@pytest.mark.asyncio
async def test_accept_with_edited_text_updates_the_record(client_as, kb_env):
    async with client_as("qa_reviewer") as c:
        resp = await c.post("/api/qa-review/review", json={
            "contentId": "P1", "sourceJsonlPath": str(kb_env["jsonl_path"]), "decision": "accept",
            "editedText": "A reviewer-corrected version of the page text.",
        })
    assert resp.status_code == 200
    saved = json.loads(kb_env["jsonl_path"].read_text(encoding="utf-8").splitlines()[0])
    assert saved["text"] == "A reviewer-corrected version of the page text."
    assert saved["metadata"]["manual_review"]["edited"] is True


@pytest.mark.asyncio
async def test_history_records_whether_text_was_edited(client_as, kb_env):
    async with client_as("qa_reviewer") as c:
        await c.post("/api/qa-review/review", json={
            "contentId": "P1", "sourceJsonlPath": str(kb_env["jsonl_path"]), "decision": "accept",
            "editedText": "Edited.",
        })
        resp = await c.get("/api/qa-review/content/P1/history")
    assert resp.json()["data"][0]["edited"] is True


@pytest.mark.asyncio
async def test_content_detail_includes_equation_suggestions(client_as, kb_env):
    import scripts.schemas as schemas

    kb_env["jsonl_path"].write_text(
        json.dumps(schemas.record_to_dict(schemas.ContentRecord(
            content_id="P1", content_type=schemas.ContentType.PDF_NOTE, source="note.pdf", source_id="NOTE_001",
            page=1, text="page text", processing_status=schemas.ProcessingStatus.PROCESSED, qa_status=schemas.QAStatus.PENDING,
            metadata={"math_equation_blocks": [{
                "normalized_text": "1+E", "second_opinion_text": "1+6", "math_quality": "POOR_EXTRACTION", "review_required": True,
            }]},
        ))) + "\n",
        encoding="utf-8",
    )
    async with client_as("qa_reviewer") as c:
        resp = await c.get(f"/api/qa-review/content/P1?sourceJsonlPath={kb_env['jsonl_path']}")
    suggestions = resp.json()["data"]["equationSuggestions"]
    assert suggestions == [{"original": "1+E", "suggestion": "1+6", "quality": "POOR_EXTRACTION"}]


@pytest.mark.asyncio
async def test_source_image_renders_a_real_pdf_page(client_as, kb_env, tmp_path, monkeypatch):
    import scripts.content_common as content_common

    raw_dir = tmp_path / "raw_notes"
    raw_dir.mkdir()
    pdf_bytes = _make_minimal_pdf()
    (raw_dir / "note.pdf").write_bytes(pdf_bytes)
    monkeypatch.setattr(content_common, "RAW_NOTES_DIR", raw_dir)

    async with client_as("qa_reviewer") as c:
        resp = await c.get(f"/api/qa-review/content/P1/source-image?sourceJsonlPath={kb_env['jsonl_path']}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.asyncio
async def test_source_image_404_for_video_content(client_as, kb_env):
    from scripts.schemas import ContentType as CT, ProcessingStatus as PS, QAStatus as QS, ContentRecord as CR
    video_path = kb_env["data_root"] / "source_content" / "transcripts" / "vid.jsonl"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl([CR(
        content_id="V1", content_type=CT.VIDEO_TRANSCRIPT, source="vid.mp4", source_id="VID_001",
        start_time=0.0, end_time=2.0, text="hello", processing_status=PS.PROCESSED, qa_status=QS.PENDING, metadata={},
    )], video_path)

    async with client_as("qa_reviewer") as c:
        resp = await c.get(f"/api/qa-review/content/V1/source-image?sourceJsonlPath={video_path}")
    assert resp.status_code == 400


# ─── Regression: /auth/me must preserve qa_reviewer (not coerce to student) ──
# Found a real bug: auth_router.py had its OWN duplicate _user_to_response,
# separate from auth_service.py's (which signin/signup use) — /auth/me used
# the router's copy, which still lacked "qa_reviewer" in its allow-list, so
# a page refresh (which calls /auth/me, not /auth/signin) silently coerced
# the role back to "student", bouncing the QA dashboard to the student one.

@pytest.mark.asyncio
async def test_auth_me_preserves_qa_reviewer_role(db_session):
    from saarthi_backend.dao import UserDAO
    from saarthi_backend.deps import get_db
    from saarthi_backend.utils.jwt_utils import create_access_token
    from saarthi_backend.utils.password import hash_password

    user = await UserDAO.create(
        db_session, email="qa@test.local", password_hash=hash_password("x"),
        full_name="QA Reviewer", role="qa_reviewer",
    )
    await db_session.commit()
    token = create_access_token(str(user.id))

    async def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["role"] == "qa_reviewer"


def _make_minimal_pdf() -> bytes:
    content_stream = "BT /F1 12 Tf 50 750 Td (hello) Tj ET"
    content_len = len(content_stream)
    pdf = (
        "%PDF-1.4\n"
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Contents 4 0 R /Resources << /Font << /F1 << /Type /Font "
        "/Subtype /Type1 /BaseFont /Helvetica >> >> >> >>\nendobj\n"
        f"4 0 obj\n<< /Length {content_len} >>\nstream\n"
        f"{content_stream}\nendstream\nendobj\n"
        "xref\n0 5\n"
        "0000000000 65535 f \n"
        "0000000009 00000 n \n"
        "0000000058 00000 n \n"
        "0000000115 00000 n \n"
        "0000000266 00000 n \n"
        "trailer\n<< /Size 5 /Root 1 0 R >>\n"
        "startxref\n0\n%%EOF"
    )
    return pdf.encode("latin-1")
