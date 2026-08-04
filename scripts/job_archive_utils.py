#!/usr/bin/env python3
"""Shared helpers for preserving job URLs and maintaining active/archive datasets."""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlsplit, urlunsplit


def clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def slugify(value: Any, fallback: str = "job") -> str:
    text = clean(value).lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:96].strip("-") or fallback


def parse_iso_date(value: Any) -> Optional[dt.date]:
    raw = clean(value)
    if not raw:
        return None
    try:
        return dt.date.fromisoformat(raw[:10])
    except ValueError:
        return None


def normalize_url(value: Any) -> str:
    raw = clean(value)
    if not raw or not raw.lower().startswith(("http://", "https://")):
        return ""
    try:
        parts = urlsplit(raw)
        path = re.sub(r"/+", "/", parts.path or "/").rstrip("/")
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))
    except Exception:
        return raw.lower().rstrip("/")


def identity_key(job: Dict[str, Any], kind: str) -> str:
    link = ""
    for field in ("apply_link", "notification_link", "official_link", "website_link", "source_url"):
        link = normalize_url(job.get(field))
        if link:
            break
    if kind == "faculty":
        parts = [job.get("college"), job.get("post"), job.get("department"), link]
    else:
        parts = [job.get("job"), job.get("state"), job.get("agency"), link]
    normalized = [re.sub(r"\W+", " ", clean(part).lower()).strip() for part in parts]
    return "|".join(normalized)


def load_json_payload(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _job_date(job: Dict[str, Any]) -> Optional[dt.date]:
    return parse_iso_date(job.get("last_date_iso"))


def _explicitly_closed(job: Dict[str, Any]) -> bool:
    blob = f"{clean(job.get('status'))} {clean(job.get('status_label'))}".lower()
    return any(token in blob for token in ("application closed", "closed", "expired"))


def _copy_history_metadata(job: Dict[str, Any], historical: Optional[Dict[str, Any]], today: dt.date) -> Dict[str, Any]:
    out = dict(job)
    if historical:
        if clean(historical.get("slug")):
            out["slug"] = clean(historical.get("slug"))
        out["first_seen_at"] = clean(historical.get("first_seen_at")) or clean(historical.get("last_seen_at")) or today.isoformat()
    else:
        out["first_seen_at"] = clean(out.get("first_seen_at")) or today.isoformat()
    out["last_seen_at"] = today.isoformat()
    out.pop("missing_since", None)
    return out


def _mark_archived(job: Dict[str, Any], today: dt.date, reason: str, kind: str) -> Dict[str, Any]:
    out = dict(job)
    out["archived_at"] = clean(out.get("archived_at")) or today.isoformat()
    out["archive_reason"] = reason
    out["is_archived"] = True
    if reason == "deadline_expired" or _explicitly_closed(out):
        out["status"] = "Closed"
        out["status_label"] = "Application Closed"
        out["status_class"] = "avoid" if kind == "government" else "closed"
    else:
        out["status"] = "Archived"
        out["status_label"] = "Listing Archived"
        out["status_class"] = "watch"
    return out


def _is_expired(job: Dict[str, Any], today: dt.date) -> bool:
    deadline = _job_date(job)
    return bool((deadline and deadline < today) or _explicitly_closed(job))


def _days_since(value: Any, today: dt.date) -> int:
    parsed = parse_iso_date(value)
    return (today - parsed).days if parsed else 0


def reconcile_jobs(
    current_jobs: Sequence[Dict[str, Any]],
    previous_jobs: Sequence[Dict[str, Any]],
    archived_jobs: Sequence[Dict[str, Any]],
    *,
    kind: str,
    today: Optional[dt.date] = None,
    missing_grace_days: int = 14,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return active and archived jobs while preserving stable slugs and URLs.

    * A past deadline moves a job to the archive and labels it Application Closed.
    * A temporarily missing current row is carried forward for a grace period.
    * A row missing longer than the grace period is archived as Listing Archived.
    * Archived rows remain stored permanently; sitemap retention is handled separately.
    """
    today = today or dt.date.today()
    history: Dict[str, Dict[str, Any]] = {}
    for job in list(previous_jobs) + list(archived_jobs):
        key = identity_key(job, kind)
        if key and key not in history:
            history[key] = dict(job)

    active: List[Dict[str, Any]] = []
    archive_by_key: Dict[str, Dict[str, Any]] = {}
    current_keys = set()
    used_slugs = set()

    def unique_slug(job: Dict[str, Any], fallback_seed: str) -> str:
        base = clean(job.get("slug")) or slugify(fallback_seed, "job")
        slug = base
        n = 2
        while slug in used_slugs:
            slug = f"{base[:88].rstrip('-')}-{n}"
            n += 1
        used_slugs.add(slug)
        return slug

    for raw in current_jobs:
        key = identity_key(raw, kind)
        if not key or key in current_keys:
            continue
        current_keys.add(key)
        historical = history.get(key)
        job = _copy_history_metadata(dict(raw), historical, today)
        seed = clean(job.get("job")) or " ".join(clean(job.get(x)) for x in ("college", "post", "department"))
        job["slug"] = unique_slug(job, seed)
        job["is_archived"] = False
        if _is_expired(job, today):
            archived = _mark_archived(job, today, "deadline_expired", kind)
            archive_by_key[key] = archived
        else:
            active.append(job)

    previous_by_key = {identity_key(job, kind): dict(job) for job in previous_jobs if identity_key(job, kind)}
    for key, previous in previous_by_key.items():
        if key in current_keys:
            continue
        job = dict(previous)
        if clean(job.get("slug")) in used_slugs:
            continue
        used_slugs.add(clean(job.get("slug")) or unique_slug(job, clean(job.get("job")) or "job"))
        if _is_expired(job, today):
            archive_by_key[key] = _mark_archived(job, today, "deadline_expired", kind)
            continue
        missing_since = clean(job.get("missing_since")) or today.isoformat()
        job["missing_since"] = missing_since
        if _days_since(missing_since, today) >= missing_grace_days:
            archive_by_key[key] = _mark_archived(job, today, "source_missing", kind)
        else:
            job["is_archived"] = False
            job["data_state"] = "carried_forward"
            active.append(job)

    active_keys = {identity_key(job, kind) for job in active}
    for old in archived_jobs:
        key = identity_key(old, kind)
        if not key or key in active_keys:
            continue
        if key in archive_by_key:
            old_archived_at = clean(old.get("archived_at"))
            if old_archived_at:
                archive_by_key[key]["archived_at"] = old_archived_at
            continue
        item = dict(old)
        item["is_archived"] = True
        archive_by_key[key] = item

    archive = list(archive_by_key.values())
    active.sort(key=lambda j: (clean(j.get("last_date_iso")) or "9999-12-31", clean(j.get("job") or j.get("college")).lower()))
    archive.sort(key=lambda j: (clean(j.get("archived_at")), clean(j.get("last_date_iso"))), reverse=True)
    return active, archive


def archive_sitemap_jobs(jobs: Iterable[Dict[str, Any]], retention_days: int, today: Optional[dt.date] = None) -> List[Dict[str, Any]]:
    today = today or dt.date.today()
    result = []
    for job in jobs:
        archived_at = parse_iso_date(job.get("archived_at")) or _job_date(job)
        if archived_at is None or (today - archived_at).days <= retention_days:
            result.append(dict(job))
    return result
