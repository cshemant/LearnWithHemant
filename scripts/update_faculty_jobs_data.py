#!/usr/bin/env python3
"""
Faculty Jobs automation for Learn with Hemant.

What it does:
1. Loads verified faculty jobs from jobs/faculty-jobs/manual-faculty-jobs.json.
2. Optionally scans enabled official source pages from sources_faculty_jobs.csv.
3. Deduplicates and normalizes rows.
4. Writes jobs/faculty-jobs/faculty-jobs-data.json.
5. Generates the public dashboard, category pages, detail pages and faculty sitemap.

Designed for GitHub Actions cron. If scraping fails, the existing/manual data stays live.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parents[1]
FACULTY_ROOT = REPO_ROOT / "jobs" / "faculty-jobs"
DEFAULT_MANUAL_PATH = FACULTY_ROOT / "manual-faculty-jobs.json"
DEFAULT_OUT_JSON = FACULTY_ROOT / "faculty-jobs-data.json"
DEFAULT_SOURCES = REPO_ROOT / "sources_faculty_jobs.csv"
BASE_URL = "https://learnwithhemant.com"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

INFER_TEACHING_KEYWORDS = ["assistant professor", "associate professor", "professor", "lecturer", "faculty", "trainer", "teacher"]
INFER_CSE_KEYWORDS = ["computer science", "cse", "information technology", " it ", "mca", "bca", "computer applications", "data science", "ai", "artificial intelligence", "software"]
AUTO_EXCLUDE_KEYWORDS = ["result", "admit card", "answer key", "syllabus", "old", "archive", "merit list", "shortlisted", "interview schedule"]
NON_TEACHING_EXCLUDE_KEYWORDS = [
    "project associate", "project assistant", "research associate", "research assistant", "junior research fellow",
    "senior research fellow", " jrf", " srf", "lab assistant", "office assistant", "technical assistant",
    "non teaching", "non-teaching", "admin staff", "placement officer", "registrar", "librarian",
]
BAD_EXTERNAL_LINK_DOMAINS = {
    "youtube.com", "youtu.be", "facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com",
    "whatsapp.com", "wa.me", "telegram.me", "t.me", "pinterest.com", "play.google.com", "apps.apple.com", "aratt.ai",
}
BANNED_PUBLIC_TERM_RE = re.compile(r"faculty[\s_-]*plus|external[\s_-]*listing|external[\s_-]*discovery", re.I)


JOB_PORTAL_EXCLUDE_DOMAINS = {
    "faculty" + "plus.com",  # excluded from general search; allowed only through External listing discovery mode
}
EXTERNAL_LISTING_DOMAINS = {"faculty" + "plus.com"}
INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Delhi", "Goa", "Gujarat",
    "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra",
    "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Chandigarh", "Jammu and Kashmir",
    "Ladakh", "Puducherry"
]
DATE_CANDIDATE_RE = re.compile(
    r"(\d{1,2}(?:st|nd|rd|th)?[\s\-/\.]+(?:\d{1,2}|Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[\s\-/\.,]+\d{2,4}|"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[\s]+\d{1,2}(?:st|nd|rd|th)?[,\s]+\d{2,4}|"
    r"\d{4}[\-/\.]\d{1,2}[\-/\.]\d{1,2})",
    re.I,
)
LAST_DATE_HINT_RE = re.compile(
    r"(last\s+date|last\s+date\s+to\s+apply|last\s+date\s+for\s+submission|deadline|closing\s+date|apply\s+by|apply\s+on\s+or\s+before|before)",
    re.I,
)


def clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").strip().split())



def public_clean(value: Any) -> str:
    value = clean(value)
    if not value:
        return ""
    value = BANNED_PUBLIC_TERM_RE.sub("source", value)
    return clean(value)


def shorten(value: Any, max_chars: int = 140) -> str:
    value = public_clean(value)
    if len(value) <= max_chars:
        return value
    cut = value[: max_chars - 1].rsplit(" ", 1)[0].strip(" ,;:-")
    return (cut or value[: max_chars - 1]).rstrip() + "…"


def dedupe_sentences(value: str, max_chars: int = 420) -> str:
    value = public_clean(value)
    if not value:
        return ""
    parts = re.split(r"(?<=[.!?])\s+|\s+[•|]\s+", value)
    seen = set()
    out = []
    for part in parts:
        part = clean(part.strip(" -–|•"))
        if not part:
            continue
        key = re.sub(r"[^a-z0-9]+", " ", part.lower()).strip()
        if key in seen:
            continue
        seen.add(key)
        out.append(part)
        if len(" ".join(out)) >= max_chars:
            break
    return shorten(" ".join(out), max_chars)


def link_domain_blocked(url: str) -> bool:
    domain = domain_of(url)
    if not domain:
        return False
    return any(domain == bad or domain.endswith("." + bad) for bad in BAD_EXTERNAL_LINK_DOMAINS)


def safe_public_link(url: str) -> str:
    url = clean(url)
    if not url or url == "#":
        return ""
    # Never expose source-listing brand/profile/social links on public pages.
    if BANNED_PUBLIC_TERM_RE.search(url):
        return ""
    if url.startswith("mailto:"):
        email = extract_email(url.replace("mailto:", ""))
        return f"mailto:{email}" if email else ""
    if not url.startswith(("http://", "https://")):
        return ""
    if is_external_listing_url(url) or link_domain_blocked(url):
        return ""
    return url

def slugify(value: str, fallback: str = "faculty-job") -> str:
    value = clean(value).lower()
    value = re.sub(r"&", " and ", value)
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:90].strip("-") or fallback


def parse_bool(value: str) -> bool:
    return clean(value).lower() in {"1", "true", "yes", "y", "enabled", "on"}


def parse_date(value: str) -> Optional[dt.date]:
    value = clean(value)
    if not value:
        return None
    value = re.sub(r"(\d{1,2})(st|nd|rd|th)", r"\1", value, flags=re.I)
    value = value.replace(",", " ")
    formats = [
        "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
        "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
        "%d-%m-%y", "%d/%m/%y", "%d.%m.%y",
        "%d %b %Y", "%d %B %Y", "%d %b %y", "%d %B %y",
        "%b %d %Y", "%B %d %Y", "%b %d %y", "%B %d %y",
    ]
    for fmt in formats:
        try:
            parsed = dt.datetime.strptime(value, fmt).date()
            # Convert two-digit years that parse into the 1900s to the current century.
            if parsed.year < 2000:
                parsed = parsed.replace(year=parsed.year + 100)
            return parsed
        except ValueError:
            pass
    # Try to extract dates from text such as "Last date: 15 July 2026".
    match = DATE_CANDIDATE_RE.search(value)
    if match and match.group(1) != value:
        return parse_date(match.group(1))
    return None


def extract_last_date(text: str) -> tuple[str, Optional[dt.date]]:
    """Prefer a date near deadline/last-date wording instead of any random date on the page."""
    text = clean(text)
    if not text:
        return "", None
    # First search windows around deadline hints.
    for hint in LAST_DATE_HINT_RE.finditer(text):
        window = text[hint.start(): hint.start() + 220]
        date_match = DATE_CANDIDATE_RE.search(window)
        if date_match:
            raw = clean(date_match.group(1))
            parsed = parse_date(raw)
            if parsed:
                return raw, parsed
    # Fallback: first date-like value found in title/snippet/page.
    date_match = DATE_CANDIDATE_RE.search(text)
    if date_match:
        raw = clean(date_match.group(1))
        return raw, parse_date(raw)
    return "", None

def display_date(raw: str, parsed: Optional[dt.date]) -> str:
    if parsed:
        return parsed.strftime("%d-%b-%Y")
    raw = clean(raw)
    return raw or "Check official notice"


def status_class(status: str) -> str:
    s = clean(status).lower()
    if "good" in s or "active" in s:
        return "good"
    if "avoid" in s or "closed" in s:
        return "avoid"
    if "manual" in s or "check" in s or "doubt" in s:
        return "caution"
    return "watch"


def infer_department(text: str) -> str:
    blob = f" {clean(text).lower()} "
    if "computer application" in blob or " mca" in blob or " bca" in blob:
        return "Computer Applications / MCA / BCA"
    if any(k in blob for k in ["computer science", "cse", " cs "]):
        return "Computer Science / CSE"
    if any(k in blob for k in ["information technology", " it ", "software"]):
        return "Information Technology / Software"
    if any(k in blob for k in ["data science", "artificial intelligence", " ai ", "machine learning"]):
        return "AI / Data Science"
    return "CSE / IT / Multiple Departments"


def infer_post(text: str) -> str:
    blob = clean(text).lower()
    if "associate professor" in blob:
        return "Associate Professor"
    if "assistant professor" in blob:
        return "Assistant Professor"
    if re.search(r"\bprofessor\b", blob):
        return "Professor"
    if "lecturer" in blob:
        return "Lecturer"
    if "trainer" in blob:
        return "Trainer / Faculty"
    return "Faculty / Teaching Role"


def infer_eligibility(text: str) -> str:
    blob = f" {clean(text).lower()} "
    if any(x in blob for x in ["ph.d", "phd"]):
        return "PhD/NET/SET/M.Tech as per official notice."
    if any(x in blob for x in ["m.tech", "mtech", "m.e", " m e "]):
        return "M.Tech/M.E. CSE/IT; verify NET/SET/PhD requirement."
    if any(x in blob for x in ["mca", "bca"]):
        return "MCA/BCA/Computer Applications background; verify exact eligibility."
    return "Check qualification, subject code, experience and documents in official notice."


EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)


def deobfuscate_email_text(text: Any) -> str:
    """Convert common visible email forms like name [at] domain [dot] in into name@domain.in."""
    value = html.unescape(str(text or ""))
    value = value.replace("＠", "@").replace("(a)", "@")
    value = re.sub(r"\s*(?:\[at\]|\(at\)|\{at\}|\sat\s)\s*", "@", value, flags=re.I)
    value = re.sub(r"\s*(?:\[dot\]|\(dot\)|\{dot\}|\sdot\s)\s*", ".", value, flags=re.I)
    value = re.sub(r"\s+@\s+", "@", value)
    value = re.sub(r"\s+\.\s+", ".", value)
    return value


def is_bad_email(email: str) -> bool:
    email = clean(email).lower().strip(". ,;:()[]{}<>\\\"'")
    if not email or "@" not in email:
        return True
    if BANNED_PUBLIC_TERM_RE.search(email):
        return True
    local, domain = email.rsplit("@", 1)
    if not local or not domain or "." not in domain:
        return True
    bad_local_terms = ["noreply", "no-reply", "donotreply", "wordpress", "comments", "support", "admin"]
    # support/admin are rejected only for source/listing style domains, not for college domains.
    if any(x in local for x in ["noreply", "no-reply", "donotreply", "wordpress", "comments"]):
        return True
    if any(x in domain for x in ["learnwithhemant", "gravatar", "w3.org", "schema.org", "example.com", "sentry.io"]):
        return True
    if domain.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg")):
        return True
    return False


def extract_email_candidates(text: Any) -> List[str]:
    value = deobfuscate_email_text(text)
    found: List[str] = []
    seen = set()
    for match in EMAIL_RE.finditer(value):
        email = clean(match.group(0)).strip(". ,;:()[]{}<>\\\"'")
        email = re.sub(r"\.{2,}", ".", email)
        key = email.lower()
        if is_bad_email(email) or key in seen:
            continue
        seen.add(key)
        found.append(email)
    return found


def extract_email(text: Any) -> str:
    """Pick the best application email from visible page text.

    Preference is given to emails near labels such as 'Email address to apply',
    'How to apply', 'send CV', etc. This fixes cases where the source page shows
    the email in plain text instead of a mailto link.
    """
    value = deobfuscate_email_text(text)
    scored: List[tuple[int, int, str]] = []
    seen = set()
    for match in EMAIL_RE.finditer(value):
        email = clean(match.group(0)).strip(". ,;:()[]{}<>\\\"'")
        key = email.lower()
        if is_bad_email(email) or key in seen:
            continue
        seen.add(key)
        before = value[max(0, match.start() - 180): match.start()].lower()
        after = value[match.end(): match.end() + 80].lower()
        window = before + " " + after
        score = 0
        if "email address to apply" in window or "email id to apply" in window:
            score += 80
        if "apply" in window or "send" in window or "cv" in window or "resume" in window:
            score += 35
        if "email" in window or "e-mail" in window or "mail" in window:
            score += 25
        if "principal" in key or "hr" in key or "career" in key or "careers" in key or "recruit" in key:
            score += 10
        scored.append((score, match.start(), email))
    if not scored:
        return ""
    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored[0][2]


def extract_email_from_soup(soup: BeautifulSoup, visible_text: str = "") -> str:
    """Extract email from mailto links plus full visible article text."""
    pieces: List[str] = []
    try:
        for a in soup.find_all("a", href=True):
            href = clean(a.get("href"))
            text = clean(a.get_text(" ", strip=True))
            if href.lower().startswith("mailto:"):
                pieces.append("Email address to apply: " + href.replace("mailto:", "").split("?")[0])
            if "@" in text or re.search(r"\b(at|dot)\b", text, re.I):
                pieces.append(text)
    except Exception:
        pass
    if visible_text:
        pieces.append(visible_text)
    return extract_email(" | ".join(pieces))


def days_left(date_string: str) -> Optional[int]:
    if not date_string:
        return None
    try:
        date = dt.date.fromisoformat(date_string)
    except ValueError:
        return None
    return (date - dt.datetime.now(IST).date()).days


def normalize_job(raw: Dict[str, Any], source_type: str = "manual_curated") -> Optional[Dict[str, Any]]:
    title_text = clean(raw.get("title") or raw.get("job") or "")
    context_text = clean(" ".join(map(str, raw.values())))
    college = clean_college_name(clean(raw.get("college") or raw.get("College") or raw.get("source_name") or raw.get("Source")), title_text, "College / University")
    post = clean_post_name(clean(raw.get("post") or raw.get("Post") or ""), context_text or title_text)
    department = clean_department_name(clean(raw.get("department") or raw.get("Department") or ""), f"{title_text} {post} {context_text[:800]}")
    eligibility = clean_eligibility_text(clean(raw.get("eligibility") or raw.get("eligible_for") or ""), f"{title_text} {post} {department} {context_text[:1200]}")
    state = public_clean(raw.get("state") or raw.get("State") or "")
    city = public_clean(raw.get("city") or raw.get("City") or "")
    email = clean(raw.get("email") or extract_email(context_text))
    apply_link = safe_public_link(clean(raw.get("apply_link") or raw.get("official_link") or raw.get("link") or raw.get("url")))
    notification_link = safe_public_link(clean(raw.get("notification_link") or raw.get("official_notification") or "")) or apply_link
    if not apply_link and not notification_link and not email:
        return None
    last_raw = clean(raw.get("last_date_iso") or raw.get("last_date") or raw.get("last_date_display") or "")
    parsed = parse_date(last_raw)
    last_iso = parsed.isoformat() if parsed else (last_raw if re.fullmatch(r"\d{4}-\d{2}-\d{2}", last_raw) else "")
    last_display = public_clean(raw.get("last_date_display")) or display_date(last_raw, parsed)
    source_name = public_clean(raw.get("source_name") or raw.get("source") or college or "Source Discovery")
    if not source_name or "source discovery" in source_name.lower():
        source_name = "Source Discovery"
    status = public_clean(raw.get("status") or "Watch")
    if last_iso:
        left = days_left(last_iso)
        if left is not None and left < 0:
            status = "Closed"
    status_label = public_clean(raw.get("status_label") or status)
    if "discovery" in clean(raw.get("source_name")).lower() or source_type == "external_discovery":
        status_label = "Source Verified" if (apply_link or notification_link or email) else "Needs Verification"
    fit_reason = public_clean(raw.get("fit_reason") or raw.get("why"))
    if not fit_reason:
        fit_reason = "Verify eligibility, subject code, experience, documents, salary and deadline from the official college/university notice before applying."
    title = public_clean(raw.get("job") or f"{college} {post} {department}")
    slug = clean(raw.get("slug")) or slugify(f"{college}-{post}-{department}-{dt.datetime.now(IST).year}")
    source_page = clean(raw.get("source_page") or raw.get("source_url") or "")
    if is_external_listing_url(source_page):
        source_page = ""
    public_source = "source_discovery" if source_type == "external_discovery" else public_clean(source_type)
    return {
        "college": college,
        "post": post,
        "department": department,
        "eligibility": eligibility,
        "last_date_iso": last_iso if re.fullmatch(r"\d{4}-\d{2}-\d{2}", last_iso or "") else "",
        "last_date_display": public_clean(last_display),
        "email": email,
        "apply_link": apply_link,
        "notification_link": notification_link,
        "city": city,
        "state": state,
        "address": shorten(raw.get("address") or raw.get("Address") or raw.get("location") or raw.get("Location"), 220),
        "source_page": source_page,
        "verification_status": public_clean(raw.get("verification_status") or raw.get("verification") or ("Official Link Found" if apply_link or notification_link else "Check Official Notice")),
        "status": status,
        "status_label": status_label,
        "status_class": public_clean(raw.get("status_class") or status_class(status)),
        "source": public_source,
        "source_name": source_name,
        "fit_reason": dedupe_sentences(fit_reason, 320),
        "profile_tags": public_clean(raw.get("profile_tags") or ", ".join(x for x in [department, post, state] if x)),
        "job": title,
        "slug": slug,
    }


def load_manual_jobs(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[WARN] Could not read manual faculty jobs: {exc}")
        return []
    raw_jobs = payload.get("jobs") if isinstance(payload, dict) else payload
    if not isinstance(raw_jobs, list):
        return []
    jobs: List[Dict[str, Any]] = []
    for raw in raw_jobs:
        if not isinstance(raw, dict):
            continue
        job = normalize_job(raw, "manual_curated")
        if job:
            jobs.append(job)
    return jobs


def keyword_match(text: str, include: Sequence[str], exclude: Sequence[str]) -> bool:
    blob = clean(text).lower()
    if any(bad and bad in blob for bad in exclude):
        return False
    if include and not any(good and good in blob for good in include):
        return False
    if any(bad in blob for bad in AUTO_EXCLUDE_KEYWORDS):
        return False
    return True


def split_keywords(value: str) -> List[str]:
    value = clean(value).lower()
    if not value:
        return []
    return [x.strip() for x in re.split(r"[|,]", value) if x.strip()]


def domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def is_excluded_domain(url: str) -> bool:
    domain = domain_of(url)
    return any(domain == blocked or domain.endswith("." + blocked) for blocked in JOB_PORTAL_EXCLUDE_DOMAINS)



def is_external_listing_url(url: str) -> bool:
    domain = domain_of(url)
    return any(domain == d or domain.endswith("." + d) for d in EXTERNAL_LISTING_DOMAINS)


def looks_like_faculty_job_text(text: str) -> bool:
    blob = BANNED_PUBLIC_TERM_RE.sub(" ", clean(text).lower())
    if not blob:
        return False
    strong_teaching = any(k in blob for k in ["assistant professor", "associate professor", "professor", "lecturer", "faculty", "teaching staff", "teacher"])
    if any(bad in blob for bad in NON_TEACHING_EXCLUDE_KEYWORDS) and not strong_teaching:
        return False
    if any(bad in blob for bad in ["admit card", "answer key", "syllabus", "question paper", "exam result"]):
        return False
    has_academic = any(k in blob for k in ["college", "university", "institute", "department", "engineering", "polytechnic", "school of", "campus"])
    has_cse_or_general = any(k in blob for k in INFER_CSE_KEYWORDS) or any(k in blob for k in ["science", "engineering", "arts", "commerce", "management", "mathematics", "physics"])
    return strong_teaching and has_academic and has_cse_or_general


def unwrap_search_url(href: str) -> str:
    href = clean(href)
    if not href:
        return ""
    parsed = urlparse(href)
    # DuckDuckGo result links often look like /l/?uddg=https%3A%2F%2Fexample.com
    params = parse_qs(parsed.query)
    if "uddg" in params and params["uddg"]:
        return unquote(params["uddg"][0])
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return ""


def infer_state(text: str, fallback: str = "") -> str:
    blob = clean(text).lower()
    for state in INDIAN_STATES:
        if state.lower() in blob:
            return state
    return clean(fallback)


def infer_college_name(title: str, page_text: str, fallback: str) -> str:
    title = clean(title)
    page_text = clean(page_text)
    # Prefer common "X invites applications" style first.
    combined = f"{title}. {page_text[:800]}"
    patterns = [
        r"([A-Z][A-Za-z0-9&.,'() -]{4,90}?(?:University|College|Institute|School|Academy|Campus))",
        r"(?:at|by)\s+([A-Z][A-Za-z0-9&.,'() -]{4,90})",
    ]
    for pat in patterns:
        match = re.search(pat, combined)
        if match:
            name = clean(match.group(1))
            name = re.sub(r"(?i)\s+(recruitment|jobs|vacancy|notification|wanted).*", "", name).strip(" -|,.")
            if len(name) >= 5:
                return name
    cleaned = re.sub(r"(?i)\b(recruitment|jobs?|vacanc(?:y|ies)|wanted|walk[- ]?in|hiring|apply online|notification|last date|2026|2025)\b.*", "", title).strip(" -|,.")
    if 5 <= len(cleaned) <= 90:
        return cleaned
    return clean(fallback) or "College / University"



def clean_college_name(value: str, title: str = "", fallback: str = "College / University") -> str:
    raw = public_clean(value or title or fallback)
    raw = re.sub(r"(?i)\s*[-–|]*\s*(institution profile|college profile|university profile)\s*[:|-].*$", "", raw).strip(" -–|,.")
    raw = re.sub(r"(?i)\s+(recruitment|jobs?|vacanc(?:y|ies)|wanted|walk[- ]?in|hiring|faculty recruitment|notification|apply online|last date|number of posts|duration of the project|essential).*", "", raw).strip(" -–|,.")
    if len(raw) > 95 or raw.count(" ") > 14:
        candidate = infer_college_name(title or raw, raw, fallback)
        raw = public_clean(candidate)
    raw = re.sub(r"(?i)\b(source|latest faculty posts|sitemap discovery)\b", "", raw).strip(" -–|,.") or fallback
    return shorten(raw, 90)


def clean_post_name(value: str, context: str = "") -> str:
    value = public_clean(value)
    if not value or len(value) > 80 or any(bad.strip() and bad in value.lower() for bad in NON_TEACHING_EXCLUDE_KEYWORDS):
        value = infer_post(context or value)
    value = re.sub(r"(?i)\s+(number of posts|duration|essential|qualification|eligibility).*", "", value).strip(" -–|,.")
    return shorten(value or "Faculty / Teaching Role", 70)


def clean_department_name(value: str, context: str = "") -> str:
    value = public_clean(value)
    if not value or len(value) > 150:
        value = infer_department(context or value)
    value = re.sub(r"(?i)\s+(the candidate|must have|desirable|essential).*", "", value).strip(" -–|,.")
    return shorten(value or "CSE / IT / Multiple Departments", 120)


def clean_eligibility_text(value: str, context: str = "") -> str:
    value = dedupe_sentences(value or infer_eligibility(context), 260)
    return value or "Check qualification, experience and documents in the official notice."


def extract_page_context(url: str, timeout: int = 14, max_bytes: int = 2_000_000) -> tuple[str, str]:
    """Return (page_title, visible_text) for HTML/PDF-like pages. Fails soft."""
    headers = {"User-Agent": "LearnWithHemantFacultyJobsBot/1.1 (+https://learnwithhemant.com/jobs/faculty-jobs/)"}
    try:
        response = requests.get(url, headers=headers, timeout=timeout, stream=True)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        raw = response.raw.read(max_bytes, decode_content=True)
    except Exception:
        return "", ""
    if "application/pdf" in content_type or url.lower().split("?")[0].endswith(".pdf"):
        # Optional PDF extraction. If pdfminer is unavailable or fails, keep the URL/title only.
        try:
            from io import BytesIO
            from pdfminer.high_level import extract_text  # type: ignore
            text = extract_text(BytesIO(raw), maxpages=3) or ""
            return "PDF Notice", clean(text[:6000])
        except Exception:
            return "PDF Notice", ""
    try:
        html_text = raw.decode(response.encoding or "utf-8", errors="ignore")
    except Exception:
        html_text = raw.decode("utf-8", errors="ignore")
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()
    title = clean(soup.title.get_text(" ", strip=True)) if soup.title else ""
    text = clean(soup.get_text(" ", strip=True))
    return title, text[:8000]


def row_query(row: Dict[str, str]) -> str:
    raw = clean(row.get("query") or row.get("source_url"))
    if raw.lower().startswith("search:"):
        return raw.split(":", 1)[1].strip()
    return raw


def build_auto_job_from_text(row: Dict[str, str], title: str, link: str, snippet: str, page_title: str = "", page_text: str = "") -> Optional[Dict[str, Any]]:
    context = clean(" ".join([title, page_title, snippet, page_text[:2500]]))
    include = split_keywords(row.get("include_keywords", "")) or INFER_TEACHING_KEYWORDS
    exclude = split_keywords(row.get("exclude_keywords", ""))
    if not keyword_match(f"{context} {link}", include, exclude):
        return None
    if is_excluded_domain(link):
        return None
    last_raw, parsed = extract_last_date(context)
    state = infer_state(context, row.get("state", ""))
    raw = {
        "college": infer_college_name(title or page_title, page_text, row.get("source_name") or "All India Faculty Source"),
        "title": title or page_title,
        "post": infer_post(context),
        "department": infer_department(context),
        "eligibility": infer_eligibility(context),
        "last_date": last_raw,
        "last_date_iso": parsed.isoformat() if parsed else "",
        "last_date_display": display_date(last_raw, parsed),
        "email": extract_email(page_text) or extract_email(context),
        "apply_link": link,
        "notification_link": link,
        "state": state,
        "city": clean(row.get("city")),
        "status": "Manual Check" if not parsed else "Active",
        "status_label": "Manual Check" if not parsed else "Active",
        "source_name": clean(row.get("source_name")) or "All India Faculty Search",
        "fit_reason": "Auto-discovered from all-India faculty job search/source scanning. Verify official notice, eligibility, email, deadline and apply link before sharing/applying.",
    }
    return normalize_job(raw, "auto_all_india")



def text_from_node(node: Any) -> str:
    try:
        return clean(node.get_text(" ", strip=True))
    except Exception:
        return ""


def extract_label_value_from_text(text: str, labels: Sequence[str], max_chars: int = 240) -> str:
    flat = clean(text)
    if not flat:
        return ""
    for label in labels:
        pattern = re.compile(r"(?i)(?:^|[|•\n\r]|\s)(" + re.escape(label) + r")\s*[:\-–]\s*(.{2," + str(max_chars) + r"})")
        match = pattern.search(flat)
        if match:
            value = clean(match.group(2))
            value = re.split(r"(?i)\s+(?:Name of the|Organization|Department|Qualification|Eligibility|Job Location|College Address|Last Date|Email address to apply|Email Address|Email|E-mail|Apply|Official|Website)\s*[:\-–]", value)[0]
            return clean(value.strip(" |•,;"))[:max_chars]
    return ""


def extract_labeled_values(soup: BeautifulSoup, full_text: str) -> Dict[str, str]:
    labels = {
        "college": ["Name of the College", "College Name", "Organization Name", "Organization", "Hiring Organization", "College", "Institution Name", "Institute Name"],
        "post": ["Post Name", "Designation", "Name of the Post", "Job Title", "Position", "Post"],
        "department": ["Department", "Departments", "Subject", "Specialization", "Disciplines"],
        "eligibility": ["Qualification", "Qualifications", "Eligibility", "Educational Qualification", "Candidate Profile", "Candidate Requirement", "Minimum Qualification"],
        "address": ["College Address", "Organization address", "Organization Address", "Address", "Job Location", "Location", "Venue"],
        "last_date": ["Last Date", "Last Date to Apply", "Apply Before", "Closing Date", "Deadline"],
        "email": ["Email address to apply", "Email Address to Apply", "Email ID to Apply", "Email", "Email Address", "E-mail", "E Mail", "Mail ID", "Apply Email"],
    }
    found = {k: "" for k in labels}
    for tr in soup.find_all("tr"):
        cells = [text_from_node(c) for c in tr.find_all(["th", "td"])]
        cells = [c for c in cells if c]
        if len(cells) >= 2:
            key = cells[0].strip(" :–-")
            val = clean(" ".join(cells[1:]))
            for field, names in labels.items():
                if not found[field] and any(key.lower() == name.lower() or name.lower() in key.lower() for name in names):
                    found[field] = val[:360]
    for field, names in labels.items():
        if not found[field]:
            found[field] = extract_label_value_from_text(full_text, names, 360)
    return found


def choose_external_listing_links(soup: BeautifulSoup, page_url: str) -> tuple[str, str]:
    apply_candidates: List[tuple[int, str, str]] = []
    notice_candidates: List[tuple[int, str, str]] = []
    article = soup.select_one("article") or soup.select_one(".entry-content") or soup.select_one(".post-content") or soup
    for a in article.find_all("a", href=True):
        text = clean(a.get_text(" ", strip=True)).lower()
        href = urljoin(page_url, clean(a.get("href")))
        if not href.startswith(("http://", "https://", "mailto:")):
            continue
        hlow = href.lower()
        if is_external_listing_url(href) or link_domain_blocked(href):
            continue
        if any(x in hlow for x in ["#respond", "wp-login", "share=", "/tag/", "/category/", "youtube", "instagram", "facebook", "linkedin", "telegram", "whatsapp", "aratt"]):
            continue
        if any(x in text for x in ["join", "follow", "community", "telegram", "whatsapp", "instagram", "linkedin", "youtube"]):
            continue
        is_pdf = hlow.split("?")[0].endswith(".pdf")
        is_careerish = any(x in hlow or x in text for x in ["career", "recruit", "vacancy", "job", "apply", "application", "advertisement", "notification", "faculty", "uploads", ".pdf"])
        if not is_pdf and not is_careerish and not any(x in text for x in ["click here", "website", "details"]):
            continue
        score = 0
        if is_pdf:
            score += 60
        if any(x in text for x in ["official", "notification", "advertisement", "details", "notice"]):
            score += 35
        if any(x in text for x in ["apply", "application", "form", "career", "resume", "cv"]):
            score += 40
        if any(x in hlow for x in ["career", "recruit", "faculty", "job", "vacancy", "apply"]):
            score += 20
        if score <= 0:
            score = 5
        if any(x in text for x in ["apply", "application", "form", "career", "resume", "cv"]):
            apply_candidates.append((score, href, text))
        if any(x in text for x in ["notification", "advertisement", "official", "details", "notice", "click here", "website"]) or is_pdf:
            notice_candidates.append((score, href, text))
        if is_careerish:
            apply_candidates.append((score - 3, href, text))
            notice_candidates.append((score - 5, href, text))
    apply = sorted(apply_candidates, reverse=True)[0][1] if apply_candidates else ""
    notice = sorted(notice_candidates, reverse=True)[0][1] if notice_candidates else ""
    return safe_public_link(apply), safe_public_link(notice)


def parse_external_listing_post(url: str, timeout: int = 16) -> Optional[Dict[str, Any]]:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; LearnWithHemantExternalDiscovery/1.0; +https://learnwithhemant.com/jobs/faculty-jobs/)"}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except Exception as exc:
        print(f"[WARN] External listing post fetch failed: {url} | {exc}")
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()
    title = clean((soup.title.get_text(" ", strip=True) if soup.title else "") or "")
    h1 = soup.find("h1")
    visible_title = clean(h1.get_text(" ", strip=True)) if h1 else title
    article = soup.select_one("article") or soup.select_one(".entry-content") or soup.select_one(".post-content") or soup
    full_text = clean(article.get_text(" ", strip=True))
    context = clean(" ".join([visible_title, title, full_text[:9000]]))
    if not looks_like_faculty_job_text(context):
        return None
    labels = extract_labeled_values(article if isinstance(article, BeautifulSoup) else soup, full_text)
    page_email = extract_email(labels.get("email")) or extract_email_from_soup(soup, full_text) or extract_email(context)
    extracted_last_raw, extracted_parsed = extract_last_date(context)
    last_raw = labels.get("last_date") or extracted_last_raw
    parsed = parse_date(last_raw) or extracted_parsed
    apply_link, notification_link = choose_external_listing_links(soup, url)
    official_found = bool(apply_link or notification_link)
    college = clean_college_name(labels.get("college") or infer_college_name(visible_title, full_text, "College / University"), visible_title, "College / University")
    post = clean_post_name(labels.get("post") or infer_post(context), context)
    department = clean_department_name(labels.get("department") or infer_department(context), context)
    eligibility = clean_eligibility_text(labels.get("eligibility") or infer_eligibility(context), context)
    address = labels.get("address") or ""
    state = infer_state(" ".join([address, context]), "All India")
    raw = {
        "college": college,
        "title": visible_title,
        "post": post,
        "department": department,
        "eligibility": eligibility,
        "last_date": last_raw,
        "last_date_iso": parsed.isoformat() if parsed else "",
        "last_date_display": display_date(last_raw, parsed),
        "email": page_email,
        "apply_link": apply_link,
        "notification_link": notification_link,
        "address": address,
        "state": state,
        "city": "",
        "status": "Active" if parsed else "Manual Check",
        "status_label": "Source Verified" if official_found else "Needs Official Verification",
        "source_name": "Source Discovery",
        "source_page": "",
        "verification_status": "Official Link Found" if official_found else "Needs Official Verification",
        "fit_reason": "Vacancy data was discovered from an external listing and restructured into a compact decision format. Verify the official notice, email, deadline, eligibility and application method before applying.",
    }
    return normalize_job(raw, "external_discovery")


def strip_sitemap_loc(value: str) -> str:
    """Normalize sitemap <loc> values, including WordPress CDATA wrapped URLs."""
    value = clean(unquote(value))
    value = re.sub(r"^<!\[CDATA\[", "", value, flags=re.I).strip()
    value = re.sub(r"\]\]>$", "", value, flags=re.I).strip()
    return value


def parse_sitemap_locations(xml_text: str) -> tuple[List[str], List[str]]:
    locs = [strip_sitemap_loc(x) for x in re.findall(r"<loc>\s*(.*?)\s*</loc>", xml_text, flags=re.I | re.S)]
    locs = [x for x in locs if x.startswith(("http://", "https://"))]
    if re.search(r"<\s*sitemapindex", xml_text, flags=re.I):
        return locs, []
    return [], locs


def external_listing_url_priority(url: str) -> int:
    low = url.lower()
    score = 0
    for token in ["faculty", "assistant-professor", "associate-professor", "professor", "lecturer", "engineering", "computer", "cse", "information-technology", "mca", "bca", "wanted"]:
        if token in low:
            score += 2
    for bad in ["admit-card", "answer-key", "syllabus", "result", "question-paper"]:
        if bad in low:
            score -= 10
    return score


def sitemap_number(url: str) -> int:
    matches = re.findall(r"(\d+)(?=\.xml|/|$)", url)
    return int(matches[-1]) if matches else 0



def resolve_external_listing_url(value: str, default_kind: str = "sitemap") -> str:
    value = clean(value)
    domain = "https://www." + "faculty" + "plus.com"
    if value.startswith("external:"):
        if "category" in value or "latest" in value or "home" in value:
            return domain + "/"
        return domain + "/sitemap.xml"
    return value

def scrape_external_listing_sitemap(row: Dict[str, str], timeout: int = 18, max_links: int = 80) -> List[Dict[str, Any]]:
    source_url = resolve_external_listing_url(clean(row.get("source_url")), "sitemap") or ("https://www." + "faculty" + "plus.com/sitemap.xml")
    headers = {"User-Agent": "Mozilla/5.0 (compatible; LearnWithHemantExternalDiscovery/1.0; +https://learnwithhemant.com/jobs/faculty-jobs/)"}
    try:
        resp = requests.get(source_url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except Exception as exc:
        print(f"[WARN] External listing sitemap fetch failed: {exc}")
        return []
    sitemap_locs, url_locs = parse_sitemap_locations(resp.text)
    candidate_urls: List[str] = []

    post_sitemaps = [u for u in sitemap_locs if "post-sitemap" in u.lower()] or sitemap_locs
    # WordPress usually numbers post sitemaps. Higher numbers are normally newer, so scan those first.
    max_sitemaps_to_scan = max(8, min(len(post_sitemaps), max(12, max_links // 8)))
    ordered_sitemaps = sorted(post_sitemaps, key=sitemap_number, reverse=True)[:max_sitemaps_to_scan]

    for sitemap_url in ordered_sitemaps:
        try:
            r = requests.get(sitemap_url, headers=headers, timeout=timeout)
            r.raise_for_status()
            _, urls = parse_sitemap_locations(r.text)
            candidate_urls.extend(urls)
        except Exception as exc:
            print(f"[WARN] External listing child sitemap failed: {sitemap_url} | {exc}")
            continue
        if len(candidate_urls) >= max_links * 15:
            break
    candidate_urls.extend(url_locs)
    seen_urls: List[str] = []
    seen = set()
    for u in sorted(candidate_urls, key=external_listing_url_priority, reverse=True):
        u = clean(u)
        if not u or u in seen or not is_external_listing_url(u):
            continue
        seen.add(u)
        if external_listing_url_priority(u) <= 0:
            continue
        seen_urls.append(u)
        if len(seen_urls) >= max_links * 6:
            break
    jobs: List[Dict[str, Any]] = []
    for u in seen_urls:
        job = parse_external_listing_post(u)
        if job:
            jobs.append(job)
        if len(jobs) >= max_links:
            break
    print(f"[INFO] External listing sitemap discovery: scanned {len(ordered_sitemaps)} child sitemaps, extracted {len(jobs)} structured rows")
    return jobs


def external_category_page_urls(source_url: str, max_links: int) -> List[str]:
    base = source_url.rstrip("/") + "/"
    pages = [base]
    page_count = max(2, min(10, max_links // 15 + 1))
    for i in range(2, page_count + 1):
        pages.append(urljoin(base, f"page/{i}/"))
    return pages


def scrape_external_listing_category(row: Dict[str, str], timeout: int = 18, max_links: int = 80) -> List[Dict[str, Any]]:
    source_url = resolve_external_listing_url(clean(row.get("source_url")), "category")
    if not source_url:
        return []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; LearnWithHemantExternalDiscovery/1.0; +https://learnwithhemant.com/jobs/faculty-jobs/)"}
    candidates: List[str] = []
    scanned_pages = 0
    for page_url in external_category_page_urls(source_url, max_links):
        try:
            resp = requests.get(page_url, headers=headers, timeout=timeout)
            resp.raise_for_status()
        except Exception as exc:
            print(f"[WARN] External listing category page fetch failed: {page_url} | {exc}")
            continue
        scanned_pages += 1
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = urljoin(page_url, clean(a.get("href")))
            text = clean(a.get_text(" ", strip=True))
            if not is_external_listing_url(href):
                continue
            # Category/listing link text is often short; use URL priority instead of requiring full job text here.
            if external_listing_url_priority(href + " " + text) > 0:
                candidates.append(href)
    seen: List[str] = []
    for href in candidates:
        href = href.split("#")[0]
        if href not in seen:
            seen.append(href)
    jobs: List[Dict[str, Any]] = []
    for href in seen[: max_links * 3]:
        job = parse_external_listing_post(href)
        if job:
            jobs.append(job)
        if len(jobs) >= max_links:
            break
    print(f"[INFO] External listing category discovery: scanned {scanned_pages} listing pages, extracted {len(jobs)} structured rows")
    return jobs

def scrape_search_query(row: Dict[str, str], timeout: int = 18, max_links: int = 12) -> List[Dict[str, Any]]:
    """Discover faculty vacancy URLs through DuckDuckGo HTML search, then normalize candidate pages.

    This is intentionally conservative: it avoids External listing and marks rows as Manual Check/Active,
    because search discovery can find duplicates, stale pages, PDFs and pages needing human verification.
    """
    query = row_query(row)
    source_name = clean(row.get("source_name")) or query[:60] or "All India Search"
    if not query:
        return []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; LearnWithHemantFacultyJobsBot/1.1; +https://learnwithhemant.com/jobs/faculty-jobs/)"}
    search_url = "https://duckduckgo.com/html/?q=" + quote_plus(query)
    try:
        response = requests.get(search_url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except Exception as exc:
        print(f"[WARN] Search fetch failed for {source_name}: {exc}")
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    candidates: List[tuple[str, str, str]] = []
    for result in soup.select(".result"):
        a = result.select_one("a.result__a") or result.find("a", href=True)
        if not a:
            continue
        title = clean(a.get_text(" ", strip=True))
        link = unwrap_search_url(a.get("href", ""))
        snippet_el = result.select_one(".result__snippet")
        snippet = clean(snippet_el.get_text(" ", strip=True)) if snippet_el else ""
        if not title or not link or not link.startswith(("http://", "https://")):
            continue
        candidates.append((title, link, snippet))
    # Fallback for simple pages/changed markup.
    if not candidates:
        for a in soup.find_all("a", href=True):
            title = clean(a.get_text(" ", strip=True))
            link = unwrap_search_url(a.get("href", ""))
            if title and link.startswith(("http://", "https://")):
                candidates.append((title, link, ""))
    jobs: List[Dict[str, Any]] = []
    seen = set()
    include = split_keywords(row.get("include_keywords", "")) or INFER_TEACHING_KEYWORDS
    exclude = split_keywords(row.get("exclude_keywords", ""))
    for title, link, snippet in candidates:
        key = link.lower().split("#")[0]
        if key in seen or is_excluded_domain(link):
            continue
        seen.add(key)
        if not keyword_match(f"{title} {snippet} {link}", include, exclude):
            continue
        page_title, page_text = extract_page_context(link)
        job = build_auto_job_from_text(row, title, link, snippet, page_title, page_text)
        if job:
            jobs.append(job)
        if len(jobs) >= max_links:
            break
    print(f"[INFO] {source_name}: discovered {len(jobs)} possible faculty jobs")
    return jobs


def scrape_source(row: Dict[str, str], timeout: int = 18, max_links: int = 15) -> List[Dict[str, Any]]:
    url = clean(row.get("source_url"))
    source_name = clean(row.get("source_name")) or url
    if not url:
        return []
    include = split_keywords(row.get("include_keywords", "")) or INFER_TEACHING_KEYWORDS
    exclude = split_keywords(row.get("exclude_keywords", ""))
    headers = {"User-Agent": "LearnWithHemantFacultyJobsBot/1.0 (+https://learnwithhemant.com/jobs/faculty-jobs/)"}
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except Exception as exc:
        print(f"[WARN] Source fetch failed for {source_name}: {exc}")
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    jobs: List[Dict[str, Any]] = []
    seen = set()
    page_text = soup.get_text(" ", strip=True)
    for a in soup.find_all("a", href=True):
        text = clean(a.get_text(" ", strip=True))
        href = clean(a.get("href"))
        if not text or len(text) < 8:
            continue
        combined = f"{text} {href}"
        if not keyword_match(combined, include, exclude):
            continue
        link = urljoin(url, href)
        if is_excluded_domain(link):
            continue
        key = (text.lower(), link.lower())
        if key in seen:
            continue
        seen.add(key)
        page_title, detail_text = extract_page_context(link)
        context = clean(" ".join([text, page_title, detail_text[:2500], page_text[:1200]]))
        last_raw, parsed = extract_last_date(context)
        raw = {
            "college": source_name,
            "title": text,
            "post": infer_post(text),
            "department": infer_department(text),
            "eligibility": infer_eligibility(context),
            "last_date": last_raw,
            "last_date_iso": parsed.isoformat() if parsed else "",
            "last_date_display": display_date(last_raw, parsed),
            "email": extract_email(detail_text) or extract_email(page_text) or extract_email(context),
            "apply_link": link,
            "notification_link": link,
            "state": clean(row.get("state")),
            "city": clean(row.get("city")),
            "status": "Manual Check" if not parsed else "Active",
            "status_label": "Manual Check" if not parsed else "Active",
            "source_name": source_name,
            "fit_reason": "Auto-found from an enabled official source. Manually verify the PDF/notice before applying or sharing.",
        }
        job = normalize_job(raw, "auto_source")
        if job:
            jobs.append(job)
        if len(jobs) >= max_links:
            break
    print(f"[INFO] {source_name}: found {len(jobs)} possible faculty notices")
    return jobs


def load_sources(path: Path, max_sources: int) -> List[Dict[str, str]]:
    if max_sources <= 0:
        return []
    if not path.exists():
        return []
    rows: List[Dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if not parse_bool(row.get("enabled", "")):
                continue
            rows.append({k: v for k, v in row.items() if k})
            if len(rows) >= max_sources:
                break
    return rows


def merge_jobs(manual: List[Dict[str, Any]], auto: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen = set()

    def add(job: Dict[str, Any]) -> None:
        unique_value = clean(job.get("apply_link") or job.get("notification_link") or job.get("email") or job.get("slug"))
        key = (clean(job.get("college")).lower(), clean(job.get("post")).lower(), clean(job.get("department")).lower(), unique_value.lower())
        if not key[3] or key in seen:
            return
        seen.add(key)
        # Ensure slug uniqueness.
        base_slug = slugify(clean(job.get("slug")) or f"{job.get('college')} {job.get('post')} {job.get('department')}")
        slug = base_slug
        i = 2
        existing_slugs = {clean(j.get("slug")) for j in merged}
        while slug in existing_slugs:
            slug = f"{base_slug}-{i}"
            i += 1
        job["slug"] = slug
        merged.append(job)

    for job in manual:
        add(dict(job))

    priority = {"Good Match": 0, "Active": 0, "Manual Check": 1, "Watch": 2, "Closed": 9, "Avoid": 9}
    auto_sorted = sorted(auto, key=lambda j: (priority.get(clean(j.get("status")), 5), j.get("last_date_iso") or "9999-12-31"))
    for job in auto_sorted:
        add(dict(job))
        if len(merged) >= limit:
            break
    return merged[:limit]


def esc(value: Any) -> str:
    return html.escape(public_clean(value), quote=True)


def url_for(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    return BASE_URL + path


def page_head(title: str, description: str, canonical_path: str, extra_schema: str = "") -> str:
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta name="msvalidate.01" content="4F051335E3D7ED544E20B8292B4E66BD"/>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}"/>
<link rel="canonical" href="{url_for(canonical_path)}"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&amp;display=swap" rel="stylesheet"/>
<link href="/style.css" rel="stylesheet"/>
<link href="/brand-logo.png" rel="icon" type="image/png"/>
<link href="/brand-logo.png" rel="apple-touch-icon"/>
{extra_schema}
</head>'''


def site_header(active: str = "faculty") -> str:
    return '''<body class="home-v2-body jobs-dashboard-body faculty-jobs-body">
<header class="site-header home-v2-header">
<div class="container nav home-v2-nav">
<a class="brand home-v2-brand" href="/home/">
<img alt="Learn with Hemant logo" class="brand-logo" src="/brand-logo.png"/>
<div><span>Learn with Hemant</span><small>Build • Deploy • Grow</small></div>
</a>
<nav aria-label="Main Navigation" class="nav-links home-v2-links">
<a href="/about/">Mentor</a>
<a href="/courses/web-development/">Courses</a>
<a href="/projects/">Projects</a>
<a href="/guest-lecture/">Guest Lecture</a>
<a href="/tool/">Tool</a>
<a class="active-nav-link" href="/jobs/">Jobs</a>
</nav>
<a class="nav-cta home-v2-cta" href="/apply/">Apply Now <span>→</span></a>
<button aria-controls="mobileSiteMenu" aria-expanded="false" aria-label="Open menu" class="mobile-menu-toggle" type="button"><span></span><span></span><span></span></button>
</div>
</header>
<div class="mobile-menu-backdrop" data-mobile-menu-close=""></div>
<aside aria-hidden="true" class="mobile-site-menu" id="mobileSiteMenu">
<div class="mobile-menu-head"><a class="mobile-menu-brand" href="/home/"><img alt="Learn with Hemant logo" src="/brand-logo.png"/></a><button aria-label="Close menu" class="mobile-menu-close" data-mobile-menu-close="" type="button">×</button></div>
<nav aria-label="Mobile navigation" class="mobile-menu-links">
<a href="/home/">Home</a><a href="/about/">Mentor</a><a href="/courses/web-development/">Courses</a><a href="/projects/">Projects</a><a href="/guest-lecture/">Guest Lecture</a><a href="/tool/">Tool</a><a href="/jobs/">Govt Jobs</a><a href="/jobs/faculty-jobs/">Faculty Jobs</a><a href="/apply/">Apply Now</a><a href="https://wa.me/918197565002?text=Hi%20Hemant%2C%20I%20want%20faculty%20job%20updates." rel="noopener" target="_blank">WhatsApp Updates</a>
</nav>
</aside>'''


def site_footer() -> str:
    return '''<footer class="site-footer v2-footer">
<div class="container v2-footer-grid">
<div class="v2-footer-brand"><div class="brand home-v2-brand footer-brand-row"><img class="brand-logo" src="/brand-logo.png" alt="Learn with Hemant logo"/><div><span>Learn with Hemant</span><small>Helping beginners become confident developers through practical training.</small></div></div></div>
<div><h3>Quick Links</h3><div class="v2-footer-links"><a href="/about/">Mentor</a><a href="/roadmap/">Roadmap</a><a href="/courses/web-development/">Courses</a><a href="/projects/">Projects</a><a href="/guest-lecture/">Guest Lecture</a><a href="/apply/">Free Demo</a></div></div>
<div><h3>Jobs</h3><div class="v2-footer-links"><a href="/jobs/">CSE Govt Jobs</a><a href="/jobs/faculty-jobs/">Faculty Jobs</a><a href="/jobs/faculty-jobs/cse/">CSE Faculty Jobs</a><a href="/jobs/faculty-jobs/rajasthan/">Rajasthan Faculty Jobs</a></div></div>
<div><h3>Connect</h3><div class="v2-footer-links"><a href="https://wa.me/918197565002?text=Hi%20Hemant%2C%20I%20want%20faculty%20job%20updates." target="_blank" rel="noopener">WhatsApp Updates</a><a href="mailto:learnwithhemantsingh@gmail.com">learnwithhemantsingh@gmail.com</a><span>India (IST)</span><span>Mon - Sat: 9:00 AM - 8:00 PM</span></div></div>
</div>
<div class="container v2-footer-bottom"><span>© 2026 Learn with Hemant. All rights reserved.</span><div class="v2-footer-bottom-links"><a href="/privacy.html">Privacy Policy</a><a href="/terms.html">Terms of Use</a><a href="/refund.html">Refund Policy</a><a href="/contact/">Contact</a></div></div>
</footer>
<script>
(function(){const toggle=document.querySelector('.mobile-menu-toggle');const menu=document.getElementById('mobileSiteMenu');const backdrop=document.querySelector('.mobile-menu-backdrop');const closeItems=document.querySelectorAll('[data-mobile-menu-close]');const links=document.querySelectorAll('.mobile-menu-links a');if(!toggle||!menu||!backdrop)return;function openMenu(){document.body.classList.add('mobile-menu-open');toggle.setAttribute('aria-expanded','true');menu.setAttribute('aria-hidden','false')}function closeMenu(){document.body.classList.remove('mobile-menu-open');toggle.setAttribute('aria-expanded','false');menu.setAttribute('aria-hidden','true')}toggle.addEventListener('click',openMenu);closeItems.forEach(item=>item.addEventListener('click',closeMenu));links.forEach(link=>link.addEventListener('click',closeMenu));document.addEventListener('keydown',function(event){if(event.key==='Escape')closeMenu()})})();
(function(){const search=document.getElementById('facultyJobsSearch');const chips=Array.from(document.querySelectorAll('.jobs-filter-chips button'));const rows=Array.from(document.querySelectorAll('#facultyJobsTableBody tr'));let active='all';function left(date){if(!date)return null;const today=new Date();today.setHours(0,0,0,0);const d=new Date(date+'T00:00:00');if(Number.isNaN(d.getTime()))return null;return Math.ceil((d-today)/(1000*60*60*24));}function match(row){const f=active.toLowerCase();if(f==='all'||f==='all india')return true;const txt=row.textContent.toLowerCase();const tags=(row.dataset.tags||'').toLowerCase();const st=(row.dataset.state||'').toLowerCase();const status=(row.dataset.status||'').toLowerCase();const l=left(row.dataset.last||'');if(f==='closing soon')return l!==null&&l>=0&&l<=7;if(f==='active')return !status.includes('closed');return txt.includes(f)||tags.includes(f)||st.includes(f)||status.includes(f);}function apply(){const q=(search&&search.value?search.value:'').trim().toLowerCase();rows.forEach(row=>{const ok=(!q||row.textContent.toLowerCase().includes(q))&&match(row);row.hidden=!ok;});}chips.forEach(chip=>chip.addEventListener('click',()=>{chips.forEach(c=>c.classList.remove('active'));chip.classList.add('active');active=chip.dataset.filter||'all';apply();}));if(search)search.addEventListener('input',apply);apply();})();
</script>
</body>
</html>'''


def summary_counts(jobs: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    total = len(jobs)
    cse = sum(1 for j in jobs if any(k in f"{j.get('department')} {j.get('profile_tags')}".lower() for k in ["cse", "computer", "it", "mca", "bca", "data science", "ai"]))
    soon = 0
    active = 0
    for j in jobs:
        if clean(j.get("status")).lower() != "closed":
            active += 1
        left = days_left(clean(j.get("last_date_iso")))
        if left is not None and 0 <= left <= 7:
            soon += 1
    return {"total": total, "cse": cse, "soon": soon, "active": active}


def table_rows(jobs: Sequence[Dict[str, Any]]) -> str:
    rows = []
    for job in jobs:
        slug = clean(job.get("slug"))
        detail_url = f"/jobs/faculty-jobs/{slug}/" if slug else "/jobs/faculty-jobs/"
        college_name = shorten(job.get("college"), 72)
        post_dept = shorten(f"{job.get('post')} • {job.get('department')}", 90)
        eligibility = shorten(job.get("eligibility"), 135)
        college_html = f'<a class="faculty-job-title-link" href="{esc(detail_url)}"><strong>{esc(college_name)}</strong></a>'
        email_value = clean(job.get("email"))
        email_html = f'<a href="mailto:{esc(email_value)}">{esc(email_value)}</a>' if email_value else '<span class="muted-link-text">Check notice</span>'
        apply = safe_public_link(clean(job.get("apply_link")))
        notice = safe_public_link(clean(job.get("notification_link")))
        apply_html = f'<a class="official-link" href="{esc(apply)}" target="_blank" rel="noopener">Apply</a>' if apply else '<span class="muted-link-text">Check notice</span>'
        notice_html = f'<a class="official-link notice-link" href="{esc(notice)}" target="_blank" rel="noopener">Notice</a>' if notice else '<span class="muted-link-text">Check notice</span>'
        row = (
            f'<tr data-state="{esc(job.get("state"))}" data-tags="{esc(job.get("profile_tags"))}" data-status="{esc(job.get("status"))}" data-last="{esc(job.get("last_date_iso"))}">'
            f'<td data-label="College">{college_html}<span>{esc(post_dept)}</span></td>'
            f'<td data-label="Eligibility">{esc(eligibility)}</td>'
            f'<td data-label="Last Date"><strong>{esc(job.get("last_date_display"))}</strong></td>'
            f'<td data-label="Email">{email_html}</td>'
            f'<td data-label="Apply Link">{apply_html}</td>'
            f'<td data-label="Official Notice">{notice_html}</td>'
            '</tr>'
        )
        rows.append(row)
    if not rows:
        return '<tr><td colspan="6">No faculty jobs available right now. Add rows in manual-faculty-jobs.json or enable official sources.</td></tr>'
    return "\n".join(rows)


def dashboard_page(jobs: Sequence[Dict[str, Any]], payload: Dict[str, Any], title: str, description: str, canonical_path: str, heading: str, subheading: str, active_filter: str = "all") -> str:
    counts = summary_counts(jobs)
    chips = [
        ("all", "All"), ("All India", "All India"), ("CSE", "CSE/IT"), ("Assistant Professor", "Assistant Professor"),
        ("Lecturer", "Lecturer"), ("Rajasthan", "Rajasthan"), ("Closing Soon", "Closing Soon"), ("Active", "Active")
    ]
    chip_html = "".join(f'<button class="{"active" if key == active_filter else ""}" data-filter="{esc(key)}" type="button">{esc(label)}</button>' for key, label in chips)
    return page_head(title, description, canonical_path) + site_header() + f'''
<main class="jobs-dashboard-main faculty-jobs-main">
<section class="jobs-summary-section">
<div class="container faculty-jobs-topbar"><a href="/jobs/">← Govt Jobs</a><a href="/jobs/faculty-jobs/all-india/">All India</a><a href="/jobs/faculty-jobs/cse/">CSE Faculty</a><a href="/jobs/faculty-jobs/rajasthan/">Rajasthan</a><a href="/jobs/faculty-jobs/assistant-professor/">Assistant Professor</a></div>
<div class="container jobs-summary-grid">
<article class="jobs-summary-card"><strong>{counts['total']}</strong><span>Total Faculty Rows</span></article>
<article class="jobs-summary-card good"><strong>{counts['cse']}</strong><span>CSE/IT Focus</span></article>
<article class="jobs-summary-card soon"><strong>{counts['soon']}</strong><span>Closing Soon</span></article>
<article class="jobs-summary-card teach"><strong>{counts['active']}</strong><span>Active/Watch</span></article>
</div>
</section>
<section class="jobs-table-section">
<div class="container"><div class="jobs-panel">
<div class="jobs-panel-head"><div><span class="jobs-mini-eyebrow">{esc(payload.get('updated_label') or 'Updated')}</span><h1>{esc(heading)}</h1><p>{esc(subheading)}</p></div><a class="jobs-suggest-btn" href="https://wa.me/918197565002?text=Hi%20Hemant%2C%20I%20found%20a%20faculty%20job%20to%20add." target="_blank" rel="noopener">Suggest Faculty Job</a></div>
<div aria-label="Faculty job filters" class="jobs-controls"><div class="jobs-search-wrap"><input id="facultyJobsSearch" aria-label="Search faculty jobs" placeholder="Search college, eligibility, state, department..." type="search"/></div><div class="jobs-filter-chips" role="group">{chip_html}</div></div>
<div class="jobs-table-wrap"><table class="jobs-table faculty-jobs-table"><thead><tr><th>College Name</th><th>Eligibility</th><th>Last Date</th><th>Email</th><th>Apply Link</th><th>Official Notice</th></tr></thead><tbody id="facultyJobsTableBody">{table_rows(jobs)}</tbody></table></div>
<p class="jobs-table-note">This page is generated from verified manual rows plus optional official-source scanning. Always verify the official PDF/notice before applying or emailing your CV.</p>
</div></div>
</section>
<section class="faculty-seo-section"><div class="container faculty-seo-card"><h2>Why this faculty jobs page is different</h2><p>Instead of long copied job posts, this page keeps teaching vacancies in a quick decision format: college name, eligibility, last date, email, apply link and official notice. Separate detail and category URLs are generated automatically for search visibility.</p></div></section>
</main>
''' + site_footer()



def stable_order(items: Sequence[str], key: str) -> List[str]:
    seed = clean(key) or "faculty-job"
    return sorted(list(items), key=lambda item: hashlib.sha256((seed + "|" + item).encode("utf-8")).hexdigest())


def faculty_generated_content(job: Dict[str, Any]) -> str:
    college = clean_college_name(job.get("college"), fallback="The college/university")
    post = clean_post_name(job.get("post"), f"{job.get('job')} {job.get('department')}")
    dept = clean_department_name(job.get("department"), f"{job.get('job')} {job.get('eligibility')}")
    state = public_clean(job.get("state")) or "India"
    city = public_clean(job.get("city"))
    address = shorten(job.get("address"), 180)
    last_date = public_clean(job.get("last_date_display")) or "the official deadline"
    place_items = []
    for x in [city, state]:
        if x and x.lower() not in {p.lower() for p in place_items}:
            place_items.append(x)
    place = public_clean(", ".join(place_items)) or state
    article = "an" if post[:1].lower() in {"a", "e", "i", "o", "u"} else "a"
    requirements = stable_order([
        f"Relevant academic qualification for {dept}, such as M.Tech/M.E./MCA/PhD/NET/SET wherever required by the institution.",
        "Ability to teach theory subjects, conduct lab sessions and guide students in practical assignments.",
        "Comfort with syllabus planning, assessment work, mentoring and basic academic documentation.",
        "Good communication skills for classroom teaching, doubt solving and student project guidance.",
        "Readiness to follow university, AICTE/UGC or institution-specific qualification rules mentioned in the notice.",
        "Updated subject knowledge in programming, databases, web development, AI/Data Science or related computer-science areas.",
    ], clean(job.get("slug")))[:4]
    responsibilities = stable_order([
        f"Handle classes and academic activities for {dept} students.",
        "Prepare lectures, practical sessions, assignments and internal assessment material.",
        "Guide students for projects, internships, placement preparation and technical skill building.",
        "Support departmental work such as labs, records, attendance, examination duties and mentoring.",
        "Coordinate with the department for curriculum delivery, workshops, guest sessions and student outcomes.",
    ], clean(job.get("slug")) + "resp")[:4]
    req_html = "".join(f"<li>{esc(x)}</li>" for x in requirements)
    resp_html = "".join(f"<li>{esc(x)}</li>" for x in responsibilities)
    address_html = f"<p><strong>Listed location:</strong> {esc(address)}</p>" if address else ""
    return f'''
<section class="faculty-auto-content">
<h2>About this opening</h2>
<p>{esc(college)} is listed for {esc(post)} hiring in {esc(dept)}. This page keeps the vacancy in a quick decision format with eligibility, last date, email, apply link and notice details.</p>
<p>This opportunity may be relevant for candidates looking for teaching roles in {esc(place)}. The displayed last date is {esc(last_date)}; candidates should confirm the deadline from the official notice before applying.</p>
{address_html}
<h2>Candidate requirements</h2>
<p>Review these common requirements along with the official notification:</p>
<ul>{req_html}</ul>
<h2>Expected job role</h2>
<p>The exact workload can vary by institution, but {article} {esc(post)} role in {esc(dept)} generally includes:</p>
<ul>{resp_html}</ul>
<h2>How to apply</h2>
<p>Prepare an updated CV, qualification certificates, experience documents and research/publication details if applicable. Apply through the official apply link or email only after verifying the vacancy details.</p>
</section>'''



def has_external_official_link(job: Dict[str, Any]) -> bool:
    for field in ["apply_link", "notification_link"]:
        link = clean(job.get(field))
        if safe_public_link(link):
            return True
    return False

def jobposting_schema(job: Dict[str, Any], canonical_path: str) -> str:
    today = dt.datetime.now(IST).date().isoformat()
    valid = clean(job.get("last_date_iso")) or dt.datetime.now(IST).date().replace(year=dt.datetime.now(IST).year + 1).isoformat()
    data = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": clean(f"{job.get('post')} - {job.get('department')}") or "Faculty Job",
        "description": clean(f"{job.get('college')} is listed for {job.get('post')} in {job.get('department')}. Eligibility: {job.get('eligibility')}. Verify details from the official notice before applying."),
        "datePosted": today,
        "validThrough": valid + "T23:59:00+05:30",
        "employmentType": "FULL_TIME",
        "hiringOrganization": {"@type": "Organization", "name": clean(job.get("college")) or "College / University", "sameAs": clean(job.get("apply_link")) or BASE_URL},
        "jobLocation": {"@type": "Place", "address": {"@type": "PostalAddress", "addressLocality": clean(job.get("city")) or clean(job.get("state")) or "India", "addressRegion": clean(job.get("state")) or "India", "addressCountry": "IN"}},
        "url": url_for(canonical_path),
    }
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False) + '</script>'



def is_actual_job_posting(job: Dict[str, Any]) -> bool:
    """Only add JobPosting schema when the row looks like a real vacancy, not a generic watchlist/source row."""
    college = clean(job.get("college")).lower()
    generic_markers = ["state universities", "private engineering colleges", "universities / colleges", "source watch"]
    if any(marker in college for marker in generic_markers):
        return False
    if clean(job.get("source")) in {"external_discovery", "source_discovery"} and not has_external_official_link(job):
        return False
    if clean(job.get("last_date_iso")) or clean(job.get("email")) or has_external_official_link(job):
        return True
    return clean(job.get("source")) == "auto_source" and clean(job.get("status")).lower() not in {"watch", "closed"}


def detail_page(job: Dict[str, Any]) -> str:
    slug = clean(job.get("slug"))
    canonical = f"/jobs/faculty-jobs/{slug}/"
    college = clean_college_name(job.get("college"))
    post = clean_post_name(job.get("post"), f"{job.get('job')} {job.get('department')}")
    dept = clean_department_name(job.get("department"), f"{job.get('job')} {job.get('eligibility')}")
    title = f"{college} {post} {dept} | Faculty Job"
    desc = f"Check {college} {post} details: eligibility, last date, email, official notice and apply link."
    schema = jobposting_schema(job, canonical) if is_actual_job_posting(job) else ""
    email_value = clean(job.get("email"))
    email_html = f'<a href="mailto:{esc(email_value)}">{esc(email_value)}</a>' if email_value else 'Check official notice'
    apply = safe_public_link(clean(job.get("apply_link")))
    notice = safe_public_link(clean(job.get("notification_link")))
    actions = []
    if notice:
        actions.append(f'<a class="official-link notice-link" href="{esc(notice)}" target="_blank" rel="noopener">Open Official Notice</a>')
    if apply:
        actions.append(f'<a class="official-link" href="{esc(apply)}" target="_blank" rel="noopener">Apply / Career Page</a>')
    if email_value:
        actions.append(f'<a class="official-link" href="mailto:{esc(email_value)}">Email CV</a>')
    actions_html = "".join(actions) if actions else '<span class="muted-link-text">Check the official notice before applying.</span>'
    return page_head(title, desc, canonical, schema) + site_header() + f'''
<main class="jobs-dashboard-main faculty-jobs-main">
<section class="jobs-table-section"><div class="container"><article class="jobs-panel faculty-detail-card">
<a class="faculty-back-link" href="/jobs/faculty-jobs/">← Back to Faculty Jobs</a>
<span class="jobs-mini-eyebrow">{esc(job.get('status_label'))}</span>
<h1>{esc(college)} {esc(post)}</h1>
<p class="faculty-detail-subtitle">{esc(dept)} • {esc(job.get('city'))} {esc(job.get('state'))}</p>
<div class="faculty-detail-grid">
<div><span>College Name</span><strong>{esc(college)}</strong></div>
<div><span>Post</span><strong>{esc(post)}</strong></div>
<div><span>Department</span><strong>{esc(dept)}</strong></div>
<div><span>Last Date</span><strong>{esc(job.get('last_date_display'))}</strong></div>
<div><span>Email</span><strong>{email_html}</strong></div>
<div><span>Verification</span><strong>{esc(job.get('verification_status'))}</strong></div>
</div>
<h2>Eligibility</h2><p>{esc(job.get('eligibility'))}</p>
<h2>Important note</h2><p>{esc(job.get('fit_reason'))}</p>
<div class="faculty-detail-actions">{actions_html}</div>
{faculty_generated_content(job)}
<div class="faculty-related-links"><a href="/jobs/faculty-jobs/cse/">CSE Faculty Jobs</a><a href="/jobs/faculty-jobs/assistant-professor/">Assistant Professor Jobs</a><a href="/jobs/faculty-jobs/rajasthan/">Rajasthan Faculty Jobs</a></div>
</article></div></section>
</main>
''' + site_footer()



def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def filter_jobs(jobs: Sequence[Dict[str, Any]], kind: str) -> List[Dict[str, Any]]:
    kind_l = kind.lower()
    if kind_l == "all-india":
        return list(jobs)
    if kind_l == "cse":
        return [j for j in jobs if any(k in f"{j.get('department')} {j.get('profile_tags')}".lower() for k in ["cse", "computer", "it", "mca", "bca", "data science", "ai"])]
    if kind_l == "rajasthan":
        return [j for j in jobs if "rajasthan" in f"{j.get('state')} {j.get('city')} {j.get('college')} {j.get('profile_tags')}".lower()]
    if kind_l == "assistant-professor":
        return [j for j in jobs if "assistant professor" in f"{j.get('post')} {j.get('job')}".lower()]
    if kind_l == "closing-soon":
        return [j for j in jobs if (days_left(clean(j.get('last_date_iso'))) is not None and 0 <= days_left(clean(j.get('last_date_iso'))) <= 7)]
    return list(jobs)


def generate_pages(payload: Dict[str, Any]) -> List[str]:
    jobs = payload.get("jobs") or []
    generated_paths: List[str] = []
    write_file(FACULTY_ROOT / "index.html", dashboard_page(
        jobs, payload,
        "Faculty Jobs for CSE/IT | College Teaching Vacancies | Learn with Hemant",
        "Find faculty jobs for CSE, IT, MCA and Computer Science teaching roles. Check college name, eligibility, last date, email, official apply link and official notice.",
        "/jobs/faculty-jobs/",
        "Faculty Jobs for CSE / IT",
        "Automated teaching-job dashboard with clean eligibility, last date, email and official apply links.",
    ))
    generated_paths.append("/jobs/faculty-jobs/")
    categories = {
        "all-india": ("All India Faculty Jobs", "All-India teaching vacancies discovered from enabled official pages and search queries.", "All India Faculty Jobs | CSE / IT Teaching Vacancies"),
        "cse": ("CSE / IT Faculty Jobs", "CSE, IT, MCA, BCA, AI and Data Science focused teaching jobs.", "CSE Faculty Jobs | Computer Science Teaching Vacancies"),
        "rajasthan": ("Rajasthan Faculty Jobs", "Rajasthan college and university teaching jobs for CSE/IT candidates.", "Rajasthan Faculty Jobs | Assistant Professor / Lecturer"),
        "assistant-professor": ("Assistant Professor Jobs", "Assistant Professor openings in CSE/IT and related teaching departments.", "Assistant Professor Jobs for CSE/IT"),
        "closing-soon": ("Faculty Jobs Closing Soon", "Teaching vacancies whose last date is within the next seven days.", "Faculty Jobs Closing Soon"),
    }
    for slug, (heading, subheading, title) in categories.items():
        filtered = filter_jobs(jobs, slug)
        write_file(FACULTY_ROOT / slug / "index.html", dashboard_page(
            filtered, payload, f"{title} | Learn with Hemant", subheading,
            f"/jobs/faculty-jobs/{slug}/", heading, subheading,
            "All India" if slug == "all-india" else "Rajasthan" if slug == "rajasthan" else "Assistant Professor" if slug == "assistant-professor" else "CSE" if slug == "cse" else "Closing Soon"
        ))
        generated_paths.append(f"/jobs/faculty-jobs/{slug}/")
    for job in jobs:
        slug = clean(job.get("slug"))
        if not slug:
            continue
        write_file(FACULTY_ROOT / slug / "index.html", detail_page(job))
        generated_paths.append(f"/jobs/faculty-jobs/{slug}/")
    return generated_paths


def sanitize_public_payload(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k in {"external_listing_url"}:
                continue
            if k in {"source_page"} and is_external_listing_url(clean(v)):
                out[k] = ""
            elif k in {"apply_link", "notification_link"}:
                out[k] = safe_public_link(clean(v))
            else:
                out[k] = sanitize_public_payload(v)
        return out
    if isinstance(value, list):
        return [sanitize_public_payload(v) for v in value]
    if isinstance(value, str):
        return public_clean(value)
    return value


def write_json(payload: Dict[str, Any], out_json: Path) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    payload = sanitize_public_payload(payload)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Updated {out_json} with {len(payload.get('jobs') or [])} faculty jobs")




def cleanup_generated_dirs(valid_paths: Sequence[str]) -> None:
    """Remove stale generated faculty detail/category directories when slugs change."""
    protected = {"all-india", "cse", "rajasthan", "assistant-professor", "closing-soon"}
    valid_slugs = set()
    for path in valid_paths:
        parts = [p for p in path.strip("/").split("/") if p]
        if len(parts) >= 3 and parts[0] == "jobs" and parts[1] == "faculty-jobs":
            valid_slugs.add(parts[2])
    for child in FACULTY_ROOT.iterdir() if FACULTY_ROOT.exists() else []:
        if not child.is_dir():
            continue
        if child.name in protected or child.name in valid_slugs:
            continue
        index_file = child / "index.html"
        if index_file.exists():
            import shutil
            shutil.rmtree(child)
            print(f"[INFO] Removed stale generated faculty page: {child}")


def write_faculty_sitemap(paths: Sequence[str]) -> None:
    today = dt.datetime.now(IST).date().isoformat()
    body = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path in sorted(set(paths)):
        body.append("  <url>")
        body.append(f"    <loc>{url_for(path)}</loc>")
        body.append(f"    <lastmod>{today}</lastmod>")
        body.append("    <changefreq>daily</changefreq>")
        body.append("    <priority>0.78</priority>")
        body.append("  </url>")
    body.append("</urlset>")
    write_file(REPO_ROOT / "sitemap-faculty-jobs.xml", "\n".join(body) + "\n")


def update_main_sitemap(paths: Sequence[str]) -> None:
    sitemap_path = REPO_ROOT / "sitemap.xml"
    if not sitemap_path.exists():
        return
    text = sitemap_path.read_text(encoding="utf-8")
    # Remove older faculty-job entries before inserting fresh ones.
    text = re.sub(r"\s*<url>\s*<loc>https://learnwithhemant\.com/jobs/faculty-jobs/.*?</url>", "", text, flags=re.S)
    today = dt.datetime.now(IST).date().isoformat()
    entries = []
    for path in sorted(set(paths)):
        entries.append(f"""
  <url>
    <loc>{url_for(path)}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.78</priority>
  </url>""")
    if "</urlset>" in text:
        text = text.replace("</urlset>", "".join(entries) + "\n</urlset>")
        sitemap_path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Update static faculty jobs dashboard and pages.")
    parser.add_argument("--manual-json", default=str(DEFAULT_MANUAL_PATH))
    parser.add_argument("--sources", default=str(DEFAULT_SOURCES))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--limit", type=int, default=150)
    parser.add_argument("--max-sources", type=int, default=30)
    parser.add_argument("--max-links-per-source", type=int, default=100)
    args = parser.parse_args()

    manual_path = (REPO_ROOT / args.manual_json).resolve() if not Path(args.manual_json).is_absolute() else Path(args.manual_json)
    sources_path = (REPO_ROOT / args.sources).resolve() if not Path(args.sources).is_absolute() else Path(args.sources)
    out_json = (REPO_ROOT / args.out_json).resolve() if not Path(args.out_json).is_absolute() else Path(args.out_json)

    manual_jobs = load_manual_jobs(manual_path)
    print(f"[INFO] Loaded {len(manual_jobs)} manual faculty rows")
    auto_jobs: List[Dict[str, Any]] = []
    sources = load_sources(sources_path, args.max_sources)
    print(f"[INFO] Enabled official sources: {len(sources)}")
    for source in sources:
        source_type = clean(source.get("source_type") or source.get("type")).lower()
        source_url = clean(source.get("source_url"))
        if source_type in {"external_sitemap", "external_listing_sitemap"}:
            auto_jobs.extend(scrape_external_listing_sitemap(source, max_links=args.max_links_per_source))
        elif source_type in {"external_category", "external_listing_category", "external_listing_page"}:
            auto_jobs.extend(scrape_external_listing_category(source, max_links=args.max_links_per_source))
        elif source_type in {"search", "search_query", "duckduckgo"} or source_url.lower().startswith("search:"):
            auto_jobs.extend(scrape_search_query(source, max_links=args.max_links_per_source))
        else:
            auto_jobs.extend(scrape_source(source, max_links=args.max_links_per_source))
    print(f"[INFO] Auto rows before dedupe: {len(auto_jobs)}")
    jobs = merge_jobs(manual_jobs, auto_jobs, args.limit)
    print(f"[INFO] Rows after dedupe/limit: {len(jobs)}")
    now = dt.datetime.now(IST)
    payload = {
        "generated_at": now.isoformat(timespec="seconds"),
        "updated_label": now.strftime("Updated: %d %b %Y, %I:%M %p IST"),
        "source": "manual verified faculty jobs + external listing discovery + enabled official-source scanner",
        "manual_count": len(manual_jobs),
        "auto_count": len(auto_jobs),
        "jobs": jobs,
    }
    write_json(payload, out_json)
    paths = generate_pages(payload)
    cleanup_generated_dirs(paths)
    write_faculty_sitemap(paths)
    update_main_sitemap(paths)
    print(f"[OK] Generated {len(paths)} faculty job/category URLs")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
