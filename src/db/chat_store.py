import os
from supabase import create_client, Client
from typing import List, Dict

def get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    # Use service_role key for full DB access (bypasses RLS).
    # Falls back to anon key if service key not set.
    key = (
        os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
        or os.environ["SUPABASE_KEY"]
    )
    return create_client(url, key)


# ─── Threads ───────────────────────────────────────────────

def create_thread(title: str) -> str:
    """Creates a new chat thread and returns its UUID."""
    client = get_client()
    res = client.table("threads").insert({"title": title}).execute()
    return res.data[0]["id"]


def list_threads() -> List[Dict]:
    """Returns all threads sorted by newest first, including linked dataset name."""
    client = get_client()
    res = (
        client.table("threads")
        .select("id, title, created_at, dataset_name")
        .order("created_at", desc=True)
        .execute()
    )
    return res.data


def delete_thread(thread_id: str) -> None:
    """Deletes a thread and all its messages (cascade)."""
    client = get_client()
    client.table("threads").delete().eq("id", thread_id).execute()


# ─── Messages ──────────────────────────────────────────────

def save_message(thread_id: str, role: str, content: str) -> None:
    """Saves a single message to a thread."""
    client = get_client()
    client.table("messages").insert({
        "thread_id": thread_id,
        "role": role,
        "content": content,
    }).execute()


def load_thread_messages(thread_id: str) -> List[Dict]:
    """Loads all messages for a thread in chronological order."""
    client = get_client()
    res = (
        client.table("messages")
        .select("role, content")
        .eq("thread_id", thread_id)
        .order("created_at")
        .execute()
    )
    return res.data


def get_thread_title_from_query(query: str) -> str:
    """Generates a short thread title from the first user message."""
    return query[:50] + ("..." if len(query) > 50 else "")
