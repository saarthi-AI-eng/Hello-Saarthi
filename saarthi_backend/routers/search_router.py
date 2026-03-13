"""Search: GET /search?q=... (under /api, paginated per type)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.dao.search_dao import search
from saarthi_backend.deps import get_db, get_pagination
from saarthi_backend.schema.pagination_schemas import PaginationParams
from saarthi_backend.schema.search_schemas import SearchItem, SearchResponse

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search_api(
    db: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    q: str = "",
):
    """Search courses, materials, videos (paginated per type: limit/offset apply to each)."""
    if not q or len(q.strip()) < 2:
        return SearchResponse(limit=pagination.limit, offset=pagination.offset)
    courses, materials, videos, total_courses, total_materials, total_videos = await search(
        db,
        q.strip(),
        limit_per_type=pagination.limit,
        offset_per_type=pagination.offset,
    )
    return SearchResponse(
        courses=[
            SearchItem(type="course", id=str(c.id), title=c.title, subtitle=c.code, link=f"/courses/{c.id}")
            for c in courses
        ],
        materials=[
            SearchItem(type="material", id=str(m.id), title=m.title, subtitle=m.type, link=m.url)
            for m in materials
        ],
        videos=[
            SearchItem(type="video", id=str(v.id), title=v.title, subtitle=f"{v.duration_seconds}s", link=f"/videos/{v.id}")
            for v in videos
        ],
        totalCourses=total_courses,
        totalMaterials=total_materials,
        totalVideos=total_videos,
        limit=pagination.limit,
        offset=pagination.offset,
    )
