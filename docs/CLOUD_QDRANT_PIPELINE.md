# Qdrant Cloud Pipeline Runbook

This document covers **only** the Qdrant Cloud pipeline —
`QDRANT_BACKEND=cloud`. For the local, self-hosted Docker pipeline, see
`docs/LOCAL_QDRANT_PIPELINE.md`. **Local and Cloud are independent
databases.** Switching `QDRANT_BACKEND` does not synchronize or migrate
data between them — the only way data moves from one to the other is the
explicit, manually-run `scripts/migrate_qdrant_local_to_cloud.py`.

The same OCR, QA, chunking, and embedding pipeline is reused unchanged
for both backends — only the final Qdrant upsert/validate/export step's
*destination* differs, resolved once in
`src/knowledge_base/qdrant_store.py::QdrantKBStore._ensure_client()`.

---

## 1. Qdrant Cloud Cluster Creation

Sign in at https://cloud.qdrant.io and create a cluster from its
dashboard (free tier available). This step is done in Qdrant's own web
console, outside this repository — not automated by anything here.

## 2. Provider and Region Configuration

Pick a cloud provider/region in the cluster-creation wizard — choose one
close to wherever this pipeline actually runs (lower embedding-upload
latency). This repository has no opinion on which provider/region; it's
a pure Qdrant Cloud console setting.

## 3. Obtaining the Cluster Endpoint

Qdrant Cloud shows the cluster's HTTPS endpoint on the cluster's detail
page, in the form:
```
https://<cluster-id>.<region>.<provider>.cloud.qdrant.io
```
This is `QDRANT_CLOUD_URL` below — **always `https://`**, never plain
`http://` (`QdrantKBStore._ensure_client()` enforces this and refuses to
connect otherwise).

## 4. Creating a Database API Key

In the cluster's "API Keys" panel, create a **database API key** scoped
to that cluster — **not** your Qdrant Cloud account's Management API key
(which manages clusters themselves, not collections/points, and should
never be used here or stored in this repo at all).

## 5. Securely Configuring Cloud Credentials in `.env.kb`

```powershell
copy .env.kb.example .env.kb
notepad .env.kb
```
Set:
```env
QDRANT_CLOUD_URL=https://<your-cluster-id>.<region>.<provider>.cloud.qdrant.io
QDRANT_CLOUD_API_KEY=<your database API key>
```
- `.env.kb` is gitignored — verify with `git check-ignore -v .env.kb`
  (should print the matching `.gitignore` line; if it prints nothing,
  **stop** — something is wrong with your `.gitignore` before you
  proceed).
- `.env.kb.example` (the committed template) only ever contains empty
  placeholders for these two variables — never put a real key there.
- Nothing in this codebase prints `QDRANT_CLOUD_API_KEY`'s value in any
  log, error message, or exception — `QdrantKBStore`'s connection log
  line prints only the URL; `KBConfig.to_dict()` (used by manifests)
  redacts both API-key fields to the literal string `"<redacted>"`.
- Rotate a compromised key immediately from the same "API Keys" panel
  (revoke the old one, create a new one, update `.env.kb`) — Qdrant Cloud
  keys aren't automatically rotatable from this repo; it's a console
  action.

## 6. Configuring `QDRANT_BACKEND=cloud`

```env
QDRANT_BACKEND=cloud
```
Everything downstream (`build_kb_qdrant.py`, `validate_kb_qdrant.py`,
`export_kb_qdrant.py`) now resolves to Cloud automatically — no
per-script flag needed; the backend is resolved once in `KBConfig`.

## 7. Activating the Correct Python Environment

Same as local — `..\.venv\Scripts\Activate.ps1` for everything except
ingestion (`.venv-ocr`, see `docs/COMPLETE_PIPELINE_SETUP.md` §5.3).
Backend choice doesn't change which venv anything uses.

## 8. Verifying the Cloud Connection

```powershell
python -c "from src.knowledge_base.config import load_config; from src.knowledge_base.qdrant_store import QdrantKBStore; print(QdrantKBStore(load_config()).verify_connection())"
```
Prints `True` on success. On failure, raises a `RuntimeError` naming only
the backend and the exception *type* — never the raw exception text or
the API key, even on an auth failure.

**Verified this session** against a real cluster the user provisioned:
connection succeeded (`verify_connection() -> True`), and
`collection_exists()` correctly reported the collection doesn't exist yet
(nothing has been migrated or upserted there).

## 9. Creating or Validating the Cloud Collection

Created automatically, the same way as local, the first time anything
upserts (`QdrantKBStore.ensure_collection()` — 1024-dim, COSINE
distance, matching `embedding_dim`/the existing payload schema exactly;
no new/incompatible schema is ever introduced). If a collection with
this name **already exists** on your cluster, its vector config is
inspected, never blindly modified or recreated — an incompatible existing
collection raises a clear error instead of silently deleting it.

## 10-13. Running OCR/Video Ingestion, Auto-QA, Normalization, Chunking

Identical to `docs/LOCAL_QDRANT_PIPELINE.md` §6-8 — these stages never
touch Qdrant at all, so the active backend is irrelevant to them.

## 14. BGE-M3 Embedding Generation

Identical to local (`scripts/embed_chunks_kb.py`) — embedding also never
touches Qdrant.

## 15. Upserting Into Cloud Qdrant

```powershell
# Notes/PDFs only — OCR via .venv-ocr, never touches videos:
..\.venv-ocr\Scripts\python.exe -m scripts.ingest_notes --output "E:\SaarthiData\source_content\ocr"

# QA -> normalize (approved-only by default) -> chunk -> embed (GPU) -> Cloud upsert:
python -m scripts.build_kb_qdrant
```
With `QDRANT_BACKEND=cloud` set, this upserts into your Cloud cluster
instead of local Docker — same idempotent, content-hash-gated logic,
same deterministic point IDs. Don't pass `--run-ingestion` if you only
want notes/PDFs processed — that flag also runs `ingest_videos.py`.
Don't pass `--allow-pending` for a production upload — only `approved`
content should reach Cloud; `pending`/`rejected`/`reprocess_requested`
stay excluded (see §16 of `docs/KB_PIPELINE_SETUP.md` and the manual QA
dashboard for reviewing `pending` content later).

**Verified on this project's real cluster**: 126 input files → 206
approved chunks → 206 points in Cloud, 1024-dim, Cosine, 0 duplicate
IDs, 0 validation warnings/errors.

## 16. Validating the Cloud Collection

```powershell
python -m scripts.validate_kb_qdrant
```
Same report shape as local; `qdrant_point_count` now reflects the Cloud
collection.

## 16b. Viewing, Querying, and Sharing Access to the Cloud KB

**Browsing visually**: [cloud.qdrant.io](https://cloud.qdrant.io) → open
your cluster → its dashboard lets you see collection stats and browse
points without writing any code.

**From the terminal**, using what's already in this repo (all verified
live against this project's real cluster):
```powershell
# Peek at a few real points with their payload
python -c "from src.knowledge_base.config import load_config; from src.knowledge_base.qdrant_store import QdrantKBStore; c=load_config(); client=QdrantKBStore(c)._ensure_client(); pts,_=client.scroll(c.qdrant_collection, limit=3, with_payload=True); [print(p.payload.get('source_file'), p.payload.get('page'), p.payload.get('text')[:80]) for p in pts]"

# A real semantic query against it
python -c "from src.knowledge_base.config import load_config; from src.knowledge_base.embedder import BGEEmbedder; from src.knowledge_base.qdrant_store import QdrantKBStore; c=load_config(); e=BGEEmbedder(c); v=e.embed_texts(['your query here'])[0]; client=QdrantKBStore(c)._ensure_client(); [print(h.score, h.payload.get('source_file'), h.payload.get('page')) for h in client.query_points(c.qdrant_collection, query=v, limit=3).points]"
```

**Giving others access** — three values, set in *their own* local
`.env.kb` (never commit it, never share it over chat/email in plaintext
if you can avoid it — use your team's usual secrets channel):
```env
QDRANT_BACKEND=cloud
QDRANT_CLOUD_URL=<this cluster's endpoint — see §3>
QDRANT_CLOUD_API_KEY=<their OWN key — see below>
```

**Don't hand out the same API key to everyone.** In the Cloud console's
API Keys panel for this cluster, create a **separate key per person or
service** — you can then revoke one person's access later without
rotating the key for everyone else. If your plan supports scoped keys,
give read-only/query-only keys to anyone who only needs retrieval (e.g.
an AI app backend integrating this KB), and reserve a write-capable key
for whoever runs the ingestion pipeline.

Once someone has those three values, they can either run this repo's own
scripts, or connect directly from their own application code:
```python
from qdrant_client import QdrantClient
client = QdrantClient(url="https://...", api_key="...")
client.query_points("saarthi_knowledge_base_v1", query=<1024-dim vector>, limit=5)
```
They need to embed their query text with the same model (`BAAI/bge-m3`)
to get a comparable vector — `src/knowledge_base/embedder.py` is the
reference implementation if they're wiring retrieval into another app
rather than using this repo's own scripts.

## 17. Exporting and Backing Up Cloud Data

```powershell
python -m scripts.export_kb_qdrant --qdrant-snapshot
```
Triggers a snapshot via Qdrant's own Cloud-cluster snapshot API (same
code path as local — `QdrantKBStore`'s client doesn't know or care which
backend it's talking to). Download it the same way the script prints.

## 18. Switching Safely Between Cloud and Local

Just change `QDRANT_BACKEND` in `.env.kb` — nothing else. **This never
copies, syncs, or deletes data in either direction.** If you want the
same content in both, run the full pipeline once per backend (same
local chunks.jsonl/embeddings.jsonl, two separate upserts), or use
`scripts/migrate_qdrant_local_to_cloud.py` (§below) to copy
already-upserted points from local into Cloud directly, without
re-embedding.

## 19. Troubleshooting Common Cloud Connection Errors

| Symptom | Fix |
|---|---|
| `ValueError: QDRANT_BACKEND=cloud requires QDRANT_CLOUD_URL to be set` | Set it in `.env.kb` (step 5). |
| `ValueError: ... requires QDRANT_CLOUD_API_KEY to be set` | Same — a database API key, not left blank. |
| `ValueError: QDRANT_CLOUD_URL must use https://` | Cloud endpoints are always `https://`; check for a copy-paste error. |
| `RuntimeError: Could not connect to Qdrant (cloud backend): ...` | Usually an auth failure (wrong/revoked key — rotate per step 4) or the cluster is suspended (§20) or paused. The error deliberately omits the raw exception text and the key; check the Cloud console for the cluster's actual status. |
| Collection schema mismatch on an existing Cloud collection | The pipeline refuses to modify/recreate it automatically — resolve manually (delete via the Cloud console only if you're certain, or use a different `QDRANT_COLLECTION` name). |

## 20. Free-Tier Limitations and Cluster Suspension

Qdrant Cloud's free tier has a limited cluster size and may suspend an
idle/over-quota cluster — if `verify_connection()` suddenly starts
failing with no config change on your end, check the cluster's status in
the Cloud console first (not a code bug). This repository doesn't ever
retry or auto-handle a suspended cluster — a failure surfaces immediately
as a clear, explicit error, by design, rather than silently degrading.

---

## Local vs. Cloud: Comparison

| | Local (Docker) | Cloud |
|---|---|---|
| Setup | `docker compose -f docker-compose.kb.yml up -d` | Create cluster + API key in Qdrant Cloud console |
| Connection | `http://localhost:6333`, no auth required | `https://...cloud.qdrant.io`, database API key required |
| Ingestion/QA/chunk/embed | Identical — backend-agnostic | Identical — backend-agnostic |
| Upsert/validate/export | Same code, `QDRANT_BACKEND=local` | Same code, `QDRANT_BACKEND=cloud` |
| Backup | Server-side snapshot, downloaded via `curl` to local disk | Server-side snapshot via the same API; Cloud also offers its own console-level cluster backups (outside this repo's scope) |
| Team access | Whoever can reach your Docker host/network | Anyone with the cluster endpoint + a database API key — manage access via Cloud's own key scoping, not this repo |
| Cost | Free (your own hardware) | Free tier available; paid tiers for larger/persistent clusters |
| Data location | Your machine's disk (`SAARTHI_KB_DATA_ROOT\qdrant\storage`) | Qdrant's cloud infrastructure |
