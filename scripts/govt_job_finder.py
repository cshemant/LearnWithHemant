#!/usr/bin/env python3
"""
Govt Job Vacancy Finder + Eligibility Matcher
For: B.Tech + M.Tech Computer Science profile

What it does:
- Scans official government recruitment pages
- Extracts vacancy rows/links from HTML tables and notices
- Reads linked PDF notifications where possible
- Matches computer/IT/teaching/office keywords
- Checks basic eligibility signals: subject, education, age, dates, experience risk
- Exports Excel with:
  Eligible Apply Now, Doubtful Manual Check, Avoid or Closed, All Raw Matches, Sources, Profile

Install:
  pip install -r requirements.txt

Run:
  python govt_job_finder.py

Optional:
  python govt_job_finder.py --profile profile.json --sources sources_gov_jobs.csv --out jobs.xlsx

Important:
- This is a vacancy discovery + eligibility pre-filter tool.
- Always manually verify official PDF notification before applying.
- It does not auto-apply, because OTP/payment/declaration/document upload must be handled manually.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import io
import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, urldefrag

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

try:
    import pdfplumber
except Exception:
    pdfplumber = None


# Excel/openpyxl rejects ASCII control characters that sometimes appear when
# a government portal returns an image/binary file instead of an HTML/PDF page.
# Example failure: "JFIF ... cannot be used in worksheets."
EXCEL_ILLEGAL_CHAR_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
IMAGE_MAGIC_PREFIXES = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF87a", b"GIF89a", b"RIFF")


def is_image_response(content: bytes, content_type: str = "") -> bool:
    ctype = (content_type or "").lower()
    return ctype.startswith("image/") or any(content.startswith(prefix) for prefix in IMAGE_MAGIC_PREFIXES)


def excel_safe_value(value):
    if not isinstance(value, str):
        return value
    return EXCEL_ILLEGAL_CHAR_RE.sub(" ", value)


def excel_safe_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    safe = frame.copy()
    for column in safe.select_dtypes(include=["object"]).columns:
        safe[column] = safe[column].map(excel_safe_value)
    return safe


# -----------------------------
# Default profile: edit as needed
# -----------------------------

DEFAULT_PROFILE = {
    "name": "Hemant Kumar",
    "dob": "1992-02-12",
    "category": "GENERAL",
    "education": [
        "B.Tech Computer Science Engineering",
        "M.Tech Computer Science Engineering"
    ],
    "highest_degree": "M.Tech",
    "marks_percent": 60,
    "subjects": [
        "computer science",
        "computer science and engineering",
        "computer applications",
        "information technology",
        "software engineering",
        "data science",
        "artificial intelligence",
        "machine learning",
        "cyber security",
        "database",
        "programming"
    ],
    "preferred_roles": [
        "assistant professor",
        "lecturer",
        "guest faculty",
        "teaching assistant",
        "computer instructor",
        "programmer",
        "software developer",
        "system analyst",
        "it assistant",
        "computer operator",
        "data entry operator",
        "junior assistant",
        "lower division clerk",
        "clerk",
        "office assistant",
        "technical assistant",
        "scientist b",
        "scientific officer",
        "informatics assistant",
        "mis officer"
    ],
    "states_preferred": [
        "Rajasthan", "Bihar", "Uttar Pradesh", "Delhi", "Madhya Pradesh",
        "Jharkhand", "Haryana", "Central"
    ]
}


# -----------------------------
# Starter official sources
# Add/remove URLs as needed.
# -----------------------------

DEFAULT_SOURCES = [
    # Rajasthan
    {"state": "Rajasthan", "agency": "State Recruitment Portal", "url": "https://recruitment.rajasthan.gov.in/", "source_type": "html"},
    {"state": "Rajasthan", "agency": "RPSC", "url": "https://rpsc.rajasthan.gov.in/advertisements", "source_type": "html"},
    {"state": "Rajasthan", "agency": "RSSB", "url": "https://rssb.rajasthan.gov.in/", "source_type": "html"},

    # Bihar
    {"state": "Bihar", "agency": "BPSC", "url": "https://bpsc.bihar.gov.in/advertisement/", "source_type": "html"},
    {"state": "Bihar", "agency": "BSSC", "url": "https://bssc.bihar.gov.in/", "source_type": "html"},
    {"state": "Bihar", "agency": "BTSC", "url": "https://btsc.bihar.gov.in/recruitment", "source_type": "html"},
    {"state": "Bihar", "agency": "CSBC", "url": "https://csbc.bihar.gov.in/", "source_type": "html"},
    {"state": "Bihar", "agency": "BPSSC", "url": "https://bpssc.bihar.gov.in/", "source_type": "html"},

    # Uttar Pradesh
    {"state": "Uttar Pradesh", "agency": "UPPSC", "url": "https://uppsc.up.nic.in/CandidatePages/Notifications.aspx", "source_type": "html"},
    {"state": "Uttar Pradesh", "agency": "UPSSSC", "url": "https://upsssc.gov.in/", "source_type": "html"},

    # Delhi / Central
    {"state": "Delhi", "agency": "DSSSB", "url": "https://dsssb.delhi.gov.in/dsssb-vacancies", "source_type": "html"},
    {"state": "Central", "agency": "SSC", "url": "https://ssc.gov.in/", "source_type": "html"},
    {"state": "Central", "agency": "UPSC", "url": "https://upsc.gov.in/recruitment/recruitment-advertisement", "source_type": "html"},
    {"state": "Central", "agency": "NIELIT Delhi Recruitment", "url": "https://recruit-delhi.nielit.gov.in/", "source_type": "html"},
    {"state": "Central", "agency": "NCS Govt Jobs", "url": "https://www.ncs.gov.in/job-seeker/Pages/GovtJob.aspx", "source_type": "html"},

    # MP / Haryana / Jharkhand
    {"state": "Madhya Pradesh", "agency": "MPESB", "url": "https://esb.mp.gov.in/e_default.html", "source_type": "html"},
    {"state": "Haryana", "agency": "HSSC", "url": "https://hssc.gov.in/", "source_type": "html"},
    {"state": "Jharkhand", "agency": "JSSC", "url": "https://jssc.jharkhand.gov.in/", "source_type": "html"},
    {"state": "Jharkhand", "agency": "JPSC", "url": "https://www.jpsc.gov.in/", "source_type": "html"},
]


COMPUTER_KEYWORDS = [
    "computer", "cse", "computer science", "computer application", "information technology",
    "informatics", "it ", "software", "programmer", "programming", "system analyst",
    "data", "database", "network", "cyber", "ai", "artificial intelligence", "machine learning",
    "web", "developer", "technical assistant", "scientist-b", "scientist b",
    "scientific officer", "assistant professor", "lecturer", "faculty", "instructor",
    "computer operator", "data entry", "office assistant", "junior assistant", "clerk",
    "ldc", "udc", "stenographer", "mis"
]

NEGATIVE_SUBJECT_KEYWORDS = [
    "yoga", "physical education", "physical sciences", "chemistry", "botany", "zoology",
    "law", "prosecution", "medical officer", "nursing", "agriculture", "veterinary",
    "ayurveda", "homeopathy", "pharmacy", "civil engineering", "mechanical engineering",
    "electrical engineering", "automobile", "leather technology"
]

TEACHING_KEYWORDS = [
    "assistant professor", "lecturer", "guest faculty", "faculty", "instructor",
    "teaching", "professor", "polytechnic"
]

OFFICE_KEYWORDS = [
    "junior assistant", "clerk", "ldc", "udc", "office assistant", "data entry",
    "computer operator", "stenographer", "assistant"
]

APPLY_KEYWORDS = [
    "apply", "online", "application", "registration", "last date", "start date",
    "advertisement", "notification", "recruitment", "vacancy", "vacancies", "advt"
]

# Links on many official portals are generic (for example "Advertisement 06/2026")
# and the CSE/IT keywords are only inside the linked detail page or PDF.  These
# terms are therefore used for one-level discovery before eligibility filtering.
NOTICE_LINK_KEYWORDS = [
    "advertisement", "notification", "recruitment", "vacancy", "vacancies",
    "current opening", "current openings", "career opportunity", "career opportunities",
    "job opening", "job openings", "apply online", "view details", "read more",
    "download advertisement", "advt", "employment notice", "walk-in"
]

NON_VACANCY_LINK_KEYWORDS = [
    "result", "answer key", "admit card", "shortlist", "merit list", "syllabus",
    "interview schedule", "exam schedule", "archive", "archives", "old advertisement",
    "corrigendum only", "faq", "tender", "procurement"
]

PDF_HINTS = [".pdf", " pdf", "pdf ", "download", "document", "attachment", "getfile", "viewfile"]

DATE_PATTERNS = [
    # 23-07-2026, 23/07/2026, 23.07.2026
    r"\b([0-3]?\d[-/.][01]?\d[-/.](?:20)?\d{2})\b",
    # 2026-07-23
    r"\b((?:20)\d{2}[-/.][01]?\d[-/.][0-3]?\d)\b",
    # 23 Jul 2026 / 23rd July 2026
    r"\b([0-3]?\d(?:st|nd|rd|th)?\s+(?:Jan|January|Feb|February|Mar|March|Apr|April|May|Jun|June|Jul|July|Aug|August|Sep|Sept|September|Oct|October|Nov|November|Dec|December)\s+(?:20)?\d{2})\b",
    # July 23, 2026 / Jul 23 2026
    r"\b((?:Jan|January|Feb|February|Mar|March|Apr|April|May|Jun|June|Jul|July|Aug|August|Sep|Sept|September|Oct|October|Nov|November|Dec|December)\s+[0-3]?\d,?\s+(?:20)?\d{2})\b",
]

AGE_PATTERNS = [
    r"(?:maximum|max\.?|upper age|age limit|not exceeding|below)\s*(?:age)?\s*(?:is)?\s*(\d{2})\s*(?:years|yrs|year)",
    r"(\d{2})\s*(?:years|yrs|year)\s*(?:as on|upper age|max|maximum|not exceeding)",
]


@dataclasses.dataclass
class Vacancy:
    state: str
    agency: str
    name: str
    eligibility: str
    start_date: str
    apply_date: str
    link: str
    source_url: str
    role_type: str
    match_score: int
    status: str
    reason: str
    extracted_text: str


def normalize_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def text_lower(text: str) -> str:
    return normalize_text(text).lower()


def today() -> dt.date:
    return dt.date.today()


def parse_profile_age(profile: Dict) -> Optional[int]:
    dob = profile.get("dob")
    if not dob:
        return None
    try:
        d = dt.datetime.strptime(dob, "%Y-%m-%d").date()
    except ValueError:
        return None
    t = today()
    return t.year - d.year - ((t.month, t.day) < (d.month, d.day))


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9,hi;q=0.7",
        "Cache-Control": "no-cache",
    })
    return session


def safe_request(session: requests.Session, url: str, timeout: int = 25) -> Tuple[Optional[bytes], str, Optional[int]]:
    try:
        resp = session.get(url, timeout=timeout, allow_redirects=True)
        ctype = resp.headers.get("Content-Type", "")
        if resp.status_code >= 400:
            print(f"[WARN] HTTP {resp.status_code} for {url}", file=sys.stderr)
            return None, ctype, resp.status_code
        return resp.content, ctype, resp.status_code
    except Exception as e:
        print(f"[WARN] Could not fetch {url}: {e}", file=sys.stderr)
        return None, "", None


def _host(value: str) -> str:
    host = (urlparse(value).hostname or "").lower().strip(".")
    return host[4:] if host.startswith("www.") else host


def is_same_or_safe_domain(base_url: str, link: str) -> bool:
    try:
        base_host = _host(base_url)
        target_host = _host(link)
        if not target_host:
            return True
        if target_host == base_host or target_host.endswith("." + base_host) or base_host.endswith("." + target_host):
            return True
        # Government notices are sometimes served from another official NIC/GOV host.
        return target_host.endswith(".gov.in") or target_host.endswith(".nic.in") or target_host in {"gov.in", "nic.in"}
    except Exception:
        return False


def normalize_link(base_url: str, raw: str) -> str:
    raw = (raw or "").strip().strip("'\"")
    if not raw or raw.startswith(("#", "javascript:", "mailto:", "tel:")):
        return ""
    absolute = urljoin(base_url, raw)
    absolute, _ = urldefrag(absolute)
    return absolute


def anchor_targets(anchor, base_url: str) -> List[str]:
    targets: List[str] = []
    for attr in ("href", "data-href", "data-url", "data-link", "data-download"):
        value = anchor.get(attr)
        link = normalize_link(base_url, value)
        if link:
            targets.append(link)
    scriptish = " ".join(str(anchor.get(attr) or "") for attr in ("onclick", "data-onclick"))
    for raw in re.findall(r"['\"]([^'\"]{4,500})['\"]", scriptish):
        if any(hint in raw.lower() for hint in PDF_HINTS + NOTICE_LINK_KEYWORDS):
            link = normalize_link(base_url, raw)
            if link:
                targets.append(link)
    return list(dict.fromkeys(targets))


def looks_like_notice(label: str, href: str) -> bool:
    blob = text_lower(f"{label} {href}")
    if any(bad in blob for bad in NON_VACANCY_LINK_KEYWORDS):
        return False
    return bool(keyword_hits(blob, NOTICE_LINK_KEYWORDS) or keyword_hits(blob, APPLY_KEYWORDS) or keyword_hits(blob, COMPUTER_KEYWORDS))


def looks_like_pdf(label: str, href: str) -> bool:
    label_l = text_lower(label)
    href_l = (href or "").lower()
    if ".pdf" in href_l or re.search(r"\bpdf\b", label_l):
        return True
    return any(hint in href_l for hint in ["download", "attachment", "getfile", "viewfile", "document"])


def extract_dates(text: str) -> List[str]:
    found = []
    for pat in DATE_PATTERNS:
        for m in re.findall(pat, text, flags=re.IGNORECASE):
            found.append(m)
    # preserve order, unique
    out = []
    seen = set()
    for d in found:
        if d not in seen:
            out.append(d)
            seen.add(d)
    return out


def parse_date_flexible(s: str) -> Optional[dt.date]:
    if not s:
        return None
    s = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", s.strip(), flags=re.I).replace(",", "")
    formats = [
        "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
        "%d-%m-%y", "%d/%m/%y", "%d.%m.%y",
        "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
        "%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y",
        "%d %b %y", "%d %B %y", "%b %d %y", "%B %d %y"
    ]
    for fmt in formats:
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def guess_start_last_dates(text: str) -> Tuple[str, str]:
    dates = extract_dates(text)
    if not dates:
        return "", ""
    # Heuristic:
    # - if surrounding text contains last/closing/end, use that date as apply_date
    # - otherwise last detected date is likely last date
    lowered = text_lower(text)
    apply_date = ""
    start_date = ""

    for d in dates:
        idx = lowered.find(d.lower())
        window = lowered[max(0, idx - 80): idx + 80] if idx >= 0 else ""
        if any(k in window for k in ["last date", "closing date", "end date", "last", "upto", "up to", "till"]):
            apply_date = d
        if any(k in window for k in ["start date", "from", "opening date", "commencement"]):
            start_date = d

    if not start_date and dates:
        start_date = dates[0]
    if not apply_date and dates:
        apply_date = dates[-1]

    return start_date, apply_date


def extract_max_age(text: str) -> Optional[int]:
    lowered = text_lower(text)
    for pat in AGE_PATTERNS:
        m = re.search(pat, lowered, flags=re.IGNORECASE)
        if m:
            try:
                age = int(m.group(1))
                if 16 <= age <= 65:
                    return age
            except Exception:
                pass
    return None


def keyword_hits(text: str, keywords: Iterable[str]) -> List[str]:
    lowered = f" {text_lower(text)} "
    hits = []
    for k in keywords:
        kk = k.lower().strip()
        if not kk:
            continue
        if len(kk) <= 3 and kk.replace("-", "").isalnum():
            matched = re.search(r"\b" + re.escape(kk) + r"\b", lowered) is not None
        else:
            matched = kk in lowered
        if matched:
            hits.append(k)
    return hits


def detect_role_type(text: str) -> str:
    l = text_lower(text)
    if any(k in l for k in TEACHING_KEYWORDS):
        return "Teaching"
    if any(k in l for k in OFFICE_KEYWORDS):
        return "Office/Clerical"
    if any(k in l for k in ["programmer", "system analyst", "scientist", "technical", "it assistant", "software"]):
        return "Technical/IT"
    return "General/Other"


def education_fit(text: str, profile: Dict) -> Tuple[bool, str]:
    l = text_lower(text)
    has_mtech = any(k in l for k in ["m.tech", "mtech", "m.e.", "master", "post graduate", "post-graduate", "pg", "m.sc", "mca"])
    has_btech = any(k in l for k in ["b.tech", "btech", "b.e.", "bachelor", "graduate", "graduation", "degree"])
    has_cse = any(sub in l for sub in profile.get("subjects", []))
    requires_specific_non_cse = any(k in l for k in NEGATIVE_SUBJECT_KEYWORDS)

    if has_mtech and has_cse:
        return True, "PG/M.Tech + Computer/IT subject appears to match"
    if has_btech and has_cse:
        return True, "B.Tech/Graduate + Computer/IT subject appears to match"
    if ("any graduate" in l or "graduate in any discipline" in l or "graduation in any discipline" in l):
        return True, "Any graduate appears eligible"
    if has_btech and not requires_specific_non_cse:
        return True, "Graduate/Bachelor degree appears eligible; subject needs manual check"
    if requires_specific_non_cse and not has_cse:
        return False, "Specific non-CSE subject appears required"
    return False, "Education/subject not clearly matched"


def is_closed(apply_date: str) -> bool:
    d = parse_date_flexible(apply_date)
    if d is None:
        return False
    return d < today()


def compute_match_status(text: str, profile: Dict, apply_date: str) -> Tuple[int, str, str]:
    lowered = text_lower(text)
    score = 0
    reasons = []

    comp_hits = keyword_hits(text, COMPUTER_KEYWORDS)
    preferred_hits = keyword_hits(text, profile.get("preferred_roles", []))
    neg_hits = keyword_hits(text, NEGATIVE_SUBJECT_KEYWORDS)

    if comp_hits:
        score += min(40, 8 * len(comp_hits))
        reasons.append(f"Computer/IT/office keywords: {', '.join(comp_hits[:6])}")
    if preferred_hits:
        score += min(25, 10 * len(preferred_hits))
        reasons.append(f"Preferred role keywords: {', '.join(preferred_hits[:5])}")

    fit, fit_reason = education_fit(text, profile)
    if fit:
        score += 25
        reasons.append(fit_reason)
    else:
        score -= 20
        reasons.append(fit_reason)

    max_age = extract_max_age(text)
    user_age = parse_profile_age(profile)
    if max_age and user_age:
        if user_age <= max_age:
            score += 10
            reasons.append(f"Age appears okay: user age {user_age}, max {max_age}")
        else:
            score -= 35
            reasons.append(f"Age risk: user age {user_age}, max {max_age}")

    if neg_hits:
        score -= min(35, 10 * len(neg_hits))
        reasons.append(f"Non-CSE subject risk: {', '.join(neg_hits[:4])}")

    if apply_date and is_closed(apply_date):
        score -= 50
        reasons.append("Last date appears closed")

    # Eligibility classification
    if apply_date and is_closed(apply_date):
        status = "Avoid or Closed"
    elif score >= 55 and fit:
        status = "Eligible Apply Now"
    elif score >= 20:
        status = "Doubtful Manual Check"
    else:
        status = "Avoid or Closed"

    return max(0, min(100, score)), status, " | ".join(reasons)


def extract_pdf_text(pdf_bytes: bytes, max_pages: int = 6) -> str:
    if pdfplumber is None:
        return ""
    try:
        text_parts = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages[:max_pages]:
                text_parts.append(page.extract_text() or "")
        return normalize_text(" ".join(text_parts))
    except Exception as e:
        print(f"[WARN] PDF parse failed: {e}", file=sys.stderr)
        return ""


def vacancy_from_text(
    state: str,
    agency: str,
    text: str,
    link: str,
    source_url: str,
    profile: Dict
) -> Optional[Vacancy]:
    cleaned = normalize_text(text)
    if len(cleaned) < 10:
        return None

    # Keep rows/notices that look like recruitment OR match target keywords.
    apply_hits = keyword_hits(cleaned, APPLY_KEYWORDS)
    comp_hits = keyword_hits(cleaned, COMPUTER_KEYWORDS)
    preferred_hits = keyword_hits(cleaned, profile.get("preferred_roles", []))

    if not (apply_hits or comp_hits or preferred_hits):
        return None

    start_date, apply_date = guess_start_last_dates(cleaned)
    score, status, reason = compute_match_status(cleaned, profile, apply_date)

    # Generate compact name
    name = cleaned[:180]
    name = re.sub(r"\s+", " ", name)
    role_type = detect_role_type(cleaned)

    return Vacancy(
        state=state,
        agency=agency,
        name=name,
        eligibility="Auto-extracted: " + reason[:400],
        start_date=start_date,
        apply_date=apply_date,
        link=link,
        source_url=source_url,
        role_type=role_type,
        match_score=score,
        status=status,
        reason=reason,
        extracted_text=cleaned[:3000]
    )


def _extract_page_candidates(
    soup: BeautifulSoup,
    page_url: str,
    source: Dict,
    profile: Dict,
) -> Tuple[List[Vacancy], List[Tuple[str, str]]]:
    state = source.get("state", "")
    agency = source.get("agency", "")
    vacancies: List[Vacancy] = []
    links: List[Tuple[str, str]] = []

    # Structured table rows are the most reliable source of title/date/link data.
    for tr in soup.find_all("tr"):
        cells = [normalize_text(c.get_text(" ")) for c in tr.find_all(["td", "th"])]
        if not cells or len(" ".join(cells)) < 10:
            continue
        row_text = " | ".join(cells)
        row_links: List[str] = []
        for a in tr.find_all("a"):
            row_links.extend(anchor_targets(a, page_url))
        row_link = row_links[0] if row_links else page_url
        v = vacancy_from_text(state, agency, row_text, row_link, source.get("url", page_url), profile)
        if v:
            vacancies.append(v)

    for a in soup.find_all("a"):
        label = normalize_text(a.get_text(" ") or a.get("title") or a.get("aria-label") or "")
        for href in anchor_targets(a, page_url):
            if not is_same_or_safe_domain(source.get("url", page_url), href):
                continue
            if looks_like_notice(label, href) or looks_like_pdf(label, href):
                links.append((label, href))
                # Add immediately only when the visible text itself contains enough signal.
                if keyword_hits(label, COMPUTER_KEYWORDS) or keyword_hits(label, profile.get("preferred_roles", [])):
                    v = vacancy_from_text(state, agency, label, href, source.get("url", page_url), profile)
                    if v:
                        vacancies.append(v)

    # Some portals expose download paths only inside scripts/onclick blocks.
    raw_html = str(soup)
    for raw in re.findall(r"(?:https?://[^\"'<>\s]+|[A-Za-z0-9_./?=&%-]{4,}\.pdf(?:\?[^\"'<>\s]*)?)", raw_html, flags=re.I):
        href = normalize_link(page_url, raw)
        if href and is_same_or_safe_domain(source.get("url", page_url), href) and looks_like_pdf("", href):
            links.append(("Advertisement PDF", href))

    unique_links: List[Tuple[str, str]] = []
    seen = set()
    for label, href in links:
        if href in seen:
            continue
        seen.add(href)
        unique_links.append((label, href))
    return vacancies, unique_links


def scrape_html_source(
    session: requests.Session,
    source: Dict,
    profile: Dict,
    max_pdfs: int = 8,
    max_detail_pages: int = 6,
) -> Tuple[List[Vacancy], Dict[str, object]]:
    url = source["url"]
    state = source.get("state", "")
    agency = source.get("agency", "")
    stats: Dict[str, object] = {
        "state": state,
        "agency": agency,
        "url": url,
        "landing_status": None,
        "detail_pages_fetched": 0,
        "pdfs_fetched": 0,
        "candidates": 0,
        "errors": [],
    }

    content, ctype, status_code = safe_request(session, url)
    stats["landing_status"] = status_code
    if not content:
        stats["errors"] = [f"landing page unavailable ({status_code or 'network error'})"]
        return [], stats

    if is_image_response(content, ctype):
        stats["errors"] = ["landing URL returned an image instead of a recruitment page"]
        return [], stats

    # A configured source itself may be a PDF.
    if b"%PDF" in content[:20] or "pdf" in (ctype or "").lower():
        text = extract_pdf_text(content, max_pages=10)
        vacancies = []
        if text:
            v = vacancy_from_text(state, agency, text, url, url, profile)
            if v:
                vacancies.append(v)
        stats["pdfs_fetched"] = 1
        stats["candidates"] = len(vacancies)
        return vacancies, stats

    soup = BeautifulSoup(content.decode("utf-8", errors="ignore"), "html.parser")
    vacancies, discovered_links = _extract_page_candidates(soup, url, source, profile)

    fetched = {url}
    pdf_queue: List[Tuple[str, str]] = [(label, href) for label, href in discovered_links if looks_like_pdf(label, href)]
    detail_queue: List[Tuple[str, str]] = [
        (label, href) for label, href in discovered_links
        if not looks_like_pdf(label, href) and href != url and looks_like_notice(label, href)
    ]

    # Follow a small number of notice/detail pages. This is the missing step on
    # portals whose landing page only says "Advertisement 07/2026".
    detail_count = 0
    while detail_queue and detail_count < max_detail_pages:
        label, href = detail_queue.pop(0)
        if href in fetched:
            continue
        fetched.add(href)
        page_bytes, page_ctype, page_status = safe_request(session, href, timeout=30)
        if not page_bytes:
            continue
        if is_image_response(page_bytes, page_ctype):
            continue
        if b"%PDF" in page_bytes[:20] or "pdf" in (page_ctype or "").lower():
            pdf_queue.append((label, href))
            # Reuse already downloaded bytes below through a tiny local cache.
            continue
        detail_count += 1
        stats["detail_pages_fetched"] = detail_count
        detail_soup = BeautifulSoup(page_bytes.decode("utf-8", errors="ignore"), "html.parser")
        page_text = normalize_text(detail_soup.get_text(" "))
        if keyword_hits(page_text, COMPUTER_KEYWORDS) or keyword_hits(page_text, profile.get("preferred_roles", [])):
            v = vacancy_from_text(state, agency, page_text, href, url, profile)
            if v:
                vacancies.append(v)
        page_vacancies, page_links = _extract_page_candidates(detail_soup, href, source, profile)
        vacancies.extend(page_vacancies)
        for child_label, child_href in page_links:
            if child_href in fetched:
                continue
            if looks_like_pdf(child_label, child_href):
                pdf_queue.append((child_label, child_href))
            elif len(detail_queue) < max_detail_pages * 3 and looks_like_notice(child_label, child_href):
                detail_queue.append((child_label, child_href))

    # Parse more than the first three PDFs and detect PDFs by response content,
    # not only by a .pdf suffix.
    seen_pdf = set()
    pdf_count = 0
    for label, href in pdf_queue:
        if pdf_count >= max_pdfs or href in seen_pdf:
            continue
        seen_pdf.add(href)
        pdf_bytes, pdf_ctype, pdf_status = safe_request(session, href, timeout=40)
        if not pdf_bytes:
            continue
        if is_image_response(pdf_bytes, pdf_ctype):
            continue
        if b"%PDF" not in pdf_bytes[:20] and "pdf" not in (pdf_ctype or "").lower():
            # A supposed PDF can actually be an HTML notice page; inspect it once.
            try:
                extra_soup = BeautifulSoup(pdf_bytes.decode("utf-8", errors="ignore"), "html.parser")
                extra_text = normalize_text(extra_soup.get_text(" "))
                if keyword_hits(extra_text, COMPUTER_KEYWORDS) or keyword_hits(extra_text, profile.get("preferred_roles", [])):
                    v = vacancy_from_text(state, agency, extra_text, href, url, profile)
                    if v:
                        vacancies.append(v)
            except Exception:
                pass
            continue
        pdf_text = extract_pdf_text(pdf_bytes, max_pages=10)
        if pdf_text:
            combined = f"{label} {pdf_text}"
            v = vacancy_from_text(state, agency, combined, href, url, profile)
            if v:
                vacancies.append(v)
        pdf_count += 1
        stats["pdfs_fetched"] = pdf_count
        time.sleep(0.25)

    stats["candidates"] = len(vacancies)
    return vacancies, stats


def dedupe_vacancies(vacancies: List[Vacancy]) -> List[Vacancy]:
    seen = set()
    out = []
    for v in vacancies:
        key = (v.link.strip().lower(), v.name[:80].strip().lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
    out.sort(key=lambda x: (x.status != "Eligible Apply Now", -x.match_score, x.apply_date or "9999"))
    return out


def load_profile(path: Optional[str]) -> Dict:
    if not path:
        return DEFAULT_PROFILE
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_sources(path: Optional[str]) -> List[Dict]:
    if not path:
        return DEFAULT_SOURCES
    sources = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("url"):
                sources.append({
                    "state": row.get("state", ""),
                    "agency": row.get("agency", ""),
                    "url": row["url"],
                    "source_type": row.get("source_type", "html") or "html"
                })
    return sources


def save_default_files(directory: Path) -> None:
    profile_path = directory / "profile.json"
    sources_path = directory / "sources_gov_jobs.csv"

    if not profile_path.exists():
        profile_path.write_text(json.dumps(DEFAULT_PROFILE, indent=2, ensure_ascii=False), encoding="utf-8")

    if not sources_path.exists():
        with open(sources_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["state", "agency", "url", "source_type"])
            writer.writeheader()
            for s in DEFAULT_SOURCES:
                writer.writerow(s)


def export_excel(vacancies: List[Vacancy], sources: List[Dict], profile: Dict, out_path: str) -> None:
    rows = []
    for v in vacancies:
        rows.append(dataclasses.asdict(v))

    df = pd.DataFrame(rows)

    # Requested core columns first
    core_cols = ["name", "eligibility", "start_date", "apply_date", "link"]
    extra_cols = [
        "state", "agency", "role_type", "match_score", "status",
        "reason", "source_url", "extracted_text"
    ]

    if df.empty:
        df = pd.DataFrame(columns=core_cols + extra_cols)

    rename = {
        "name": "Name",
        "eligibility": "Eligibility",
        "start_date": "Start Date",
        "apply_date": "Apply Date",
        "link": "Link",
        "state": "State",
        "agency": "Agency",
        "role_type": "Role Type",
        "match_score": "Match Score",
        "status": "Status",
        "reason": "Reason",
        "source_url": "Source URL",
        "extracted_text": "Extracted Text"
    }

    all_cols = core_cols + extra_cols
    for col in all_cols:
        if col not in df.columns:
            df[col] = ""

    df = df[all_cols].rename(columns=rename)

    eligible = df[df["Status"] == "Eligible Apply Now"].copy()
    doubtful = df[df["Status"] == "Doubtful Manual Check"].copy()
    avoid = df[df["Status"] == "Avoid or Closed"].copy()

    sources_df = pd.DataFrame(sources)
    profile_df = pd.DataFrame(
        [{"Field": k, "Value": ", ".join(v) if isinstance(v, list) else v} for k, v in profile.items()]
    )

    # Remove control characters before openpyxl writes any worksheet. Some
    # official sites return JPEG/image bytes for download links, and decoding
    # those bytes can inject characters that Excel refuses to store.
    df = excel_safe_dataframe(df)
    eligible = excel_safe_dataframe(eligible)
    doubtful = excel_safe_dataframe(doubtful)
    avoid = excel_safe_dataframe(avoid)
    sources_df = excel_safe_dataframe(sources_df)
    profile_df = excel_safe_dataframe(profile_df)

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        eligible.to_excel(writer, sheet_name="Eligible Apply Now", index=False)
        doubtful.to_excel(writer, sheet_name="Doubtful Manual Check", index=False)
        avoid.to_excel(writer, sheet_name="Avoid or Closed", index=False)
        df.to_excel(writer, sheet_name="All Raw Matches", index=False)
        sources_df.to_excel(writer, sheet_name="Sources", index=False)
        profile_df.to_excel(writer, sheet_name="Profile", index=False)

        # Simple formatting
        wb = writer.book
        for ws in wb.worksheets:
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions

            # widths
            width_map = {
                "A": 42, "B": 70, "C": 16, "D": 16, "E": 55,
                "F": 18, "G": 22, "H": 18, "I": 14, "J": 20,
                "K": 70, "L": 55, "M": 90
            }
            for col, width in width_map.items():
                ws.column_dimensions[col].width = width

            # header style
            for cell in ws[1]:
                cell.font = cell.font.copy(bold=True)
                cell.alignment = cell.alignment.copy(wrap_text=True, vertical="top")
            for row in ws.iter_rows(min_row=2):
                for cell in row:
                    cell.alignment = cell.alignment.copy(wrap_text=True, vertical="top")

            # Limit row height
            for i in range(1, min(ws.max_row, 200) + 1):
                ws.row_dimensions[i].height = 30

    print(f"[OK] Excel created: {out_path}")


def run(
    profile_path: Optional[str],
    sources_path: Optional[str],
    out_path: str,
    max_pdfs: int,
    max_detail_pages: int = 6,
) -> Dict[str, object]:
    base_dir = Path(".")
    save_default_files(base_dir)

    profile = load_profile(profile_path)
    sources = load_sources(sources_path)
    session = build_session()
    all_vacancies: List[Vacancy] = []
    source_results: List[Dict[str, object]] = []

    print(f"[INFO] Profile: {profile.get('name')} | DOB: {profile.get('dob')} | Category: {profile.get('category')}")
    print(f"[INFO] Scanning {len(sources)} sources...")

    for idx, source in enumerate(sources, start=1):
        print(f"[{idx}/{len(sources)}] {source.get('state')} - {source.get('agency')} - {source.get('url')}")
        try:
            if source.get("source_type", "html").lower() == "html":
                found, stats = scrape_html_source(
                    session,
                    source,
                    profile,
                    max_pdfs=max_pdfs,
                    max_detail_pages=max_detail_pages,
                )
            else:
                found = []
                stats = {
                    "state": source.get("state", ""),
                    "agency": source.get("agency", ""),
                    "url": source.get("url", ""),
                    "landing_status": None,
                    "detail_pages_fetched": 0,
                    "pdfs_fetched": 0,
                    "candidates": 0,
                    "errors": [f"unsupported source_type={source.get('source_type')}"]
                }
            print(
                f"   found candidates: {len(found)} | landing={stats.get('landing_status')} "
                f"| detail_pages={stats.get('detail_pages_fetched')} | pdfs={stats.get('pdfs_fetched')}"
            )
            source_results.append(stats)
            all_vacancies.extend(found)
        except Exception as e:
            print(f"[ERROR] Source failed: {source.get('url')} -> {e}", file=sys.stderr)
            source_results.append({
                "state": source.get("state", ""),
                "agency": source.get("agency", ""),
                "url": source.get("url", ""),
                "landing_status": None,
                "detail_pages_fetched": 0,
                "pdfs_fetched": 0,
                "candidates": 0,
                "errors": [str(e)],
            })
        time.sleep(0.35)

    all_vacancies = dedupe_vacancies(all_vacancies)
    print(f"[INFO] Total unique candidate vacancies/notices: {len(all_vacancies)}")
    export_excel(all_vacancies, sources, profile, out_path)

    reached = sum(1 for item in source_results if isinstance(item.get("landing_status"), int) and int(item["landing_status"]) < 400)
    failed = len(source_results) - reached
    return {
        "sources_total": len(sources),
        "sources_reached": reached,
        "sources_failed": failed,
        "candidate_count": len(all_vacancies),
        "source_results": source_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Government job vacancy finder for B.Tech/M.Tech CSE profile.")
    parser.add_argument("--profile", default=None, help="Path to profile.json")
    parser.add_argument("--sources", default=None, help="Path to sources_gov_jobs.csv")
    parser.add_argument("--out", default="government_jobs_tracker.xlsx", help="Output Excel file path")
    parser.add_argument("--max-pdfs", type=int, default=8, help="Max PDFs to parse per source")
    parser.add_argument("--max-detail-pages", type=int, default=6, help="Max recruitment/detail HTML pages to follow per source")
    args = parser.parse_args()

    run(args.profile, args.sources, args.out, args.max_pdfs, args.max_detail_pages)


if __name__ == "__main__":
    main()
