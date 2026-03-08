from __future__ import annotations

import os
import json
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# --- Paths / config (conventional & robust) ---
BASE_DIR = Path(__file__).resolve().parent

# Load .env that sits next to the script (works in cron, systemd, shell, IDE)
load_dotenv(BASE_DIR / ".env")

# Tokens
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
RESUME_ID = os.getenv("RESUME_ID")

if not ACCESS_TOKEN or not RESUME_ID:
    raise SystemExit("❌ Missing ACCESS_TOKEN or RESUME_ID in .env")

# Side-effect files live next to the script
SENDED_FILE = BASE_DIR / "sended"
ACTION_REQUIRED_FILE = BASE_DIR / "action_required"
EXCLUDED_EMPLOYERS_FILE = BASE_DIR / "excluded_employers"
ALREADY_APPLIED_FILE = BASE_DIR / "already_applied"
LETTER_FILE = BASE_DIR / "letter.txt"
CFG_FILE = BASE_DIR / "cfg.json"

# Load config
with CFG_FILE.open("r", encoding="utf-8") as cfg_file:
    cfg = json.load(cfg_file)

KEYWORDS = cfg["keywords"]
EXCLUDED_CITIES = set(cfg["excluded_cities"])
EXCLUDED_WORDS = set(w.lower() for w in cfg["excluded_words"])
AREA = cfg["area"]
PER_PAGE = cfg["per_page"]

# HTTP defaults
HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json",
}
TIMEOUT = 15  # seconds


# --- Utils ---
def read_ids(file_path: Path) -> set[str]:
    """Read IDs from file into a set. Tolerant to missing file."""
    if not file_path.exists():
        return set()
    ids: set[str] = set()
    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            if "id:" in line:
                try:
                    parts = line.split("id:")[1].strip().split("|")[0]
                    vacancy_id = parts.strip()
                    if vacancy_id:
                        ids.add(vacancy_id)
                except IndexError:
                    continue
    return ids


def read_letter() -> str | None:
    """Read cover letter; return None if absent/empty."""
    try:
        text = LETTER_FILE.read_text(encoding="utf-8").strip()
        return text or None
    except FileNotFoundError:
        print(f"⚠ Letter file '{LETTER_FILE.name}' not found. Will apply without letter.")
        return None
    except Exception as e:
        print(f"⚠ Error reading letter file: {e}")
        return None


def write_log(file_path: Path, vacancy_id: str, name: str, city: str, reason: str | None = None) -> None:
    date = datetime.now().strftime("%Y-%m-%d %H:%M")
    reason_text = f" | reason: {reason}" if reason else ""
    line = f"{date} | id: {vacancy_id} | {name} | {city}{reason_text}\n"
    with file_path.open("a", encoding="utf-8") as f:
        f.write(line)


def contains_excluded_word(text: str, excluded_words: set[str]) -> bool:
    tl = text.lower()
    return any(w in tl for w in excluded_words)


# --- API ---
def search_vacancies(page: int):
    url = "https://api.hh.ru/vacancies"
    params = {
        "text": " OR ".join(KEYWORDS),
        "per_page": PER_PAGE,
        "page": page,
        "area": AREA,
    }
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=TIMEOUT)
    except requests.RequestException as e:
        print(f"❌ Network error on search: {e}")
        return None

    if r.status_code == 200:
        return r.json()
    print(f"❌ Failed to search vacancies: {r.status_code} - {r.text}")
    return None


def apply_to_vacancy(vacancy_id: str, resume_id: str, name: str, city: str, letter: str | None = None) -> str:
    url = "https://api.hh.ru/negotiations"
    params = {"vacancy_id": vacancy_id, "resume_id": resume_id}
    if letter:
        params["message"] = letter

    try:
        r = requests.post(url, headers=HEADERS, params=params, timeout=TIMEOUT)
    except requests.RequestException as e:
        print(f"❌ Network error on apply {vacancy_id}: {e}")
        return "error"

    if r.status_code == 201:
        letter_status = "with letter" if letter else "without letter"
        print(f"✓ Successfully applied {vacancy_id} ({name} - {city}) [{letter_status}]")
        write_log(SENDED_FILE, vacancy_id, name, city)
        return "success"

    if r.status_code == 403:
        # Try to classify
        low = r.text.lower()
        if "already_applied" in low:
            print(f"⚠ Already applied {vacancy_id} ({name} - {city})")
            write_log(ALREADY_APPLIED_FILE, vacancy_id, name, city, reason="already_applied")
            return "already_applied"
        if "letter required" in low:
            print(f"📝 Letter required {vacancy_id} ({name} - {city})")
            write_log(ACTION_REQUIRED_FILE, vacancy_id, name, city, reason="letter_required")
            return "action_required"
        if "test_required" in low:
            print(f"📋 Test required {vacancy_id} ({name} - {city})")
            write_log(ACTION_REQUIRED_FILE, vacancy_id, name, city, reason="test_required")
            return "action_required"

        print(f"❌ Access denied {vacancy_id} ({name} - {city}): {r.text}")
        return "error"

    print(f"❌ Failed to apply {vacancy_id} ({name} - {city}): {r.status_code} - {r.text}")
    return "error"


# --- Main ---
def main() -> None:
    page = 0

    excluded_employers = read_ids(EXCLUDED_EMPLOYERS_FILE)

    cover_letter = read_letter()
    if cover_letter:
        print(f"📝 Cover letter loaded: {len(cover_letter)} chars")
    else:
        print("📝 No cover letter; sending without letter")

    successful = 0
    total = 0
    already_applied_count = 0
    action_required_count = 0
    excluded_by_employer_count = 0
    excluded_by_filter_count = 0

    print("🚀 Starting vacancy application process...")

    while True:
        print(f"📖 Processing page {page}...")
        data = search_vacancies(page)
        if not data or "items" not in data:
            break

        vacancies = data["items"]
        if not vacancies:
            break

        if page == 0:
            print(f"📈 Total found: {data.get('found', 'unknown')}")
            print(f"📈 Total pages: {data.get('pages', 'unknown')}")

        print(f"📄 Page {page}: {len(vacancies)} vacancies")

        for v in vacancies:
            vacancy_id = v.get("id")
            if not vacancy_id:
                print(f"⚠ Skipping vacancy with no ID: {v}")
                continue

            employer_id = (v.get("employer") or {}).get("id")
            city = (v.get("area") or {}).get("name", "")
            name = v.get("name", "")
            total += 1

            if employer_id in excluded_employers:
                print(f"🚫 Excluded employer: {employer_id}")
                excluded_by_employer_count += 1
                continue

            name_lower = name.lower()
            if city not in EXCLUDED_CITIES and any(kw.lower() in name_lower for kw in KEYWORDS):
                if not contains_excluded_word(name_lower, EXCLUDED_WORDS):
                    print(f"🎯 Applying: {name} - {city}")
                    result = apply_to_vacancy(vacancy_id, RESUME_ID, name, city, cover_letter)
                    if result == "success":
                        successful += 1
                    elif result == "already_applied":
                        already_applied_count += 1
                    elif result == "action_required":
                        action_required_count += 1
                    time.sleep(1)  # rate limiting
                else:
                    print(f"🚫 Excluded by word filter: {name}")
                    excluded_by_filter_count += 1
            else:
                print(f"⏭ Excluded by city/keyword: {name} - {city}")
                excluded_by_filter_count += 1

        if data.get("pages", 0) - 1 == page:
            break
        page += 1

    print("\n📊 Summary:")
    print(f"Total processed: {total}")
    print(f"✅ Successful applications: {successful}")
    print(f"⚠ Already applied: {already_applied_count}")
    print(f"📝 Action required (letter/test): {action_required_count}")
    print(f"🚫 Excluded by employer: {excluded_by_employer_count}")
    print(f"⏭ Excluded by filters: {excluded_by_filter_count}")
    print("✅ Process completed!")


if __name__ == "__main__":
    main()
