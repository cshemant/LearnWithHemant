function escapeRegex(value) {
  return String(value || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function countMatches(text, list) {
  const lower = String(text || '').toLowerCase();
  return list.filter(item => new RegExp('\\b' + escapeRegex(item) + '\\b', 'i').test(lower)).length;
}

function matchedTerms(text, list) {
  const lower = String(text || '').toLowerCase();
  return list.filter(item => new RegExp('\\b' + escapeRegex(item) + '\\b', 'i').test(lower));
}

function unique(list) {
  return [...new Set((list || []).filter(Boolean))];
}

function normalizeResumeText(text) {
  return String(text || '')
    .replace(/\u0000/g, ' ')
    .replace(/\r/g, '\n')
    .replace(/[\t ]+/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function compactText(text) {
  return normalizeResumeText(text).replace(/\s+/g, ' ').trim();
}

function wordCountOf(text) {
  const normalized = compactText(text);
  return normalized ? normalized.split(/\s+/).filter(Boolean).length : 0;
}

function hasAny(text, patterns) {
  return patterns.some(pattern => pattern.test(text));
}

function pct(score, max) {
  return Math.round((score / max) * 100);
}

function clamp(num, min, max) {
  return Math.max(min, Math.min(max, num));
}

function sectionLikeText(text, keywords) {
  const lower = String(text || '').toLowerCase();
  const blocks = lower.split(/\n{2,}|(?=\b(?:project|projects|experience|skills|education|training|internship|summary)\b)/i);
  return blocks.filter(block => keywords.some(k => block.includes(k))).join(' ');
}

function getRoleScore(parts) {
  const total = parts.reduce((sum, item) => sum + item.max, 0);
  const score = parts.reduce((sum, item) => sum + (item.ok ? item.max : 0), 0);
  return Math.round((score / total) * 100);
}

export function validateResumeText(text) {
  const normalized = normalizeResumeText(text).slice(0, 30000);
  const wordCount = wordCountOf(normalized);
  if (wordCount < 40) {
    const error = new Error('Not enough readable resume text found. Please upload a text-based PDF/DOCX resume.');
    error.status = 400;
    throw error;
  }
  return normalized;
}

export function getAdvancedPreview() {
  return [
    { title: 'Skill-to-Project Mapping', short: 'Shows which skills are proven by projects and which are only written as keywords.' },
    { title: 'Project Proof Analysis', short: 'Checks GitHub/live links, deployment, database, API, admin, authentication and payment proof.' },
    { title: 'Role Fit Score', short: 'Estimates readiness for Frontend, WordPress, Magento, Full Stack and Internship roles.' },
    { title: 'Interview Risk Areas', short: 'Highlights topics where an interviewer may find weak proof or shallow understanding.' },
    { title: 'ATS & Resume Parsing Check', short: 'Checks machine readability, section clarity, contact visibility and ATS risk.' },
    { title: 'Red Flags', short: 'Finds generic claims, missing portfolio proof, weak metrics and copied-project signals.' },
    { title: '7-Day Fix Plan', short: 'Gives immediate tasks that a fresher can complete this week.' },
    { title: '30-Day Career Roadmap', short: 'Gives a practical project and profile roadmap for job readiness.' },
    { title: 'Resume Rewrite Examples', short: 'Shows weak lines and better proof-based alternatives.' }
  ];
}

export function analyzeResume(inputText, options = {}) {
  const text = validateResumeText(inputText);
  const lower = compactText(text).toLowerCase();
  const wordCount = wordCountOf(text);

  const strengths = [];
  const negatives = [];
  const improvements = [];
  const categories = [];

  const emailFound = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i.test(text);
  const phoneFound = /(\+?91[-\s]?)?[6-9]\d{9}\b/.test(text.replace(/\s+/g, ' '));
  const hasLinkedIn = /linkedin\.com|\blinkedin\b/i.test(text);
  const hasGithub = /github\.com|\bgithub\b/i.test(text);
  const hasPortfolio = /portfolio|netlify|vercel|pages\.dev|cloudflare|live\s+link|deployed|deployment|https?:\/\//i.test(text);

  let contactScore = 0;
  if (emailFound) { contactScore += 3; strengths.push('Email address is present.'); } else { negatives.push('Email address is missing or not clearly visible.'); improvements.push('Add a professional email address in the top header.'); }
  if (phoneFound) { contactScore += 3; strengths.push('Mobile number is available for recruiter contact.'); } else { negatives.push('Phone number is missing or difficult to detect.'); improvements.push('Add a recruiter-visible mobile number near your name.'); }
  if (hasLinkedIn) contactScore += 2; else improvements.push('Add a LinkedIn profile link to improve recruiter trust.');
  if (hasGithub) contactScore += 2; else improvements.push('Add a GitHub link so your skills have public proof.');
  if (hasPortfolio) contactScore += 2; else { negatives.push('Portfolio, GitHub or live project proof is weak.'); improvements.push('Add at least one live project or portfolio link.'); }
  categories.push({ name: 'Contact & Proof Links', score: clamp(contactScore, 0, 12), max: 12 });

  const skillGroups = {
    frontend: ['html','css','javascript','typescript','react','bootstrap','tailwind','jquery','responsive'],
    backend: ['php','node','nodejs','express','laravel','python','java','rest','api','graphql'],
    database: ['mysql','sql','mongodb','database'],
    cms: ['wordpress','magento','adobe commerce','shopify','e-commerce','ecommerce'],
    workflow: ['git','github','postman','docker','linux','cloudflare','vercel','netlify','deployment','cpanel'],
    ai: ['ai','chatgpt','copilot','prompt','openai','automation']
  };
  const allSkills = unique(Object.values(skillGroups).flat());
  const detectedSkills = matchedTerms(lower, allSkills);

  const projectKeywords = ['project','projects','website','ecommerce','e-commerce','portfolio','dashboard','application','system','clone','module','portal'];
  const projectText = sectionLikeText(text, projectKeywords) || lower;
  const actionWords = ['built','developed','created','designed','implemented','integrated','deployed','optimized','automated','customized','handled','maintained'];
  const proofWindow = (projectText + ' ' + lower.match(/.{0,120}(built|developed|implemented|integrated|deployed|project|website|application).{0,220}/gi)?.join(' ') || '').toLowerCase();
  const provenSkills = detectedSkills.filter(skill => new RegExp('\\b' + escapeRegex(skill) + '\\b', 'i').test(proofWindow));
  const weakProofSkills = detectedSkills.filter(skill => !provenSkills.includes(skill));

  let skillProofScore = 0;
  skillProofScore += Math.min(7, detectedSkills.length);
  skillProofScore += Math.min(8, provenSkills.length * 2);
  if (detectedSkills.length >= 6 && provenSkills.length >= 3) { skillProofScore += 3; strengths.push('Multiple technical skills are backed by project or work context.'); }
  else if (detectedSkills.length >= 6) { negatives.push('Several skills are listed, but project-level proof is not strong enough.'); improvements.push('Connect every major skill with a project line that shows where it was used.'); }
  else { negatives.push('Technical skill coverage is thin for a web development fresher.'); improvements.push('Add focused skills such as HTML, CSS, JavaScript, GitHub, API, database and deployment.'); }
  categories.push({ name: 'Skill Proof Mapping', score: clamp(skillProofScore, 0, 18), max: 18 });

  const projectMentions = countMatches(lower, projectKeywords);
  const featureKeywords = ['api','payment','gateway','admin','database','authentication','login','crud','responsive','checkout','cart','dashboard','cms','theme','plugin'];
  const projectFeatureHits = countMatches(lower, featureKeywords);
  const projectActionHits = countMatches(lower, actionWords);
  const projectProofFound = hasGithub || hasPortfolio;
  const hasRealWorldFeature = projectFeatureHits >= 3;
  const hasDeploymentProof = /deployed|deployment|live\s+link|netlify|vercel|cloudflare|pages\.dev|cpanel|server/i.test(text);

  let projectScore = 0;
  if (projectMentions >= 2) { projectScore += 6; strengths.push('Project work is mentioned in the resume.'); } else { negatives.push('Project section is missing or not detailed enough.'); improvements.push('Add 2-3 projects with title, tech stack, features, your role and output.'); }
  if (projectProofFound) { projectScore += 5; strengths.push('GitHub, portfolio or live project proof is visible.'); } else { negatives.push('No GitHub, portfolio or live project proof found.'); improvements.push('Deploy one project and add both live link and GitHub repository.'); }
  if (hasDeploymentProof) projectScore += 4; else improvements.push('Mention deployment proof such as Cloudflare Pages, Vercel, Netlify, cPanel or server deployment.');
  if (hasRealWorldFeature) projectScore += 4; else improvements.push('Add real-world project features like login, database, API, admin panel, cart, payment or dashboard.');
  if (projectActionHits >= 4) projectScore += 3; else improvements.push('Use action verbs such as built, implemented, integrated, deployed and optimized.');
  categories.push({ name: 'Project Proof Score', score: clamp(projectScore, 0, 22), max: 22 });

  const standardSectionsFound = /(skills|technical skills|projects|education|experience|internship|training|certification|achievements|summary)/i.test(text);
  const bulletsFound = /[-•●▪*]/.test(text) || /\n\s*\d+[.)]/.test(text);
  const personalRedFlag = /(father|mother|marital|religion|blood group)/i.test(text);
  const hasMetrics = /(\d+\s*%|\b\d+\+|\b\d+\s*(users|students|projects|pages|modules|clients|months|years|websites|apis|features)\b)/i.test(text);
  const hasTargetRole = /(web developer|frontend|front-end|backend|back-end|full stack|wordpress developer|magento developer|software developer|technical trainer|lecturer|assistant professor|intern)/i.test(text);

  let atsScore = 0;
  if (wordCount >= 300 && wordCount <= 900) atsScore += 3; else if (wordCount > 150) atsScore += 2; else improvements.push('Add enough readable details while keeping the resume concise.');
  if (standardSectionsFound) atsScore += 3; else { negatives.push('Standard resume sections are not clearly visible.'); improvements.push('Use clear sections: Summary, Skills, Projects, Education, Experience/Training and Certifications.'); }
  if (bulletsFound) atsScore += 2; else improvements.push('Use bullet points for project and experience details.');
  if (!personalRedFlag) atsScore += 2; else { negatives.push('Unnecessary personal details may reduce professional resume quality.'); improvements.push('Remove unnecessary personal details and keep the resume job-focused.'); }
  if (hasTargetRole) atsScore += 2; else { negatives.push('Target role is not clear enough.'); improvements.push('Add a focused headline such as “Fresher Web Developer” or “WordPress / Magento Developer”.'); }
  categories.push({ name: 'ATS Readability', score: clamp(atsScore, 0, 12), max: 12 });

  const roleFits = buildRoleFits({ lower, detectedSkills, provenSkills, projectProofFound, hasDeploymentProof, hasRealWorldFeature, hasTargetRole });
  const topRole = roleFits[0];
  const roleScore = Math.round(roleFits.slice(0, 3).reduce((sum, role) => sum + role.score, 0) / 3 * 0.16);
  if (topRole.score >= 70) strengths.push(`${topRole.name} role readiness is visible.`);
  else { negatives.push('Role fit is not strong enough for a clear fresher job target.'); improvements.push('Choose one primary target role and make skills, projects and headline match that role.'); }
  categories.push({ name: 'Role Fit Score', score: clamp(roleScore, 0, 16), max: 16 });

  let interviewScore = 0;
  if (hasMetrics) { interviewScore += 3; strengths.push('Resume includes measurable proof or quantified experience.'); } else { negatives.push('Resume lacks measurable outcomes or numbers.'); improvements.push('Add numbers such as projects built, modules handled, pages created, students trained or performance improved.'); }
  if (provenSkills.length >= 4) interviewScore += 3; else improvements.push('Prepare explanations for each listed skill through one real project example.');
  if (projectFeatureHits >= 4) interviewScore += 2; else improvements.push('Add features that create interview discussion points: login, database, API, deployment, payment or admin panel.');
  if (projectActionHits >= 4) interviewScore += 2; else improvements.push('Rewrite duty-based lines into achievement-oriented bullets.');
  categories.push({ name: 'Interview Readiness', score: clamp(interviewScore, 0, 10), max: 10 });

  let modernScore = 0;
  const workflowHits = matchedTerms(lower, skillGroups.workflow);
  const aiHits = matchedTerms(lower, skillGroups.ai);
  if (workflowHits.length >= 3) { modernScore += 6; strengths.push('Modern workflow tools such as GitHub, deployment or API testing are visible.'); }
  else { negatives.push('Modern workflow proof is weak.'); improvements.push('Show GitHub, deployment, API testing, Cloudflare/Vercel/Netlify or automation usage.'); }
  if (aiHits.length >= 1) modernScore += 2; else improvements.push('If you use AI tools, mention practical AI-assisted debugging, code review or productivity workflow.');
  if (/api|payment gateway|e-commerce|ecommerce|wordpress|magento/i.test(text)) modernScore += 2;
  categories.push({ name: 'Modern Workflow Proof', score: clamp(modernScore, 0, 10), max: 10 });

  const rawScore = categories.reduce((sum, c) => sum + c.score, 0);
  const score = clamp(rawScore, 0, 100);
  let grade = 'Foundation Stage';
  let summary = 'Your resume needs stronger project proof, clearer role focus and practical action steps.';
  if (score >= 85) { grade = 'Job-Ready Fresher'; summary = 'Strong proof-based profile. Focus on interview practice and targeted applications.'; }
  else if (score >= 70) { grade = 'Interview-Ready Soon'; summary = 'Good base. Improve project proof, metrics and role-specific positioning.'; }
  else if (score >= 50) { grade = 'Improving Profile'; summary = 'Potential is visible, but proof, role fit and interview evidence need work.'; }

  const proofSummary = {
    skillsMentioned: detectedSkills.length,
    skillsProven: provenSkills.length,
    weakProofSkills: weakProofSkills.slice(0, 8),
    topRole: topRole.name,
    topRoleScore: topRole.score
  };

  const insightCards = [
    {
      label: 'Skills Mentioned',
      value: String(detectedSkills.length),
      note: detectedSkills.length ? detectedSkills.slice(0, 6).join(', ') : 'Add focused web development skills.'
    },
    {
      label: 'Skills Proven by Projects',
      value: `${provenSkills.length}/${Math.max(detectedSkills.length, 1)}`,
      note: weakProofSkills.length ? `Weak proof: ${weakProofSkills.slice(0, 4).join(', ')}` : 'Major skills are connected with proof.'
    },
    {
      label: 'Best Role Fit',
      value: `${topRole.score}%`,
      note: topRole.name
    },
    {
      label: 'Job Proof Score',
      value: `${pct(projectScore + skillProofScore, 40)}%`,
      note: 'Based on projects, links, deployment, features and skill evidence.'
    }
  ];

  const report = {
    score,
    grade,
    summary,
    categories,
    strengths: unique(strengths).slice(0, 6),
    negatives: unique(negatives).slice(0, 6),
    improvements: unique(improvements).slice(0, 9),
    wordCount,
    insightCards,
    proofSummary,
    roleFits,
    advancedLocked: !options.includeAdvanced,
    advancedPreview: getAdvancedPreview()
  };

  if (options.includeAdvanced) {
    report.advancedSections = buildAdvancedSections({ categories, proofSummary, roleFits, detectedSkills, provenSkills, weakProofSkills, facts: { emailFound, phoneFound, hasLinkedIn, hasGithub, hasPortfolio, projectMentions, projectFeatureHits, projectActionHits, projectProofFound, hasDeploymentProof, hasRealWorldFeature, standardSectionsFound, bulletsFound, personalRedFlag, hasMetrics, hasTargetRole, workflowHits, aiHits, wordCount, score } });
  }

  return report;
}

function buildRoleFits(ctx) {
  const { lower, detectedSkills, provenSkills, projectProofFound, hasDeploymentProof, hasRealWorldFeature, hasTargetRole } = ctx;
  const has = (items) => items.some(item => detectedSkills.includes(item) || lower.includes(item));
  const proven = (items) => items.some(item => provenSkills.includes(item));

  const roles = [
    {
      name: 'Frontend Fresher',
      score: getRoleScore([
        { ok: has(['html']), max: 15 }, { ok: has(['css']), max: 15 }, { ok: has(['javascript','typescript']), max: 20 },
        { ok: has(['react','bootstrap','tailwind','jquery']), max: 15 }, { ok: proven(['html','css','javascript','react']), max: 20 }, { ok: hasDeploymentProof, max: 15 }
      ])
    },
    {
      name: 'WordPress Developer',
      score: getRoleScore([
        { ok: has(['wordpress']), max: 25 }, { ok: has(['php']), max: 20 }, { ok: has(['mysql','sql']), max: 15 },
        { ok: /theme|plugin|woocommerce|cms/i.test(lower), max: 15 }, { ok: projectProofFound, max: 15 }, { ok: hasDeploymentProof, max: 10 }
      ])
    },
    {
      name: 'Magento / E-commerce Developer',
      score: getRoleScore([
        { ok: has(['magento','adobe commerce']), max: 30 }, { ok: has(['php']), max: 15 }, { ok: has(['mysql','sql']), max: 10 },
        { ok: /e-commerce|ecommerce|checkout|cart|payment|api/i.test(lower), max: 20 }, { ok: projectProofFound, max: 15 }, { ok: hasDeploymentProof, max: 10 }
      ])
    },
    {
      name: 'Full Stack Fresher',
      score: getRoleScore([
        { ok: has(['html','css']), max: 15 }, { ok: has(['javascript','typescript']), max: 15 }, { ok: has(['php','node','nodejs','laravel','python','java']), max: 20 },
        { ok: has(['mysql','sql','mongodb','database']), max: 15 }, { ok: /api|rest|authentication|login|crud/i.test(lower), max: 20 }, { ok: hasDeploymentProof, max: 15 }
      ])
    },
    {
      name: 'Internship Ready',
      score: getRoleScore([
        { ok: hasTargetRole, max: 15 }, { ok: detectedSkills.length >= 6, max: 20 }, { ok: provenSkills.length >= 3, max: 25 },
        { ok: projectProofFound, max: 20 }, { ok: hasRealWorldFeature, max: 10 }, { ok: hasDeploymentProof, max: 10 }
      ])
    }
  ];
  return roles.sort((a, b) => b.score - a.score);
}

function buildAdvancedSections(context) {
  const { categories, proofSummary, roleFits, detectedSkills, provenSkills, weakProofSkills, facts } = context;
  const getPct = (name) => {
    const item = categories.find(c => c.name === name);
    return item ? pct(item.score, item.max) : 0;
  };

  const interviewRisks = [];
  if (weakProofSkills.length) interviewRisks.push(`You may be asked about ${weakProofSkills.slice(0, 4).join(', ')}, but project proof for these skills is weak.`);
  if (!facts.hasMetrics) interviewRisks.push('Interview answers may sound generic because measurable outcomes are missing.');
  if (!facts.hasDeploymentProof) interviewRisks.push('Deployment questions may become risky because live hosting proof is not visible.');
  if (facts.projectFeatureHits < 4) interviewRisks.push('Project-depth questions may become risky because real-world features are limited.');
  if (!interviewRisks.length) interviewRisks.push('Interview risk is moderate. Prepare strong explanations for your best project and deployment workflow.');

  const redFlags = [];
  if (!facts.hasTargetRole) redFlags.push('Target role is unclear; the resume should be focused on one primary job path.');
  if (!facts.hasGithub && !facts.hasPortfolio) redFlags.push('No public project proof is visible through GitHub, portfolio or live project links.');
  if (!facts.hasMetrics) redFlags.push('No measurable achievements are visible, so the resume may look duty-based.');
  if (facts.personalRedFlag) redFlags.push('Unnecessary personal details may reduce professional quality.');
  if (facts.projectFeatureHits < 3) redFlags.push('Projects may look like tutorial-level work because real-world features are not clearly shown.');
  if (!redFlags.length) redFlags.push('No major red flag detected, but stronger proof and sharper targeting can still improve conversion.');

  const sevenDay = [
    'Day 1: Add one focused target role headline and remove generic summary lines.',
    'Day 2: Add GitHub and live project links near each major project.',
    'Day 3: Rewrite project bullets using feature + tech stack + outcome format.',
    'Day 4: Add missing proof for weak skills listed in the Skill-to-Project Mapping section.',
    'Day 5: Add one measurable result such as pages built, modules completed, APIs integrated or performance improved.',
    'Day 6: Prepare interview explanations for your strongest project, deployment, database and API workflow.',
    'Day 7: Apply to 15 targeted internships/jobs with this improved resume.'
  ];

  const thirtyDay = [
    'Week 1: Fix resume structure, role focus, GitHub/live links and project descriptions.',
    'Week 2: Build one proof project with login, database, API and responsive UI.',
    'Week 3: Deploy the project and document the workflow in GitHub README with screenshots.',
    'Week 4: Practice interview questions from your weak areas and apply with a targeted message.'
  ];

  return [
    {
      title: 'Skill-to-Project Mapping',
      score: getPct('Skill Proof Mapping'),
      points: [
        `${proofSummary.skillsMentioned} skills are mentioned in the resume.`,
        `${proofSummary.skillsProven} skills are connected with project/work proof.`,
        weakProofSkills.length ? `Weak proof skills: ${weakProofSkills.slice(0, 8).join(', ')}.` : 'Major skills are supported by project or work context.',
        'USP insight: this is not only a resume check; it checks whether skills are proven through real work.'
      ]
    },
    {
      title: 'Project Proof Analysis',
      score: getPct('Project Proof Score'),
      points: [
        facts.hasGithub || facts.hasPortfolio ? 'Public proof is visible through GitHub, portfolio or live project signals.' : 'Public proof is missing; add GitHub and live project links.',
        facts.hasDeploymentProof ? 'Deployment proof is visible.' : 'Deployment proof is missing; add Cloudflare Pages, Vercel, Netlify, cPanel or server details.',
        facts.projectFeatureHits >= 3 ? 'Real-world project features are visible.' : 'Add features such as login, database, API, admin panel, checkout or payment gateway.',
        'Best improvement: make every project show problem, features, tech stack, your contribution and output.'
      ]
    },
    {
      title: 'Role Fit Score',
      score: Math.round(roleFits.slice(0, 3).reduce((sum, role) => sum + role.score, 0) / 3),
      points: roleFits.map(role => `${role.name}: ${role.score}% readiness.`)
    },
    {
      title: 'Interview Risk Areas',
      score: getPct('Interview Readiness'),
      points: interviewRisks
    },
    {
      title: 'ATS & Resume Parsing Check',
      score: getPct('ATS Readability'),
      points: [
        facts.emailFound && facts.phoneFound ? 'Email and phone are readable for recruiter contact.' : 'Contact details need better visibility in the top header.',
        facts.standardSectionsFound ? 'Standard resume sections are detected.' : 'Use standard section headings for better ATS readability.',
        facts.bulletsFound ? 'Bullet-style formatting is visible.' : 'Use bullet points for easy scanning.',
        facts.wordCount >= 300 && facts.wordCount <= 900 ? 'Resume length is in a practical one-page range.' : 'Resume length should be optimized for quick recruiter scanning.'
      ]
    },
    {
      title: 'Red Flags',
      score: Math.max(35, 100 - redFlags.length * 12),
      points: redFlags
    },
    {
      title: '7-Day Fix Plan',
      score: 90,
      points: sevenDay
    },
    {
      title: '30-Day Career Roadmap',
      score: 90,
      points: thirtyDay
    },
    {
      title: 'Resume Rewrite Examples',
      score: 84,
      rewrite: [
        {
          old: 'Worked on web development projects.',
          better: 'Built and deployed responsive web pages with project-specific features, clean UI structure and live hosting proof.'
        },
        {
          old: 'Knowledge of HTML, CSS and JavaScript.',
          better: 'Used HTML, CSS and JavaScript to build a responsive project with form handling, UI interactions and deployment-ready structure.'
        },
        {
          old: 'Responsible for project work.',
          better: 'Implemented project modules including UI, database/API flow, testing and deployment documentation.'
        }
      ]
    }
  ];
}
