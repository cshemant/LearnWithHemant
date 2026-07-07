import { jsonResponse, handleOptions, readJson } from '../_utils/http.js';
import { buildExpertPlan, buildResearchPrompt, validateResearchPayload } from '../_utils/research-planner.js';

export async function onRequestOptions() {
  return handleOptions();
}

function extractJson(text) {
  const raw = String(text || '').trim();
  if (!raw) throw new Error('Empty AI response.');
  try {
    return JSON.parse(raw);
  } catch (_) {
    const match = raw.match(/\{[\s\S]*\}/);
    if (!match) throw new Error('AI response did not contain JSON.');
    return JSON.parse(match[0]);
  }
}

function enforcePlanShape(plan, fallback, sourceName) {
  const safe = { ...fallback, ...plan, source: sourceName || plan.source || fallback.source, ok: true };
  safe.fitScore = Math.max(40, Math.min(98, Number(safe.fitScore || fallback.fitScore || 70)));
  safe.recommendedTitles = Array.isArray(safe.recommendedTitles) && safe.recommendedTitles.length ? safe.recommendedTitles.slice(0, 3) : fallback.recommendedTitles;
  safe.noveltyAngle = Array.isArray(safe.noveltyAngle) && safe.noveltyAngle.length ? safe.noveltyAngle.slice(0, 4) : fallback.noveltyAngle;
  safe.methodStack = Array.isArray(safe.methodStack) && safe.methodStack.length ? safe.methodStack.slice(0, 7) : fallback.methodStack;
  safe.datasetPlan = Array.isArray(safe.datasetPlan) && safe.datasetPlan.length ? safe.datasetPlan.slice(0, 5) : fallback.datasetPlan;
  safe.evaluationMetrics = Array.isArray(safe.evaluationMetrics) && safe.evaluationMetrics.length ? safe.evaluationMetrics.slice(0, 7) : fallback.evaluationMetrics;
  safe.roadmap = Array.isArray(safe.roadmap) && safe.roadmap.length ? safe.roadmap.slice(0, 7) : fallback.roadmap;
  safe.proposalOutline = Array.isArray(safe.proposalOutline) && safe.proposalOutline.length ? safe.proposalOutline.slice(0, 6) : fallback.proposalOutline;
  safe.publicationPath = Array.isArray(safe.publicationPath) && safe.publicationPath.length ? safe.publicationPath.slice(0, 5) : fallback.publicationPath;
  return safe;
}


const RESEARCH_PLAN_SCHEMA = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' },
    source: { type: 'string' },
    fitScore: { type: 'number' },
    fitLevel: { type: 'string' },
    summary: { type: 'string' },
    selectedTitle: { type: 'string' },
    recommendedTitles: { type: 'array', items: { type: 'string' } },
    area: { type: 'string' },
    researchGap: { type: 'string' },
    noveltyAngle: { type: 'array', items: { type: 'string' } },
    methodStack: { type: 'array', items: { type: 'string' } },
    datasetPlan: { type: 'array', items: { type: 'string' } },
    evaluationMetrics: { type: 'array', items: { type: 'string' } },
    expectedContribution: { type: 'string' },
    difficulty: { type: 'string' },
    roadmap: { type: 'array', items: { type: 'string' } },
    proposalOutline: { type: 'array', items: { type: 'string' } },
    interviewPitch: { type: 'string' },
    publicationPath: { type: 'array', items: { type: 'string' } },
    userProfile: {
      type: 'object',
      properties: {
        qualification: { type: 'string' },
        interest: { type: 'string' },
        goal: { type: 'string' },
        coding: { type: 'string' },
        dataset: { type: 'string' },
        mode: { type: 'string' },
        timeline: { type: 'string' },
        publication: { type: 'string' }
      },
      required: ['qualification', 'interest', 'goal', 'coding', 'dataset', 'mode', 'timeline', 'publication']
    }
  },
  required: [
    'ok', 'fitScore', 'fitLevel', 'summary', 'selectedTitle', 'recommendedTitles',
    'area', 'researchGap', 'noveltyAngle', 'methodStack', 'datasetPlan',
    'evaluationMetrics', 'expectedContribution', 'difficulty', 'roadmap',
    'proposalOutline', 'interviewPitch', 'publicationPath', 'userProfile'
  ]
};

async function callOpenAI(prompt, env) {
  const model = env.OPENAI_MODEL || 'gpt-4.1-mini';
  const response = await fetch('https://api.openai.com/v1/responses', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${env.OPENAI_API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      model,
      input: [
        { role: 'system', content: 'Return valid JSON only. You are a careful CSE PhD research advisor for Indian students and faculty.' },
        { role: 'user', content: prompt }
      ],
      text: { format: { type: 'json_object' } },
      temperature: 0.45,
      max_output_tokens: 2200
    })
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`OpenAI API error ${response.status}: ${detail.slice(0, 200)}`);
  }
  const data = await response.json();
  const outputText = data.output_text || (data.output || [])
    .flatMap(item => item.content || [])
    .map(part => part.text || '')
    .join('\n');
  return extractJson(outputText);
}

function readGeminiInteractionText(data) {
  const directText =
    data?.output_text ||
    data?.outputText ||
    data?.text ||
    data?.response?.output_text ||
    data?.response?.outputText ||
    '';

  if (String(directText).trim()) return String(directText).trim();

  // REST Interactions API returns model text inside steps[].content[].text.
  // output_text is an SDK convenience field, so it may not appear in raw REST responses.
  const stepText = (data?.steps || [])
    .filter(step => !step.type || step.type === 'model_output')
    .flatMap(step => step.content || step.outputs || [])
    .map(part => {
      if (typeof part === 'string') return part;
      if (typeof part?.text === 'string') return part.text;
      if (typeof part?.content === 'string') return part.content;
      return '';
    })
    .filter(Boolean)
    .join('\n')
    .trim();

  if (stepText) return stepText;

  // Legacy Interactions API shape used outputs[].text.
  const legacyText = (data?.outputs || [])
    .map(output => {
      if (typeof output === 'string') return output;
      if (typeof output?.text === 'string') return output.text;
      if (Array.isArray(output?.content)) {
        return output.content.map(part => part?.text || '').filter(Boolean).join('\n');
      }
      return '';
    })
    .filter(Boolean)
    .join('\n')
    .trim();

  return legacyText;
}

async function callGemini(prompt, env) {
  const model = env.GEMINI_MODEL || 'gemini-3-flash-preview';

  const response = await fetch('https://generativelanguage.googleapis.com/v1beta/interactions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-goog-api-key': env.GEMINI_API_KEY,
      'Api-Revision': '2026-05-20'
    },
    body: JSON.stringify({
      model,
      input: prompt,
      response_format: {
        type: 'text',
        mime_type: 'application/json',
        schema: RESEARCH_PLAN_SCHEMA
      }
    })
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Gemini API error ${response.status}: ${detail.slice(0, 260)}`);
  }

  const data = await response.json();
  const outputText = readGeminiInteractionText(data);

  if (!String(outputText).trim()) {
    const shape = Object.keys(data || {}).slice(0, 8).join(', ') || 'no response keys';
    throw new Error(`Gemini returned no readable text from the Interactions API. Response keys: ${shape}`);
  }

  return extractJson(outputText);
}

export async function onRequestPost({ request, env }) {
  try {
    const payload = await readJson(request);
    const input = validateResearchPayload(payload);
    const fallback = buildExpertPlan(input);
    const prompt = buildResearchPrompt(input);

    let apiError = '';
    if (input.wantApi && env.OPENAI_API_KEY) {
      try {
        const plan = await callOpenAI(prompt, env);
        return jsonResponse(enforcePlanShape(plan, fallback, 'openai-api'));
      } catch (error) {
        apiError = error.message || 'OpenAI API failed.';
      }
    }

    if (input.wantApi && env.GEMINI_API_KEY) {
      try {
        const plan = await callGemini(prompt, env);
        return jsonResponse(enforcePlanShape(plan, fallback, 'gemini-api'));
      } catch (error) {
        apiError = error.message || 'Gemini API failed.';
      }
    }

    return jsonResponse({
      ...fallback,
      source: apiError ? 'expert-engine-api-fallback' : 'expert-engine-no-api-key',
      apiNote: apiError ? `AI API failed, so expert fallback was used. ${apiError}` : 'No API key configured, so the built-in expert engine generated this plan.'
    });
  } catch (error) {
    return jsonResponse({ ok: false, error: error.message || 'Research plan generation failed.' }, error.status || 500);
  }
}
