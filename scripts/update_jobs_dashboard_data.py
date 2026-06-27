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
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
FINDER_PATH = Path(__file__).with_name("govt_job_finder.py")
MANUAL_JOBS_PATH = REPO_ROOT / "jobs" / "manual-jobs.json"

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
    value = clean(value)
    if not value or value.lower().startswith("check"):
        return None
    formats = [
        "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
        "%d-%m-%y", "%d/%m/%y", "%d.%m.%y",
        "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
        "%d %b %Y", "%d %B %Y",
        "%d %b %y", "%d %B %y",
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
    name = clean(name)
    for sep in [" | ", " - ", " – "]:
        if sep in name:
            first = clean(name.split(sep)[0])
            if len(first) >= 12:
                name = first
                break
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
    name = clean(row.get("Name"))
    eligibility = clean(row.get("Eligibility")).replace("Auto-extracted:", "").strip()
    reason = clean(row.get("Reason"))
    agency = clean(row.get("Agency"))
    state = clean(row.get("State"))
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
                job = dict(job)
                job["source"] = job.get("source") or "manual_curated"
                clean_jobs.append(job)
        return clean_jobs
    except Exception as exc:
        print(f"[WARN] Could not load manual jobs from {path}: {exc}")
        return []


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
    title = clean(job.get("job")).lower()
    subtitle = clean(job.get("subtitle")).lower()
    eligible = clean(job.get("eligible_for")).lower()
    agency = clean(job.get("agency")).lower()
    blob = f"{title} {subtitle} {eligible} {agency}"

    # Remove obvious non-vacancy pages, but do not over-filter.
    if any(bad in blob for bad in AUTO_EXCLUDE_TITLE_KEYWORDS):
        return False
    if is_closed_job(job):
        return False
    if job.get("status") == "Avoid":
        return False

    score = int(job.get("match_score") or 0)
    useful_words = [
        "recruit", "vacancy", "advertisement", "notification", "apply",
        "assistant professor", "lecturer", "faculty", "computer", "it",
        "programmer", "software", "scientist", "assistant", "clerk", "operator"
    ]

    # Keep more all-India scanner output as Manual Check/Watch, instead of hiding it.
    if score >= 20:
        return True
    if any(word in blob for word in useful_words):
        return True
    return False


def merge_manual_and_auto_jobs(manual_jobs: List[Dict[str, Any]], auto_jobs: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen = set()

    def add(job: Dict[str, Any]) -> None:
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


def build_json_from_excel(excel_path: Path, limit: int, manual_jobs: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    df = pd.read_excel(excel_path, sheet_name="All Raw Matches")
    if df.empty:
        return {"jobs": []}

    jobs: List[Dict[str, Any]] = []
    seen = set()
    for _, row in df.iterrows():
        job = row_to_job(row.to_dict())
        key = (job["job"].lower(), job["official_link"].lower())
        if key in seen or not job["official_link"]:
            continue
        seen.add(key)
        jobs.append(job)

    # Keep dashboard useful and not too noisy.
    priority = {"Good Match": 0, "Doubtful": 1, "Watch": 2, "Avoid": 3}
    jobs.sort(key=lambda j: (priority.get(j["status"], 9), -(j.get("match_score") or 0), j.get("last_date_iso") or "9999-12-31"))
    manual_jobs = manual_jobs or []
    useful_auto_count = sum(1 for job in jobs if is_useful_auto_job(job))
    print(f"[INFO] Excel rows converted: {len(jobs)} | useful auto rows after filter: {useful_auto_count} | manual rows: {len(manual_jobs)}")
    jobs = merge_manual_and_auto_jobs(manual_jobs, jobs, limit)
    print(f"[INFO] Final dashboard rows: {len(jobs)}")

    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30)))
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "updated_label": now.strftime("Updated: %d %b %Y"),
        "source": "manual verified jobs + nightly government job scanner",
        "manual_count": len(manual_jobs),
        "jobs": jobs,
    }


def write_json_safely(payload: Dict[str, Any], out_json: Path) -> None:
    jobs = payload.get("jobs") or []
    if not jobs and out_json.exists():
        print(f"[WARN] No jobs found. Keeping existing {out_json} unchanged.")
        return
    out_json.parent.mkdir(parents=True, exist_ok=True)
    temp_path = out_json.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(out_json)
    print(f"[OK] Updated {out_json} with {len(jobs)} jobs.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Update jobs/jobs-data.json for the static dashboard.")
    parser.add_argument("--profile", default=None, help="Optional profile.json path for the finder.")
    parser.add_argument("--sources", default=None, help="Optional sources_gov_jobs.csv path for the finder.")
    parser.add_argument("--excel-out", default="jobs/government_jobs_tracker.xlsx", help="Temporary / committed Excel output path.")
    parser.add_argument("--out-json", default="jobs/jobs-data.json", help="Dashboard JSON output path.")
    parser.add_argument("--manual-json", default="jobs/manual-jobs.json", help="Manual verified dashboard jobs that must always remain visible.")
    parser.add_argument("--max-pdfs", type=int, default=int(os.getenv("MAX_PDFS", "4")), help="Max PDFs to parse per source.")
    parser.add_argument("--limit", type=int, default=int(os.getenv("MAX_DASHBOARD_JOBS", "60")), help="Max dashboard jobs to keep.")
    args = parser.parse_args()

    os.chdir(REPO_ROOT)
    excel_path = REPO_ROOT / args.excel_out
    out_json = REPO_ROOT / args.out_json
    manual_json = REPO_ROOT / args.manual_json
    manual_jobs = load_manual_jobs(manual_json)
    print(f"[INFO] Loaded {len(manual_jobs)} manual verified dashboard jobs from {manual_json}")

    finder = load_finder_module()
    try:
        finder.run(args.profile, args.sources, str(excel_path), args.max_pdfs)
    except Exception as exc:
        print(f"[ERROR] Finder failed: {exc}")
        if out_json.exists():
            print(f"[WARN] Keeping existing {out_json} unchanged.")
            return
        raise

    payload = build_json_from_excel(excel_path, args.limit, manual_jobs=manual_jobs)
    write_json_safely(payload, out_json)


if __name__ == "__main__":
    main()
