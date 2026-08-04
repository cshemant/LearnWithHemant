#!/usr/bin/env python3
from pathlib import Path
import datetime as dt
import html
import json
import re
from typing import Any, Dict, Iterable, List

from job_archive_utils import archive_sitemap_jobs, clean, load_json_payload, slugify

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "jobs" / "jobs-data.json"
ARCHIVE_DATA = ROOT / "jobs" / "job-archive.json"
BASE = "https://learnwithhemant.com"
TODAY = dt.date.today()
RETENTION_DAYS = 365


def esc(value: Any) -> str:
    return html.escape(clean(value), quote=True)


def ensure_slugs(jobs: List[Dict[str, Any]], used=None) -> None:
    used = used if used is not None else set()
    for job in jobs:
        existing = clean(job.get("slug"))
        base = slugify(existing or f"{job.get('job', '')} {job.get('state', '')} {job.get('type', '')} {TODAY.year}", "government-job")
        slug = base
        i = 2
        while slug in used:
            slug = f"{base[:88].strip('-')}-{i}"
            i += 1
        used.add(slug)
        job["slug"] = slug
        job["detail_url"] = f"/jobs/{slug}/"


def days_left(date_string: str) -> str:
    if not date_string:
        return ""
    try:
        deadline = dt.date.fromisoformat(date_string)
    except Exception:
        return ""
    diff = (deadline - TODAY).days
    if diff < 0:
        return "Closed"
    if diff == 0:
        return "Closing today"
    if diff == 1:
        return "1 day left"
    return f"{diff} days left"


def status_class(job: Dict[str, Any]) -> str:
    value = clean(job.get("status_class")).lower()
    return value if value in {"good", "doubtful", "caution", "avoid", "watch", "closed"} else "watch"


def is_archived(job: Dict[str, Any]) -> bool:
    return bool(job.get("is_archived")) or clean(job.get("status")).lower() in {"closed", "archived"}


def detail_positioning(job: Dict[str, Any]) -> str:
    if is_archived(job):
        return "This page is retained as a historical vacancy record. The application window is no longer shown as active; use the related current vacancies below for new opportunities."
    status = clean(job.get("status"))
    typ = clean(job.get("type"))
    eligible = clean(job.get("eligible_for"))
    if status == "Good Match":
        return f"This listing is marked as a good match because the available eligibility note fits the stated route: {eligible}. Use it as a shortlisting signal, not as final confirmation."
    if status == "Avoid":
        return f"This listing is marked as avoid for a CSE/IT-focused candidate because the eligibility note says: {eligible}. Keep it only for reference unless the official notice proves your qualification is accepted."
    if status == "Doubtful":
        return "This listing needs manual verification. The role may look relevant from the title or department, but the eligibility, subject code, age limit or experience condition can change the final decision."
    if typ == "Teaching":
        return "This is being tracked as a teaching route. Verify subject, NET/SET/PhD requirement, marks percentage and institution-specific rules from the official notice."
    if "IT" in typ or "Computer" in typ:
        return "This is being tracked as a possible computer/IT route. Confirm whether B.Tech CSE, M.Tech CSE, MCA or BCA is explicitly accepted for the exact post."
    return "This is being tracked as a watchlist opportunity. Open the official notice first, then confirm whether the job title, qualification and age rules match your profile."


def role_focus(job: Dict[str, Any]) -> str:
    typ = clean(job.get("type")) or "Government"
    tags = clean(job.get("profile_tags"))
    if tags:
        return f"The dashboard currently tags this opening for: {tags}. These tags are only a quick filter and should be verified from the official recruitment PDF."
    if typ == "Office":
        return "This appears closer to an office/general recruitment path than a pure software development job. Check the exact post list before spending time on the application."
    if typ == "Teaching":
        return "For teaching roles, subject eligibility matters more than the broad title. Confirm the Computer Science / IT subject code and qualification norms."
    if "Computer" in typ or "IT" in typ:
        return "For technical roles, verify whether the department asks for Computer Science, Information Technology, Computer Applications or another equivalent branch."
    return "The profile fit depends on the detailed notification. Do not rely only on the short title shown in the tracker."


def meta_desc(job: Dict[str, Any]) -> str:
    title = clean(job.get("job")) or "Government job"
    state = clean(job.get("state")) or "India"
    eligible = clean(job.get("eligible_for")) or "Check eligibility"
    prefix = "Archived application record" if is_archived(job) else "Government vacancy"
    return f"{prefix}: {title} for {state}. Check eligibility, status, last date, official notice and related active CSE/IT vacancies. {eligible}"[:158]


def header_html() -> str:
    return '''<header class="site-header home-v2-header"><div class="container nav home-v2-nav"><a class="brand home-v2-brand" href="/home/"><img alt="Learn with Hemant logo" class="brand-logo" src="/brand-logo.png"/><div><span>Learn with Hemant</span><small>Build • Deploy • Grow</small></div></a><nav aria-label="Main Navigation" class="nav-links home-v2-links"><a href="/about/">Mentor</a><a href="/courses/web-development/">Courses</a><a href="/projects/">Projects</a><a href="/guest-lecture/">Guest Lecture</a><a href="/tool/">Tool</a><a class="active-nav-link" href="/jobs/">Govt Jobs</a></nav><a class="nav-cta home-v2-cta" href="/apply/">Apply Now <span>→</span></a><button aria-controls="mobileSiteMenu" aria-expanded="false" aria-label="Open menu" class="mobile-menu-toggle" type="button"><span></span><span></span><span></span></button></div></header><div class="mobile-menu-backdrop" data-mobile-menu-close=""></div><aside aria-hidden="true" class="mobile-site-menu" id="mobileSiteMenu"><div class="mobile-menu-head"><a class="mobile-menu-brand" href="/home/"><img alt="Learn with Hemant logo" src="/brand-logo.png"/></a><button aria-label="Close menu" class="mobile-menu-close" data-mobile-menu-close="" type="button">×</button></div><nav aria-label="Mobile navigation" class="mobile-menu-links"><a href="/home/">Home</a><a href="/about/">Mentor</a><a href="/courses/web-development/">Courses</a><a href="/projects/">Projects</a><a href="/guest-lecture/">Guest Lecture</a><a href="/tool/">Tool</a><a href="/jobs/">Govt Jobs</a><a href="/jobs/archive/">Closed Govt Jobs</a><a href="/jobs/faculty-jobs/">Faculty Jobs</a><a href="/apply/">Apply Now</a></nav></aside>'''


def footer_html() -> str:
    return '''<footer class="site-footer v2-footer"><div class="container v2-footer-grid"><div class="v2-footer-brand"><div class="brand home-v2-brand footer-brand-row"><img class="brand-logo" src="/brand-logo.png" alt="Learn with Hemant logo"/><div><span>Learn with Hemant</span><small>Helping beginners become confident developers through practical training.</small></div></div></div><div><h3>Quick Links</h3><div class="v2-footer-links"><a href="/about/">Mentor</a><a href="/roadmap/">Roadmap</a><a href="/courses/web-development/">Courses</a><a href="/projects/">Projects</a><a href="/guest-lecture/">Guest Lecture</a><a href="/apply/">Free Demo</a></div></div><div><h3>Jobs</h3><div class="v2-footer-links"><a href="/jobs/">CSE Govt Jobs</a><a href="/jobs/archive/">Closed Govt Jobs</a><a href="/jobs/faculty-jobs/">Faculty Jobs</a><a href="/jobs/faculty-jobs/archive/">Closed Faculty Jobs</a></div></div><div><h3>Connect</h3><div class="v2-footer-links"><a href="mailto:learnwithhemantsingh@gmail.com">learnwithhemantsingh@gmail.com</a><span>India (IST)</span><span>Mon - Sat: 9:00 AM - 8:00 PM</span></div></div></div><div class="container v2-footer-bottom"><span>© 2026 Learn with Hemant. All rights reserved.</span><div class="v2-footer-bottom-links"><a href="/privacy.html">Privacy Policy</a><a href="/terms.html">Terms of Use</a><a href="/refund.html">Refund Policy</a><a href="/contact/">Contact</a></div></div></footer><script>(function(){const toggle=document.querySelector('.mobile-menu-toggle');const menu=document.getElementById('mobileSiteMenu');const backdrop=document.querySelector('.mobile-menu-backdrop');const closeItems=document.querySelectorAll('[data-mobile-menu-close]');const links=document.querySelectorAll('.mobile-menu-links a');if(!toggle||!menu||!backdrop)return;function openMenu(){document.body.classList.add('mobile-menu-open');toggle.setAttribute('aria-expanded','true');menu.setAttribute('aria-hidden','false')}function closeMenu(){document.body.classList.remove('mobile-menu-open');toggle.setAttribute('aria-expanded','false');menu.setAttribute('aria-hidden','true')}toggle.addEventListener('click',openMenu);closeItems.forEach(item=>item.addEventListener('click',closeMenu));links.forEach(link=>link.addEventListener('click',closeMenu));document.addEventListener('keydown',function(event){if(event.key==='Escape')closeMenu()})})();</script>'''


def related_jobs(job: Dict[str, Any], active_jobs: List[Dict[str, Any]], limit: int = 3) -> List[Dict[str, Any]]:
    current_slug = clean(job.get("slug"))
    state = clean(job.get("state")).lower()
    typ = clean(job.get("type")).lower()
    tags = set(re.findall(r"[a-z0-9]+", clean(job.get("profile_tags")).lower()))
    ranked = []
    for candidate in active_jobs:
        if clean(candidate.get("slug")) == current_slug:
            continue
        score = 0
        if state and state == clean(candidate.get("state")).lower():
            score += 4
        if typ and typ == clean(candidate.get("type")).lower():
            score += 3
        candidate_tags = set(re.findall(r"[a-z0-9]+", clean(candidate.get("profile_tags")).lower()))
        score += min(3, len(tags & candidate_tags))
        ranked.append((score, clean(candidate.get("last_date_iso")) or "9999-12-31", candidate))
    ranked.sort(key=lambda item: (-item[0], item[1], clean(item[2].get("job")).lower()))
    return [item[2] for item in ranked[:limit]]


def related_html(job: Dict[str, Any], active_jobs: List[Dict[str, Any]]) -> str:
    items = related_jobs(job, active_jobs)
    if not items:
        return '<p>No related active vacancy is currently available. Check the main government jobs page regularly.</p>'
    cards = []
    for item in items:
        cards.append(f'''<a class="job-related-card" href="/jobs/{esc(item.get('slug'))}/"><strong>{esc(item.get('job'))}</strong><span>{esc(item.get('state') or 'India')} • {esc(item.get('type') or 'Government')}</span><small>{esc(item.get('last_date_display') or 'Check official notice')}</small></a>''')
    return '<div class="job-related-grid">' + ''.join(cards) + '</div>'


def detail_page(job: Dict[str, Any], active_jobs: List[Dict[str, Any]]) -> str:
    title = clean(job.get("job")) or "Government Job Notice"
    slug = clean(job.get("slug"))
    canonical = f"{BASE}/jobs/{slug}/"
    state = clean(job.get("state")) or "India"
    agency = clean(job.get("agency") or job.get("subtitle")) or "Official recruitment source"
    typ = clean(job.get("type")) or "Government"
    archived = is_archived(job)
    status = "Application Closed" if archived and clean(job.get("status")).lower() == "closed" else (clean(job.get("status_label") or job.get("status")) or "Watch")
    status_c = "avoid" if archived else status_class(job)
    last = clean(job.get("last_date_display")) or "Check official notice"
    tags = clean(job.get("profile_tags")) or "Verify from official notice"
    eligible = clean(job.get("eligible_for")) or "Check official notification before applying."
    why = clean(job.get("fit_reason") or job.get("why")) or detail_positioning(job)
    verified = clean(job.get("verified_on") or job.get("last_seen_at")) or "Recently verified"
    notice = clean(job.get("notification_link") or job.get("official_link"))
    apply = "" if archived else clean(job.get("apply_link") or job.get("official_link"))
    meta = meta_desc(job)
    schema = {"@context": "https://schema.org", "@type": "WebPage", "name": f"{title} - {'Archived' if archived else 'Details'}", "description": meta, "url": canonical, "isPartOf": {"@type": "WebSite", "name": "Learn with Hemant", "url": BASE}, "about": {"@type": "Thing", "name": title}}
    breadcrumb = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "Home", "item": BASE + "/home/"}, {"@type": "ListItem", "position": 2, "name": "Government Jobs", "item": BASE + "/jobs/"}, {"@type": "ListItem", "position": 3, "name": title, "item": canonical}]}
    facts = [("Job Title", title), ("Agency / Source", agency), ("State / Region", state), ("Role Type", typ), ("Eligibility", eligible), ("Profile Tags", tags), ("Status", status), ("Last Date", last), ("Verified On", verified), ("Contact Details", clean(job.get("contact") or job.get("contact_details")) or "Use official notice / recruitment portal")]
    fact_html = ''.join(f'<div><span>{esc(k)}</span><strong>{esc(v)}</strong></div>' for k, v in facts)
    actions = ''
    if notice:
        label = "View Archived Official Notice" if archived else clean(job.get("notification_label")) or "Official Notice"
        actions += f'<a class="official-link notice-link" href="{esc(notice)}" target="_blank" rel="noopener">{esc(label)}</a>'
    if apply:
        label = clean(job.get("apply_label") or job.get("official_label")) or "Apply / Check"
        actions += f'<a class="official-link" href="{esc(apply)}" target="_blank" rel="noopener">{esc(label)}</a>'
    if not actions:
        actions = '<a class="official-link muted-link" href="/jobs/">View Active Jobs</a>'
    closed_banner = '<div class="job-closed-banner"><strong>Application Closed</strong><span>This URL is retained as a historical record and is no longer listed among active vacancies.</span></div>' if archived else ''
    return f'''<!DOCTYPE html><html lang="en"><head><meta name="msvalidate.01" content="4F051335E3D7ED544E20B8292B4E66BD"/><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/><title>{esc(title)} | {'Application Closed' if archived else 'Eligibility, Last Date, Official Link'} | Learn with Hemant</title><meta name="description" content="{esc(meta)}"/><link rel="canonical" href="{esc(canonical)}"/><link rel="preconnect" href="https://fonts.googleapis.com"/><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&amp;display=swap" rel="stylesheet"/><link href="/style.css" rel="stylesheet"/><link href="/brand-logo.png" rel="icon" type="image/png"/><script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script><script type="application/ld+json">{json.dumps(breadcrumb, ensure_ascii=False)}</script></head><body class="home-v2-body jobs-dashboard-body govt-job-detail-body">{header_html()}<main class="jobs-dashboard-main govt-detail-main"><section class="jobs-table-section"><div class="container"><article class="jobs-panel govt-detail-shell"><a class="faculty-back-link" href="{'/jobs/archive/' if archived else '/jobs/'}">← Back to {'Closed' if archived else 'Active'} Govt Jobs</a>{closed_banner}<div class="govt-detail-hero-card"><div><span class="jobs-mini-eyebrow govt-detail-eyebrow">{esc(status)}</span><h1>{esc(title)}</h1><p class="faculty-detail-subtitle">{esc(agency)} • {esc(state)} • {esc(typ)}</p></div><div class="govt-detail-status-box"><span>Status</span><strong class="fit-badge {esc(status_c)}">{esc(status)}</strong><small>{esc(last)}</small></div></div><div class="govt-detail-grid-main"><section class="govt-detail-content-card"><h2>Quick Details</h2><div class="faculty-detail-grid govt-detail-facts">{fact_html}</div><h2>Eligibility and Profile Fit</h2><p>{esc(why)}</p><p>{esc(detail_positioning(job))}</p><h2>CSE / IT Decision Note</h2><p>{esc(role_focus(job))}</p><h2>What to Verify</h2><ul class="govt-detail-checklist"><li>Match your qualification, branch, percentage and subject code with the official notification.</li><li>Confirm age limit, category relaxation, fee, documents and experience requirements.</li><li>For archived pages, do not assume applications are still accepted.</li><li>Keep a copy of the notification PDF and application receipt after applying.</li></ul></section><aside class="govt-detail-side-card"><h2>Official Verification</h2><p>The legal source of truth remains the official notification or recruitment portal.</p><div class="faculty-detail-actions govt-detail-actions">{actions}</div></aside></div><section class="related-active-jobs"><h2>Related Active Vacancies</h2>{related_html(job, active_jobs)}</section><div class="faculty-related-links"><a href="/jobs/">All Active Govt Jobs</a><a href="/jobs/archive/">Closed Govt Jobs</a><a href="/jobs/faculty-jobs/">Faculty Jobs</a></div></article></div></section></main>{footer_html()}</body></html>'''


def static_rows(jobs: Iterable[Dict[str, Any]]) -> str:
    rows = []
    for job in jobs:
        link = clean(job.get("detail_url")) or f"/jobs/{clean(job.get('slug'))}/"
        title = clean(job.get("job")) or "Government Job Notice"
        sub = clean(job.get("subtitle") or job.get("agency")) or "Official recruitment source"
        eligible = clean(job.get("eligible_for")) or "Check official notification before applying."
        typ = clean(job.get("type")) or "Computer/IT"
        status = clean(job.get("status")) or "Watch"
        status_label = clean(job.get("status_label")) or status
        last_iso = clean(job.get("last_date_iso"))
        last_disp = clean(job.get("last_date_display")) or "Check official notice"
        tags = clean(job.get("profile_tags"))
        sc = status_class(job)
        notice = clean(job.get("notification_link") or job.get("official_link")) or "#"
        apply = clean(job.get("apply_link") or job.get("official_link")) or "#"
        left = days_left(last_iso)
        left_html = f'<span class="deadline-note">{esc(left)}</span>' if left else ''
        rows.append(f'''<tr data-last="{esc(last_iso)}" data-status="{esc(status)}" data-tags="{esc(tags)}" data-type="{esc(typ)}"><td data-label="Job"><a class="govt-job-title-link" href="{esc(link)}"><strong>{esc(title)}</strong></a><span>{esc(sub)}</span></td><td data-label="Eligible For">{esc(eligible)}</td><td data-label="Type">{esc(typ)}</td><td data-label="Status"><span class="fit-badge {esc(sc)}">{esc(status_label)}</span></td><td data-label="Last Date"><strong>{esc(last_disp)}</strong>{left_html}</td><td data-label="Official Links"><div class="official-links-stack"><a class="official-link notice-link" href="{esc(notice)}" rel="noopener" target="_blank">Notice</a><a class="official-link" href="{esc(apply)}" rel="noopener" target="_blank">Apply</a></div></td></tr>''')
    return '\n'.join(rows)


def archive_page(jobs: List[Dict[str, Any]]) -> str:
    cards = []
    for job in jobs:
        cards.append(f'''<article class="archive-job-card"><span>Application Closed</span><h2><a href="/jobs/{esc(job.get('slug'))}/">{esc(job.get('job') or 'Government Job')}</a></h2><p>{esc(job.get('agency') or job.get('subtitle') or 'Official recruitment source')} • {esc(job.get('state') or 'India')}</p><small>Last date: {esc(job.get('last_date_display') or 'Not available')}</small></article>''')
    body = ''.join(cards) or '<p>No closed government jobs are currently stored in the archive.</p>'
    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/><title>Closed Government Jobs Archive | Learn with Hemant</title><meta name="description" content="Historical government job pages retained after their application deadlines, with links to current CSE and IT vacancies."/><link rel="canonical" href="{BASE}/jobs/archive/"/><link href="/style.css" rel="stylesheet"/><link href="/brand-logo.png" rel="icon" type="image/png"/></head><body class="home-v2-body jobs-dashboard-body">{header_html()}<main class="jobs-dashboard-main"><section class="jobs-table-section"><div class="container"><div class="jobs-panel archive-jobs-shell"><span class="jobs-mini-eyebrow">Historical records</span><h1>Closed Government Jobs Archive</h1><p>Expired job URLs are retained instead of being deleted. These pages are for reference only; use the active jobs page before applying.</p><div class="archive-job-grid">{body}</div><div class="faculty-related-links"><a href="/jobs/">View Active Government Jobs</a><a href="/jobs/faculty-jobs/">View Faculty Jobs</a></div></div></div></section></main>{footer_html()}</body></html>'''


def write_sitemap(path: Path, urls: Iterable[str], *, changefreq: str, priority: str) -> None:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in sorted(set(urls)):
        lines.extend(['  <url>', f'    <loc>{BASE}{url}</loc>', f'    <lastmod>{TODAY.isoformat()}</lastmod>', f'    <changefreq>{changefreq}</changefreq>', f'    <priority>{priority}</priority>', '  </url>'])
    lines.append('</urlset>')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def update_robots() -> None:
    robots = ROOT / 'robots.txt'
    text = robots.read_text(encoding='utf-8') if robots.exists() else ''
    for line in [f'Sitemap: {BASE}/sitemap-govt-jobs.xml', f'Sitemap: {BASE}/sitemap-job-archive.xml']:
        if line not in text:
            text = text.rstrip() + '\n' + line + '\n'
    robots.write_text(text, encoding='utf-8')


def update_main_sitemap(active_jobs: List[Dict[str, Any]]) -> None:
    path = ROOT / 'sitemap.xml'
    if not path.exists():
        return
    text = path.read_text(encoding='utf-8')
    # Remove generated government detail URLs while preserving /jobs/, /jobs/archive/ and faculty URLs.
    text = re.sub(r'\s*<url>\s*<loc>https://learnwithhemant\.com/jobs/(?!faculty-jobs/|archive/|</loc>)[^<]+</loc>.*?</url>', '', text, flags=re.S)
    entries = []
    wanted = ['/jobs/', '/jobs/archive/'] + [f"/jobs/{clean(job.get('slug'))}/" for job in active_jobs]
    for url in wanted:
        loc = BASE + url
        if loc in text:
            continue
        entries.append(f'''  <url>\n    <loc>{loc}</loc>\n    <lastmod>{TODAY.isoformat()}</lastmod>\n    <changefreq>{'daily' if url != '/jobs/archive/' else 'weekly'}</changefreq>\n    <priority>{'0.82' if url == '/jobs/' else '0.70' if url == '/jobs/archive/' else '0.74'}</priority>\n  </url>''')
    if entries and '</urlset>' in text:
        text = text.replace('</urlset>', '\n' + '\n'.join(entries) + '\n</urlset>')
    path.write_text(text, encoding='utf-8')


def add_css() -> None:
    css_path = ROOT / 'style.css'
    css = css_path.read_text(encoding='utf-8')
    marker = 'Job archive and related vacancy components'
    if marker in css:
        return
    css += '''\n\n/* Job archive and related vacancy components */
.job-closed-banner{display:flex;gap:12px;align-items:center;justify-content:space-between;margin:18px 0;padding:15px 18px;border:1px solid #fecaca;background:#fff1f2;border-radius:16px;color:#9f1239}.job-closed-banner strong{font-size:16px}.job-closed-banner span{font-weight:650}.related-active-jobs{margin-top:24px;border-top:1px solid #e5e7eb;padding-top:22px}.job-related-grid,.archive-job-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.job-related-card,.archive-job-card{display:grid;gap:8px;border:1px solid #dce6f3;border-radius:18px;padding:16px;background:#fff;text-decoration:none}.job-related-card strong,.archive-job-card h2{color:#101828;margin:0;font-size:16px}.job-related-card span,.archive-job-card p{color:#475467;margin:0}.job-related-card small,.archive-job-card small{color:#667085;font-weight:750}.archive-job-card>span{color:#b42318;font-size:12px;font-weight:900;text-transform:uppercase}.archive-job-card a{color:inherit;text-decoration:none}.archive-job-card a:hover{text-decoration:underline}.archive-jobs-shell{padding:28px}.archive-jobs-shell>p{color:#475467;max-width:850px;line-height:1.65}.fit-badge.closed{background:#fff1f2;color:#b42318;border-color:#fecdd3}@media(max-width:900px){.job-related-grid,.archive-job-grid{grid-template-columns:1fr 1fr}}@media(max-width:620px){.job-related-grid,.archive-job-grid{grid-template-columns:1fr}.job-closed-banner{align-items:flex-start;flex-direction:column}}\n'''
    css_path.write_text(css, encoding='utf-8')


def main() -> None:
    payload = load_json_payload(DATA)
    archive_payload = load_json_payload(ARCHIVE_DATA)
    active_jobs = list(payload.get('jobs') or [])
    archived_jobs = list(archive_payload.get('jobs') or [])
    used = set()
    ensure_slugs(active_jobs, used)
    ensure_slugs(archived_jobs, used)
    payload['jobs'] = active_jobs
    archive_payload['jobs'] = archived_jobs
    DATA.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    ARCHIVE_DATA.parent.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DATA.write_text(json.dumps(archive_payload, indent=2, ensure_ascii=False), encoding='utf-8')

    for job in active_jobs + archived_jobs:
        out = ROOT / 'jobs' / clean(job.get('slug')) / 'index.html'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(detail_page(job, active_jobs), encoding='utf-8')

    index_path = ROOT / 'jobs' / 'index.html'
    index = index_path.read_text(encoding='utf-8')
    index = re.sub(r'<tbody id="jobsTableBody">.*?</tbody>', '<tbody id="jobsTableBody">\n' + static_rows(active_jobs) + '\n</tbody>', index, flags=re.S)
    if 'href="/jobs/archive/"' not in index:
        index = index.replace('<div class="jobs-panel-actions">', '<div class="jobs-panel-actions"><a class="jobs-suggest-btn" href="/jobs/archive/">Closed Jobs Archive</a>', 1)
    index_path.write_text(index, encoding='utf-8')

    archive_dir = ROOT / 'jobs' / 'archive'
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.joinpath('index.html').write_text(archive_page(archived_jobs), encoding='utf-8')

    active_urls = ['/jobs/'] + [f"/jobs/{clean(job.get('slug'))}/" for job in active_jobs]
    recent_archived = archive_sitemap_jobs(archived_jobs, RETENTION_DAYS, TODAY)
    archive_urls = ['/jobs/archive/'] + [f"/jobs/{clean(job.get('slug'))}/" for job in recent_archived]
    write_sitemap(ROOT / 'sitemap-govt-jobs.xml', active_urls, changefreq='daily', priority='0.74')
    write_sitemap(ROOT / 'sitemap-job-archive.xml', archive_urls, changefreq='monthly', priority='0.55')
    update_robots()
    update_main_sitemap(active_jobs)
    add_css()
    print(f"[OK] Generated {len(active_jobs)} active and {len(archived_jobs)} archived government job pages")


if __name__ == '__main__':
    main()
