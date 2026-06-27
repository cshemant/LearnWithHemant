var __defProp = Object.defineProperty;
var __name = (target, value) => __defProp(target, "name", { value, configurable: true });

// .wrangler/tmp/pages-qcyaQ6/functionsWorker-0.5353621274107482.mjs
var __defProp2 = Object.defineProperty;
var __name2 = /* @__PURE__ */ __name((target, value) => __defProp2(target, "name", { value, configurable: true }), "__name");
function jsonResponse(data, status = 200) {
  const headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store"
  };
  if (data === null) {
    return new Response(null, { status, headers });
  }
  return new Response(JSON.stringify(data), { status, headers });
}
__name(jsonResponse, "jsonResponse");
__name2(jsonResponse, "jsonResponse");
function handleOptions() {
  return jsonResponse(null, 204);
}
__name(handleOptions, "handleOptions");
__name2(handleOptions, "handleOptions");
async function readJson(request) {
  const contentType = request.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    throw new Error("Request must be JSON.");
  }
  return request.json();
}
__name(readJson, "readJson");
__name2(readJson, "readJson");
function escapeRegex(value) {
  return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
__name(escapeRegex, "escapeRegex");
__name2(escapeRegex, "escapeRegex");
function countMatches(text, list) {
  const lower = String(text || "").toLowerCase();
  return list.filter((item) => new RegExp("\\b" + escapeRegex(item) + "\\b", "i").test(lower)).length;
}
__name(countMatches, "countMatches");
__name2(countMatches, "countMatches");
function matchedTerms(text, list) {
  const lower = String(text || "").toLowerCase();
  return list.filter((item) => new RegExp("\\b" + escapeRegex(item) + "\\b", "i").test(lower));
}
__name(matchedTerms, "matchedTerms");
__name2(matchedTerms, "matchedTerms");
function unique(list) {
  return [...new Set((list || []).filter(Boolean))];
}
__name(unique, "unique");
__name2(unique, "unique");
function normalizeResumeText(text) {
  return String(text || "").replace(/\u0000/g, " ").replace(/\r/g, "\n").replace(/[\t ]+/g, " ").replace(/\n{3,}/g, "\n\n").trim();
}
__name(normalizeResumeText, "normalizeResumeText");
__name2(normalizeResumeText, "normalizeResumeText");
function compactText(text) {
  return normalizeResumeText(text).replace(/\s+/g, " ").trim();
}
__name(compactText, "compactText");
__name2(compactText, "compactText");
function wordCountOf(text) {
  const normalized = compactText(text);
  return normalized ? normalized.split(/\s+/).filter(Boolean).length : 0;
}
__name(wordCountOf, "wordCountOf");
__name2(wordCountOf, "wordCountOf");
function pct(score, max) {
  return Math.round(score / max * 100);
}
__name(pct, "pct");
__name2(pct, "pct");
function clamp(num, min, max) {
  return Math.max(min, Math.min(max, num));
}
__name(clamp, "clamp");
__name2(clamp, "clamp");
function sectionLikeText(text, keywords) {
  const lower = String(text || "").toLowerCase();
  const blocks = lower.split(/\n{2,}|(?=\b(?:project|projects|experience|skills|education|training|internship|summary)\b)/i);
  return blocks.filter((block) => keywords.some((k) => block.includes(k))).join(" ");
}
__name(sectionLikeText, "sectionLikeText");
__name2(sectionLikeText, "sectionLikeText");
function getRoleScore(parts) {
  const total = parts.reduce((sum, item) => sum + item.max, 0);
  const score = parts.reduce((sum, item) => sum + (item.ok ? item.max : 0), 0);
  return Math.round(score / total * 100);
}
__name(getRoleScore, "getRoleScore");
__name2(getRoleScore, "getRoleScore");
function validateResumeText(text) {
  const normalized = normalizeResumeText(text).slice(0, 3e4);
  const wordCount = wordCountOf(normalized);
  if (wordCount < 40) {
    const error = new Error("Not enough readable resume text found. Please upload a text-based PDF/DOCX resume.");
    error.status = 400;
    throw error;
  }
  return normalized;
}
__name(validateResumeText, "validateResumeText");
__name2(validateResumeText, "validateResumeText");
function getAdvancedPreview() {
  return [
    { title: "Skill-to-Project Mapping", short: "Shows which skills are proven by projects and which are only written as keywords." },
    { title: "Project Proof Analysis", short: "Checks GitHub/live links, deployment, database, API, admin, authentication and payment proof." },
    { title: "Role Fit Score", short: "Estimates readiness for Frontend, WordPress, Magento, Full Stack and Internship roles." },
    { title: "Interview Risk Areas", short: "Highlights topics where an interviewer may find weak proof or shallow understanding." },
    { title: "ATS & Resume Parsing Check", short: "Checks machine readability, section clarity, contact visibility and ATS risk." },
    { title: "Red Flags", short: "Finds generic claims, missing portfolio proof, weak metrics and copied-project signals." },
    { title: "7-Day Fix Plan", short: "Gives immediate tasks that a fresher can complete this week." },
    { title: "30-Day Career Roadmap", short: "Gives a practical project and profile roadmap for job readiness." },
    { title: "Resume Rewrite Examples", short: "Shows weak lines and better proof-based alternatives." }
  ];
}
__name(getAdvancedPreview, "getAdvancedPreview");
__name2(getAdvancedPreview, "getAdvancedPreview");
function analyzeResume(inputText, options = {}) {
  const text = validateResumeText(inputText);
  const lower = compactText(text).toLowerCase();
  const wordCount = wordCountOf(text);
  const strengths = [];
  const negatives = [];
  const improvements = [];
  const categories = [];
  const emailFound = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i.test(text);
  const phoneFound = /(\+?91[-\s]?)?[6-9]\d{9}\b/.test(text.replace(/\s+/g, " "));
  const hasLinkedIn = /linkedin\.com|\blinkedin\b/i.test(text);
  const hasGithub = /github\.com|\bgithub\b/i.test(text);
  const hasPortfolio = /portfolio|netlify|vercel|pages\.dev|cloudflare|live\s+link|deployed|deployment|https?:\/\//i.test(text);
  let contactScore = 0;
  if (emailFound) {
    contactScore += 3;
    strengths.push("Email address is present.");
  } else {
    negatives.push("Email address is missing or not clearly visible.");
    improvements.push("Add a professional email address in the top header.");
  }
  if (phoneFound) {
    contactScore += 3;
    strengths.push("Mobile number is available for recruiter contact.");
  } else {
    negatives.push("Phone number is missing or difficult to detect.");
    improvements.push("Add a recruiter-visible mobile number near your name.");
  }
  if (hasLinkedIn) contactScore += 2;
  else improvements.push("Add a LinkedIn profile link to improve recruiter trust.");
  if (hasGithub) contactScore += 2;
  else improvements.push("Add a GitHub link so your skills have public proof.");
  if (hasPortfolio) contactScore += 2;
  else {
    negatives.push("Portfolio, GitHub or live project proof is weak.");
    improvements.push("Add at least one live project or portfolio link.");
  }
  categories.push({ name: "Contact & Proof Links", score: clamp(contactScore, 0, 12), max: 12 });
  const skillGroups = {
    frontend: ["html", "css", "javascript", "typescript", "react", "bootstrap", "tailwind", "jquery", "responsive"],
    backend: ["php", "node", "nodejs", "express", "laravel", "python", "java", "rest", "api", "graphql"],
    database: ["mysql", "sql", "mongodb", "database"],
    cms: ["wordpress", "magento", "adobe commerce", "shopify", "e-commerce", "ecommerce"],
    workflow: ["git", "github", "postman", "docker", "linux", "cloudflare", "vercel", "netlify", "deployment", "cpanel"],
    ai: ["ai", "chatgpt", "copilot", "prompt", "openai", "automation"]
  };
  const allSkills = unique(Object.values(skillGroups).flat());
  const detectedSkills = matchedTerms(lower, allSkills);
  const projectKeywords = ["project", "projects", "website", "ecommerce", "e-commerce", "portfolio", "dashboard", "application", "system", "clone", "module", "portal"];
  const projectText = sectionLikeText(text, projectKeywords) || lower;
  const actionWords = ["built", "developed", "created", "designed", "implemented", "integrated", "deployed", "optimized", "automated", "customized", "handled", "maintained"];
  const proofWindow = (projectText + " " + lower.match(/.{0,120}(built|developed|implemented|integrated|deployed|project|website|application).{0,220}/gi)?.join(" ") || "").toLowerCase();
  const provenSkills = detectedSkills.filter((skill) => new RegExp("\\b" + escapeRegex(skill) + "\\b", "i").test(proofWindow));
  const weakProofSkills = detectedSkills.filter((skill) => !provenSkills.includes(skill));
  let skillProofScore = 0;
  skillProofScore += Math.min(7, detectedSkills.length);
  skillProofScore += Math.min(8, provenSkills.length * 2);
  if (detectedSkills.length >= 6 && provenSkills.length >= 3) {
    skillProofScore += 3;
    strengths.push("Multiple technical skills are backed by project or work context.");
  } else if (detectedSkills.length >= 6) {
    negatives.push("Several skills are listed, but project-level proof is not strong enough.");
    improvements.push("Connect every major skill with a project line that shows where it was used.");
  } else {
    negatives.push("Technical skill coverage is thin for a web development fresher.");
    improvements.push("Add focused skills such as HTML, CSS, JavaScript, GitHub, API, database and deployment.");
  }
  categories.push({ name: "Skill Proof Mapping", score: clamp(skillProofScore, 0, 18), max: 18 });
  const projectMentions = countMatches(lower, projectKeywords);
  const featureKeywords = ["api", "payment", "gateway", "admin", "database", "authentication", "login", "crud", "responsive", "checkout", "cart", "dashboard", "cms", "theme", "plugin"];
  const projectFeatureHits = countMatches(lower, featureKeywords);
  const projectActionHits = countMatches(lower, actionWords);
  const projectProofFound = hasGithub || hasPortfolio;
  const hasRealWorldFeature = projectFeatureHits >= 3;
  const hasDeploymentProof = /deployed|deployment|live\s+link|netlify|vercel|cloudflare|pages\.dev|cpanel|server/i.test(text);
  let projectScore = 0;
  if (projectMentions >= 2) {
    projectScore += 6;
    strengths.push("Project work is mentioned in the resume.");
  } else {
    negatives.push("Project section is missing or not detailed enough.");
    improvements.push("Add 2-3 projects with title, tech stack, features, your role and output.");
  }
  if (projectProofFound) {
    projectScore += 5;
    strengths.push("GitHub, portfolio or live project proof is visible.");
  } else {
    negatives.push("No GitHub, portfolio or live project proof found.");
    improvements.push("Deploy one project and add both live link and GitHub repository.");
  }
  if (hasDeploymentProof) projectScore += 4;
  else improvements.push("Mention deployment proof such as Cloudflare Pages, Vercel, Netlify, cPanel or server deployment.");
  if (hasRealWorldFeature) projectScore += 4;
  else improvements.push("Add real-world project features like login, database, API, admin panel, cart, payment or dashboard.");
  if (projectActionHits >= 4) projectScore += 3;
  else improvements.push("Use action verbs such as built, implemented, integrated, deployed and optimized.");
  categories.push({ name: "Project Proof Score", score: clamp(projectScore, 0, 22), max: 22 });
  const standardSectionsFound = /(skills|technical skills|projects|education|experience|internship|training|certification|achievements|summary)/i.test(text);
  const bulletsFound = /[-•●▪*]/.test(text) || /\n\s*\d+[.)]/.test(text);
  const personalRedFlag = /(father|mother|marital|religion|blood group)/i.test(text);
  const hasMetrics = /(\d+\s*%|\b\d+\+|\b\d+\s*(users|students|projects|pages|modules|clients|months|years|websites|apis|features)\b)/i.test(text);
  const hasTargetRole = /(web developer|frontend|front-end|backend|back-end|full stack|wordpress developer|magento developer|software developer|technical trainer|lecturer|assistant professor|intern)/i.test(text);
  let atsScore = 0;
  if (wordCount >= 300 && wordCount <= 900) atsScore += 3;
  else if (wordCount > 150) atsScore += 2;
  else improvements.push("Add enough readable details while keeping the resume concise.");
  if (standardSectionsFound) atsScore += 3;
  else {
    negatives.push("Standard resume sections are not clearly visible.");
    improvements.push("Use clear sections: Summary, Skills, Projects, Education, Experience/Training and Certifications.");
  }
  if (bulletsFound) atsScore += 2;
  else improvements.push("Use bullet points for project and experience details.");
  if (!personalRedFlag) atsScore += 2;
  else {
    negatives.push("Unnecessary personal details may reduce professional resume quality.");
    improvements.push("Remove unnecessary personal details and keep the resume job-focused.");
  }
  if (hasTargetRole) atsScore += 2;
  else {
    negatives.push("Target role is not clear enough.");
    improvements.push("Add a focused headline such as \u201CFresher Web Developer\u201D or \u201CWordPress / Magento Developer\u201D.");
  }
  categories.push({ name: "ATS Readability", score: clamp(atsScore, 0, 12), max: 12 });
  const roleFits = buildRoleFits({ lower, detectedSkills, provenSkills, projectProofFound, hasDeploymentProof, hasRealWorldFeature, hasTargetRole });
  const topRole = roleFits[0];
  const roleScore = Math.round(roleFits.slice(0, 3).reduce((sum, role) => sum + role.score, 0) / 3 * 0.16);
  if (topRole.score >= 70) strengths.push(`${topRole.name} role readiness is visible.`);
  else {
    negatives.push("Role fit is not strong enough for a clear fresher job target.");
    improvements.push("Choose one primary target role and make skills, projects and headline match that role.");
  }
  categories.push({ name: "Role Fit Score", score: clamp(roleScore, 0, 16), max: 16 });
  let interviewScore = 0;
  if (hasMetrics) {
    interviewScore += 3;
    strengths.push("Resume includes measurable proof or quantified experience.");
  } else {
    negatives.push("Resume lacks measurable outcomes or numbers.");
    improvements.push("Add numbers such as projects built, modules handled, pages created, students trained or performance improved.");
  }
  if (provenSkills.length >= 4) interviewScore += 3;
  else improvements.push("Prepare explanations for each listed skill through one real project example.");
  if (projectFeatureHits >= 4) interviewScore += 2;
  else improvements.push("Add features that create interview discussion points: login, database, API, deployment, payment or admin panel.");
  if (projectActionHits >= 4) interviewScore += 2;
  else improvements.push("Rewrite duty-based lines into achievement-oriented bullets.");
  categories.push({ name: "Interview Readiness", score: clamp(interviewScore, 0, 10), max: 10 });
  let modernScore = 0;
  const workflowHits = matchedTerms(lower, skillGroups.workflow);
  const aiHits = matchedTerms(lower, skillGroups.ai);
  if (workflowHits.length >= 3) {
    modernScore += 6;
    strengths.push("Modern workflow tools such as GitHub, deployment or API testing are visible.");
  } else {
    negatives.push("Modern workflow proof is weak.");
    improvements.push("Show GitHub, deployment, API testing, Cloudflare/Vercel/Netlify or automation usage.");
  }
  if (aiHits.length >= 1) modernScore += 2;
  else improvements.push("If you use AI tools, mention practical AI-assisted debugging, code review or productivity workflow.");
  if (/api|payment gateway|e-commerce|ecommerce|wordpress|magento/i.test(text)) modernScore += 2;
  categories.push({ name: "Modern Workflow Proof", score: clamp(modernScore, 0, 10), max: 10 });
  const rawScore = categories.reduce((sum, c) => sum + c.score, 0);
  const score = clamp(rawScore, 0, 100);
  let grade = "Foundation Stage";
  let summary = "Your resume needs stronger project proof, clearer role focus and practical action steps.";
  if (score >= 85) {
    grade = "Job-Ready Fresher";
    summary = "Strong proof-based profile. Focus on interview practice and targeted applications.";
  } else if (score >= 70) {
    grade = "Interview-Ready Soon";
    summary = "Good base. Improve project proof, metrics and role-specific positioning.";
  } else if (score >= 50) {
    grade = "Improving Profile";
    summary = "Potential is visible, but proof, role fit and interview evidence need work.";
  }
  const proofSummary = {
    skillsMentioned: detectedSkills.length,
    skillsProven: provenSkills.length,
    weakProofSkills: weakProofSkills.slice(0, 8),
    topRole: topRole.name,
    topRoleScore: topRole.score
  };
  const insightCards = [
    {
      label: "Skills Mentioned",
      value: String(detectedSkills.length),
      note: detectedSkills.length ? detectedSkills.slice(0, 6).join(", ") : "Add focused web development skills."
    },
    {
      label: "Skills Proven by Projects",
      value: `${provenSkills.length}/${Math.max(detectedSkills.length, 1)}`,
      note: weakProofSkills.length ? `Weak proof: ${weakProofSkills.slice(0, 4).join(", ")}` : "Major skills are connected with proof."
    },
    {
      label: "Best Role Fit",
      value: `${topRole.score}%`,
      note: topRole.name
    },
    {
      label: "Job Proof Score",
      value: `${pct(projectScore + skillProofScore, 40)}%`,
      note: "Based on projects, links, deployment, features and skill evidence."
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
__name(analyzeResume, "analyzeResume");
__name2(analyzeResume, "analyzeResume");
function buildRoleFits(ctx) {
  const { lower, detectedSkills, provenSkills, projectProofFound, hasDeploymentProof, hasRealWorldFeature, hasTargetRole } = ctx;
  const has = /* @__PURE__ */ __name2((items) => items.some((item) => detectedSkills.includes(item) || lower.includes(item)), "has");
  const proven = /* @__PURE__ */ __name2((items) => items.some((item) => provenSkills.includes(item)), "proven");
  const roles = [
    {
      name: "Frontend Fresher",
      score: getRoleScore([
        { ok: has(["html"]), max: 15 },
        { ok: has(["css"]), max: 15 },
        { ok: has(["javascript", "typescript"]), max: 20 },
        { ok: has(["react", "bootstrap", "tailwind", "jquery"]), max: 15 },
        { ok: proven(["html", "css", "javascript", "react"]), max: 20 },
        { ok: hasDeploymentProof, max: 15 }
      ])
    },
    {
      name: "WordPress Developer",
      score: getRoleScore([
        { ok: has(["wordpress"]), max: 25 },
        { ok: has(["php"]), max: 20 },
        { ok: has(["mysql", "sql"]), max: 15 },
        { ok: /theme|plugin|woocommerce|cms/i.test(lower), max: 15 },
        { ok: projectProofFound, max: 15 },
        { ok: hasDeploymentProof, max: 10 }
      ])
    },
    {
      name: "Magento / E-commerce Developer",
      score: getRoleScore([
        { ok: has(["magento", "adobe commerce"]), max: 30 },
        { ok: has(["php"]), max: 15 },
        { ok: has(["mysql", "sql"]), max: 10 },
        { ok: /e-commerce|ecommerce|checkout|cart|payment|api/i.test(lower), max: 20 },
        { ok: projectProofFound, max: 15 },
        { ok: hasDeploymentProof, max: 10 }
      ])
    },
    {
      name: "Full Stack Fresher",
      score: getRoleScore([
        { ok: has(["html", "css"]), max: 15 },
        { ok: has(["javascript", "typescript"]), max: 15 },
        { ok: has(["php", "node", "nodejs", "laravel", "python", "java"]), max: 20 },
        { ok: has(["mysql", "sql", "mongodb", "database"]), max: 15 },
        { ok: /api|rest|authentication|login|crud/i.test(lower), max: 20 },
        { ok: hasDeploymentProof, max: 15 }
      ])
    },
    {
      name: "Internship Ready",
      score: getRoleScore([
        { ok: hasTargetRole, max: 15 },
        { ok: detectedSkills.length >= 6, max: 20 },
        { ok: provenSkills.length >= 3, max: 25 },
        { ok: projectProofFound, max: 20 },
        { ok: hasRealWorldFeature, max: 10 },
        { ok: hasDeploymentProof, max: 10 }
      ])
    }
  ];
  return roles.sort((a, b) => b.score - a.score);
}
__name(buildRoleFits, "buildRoleFits");
__name2(buildRoleFits, "buildRoleFits");
function buildAdvancedSections(context) {
  const { categories, proofSummary, roleFits, detectedSkills, provenSkills, weakProofSkills, facts } = context;
  const getPct = /* @__PURE__ */ __name2((name) => {
    const item = categories.find((c) => c.name === name);
    return item ? pct(item.score, item.max) : 0;
  }, "getPct");
  const interviewRisks = [];
  if (weakProofSkills.length) interviewRisks.push(`You may be asked about ${weakProofSkills.slice(0, 4).join(", ")}, but project proof for these skills is weak.`);
  if (!facts.hasMetrics) interviewRisks.push("Interview answers may sound generic because measurable outcomes are missing.");
  if (!facts.hasDeploymentProof) interviewRisks.push("Deployment questions may become risky because live hosting proof is not visible.");
  if (facts.projectFeatureHits < 4) interviewRisks.push("Project-depth questions may become risky because real-world features are limited.");
  if (!interviewRisks.length) interviewRisks.push("Interview risk is moderate. Prepare strong explanations for your best project and deployment workflow.");
  const redFlags = [];
  if (!facts.hasTargetRole) redFlags.push("Target role is unclear; the resume should be focused on one primary job path.");
  if (!facts.hasGithub && !facts.hasPortfolio) redFlags.push("No public project proof is visible through GitHub, portfolio or live project links.");
  if (!facts.hasMetrics) redFlags.push("No measurable achievements are visible, so the resume may look duty-based.");
  if (facts.personalRedFlag) redFlags.push("Unnecessary personal details may reduce professional quality.");
  if (facts.projectFeatureHits < 3) redFlags.push("Projects may look like tutorial-level work because real-world features are not clearly shown.");
  if (!redFlags.length) redFlags.push("No major red flag detected, but stronger proof and sharper targeting can still improve conversion.");
  const sevenDay = [
    "Day 1: Add one focused target role headline and remove generic summary lines.",
    "Day 2: Add GitHub and live project links near each major project.",
    "Day 3: Rewrite project bullets using feature + tech stack + outcome format.",
    "Day 4: Add missing proof for weak skills listed in the Skill-to-Project Mapping section.",
    "Day 5: Add one measurable result such as pages built, modules completed, APIs integrated or performance improved.",
    "Day 6: Prepare interview explanations for your strongest project, deployment, database and API workflow.",
    "Day 7: Apply to 15 targeted internships/jobs with this improved resume."
  ];
  const thirtyDay = [
    "Week 1: Fix resume structure, role focus, GitHub/live links and project descriptions.",
    "Week 2: Build one proof project with login, database, API and responsive UI.",
    "Week 3: Deploy the project and document the workflow in GitHub README with screenshots.",
    "Week 4: Practice interview questions from your weak areas and apply with a targeted message."
  ];
  return [
    {
      title: "Skill-to-Project Mapping",
      score: getPct("Skill Proof Mapping"),
      points: [
        `${proofSummary.skillsMentioned} skills are mentioned in the resume.`,
        `${proofSummary.skillsProven} skills are connected with project/work proof.`,
        weakProofSkills.length ? `Weak proof skills: ${weakProofSkills.slice(0, 8).join(", ")}.` : "Major skills are supported by project or work context.",
        "USP insight: this is not only a resume check; it checks whether skills are proven through real work."
      ]
    },
    {
      title: "Project Proof Analysis",
      score: getPct("Project Proof Score"),
      points: [
        facts.hasGithub || facts.hasPortfolio ? "Public proof is visible through GitHub, portfolio or live project signals." : "Public proof is missing; add GitHub and live project links.",
        facts.hasDeploymentProof ? "Deployment proof is visible." : "Deployment proof is missing; add Cloudflare Pages, Vercel, Netlify, cPanel or server details.",
        facts.projectFeatureHits >= 3 ? "Real-world project features are visible." : "Add features such as login, database, API, admin panel, checkout or payment gateway.",
        "Best improvement: make every project show problem, features, tech stack, your contribution and output."
      ]
    },
    {
      title: "Role Fit Score",
      score: Math.round(roleFits.slice(0, 3).reduce((sum, role) => sum + role.score, 0) / 3),
      points: roleFits.map((role) => `${role.name}: ${role.score}% readiness.`)
    },
    {
      title: "Interview Risk Areas",
      score: getPct("Interview Readiness"),
      points: interviewRisks
    },
    {
      title: "ATS & Resume Parsing Check",
      score: getPct("ATS Readability"),
      points: [
        facts.emailFound && facts.phoneFound ? "Email and phone are readable for recruiter contact." : "Contact details need better visibility in the top header.",
        facts.standardSectionsFound ? "Standard resume sections are detected." : "Use standard section headings for better ATS readability.",
        facts.bulletsFound ? "Bullet-style formatting is visible." : "Use bullet points for easy scanning.",
        facts.wordCount >= 300 && facts.wordCount <= 900 ? "Resume length is in a practical one-page range." : "Resume length should be optimized for quick recruiter scanning."
      ]
    },
    {
      title: "Red Flags",
      score: Math.max(35, 100 - redFlags.length * 12),
      points: redFlags
    },
    {
      title: "7-Day Fix Plan",
      score: 90,
      points: sevenDay
    },
    {
      title: "30-Day Career Roadmap",
      score: 90,
      points: thirtyDay
    },
    {
      title: "Resume Rewrite Examples",
      score: 84,
      rewrite: [
        {
          old: "Worked on web development projects.",
          better: "Built and deployed responsive web pages with project-specific features, clean UI structure and live hosting proof."
        },
        {
          old: "Knowledge of HTML, CSS and JavaScript.",
          better: "Used HTML, CSS and JavaScript to build a responsive project with form handling, UI interactions and deployment-ready structure."
        },
        {
          old: "Responsible for project work.",
          better: "Implemented project modules including UI, database/API flow, testing and deployment documentation."
        }
      ]
    }
  ];
}
__name(buildAdvancedSections, "buildAdvancedSections");
__name2(buildAdvancedSections, "buildAdvancedSections");
var encoder = new TextEncoder();
async function sha256Hex(value) {
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(String(value || "")));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}
__name(sha256Hex, "sha256Hex");
__name2(sha256Hex, "sha256Hex");
async function hmacSha256Bytes(message, secret) {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(message));
  return new Uint8Array(signature);
}
__name(hmacSha256Bytes, "hmacSha256Bytes");
__name2(hmacSha256Bytes, "hmacSha256Bytes");
function bytesToBase64Url(bytes) {
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}
__name(bytesToBase64Url, "bytesToBase64Url");
__name2(bytesToBase64Url, "bytesToBase64Url");
function base64UrlToBytes(value) {
  const base64 = String(value || "").replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(String(value || "").length / 4) * 4, "=");
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}
__name(base64UrlToBytes, "base64UrlToBytes");
__name2(base64UrlToBytes, "base64UrlToBytes");
function base64UrlDecodeText(value) {
  return new TextDecoder().decode(base64UrlToBytes(value));
}
__name(base64UrlDecodeText, "base64UrlDecodeText");
__name2(base64UrlDecodeText, "base64UrlDecodeText");
async function verifyToken(token, secret) {
  if (!secret) throw new Error("REPORT_TOKEN_SECRET is not configured.");
  const [body, sig] = String(token || "").split(".");
  if (!body || !sig) throw new Error("Invalid unlock token.");
  const expected = bytesToBase64Url(await hmacSha256Bytes(body, secret));
  if (expected !== sig) throw new Error("Unlock token verification failed.");
  const payload = JSON.parse(base64UrlDecodeText(body));
  if (payload.exp && Date.now() > Number(payload.exp)) throw new Error("Unlock token expired. Please unlock the report again.");
  return payload;
}
__name(verifyToken, "verifyToken");
__name2(verifyToken, "verifyToken");
function getReportTokenSecret(env) {
  return env.REPORT_TOKEN_SECRET || env.RAZORPAY_KEY_SECRET || "";
}
__name(getReportTokenSecret, "getReportTokenSecret");
__name2(getReportTokenSecret, "getReportTokenSecret");
async function onRequestOptions() {
  return handleOptions();
}
__name(onRequestOptions, "onRequestOptions");
__name2(onRequestOptions, "onRequestOptions");
async function onRequestPost({ request, env }) {
  try {
    const payload = await readJson(request);
    const text = validateResumeText(payload.text || "");
    const reportId = (await sha256Hex(text)).slice(0, 24);
    const tokenPayload = await verifyToken(payload.unlockToken, getReportTokenSecret(env));
    if (tokenPayload.type !== "advanced-resume-report" || Number(tokenPayload.amount) !== 99) {
      return jsonResponse({ ok: false, error: "This payment token is not valid for Advanced Resume Report." }, 403);
    }
    if (tokenPayload.reportId && tokenPayload.reportId !== reportId) {
      return jsonResponse({ ok: false, error: "This unlock token belongs to a different resume scan. Please scan and unlock again." }, 403);
    }
    const report = analyzeResume(text, { includeAdvanced: true });
    return jsonResponse({
      ok: true,
      advancedUnlocked: true,
      reportId,
      advancedSections: report.advancedSections
    });
  } catch (error) {
    return jsonResponse({ ok: false, error: error.message || "Advanced report generation failed." }, error.status || 500);
  }
}
__name(onRequestPost, "onRequestPost");
__name2(onRequestPost, "onRequestPost");
async function onRequestOptions2() {
  return handleOptions();
}
__name(onRequestOptions2, "onRequestOptions2");
__name2(onRequestOptions2, "onRequestOptions");
async function onRequestPost2({ request }) {
  try {
    const payload = await readJson(request);
    const text = validateResumeText(payload.text || "");
    const report = analyzeResume(text, { includeAdvanced: false });
    const reportId = (await sha256Hex(text)).slice(0, 24);
    return jsonResponse({
      ok: true,
      ...report,
      reportId,
      protectedBy: "cloudflare-pages-function"
    });
  } catch (error) {
    return jsonResponse({ ok: false, error: error.message || "Resume scoring failed." }, error.status || 500);
  }
}
__name(onRequestPost2, "onRequestPost2");
__name2(onRequestPost2, "onRequestPost");
var routes = [
  {
    routePath: "/api/resume-advanced",
    mountPath: "/api",
    method: "OPTIONS",
    middlewares: [],
    modules: [onRequestOptions]
  },
  {
    routePath: "/api/resume-advanced",
    mountPath: "/api",
    method: "POST",
    middlewares: [],
    modules: [onRequestPost]
  },
  {
    routePath: "/api/resume-score",
    mountPath: "/api",
    method: "OPTIONS",
    middlewares: [],
    modules: [onRequestOptions2]
  },
  {
    routePath: "/api/resume-score",
    mountPath: "/api",
    method: "POST",
    middlewares: [],
    modules: [onRequestPost2]
  }
];
function lexer(str) {
  var tokens = [];
  var i = 0;
  while (i < str.length) {
    var char = str[i];
    if (char === "*" || char === "+" || char === "?") {
      tokens.push({ type: "MODIFIER", index: i, value: str[i++] });
      continue;
    }
    if (char === "\\") {
      tokens.push({ type: "ESCAPED_CHAR", index: i++, value: str[i++] });
      continue;
    }
    if (char === "{") {
      tokens.push({ type: "OPEN", index: i, value: str[i++] });
      continue;
    }
    if (char === "}") {
      tokens.push({ type: "CLOSE", index: i, value: str[i++] });
      continue;
    }
    if (char === ":") {
      var name = "";
      var j = i + 1;
      while (j < str.length) {
        var code = str.charCodeAt(j);
        if (
          // `0-9`
          code >= 48 && code <= 57 || // `A-Z`
          code >= 65 && code <= 90 || // `a-z`
          code >= 97 && code <= 122 || // `_`
          code === 95
        ) {
          name += str[j++];
          continue;
        }
        break;
      }
      if (!name)
        throw new TypeError("Missing parameter name at ".concat(i));
      tokens.push({ type: "NAME", index: i, value: name });
      i = j;
      continue;
    }
    if (char === "(") {
      var count = 1;
      var pattern = "";
      var j = i + 1;
      if (str[j] === "?") {
        throw new TypeError('Pattern cannot start with "?" at '.concat(j));
      }
      while (j < str.length) {
        if (str[j] === "\\") {
          pattern += str[j++] + str[j++];
          continue;
        }
        if (str[j] === ")") {
          count--;
          if (count === 0) {
            j++;
            break;
          }
        } else if (str[j] === "(") {
          count++;
          if (str[j + 1] !== "?") {
            throw new TypeError("Capturing groups are not allowed at ".concat(j));
          }
        }
        pattern += str[j++];
      }
      if (count)
        throw new TypeError("Unbalanced pattern at ".concat(i));
      if (!pattern)
        throw new TypeError("Missing pattern at ".concat(i));
      tokens.push({ type: "PATTERN", index: i, value: pattern });
      i = j;
      continue;
    }
    tokens.push({ type: "CHAR", index: i, value: str[i++] });
  }
  tokens.push({ type: "END", index: i, value: "" });
  return tokens;
}
__name(lexer, "lexer");
__name2(lexer, "lexer");
function parse(str, options) {
  if (options === void 0) {
    options = {};
  }
  var tokens = lexer(str);
  var _a = options.prefixes, prefixes = _a === void 0 ? "./" : _a, _b = options.delimiter, delimiter = _b === void 0 ? "/#?" : _b;
  var result = [];
  var key = 0;
  var i = 0;
  var path = "";
  var tryConsume = /* @__PURE__ */ __name2(function(type) {
    if (i < tokens.length && tokens[i].type === type)
      return tokens[i++].value;
  }, "tryConsume");
  var mustConsume = /* @__PURE__ */ __name2(function(type) {
    var value2 = tryConsume(type);
    if (value2 !== void 0)
      return value2;
    var _a2 = tokens[i], nextType = _a2.type, index = _a2.index;
    throw new TypeError("Unexpected ".concat(nextType, " at ").concat(index, ", expected ").concat(type));
  }, "mustConsume");
  var consumeText = /* @__PURE__ */ __name2(function() {
    var result2 = "";
    var value2;
    while (value2 = tryConsume("CHAR") || tryConsume("ESCAPED_CHAR")) {
      result2 += value2;
    }
    return result2;
  }, "consumeText");
  var isSafe = /* @__PURE__ */ __name2(function(value2) {
    for (var _i = 0, delimiter_1 = delimiter; _i < delimiter_1.length; _i++) {
      var char2 = delimiter_1[_i];
      if (value2.indexOf(char2) > -1)
        return true;
    }
    return false;
  }, "isSafe");
  var safePattern = /* @__PURE__ */ __name2(function(prefix2) {
    var prev = result[result.length - 1];
    var prevText = prefix2 || (prev && typeof prev === "string" ? prev : "");
    if (prev && !prevText) {
      throw new TypeError('Must have text between two parameters, missing text after "'.concat(prev.name, '"'));
    }
    if (!prevText || isSafe(prevText))
      return "[^".concat(escapeString(delimiter), "]+?");
    return "(?:(?!".concat(escapeString(prevText), ")[^").concat(escapeString(delimiter), "])+?");
  }, "safePattern");
  while (i < tokens.length) {
    var char = tryConsume("CHAR");
    var name = tryConsume("NAME");
    var pattern = tryConsume("PATTERN");
    if (name || pattern) {
      var prefix = char || "";
      if (prefixes.indexOf(prefix) === -1) {
        path += prefix;
        prefix = "";
      }
      if (path) {
        result.push(path);
        path = "";
      }
      result.push({
        name: name || key++,
        prefix,
        suffix: "",
        pattern: pattern || safePattern(prefix),
        modifier: tryConsume("MODIFIER") || ""
      });
      continue;
    }
    var value = char || tryConsume("ESCAPED_CHAR");
    if (value) {
      path += value;
      continue;
    }
    if (path) {
      result.push(path);
      path = "";
    }
    var open = tryConsume("OPEN");
    if (open) {
      var prefix = consumeText();
      var name_1 = tryConsume("NAME") || "";
      var pattern_1 = tryConsume("PATTERN") || "";
      var suffix = consumeText();
      mustConsume("CLOSE");
      result.push({
        name: name_1 || (pattern_1 ? key++ : ""),
        pattern: name_1 && !pattern_1 ? safePattern(prefix) : pattern_1,
        prefix,
        suffix,
        modifier: tryConsume("MODIFIER") || ""
      });
      continue;
    }
    mustConsume("END");
  }
  return result;
}
__name(parse, "parse");
__name2(parse, "parse");
function match(str, options) {
  var keys = [];
  var re = pathToRegexp(str, keys, options);
  return regexpToFunction(re, keys, options);
}
__name(match, "match");
__name2(match, "match");
function regexpToFunction(re, keys, options) {
  if (options === void 0) {
    options = {};
  }
  var _a = options.decode, decode = _a === void 0 ? function(x) {
    return x;
  } : _a;
  return function(pathname) {
    var m = re.exec(pathname);
    if (!m)
      return false;
    var path = m[0], index = m.index;
    var params = /* @__PURE__ */ Object.create(null);
    var _loop_1 = /* @__PURE__ */ __name2(function(i2) {
      if (m[i2] === void 0)
        return "continue";
      var key = keys[i2 - 1];
      if (key.modifier === "*" || key.modifier === "+") {
        params[key.name] = m[i2].split(key.prefix + key.suffix).map(function(value) {
          return decode(value, key);
        });
      } else {
        params[key.name] = decode(m[i2], key);
      }
    }, "_loop_1");
    for (var i = 1; i < m.length; i++) {
      _loop_1(i);
    }
    return { path, index, params };
  };
}
__name(regexpToFunction, "regexpToFunction");
__name2(regexpToFunction, "regexpToFunction");
function escapeString(str) {
  return str.replace(/([.+*?=^!:${}()[\]|/\\])/g, "\\$1");
}
__name(escapeString, "escapeString");
__name2(escapeString, "escapeString");
function flags(options) {
  return options && options.sensitive ? "" : "i";
}
__name(flags, "flags");
__name2(flags, "flags");
function regexpToRegexp(path, keys) {
  if (!keys)
    return path;
  var groupsRegex = /\((?:\?<(.*?)>)?(?!\?)/g;
  var index = 0;
  var execResult = groupsRegex.exec(path.source);
  while (execResult) {
    keys.push({
      // Use parenthesized substring match if available, index otherwise
      name: execResult[1] || index++,
      prefix: "",
      suffix: "",
      modifier: "",
      pattern: ""
    });
    execResult = groupsRegex.exec(path.source);
  }
  return path;
}
__name(regexpToRegexp, "regexpToRegexp");
__name2(regexpToRegexp, "regexpToRegexp");
function arrayToRegexp(paths, keys, options) {
  var parts = paths.map(function(path) {
    return pathToRegexp(path, keys, options).source;
  });
  return new RegExp("(?:".concat(parts.join("|"), ")"), flags(options));
}
__name(arrayToRegexp, "arrayToRegexp");
__name2(arrayToRegexp, "arrayToRegexp");
function stringToRegexp(path, keys, options) {
  return tokensToRegexp(parse(path, options), keys, options);
}
__name(stringToRegexp, "stringToRegexp");
__name2(stringToRegexp, "stringToRegexp");
function tokensToRegexp(tokens, keys, options) {
  if (options === void 0) {
    options = {};
  }
  var _a = options.strict, strict = _a === void 0 ? false : _a, _b = options.start, start = _b === void 0 ? true : _b, _c = options.end, end = _c === void 0 ? true : _c, _d = options.encode, encode = _d === void 0 ? function(x) {
    return x;
  } : _d, _e = options.delimiter, delimiter = _e === void 0 ? "/#?" : _e, _f = options.endsWith, endsWith = _f === void 0 ? "" : _f;
  var endsWithRe = "[".concat(escapeString(endsWith), "]|$");
  var delimiterRe = "[".concat(escapeString(delimiter), "]");
  var route = start ? "^" : "";
  for (var _i = 0, tokens_1 = tokens; _i < tokens_1.length; _i++) {
    var token = tokens_1[_i];
    if (typeof token === "string") {
      route += escapeString(encode(token));
    } else {
      var prefix = escapeString(encode(token.prefix));
      var suffix = escapeString(encode(token.suffix));
      if (token.pattern) {
        if (keys)
          keys.push(token);
        if (prefix || suffix) {
          if (token.modifier === "+" || token.modifier === "*") {
            var mod = token.modifier === "*" ? "?" : "";
            route += "(?:".concat(prefix, "((?:").concat(token.pattern, ")(?:").concat(suffix).concat(prefix, "(?:").concat(token.pattern, "))*)").concat(suffix, ")").concat(mod);
          } else {
            route += "(?:".concat(prefix, "(").concat(token.pattern, ")").concat(suffix, ")").concat(token.modifier);
          }
        } else {
          if (token.modifier === "+" || token.modifier === "*") {
            throw new TypeError('Can not repeat "'.concat(token.name, '" without a prefix and suffix'));
          }
          route += "(".concat(token.pattern, ")").concat(token.modifier);
        }
      } else {
        route += "(?:".concat(prefix).concat(suffix, ")").concat(token.modifier);
      }
    }
  }
  if (end) {
    if (!strict)
      route += "".concat(delimiterRe, "?");
    route += !options.endsWith ? "$" : "(?=".concat(endsWithRe, ")");
  } else {
    var endToken = tokens[tokens.length - 1];
    var isEndDelimited = typeof endToken === "string" ? delimiterRe.indexOf(endToken[endToken.length - 1]) > -1 : endToken === void 0;
    if (!strict) {
      route += "(?:".concat(delimiterRe, "(?=").concat(endsWithRe, "))?");
    }
    if (!isEndDelimited) {
      route += "(?=".concat(delimiterRe, "|").concat(endsWithRe, ")");
    }
  }
  return new RegExp(route, flags(options));
}
__name(tokensToRegexp, "tokensToRegexp");
__name2(tokensToRegexp, "tokensToRegexp");
function pathToRegexp(path, keys, options) {
  if (path instanceof RegExp)
    return regexpToRegexp(path, keys);
  if (Array.isArray(path))
    return arrayToRegexp(path, keys, options);
  return stringToRegexp(path, keys, options);
}
__name(pathToRegexp, "pathToRegexp");
__name2(pathToRegexp, "pathToRegexp");
var escapeRegex2 = /[.+?^${}()|[\]\\]/g;
function* executeRequest(request) {
  const requestPath = new URL(request.url).pathname;
  for (const route of [...routes].reverse()) {
    if (route.method && route.method !== request.method) {
      continue;
    }
    const routeMatcher = match(route.routePath.replace(escapeRegex2, "\\$&"), {
      end: false
    });
    const mountMatcher = match(route.mountPath.replace(escapeRegex2, "\\$&"), {
      end: false
    });
    const matchResult = routeMatcher(requestPath);
    const mountMatchResult = mountMatcher(requestPath);
    if (matchResult && mountMatchResult) {
      for (const handler of route.middlewares.flat()) {
        yield {
          handler,
          params: matchResult.params,
          path: mountMatchResult.path
        };
      }
    }
  }
  for (const route of routes) {
    if (route.method && route.method !== request.method) {
      continue;
    }
    const routeMatcher = match(route.routePath.replace(escapeRegex2, "\\$&"), {
      end: true
    });
    const mountMatcher = match(route.mountPath.replace(escapeRegex2, "\\$&"), {
      end: false
    });
    const matchResult = routeMatcher(requestPath);
    const mountMatchResult = mountMatcher(requestPath);
    if (matchResult && mountMatchResult && route.modules.length) {
      for (const handler of route.modules.flat()) {
        yield {
          handler,
          params: matchResult.params,
          path: matchResult.path
        };
      }
      break;
    }
  }
}
__name(executeRequest, "executeRequest");
__name2(executeRequest, "executeRequest");
var pages_template_worker_default = {
  async fetch(originalRequest, env, workerContext) {
    let request = originalRequest;
    const handlerIterator = executeRequest(request);
    let data = {};
    let isFailOpen = false;
    const next = /* @__PURE__ */ __name2(async (input, init) => {
      if (input !== void 0) {
        let url = input;
        if (typeof input === "string") {
          url = new URL(input, request.url).toString();
        }
        request = new Request(url, init);
      }
      const result = handlerIterator.next();
      if (result.done === false) {
        const { handler, params, path } = result.value;
        const context = {
          request: new Request(request.clone()),
          functionPath: path,
          next,
          params,
          get data() {
            return data;
          },
          set data(value) {
            if (typeof value !== "object" || value === null) {
              throw new Error("context.data must be an object");
            }
            data = value;
          },
          env,
          waitUntil: workerContext.waitUntil.bind(workerContext),
          passThroughOnException: /* @__PURE__ */ __name2(() => {
            isFailOpen = true;
          }, "passThroughOnException")
        };
        const response = await handler(context);
        if (!(response instanceof Response)) {
          throw new Error("Your Pages function should return a Response");
        }
        return cloneResponse(response);
      } else if ("ASSETS") {
        const response = await env["ASSETS"].fetch(request);
        return cloneResponse(response);
      } else {
        const response = await fetch(request);
        return cloneResponse(response);
      }
    }, "next");
    try {
      return await next();
    } catch (error) {
      if (isFailOpen) {
        const response = await env["ASSETS"].fetch(request);
        return cloneResponse(response);
      }
      throw error;
    }
  }
};
var cloneResponse = /* @__PURE__ */ __name2((response) => (
  // https://fetch.spec.whatwg.org/#null-body-status
  new Response(
    [101, 204, 205, 304].includes(response.status) ? null : response.body,
    response
  )
), "cloneResponse");
var drainBody = /* @__PURE__ */ __name2(async (request, env, _ctx, middlewareCtx) => {
  try {
    return await middlewareCtx.next(request, env);
  } finally {
    try {
      if (request.body !== null && !request.bodyUsed) {
        const reader = request.body.getReader();
        while (!(await reader.read()).done) {
        }
      }
    } catch (e) {
      console.error("Failed to drain the unused request body.", e);
    }
  }
}, "drainBody");
var middleware_ensure_req_body_drained_default = drainBody;
function reduceError(e) {
  return {
    name: e?.name,
    message: e?.message ?? String(e),
    stack: e?.stack,
    cause: e?.cause === void 0 ? void 0 : reduceError(e.cause)
  };
}
__name(reduceError, "reduceError");
__name2(reduceError, "reduceError");
var jsonError = /* @__PURE__ */ __name2(async (request, env, _ctx, middlewareCtx) => {
  try {
    return await middlewareCtx.next(request, env);
  } catch (e) {
    const error = reduceError(e);
    return Response.json(error, {
      status: 500,
      headers: { "MF-Experimental-Error-Stack": "true" }
    });
  }
}, "jsonError");
var middleware_miniflare3_json_error_default = jsonError;
var __INTERNAL_WRANGLER_MIDDLEWARE__ = [
  middleware_ensure_req_body_drained_default,
  middleware_miniflare3_json_error_default
];
var middleware_insertion_facade_default = pages_template_worker_default;
var __facade_middleware__ = [];
function __facade_register__(...args) {
  __facade_middleware__.push(...args.flat());
}
__name(__facade_register__, "__facade_register__");
__name2(__facade_register__, "__facade_register__");
function __facade_invokeChain__(request, env, ctx, dispatch, middlewareChain) {
  const [head, ...tail] = middlewareChain;
  const middlewareCtx = {
    dispatch,
    next(newRequest, newEnv) {
      return __facade_invokeChain__(newRequest, newEnv, ctx, dispatch, tail);
    }
  };
  return head(request, env, ctx, middlewareCtx);
}
__name(__facade_invokeChain__, "__facade_invokeChain__");
__name2(__facade_invokeChain__, "__facade_invokeChain__");
function __facade_invoke__(request, env, ctx, dispatch, finalMiddleware) {
  return __facade_invokeChain__(request, env, ctx, dispatch, [
    ...__facade_middleware__,
    finalMiddleware
  ]);
}
__name(__facade_invoke__, "__facade_invoke__");
__name2(__facade_invoke__, "__facade_invoke__");
var __Facade_ScheduledController__ = class ___Facade_ScheduledController__ {
  static {
    __name(this, "___Facade_ScheduledController__");
  }
  constructor(scheduledTime, cron, noRetry) {
    this.scheduledTime = scheduledTime;
    this.cron = cron;
    this.#noRetry = noRetry;
  }
  scheduledTime;
  cron;
  static {
    __name2(this, "__Facade_ScheduledController__");
  }
  #noRetry;
  noRetry() {
    if (!(this instanceof ___Facade_ScheduledController__)) {
      throw new TypeError("Illegal invocation");
    }
    this.#noRetry();
  }
};
function wrapExportedHandler(worker) {
  if (__INTERNAL_WRANGLER_MIDDLEWARE__ === void 0 || __INTERNAL_WRANGLER_MIDDLEWARE__.length === 0) {
    return worker;
  }
  for (const middleware of __INTERNAL_WRANGLER_MIDDLEWARE__) {
    __facade_register__(middleware);
  }
  const fetchDispatcher = /* @__PURE__ */ __name2(function(request, env, ctx) {
    if (worker.fetch === void 0) {
      throw new Error("Handler does not export a fetch() function.");
    }
    return worker.fetch(request, env, ctx);
  }, "fetchDispatcher");
  return {
    ...worker,
    fetch(request, env, ctx) {
      const dispatcher = /* @__PURE__ */ __name2(function(type, init) {
        if (type === "scheduled" && worker.scheduled !== void 0) {
          const controller = new __Facade_ScheduledController__(
            Date.now(),
            init.cron ?? "",
            () => {
            }
          );
          return worker.scheduled(controller, env, ctx);
        }
      }, "dispatcher");
      return __facade_invoke__(request, env, ctx, dispatcher, fetchDispatcher);
    }
  };
}
__name(wrapExportedHandler, "wrapExportedHandler");
__name2(wrapExportedHandler, "wrapExportedHandler");
function wrapWorkerEntrypoint(klass) {
  if (__INTERNAL_WRANGLER_MIDDLEWARE__ === void 0 || __INTERNAL_WRANGLER_MIDDLEWARE__.length === 0) {
    return klass;
  }
  for (const middleware of __INTERNAL_WRANGLER_MIDDLEWARE__) {
    __facade_register__(middleware);
  }
  return class extends klass {
    #fetchDispatcher = /* @__PURE__ */ __name2((request, env, ctx) => {
      this.env = env;
      this.ctx = ctx;
      if (super.fetch === void 0) {
        throw new Error("Entrypoint class does not define a fetch() function.");
      }
      return super.fetch(request);
    }, "#fetchDispatcher");
    #dispatcher = /* @__PURE__ */ __name2((type, init) => {
      if (type === "scheduled" && super.scheduled !== void 0) {
        const controller = new __Facade_ScheduledController__(
          Date.now(),
          init.cron ?? "",
          () => {
          }
        );
        return super.scheduled(controller);
      }
    }, "#dispatcher");
    fetch(request) {
      return __facade_invoke__(
        request,
        this.env,
        this.ctx,
        this.#dispatcher,
        this.#fetchDispatcher
      );
    }
  };
}
__name(wrapWorkerEntrypoint, "wrapWorkerEntrypoint");
__name2(wrapWorkerEntrypoint, "wrapWorkerEntrypoint");
var WRAPPED_ENTRY;
if (typeof middleware_insertion_facade_default === "object") {
  WRAPPED_ENTRY = wrapExportedHandler(middleware_insertion_facade_default);
} else if (typeof middleware_insertion_facade_default === "function") {
  WRAPPED_ENTRY = wrapWorkerEntrypoint(middleware_insertion_facade_default);
}
var middleware_loader_entry_default = WRAPPED_ENTRY;

// C:/Users/user/AppData/Local/npm-cache/_npx/32026684e21afda6/node_modules/wrangler/templates/middleware/middleware-ensure-req-body-drained.ts
var drainBody2 = /* @__PURE__ */ __name(async (request, env, _ctx, middlewareCtx) => {
  try {
    return await middlewareCtx.next(request, env);
  } finally {
    try {
      if (request.body !== null && !request.bodyUsed) {
        const reader = request.body.getReader();
        while (!(await reader.read()).done) {
        }
      }
    } catch (e) {
      console.error("Failed to drain the unused request body.", e);
    }
  }
}, "drainBody");
var middleware_ensure_req_body_drained_default2 = drainBody2;

// C:/Users/user/AppData/Local/npm-cache/_npx/32026684e21afda6/node_modules/wrangler/templates/middleware/middleware-miniflare3-json-error.ts
function reduceError2(e) {
  return {
    name: e?.name,
    message: e?.message ?? String(e),
    stack: e?.stack,
    cause: e?.cause === void 0 ? void 0 : reduceError2(e.cause)
  };
}
__name(reduceError2, "reduceError");
var jsonError2 = /* @__PURE__ */ __name(async (request, env, _ctx, middlewareCtx) => {
  try {
    return await middlewareCtx.next(request, env);
  } catch (e) {
    const error = reduceError2(e);
    return Response.json(error, {
      status: 500,
      headers: { "MF-Experimental-Error-Stack": "true" }
    });
  }
}, "jsonError");
var middleware_miniflare3_json_error_default2 = jsonError2;

// .wrangler/tmp/bundle-tbR9wR/middleware-insertion-facade.js
var __INTERNAL_WRANGLER_MIDDLEWARE__2 = [
  middleware_ensure_req_body_drained_default2,
  middleware_miniflare3_json_error_default2
];
var middleware_insertion_facade_default2 = middleware_loader_entry_default;

// C:/Users/user/AppData/Local/npm-cache/_npx/32026684e21afda6/node_modules/wrangler/templates/middleware/common.ts
var __facade_middleware__2 = [];
function __facade_register__2(...args) {
  __facade_middleware__2.push(...args.flat());
}
__name(__facade_register__2, "__facade_register__");
function __facade_invokeChain__2(request, env, ctx, dispatch, middlewareChain) {
  const [head, ...tail] = middlewareChain;
  const middlewareCtx = {
    dispatch,
    next(newRequest, newEnv) {
      return __facade_invokeChain__2(newRequest, newEnv, ctx, dispatch, tail);
    }
  };
  return head(request, env, ctx, middlewareCtx);
}
__name(__facade_invokeChain__2, "__facade_invokeChain__");
function __facade_invoke__2(request, env, ctx, dispatch, finalMiddleware) {
  return __facade_invokeChain__2(request, env, ctx, dispatch, [
    ...__facade_middleware__2,
    finalMiddleware
  ]);
}
__name(__facade_invoke__2, "__facade_invoke__");

// .wrangler/tmp/bundle-tbR9wR/middleware-loader.entry.ts
var __Facade_ScheduledController__2 = class ___Facade_ScheduledController__2 {
  constructor(scheduledTime, cron, noRetry) {
    this.scheduledTime = scheduledTime;
    this.cron = cron;
    this.#noRetry = noRetry;
  }
  scheduledTime;
  cron;
  static {
    __name(this, "__Facade_ScheduledController__");
  }
  #noRetry;
  noRetry() {
    if (!(this instanceof ___Facade_ScheduledController__2)) {
      throw new TypeError("Illegal invocation");
    }
    this.#noRetry();
  }
};
function wrapExportedHandler2(worker) {
  if (__INTERNAL_WRANGLER_MIDDLEWARE__2 === void 0 || __INTERNAL_WRANGLER_MIDDLEWARE__2.length === 0) {
    return worker;
  }
  for (const middleware of __INTERNAL_WRANGLER_MIDDLEWARE__2) {
    __facade_register__2(middleware);
  }
  const fetchDispatcher = /* @__PURE__ */ __name(function(request, env, ctx) {
    if (worker.fetch === void 0) {
      throw new Error("Handler does not export a fetch() function.");
    }
    return worker.fetch(request, env, ctx);
  }, "fetchDispatcher");
  return {
    ...worker,
    fetch(request, env, ctx) {
      const dispatcher = /* @__PURE__ */ __name(function(type, init) {
        if (type === "scheduled" && worker.scheduled !== void 0) {
          const controller = new __Facade_ScheduledController__2(
            Date.now(),
            init.cron ?? "",
            () => {
            }
          );
          return worker.scheduled(controller, env, ctx);
        }
      }, "dispatcher");
      return __facade_invoke__2(request, env, ctx, dispatcher, fetchDispatcher);
    }
  };
}
__name(wrapExportedHandler2, "wrapExportedHandler");
function wrapWorkerEntrypoint2(klass) {
  if (__INTERNAL_WRANGLER_MIDDLEWARE__2 === void 0 || __INTERNAL_WRANGLER_MIDDLEWARE__2.length === 0) {
    return klass;
  }
  for (const middleware of __INTERNAL_WRANGLER_MIDDLEWARE__2) {
    __facade_register__2(middleware);
  }
  return class extends klass {
    #fetchDispatcher = /* @__PURE__ */ __name((request, env, ctx) => {
      this.env = env;
      this.ctx = ctx;
      if (super.fetch === void 0) {
        throw new Error("Entrypoint class does not define a fetch() function.");
      }
      return super.fetch(request);
    }, "#fetchDispatcher");
    #dispatcher = /* @__PURE__ */ __name((type, init) => {
      if (type === "scheduled" && super.scheduled !== void 0) {
        const controller = new __Facade_ScheduledController__2(
          Date.now(),
          init.cron ?? "",
          () => {
          }
        );
        return super.scheduled(controller);
      }
    }, "#dispatcher");
    fetch(request) {
      return __facade_invoke__2(
        request,
        this.env,
        this.ctx,
        this.#dispatcher,
        this.#fetchDispatcher
      );
    }
  };
}
__name(wrapWorkerEntrypoint2, "wrapWorkerEntrypoint");
var WRAPPED_ENTRY2;
if (typeof middleware_insertion_facade_default2 === "object") {
  WRAPPED_ENTRY2 = wrapExportedHandler2(middleware_insertion_facade_default2);
} else if (typeof middleware_insertion_facade_default2 === "function") {
  WRAPPED_ENTRY2 = wrapWorkerEntrypoint2(middleware_insertion_facade_default2);
}
var middleware_loader_entry_default2 = WRAPPED_ENTRY2;
export {
  __INTERNAL_WRANGLER_MIDDLEWARE__2 as __INTERNAL_WRANGLER_MIDDLEWARE__,
  middleware_loader_entry_default2 as default
};
//# sourceMappingURL=functionsWorker-0.5353621274107482.js.map
