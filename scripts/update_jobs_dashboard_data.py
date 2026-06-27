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

    return {
        "job": safe_job_title(name),
        "subtitle": subtitle[:90],
        "eligible_for": eligibility[:260] or "Check official notification for education, subject code, age limit and documents.",
        "type": role,
        "status": status_info["status"],
        "status_label": status_info["label"],
        "status_class": status_info["class"],
        "last_date_iso": parsed_apply_date.isoformat() if parsed_apply_date else "",
        "last_date_display": display_date(raw_apply_date, parsed_apply_date),
        "official_link": link,
        "official_label": link_label(status_info["status"]),
        "state": state,
        "agency": agency,
        "match_score": score,
    }


def build_json_from_excel(excel_path: Path, limit: int) -> Dict[str, Any]:
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
    jobs = jobs[:limit]

    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30)))
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "updated_label": now.strftime("Updated: %d %b %Y"),
        "source": "nightly government job scanner",
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
    parser.add_argument("--max-pdfs", type=int, default=int(os.getenv("MAX_PDFS", "4")), help="Max PDFs to parse per source.")
    parser.add_argument("--limit", type=int, default=int(os.getenv("MAX_DASHBOARD_JOBS", "40")), help="Max dashboard jobs to keep.")
    args = parser.parse_args()

    os.chdir(REPO_ROOT)
    excel_path = REPO_ROOT / args.excel_out
    out_json = REPO_ROOT / args.out_json

    finder = load_finder_module()
    try:
        finder.run(args.profile, args.sources, str(excel_path), args.max_pdfs)
    except Exception as exc:
        print(f"[ERROR] Finder failed: {exc}")
        if out_json.exists():
            print(f"[WARN] Keeping existing {out_json} unchanged.")
            return
        raise

    payload = build_json_from_excel(excel_path, args.limit)
    write_json_safely(payload, out_json)


if __name__ == "__main__":
    main()
