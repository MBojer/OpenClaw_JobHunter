"""
scripts/local_llm/score_jobs.py
Score unscored jobs using Qwen2.5:7b via Ollama.
After scoring, runs a dedup pass to detect cross-posted jobs.
"""
import sys
import json
import argparse
import re
import hashlib
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.db.client import fetchall, fetchone, execute
from scripts.local_llm.ollama_client import generate, is_available, OllamaError

SCORE_PROMPT_TEMPLATE = (
    Path(__file__).parent.parent.parent
    / "skills" / "job-filter" / "filter_prompt.txt"
).read_text()

DEDUP_PROMPT_TEMPLATE = (
    Path(__file__).parent.parent.parent
    / "skills" / "job-filter" / "dedup_prompt.txt"
).read_text()


def load_profile_summary() -> tuple[str, str]:
    row = fetchone("SELECT structured, preferences FROM profile WHERE id = 1")
    if not row:
        return "No profile set up yet.", "None"

    p    = row["structured"]
    pref = row["preferences"]

    skills_all = (
        p.get("skills", {}).get("languages", []) +
        p.get("skills", {}).get("frameworks", []) +
        p.get("skills", {}).get("tools", [])
    )
    summary = (
        f"Title: {p.get('current_title', 'Unknown')}\n"
        f"Location: {p.get('location', {}).get('city', '?')}, "
        f"{p.get('location', {}).get('country', '?')}\n"
        f"Key skills: {', '.join(skills_all[:12])}\n"
        f"Experience: {len(p.get('experience', []))} roles"
    )

    excluded = pref.get("keywords_excluded", [])
    min_sal  = pref.get("salary", {}).get("min_dkk_monthly")
    hard     = []
    if excluded:
        hard.append(f"Must NOT contain: {', '.join(excluded)}")
    if min_sal:
        hard.append(f"Salary >= {min_sal} DKK/month if specified")

    return summary, "\n".join(hard) if hard else "None"


def parse_json_response(text: str) -> dict | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


# ── Scoring ───────────────────────────────────────────────────────────────────

def score_jobs(limit: int = None, rescore: bool = False, job_id: str = None):
    if not is_available():
        print("ERROR: Ollama is not reachable.")
        sys.exit(1)

    profile_summary, hard_requirements = load_profile_summary()

    where = "WHERE score IS NULL" if not rescore else "WHERE TRUE"
    if job_id:
        where = f"WHERE id = '{job_id}'"
    limit_clause = f"LIMIT {limit}" if limit else ""

    jobs = fetchall(f"""
        SELECT id, title, company, location, description_raw
        FROM jobs
        {where}
        ORDER BY scraped_at DESC
        {limit_clause}
    """)

    if not jobs:
        print("No jobs to score.")
        return []

    print(f"Scoring {len(jobs)} job(s)...")
    scored_ids = []
    errors     = 0

    for job in jobs:
        job_id_str = str(job["id"])
        try:
            prompt = (SCORE_PROMPT_TEMPLATE
                .replace("{profile_summary}",   profile_summary)
                .replace("{hard_requirements}", hard_requirements)
                .replace("{title}",             job["title"] or "")
                .replace("{company}",           job["company"] or "")
                .replace("{location}",          job["location"] or "")
                .replace("{description}",       (job["description_raw"] or "")[:3000])
            )
            response = generate(prompt, json_mode=True)
            parsed   = parse_json_response(response)

            if not parsed or "score" not in parsed:
                print(f"  ✗ {job['title']} — could not parse response")
                errors += 1
                continue

            try:
                score = max(0, min(100, int(float(str(parsed["score"]).strip()))))
            except (ValueError, TypeError):
                print(f"  ✗ {job['title']} — invalid score value: {parsed['score']!r}")
                errors += 1
                continue
            tags   = parsed.get("tags", [])
            reason = parsed.get("reason", "")[:300]

            execute("""
                UPDATE jobs
                SET score = %s, tags = %s, score_reason = %s, scored_at = %s
                WHERE id = %s
            """, (score, tags, reason, datetime.now(timezone.utc), job_id_str))

            print(f"  ✓ {job['title']} @ {job['company']} — {score}/100")
            scored_ids.append(job_id_str)

        except OllamaError as e:
            print(f"  ✗ Ollama error: {e}")
            errors += 1
            break
        except Exception as e:
            print(f"  ✗ Error scoring {job_id_str}: {e}")
            errors += 1

    execute("""
        INSERT INTO run_log (run_type, status, jobs_found, finished_at)
        VALUES ('score', %s, %s, NOW())
    """, ("ok" if errors == 0 else "partial", len(scored_ids)))

    print(f"\nScoring done. {len(scored_ids)} scored, {errors} errors.")
    return scored_ids


# ── Deduplication ─────────────────────────────────────────────────────────────

def dedup_jobs(scored_ids: list[str]):
    """
    Second pass after scoring.
    For each scored job, check if a similar job from the same company
    already exists in the DB (last 30 days). Uses Qwen to compare.
    Only fires when there are 2+ jobs from the same company.
    """
    if not scored_ids:
        return

    print(f"\nRunning dedup pass on {len(scored_ids)} newly scored job(s)...")
    dupes_found = 0

    for job_id_str in scored_ids:
        job = fetchone("""
            SELECT id, title, company, location, description_raw
            FROM jobs WHERE id = %s
        """, (job_id_str,))
        if not job or not job["company"]:
            continue

        # Find other non-duplicate jobs from same company in last 30 days
        candidates = fetchall("""
            SELECT id, title, location
            FROM jobs
            WHERE company ILIKE %s
              AND id != %s
              AND status != 'duplicate'
              AND scraped_at > NOW() - INTERVAL '30 days'
            ORDER BY scraped_at DESC
            LIMIT 5
        """, (job["company"], job_id_str))

        if not candidates:
            continue

        for candidate in candidates:
            prompt = DEDUP_PROMPT_TEMPLATE.format(
                title_a    = job["title"] or "",
                company_a  = job["company"] or "",
                location_a = job["location"] or "",
                title_b    = candidate["title"] or "",
                company_b  = job["company"],
                location_b = candidate["location"] or "",
            )

            try:
                response = generate(prompt, temperature=0.0)
                parsed   = parse_json_response(response)

                if not parsed:
                    continue

                is_duplicate = str(parsed.get("duplicate", "")).upper() == "YES"

                if is_duplicate:
                    # Mark the newer job (current) as duplicate of the older one (candidate)
                    execute("""
                        UPDATE jobs
                        SET status       = 'duplicate',
                            duplicate_of = %s,
                            updated_at   = NOW()
                        WHERE id = %s
                    """, (str(candidate["id"]), job_id_str))

                    print(f"  ~ Duplicate: '{job['title']}' → '{candidate['title']}' "
                          f"[{parsed.get('reason', '')}]")
                    dupes_found += 1
                    break  # No need to check other candidates once marked

            except OllamaError as e:
                print(f"  ✗ Ollama error during dedup: {e}")
                break
            except Exception as e:
                print(f"  ✗ Dedup error: {e}")

    print(f"Dedup done. {dupes_found} duplicate(s) found.")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit",      type=int)
    parser.add_argument("--rescore",    action="store_true")
    parser.add_argument("--job-id",     type=str)
    parser.add_argument("--skip-dedup", action="store_true")
    args = parser.parse_args()

    scored = score_jobs(limit=args.limit, rescore=args.rescore, job_id=args.job_id)

    if not args.skip_dedup:
        dedup_jobs(scored)