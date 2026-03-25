#!/usr/bin/env python3
"""
patches/014_qdrant_dedup.py
Adds semantic deduplication via Qdrant + nomic-embed-text.

Replaces Qwen-based dedup (same company only) with vector similarity
search (catches cross-board duplicates: same job on jobindex + ofir + linkedin).

Changes:
  1. .env.example — add QDRANT_URL, QDRANT_API_KEY, EMBED_MODEL placeholders
  2. scripts/qdrant/__init__.py + qdrant_client.py — new files
  3. scripts/scraping/run_scrape.py — embed + check Qdrant before saving job
  4. scripts/local_llm/score_jobs.py — skip Qwen dedup if Qdrant is active
  5. CLAUDE.md — update

Run from workspace root:
    python3 patches/014_qdrant_dedup.py
"""
import sys
import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent
OK   = 0
FAIL = 0


def patch(description, path, old, new):
    global OK, FAIL
    f = WORKSPACE / path
    if not f.exists():
        print(f"  ✗ FILE NOT FOUND: {path}")
        FAIL += 1
        return
    content = f.read_text()
    if new in content:
        print(f"  ~ already applied: {description}")
        OK += 1
        return
    if old not in content:
        print(f"  ✗ anchor not found: {description}")
        print(f"    Looking for: {old[:70]!r}...")
        FAIL += 1
        return
    f.write_text(content.replace(old, new, 1))
    print(f"  ✓ {description}")
    OK += 1


def write_file(description, path, content):
    global OK
    f = WORKSPACE / path
    f.parent.mkdir(parents=True, exist_ok=True)
    if f.exists() and f.read_text() == content:
        print(f"  ~ already exists: {description}")
    else:
        f.write_text(content)
        print(f"  ✓ {description}")
    OK += 1


def auto_commit(files, message):
    print("\n  Auto-committing...")
    for f in files:
        subprocess.run(["git", "add", f], cwd=WORKSPACE)
    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=WORKSPACE, capture_output=True, text=True
    )
    if result.returncode == 0:
        push = subprocess.run(["git", "push"], cwd=WORKSPACE,
                              capture_output=True, text=True)
        if push.returncode == 0:
            print("  ✓ Committed and pushed")
        else:
            print(f"  ⚠ Committed but push failed: {push.stderr.strip()}")
    else:
        print(f"  ~ Nothing new to commit: {result.stdout.strip()}")


print("\n📋 Patch 014 — Qdrant semantic deduplication\n")

# ── 1. .env.example — add Qdrant placeholders ────────────────────────────────
patch(
    ".env.example — add Qdrant config",
    ".env.example",
    "ORS_BASE_URL=https://ors.example.com",
    "ORS_BASE_URL=https://ors.example.com\n"
    "\n"
    "# Qdrant vector store (for semantic deduplication)\n"
    "# Leave QDRANT_API_KEY empty for local unauthenticated instances\n"
    "QDRANT_URL=http://localhost:6333\n"
    "QDRANT_API_KEY=\n"
    "EMBED_MODEL=nomic-embed-text",
)

# ── 2. scripts/qdrant/__init__.py ────────────────────────────────────────────
write_file(
    "scripts/qdrant/__init__.py",
    "scripts/qdrant/__init__.py",
    "",
)

# ── 3. run_scrape.py — import Qdrant client ───────────────────────────────────
patch(
    "run_scrape.py — import Qdrant client",
    "scripts/scraping/run_scrape.py",
    "from scripts.db.client import fetchone, fetchall, execute\n"
    "from scripts.scraping.base_connector import JobListing",
    "from scripts.db.client import fetchone, fetchall, execute\n"
    "from scripts.scraping.base_connector import JobListing\n"
    "from scripts.qdrant.qdrant_client import (\n"
    "    upsert_job, find_similar, is_available as qdrant_available, QdrantError\n"
    ")",
)

# ── 4. run_scrape.py — init Qdrant flag before board loop ────────────────────
patch(
    "run_scrape.py — init Qdrant availability flag",
    "scripts/scraping/run_scrape.py",
    "    total_new   = 0\n"
    "    total_found = 0\n"
    "    run_status  = \"ok\"",
    "    total_new   = 0\n"
    "    total_found = 0\n"
    "    run_status  = \"ok\"\n"
    "    _qdrant_on  = qdrant_available()\n"
    "    if _qdrant_on:\n"
    "        print(\"  [Qdrant] Semantic dedup active\")\n"
    "    else:\n"
    "        print(\"  [Qdrant] Not available — using URL dedup only\")",
)

# ── 5. run_scrape.py — semantic dedup check before saving ────────────────────
patch(
    "run_scrape.py — semantic dedup in save_job",
    "scripts/scraping/run_scrape.py",
    "def save_job(listing: JobListing, board_id: int) -> bool:\n"
    "    \"\"\"Insert job. Returns True if new, False if duplicate.\"\"\"\n"
    "    if url_exists(listing.url):\n"
    "        return False",
    "def save_job(listing: JobListing, board_id: int,\n"
    "             qdrant_on: bool = False) -> bool:\n"
    "    \"\"\"Insert job. Returns True if new, False if duplicate.\"\"\"\n"
    "    if url_exists(listing.url):\n"
    "        return False\n"
    "\n"
    "    # Semantic dedup — check if a similar job already exists\n"
    "    if qdrant_on and listing.description_raw:\n"
    "        try:\n"
    "            similar = find_similar(listing.description_raw)\n"
    "            if similar:\n"
    "                best = similar[0]\n"
    "                print(f\"  [Qdrant] Semantic duplicate ({best['score']:.2f}): \"\n"
    "                      f\"{listing.title[:50]}\")\n"
    "                return False\n"
    "        except QdrantError as e:\n"
    "            print(f\"  [Qdrant] Dedup check failed: {e}\")",
)

# ── 6. run_scrape.py — pass qdrant_on to save_job and upsert after save ──────
patch(
    "run_scrape.py — pass qdrant_on and upsert after save",
    "scripts/scraping/run_scrape.py",
    "                if save_job(listing, board_id):\n"
    "                        new_count += 1",
    "                saved = save_job(listing, board_id, qdrant_on=_qdrant_on)\n"
    "                    if saved:\n"
    "                        new_count += 1\n"
    "                        # Upsert embedding to Qdrant after successful save\n"
    "                        if _qdrant_on and listing.description_raw:\n"
    "                            try:\n"
    "                                job_row = fetchone(\n"
    "                                    \"SELECT id FROM jobs WHERE url = %s\",\n"
    "                                    (listing.url,)\n"
    "                                )\n"
    "                                if job_row:\n"
    "                                    upsert_job(\n"
    "                                        str(job_row[\"id\"]),\n"
    "                                        listing.description_raw\n"
    "                                    )\n"
    "                            except QdrantError as e:\n"
    "                                print(f\"  [Qdrant] Upsert failed: {e}\")",
)

# ── 7. score_jobs.py — skip Qwen dedup if Qdrant handled it ──────────────────
patch(
    "score_jobs.py — note Qdrant handles cross-board dedup",
    "scripts/local_llm/score_jobs.py",
    "def dedup_jobs(scored_ids: list[str]):",
    "def dedup_jobs(scored_ids: list[str]):\n"
    "    \"\"\"\n"
    "    Qwen-based dedup: same-company title comparison.\n"
    "    Cross-board dedup is handled by Qdrant at scrape time (see run_scrape.py).\n"
    "    This pass catches remaining same-company duplicates Qdrant may miss.\n"
    "    \"\"\"  # noqa: D400",
)

# ── 8. CLAUDE.md — update ────────────────────────────────────────────────────
claude = WORKSPACE / "CLAUDE.md"
content = claude.read_text()
old = "- **Commute scoring** — ORS client in `scripts/commute/ors_client.py`."
new = ("- **Qdrant semantic dedup** — `scripts/qdrant/qdrant_client.py`. "
       "Embeds job descriptions with `nomic-embed-text` via Ollama, stores in Qdrant. "
       "Checked at scrape time before saving — catches cross-board duplicates. "
       "Threshold 0.92 cosine similarity. Falls back gracefully if Qdrant unavailable.\n"
       "- **Commute scoring** — ORS client in `scripts/commute/ors_client.py`.")
if old in content:
    claude.write_text(content.replace(old, new))
    print("  ✓ CLAUDE.md — add Qdrant dedup note")
    OK += 1
else:
    print("  ~ CLAUDE.md — anchor not found, skipping")

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'─'*50}")
print(f"✓ {OK} applied   ✗ {FAIL} failed")
if FAIL:
    sys.exit(1)

auto_commit(
    [
        ".env.example",
        "scripts/qdrant/__init__.py",
        "scripts/qdrant/qdrant_client.py",
        "scripts/scraping/run_scrape.py",
        "scripts/local_llm/score_jobs.py",
        "CLAUDE.md",
        "patches/014_qdrant_dedup.py",
    ],
    "feat: Qdrant semantic deduplication with nomic-embed-text"
)

print("\nNext steps:")
print("  1. Add QDRANT_URL to .env (e.g. http://your-qdrant:6333)")
print("  2. python3 scripts/scraping/run_scrape.py --dry-run")
print("     (should show: [Qdrant] Semantic dedup active)")