"""
scripts/local_llm/score_jobs.py
Score unscored jobs using Qwen2.5:7b via Ollama.
After scoring, runs a dedup pass to detect cross-posted jobs.
"""
import sys
import json
import argparse
import re
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.db.client import fetchall, fetchone, execute
from scripts.local_llm.ollama_client import generate, is_available, OllamaError
from scripts.commute.ors_client import (
    get_best_commute, get_coordinates, is_available as ors_available, ORSError
)

SCORE_PROMPT_TEMPLATE = (
    Path(__file__).parent.parent.parent
    / "skills" / "job-filter" / "filter_prompt.txt"
).read_text()

DEDUP_PROMPT_TEMPLATE = (
    Path(__file__).parent.parent.parent
    / "skills" / "job-filter" / "dedup_prompt.txt"
).read_text()


def load_profile_summary() -> tuple[str, str]:
    row = fetchone("SELECT structured, preferences, skills FROM profile WHERE id = 1")
    if not row:
        return "No profile set up yet.", "None"

    p      = row["structured"]
    pref   = row["preferences"]
    skills = row["skills"] or {}

    skills_all = (
        skills.get("languages", []) +
        skills.get("frameworks", []) +
        skills.get("tools", [])
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


def score_jobs(limit: int = None, rescore: bool = False, job_id: str = None):
    if not is_available():
        print("ERROR: Processing LLM is not reachable.")
        sys.exit(1)

    profile_summary, hard_requirements = load_profile_summary()

    # Load commute preferences
    _prefs_row = fetchone("SELECT preferences FROM profile WHERE id = 1")
    _prefs     = _prefs_row["preferences"] if _prefs_row else {}
    _commute   = _prefs.get("commute", {})
    _home_addr = _commute.get("home_address")
    _home_coords = None
    _max_min   = _commute.get("max_minutes", 45)
    _modes     = _commute.get("modes", ["driving-car"])
    _ors_on    = ors_available() and bool(_home_addr)
    if _ors_on:
        try:
            stored = _commute.get("home_coords")
            if stored:
                _home_coords = tuple(stored)
            else:
                _home_coords = get_coordinates(_home_addr)
            if not _home_coords:
                print(f"  ⚠ Could not geocode home address: {_home_addr}")
                _ors_on = False
        except ORSError as e:
            print(f"  ⚠ ORS unavailable: {e}")
            _ors_on = False

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
            # Use .replace() not .format() — descriptions contain {} characters
            prompt = (SCORE_PROMPT_TEMPLATE
                .replace("{profile_summary}",   profile_summary)
                .replace("{hard_requirements}", hard_requirements)
                .replace("{title}",             job["title"] or "")
                .replace("{company}",           job["company"] or "")
                .replace("{location}",          job["location"] or "")
                .replace("{description}",       (job["description_raw"] or "")[:3000])
            )

            # json_mode=True forces Ollama to return valid JSON
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

            tags     = parsed.get("tags", [])
            reason   = parsed.get("reason", "")[:300]

            # Extract company/location if Qwen found them and DB columns are empty
            extracted_company  = parsed.get("company") or None
            extracted_location = parsed.get("location") or None
            extracted_remote   = parsed.get("remote")

            execute("""
                UPDATE jobs
                SET score        = %s,
                    tags         = %s,
                    score_reason = %s,
                    scored_at    = %s,
                    company      = COALESCE(NULLIF(company, ''), %s),
                    location     = COALESCE(NULLIF(location, ''), %s),
                    remote       = COALESCE(remote, %s)
                WHERE id = %s
            """, (score, tags, reason, datetime.now(timezone.utc),
                  extracted_company, extracted_location, extracted_remote,
                  job_id_str))

            # Commute calculation — skip for remote jobs or missing location
            commute_minutes = None
            commute_mode    = None
            job_location = extracted_location or job.get("location") or ""
            is_remote    = extracted_remote or job.get("remote") or False

            if _ors_on and job_location and not is_remote:
                try:
                    commute_minutes, commute_mode = get_best_commute(
                        _home_coords, job_location, _modes
                    )
                    if commute_minutes is not None:
                        # Penalise score if commute exceeds max
                        if commute_minutes > _max_min:
                            penalty = min(20, (commute_minutes - _max_min) // 5 * 5)
                            score   = max(0, score - penalty)
                        execute("""
                            UPDATE jobs
                            SET commute_minutes = %s, commute_mode = %s
                            WHERE id = %s
                        """, (commute_minutes, commute_mode, job_id_str))
                        mode_label = commute_mode.replace('driving-car','🚗').replace('cycling-electric','⚡🚲').replace('cycling-regular','🚲').replace('foot-walking','🚶')
                        print(f"     🗺 {commute_minutes} min {mode_label}")
                except ORSError as e:
                    print(f"     ⚠ Commute lookup failed: {e}")

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


def dedup_jobs(scored_ids: list[str]):
    """
    Qwen-based dedup: same-company title comparison.
    Cross-board dedup is handled by Qdrant at scrape time (see run_scrape.py).
    This pass catches remaining same-company duplicates Qdrant may miss.
    """  # noqa: D400
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
            prompt = (DEDUP_PROMPT_TEMPLATE
                .replace("{title_a}",    job["title"] or "")
                .replace("{company_a}",  job["company"] or "")
                .replace("{location_a}", job["location"] or "")
                .replace("{title_b}",    candidate["title"] or "")
                .replace("{company_b}",  job["company"])
                .replace("{location_b}", candidate["location"] or "")
            )

            try:
                response = generate(prompt, temperature=0.0, json_mode=True)
                parsed   = parse_json_response(response)

                if not parsed:
                    continue

                is_duplicate = str(parsed.get("duplicate", "")).upper() == "YES"

                if is_duplicate:
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
                    break

            except OllamaError as e:
                print(f"  ✗ Ollama error during dedup: {e}")
                break
            except Exception as e:
                print(f"  ✗ Dedup error: {e}")

    print(f"Dedup done. {dupes_found} duplicate(s) found.")


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
