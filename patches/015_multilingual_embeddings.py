#!/usr/bin/env python3
"""
patches/015_multilingual_embeddings.py
Switches embedding model from nomic-embed-text to
zylonai/multilingual-e5-large:latest for much better Danish/multilingual support.

Test results vs nomic-embed-text:
  Same job reworded (DA):  0.9692  (was 0.7640) ✓
  Same job EN vs DA:       0.9592  (was 0.6887) ✓
  Different jobs, field:   0.8388  (was 0.5440) — below 0.92 threshold ✓
  Completely different:    0.8265  (was 0.6896) — below 0.92 threshold ✓

Threshold 0.92 cleanly separates duplicates from non-duplicates.

Changes:
  1. scripts/qdrant/qdrant_client.py — update default EMBED_MODEL and vector size
  2. .env.example — update EMBED_MODEL default
  3. Recreates Qdrant jobs collection (1024d vs nomic's 768d — incompatible)
  4. CLAUDE.md — update embedding model note

Run from workspace root:
    python3 patches/015_multilingual_embeddings.py
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


print("\n📋 Patch 015 — Switch to zylonai/multilingual-e5-large embeddings\n")

# ── 1. qdrant_client.py — update default model and vector size ────────────────
patch(
    "qdrant_client.py — update default EMBED_MODEL",
    "scripts/qdrant/qdrant_client.py",
    'EMBED_MODEL      = os.environ.get("EMBED_MODEL", "nomic-embed-text")',
    'EMBED_MODEL      = os.environ.get("EMBED_MODEL", "zylonai/multilingual-e5-large:latest")',
)

patch(
    "qdrant_client.py — update default vector size to 1024",
    "scripts/qdrant/qdrant_client.py",
    "def ensure_collection(vector_size: int = 768):",
    "def ensure_collection(vector_size: int = 1024):",
)

# ── 2. .env.example — update EMBED_MODEL default ─────────────────────────────
patch(
    ".env.example — update EMBED_MODEL default",
    ".env.example",
    "EMBED_MODEL=nomic-embed-text",
    "# zylonai/multilingual-e5-large:latest — best for Danish/multilingual job dedup\n"
    "# Requires OLLAMA_FLASH_ATTENTION=false on the Ollama server\n"
    "EMBED_MODEL=zylonai/multilingual-e5-large:latest",
)

# ── 3. Recreate Qdrant collection with correct 1024d vector size ───────────────
print("\n  Recreating Qdrant jobs collection (768d → 1024d)...")
import sys, os
sys.path.insert(0, str(WORKSPACE))
os.chdir(WORKSPACE)

try:
    from dotenv import load_dotenv
    load_dotenv(".env")

    # Override model for this session
    os.environ["EMBED_MODEL"] = "zylonai/multilingual-e5-large:latest"

    from scripts.qdrant.qdrant_client import (
        _qdrant_request, COLLECTION_NAME, is_available, get_embedding
    )

    if not is_available():
        print("  ⚠ Qdrant not reachable — skipping collection recreate")
        print("    Run manually after setting QDRANT_URL in .env:")
        print("    python3 -c \"from scripts.qdrant.qdrant_client import *; "
              "_qdrant_request('DELETE', f'/collections/{COLLECTION_NAME}'); "
              "ensure_collection(1024)\"")
        OK += 1
    else:
        # Delete existing collection
        try:
            _qdrant_request("DELETE", f"/collections/{COLLECTION_NAME}")
            print(f"  ✓ Deleted old '{COLLECTION_NAME}' collection")
        except Exception as e:
            print(f"  ~ Collection delete: {e} (may not have existed)")

        # Recreate with 1024d
        _qdrant_request("PUT", f"/collections/{COLLECTION_NAME}", {
            "vectors": {"size": 1024, "distance": "Cosine"}
        })
        print(f"  ✓ Created '{COLLECTION_NAME}' collection (1024d, Cosine)")

        # Quick smoke test
        vec = get_embedding("IT Administrator job Denmark")
        print(f"  ✓ Embedding dimensions: {len(vec)}")
        OK += 1

except Exception as e:
    print(f"  ✗ Collection recreate failed: {e}")
    FAIL += 1

# ── 4. CLAUDE.md — update embedding model note ───────────────────────────────
claude = WORKSPACE / "CLAUDE.md"
content = claude.read_text()
old = ("- **Qdrant semantic dedup** — `scripts/qdrant/qdrant_client.py`. "
       "Embeds job descriptions with `nomic-embed-text` via Ollama, stores in Qdrant. "
       "Checked at scrape time before saving — catches cross-board duplicates. "
       "Threshold 0.92 cosine similarity. Falls back gracefully if Qdrant unavailable.")
new = ("- **Qdrant semantic dedup** — `scripts/qdrant/qdrant_client.py`. "
       "Embeds with `zylonai/multilingual-e5-large:latest` (1024d, requires "
       "`OLLAMA_FLASH_ATTENTION=false` on Ollama server). "
       "Threshold 0.92 cosine similarity — cleanly separates DA/EN duplicates. "
       "Falls back gracefully if Qdrant unavailable.")
if old in content:
    claude.write_text(content.replace(old, new))
    print("  ✓ CLAUDE.md — update embedding model note")
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
        "scripts/qdrant/qdrant_client.py",
        ".env.example",
        "CLAUDE.md",
        "patches/015_multilingual_embeddings.py",
    ],
    "feat: switch to zylonai/multilingual-e5-large for multilingual job dedup"
)

print("\nNext steps:")
print("  1. Update .env: EMBED_MODEL=zylonai/multilingual-e5-large:latest")
print("  2. python3 scripts/scraping/run_scrape.py --dry-run")
print("     (verify [Qdrant] Semantic dedup active)")
print("  3. Run a full scrape to populate Qdrant with 1024d vectors:")
print("     python3 scripts/scraping/run_scrape.py")