#!/usr/bin/env python3
"""
patches/004_extract_company_location.py
Extracts company name and location from job descriptions during scoring.

Run from workspace root:
    python3 patches/004_extract_company_location.py
"""
import sys
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent
OK = 0
FAIL = 0

def patch_file(description, path, old, new):
    global OK, FAIL
    f = WORKSPACE / path
    content = f.read_text()
    if new in content:
        print(f"  ~ already applied: {description}")
        OK += 1
        return
    if old not in content:
        print(f"  ✗ anchor not found: {description}")
        FAIL += 1
        return
    f.write_text(content.replace(old, new, 1))
    print(f"  ✓ {description}")
    OK += 1

print("\n📋 Patch 004 — Extract company + location during scoring\n")

# ── 1. filter_prompt.txt ──────────────────────────────────────────────────────
patch_file(
    "filter_prompt.txt — add company/location fields",
    "skills/job-filter/filter_prompt.txt",
    'Required JSON structure:\n{\n  "score": <integer 0-100>,\n  "tags": ["tag1", "tag2"],\n  "reason": "One sentence explaining the score."\n}',
    'Required JSON structure:\n{\n  "score": <integer 0-100>,\n  "company": "Company name or null if not found",\n  "location": "City or region or null if not found",\n  "remote": true or false or null,\n  "tags": ["tag1", "tag2"],\n  "reason": "One sentence explaining the score."\n}',
)

# ── 2. score_jobs.py — edit line by line ─────────────────────────────────────
score_path = WORKSPACE / "scripts/local_llm/score_jobs.py"
lines = score_path.read_text().splitlines(keepends=True)

# Find the tags line
tags_line = None
for i, line in enumerate(lines):
    if 'tags   = parsed.get("tags"' in line or 'tags     = parsed.get("tags"' in line:
        tags_line = i
        break

if tags_line is None:
    print("  ✗ anchor not found: score_jobs.py — could not find tags line")
    FAIL += 1
else:
    # Check if already patched
    block = "".join(lines[tags_line:tags_line+15])
    if "extracted_company" in block:
        print("  ~ already applied: score_jobs.py — extracted fields")
        OK += 1
    else:
        # Find the execute() call that follows tags/reason
        exec_line = None
        for i in range(tags_line, min(tags_line + 10, len(lines))):
            if 'execute("""' in lines[i] or "execute(\"\"\"" in lines[i]:
                exec_line = i
                break

        # Find the end of that execute call (closing parenthesis)
        exec_end = None
        if exec_line:
            for i in range(exec_line, min(exec_line + 15, len(lines))):
                if lines[i].strip().endswith(', job_id_str))') or \
                   lines[i].strip().endswith(', job_id_str))'):
                    exec_end = i
                    break

        if exec_line is None or exec_end is None:
            print("  ✗ anchor not found: score_jobs.py — could not find execute block")
            FAIL += 1
        else:
            indent = "            "
            new_block = (
                f'{indent}tags     = parsed.get("tags", [])\n'
                f'{indent}reason   = parsed.get("reason", "")[:300]\n'
                f'\n'
                f'{indent}# Extract company/location if Qwen found them and DB is empty\n'
                f'{indent}extracted_company  = parsed.get("company") or None\n'
                f'{indent}extracted_location = parsed.get("location") or None\n'
                f'{indent}extracted_remote   = parsed.get("remote")\n'
                f'\n'
                f'{indent}execute("""\n'
                f'{indent}    UPDATE jobs\n'
                f'{indent}    SET score        = %s,\n'
                f'{indent}        tags         = %s,\n'
                f'{indent}        score_reason = %s,\n'
                f'{indent}        scored_at    = %s,\n'
                f"{indent}        company      = COALESCE(NULLIF(company, ''), %s),\n"
                f"{indent}        location     = COALESCE(NULLIF(location, ''), %s),\n"
                f'{indent}        remote       = COALESCE(remote, %s)\n'
                f'{indent}    WHERE id = %s\n'
                f'{indent}""", (score, tags, reason, datetime.now(timezone.utc),\n'
                f'{indent}        extracted_company, extracted_location, extracted_remote,\n'
                f'{indent}        job_id_str))\n'
            )
            lines[tags_line:exec_end + 1] = [new_block]
            score_path.write_text("".join(lines))
            print("  ✓ score_jobs.py — extracted company/location fields")
            OK += 1

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'─'*50}")
print(f"✓ {OK} applied   ✗ {FAIL} failed")
if FAIL:
    print("\nSome patches failed — check output above.")
    sys.exit(1)
else:
    print("\nAll done. Rescore existing jobs to backfill:")
    print("  python3 scripts/local_llm/score_jobs.py --rescore --skip-dedup")
    print("\nCommit with:")
    print("  git add skills/job-filter/filter_prompt.txt scripts/local_llm/score_jobs.py patches/004_extract_company_location.py")
    print('  git commit -m "feat: extract company and location from description during scoring"')