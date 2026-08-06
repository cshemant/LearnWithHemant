#!/usr/bin/env python3
"""Protect every generated job URL from being lost after a local Git push.

The script merges the current JSON files with records found in Git history and
with a persistent URL ledger. Recent jobs that disappeared only because a stale
local snapshot was pushed are carried forward temporarily. Older/missing jobs
are moved to the archive, never silently deleted.

This script uses only the Python standard library so it can run immediately in
GitHub Actions before the scrapers and page generators.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from job_archive_utils import clean, identity_key, load_json_payload, parse_iso_date, slugify

ROOT = Path(__file__).resolve().parents[1]
TODAY = dt.date.today()
RECENT_SNAPSHOT_LIMIT = 12
HISTORY_COMMIT_LIMIT = 250
CARRY_FORWARD_DAYS = 14

CONFIGS = {
    "government": {
        "active": ROOT / "jobs" / "jobs-data.json",
        "archive": ROOT / "jobs" / "job-archive.json",
        "ledger": ROOT / "jobs" / "job-url-ledger.json",
        "prefix": "/jobs/",
        "reserved": {"archive", "faculty-jobs"},
    },
    "faculty": {
        "active": ROOT / "jobs" / "faculty-jobs" / "faculty-jobs-data.json",
        "archive": ROOT / "jobs" / "faculty-jobs" / "faculty-jobs-archive.json",
        "ledger": ROOT / "jobs" / "faculty-jobs" / "faculty-job-url-ledger.json",
        "prefix": "/jobs/faculty-jobs/",
        "reserved": {"archive", "all-india", "cse", "rajasthan", "assistant-professor", "closing-soon"},
    },
}
INVALID_PATHS = ROOT / "jobs" / "invalid-job-urls.json"

FALSE_POSITIVE_PHRASES = (
    "awards and accolades", "awards & accolades", "business model", "corporate profile",
    "skip to main content", "screen reader access", "universal content",
    "single sign on", "one digital identity", "question bank", "photo gallery",
    "video gallery", "font size", "cut-off date for having completed graduation",
)
ROLE_SIGNALS = (
    "recruitment", "vacancy", "vacancies", "notification", "notice", "advertisement",
    "advt", "job", "opening", "assistant professor", "lecturer", "teacher", "faculty",
    "programmer", "developer", "scientist", "technical assistant", "computer operator",
    "data entry operator", "junior assistant", "office assistant", "clerk", "stenographer",
    "instructor", "engineer", "officer", "exam",
)


def acceptable_historical_job(job: Dict[str, Any], kind: str) -> bool:
    """Reject only obvious scanner/navigation garbage while preserving real URLs."""
    if kind != "government":
        return True
    source = clean(job.get("source")).lower()
    if source in {"manual_curated", "manual_all_india_watchlist"}:
        return True
    title = clean(job.get("job")).lower().replace("&", "and")
    if len(title) < 8:
        return False
    if any(phrase.replace("&", "and") in title for phrase in FALSE_POSITIVE_PHRASES):
        return False
    if source == "auto_scanner" and not any(signal in title for signal in ROLE_SIGNALS):
        return False
    return True


def now_ist() -> str:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).isoformat(timespec="seconds")


def normalize_path(value: Any) -> str:
    raw = clean(value)
    if not raw:
        return ""
    raw = "/" + raw.strip("/") + "/"
    return re.sub(r"/+", "/", raw)


_INVALID_PATH_CACHE: Optional[set[str]] = None


def invalid_paths() -> set[str]:
    global _INVALID_PATH_CACHE
    if _INVALID_PATH_CACHE is None:
        payload = load_json_payload(INVALID_PATHS)
        _INVALID_PATH_CACHE = {normalize_path(path) for path in payload.get("paths", []) if clean(path)}
    return _INVALID_PATH_CACHE


def get_slug(job: Dict[str, Any], kind: str) -> str:
    cfg = CONFIGS[kind]
    slug = clean(job.get("slug"))
    if not slug:
        detail = normalize_path(job.get("detail_url"))
        prefix = cfg["prefix"]
        if detail.startswith(prefix):
            slug = detail[len(prefix):].strip("/")
    if not slug:
        if kind == "faculty":
            seed = " ".join(clean(job.get(key)) for key in ("college", "post", "department"))
        else:
            seed = " ".join(clean(job.get(key)) for key in ("job", "state", "type"))
        slug = slugify(seed, "job")
    slug = slugify(slug, "job")
    if slug in cfg["reserved"]:
        return ""
    return slug


def normalize_job(job: Dict[str, Any], kind: str) -> Optional[Dict[str, Any]]:
    if not isinstance(job, dict):
        return None
    out = dict(job)
    if not acceptable_historical_job(out, kind):
        return None
    slug = get_slug(out, kind)
    if not slug:
        return None
    out["slug"] = slug
    out["detail_url"] = f"{CONFIGS[kind]['prefix']}{slug}/"
    if normalize_path(out["detail_url"]) in invalid_paths():
        return None
    return out


def read_json_from_git(commit: str, relative_path: str) -> Dict[str, Any]:
    try:
        proc = subprocess.run(
            ["git", "show", f"{commit}:{relative_path}"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return {}
        data = json.loads(proc.stdout)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def history_commits(paths: Sequence[Path]) -> List[str]:
    try:
        rel_paths = [str(path.relative_to(ROOT)).replace("\\", "/") for path in paths]
        proc = subprocess.run(
            ["git", "log", "--all", f"--max-count={HISTORY_COMMIT_LIMIT}", "--format=%H", "--", *rel_paths],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return []
        seen = set()
        commits = []
        for line in proc.stdout.splitlines():
            commit = line.strip()
            if commit and commit not in seen:
                seen.add(commit)
                commits.append(commit)
        return commits
    except Exception:
        return []


def extract_jobs(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    jobs = payload.get("jobs")
    return [dict(job) for job in jobs if isinstance(job, dict)] if isinstance(jobs, list) else []


def record_quality(job: Dict[str, Any]) -> int:
    fields = (
        "job", "college", "post", "department", "agency", "state", "eligible_for",
        "eligibility", "last_date_iso", "official_link", "notification_link", "apply_link",
        "source_url", "slug", "detail_url",
    )
    return sum(1 for field in fields if clean(job.get(field)))


def merge_by_slug(records: Iterable[Dict[str, Any]], kind: str) -> Dict[str, Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for raw in records:
        job = normalize_job(raw, kind)
        if not job:
            continue
        slug = job["slug"]
        old = merged.get(slug)
        if old is None or record_quality(job) >= record_quality(old):
            combined = dict(old or {})
            combined.update({key: value for key, value in job.items() if value not in (None, "", [], {})})
            combined["slug"] = slug
            combined["detail_url"] = f"{CONFIGS[kind]['prefix']}{slug}/"
            merged[slug] = combined
    return merged


def is_expired(job: Dict[str, Any]) -> bool:
    deadline = parse_iso_date(job.get("last_date_iso"))
    status_blob = f"{clean(job.get('status'))} {clean(job.get('status_label'))}".lower()
    return bool((deadline and deadline < TODAY) or any(word in status_blob for word in ("closed", "expired")))


def seen_recently(job: Dict[str, Any]) -> bool:
    seen = parse_iso_date(job.get("last_seen_at")) or parse_iso_date(job.get("verified_on"))
    if seen is None:
        return False
    return (TODAY - seen).days <= CARRY_FORWARD_DAYS


def mark_active_recovered(job: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(job)
    out["is_archived"] = False
    out["data_state"] = "recovered_from_git_history"
    out["missing_since"] = clean(out.get("missing_since")) or TODAY.isoformat()
    out.pop("archived_at", None)
    out.pop("archive_reason", None)
    if clean(out.get("status")).lower() in {"closed", "archived"}:
        out["status"] = "Watch"
        out["status_label"] = "Verify Current Status"
        out["status_class"] = "caution"
    return out


def mark_archived(job: Dict[str, Any], reason: str) -> Dict[str, Any]:
    out = dict(job)
    out["is_archived"] = True
    out["archived_at"] = clean(out.get("archived_at")) or TODAY.isoformat()
    out["archive_reason"] = clean(out.get("archive_reason")) or reason
    if is_expired(out):
        out["status"] = "Closed"
        out["status_label"] = "Application Closed"
        out["status_class"] = "avoid" if clean(out.get("type")).lower() != "faculty" else "closed"
    else:
        out["status"] = "Archived"
        out["status_label"] = "Listing Archived"
        out["status_class"] = "watch"
    return out


def sorted_jobs(jobs: Iterable[Dict[str, Any]], archived: bool = False) -> List[Dict[str, Any]]:
    result = list(jobs)
    if archived:
        result.sort(key=lambda j: (clean(j.get("archived_at")), clean(j.get("last_date_iso")), clean(j.get("slug"))), reverse=True)
    else:
        result.sort(key=lambda j: (clean(j.get("last_date_iso")) or "9999-12-31", clean(j.get("job") or j.get("college")).lower()))
    return result


def write_payload(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_history(kind: str) -> Tuple[List[List[Dict[str, Any]]], List[Dict[str, Any]]]:
    cfg = CONFIGS[kind]
    paths = [cfg["active"], cfg["archive"], cfg["ledger"]]
    commits = history_commits(paths)
    snapshots: List[List[Dict[str, Any]]] = []
    all_records: List[Dict[str, Any]] = []
    current_head = ""
    try:
        current_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=False, capture_output=True, text=True).stdout.strip()
    except Exception:
        pass

    for commit in commits:
        commit_records: List[Dict[str, Any]] = []
        for path in paths:
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            payload = read_json_from_git(commit, rel)
            jobs = extract_jobs(payload)
            commit_records.extend(jobs)
            all_records.extend(jobs)
        if commit != current_head and commit_records:
            snapshots.append(commit_records)
    return snapshots[:RECENT_SNAPSHOT_LIMIT], all_records


def preserve_kind(kind: str) -> Dict[str, int]:
    cfg = CONFIGS[kind]
    active_payload = load_json_payload(cfg["active"])
    archive_payload = load_json_payload(cfg["archive"])
    ledger_payload = load_json_payload(cfg["ledger"])

    current_active = merge_by_slug(extract_jobs(active_payload), kind)
    current_archive = merge_by_slug(extract_jobs(archive_payload), kind)
    ledger_records = extract_jobs(ledger_payload)
    recent_snapshots, all_history_records = load_history(kind)

    current_identity_to_slug = {
        identity_key(job, kind): slug
        for slug, job in current_active.items()
        if identity_key(job, kind)
    }

    # Recover recently visible active URLs. This specifically protects against a
    # stale local snapshot replacing a richer GitHub-generated JSON file.
    recovered_active = 0
    for snapshot in recent_snapshots:
        for raw in snapshot:
            job = normalize_job(raw, kind)
            if not job or job.get("is_archived") or clean(job.get("status")).lower() in {"closed", "archived"}:
                continue
            slug = job["slug"]
            if slug in current_active or slug in current_archive:
                continue
            key = identity_key(job, kind)
            if key and key in current_identity_to_slug and current_identity_to_slug[key] != slug:
                current_archive[slug] = mark_archived(job, "historical_url_alias")
                current_archive[slug]["alias_of"] = current_identity_to_slug[key]
                continue
            if not is_expired(job) and (parse_iso_date(job.get("last_date_iso")) is not None or seen_recently(job)):
                current_active[slug] = mark_active_recovered(job)
                if key:
                    current_identity_to_slug[key] = slug
                recovered_active += 1
            else:
                current_archive[slug] = mark_archived(job, "recovered_from_git_history")

    # Build a permanent ledger from every source we can access. Every valid slug
    # ever committed remains represented even after it leaves active results.
    ledger = merge_by_slug(
        [*all_history_records, *ledger_records, *current_archive.values(), *current_active.values()],
        kind,
    )

    active_slugs = set(current_active)
    recovered_archive = 0
    for slug, job in ledger.items():
        if slug in active_slugs or slug in current_archive:
            continue
        current_archive[slug] = mark_archived(job, "permanent_url_ledger")
        recovered_archive += 1

    # An active URL always wins over an archived copy of the same slug.
    for slug in active_slugs:
        current_archive.pop(slug, None)

    active_jobs = sorted_jobs(current_active.values(), archived=False)
    archived_jobs = sorted_jobs(current_archive.values(), archived=True)
    ledger_jobs = sorted_jobs(merge_by_slug([*active_jobs, *archived_jobs], kind).values(), archived=True)

    active_payload["jobs"] = active_jobs
    active_payload["active_count"] = len(active_jobs)
    active_payload["archive_count"] = len(archived_jobs)
    active_payload["history_protected_at"] = now_ist()
    if kind == "government":
        active_payload["updated_label"] = f"Updated: {TODAY.strftime('%d %b %Y')} • {len(active_jobs)} active vacancies"
    else:
        active_payload["updated_label"] = f"Updated: {TODAY.strftime('%d %b %Y')} • {len(active_jobs)} active jobs"

    archive_out = dict(archive_payload)
    archive_out["generated_at"] = now_ist()
    archive_out["retention_days_in_sitemap"] = int(archive_out.get("retention_days_in_sitemap") or 365)
    archive_out["jobs"] = archived_jobs
    archive_out["history_protected"] = True

    ledger_out = {
        "generated_at": now_ist(),
        "description": "Permanent ledger of every valid generated job URL. Do not replace this file with a smaller local snapshot.",
        "jobs": ledger_jobs,
    }

    write_payload(cfg["active"], active_payload)
    write_payload(cfg["archive"], archive_out)
    write_payload(cfg["ledger"], ledger_out)
    print(
        f"[OK] {kind}: {len(active_jobs)} active, {len(archived_jobs)} archived, "
        f"{len(ledger_jobs)} protected URLs; restored {recovered_active} active and {recovered_archive} archive records"
    )
    return {
        "active": len(active_jobs),
        "archive": len(archived_jobs),
        "ledger": len(ledger_jobs),
        "restored_active": recovered_active,
        "restored_archive": recovered_archive,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Recover and preserve job URL history from Git commits.")
    parser.add_argument("--kind", choices=["government", "faculty", "all"], default="all")
    args = parser.parse_args()
    kinds = list(CONFIGS) if args.kind == "all" else [args.kind]
    for kind in kinds:
        preserve_kind(kind)


if __name__ == "__main__":
    main()
