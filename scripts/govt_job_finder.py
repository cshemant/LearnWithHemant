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
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

try:
    import pdfplumber
except Exception:
    pdfplumber = None


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

DATE_PATTERNS = [
    # 23-07-2026, 23/07/2026, 23.07.2026
    r"\b([0-3]?\d[-/.][01]?\d[-/.](?:20)?\d{2})\b",
    # 2026-07-23
    r"\b((?:20)\d{2}[-/.][01]?\d[-/.][0-3]?\d)\b",
    # 23 Jul 2026 / 23 July 2026
    r"\b([0-3]?\d\s+(?:Jan|January|Feb|February|Mar|March|Apr|April|May|Jun|June|Jul|July|Aug|August|Sep|Sept|September|Oct|October|Nov|November|Dec|December)\s+(?:20)?\d{2})\b",
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


def safe_request(session: requests.Session, url: str, timeout: int = 20) -> Tuple[Optional[bytes], str, Optional[int]]:
    try:
        resp = session.get(url, timeout=timeout, allow_redirects=True)
        ctype = resp.headers.get("Content-Type", "")
        if resp.status_code >= 400:
            return None, ctype, resp.status_code
        return resp.content, ctype, resp.status_code
    except Exception as e:
        print(f"[WARN] Could not fetch {url}: {e}", file=sys.stderr)
        return None, "", None


def is_same_or_safe_domain(base_url: str, link: str) -> bool:
    try:
        base = urlparse(base_url)
        target = urlparse(link)
        if not target.netloc:
            return True
        # allow same host or direct government domains
        govish = (".gov.in" in target.netloc) or (".nic.in" in target.netloc) or ("rajasthan.gov.in" in target.netloc)
        return target.netloc == base.netloc or govish
    except Exception:
        return False


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
    s = s.strip()
    formats = [
        "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
        "%d-%m-%y", "%d/%m/%y", "%d.%m.%y",
        "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
        "%d %b %Y", "%d %B %Y",
        "%d %b %y", "%d %B %y"
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
        if kk and kk in lowered:
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


def scrape_html_source(session: requests.Session, source: Dict, profile: Dict, max_pdfs: int = 8) -> List[Vacancy]:
    url = source["url"]
    state = source.get("state", "")
    agency = source.get("agency", "")

    content, ctype, status_code = safe_request(session, url)
    if not content:
        return []

    html = content.decode("utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")
    vacancies: List[Vacancy] = []

    # 1) Extract HTML table rows
    for tr in soup.find_all("tr"):
        cells = [normalize_text(c.get_text(" ")) for c in tr.find_all(["td", "th"])]
        if not cells or len(" ".join(cells)) < 10:
            continue
        row_text = " | ".join(cells)
        row_links = []
        for a in tr.find_all("a", href=True):
            row_links.append(urljoin(url, a["href"]))
        row_link = row_links[0] if row_links else url
        v = vacancy_from_text(state, agency, row_text, row_link, url, profile)
        if v:
            vacancies.append(v)

    # 2) Extract relevant links/notices from anchors
    links: List[Tuple[str, str]] = []
    for a in soup.find_all("a", href=True):
        label = normalize_text(a.get_text(" "))
        href = urljoin(url, a["href"])
        if not is_same_or_safe_domain(url, href):
            continue
        joined = f"{label} {href}"
        if keyword_hits(joined, APPLY_KEYWORDS) or keyword_hits(joined, COMPUTER_KEYWORDS):
            links.append((label, href))

    # de-duplicate links
    seen_links = set()
    unique_links = []
    for label, href in links:
        if href not in seen_links:
            unique_links.append((label, href))
            seen_links.add(href)

    for label, href in unique_links:
        v = vacancy_from_text(state, agency, label, href, url, profile)
        if v:
            vacancies.append(v)

    # 3) Read selected PDFs
    pdf_count = 0
    for label, href in unique_links:
        if pdf_count >= max_pdfs:
            break
        if ".pdf" not in href.lower():
            continue
        # Fetch only likely relevant PDFs
        if not (keyword_hits(label, APPLY_KEYWORDS) or keyword_hits(label, COMPUTER_KEYWORDS)):
            continue
        pdf_bytes, pdf_ctype, pdf_status = safe_request(session, href, timeout=30)
        if not pdf_bytes:
            continue
        if b"%PDF" not in pdf_bytes[:20] and "pdf" not in pdf_ctype.lower():
            continue
        pdf_text = extract_pdf_text(pdf_bytes)
        if pdf_text:
            combined = f"{label} {pdf_text}"
            v = vacancy_from_text(state, agency, combined, href, url, profile)
            if v:
                vacancies.append(v)
        pdf_count += 1
        time.sleep(0.5)

    return vacancies


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


def run(profile_path: Optional[str], sources_path: Optional[str], out_path: str, max_pdfs: int) -> None:
    base_dir = Path(".")
    save_default_files(base_dir)

    profile = load_profile(profile_path)
    sources = load_sources(sources_path)

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 GovtJobFinder/1.0 (+manual verification required)"
    })

    all_vacancies: List[Vacancy] = []

    print(f"[INFO] Profile: {profile.get('name')} | DOB: {profile.get('dob')} | Category: {profile.get('category')}")
    print(f"[INFO] Scanning {len(sources)} sources...")

    for idx, source in enumerate(sources, start=1):
        print(f"[{idx}/{len(sources)}] {source.get('state')} - {source.get('agency')} - {source.get('url')}")
        try:
            if source.get("source_type", "html").lower() == "html":
                found = scrape_html_source(session, source, profile, max_pdfs=max_pdfs)
            else:
                found = []
            print(f"   found candidates: {len(found)}")
            all_vacancies.extend(found)
        except Exception as e:
            print(f"[ERROR] Source failed: {source.get('url')} -> {e}", file=sys.stderr)
        time.sleep(0.7)

    all_vacancies = dedupe_vacancies(all_vacancies)
    print(f"[INFO] Total unique candidate vacancies/notices: {len(all_vacancies)}")

    export_excel(all_vacancies, sources, profile, out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Government job vacancy finder for B.Tech/M.Tech CSE profile.")
    parser.add_argument("--profile", default=None, help="Path to profile.json")
    parser.add_argument("--sources", default=None, help="Path to sources_gov_jobs.csv")
    parser.add_argument("--out", default="government_jobs_tracker.xlsx", help="Output Excel file path")
    parser.add_argument("--max-pdfs", type=int, default=8, help="Max PDFs to parse per source")
    args = parser.parse_args()

    run(args.profile, args.sources, args.out, args.max_pdfs)


if __name__ == "__main__":
    main()
