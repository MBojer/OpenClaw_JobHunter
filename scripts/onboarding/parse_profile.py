"""
scripts/onboarding/parse_profile.py
Parse raw LinkedIn/CV text into structured profile.json using Qwen2.5:7b.
Called by the onboarding skill — never by the free model directly.
"""
import sys
import json
import argparse
import tempfile
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.local_llm.ollama_client import generate, is_available, OllamaError
from scripts.db.client import execute, fetchone

PROMPT_TEMPLATE = (
    Path(__file__).parent.parent.parent
    / "skills" / "onboarding" / "parse_prompt.txt"
).read_text()

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


def parse_raw(raw_text: str) -> dict:
    """Send raw text to Qwen, return structured dict."""
    if not is_available():
        raise RuntimeError("Ollama is not reachable. Is it running?")

    prompt   = PROMPT_TEMPLATE + "\n" + raw_text
    response = generate(prompt, temperature=0.05, json_mode=True, num_predict=2048)

    # Strip markdown fences if present
    response = response.strip()
    if response.startswith("```"):
        lines    = response.split("\n")
        response = "\n".join(lines[1:-1])

    return json.loads(response)


def save_profile(profile: dict, preferences: dict):
    """Write profile.json and preferences.json, and upsert to DB."""
    CONFIG_DIR.mkdir(exist_ok=True)

    (CONFIG_DIR / "profile.json").write_text(
        json.dumps(profile, indent=2, ensure_ascii=False)
    )
    (CONFIG_DIR / "preferences.json").write_text(
        json.dumps(preferences, indent=2, ensure_ascii=False)
    )

    execute("""
        INSERT INTO profile (id, structured, preferences, onboarded_at, updated_at)
        VALUES (1, %s, %s, NOW(), NOW())
        ON CONFLICT (id) DO UPDATE SET
            structured   = EXCLUDED.structured,
            preferences  = EXCLUDED.preferences,
            onboarded_at = COALESCE(profile.onboarded_at, NOW()),
            updated_at   = NOW()
    """, (json.dumps(profile), json.dumps(preferences)))

    # Write dedicated skills column
    execute(
        "UPDATE profile SET skills = %s WHERE id = 1",
        (json.dumps(profile.get("skills", {})),)
    )

    # Replace experience rows (full replace on every save)
    execute("DELETE FROM profile_experience")
    for i, role in enumerate(profile.get("experience", [])):
        execute("""
            INSERT INTO profile_experience
                (title, company, from_date, to_date, description, sort_order)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            role.get("title", ""),
            role.get("company", ""),
            role.get("from"),
            role.get("to"),
            role.get("description"),
            i,
        ))

    print("Profile saved to config/profile.json and database.")


def save_raw_input(raw_text: str):
    """Store the raw input in DB only — never write to a readable file."""
    execute("""
        UPDATE profile SET raw_input = %s WHERE id = 1
    """, (raw_text,))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group  = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input",        type=str, help="Path to raw text file")
    group.add_argument("--profile-json", type=str, help="Pre-parsed JSON string (for --save mode)")
    parser.add_argument("--save",         action="store_true")
    parser.add_argument("--prefs-json",  type=str, help="Preferences JSON string (for --save mode)")
    args = parser.parse_args()

    if args.save and args.profile_json:
        profile     = json.loads(args.profile_json)
        preferences = json.loads(args.prefs_json) if args.prefs_json else {}
        save_profile(profile, preferences)
        sys.exit(0)

    # Parse mode
    raw_text = Path(args.input).read_text(encoding="utf-8")

    try:
        structured = parse_raw(raw_text)
        print(json.dumps(structured, indent=2, ensure_ascii=False))
    except json.JSONDecodeError as e:
        print(f"ERROR: Could not parse Qwen response as JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except OllamaError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
