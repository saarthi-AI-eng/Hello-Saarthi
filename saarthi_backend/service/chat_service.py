"""Chat feature service: conversations and messages."""

from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.ai import run_chat
from saarthi_backend.dao import ChatMessageDAO, ConversationDAO
from saarthi_backend.model import ChatMessage, Conversation


async def create_conversation(db: AsyncSession, user_id: int, title: str = "New Chat") -> Conversation:
    return await ConversationDAO.create(db, user_id, title=title)


async def list_conversations(
    db: AsyncSession, user_id: int, limit: int = 20, offset: int = 0
) -> tuple[list[Conversation], int]:
    items = await ConversationDAO.list_by_user(db, user_id, limit=limit, offset=offset)
    total = await ConversationDAO.count_by_user(db, user_id)
    return items, total


async def get_conversation(
    db: AsyncSession, conversation_id: int, user_id: int
) -> tuple[Conversation | None, list[ChatMessage]]:
    c = await ConversationDAO.get_by_id(db, conversation_id, user_id)
    if not c:
        return None, []
    messages = await ChatMessageDAO.list_by_conversation(db, conversation_id)
    return c, messages


async def update_conversation_title(
    db: AsyncSession, conversation_id: int, user_id: int, title: str
) -> Conversation | None:
    return await ConversationDAO.update_title(db, conversation_id, user_id, title)


async def delete_conversation(db: AsyncSession, conversation_id: int, user_id: int) -> bool:
    return await ConversationDAO.delete(db, conversation_id, user_id)


def _apply_document_context(message: str, context_material_title: str | None) -> str:
    """Prepend document context so the AI can answer in context of the viewed material."""
    if not context_material_title or not context_material_title.strip():
        return message
    return (
        f'The user is currently viewing the document "{context_material_title.strip()}". '
        f"Answer their question in that context when relevant.\n\nQuestion: {message}"
    )


async def send_message(
    db: AsyncSession,
    conversation_id: int,
    user_id: int,
    message: str,
    context_material_title: str | None = None,
) -> tuple[ChatMessage, ChatMessage] | None:
    """Append user message, call AI (src/ graph), append assistant reply. Returns (user_msg, assistant_msg) or None if conversation not found."""
    conv = await ConversationDAO.get_by_id(db, conversation_id, user_id)
    if not conv:
        return None
    existing = await ChatMessageDAO.list_by_conversation(db, conversation_id)
    user_msg = await ChatMessageDAO.create(db, conversation_id, "user", message)
    history = [{"role": m.role, "content": m.content} for m in existing]
    history.append({"role": "user", "content": message})
    prompt_for_ai = _apply_document_context(message, context_material_title)
    assistant_content = await run_chat(prompt_for_ai, history, mind_mode=False)
    assistant_msg = await ChatMessageDAO.create(db, conversation_id, "assistant", assistant_content)
    if len(existing) == 0:
        title = (message.strip()[:200] + "…") if len(message.strip()) > 200 else message.strip()
        if not title:
            title = "New Chat"
        await ConversationDAO.update_title(db, conversation_id, user_id, title)
    await ConversationDAO.touch(db, conversation_id)
    return user_msg, assistant_msg


async def stateless_message(
    message: str,
    conversation_history: list[dict],
    mind_mode: bool = False,
    context_material_title: str | None = None,
) -> str:
    """Stateless chat (no persistence). Returns assistant answer text."""
    history = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in conversation_history]
    history.append({"role": "user", "content": message})
    prompt_for_ai = _apply_document_context(message, context_material_title)
    return await run_chat(prompt_for_ai, history, mind_mode=mind_mode)
