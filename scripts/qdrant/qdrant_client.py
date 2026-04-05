"""
scripts/qdrant/qdrant_client.py
Qdrant vector store client for semantic job deduplication.

Uses nomic-embed-text via Ollama to embed job descriptions,
then finds near-duplicates by cosine similarity.

This replaces the Qwen-based dedup (which only matches same-company)
with cross-board semantic dedup (catches same job on jobindex + ofir + linkedin).

Similarity threshold: 0.92 — tune up to reduce false positives,
down to catch more duplicates.
"""
import os
import json
import re
import urllib.request
import urllib.error
from html.parser import HTMLParser
from dotenv import load_dotenv

load_dotenv()

QDRANT_URL        = os.environ.get("QDRANT_URL", "").rstrip("/")
QDRANT_API_KEY    = os.environ.get("QDRANT_API_KEY", "")   # optional for local
PROC_LLM_BASE_URL = os.environ.get("PROC_LLM_BASE_URL", "http://localhost:11434")
PROC_LLM_API_KEY  = os.environ.get("PROC_LLM_API_KEY", "")
EMBED_MODEL       = os.environ.get("EMBED_MODEL", "zylonai/multilingual-e5-large:latest")
_agent_id         = os.environ.get("OPENCLAW_AGENT_ID", "default")
COLLECTION_NAME   = f"jobs_{_agent_id}"
SIMILARITY_THRESHOLD = 0.92


class QdrantError(Exception):
    pass


class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts = []

    def handle_data(self, data):
        self._parts.append(data)


def _strip_html(text: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    s = _HTMLStripper()
    s.feed(text)
    return re.sub(r'\s+', ' ', ' '.join(s._parts)).strip()


def _qdrant_request(method: str, path: str, body: dict = None) -> dict:
    """Make a request to Qdrant REST API."""
    if not QDRANT_URL:
        raise QdrantError("QDRANT_URL not set in .env")

    url = f"{QDRANT_URL}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if QDRANT_API_KEY:
        headers["api-key"] = QDRANT_API_KEY

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise QdrantError(f"Qdrant {method} {path} failed ({e.code}): {body}") from e
    except urllib.error.URLError as e:
        raise QdrantError(f"Cannot reach Qdrant at {QDRANT_URL}: {e}") from e


def get_embedding(text: str) -> list[float]:
    """Get embedding vector via processing LLM endpoint."""
    url = f"{PROC_LLM_BASE_URL}/api/embeddings"
    payload = json.dumps({"model": EMBED_MODEL, "prompt": _strip_html(text)[:2000]}).encode()
    headers = {"Content-Type": "application/json"}
    if PROC_LLM_API_KEY:
        headers["Authorization"] = f"Bearer {PROC_LLM_API_KEY}"
    req = urllib.request.Request(
        url, data=payload,
        headers=headers,
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data["embedding"]
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise QdrantError(f"Embedding failed: HTTP {e.code}: {body}") from e
    except Exception as e:
        raise QdrantError(f"Embedding failed: {e}") from e


def ensure_collection(vector_size: int = 1024):
    """Create jobs collection if it doesn't exist."""
    try:
        _qdrant_request("GET", f"/collections/{COLLECTION_NAME}")
        return  # Already exists
    except QdrantError:
        pass

    _qdrant_request("PUT", f"/collections/{COLLECTION_NAME}", {
        "vectors": {
            "size": vector_size,
            "distance": "Cosine"
        }
    })


def upsert_job(job_id: str, text: str) -> list[float]:
    """
    Embed job text and store in Qdrant.
    Returns the embedding vector.
    """
    vector = get_embedding(text)
    ensure_collection(len(vector))

    _qdrant_request("PUT", f"/collections/{COLLECTION_NAME}/points", {
        "points": [{
            "id": job_id_to_uint(job_id),
            "vector": vector,
            "payload": {"job_uuid": job_id}
        }]
    })
    return vector


def find_similar(text: str, limit: int = 3) -> list[dict]:
    """
    Find similar jobs by embedding the given text and searching Qdrant.
    Returns list of {job_uuid, score} dicts above SIMILARITY_THRESHOLD.
    """
    vector = get_embedding(text)
    ensure_collection(len(vector))

    result = _qdrant_request("POST", f"/collections/{COLLECTION_NAME}/points/search", {
        "vector": vector,
        "limit": limit,
        "with_payload": True,
        "score_threshold": SIMILARITY_THRESHOLD
    })

    hits = result.get("result", [])
    return [
        {"job_uuid": h["payload"]["job_uuid"], "score": h["score"]}
        for h in hits
    ]


def job_id_to_uint(job_id: str) -> int:
    """
    Convert UUID string to uint64 for Qdrant point ID.
    Takes first 16 hex chars of UUID (without dashes) as int.
    """
    hex_str = job_id.replace("-", "")[:16]
    return int(hex_str, 16)


def is_available() -> bool:
    """Check if Qdrant is reachable."""
    if not QDRANT_URL:
        return False
    try:
        _qdrant_request("GET", "/")
        return True
    except Exception:
        return False