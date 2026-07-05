from pathlib import Path
import json, re, html, datetime as dt

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'jobs/jobs-data.json'
BASE='https://learnwithhemant.com'
TODAY=dt.date.today().isoformat()

def clean(v):
    if v is None: return ''
    return ' '.join(str(v).strip().split())

def esc(v): return html.escape(clean(v), quote=True)

def slugify(value, fallback='government-job'):
    s=clean(value).lower().replace('&',' and ')
    s=re.sub(r'[^a-z0-9]+','-',s)
    s=re.sub(r'-+','-',s).strip('-')
    return s[:88].strip('-') or fallback

def ensure_slugs(jobs):
    seen=set()
    for job in jobs:
        existing=clean(job.get('slug'))
        base=slugify(existing or f"{job.get('job','')} {job.get('state','')} {job.get('type','')} 2026")
        slug=base
        i=2
        while slug in seen:
            slug=f"{base[:82].strip('-')}-{i}"
            i+=1
        seen.add(slug)
        job['slug']=slug
        job['detail_url']=f"/jobs/{slug}/"

def days_left(date_string):
    if not date_string: return ''
    try: d=dt.date.fromisoformat(date_string)
    except Exception: return ''
    diff=(d-dt.date.today()).days
    if diff < 0: return 'Closed'
    if diff == 0: return 'Closing today'
    if diff == 1: return '1 day left'
    return f'{diff} days left'

def status_class(job):
    c=clean(job.get('status_class')).lower()
    return c if c in {'good','doubtful','caution','avoid','watch'} else 'watch'

def detail_positioning(job):
    status=clean(job.get('status'))
    typ=clean(job.get('type'))
    eligible=clean(job.get('eligible_for'))
    if status == 'Good Match':
        return f"This listing is marked as a good match because the available eligibility note fits the stated route: {eligible}. Use it as a shortlisting signal, not as final confirmation."
    if status == 'Avoid':
        return f"This listing is marked as avoid for a CSE/IT-focused candidate because the eligibility note says: {eligible}. Keep it only for reference unless the official notice proves your qualification is accepted."
    if status == 'Doubtful':
        return "This listing needs manual verification. The role may look relevant from the title or department, but the eligibility, subject code, age limit or experience condition can change the final decision."
    if typ == 'Teaching':
        return "This is being tracked as a teaching route. Verify subject, NET/SET/PhD requirement, marks percentage and institution-specific rules from the official notice."
    if 'IT' in typ or 'Computer' in typ:
        return "This is being tracked as a possible computer/IT route. Confirm whether B.Tech CSE, M.Tech CSE, MCA or BCA is explicitly accepted for the exact post."
    return "This is being tracked as a watchlist opportunity. Open the official notice first, then confirm whether the job title, qualification and age rules match your profile."

def role_focus(job):
    typ=clean(job.get('type')) or 'Government'
    tags=clean(job.get('profile_tags'))
    if tags:
        return f"The dashboard currently tags this opening for: {tags}. These tags are only a quick filter and should be verified from the official recruitment PDF."
    if typ == 'Office':
        return "This appears closer to an office/general recruitment path than a pure software development job. Check the exact post list before spending time on the application."
    if typ == 'Teaching':
        return "For teaching roles, subject eligibility matters more than the broad title. Confirm the Computer Science / IT subject code and qualification norms."
    if 'Computer' in typ or 'IT' in typ:
        return "For technical roles, verify whether the department asks for Computer Science, Information Technology, Computer Applications or another equivalent branch."
    return "The profile fit depends on the detailed notification. Do not rely only on the short title shown in the tracker."

def meta_desc(job):
    title=clean(job.get('job')) or 'Government job'
    state=clean(job.get('state')) or 'India'
    eligible=clean(job.get('eligible_for')) or 'Check eligibility'
    return f"{title} details for {state}: eligibility, status, last date, official notice and apply link for CSE/IT candidates. {eligible}"[:158]

def header_html():
    return '''<header class="site-header home-v2-header">
<div class="container nav home-v2-nav">
<a class="brand home-v2-brand" href="/home/"><img alt="Learn with Hemant logo" class="brand-logo" src="/brand-logo.png"/><div><span>Learn with Hemant</span><small>Build • Deploy • Grow</small></div></a>
<nav aria-label="Main Navigation" class="nav-links home-v2-links"><a href="/about/">Mentor</a><a href="/courses/web-development/">Courses</a><a href="/projects/">Projects</a><a href="/guest-lecture/">Guest Lecture</a><a href="/tool/">Tool</a><a class="active-nav-link" href="/jobs/">Govt Jobs</a></nav>
<a class="nav-cta home-v2-cta" href="/apply/">Apply Now <span>→</span></a><button aria-controls="mobileSiteMenu" aria-expanded="false" aria-label="Open menu" class="mobile-menu-toggle" type="button"><span></span><span></span><span></span></button>
</div></header>
<div class="mobile-menu-backdrop" data-mobile-menu-close=""></div><aside aria-hidden="true" class="mobile-site-menu" id="mobileSiteMenu"><div class="mobile-menu-head"><a class="mobile-menu-brand" href="/home/"><img alt="Learn with Hemant logo" src="/brand-logo.png"/></a><button aria-label="Close menu" class="mobile-menu-close" data-mobile-menu-close="" type="button">×</button></div><nav aria-label="Mobile navigation" class="mobile-menu-links"><a href="/home/">Home</a><a href="/about/">Mentor</a><a href="/courses/web-development/">Courses</a><a href="/projects/">Projects</a><a href="/guest-lecture/">Guest Lecture</a><a href="/tool/">Tool</a><a href="/jobs/">Govt Jobs</a><a href="/jobs/faculty-jobs/">Faculty Jobs</a><a href="/apply/">Apply Now</a><a href="https://wa.me/918197565002?text=Hi%20Hemant%2C%20I%20want%20CSE%20govt%20job%20updates." rel="noopener" target="_blank">WhatsApp Updates</a></nav></aside>'''

def footer_html():
    return '''<footer class="site-footer v2-footer"><div class="container v2-footer-grid"><div class="v2-footer-brand"><div class="brand home-v2-brand footer-brand-row"><img class="brand-logo" src="/brand-logo.png" alt="Learn with Hemant logo"/><div><span>Learn with Hemant</span><small>Helping beginners become confident developers through practical training.</small></div></div></div><div><h3>Quick Links</h3><div class="v2-footer-links"><a href="/about/">Mentor</a><a href="/roadmap/">Roadmap</a><a href="/courses/web-development/">Courses</a><a href="/projects/">Projects</a><a href="/guest-lecture/">Guest Lecture</a><a href="/apply/">Free Demo</a></div></div><div><h3>Jobs</h3><div class="v2-footer-links"><a href="/jobs/">CSE Govt Jobs</a><a href="/jobs/faculty-jobs/">Faculty Jobs</a><a href="/jobs/faculty-jobs/cse/">CSE Faculty Jobs</a><a href="/jobs/faculty-jobs/rajasthan/">Rajasthan Faculty Jobs</a></div></div><div><h3>Connect</h3><div class="v2-footer-links"><a href="https://wa.me/918197565002?text=Hi%20Hemant%2C%20I%20want%20CSE%20govt%20job%20updates." target="_blank" rel="noopener">WhatsApp Updates</a><a href="mailto:learnwithhemantsingh@gmail.com">learnwithhemantsingh@gmail.com</a><span>India (IST)</span><span>Mon - Sat: 9:00 AM - 8:00 PM</span></div></div></div><div class="container v2-footer-bottom"><span>© 2026 Learn with Hemant. All rights reserved.</span><div class="v2-footer-bottom-links"><a href="/privacy.html">Privacy Policy</a><a href="/terms.html">Terms of Use</a><a href="/refund.html">Refund Policy</a><a href="/contact/">Contact</a></div></div></footer><script>(function(){const toggle=document.querySelector('.mobile-menu-toggle');const menu=document.getElementById('mobileSiteMenu');const backdrop=document.querySelector('.mobile-menu-backdrop');const closeItems=document.querySelectorAll('[data-mobile-menu-close]');const links=document.querySelectorAll('.mobile-menu-links a');if(!toggle||!menu||!backdrop)return;function openMenu(){document.body.classList.add('mobile-menu-open');toggle.setAttribute('aria-expanded','true');menu.setAttribute('aria-hidden','false')}function closeMenu(){document.body.classList.remove('mobile-menu-open');toggle.setAttribute('aria-expanded','false');menu.setAttribute('aria-hidden','true')}toggle.addEventListener('click',openMenu);closeItems.forEach(item=>item.addEventListener('click',closeMenu));links.forEach(link=>link.addEventListener('click',closeMenu));document.addEventListener('keydown',function(event){if(event.key==='Escape')closeMenu()})})();</script>'''

def detail_page(job):
    title=clean(job.get('job')) or 'Government Job Notice'
    slug=clean(job.get('slug'))
    canonical=f"{BASE}/jobs/{slug}/"
    state=clean(job.get('state')) or 'India'
    agency=clean(job.get('agency') or job.get('subtitle')) or 'Official recruitment source'
    typ=clean(job.get('type')) or 'Government'
    status=clean(job.get('status_label') or job.get('status')) or 'Watch'
    status_c=status_class(job)
    last=clean(job.get('last_date_display')) or 'Check official notice'
    tags=clean(job.get('profile_tags')) or 'Verify from official notice'
    eligible=clean(job.get('eligible_for')) or 'Check official notification before applying.'
    why=clean(job.get('fit_reason') or job.get('why')) or detail_positioning(job)
    verified=clean(job.get('verified_on')) or 'Recently verified'
    notice=clean(job.get('notification_link') or job.get('official_link'))
    apply=clean(job.get('apply_link') or job.get('official_link'))
    notice_label=clean(job.get('notification_label')) or 'Official Notice'
    apply_label=clean(job.get('apply_label') or job.get('official_label')) or 'Apply / Check'
    meta=meta_desc(job)
    schema={"@context":"https://schema.org","@type":"WebPage","name":f"{title} - Details","description":meta,"url":canonical,"isPartOf":{"@type":"WebSite","name":"Learn with Hemant","url":BASE},"about":{"@type":"Thing","name":title}}
    breadcrumb={"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Home","item":BASE+"/home/"},{"@type":"ListItem","position":2,"name":"Government Jobs","item":BASE+"/jobs/"},{"@type":"ListItem","position":3,"name":title,"item":canonical}]}
    facts=[('Job Title',title),('Agency / Source',agency),('State / Region',state),('Role Type',typ),('Eligibility',eligible),('Profile Tags',tags),('Status',status),('Last Date',last),('Verified On',verified),('Contact Details',clean(job.get('contact') or job.get('contact_details')) or 'Use official notice / recruitment portal')]
    fact_html='\n'.join(f'<div><span>{esc(k)}</span><strong>{esc(v)}</strong></div>' for k,v in facts)
    actions=''
    if notice: actions += f'<a class="official-link notice-link" href="{esc(notice)}" target="_blank" rel="noopener">{esc(notice_label)}</a>'
    if apply: actions += f'<a class="official-link" href="{esc(apply)}" target="_blank" rel="noopener">{esc(apply_label)}</a>'
    if not actions: actions='<a class="official-link muted-link" href="/jobs/">Back to Jobs</a>'
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta name="msvalidate.01" content="4F051335E3D7ED544E20B8292B4E66BD"/><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/><title>{esc(title)} | Eligibility, Last Date, Official Link | Learn with Hemant</title><meta name="description" content="{esc(meta)}"/><link rel="canonical" href="{esc(canonical)}"/><link rel="preconnect" href="https://fonts.googleapis.com"/><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&amp;display=swap" rel="stylesheet"/><link href="/style.css" rel="stylesheet"/><link href="/brand-logo.png" rel="icon" type="image/png"/><link href="/brand-logo.png" rel="apple-touch-icon"/><script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script><script type="application/ld+json">{json.dumps(breadcrumb, ensure_ascii=False)}</script></head>
<body class="home-v2-body jobs-dashboard-body govt-job-detail-body">{header_html()}<main class="jobs-dashboard-main govt-detail-main"><section class="jobs-table-section"><div class="container"><article class="jobs-panel govt-detail-shell"><a class="faculty-back-link" href="/jobs/">← Back to Govt Jobs</a><div class="govt-detail-hero-card"><div><span class="jobs-mini-eyebrow govt-detail-eyebrow">{esc(status)}</span><h1>{esc(title)}</h1><p class="faculty-detail-subtitle">{esc(agency)} • {esc(state)} • {esc(typ)}</p></div><div class="govt-detail-status-box"><span>Status</span><strong class="fit-badge {esc(status_c)}">{esc(status)}</strong><small>{esc(last)}</small></div></div><div class="govt-detail-grid-main"><section class="govt-detail-content-card"><h2>Quick Details</h2><div class="faculty-detail-grid govt-detail-facts">{fact_html}</div><h2>Eligibility and Profile Fit</h2><p>{esc(why)}</p><p>{esc(detail_positioning(job))}</p><h2>CSE / IT Decision Note</h2><p>{esc(role_focus(job))}</p><h2>What to Verify Before Applying</h2><ul class="govt-detail-checklist"><li>Match your exact qualification, branch, percentage and subject code with the official notification.</li><li>Confirm age limit, category relaxation, fee, documents and experience requirement before final submission.</li><li>Check the last date and application mode on the official portal, especially if the tracker shows a watchlist entry.</li><li>Keep a copy of the notification PDF, application receipt and payment receipt after applying.</li></ul></section><aside class="govt-detail-side-card"><h2>Official Verification</h2><p>This page restructures the vacancy into an easy decision format. The legal source of truth remains the official notification or recruitment portal.</p><div class="faculty-detail-actions govt-detail-actions">{actions}</div><div class="govt-detail-mini-note"><strong>Meaning unchanged:</strong> job title, eligibility, status, last date and official links are kept from the dashboard data. Only the explanation format is rewritten for readability and SEO.</div></aside></div><div class="faculty-related-links"><a href="/jobs/">All Govt Jobs</a><a href="/jobs/faculty-jobs/">Faculty Jobs</a><a href="/jobs/faculty-jobs/cse/">CSE Faculty Jobs</a></div></article></div></section></main>{footer_html()}</body></html>'''

def static_rows(jobs):
    rows=[]
    for job in jobs:
        link=clean(job.get('detail_url')) or f"/jobs/{clean(job.get('slug'))}/"
        title=clean(job.get('job')) or 'Government Job Notice'
        sub=clean(job.get('subtitle') or job.get('agency')) or 'Official recruitment source'
        eligible=clean(job.get('eligible_for')) or 'Check official notification before applying.'
        typ=clean(job.get('type')) or 'Computer/IT'
        status=clean(job.get('status')) or 'Watch'
        status_label=clean(job.get('status_label')) or status
        last_iso=clean(job.get('last_date_iso'))
        last_disp=clean(job.get('last_date_display')) or 'Check official notice'
        tags=clean(job.get('profile_tags'))
        sc=status_class(job)
        notice=clean(job.get('notification_link') or job.get('official_link')) or '#'
        apply=clean(job.get('apply_link') or job.get('official_link')) or '#'
        nlabel=clean(job.get('notification_label')) or 'Notice'
        alabel=clean(job.get('apply_label') or job.get('official_label')) or 'Apply'
        apply_class='official-link muted-link' if status == 'Avoid' else 'official-link'
        left=days_left(last_iso)
        left_html=f'<span class="deadline-note">{esc(left)}</span>' if left else ''
        rows.append(f'''<tr data-last="{esc(last_iso)}" data-status="{esc(status)}" data-tags="{esc(tags)}" data-type="{esc(typ)}"><td data-label="Job"><a class="govt-job-title-link" href="{esc(link)}"><strong>{esc(title)}</strong></a><span>{esc(sub)}</span></td><td data-label="Eligible For">{esc(eligible)}</td><td data-label="Type">{esc(typ)}</td><td data-label="Status"><span class="fit-badge {esc(sc)}">{esc(status_label)}</span></td><td data-label="Last Date"><strong>{esc(last_disp)}</strong>{left_html}</td><td data-label="Official Links"><div class="official-links-stack"><a class="official-link notice-link" href="{esc(notice)}" rel="noopener" target="_blank">{esc(nlabel)}</a><a class="{esc(apply_class)}" href="{esc(apply)}" rel="noopener" target="_blank">{esc(alabel)}</a></div></td></tr>''')
    return '\n'.join(rows)

payload=json.loads(DATA.read_text(encoding='utf-8'))
jobs=payload.get('jobs') or []
ensure_slugs(jobs)
DATA.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
for job in jobs:
    out=ROOT/'jobs'/job['slug']/'index.html'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(detail_page(job), encoding='utf-8')

# index update
idx=ROOT/'jobs/index.html'
index=idx.read_text(encoding='utf-8')
index=re.sub(r'<tbody id="jobsTableBody">.*?</tbody>', '<tbody id="jobsTableBody">\n'+static_rows(jobs)+'\n</tbody>', index, flags=re.S)
old="""        const jobCell = document.createElement('td');
        jobCell.dataset.label = 'Job';
        const title = document.createElement('strong');
        title.textContent = job.job || 'Government Job Notice';
        const subtitle = document.createElement('span');
        subtitle.textContent = job.subtitle || job.agency || 'Official recruitment source';
        jobCell.append(title, subtitle);"""
new="""        const jobCell = document.createElement('td');
        jobCell.dataset.label = 'Job';
        const title = document.createElement('strong');
        title.textContent = job.job || 'Government Job Notice';
        const subtitle = document.createElement('span');
        subtitle.textContent = job.subtitle || job.agency || 'Official recruitment source';
        const detailUrl = job.detail_url || job.detail_path || (job.slug ? '/jobs/' + job.slug + '/' : '');
        if (detailUrl) {
          const titleLink = document.createElement('a');
          titleLink.className = 'govt-job-title-link';
          titleLink.href = detailUrl;
          titleLink.setAttribute('aria-label', 'View full details for ' + title.textContent);
          titleLink.appendChild(title);
          jobCell.append(titleLink, subtitle);
        } else {
          jobCell.append(title, subtitle);
        }"""
if old in index:
    index=index.replace(old,new)
else:
    print('[WARN] Did not find expected JS block')
idx.write_text(index, encoding='utf-8')

# CSS
css_path=ROOT/'style.css'
css=css_path.read_text(encoding='utf-8')
css_add='''

/* =========================================================
   Government Job detail pages + clickable job titles
   ========================================================= */
.govt-job-title-link{display:inline-block;color:#101828;text-decoration:none;border-radius:8px;}
.govt-job-title-link:hover,.govt-job-title-link:focus{color:#2563eb;text-decoration:underline;text-underline-offset:4px;}
.govt-job-title-link strong{margin-bottom:4px;}
.govt-detail-shell{padding:28px;}
.govt-detail-hero-card{display:grid;grid-template-columns:minmax(0,1fr) 190px;gap:20px;align-items:center;border:1px solid #dce6f3;border-radius:28px;padding:24px;margin-top:18px;background:linear-gradient(135deg,#f8fbff 0%,#ffffff 54%,#eef5ff 100%);}
.govt-detail-hero-card h1{margin:30px 0 10px;font-size:clamp(30px,4vw,46px);line-height:1.12;letter-spacing:-.045em;color:#101828;}
.govt-detail-eyebrow{position:static !important;}
.govt-detail-status-box{border:1px solid #dce6f3;border-radius:22px;background:#ffffff;padding:18px;display:grid;gap:10px;justify-items:start;box-shadow:0 12px 28px rgba(16,24,40,.06);}
.govt-detail-status-box span,.govt-detail-mini-note span{color:#667085;font-size:12px;font-weight:900;text-transform:uppercase;letter-spacing:.05em;}
.govt-detail-status-box small{color:#475467;font-weight:800;}
.govt-detail-grid-main{display:grid;grid-template-columns:minmax(0,1.75fr) minmax(280px,.75fr);gap:20px;margin-top:20px;}
.govt-detail-content-card,.govt-detail-side-card{border:1px solid #dce6f3;border-radius:24px;background:#ffffff;padding:22px;box-shadow:0 12px 28px rgba(16,24,40,.045);}
.govt-detail-content-card h2,.govt-detail-side-card h2{margin:0 0 10px;font-size:22px;line-height:1.25;letter-spacing:-.03em;color:#101828;}
.govt-detail-content-card h2:not(:first-child){margin-top:24px;}
.govt-detail-content-card p,.govt-detail-side-card p{color:#475467;font-weight:650;line-height:1.68;margin:0 0 12px;}
.govt-detail-facts{grid-template-columns:repeat(2,minmax(0,1fr));}
.govt-detail-facts div:nth-child(5),.govt-detail-facts div:nth-child(10){grid-column:1/-1;}
.govt-detail-checklist{margin:10px 0 0;padding-left:20px;color:#475467;font-weight:650;line-height:1.72;}
.govt-detail-checklist li{margin-bottom:8px;}
.govt-detail-actions{margin:14px 0 0;}
.govt-detail-mini-note{margin-top:16px;border-radius:16px;padding:14px;background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;font-size:13px;line-height:1.55;font-weight:750;}
@media(max-width:880px){.govt-detail-hero-card,.govt-detail-grid-main{grid-template-columns:1fr;}.govt-detail-status-box{justify-items:start;}}
@media(max-width:620px){.govt-detail-shell{padding:18px;}.govt-detail-hero-card{padding:18px;border-radius:22px;}.govt-detail-hero-card h1{font-size:30px;line-height:1.18;margin-top:18px;}.govt-detail-facts{grid-template-columns:1fr;}.govt-detail-facts div:nth-child(5),.govt-detail-facts div:nth-child(10){grid-column:auto;}}
'''
if 'Government Job detail pages + clickable job titles' not in css:
    css_path.write_text(css+css_add, encoding='utf-8')

# sitemaps
urls=['/jobs/']+[f"/jobs/{j['slug']}/" for j in jobs]
xml=['<?xml version="1.0" encoding="UTF-8"?>','<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for u in urls:
    xml += ['  <url>', f'    <loc>{BASE}{u}</loc>', f'    <lastmod>{TODAY}</lastmod>', '    <changefreq>daily</changefreq>', f'    <priority>{"0.82" if u=="/jobs/" else "0.74"}</priority>', '  </url>']
xml.append('</urlset>')
(ROOT/'sitemap-govt-jobs.xml').write_text('\n'.join(xml)+'\n', encoding='utf-8')
robots=ROOT/'robots.txt'
rt=robots.read_text(encoding='utf-8')
line='Sitemap: https://learnwithhemant.com/sitemap-govt-jobs.xml'
if line not in rt:
    robots.write_text(rt.rstrip()+'\n'+line+'\n', encoding='utf-8')
sitemap=ROOT/'sitemap.xml'
st=sitemap.read_text(encoding='utf-8')
insert=[]
for j in jobs:
    loc=f'{BASE}/jobs/{j["slug"]}/'
    if loc not in st:
        insert.append(f'  <url>\n    <loc>{loc}</loc>\n    <lastmod>{TODAY}</lastmod>\n    <changefreq>daily</changefreq>\n    <priority>0.74</priority>\n  </url>')
if insert and '</urlset>' in st:
    sitemap.write_text(st.replace('</urlset>','\n'+'\n'.join(insert)+'\n</urlset>'), encoding='utf-8')

print('[OK] Generated govt job detail pages:', len(jobs))
