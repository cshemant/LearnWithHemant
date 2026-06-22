function countMatches(text, list) {
  const lower = String(text || '').toLowerCase();
  return list.filter(item => new RegExp('\\b' + item.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b', 'i').test(lower)).length;
}

function matchedTerms(text, list) {
  const lower = String(text || '').toLowerCase();
  return list.filter(item => new RegExp('\\b' + item.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b', 'i').test(lower));
}

function hasAny(text, patterns) {
  return patterns.some(pattern => pattern.test(text));
}

function dedupe(list) {
  return [...new Set(list)];
}

function normalizeResumeText(text) {
  return String(text || '')
    .replace(/\u0000/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function wordCountOf(text) {
  return normalizeResumeText(text).split(/\s+/).filter(Boolean).length;
}

export function validateResumeText(text) {
  const normalized = normalizeResumeText(text).slice(0, 30000);
  const wordCount = wordCountOf(normalized);
  if (wordCount < 40) {
    const error = new Error('Not enough readable resume text found. Upload a text-based PDF/DOCX or paste resume text manually.');
    error.status = 400;
    throw error;
  }
  return normalized;
}

export function getAdvancedPreview() {
  return [
    { title: 'ATS & Resume Parsing Check', short: 'Checks contact visibility, sections, readability and parsing risk.' },
    { title: 'Project Proof Score', short: 'Reviews projects, live links, GitHub proof, features and deployment signals.' },
    { title: 'Skills Match Score', short: 'Detects technical skills, missing job-ready skills and skill clustering quality.' },
    { title: 'Experience / Internship / Training Review', short: 'Checks exposure, timeline clarity, practical training and proof.' },
    { title: 'Impact & Achievement Check', short: 'Finds weak verbs, missing numbers and duty-based bullet points.' },
    { title: 'Red Flags', short: 'Highlights role confusion, weak links, missing proof and ATS risks.' },
    { title: 'Priority Improvement Plan', short: 'Gives high, medium and low priority fixes.' },
    { title: 'Suggested Resume Rewrite Examples', short: 'Shows old vs better bullet examples.' },
    { title: '7-Day and 30-Day Career Roadmap', short: 'Gives a practical short-term improvement plan.' }
  ];
}

export function analyzeResume(inputText, options = {}) {
  const text = validateResumeText(inputText);
  const lower = text.toLowerCase();
  const words = text.trim().split(/\s+/).filter(Boolean);
  const wordCount = words.length;
  const strengths = [];
  const negatives = [];
  const improvements = [];
  const categories = [];
  const facts = {};

  const emailFound = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i.test(text);
  const phoneFound = /(\+?91[-\s]?)?[6-9]\d{9}\b/.test(text.replace(/\s+/g, ' '));
  const linkHits = countMatches(lower, ['linkedin', 'github', 'portfolio', 'behance']) + ((/https?:\/\//i.test(text) || /www\./i.test(text)) ? 1 : 0);

  let contact = 0;
  if (emailFound) { contact += 3; strengths.push('Email address is present.'); } else { negatives.push('Email address is missing or not clearly visible.'); improvements.push('Add a professional email address near your name at the top.'); }
  if (phoneFound) { contact += 3; strengths.push('Mobile number is available for recruiter contact.'); } else { negatives.push('Phone number is missing or difficult to detect.'); improvements.push('Add a 10-digit mobile number in the header area.'); }
  contact += Math.min(6, linkHits * 2);
  if (linkHits >= 2) strengths.push('Profile or portfolio links are included.');
  else { negatives.push('LinkedIn, GitHub or portfolio proof is weak.'); improvements.push('Add LinkedIn plus GitHub/portfolio/live project links.'); }
  categories.push({ name: 'Contact & Links', score: contact, max: 12 });

  const skillList = ['html','css','javascript','react','node','nodejs','php','wordpress','magento','mysql','sql','mongodb','git','github','api','rest','bootstrap','tailwind','deployment','cpanel','cloudflare','figma','python','java','typescript','jquery','laravel','docker','linux','postman'];
  const detectedSkills = matchedTerms(lower, skillList);
  const skillHits = detectedSkills.length;
  const skillScore = Math.min(18, Math.round(skillHits * 2.2));
  if (skillHits >= 6) strengths.push('Good number of technical skills detected.');
  else { negatives.push('Technical skills section looks thin for a web development fresher.'); improvements.push('Add focused skills: HTML, CSS, JavaScript, GitHub, API, database, deployment and one framework/CMS.'); }
  categories.push({ name: 'Technical Skills', score: skillScore, max: 18 });

  let projectScore = 0;
  const projectMentions = countMatches(lower, ['project','projects','website','ecommerce','e-commerce','portfolio','dashboard','application','clone','system']);
  const projectFeatureHits = countMatches(lower, ['api','payment','gateway','admin','database','authentication','login','crud','responsive','checkout']);
  const projectActionHits = countMatches(lower, ['built','developed','created','designed','implemented','integrated','deployed','optimized']);
  const projectProofFound = hasAny(text, [/github\.com/i, /netlify/i, /vercel/i, /cloudflare/i, /live\s+link/i, /deployed/i, /deployment/i]);
  if (projectMentions >= 2) { projectScore += 8; strengths.push('Project work is mentioned in the resume.'); } else { negatives.push('Project section is missing or not detailed enough.'); improvements.push('Add 2-3 projects with title, tech stack, features, your role and outcome.'); }
  if (projectProofFound) { projectScore += 6; strengths.push('Live/deployment or GitHub proof is visible.'); } else { negatives.push('No live project, deployment or GitHub proof found.'); improvements.push('Add GitHub repository and live deployed link for at least one project.'); }
  if (projectFeatureHits >= 3) projectScore += 5;
  else improvements.push('Mention practical project features like API, database, admin panel, authentication, payment or responsive design.');
  if (projectActionHits >= 3) projectScore += 3;
  else improvements.push('Use action words such as built, implemented, integrated, deployed and optimized.');
  categories.push({ name: 'Project Proof', score: Math.min(22, projectScore), max: 22 });

  let education = 0;
  const educationFound = /(b\.?tech|m\.?tech|bca|mca|diploma|computer science|information technology|engineering)/i.test(text);
  const yearOrMarksFound = /(cgpa|percentage|%|20\d{2}|202\d|201\d)/i.test(text);
  if (educationFound) { education += 6; strengths.push('Education background is clearly mentioned.'); }
  else { negatives.push('Education details are not clearly detected.'); improvements.push('Add degree, branch, college, year and CGPA/percentage if useful.'); }
  if (yearOrMarksFound) education += 4;
  else improvements.push('Add graduation year and CGPA/percentage to improve profile clarity.');
  categories.push({ name: 'Education Clarity', score: education, max: 10 });

  let experience = 0;
  const experienceFound = /(internship|intern|trainee|freelance|client|job|experience|training|workshop|industrial|developer|lecturer|assistant professor)/i.test(text);
  const durationFound = /(month|months|year|years|present|remote|onsite|full[- ]?time|part[- ]?time)/i.test(text);
  if (experienceFound) { experience += 7; strengths.push('Some internship, training or work exposure is mentioned.'); }
  else { negatives.push('No internship, training, freelance or practical exposure found.'); improvements.push('If you have no job experience, add training, workshop, freelance, college project or self-built project experience.'); }
  if (durationFound) experience += 3;
  categories.push({ name: 'Experience / Training', score: experience, max: 10 });

  let ats = 0;
  const standardSectionsFound = /(skills|technical skills|projects|education|experience|certification|achievements|summary)/i.test(text);
  const bulletsFound = /[-•●▪*]/.test(text) || /\n\s*\d+[.)]/.test(text);
  const actionAchievementHits = countMatches(lower, ['improved','reduced','increased','achieved','managed','integrated','deployed','optimized','automated']);
  const personalRedFlag = /(photo|father|mother|marital|religion|blood group)/i.test(text);
  if (wordCount >= 300 && wordCount <= 900) ats += 5;
  else if (wordCount > 150) ats += 3;
  else { negatives.push('Resume text is too short for a strong fresher profile.'); improvements.push('Keep a one-page resume but include enough detail: summary, skills, projects, education and links.'); }
  if (standardSectionsFound) ats += 5;
  else { negatives.push('Standard resume sections are not clearly visible.'); improvements.push('Use clear section headings: Skills, Projects, Education, Experience/Training, Certifications.'); }
  if (bulletsFound) ats += 3;
  else improvements.push('Use bullet points to make project and experience details easy to scan.');
  if (actionAchievementHits >= 2) ats += 3;
  else improvements.push('Add result-oriented lines showing what you achieved or delivered.');
  if (!personalRedFlag) ats += 2;
  else { negatives.push('Personal details/photo-style content may reduce professional resume quality.'); improvements.push('Avoid unnecessary personal details; keep the resume job-focused.'); }
  categories.push({ name: 'ATS & Clarity', score: ats, max: 18 });

  let modern = 0;
  const modernHits = countMatches(lower, ['ai','chatgpt','copilot','prompt','automation','git','github','cloud','deploy','api','postman']);
  if (modernHits >= 3) { modern += 7; strengths.push('Modern tools or AI/deployment awareness is visible.'); }
  else { negatives.push('Modern tools like GitHub, AI tools, API testing or deployment are not strongly visible.'); improvements.push('Add GitHub, AI-assisted coding, API testing, deployment or automation tools if you know them.'); }
  if (/(wordpress|magento|e-commerce|ecommerce|payment gateway|api integration)/i.test(text)) modern += 3;
  categories.push({ name: 'Modern Job Skills', score: Math.min(10, modern), max: 10 });

  const score = categories.reduce((sum, c) => sum + c.score, 0);
  let grade = 'Needs Foundation Work';
  let summary = 'Start by improving skills, project proof and resume clarity.';
  if (score >= 80) { grade = 'Job-Ready Fresher'; summary = 'Strong resume foundation. Focus on interview practice and targeted applications.'; }
  else if (score >= 65) { grade = 'Interview-Ready Soon'; summary = 'Good base. Fix missing proof and make projects more measurable.'; }
  else if (score >= 45) { grade = 'Improving Profile'; summary = 'Potential is visible, but your resume needs stronger projects, links and clarity.'; }

  facts.detectedSkills = detectedSkills;
  facts.emailFound = emailFound;
  facts.phoneFound = phoneFound;
  facts.linkHits = linkHits;
  facts.projectProofFound = projectProofFound;
  facts.projectMentions = projectMentions;
  facts.projectFeatureHits = projectFeatureHits;
  facts.projectActionHits = projectActionHits;
  facts.educationFound = educationFound;
  facts.experienceFound = experienceFound;
  facts.durationFound = durationFound;
  facts.standardSectionsFound = standardSectionsFound;
  facts.bulletsFound = bulletsFound;
  facts.actionAchievementHits = actionAchievementHits;
  facts.personalRedFlag = personalRedFlag;
  facts.modernHits = modernHits;
  facts.hasMetrics = /(\d+\s*%|\b\d+\+|\b\d+\s*(users|students|projects|pages|modules|clients|months|years|websites|apis)\b)/i.test(text);
  facts.hasTargetRole = /(web developer|frontend|front-end|backend|back-end|full stack|wordpress developer|magento developer|software developer|technical trainer|lecturer|assistant professor)/i.test(text);
  facts.weakVerbHits = countMatches(lower, ['worked','handled','maintained','responsible','helped','learned','involved']);

  if (strengths.length === 0) strengths.push('Basic resume content is present and can be improved with structure.');

  const report = {
    score,
    grade,
    summary,
    categories,
    strengths: dedupe(strengths).slice(0, 6),
    negatives: dedupe(negatives).slice(0, 6),
    improvements: dedupe(improvements).slice(0, 8),
    wordCount,
    advancedLocked: !options.includeAdvanced,
    advancedPreview: getAdvancedPreview()
  };

  if (options.includeAdvanced) {
    report.advancedSections = buildAdvancedSections({ categories, facts, wordCount, score });
  }

  return report;
}

function buildAdvancedSections(context) {
  const { categories, facts, wordCount, score } = context;
  const getPct = (name) => {
    const item = categories.find(c => c.name === name);
    return item ? Math.round((item.score / item.max) * 100) : 0;
  };
  const missingSkills = ['GitHub', 'Live deployment', 'API integration', 'Database', 'JavaScript project', 'Portfolio link'].filter(item => {
    const l = item.toLowerCase();
    if (l.includes('github')) return !facts.detectedSkills.includes('github') && facts.linkHits < 2;
    if (l.includes('deployment')) return !facts.projectProofFound;
    if (l.includes('api')) return facts.projectFeatureHits < 2;
    if (l.includes('database')) return !facts.detectedSkills.some(s => ['mysql','sql','mongodb'].includes(s));
    if (l.includes('javascript')) return !facts.detectedSkills.includes('javascript');
    if (l.includes('portfolio')) return facts.linkHits < 2;
    return false;
  });
  const redFlags = [];
  if (!facts.hasTargetRole) redFlags.push('Target role is not clear enough. Add one focused headline like “Fresher Web Developer” or “Magento / WordPress Developer”.');
  if (!facts.projectProofFound) redFlags.push('Project proof is weak because GitHub/live deployment link is missing.');
  if (!facts.hasMetrics) redFlags.push('Resume lacks numbers such as projects built, modules handled, students trained, pages created, or performance improvement.');
  if (facts.weakVerbHits >= 2) redFlags.push('Several lines may sound duty-based instead of result-based because weak verbs are visible.');
  if (!facts.standardSectionsFound) redFlags.push('ATS may not parse the resume cleanly without standard section headings.');
  if (facts.personalRedFlag) redFlags.push('Unnecessary personal details may reduce professional quality.');
  if (!redFlags.length) redFlags.push('No major red flag detected, but resume can still be improved with stronger proof and sharper targeting.');

  return [
    {
      title: 'ATS & Resume Parsing Check',
      score: Math.round((getPct('ATS & Clarity') + getPct('Contact & Links')) / 2),
      points: [
        facts.emailFound && facts.phoneFound ? 'Email and phone are readable for recruiter contact.' : 'Contact details need better visibility in the top header.',
        facts.standardSectionsFound ? 'Standard resume sections are detected.' : 'Use standard headings: Summary, Skills, Projects, Education, Experience.',
        facts.bulletsFound ? 'Bullet-style formatting is visible.' : 'Convert long paragraphs into short bullet points.',
        wordCount >= 300 && wordCount <= 900 ? 'Resume length looks suitable for a one-page fresher resume.' : 'Resume length needs balance; keep it concise but detailed enough.'
      ]
    },
    {
      title: 'Project Proof Score',
      score: getPct('Project Proof'),
      points: [
        facts.projectMentions >= 2 ? 'Projects are mentioned, which is good for a fresher profile.' : 'Add 2–3 project entries with clear titles.',
        facts.projectProofFound ? 'Live/GitHub/deployment proof is visible.' : 'Add GitHub repository and live deployed project links.',
        facts.projectFeatureHits >= 3 ? 'Practical features like API/database/payment/admin flow are visible.' : 'Mention practical features like API, database, admin panel, payment or deployment.',
        facts.projectActionHits >= 3 ? 'Action words are visible in project/work descriptions.' : 'Start bullets with built, implemented, integrated, deployed, optimized.'
      ]
    },
    {
      title: 'Skills Match Score',
      score: getPct('Technical Skills'),
      points: [
        facts.detectedSkills.length ? 'Detected skills: ' + facts.detectedSkills.slice(0, 12).join(', ') + '.' : 'No strong technical skill cluster detected.',
        missingSkills.length ? 'Missing or weak proof: ' + missingSkills.join(', ') + '.' : 'Skill proof looks balanced for web-development targeting.',
        facts.modernHits >= 3 ? 'Modern tools like AI/Git/API/deployment are visible.' : 'Add modern tools: GitHub, AI-assisted coding, API testing, deployment workflow.',
        'Group skills into Frontend, Backend/CMS, Database, Tools and Deployment for better readability.'
      ]
    },
    {
      title: 'Experience / Internship / Training Review',
      score: getPct('Experience / Training'),
      points: [
        facts.experienceFound ? 'Experience/training exposure is visible.' : 'Add internship, training, workshop, freelance or self-project exposure.',
        facts.durationFound ? 'Timeline or duration is visible.' : 'Add month/year duration to each role, training or internship.',
        'Freshers should convert academic projects into experience-style proof with role, tools and output.',
        'Mention what you built, where it was deployed and what problem it solved.'
      ]
    },
    {
      title: 'Impact & Achievement Check',
      score: facts.hasMetrics ? 78 : 48,
      points: [
        facts.hasMetrics ? 'Some numbers/scale signals are present.' : 'Add measurable details like number of pages, modules, users, students, APIs or projects.',
        facts.actionAchievementHits >= 2 ? 'Result-oriented action words are present.' : 'Add impact verbs: improved, reduced, increased, automated, optimized, delivered.',
        facts.weakVerbHits >= 2 ? 'Replace weak phrases like “worked on” or “handled” with stronger delivery-focused lines.' : 'Weak verb usage is not very high.',
        'Each important bullet should show: action + technology + output/result.'
      ]
    },
    {
      title: 'Red Flags',
      score: Math.max(25, 100 - redFlags.length * 14),
      points: redFlags
    },
    {
      title: 'Priority Improvement Plan',
      score: score,
      points: [
        'High priority: fix missing contact, links, role clarity and project proof first.',
        'Medium priority: improve bullet quality with action verbs and measurable outcomes.',
        'Low priority: polish formatting, spacing and section order after content is strong.',
        'Apply only after resume has one clear target role and 2–3 proof-based projects.'
      ]
    },
    {
      title: 'Suggested Resume Rewrite Examples',
      score: facts.hasMetrics ? 80 : 60,
      rewrite: [
        { old: 'Worked on web development projects.', better: 'Built responsive web pages using HTML, CSS and JavaScript with clean layout, mobile-friendly design and reusable components.' },
        { old: 'Handled project tasks and learning activities.', better: 'Implemented project features such as login flow, database connection, admin panel or deployment workflow and documented the process.' },
        { old: 'Good knowledge of WordPress/Magento.', better: 'Created WordPress/Magento pages, configured products/content, understood admin workflow and practiced deployment/payment integration basics.' }
      ]
    },
    {
      title: '7-Day and 30-Day Career Roadmap',
      score: 90,
      points: [
        'Next 7 days: add LinkedIn, GitHub, live project links and rewrite top 5 weak bullets.',
        'Next 7 days: create one project proof section with tech stack, features, role and output.',
        'Next 30 days: build/deploy 2 practical projects and document screenshots plus live links.',
        'Next 30 days: prepare interview topics from HTML, CSS, JavaScript, Git, API, database and deployment.'
      ]
    }
  ];
}
