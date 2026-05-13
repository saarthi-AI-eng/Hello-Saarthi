"""Background PDF indexing service.

When a teacher uploads a PDF material, this service:
1. Extracts text from the PDF
2. Chunks it into ~500-token pieces
3. Embeds and stores in a per-course FAISS index
4. Tags every chunk with the material title so _fetch_faiss_context can find it

The indexing runs in a background thread so it never blocks the HTTP response.
"""

import re
import threading
from pathlib import Path
from typing import Optional

from saarthi_backend.utils.logging import get_logger

logger = get_logger(__name__)

_KB_ROOT = Path("knowledge_base") / "courses"
_CHUNK_SIZE = 500       # characters per chunk
_CHUNK_OVERLAP = 80


def _extract_text_from_pdf(path: Path) -> str:
    """Extract plain text from a PDF file using pypdf (no OCR needed for text PDFs)."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            pages.append(text.strip())
        return "\n\n".join(p for p in pages if p)
    except Exception as e:
        logger.warning("PDF text extraction failed for %s: %s", path, e)
        return ""


def _extract_text_from_txt(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        logger.warning("Text extraction failed for %s: %s", path, e)
        return ""


def _chunk_text(text: str, chunk_size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def _index_document_sync(
    file_path: Path,
    material_title: str,
    course_id: int,
    material_id: int,
) -> bool:
    """Blocking: extract, chunk, embed, and upsert into course FAISS index."""
    try:
        from langchain_community.vectorstores import FAISS
        from langchain_openai import OpenAIEmbeddings
        from langchain_core.documents import Document
    except ImportError:
        logger.error("LangChain / OpenAI packages not available for indexing")
        return False

    # Extract text based on file type
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        text = _extract_text_from_pdf(file_path)
    elif ext in (".txt",):
        text = _extract_text_from_txt(file_path)
    else:
        # For .doc, .docx, .ppt, .pptx — skip for now, no binary parser available without heavy deps
        logger.info("Skipping indexing for unsupported type %s (material: %s)", ext, material_title)
        return False

    if not text or len(text.strip()) < 50:
        logger.info("No extractable text in %s, skipping indexing", file_path.name)
        return False

    chunks = _chunk_text(text)
    if not chunks:
        return False

    # Build LangChain Documents with metadata so _fetch_faiss_context can filter by source
    source_tag = material_title.lower().replace(" ", "_")
    docs = [
        Document(
            page_content=chunk,
            metadata={
                "source": source_tag,
                "material_title": material_title,
                "course_id": course_id,
                "material_id": material_id,
                "chunk_index": i,
            },
        )
        for i, chunk in enumerate(chunks)
    ]

    try:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        index_path = _KB_ROOT / str(course_id) / "vector_store"
        index_path.mkdir(parents=True, exist_ok=True)

        if (index_path / "index.faiss").exists():
            # Merge into existing course index
            vs = FAISS.load_local(
                str(index_path), embeddings, allow_dangerous_deserialization=True
            )
            vs.add_documents(docs)
        else:
            # Create fresh index for this course
            vs = FAISS.from_documents(docs, embeddings)

        vs.save_local(str(index_path))
        logger.info(
            "Indexed %d chunks for material '%s' (course %d) into %s",
            len(docs), material_title, course_id, index_path,
        )
        return True

    except Exception as e:
        logger.error("FAISS indexing failed for material '%s': %s", material_title, e)
        return False


def index_material_background(
    file_path: Path,
    material_title: str,
    course_id: int,
    material_id: int,
) -> None:
    """Fire-and-forget: index a material in a background thread."""
    def _run():
        logger.info("Background indexing started for '%s' (course %d)", material_title, course_id)
        ok = _index_document_sync(file_path, material_title, course_id, material_id)
        if ok:
            logger.info("Background indexing complete for '%s'", material_title)
        else:
            logger.warning("Background indexing skipped/failed for '%s'", material_title)

    t = threading.Thread(target=_run, daemon=True)
    t.start()


def delete_material_from_index(
    material_title: str,
    course_id: int,
    material_id: int,
) -> None:
    """Remove a material's chunks from the course FAISS index on deletion."""
    def _run():
        try:
            from langchain_community.vectorstores import FAISS
            from langchain_openai import OpenAIEmbeddings

            index_path = _KB_ROOT / str(course_id) / "vector_store"
            if not (index_path / "index.faiss").exists():
                return

            embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
            vs = FAISS.load_local(
                str(index_path), embeddings, allow_dangerous_deserialization=True
            )

            # Find and remove chunks belonging to this material
            ids_to_remove = [
                doc_id for doc_id, doc in vs.docstore._dict.items()
                if doc.metadata.get("material_id") == material_id
            ]
            if ids_to_remove:
                vs.delete(ids_to_remove)
                vs.save_local(str(index_path))
                logger.info(
                    "Removed %d chunks for material_id=%d from course %d index",
                    len(ids_to_remove), material_id, course_id,
                )
        except Exception as e:
            logger.warning("Failed to remove material from index: %s", e)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
