const MAX_TEXT_LEN = 900;

const OPTION_LABELS = {
  qualification: {
    mtech: 'M.Tech / M.E. CSE',
    btech: 'B.Tech CSE',
    mca: 'MCA / Computer Applications',
    faculty: 'Working Faculty / Assistant Professor'
  },
  interest: {
    'ai-education': 'AI in Education / Employability Analytics',
    recommender: 'Recommender Systems / Data Mining',
    'software-ai': 'AI in Software Engineering',
    cybersecurity: 'Cybersecurity with Machine Learning',
    'cloud-edge': 'Cloud / Edge Computing',
    nlp: 'NLP / Indian Language AI'
  },
  goal: {
    academic: 'Academic career / Assistant Professor',
    publication: 'Research publication and PhD admission',
    industry: 'Industry research / applied AI profile',
    college: 'College project/research guidance'
  },
  coding: {
    basic: 'Basic coding level',
    intermediate: 'Intermediate coding level',
    strong: 'Strong coding level'
  },
  dataset: {
    no: 'No dataset yet',
    public: 'Can use public datasets',
    own: 'Can collect own dataset'
  },
  mode: {
    'full-time': 'Full-time PhD',
    'part-time': 'Part-time / External PhD',
    'not-sure': 'Not sure yet'
  },
  timeline: {
    '3-months': '3 months',
    '6-months': '6 months',
    '12-months': '12 months',
    'not-sure': 'Not sure'
  },
  publication: {
    none: 'No publication yet',
    conference: 'Conference target',
    journal: 'Journal target',
    scopus: 'Scopus/SCI target'
  }
};

const KNOWLEDGE = {
  'ai-education': {
    area: 'AI in Education / Employability Analytics',
    titles: [
      'Explainable Machine Learning Framework for Predicting Skill Gaps and Employability among Computer Science Students',
      'Adaptive Career Readiness Recommendation System for CSE Students using Explainable AI',
      'Learning Analytics Model for Predicting Programming Readiness using Academic, Project and Coding Assessment Data'
    ],
    gap: 'Most education analytics models predict marks, placement or pass/fail status, but they rarely explain the exact skill gap and next action for each student.',
    methods: ['XGBoost / Random Forest baseline', 'SHAP or LIME explainability', 'skill clustering', 'recommendation rules', 'dashboard-based intervention tracking'],
    datasets: ['marks and attendance', 'coding-test score', 'project completion', 'resume score', 'internship status', 'placement result'],
    metrics: ['accuracy', 'F1-score', 'AUC', 'SHAP explanation consistency', 'recommendation usefulness feedback'],
    contribution: 'A mentor-friendly system that does not only predict risk, but also explains why the learner is weak and what should be improved next.'
  },
  recommender: {
    area: 'Recommender Systems / Data Mining',
    titles: [
      'Explainable Cross-Selling Recommendation System using User Shopping Behaviour and Reinforcement Learning',
      'Hybrid Recommendation Framework for Personalized Product Suggestions using Behavioural and Contextual Signals',
      'Trust-Aware Recommender System for E-commerce using Explainable Machine Learning'
    ],
    gap: 'Many recommender systems optimize click or purchase probability but fail to explain the recommendation, handle cold-start users, or balance accuracy with trust.',
    methods: ['collaborative filtering', 'content-based filtering', 'association rules', 'learning-to-rank', 'contextual bandits', 'explainable ranking'],
    datasets: ['transaction data', 'clickstream data', 'shopping-cart logs', 'product metadata', 'public e-commerce datasets'],
    metrics: ['precision@k', 'recall@k', 'NDCG', 'coverage', 'diversity', 'explanation usefulness'],
    contribution: 'A practical recommendation framework that improves personalization while showing transparent reasons behind suggestions.'
  },
  'software-ai': {
    area: 'AI in Software Engineering',
    titles: [
      'AI-Assisted Code Quality Prediction and Bug Risk Detection for Student and Entry-Level Developer Projects',
      'Machine Learning Based Defect Prediction Framework for Web Application Code Repositories',
      'Explainable AI Model for Automated Software Testing Priority and Code Review Support'
    ],
    gap: 'AI can generate code, but students and junior developers still need a measurable way to identify weak code, risky modules and missing tests.',
    methods: ['static code metrics', 'Git commit features', 'issue-tracker signals', 'ML classification', 'code embeddings', 'explainable defect prediction'],
    datasets: ['GitHub repositories', 'bug reports', 'commit history', 'student project submissions', 'defect benchmark datasets'],
    metrics: ['precision', 'recall', 'F1-score', 'false-positive rate', 'module-level risk ranking', 'developer feedback'],
    contribution: 'An explainable system that helps mentors and teams identify bug-prone files and code-quality weaknesses before deployment.'
  },
  cybersecurity: {
    area: 'Cybersecurity with Machine Learning',
    titles: [
      'Privacy-Preserving Machine Learning Framework for Phishing and Malicious URL Detection',
      'Explainable Anomaly Detection System for Network Security using Hybrid Machine Learning',
      'Lightweight ML Model for Real-Time Malware or Phishing Classification in Resource-Constrained Systems'
    ],
    gap: 'Security models often claim high accuracy but do not provide transparent reasons, low false positives or practical deployment constraints.',
    methods: ['feature engineering', 'anomaly detection', 'Random Forest / XGBoost', 'deep learning baseline', 'explainability', 'privacy-aware evaluation'],
    datasets: ['phishing URLs', 'network intrusion data', 'system logs', 'malicious URL datasets', 'benchmark security datasets'],
    metrics: ['accuracy', 'precision', 'recall', 'F1-score', 'false-positive rate', 'latency'],
    contribution: 'A transparent detection framework that balances security accuracy, explanation and real-time usability.'
  },
  'cloud-edge': {
    area: 'Cloud / Edge Computing',
    titles: [
      'Energy-Aware Task Scheduling in Edge-Cloud Environments using Machine Learning',
      'AI-Based Resource Allocation Framework for Cloud Workloads with Cost and Latency Optimization',
      'Secure and Lightweight Edge-AI Deployment Framework for Real-Time Applications'
    ],
    gap: 'Cloud and edge solutions often optimize only one factor such as latency, while ignoring cost, energy, workload variation and deployment constraints.',
    methods: ['workload prediction', 'scheduling algorithms', 'reinforcement learning', 'simulation', 'cost-latency optimization', 'benchmark comparison'],
    datasets: ['cloud workload traces', 'server logs', 'edge task simulations', 'container metrics', 'benchmark scheduling datasets'],
    metrics: ['latency', 'cost', 'energy use', 'throughput', 'SLA violation rate', 'resource utilization'],
    contribution: 'A practical scheduling or allocation model that improves cost, latency and resource utilization together.'
  },
  nlp: {
    area: 'NLP / Indian Language AI',
    titles: [
      'Domain-Specific NLP Model for Career Guidance and Academic Query Classification in Indian Higher Education',
      'Fake News and Misinformation Detection in Indian Language Social Media using Explainable NLP',
      'Low-Resource Indian Language Educational Chatbot using Retrieval-Augmented Generation and Evaluation Metrics'
    ],
    gap: 'Generic English-first NLP systems often fail on Indian academic context, Hinglish queries and low-resource language patterns.',
    methods: ['text classification', 'embeddings', 'transformer baseline', 'retrieval-augmented generation', 'human evaluation', 'error analysis'],
    datasets: ['academic FAQs', 'student queries', 'Hinglish text', 'public NLP datasets', 'manually annotated domain data'],
    metrics: ['accuracy', 'F1-score', 'BLEU/ROUGE where relevant', 'human helpfulness score', 'groundedness', 'error categories'],
    contribution: 'A domain-specific NLP system that handles Indian educational language patterns better than a generic chatbot.'
  }
};

function cleanText(value, maxLen = MAX_TEXT_LEN) {
  return String(value || '')
    .replace(/[<>`{}]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, maxLen);
}

function pick(value, group, fallback) {
  return Object.prototype.hasOwnProperty.call(OPTION_LABELS[group], value) ? value : fallback;
}

export function validateResearchPayload(raw = {}) {
  const interest = pick(raw.interest, 'interest', 'ai-education');
  return {
    qualification: pick(raw.qualification, 'qualification', 'mtech'),
    interest,
    goal: pick(raw.goal, 'goal', 'academic'),
    coding: pick(raw.coding, 'coding', 'intermediate'),
    dataset: pick(raw.dataset, 'dataset', 'no'),
    mode: pick(raw.mode, 'mode', 'not-sure'),
    timeline: pick(raw.timeline, 'timeline', '6-months'),
    publication: pick(raw.publication, 'publication', 'none'),
    domainProblem: cleanText(raw.domainProblem, 700),
    existingSkills: cleanText(raw.existingSkills, 400),
    targetAudience: cleanText(raw.targetAudience, 300),
    cityOrCollegeContext: cleanText(raw.cityOrCollegeContext, 250),
    wantApi: raw.wantApi !== false,
    _base: KNOWLEDGE[interest]
  };
}

export function labelsFor(input) {
  return {
    qualification: OPTION_LABELS.qualification[input.qualification],
    interest: OPTION_LABELS.interest[input.interest],
    goal: OPTION_LABELS.goal[input.goal],
    coding: OPTION_LABELS.coding[input.coding],
    dataset: OPTION_LABELS.dataset[input.dataset],
    mode: OPTION_LABELS.mode[input.mode],
    timeline: OPTION_LABELS.timeline[input.timeline],
    publication: OPTION_LABELS.publication[input.publication]
  };
}

function scoreFit(input) {
  let score = 58;
  if (input.qualification === 'mtech' || input.qualification === 'faculty') score += 10;
  if (input.dataset === 'own') score += 12;
  if (input.dataset === 'public') score += 7;
  if (input.coding === 'strong') score += 10;
  if (input.coding === 'intermediate') score += 6;
  if (input.publication === 'conference') score += 5;
  if (input.publication === 'journal' || input.publication === 'scopus') score += 8;
  if (input.domainProblem.length > 50) score += 7;
  return Math.max(45, Math.min(score, 95));
}

function complexity(input) {
  if (input.coding === 'basic' && input.dataset === 'no') return 'Medium. Start with a narrow classical ML topic and avoid overclaiming deep learning novelty.';
  if (input.coding === 'strong' && input.dataset === 'own') return 'High but publishable. You can add stronger modelling, explainability and a prototype/dashboard.';
  return 'Medium to high. Keep the first version simple, then improve with explainability, validation and comparative metrics.';
}

function datasetPlan(input, base) {
  if (input.dataset === 'own') {
    return [
      `Collect a small original dataset around ${input.targetAudience || 'your target users'} with consent and clean feature definitions.`,
      `Combine it with ${base.datasets.slice(0, 3).join(', ')} for richer features.`,
      'Create a data dictionary and missing-value handling plan before model training.'
    ];
  }
  if (input.dataset === 'public') {
    return [
      `Start with public datasets related to ${base.datasets.slice(0, 4).join(', ')}.`,
      'Add one small local validation set or survey so the work does not look like a simple Kaggle-style experiment.',
      'Document preprocessing, bias limits and evaluation constraints clearly.'
    ];
  }
  return [
    `Before finalizing the title, identify at least two sources for ${base.datasets.slice(0, 4).join(', ')}.`,
    'Build a minimum dataset plan: fields, data source, collection method, privacy note and expected sample size.',
    'Choose a topic where data can be collected realistically within your timeline.'
  ];
}

function roadmap(input) {
  const baseSteps = [
    'Week 1–2: read 15–20 recent papers and write the exact research gap.',
    'Week 3–4: define dataset, features, baseline model and evaluation metrics.',
    'Month 2: build baseline model and compare at least 2–3 methods.',
    'Month 3: add explainability, recommendation layer or deployment prototype.',
    'Month 4+: prepare proposal, conference paper draft and PhD interview pitch.'
  ];
  if (input.timeline === '3-months') return baseSteps.slice(0, 4);
  if (input.timeline === '12-months') return baseSteps.concat(['Month 6–12: refine novelty, collect more validation data and target journal/Scopus publication.']);
  return baseSteps;
}

export function buildExpertPlan(input) {
  const base = input._base || KNOWLEDGE['ai-education'];
  const labels = labelsFor(input);
  const titleIndex = (input.qualification.length + input.goal.length + input.coding.length + input.dataset.length) % base.titles.length;
  const primaryTitle = base.titles[titleIndex];
  const problemLine = input.domainProblem ? `User-specific angle: ${input.domainProblem}` : `User-specific angle: focus on ${labels.goal.toLowerCase()} with practical implementation and measurable output.`;
  const fitScore = scoreFit(input);
  const titles = [
    primaryTitle,
    ...base.titles.filter(title => title !== primaryTitle)
  ].slice(0, 3);

  return {
    ok: true,
    source: 'expert-engine',
    fitScore,
    fitLevel: fitScore >= 80 ? 'Strong fit' : fitScore >= 65 ? 'Good fit' : 'Needs narrowing',
    summary: `Best direction: ${base.area}. ${problemLine}`,
    recommendedTitles: titles,
    selectedTitle: primaryTitle,
    area: base.area,
    researchGap: `${base.gap} ${problemLine}`,
    noveltyAngle: [
      'Do not present it as a generic AI chatbot. Present it as a decision-support system with scoring, explanation, roadmap and measurable evaluation.',
      input.domainProblem ? `Convert this real problem into features and measurable outcomes: ${input.domainProblem}` : 'Use a narrow target user group and a measurable outcome instead of a broad topic.',
      'Add explainability and action recommendation because this is where normal chatbot answers are weak.'
    ],
    methodStack: base.methods,
    datasetPlan: datasetPlan(input, base),
    evaluationMetrics: base.metrics,
    expectedContribution: base.contribution,
    difficulty: complexity(input),
    roadmap: roadmap(input),
    proposalOutline: [
      `Title: ${primaryTitle}`,
      `Problem statement: ${problemLine}`,
      `Objectives: prediction, explanation, recommendation and validation.`,
      `Methodology: collect/prepare data, build baseline, compare improved model, explain output and evaluate usefulness.`,
      `Expected contribution: ${base.contribution}`
    ],
    interviewPitch: `My proposed research is in ${base.area}. I want to solve a narrow problem for ${input.targetAudience || 'CSE students / academic users'} by building a model that not only predicts an outcome but also explains the reason and recommends the next action. I will validate it using ${base.metrics.slice(0, 4).join(', ')} and compare it with baseline methods.`,
    publicationPath: [
      labels.publication === 'No publication yet' ? 'Start with a small conference paper based on baseline model + literature review.' : `Target: ${labels.publication}. Keep novelty, dataset description and evaluation strong.`,
      'After the first paper, extend with explainability, deployment prototype or local dataset validation.',
      'Use the proposal as a 2-page PhD synopsis and prepare 5–7 interview questions from it.'
    ],
    userProfile: labels
  };
}

export function buildResearchPrompt(input) {
  const labels = labelsFor(input);
  const basePlan = buildExpertPlan(input);
  return `You are an Indian CSE PhD research advisor. Generate a customized, practical, non-generic research roadmap. The output must be valid JSON only, no markdown, no commentary.

User profile:
- Qualification: ${labels.qualification}
- Interest: ${labels.interest}
- Goal: ${labels.goal}
- Coding level: ${labels.coding}
- Dataset availability: ${labels.dataset}
- Preferred PhD mode: ${labels.mode}
- Timeline: ${labels.timeline}
- Publication target: ${labels.publication}
- Problem/user context: ${input.domainProblem || 'not provided'}
- Existing skills/tools: ${input.existingSkills || 'not provided'}
- Target audience: ${input.targetAudience || 'not provided'}
- City/college context: ${input.cityOrCollegeContext || 'not provided'}

Use this expert baseline so the answer remains structured and grounded:
${JSON.stringify(basePlan)}

Return exactly this JSON shape:
{
  "ok": true,
  "source": "ai-api",
  "fitScore": number,
  "fitLevel": string,
  "summary": string,
  "selectedTitle": string,
  "recommendedTitles": [string, string, string],
  "area": string,
  "researchGap": string,
  "noveltyAngle": [string, string, string],
  "methodStack": [string, string, string, string, string],
  "datasetPlan": [string, string, string],
  "evaluationMetrics": [string, string, string, string, string],
  "expectedContribution": string,
  "difficulty": string,
  "roadmap": [string, string, string, string, string],
  "proposalOutline": [string, string, string, string, string],
  "interviewPitch": string,
  "publicationPath": [string, string, string],
  "userProfile": {"qualification": string, "interest": string, "goal": string, "coding": string, "dataset": string, "mode": string, "timeline": string, "publication": string}
}

Rules:
- Make it better than a normal chatbot by being specific, measurable and action-oriented.
- Do not claim guaranteed PhD admission, publication acceptance or ranking.
- Avoid fake citations and avoid naming datasets unless they are commonly known or described generically.
- Keep each item concise but useful.`;
}
