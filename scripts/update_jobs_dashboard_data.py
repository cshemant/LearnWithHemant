#!/usr/bin/env python3
"""
Nightly CSE/IT Government Jobs Dashboard updater.

This script runs the existing govt_job_finder.py scanner, converts its Excel output
into jobs/jobs-data.json, and keeps the current jobs dashboard layout unchanged.

Designed for GitHub Actions / scheduled automation. If the scan fails or returns
no usable jobs, the previous JSON file is preserved so the live page does not go blank.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import html as html_lib
import unicodedata
import sys
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from job_archive_utils import load_json_payload, reconcile_jobs

REPO_ROOT = Path(__file__).resolve().parents[1]
FINDER_PATH = Path(__file__).with_name("govt_job_finder.py")
MANUAL_JOBS_PATH = REPO_ROOT / "jobs" / "manual-jobs.json"
INVALID_JOB_URLS_PATH = REPO_ROOT / "jobs" / "invalid-job-urls.json"

# Auto-scraped government portals often contain FAQ, old notices, cut-off PDFs,
# results, answer keys and other non-vacancy pages. These should not replace the
# manually verified dashboard rows. Manual rows are always shown first.
AUTO_EXCLUDE_TITLE_KEYWORDS = [
    # clear non-vacancy pages only. Keep the list conservative so all-India
    # opportunities are not over-filtered.
    "faq", "frequently asked", "answer key", "admit card", "result",
    "merit list", "syllabus", "certificate, number is not",
    "old advertisement", "archive", "archives",
]



DISPLAY_FIELDS = {
    "job", "subtitle", "eligible_for", "fit_reason", "why", "profile_tags",
    "type", "status", "status_label", "last_date_display", "state", "agency",
    "official_label", "notification_label", "apply_label",
}

FALSE_POSITIVE_TITLE_PHRASES = [
    "awards and accolades", "awards & accolades", "awards accolades", "business model", "corporate profile",
    "skip to main content", "screen reader access", "universal content",
    "single sign on", "one digital identity", "question bank", "photo gallery",
    "video gallery", "font size", "cut-off date for having completed graduation",
]

ROLE_TITLE_SIGNALS = [
    "recruitment", "vacancy", "vacancies", "notification", "notice", "advertisement",
    "advt", "job", "opening", "assistant professor", "lecturer", "teacher", "faculty",
    "programmer", "developer", "scientist", "technical assistant", "computer operator",
    "data entry operator", "junior assistant", "office assistant", "clerk", "stenographer",
    "instructor", "engineer", "officer", "exam",
]


def english_display_text(value: Any) -> str:
    text = html_lib.unescape(str(value or ""))
    replacements = {
        "–": "-", "—": "-", "−": "-", "•": " ", "·": " ",
        "“": '"', "”": '"', "‘": "'", "’": "'", "…": "...",
        "×": " ", "→": " ", "←": " ", "©": " ", "®": " ",
        "\u200b": "", "\u200c": "", "\u200d": "", "\ufeff": "",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[A-Za-z0-9._%+\-]+\s*(?:\[at\]|\(at\)|@)\s*[A-Za-z0-9.\-]+\s*(?:\[dot\]|\(dot\)|\.)\s*[A-Za-z]{2,}", " ", text, flags=re.I)
    text = re.sub(r"[^A-Za-z0-9\s&/(),.:'+%#\-]", " ", text)
    text = re.sub(r"\(\s*cid\s*:\s*\d+\s*\)", " ", text, flags=re.I)
    text = re.sub(r"\bA\+\s*A-\s*(?:U)?\b", " ", text, flags=re.I)
    text = re.sub(r"(?:\s*[.:]\s*){3,}", " ", text)
    text = re.sub(r"\(\s*[.\-:]+\s*\)", " ", text)
    text = re.sub(r"\bskip\s+to\s+main\s+content\b", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" -|,.;:")
    return text


def sanitize_job_record(job: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(job)
    for field in DISPLAY_FIELDS:
        if field in out:
            out[field] = english_display_text(out.get(field))
    if out.get("job"):
        out["job"] = safe_job_title(out["job"])
    return out


def is_false_positive_title(title: str) -> bool:
    normalized = english_display_text(title).lower()
    normalized_words = normalized.replace("&", "and")
    if not normalized or len(normalized) < 8:
        return True
    if any(phrase.replace("&", "and") in normalized_words for phrase in FALSE_POSITIVE_TITLE_PHRASES):
        return True
    if normalized.startswith("bilingual advertisement") and not any(
        role in normalized for role in ROLE_TITLE_SIGNALS[8:]
    ):
        return True
    return False


def keep_historical_job(job: Dict[str, Any]) -> bool:
    source = clean(job.get("source"))
    if source in {"manual_curated", "manual_all_india_watchlist"}:
        return True
    return is_useful_auto_job(sanitize_job_record(job))


def register_invalid_generated_jobs(jobs: List[Dict[str, Any]]) -> None:
    """Send confirmed scanner false positives to the existing 410 registry.

    This applies only to auto-generated rows rejected by the new quality filters;
    legitimate expired jobs continue to move to the archive and are never added here.
    """
    new_paths = set()
    for job in jobs:
        source = clean(job.get("source"))
        slug = clean(job.get("slug"))
        if source == "auto_scanner" and slug and not keep_historical_job(job):
            new_paths.add(f"/jobs/{slug}/")
    if not new_paths:
        return
    try:
        payload = json.loads(INVALID_JOB_URLS_PATH.read_text(encoding="utf-8")) if INVALID_JOB_URLS_PATH.exists() else {}
    except Exception:
        payload = {}
    paths = {str(path).strip() for path in payload.get("paths", []) if str(path).strip()}
    before = len(paths)
    paths.update(new_paths)
    payload["description"] = "Confirmed invalid, duplicate or incorrectly generated job URL paths. Legitimate expired jobs remain archived."
    payload["paths"] = sorted(paths)
    INVALID_JOB_URLS_PATH.parent.mkdir(parents=True, exist_ok=True)
    INVALID_JOB_URLS_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if len(paths) > before:
        print(f"[INFO] Added {len(paths) - before} scanner false-positive URL(s) to the 410 registry.")

def load_finder_module():
    spec = importlib.util.spec_from_file_location("govt_job_finder", FINDER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load finder module from {FINDER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return " ".join(str(value).strip().split())


def parse_date(value: str) -> Optional[dt.date]:
    value = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", clean(value), flags=re.I).replace(",", "")
    if not value or value.lower().startswith("check"):
        return None
    formats = [
        "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
        "%d-%m-%y", "%d/%m/%y", "%d.%m.%y",
        "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
        "%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y",
        "%d %b %y", "%d %B %y", "%b %d %y", "%B %d %y",
    ]
    for fmt in formats:
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def display_date(raw: str, parsed: Optional[dt.date]) -> str:
    if parsed:
        return parsed.strftime("%d-%b-%Y")
    raw = clean(raw)
    return raw if raw else "Check official notice"


def safe_job_title(name: str) -> str:
    name = english_display_text(name)
    # A pipe commonly separates portal metadata; a hyphen is often part of the
    # real role name (for example "Assistant Professor / Lecturer - CSE").
    if " | " in name:
        first = english_display_text(name.split(" | ")[0])
        if len(first) >= 12:
            name = first
    name = re.sub(r"\ben\s*$", "", name, flags=re.I).strip()
    return name[:92].rstrip(" -|,.;") or "Government Job Notice"


def status_mapping(raw_status: str, score: int) -> Dict[str, str]:
    s = clean(raw_status).lower()
    if "eligible" in s:
        return {"status": "Good Match", "label": "Good Match", "class": "good"}
    if "doubtful" in s:
        return {"status": "Doubtful", "label": "Doubtful", "class": "caution"}
    if "avoid" in s or "closed" in s:
        return {"status": "Avoid", "label": "Avoid", "class": "avoid"}
    if score >= 55:
        return {"status": "Good Match", "label": "Good Match", "class": "good"}
    if score >= 20:
        return {"status": "Doubtful", "label": "Doubtful", "class": "caution"}
    return {"status": "Watch", "label": "Watch", "class": "watch"}


def role_type(value: str, text: str) -> str:
    combined = f"{value} {text}".lower()
    if "teach" in combined or "professor" in combined or "lecturer" in combined or "faculty" in combined:
        return "Teaching"
    if "office" in combined or "clerk" in combined or "assistant" in combined or "operator" in combined:
        return "Office"
    if "technical" in combined or "programmer" in combined or "scientist" in combined or "software" in combined or "computer" in combined or "it" in combined:
        return "Computer/IT"
    return clean(value) or "Computer/IT"


def link_label(status: str) -> str:
    if status == "Good Match":
        return "Apply"
    if status == "Avoid":
        return "Verify"
    return "Check"


def infer_fit_reason(status: str, role: str, eligibility: str, reason: str) -> str:
    blob = f"{role} {eligibility} {reason}".lower()
    if status == "Good Match":
        return "Good Match: Your CSE/IT/graduate profile appears relevant. Still verify the official notification PDF before final submission."
    if status == "Avoid":
        return "Avoid: This appears outside the usual CSE/IT background or may be closed. Verify only if you have the required subject, degree and documents."
    if "experience" in blob:
        return "Doubtful: CSE/IT qualification may be relevant, but experience or specialization must be verified in the official notification."
    if "age" in blob:
        return "Doubtful: Qualification may be relevant, but age/category relaxation must be verified before applying."
    if "teach" in blob or "professor" in blob or "lecturer" in blob:
        return "Watch: Relevant for the CSE teaching route. Verify NET/SET/PhD, subject code, marks and institution rules."
    if "programmer" in blob or "computer" in blob or "it" in blob or "software" in blob:
        return "Watch: Potential CSE/IT role. Open the official notice and verify exact degree, age and experience requirements."
    return "Watch: Potential government vacancy source. Verify qualification, age, subject and deadline from the official notification."


def shorten_eligibility(status: str, role: str, eligibility: str, reason: str) -> str:
    base = clean(eligibility)
    combined = f"{base} {reason}".lower()
    role_l = clean(role).lower()
    if status == "Avoid":
        return "Avoid: qualification/subject not suitable for CSE."
    if "law" in combined or "llb" in combined or "prosecution" in combined:
        return "Avoid for CSE: LLB/law degree required."
    if "teaching" in role_l:
        return "M.Tech/NET/SET/PhD as per official notice."
    if "computer" in role_l or "it" in role_l or "programmer" in combined:
        return "B.Tech/M.Tech CSE or MCA; verify exact post."
    if "office" in role_l or "assistant" in combined or "clerk" in combined:
        return "Graduate/12th route; check age and post rules."
    if base:
        return (base[:82].rstrip(" ,.;") + "...") if len(base) > 85 else base
    return "Check official notification before applying."


def infer_profile_tags(text: str) -> str:
    blob = text.lower()
    tags: List[str] = []
    if any(x in blob for x in ["b.tech", "btech", "b.e.", "graduate", "graduation"]):
        tags.append("B.Tech CSE")
    if any(x in blob for x in ["m.tech", "mtech", "pg ", "post graduate", "assistant professor", "lecturer"]):
        tags.append("M.Tech CSE")
    if any(x in blob for x in ["mca", "bca", "computer application"]):
        tags.append("MCA/BCA")
    if "experience" in blob:
        tags.append("Experience Needed")
    if "age" in blob:
        tags.append("Check Age")
    return ", ".join(dict.fromkeys(tags))


def row_to_job(row: Dict[str, Any]) -> Dict[str, Any]:
    name = english_display_text(row.get("Name"))
    eligibility = english_display_text(row.get("Eligibility")).replace("Auto-extracted:", "").strip()
    reason = english_display_text(row.get("Reason"))
    agency = english_display_text(row.get("Agency"))
    state = english_display_text(row.get("State"))
    role = role_type(clean(row.get("Role Type")), f"{name} {eligibility} {reason}")
    raw_apply_date = clean(row.get("Apply Date"))
    parsed_apply_date = parse_date(raw_apply_date)
    score_raw = clean(row.get("Match Score"))
    try:
        score = int(float(score_raw)) if score_raw else 0
    except ValueError:
        score = 0
    status_info = status_mapping(clean(row.get("Status")), score)
    link = clean(row.get("Link")) or clean(row.get("Source URL"))
    subtitle_parts = [part for part in [agency, state] if part]
    subtitle = " / ".join(subtitle_parts) if subtitle_parts else "Official recruitment source"

    fit_reason = infer_fit_reason(status_info["status"], role, eligibility, reason)
    verified_on = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).strftime("%d %b %Y")
    return {
        "job": safe_job_title(name),
        "subtitle": subtitle[:90],
        "eligible_for": shorten_eligibility(status_info["status"], role, eligibility, reason),
        "fit_reason": fit_reason,
        "why": fit_reason,
        "verified_on": verified_on,
        "profile_tags": infer_profile_tags(f"{name} {eligibility} {reason} {role}"),
        "type": role,
        "status": status_info["status"],
        "status_label": status_info["label"],
        "status_class": status_info["class"],
        "last_date_iso": parsed_apply_date.isoformat() if parsed_apply_date else "",
        "last_date_display": display_date(raw_apply_date, parsed_apply_date),
        "official_link": link,
        "official_label": link_label(status_info["status"]),
        "notification_link": link,
        "notification_label": "Notification",
        "apply_link": link,
        "apply_label": link_label(status_info["status"]),
        "state": state,
        "agency": agency,
        "match_score": score,
        "source": "auto_scanner",
        "source_url": clean(row.get("Source URL")),
    }


def load_manual_jobs(path: Path = MANUAL_JOBS_PATH) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        jobs = payload.get("jobs") if isinstance(payload, dict) else payload
        if not isinstance(jobs, list):
            return []
        clean_jobs: List[Dict[str, Any]] = []
        for job in jobs:
            if isinstance(job, dict) and clean(job.get("job")) and clean(job.get("official_link")):
                job = sanitize_job_record(dict(job))
                job["source"] = job.get("source") or "manual_curated"
                clean_jobs.append(job)
        return clean_jobs
    except Exception as exc:
        print(f"[WARN] Could not load manual jobs from {path}: {exc}")
        return []


def split_manual_jobs(manual_jobs: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    """Return active vacancies, broad watch sources, and expired count.

    The old dashboard counted portal shortcuts as if they were live vacancies.  That
    is why the total stayed at 26 even when no new vacancy had been discovered.
    """
    active: List[Dict[str, Any]] = []
    watch_sources: List[Dict[str, Any]] = []
    expired = 0
    for job in manual_jobs:
        source = clean(job.get("source"))
        no_deadline_watch = not clean(job.get("last_date_iso")) and clean(job.get("status")) == "Watch"
        if source == "manual_all_india_watchlist" or no_deadline_watch:
            watch_sources.append(job)
            continue
        if is_closed_job(job):
            expired += 1
            continue
        active.append(job)
    return active, watch_sources, expired


def load_previous_payload(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def previous_active_auto_jobs(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    jobs = payload.get("jobs") if isinstance(payload, dict) else []
    if not isinstance(jobs, list):
        return []
    out: List[Dict[str, Any]] = []
    for job in jobs:
        if not isinstance(job, dict) or is_closed_job(job):
            continue
        source = clean(job.get("source"))
        cleaned_job = sanitize_job_record(job)
        if (source == "auto_scanner" or (source not in {"manual_curated", "manual_all_india_watchlist"} and source != "")) and is_useful_auto_job(cleaned_job):
            out.append(cleaned_job)
    return out


def is_closed_job(job: Dict[str, Any]) -> bool:
    date_raw = clean(job.get("last_date_iso"))
    if not date_raw:
        return False
    try:
        d = dt.date.fromisoformat(date_raw)
    except ValueError:
        return False
    return d < dt.date.today()


def is_useful_auto_job(job: Dict[str, Any]) -> bool:
    job = sanitize_job_record(job)
    title = clean(job.get("job")).lower()
    subtitle = clean(job.get("subtitle")).lower()
    eligible = clean(job.get("eligible_for")).lower()
    agency = clean(job.get("agency")).lower()
    blob = f"{title} {subtitle} {eligible} {agency}"

    if is_false_positive_title(title):
        return False
    if any(bad in blob for bad in AUTO_EXCLUDE_TITLE_KEYWORDS):
        return False
    if is_closed_job(job):
        return False
    if job.get("status") == "Avoid":
        return False

    # A score alone must not promote a navigation/menu fragment. The visible
    # title itself needs to look like a real notice, role or recruitment item.
    has_title_signal = any(signal in title for signal in ROLE_TITLE_SIGNALS)
    if not has_title_signal:
        return False

    score = int(job.get("match_score") or 0)
    if score >= 20:
        return True
    return any(signal in blob for signal in ROLE_TITLE_SIGNALS)


def merge_manual_and_auto_jobs(manual_jobs: List[Dict[str, Any]], auto_jobs: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen = set()

    def add(job: Dict[str, Any]) -> None:
        job = sanitize_job_record(job)
        key = (clean(job.get("job")).lower(), clean(job.get("official_link")).lower())
        if key in seen or not key[0] or not key[1]:
            return
        seen.add(key)
        merged.append(job)

    # Keep verified/manual Rajasthan rows at the top so nightly scraping never hides them.
    for job in manual_jobs:
        add(job)

    priority = {"Good Match": 0, "Doubtful": 1, "Watch": 2, "Avoid": 3}
    auto_jobs = [job for job in auto_jobs if is_useful_auto_job(job)]
    auto_jobs.sort(key=lambda j: (priority.get(j.get("status"), 9), -(j.get("match_score") or 0), j.get("last_date_iso") or "9999-12-31"))
    for job in auto_jobs:
        add(job)
        if len(merged) >= limit:
            break

    return merged[:limit]


def build_json_from_excel(
    excel_path: Path,
    limit: int,
    manual_jobs: Optional[List[Dict[str, Any]]] = None,
    previous_payload: Optional[Dict[str, Any]] = None,
    scan_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    df = pd.read_excel(excel_path, sheet_name="All Raw Matches")
    jobs: List[Dict[str, Any]] = []
    seen = set()
    if not df.empty:
        for _, row in df.iterrows():
            job = row_to_job(row.to_dict())
            key = (job["job"].lower(), job["official_link"].lower())
            if key in seen or not job["official_link"]:
                continue
            seen.add(key)
            jobs.append(job)

    priority = {"Good Match": 0, "Doubtful": 1, "Watch": 2, "Avoid": 3}
    jobs.sort(key=lambda j: (priority.get(j["status"], 9), -(j.get("match_score") or 0), j.get("last_date_iso") or "9999-12-31"))
    current_auto_jobs = [job for job in jobs if is_useful_auto_job(job)]

    manual_jobs = manual_jobs or []
    active_manual, watch_sources, expired_manual_count = split_manual_jobs(manual_jobs)
    previous_payload = previous_payload or {}
    carried_auto_jobs: List[Dict[str, Any]] = []
    scan_degraded = False
    if not current_auto_jobs:
        carried_auto_jobs = previous_active_auto_jobs(previous_payload)
        if carried_auto_jobs:
            scan_degraded = True
            print(f"[WARN] Current scan produced no useful auto vacancy; carrying {len(carried_auto_jobs)} previous active auto rows.")

    auto_for_merge = current_auto_jobs or carried_auto_jobs
    merged = merge_manual_and_auto_jobs(active_manual, auto_for_merge, limit)
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30)))
    last_success = now.isoformat(timespec="seconds") if current_auto_jobs else clean(previous_payload.get("last_successful_auto_update"))

    if current_auto_jobs:
        updated_label = f"Updated: {now.strftime('%d %b %Y')} • {len(merged)} current vacancies"
        scan_status = "ok"
    elif carried_auto_jobs:
        updated_label = f"Scanned: {now.strftime('%d %b %Y')} • showing last successful vacancy data"
        scan_status = "degraded_carried_forward"
    else:
        updated_label = f"Scanned: {now.strftime('%d %b %Y')} • no live auto vacancy found"
        scan_status = "no_auto_matches"

    report = dict(scan_report or {})
    report.update({
        "useful_auto_count": len(current_auto_jobs),
        "carried_auto_count": len(carried_auto_jobs),
        "active_manual_count": len(active_manual),
        "watch_source_count": len(watch_sources),
        "expired_manual_count": expired_manual_count,
        "final_dashboard_count": len(merged),
        "scan_status": scan_status,
    })
    print(
        f"[INFO] useful auto={len(current_auto_jobs)} | carried auto={len(carried_auto_jobs)} | "
        f"active manual={len(active_manual)} | source shortcuts={len(watch_sources)} | expired manual={expired_manual_count}"
    )
    print(f"[INFO] Final dashboard rows: {len(merged)}")

    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "last_scan_at": now.isoformat(timespec="seconds"),
        "last_successful_auto_update": last_success,
        "updated_label": updated_label,
        "source": "active verified jobs + official all-India scanner",
        "manual_count": len(active_manual),
        "auto_count": len(current_auto_jobs),
        "scan_status": scan_status,
        "scan_report": report,
        "watch_sources": watch_sources,
        "jobs": merged,
    }


def write_json_safely(payload: Dict[str, Any], out_json: Path) -> None:
    jobs = payload.get("jobs") or []
    out_json.parent.mkdir(parents=True, exist_ok=True)
    temp_path = out_json.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(out_json)
    print(f"[OK] Updated {out_json} with {len(jobs)} jobs.")




def run_faculty_quick_mode(mode: str) -> None:
    """Compatibility shortcut for quick testing the faculty-jobs scraper.

    The faculty jobs page is generated by update_faculty_jobs_data.py. This wrapper
    accepts --mode 10 so the requested command does not fail and delegates to the
    correct faculty updater with a small URL/post limit.
    """
    faculty_script = REPO_ROOT / "scripts" / "update_faculty_jobs_data.py"
    cmd = [sys.executable, str(faculty_script), "--mode", str(mode)]
    print("[INFO] Delegating quick faculty test to:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(REPO_ROOT))

def main() -> None:
    parser = argparse.ArgumentParser(description="Update jobs/jobs-data.json for the static dashboard.")
    parser.add_argument("--profile", default=None, help="Optional profile.json path for the finder.")
    parser.add_argument("--sources", default=None, help="Optional sources_gov_jobs.csv path for the finder.")
    parser.add_argument("--excel-out", default="jobs/government_jobs_tracker.xlsx", help="Temporary / committed Excel output path.")
    parser.add_argument("--out-json", default="jobs/jobs-data.json", help="Dashboard JSON output path.")
    parser.add_argument("--manual-json", default="jobs/manual-jobs.json", help="Manual verified dashboard jobs that must always remain visible.")
    parser.add_argument("--archive-json", default="jobs/job-archive.json", help="Persistent archive for expired or retired government jobs.")
    parser.add_argument("--max-pdfs", type=int, default=int(os.getenv("MAX_PDFS", "10")), help="Max PDFs to parse per source.")
    parser.add_argument("--max-detail-pages", type=int, default=int(os.getenv("MAX_DETAIL_PAGES", "8")), help="Max recruitment/detail pages to follow per source.")
    parser.add_argument("--limit", type=int, default=int(os.getenv("MAX_DASHBOARD_JOBS", "120")), help="Max dashboard jobs to keep.")
    parser.add_argument("--mode", default="full", help="Compatibility: use --mode 10 to quick-test the faculty-jobs scraper on only 10 URLs/posts.")
    args = parser.parse_args()

    if str(args.mode).strip().isdigit():
        run_faculty_quick_mode(str(args.mode).strip())
        return

    os.chdir(REPO_ROOT)

    # Recover any richer job history from earlier Git commits before reading the
    # current JSON. This prevents a stale local release push from shrinking the
    # active list or erasing already-indexed URLs.
    history_guard = REPO_ROOT / "scripts" / "preserve_job_history.py"
    if history_guard.exists():
        subprocess.check_call([sys.executable, str(history_guard), "--kind", "government"], cwd=str(REPO_ROOT))

    if str(args.mode).strip().lower() in {"archive-only", "rebuild-pages", "repair-pages"}:
        out_json = REPO_ROOT / args.out_json
        archive_json = REPO_ROOT / args.archive_json
        payload = load_json_payload(out_json)
        existing_archive = load_json_payload(archive_json)
        register_invalid_generated_jobs(list(payload.get("jobs") or []) + list(existing_archive.get("jobs") or []))
        current_clean = [sanitize_job_record(job) for job in (payload.get("jobs") or []) if keep_historical_job(job)]
        archive_clean = [sanitize_job_record(job) for job in (existing_archive.get("jobs") or []) if keep_historical_job(job)]
        active_jobs, archived_jobs = reconcile_jobs(
            current_clean,
            [],
            archive_clean,
            kind="government",
            missing_grace_days=14,
        )
        payload["jobs"] = active_jobs
        payload["active_count"] = len(active_jobs)
        payload["archive_count"] = len(archived_jobs)
        write_json_safely(payload, out_json)
        archive_json.parent.mkdir(parents=True, exist_ok=True)
        archive_json.write_text(json.dumps({
            "generated_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).isoformat(timespec="seconds"),
            "retention_days_in_sitemap": 365,
            "jobs": archived_jobs,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        detail_generator = REPO_ROOT / "scripts" / "generate_govt_job_pages.py"
        subprocess.check_call([sys.executable, str(detail_generator)], cwd=str(REPO_ROOT))
        print(f"[OK] Rebuilt government pages with {len(active_jobs)} active and {len(archived_jobs)} archived jobs")
        return
    excel_path = REPO_ROOT / args.excel_out
    out_json = REPO_ROOT / args.out_json
    manual_json = REPO_ROOT / args.manual_json
    archive_json = REPO_ROOT / args.archive_json
    manual_jobs = load_manual_jobs(manual_json)
    previous_payload = load_previous_payload(out_json)
    print(f"[INFO] Loaded {len(manual_jobs)} manual entries from {manual_json}")

    finder = load_finder_module()
    try:
        scan_report = finder.run(args.profile, args.sources, str(excel_path), args.max_pdfs, args.max_detail_pages)
    except Exception as exc:
        print(f"[ERROR] Finder failed: {exc}")
        if out_json.exists():
            print(f"[WARN] Keeping existing {out_json} unchanged.")
            return
        raise

    payload = build_json_from_excel(
        excel_path,
        args.limit,
        manual_jobs=manual_jobs,
        previous_payload=previous_payload,
        scan_report=scan_report,
    )

    existing_archive = load_json_payload(archive_json)
    register_invalid_generated_jobs(list(previous_payload.get("jobs") or []) + list(existing_archive.get("jobs") or []))
    current_clean = [sanitize_job_record(job) for job in (payload.get("jobs") or []) if keep_historical_job(job)]
    previous_clean = [sanitize_job_record(job) for job in (previous_payload.get("jobs") or []) if keep_historical_job(job)]
    archive_clean = [sanitize_job_record(job) for job in (existing_archive.get("jobs") or []) if keep_historical_job(job)]
    active_jobs, archived_jobs = reconcile_jobs(
        current_clean,
        previous_clean,
        archive_clean,
        kind="government",
        missing_grace_days=14,
    )
    payload["jobs"] = active_jobs
    payload["active_count"] = len(active_jobs)
    payload["archive_count"] = len(archived_jobs)
    payload["updated_label"] = f"Updated: {dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).strftime('%d %b %Y')} • {len(active_jobs)} active vacancies"
    write_json_safely(payload, out_json)

    archive_payload = {
        "generated_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).isoformat(timespec="seconds"),
        "retention_days_in_sitemap": 365,
        "jobs": archived_jobs,
    }
    archive_json.parent.mkdir(parents=True, exist_ok=True)
    archive_json.write_text(json.dumps(archive_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Updated {archive_json} with {len(archived_jobs)} archived government jobs.")

    scan_report_path = REPO_ROOT / "jobs" / "jobs-scan-report.json"
    scan_report_path.write_text(json.dumps(payload.get("scan_report", {}), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Wrote scan diagnostics to {scan_report_path}")

    # Keep government job titles clickable and generate one SEO detail page per row.
    detail_generator = REPO_ROOT / "scripts" / "generate_govt_job_pages.py"
    if detail_generator.exists():
        subprocess.check_call([sys.executable, str(detail_generator)], cwd=str(REPO_ROOT))


if __name__ == "__main__":
    main()
