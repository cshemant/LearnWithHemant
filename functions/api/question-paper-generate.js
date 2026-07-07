import { jsonResponse, handleOptions, readJson } from '../_utils/http.js';

export async function onRequestOptions() {
  return handleOptions();
}

const QUESTION_PAPER_SCHEMA = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' },
    source: { type: 'string' },
    generatedAt: { type: 'string' },
    subject: { type: 'string' },
    semester: { type: 'string' },
    university: { type: 'string' },
    pattern: { type: 'string' },
    marks: { type: 'number' },
    duration: { type: 'string' },
    difficultyDistribution: { type: 'string' },
    noRepetitionNote: { type: 'string' },
    sectionInstructions: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          section: { type: 'string' },
          instruction: { type: 'string' }
        },
        required: ['section', 'instruction']
      }
    },
    questions: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          section: { type: 'string' },
          text: { type: 'string' },
          marks: { type: 'number' },
          unit: { type: 'string' },
          co: { type: 'string' },
          bloom: { type: 'string' },
          difficulty: { type: 'string' },
          answerScheme: { type: 'array', items: { type: 'string' } }
        },
        required: ['section', 'text', 'marks', 'unit', 'co', 'bloom', 'difficulty', 'answerScheme']
      }
    },
    bloomSummary: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          bloomLevel: { type: 'string' },
          purpose: { type: 'string' },
          marks: { type: 'string' }
        },
        required: ['bloomLevel', 'purpose', 'marks']
      }
    },
    coSummary: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          co: { type: 'string' },
          coverage: { type: 'string' }
        },
        required: ['co', 'coverage']
      }
    },
    unitWeightage: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          unit: { type: 'string' },
          marks: { type: 'number' },
          questionCount: { type: 'number' }
        },
        required: ['unit', 'marks', 'questionCount']
      }
    },
    moderationChecklist: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          checkPoint: { type: 'string' },
          status: { type: 'string' },
          remarks: { type: 'string' }
        },
        required: ['checkPoint', 'status', 'remarks']
      }
    }
  },
  required: [
    'ok', 'source', 'generatedAt', 'subject', 'semester', 'university', 'pattern',
    'marks', 'duration', 'difficultyDistribution', 'noRepetitionNote',
    'sectionInstructions', 'questions', 'bloomSummary', 'coSummary', 'unitWeightage',
    'moderationChecklist'
  ]
};

function cleanString(value, fallback, maxLength = 2000) {
  const text = String(value || '').trim();
  return (text || fallback).slice(0, maxLength);
}

function validatePayload(payload) {
  const marks = Number(payload.marks || 70);
  if (!Number.isFinite(marks) || marks < 30 || marks > 100) {
    throw new Error('Marks must be between 30 and 100.');
  }
  return {
    subject: cleanString(payload.subject, 'DBMS', 120),
    semester: cleanString(payload.semester, '5th', 40),
    university: cleanString(payload.university, 'AKTU', 40),
    pattern: cleanString(payload.pattern, 'AKTU 2026', 80),
    marks,
    duration: cleanString(payload.duration, '3 Hours', 40),
    difficulty: cleanString(payload.difficulty, 'Easy:Medium:Hard = 30:40:30', 120),
    unitTopics: cleanString(payload.unitTopics, 'Generate balanced unit-wise topics suitable for the subject.', 3500),
    previousQuestions: cleanString(payload.previousQuestions, '', 5000)
  };
}

function extractJson(text) {
  const raw = String(text || '').trim();
  if (!raw) throw new Error('Empty AI response.');
  try {
    return JSON.parse(raw);
  } catch (_) {
    const fenced = raw.match(/```(?:json)?\s*([\s\S]*?)```/i);
    if (fenced) return JSON.parse(fenced[1]);
    const match = raw.match(/\{[\s\S]*\}/);
    if (!match) throw new Error('AI response did not contain JSON.');
    return JSON.parse(match[0]);
  }
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

  return (data?.outputs || [])
    .map(output => {
      if (typeof output === 'string') return output;
      if (typeof output?.text === 'string') return output.text;
      if (Array.isArray(output?.content)) return output.content.map(part => part?.text || '').filter(Boolean).join('\n');
      return '';
    })
    .filter(Boolean)
    .join('\n')
    .trim();
}

function buildPrompt(input) {
  const priorBlock = input.previousQuestions
    ? `Previous 5-year questions to avoid direct repetition:\n${input.previousQuestions}`
    : 'No previous-year question bank was pasted. Avoid overused textbook-style wording and create fresh applied variations.';

  return `You are a senior Indian university exam paper setter and internal moderator.
Generate a NEW dynamic question paper. Do not reuse fixed or template questions.

Inputs:
Subject: ${input.subject}
Semester: ${input.semester}
University: ${input.university}
Pattern: ${input.pattern}
Total marks: ${input.marks}
Time: ${input.duration}
Difficulty distribution: ${input.difficulty}
Unit-wise topics / syllabus:
${input.unitTopics}

${priorBlock}

Strict output rules:
- Return valid JSON only, matching the schema.
- Total question marks must equal ${input.marks}.
- Use sections A, B and C.
- For a 70-mark paper, prefer: Section A = 10 questions × 2 marks, Section B = 5 questions × 6 marks, Section C = 2 questions × 10 marks.
- Map every question to a unit, CO1-CO5, Bloom level K1-K5 with label, difficulty, marks, and answerScheme points.
- Keep Easy:Medium:Hard close to the requested ratio.
- Include unitWeightage, bloomSummary, coSummary and moderationChecklist.
- Mention no-repetition status honestly. If no previous questions were supplied, say AI avoided generic/direct repeats but strict verification needs a previous-paper bank.
- Questions must be original, exam-ready and aligned with ${input.university}/${input.pattern} tone.`;
}

async function callGemini(prompt, env) {
  const apiKey = String(env.GEMINI_API_KEY || '').trim();
  if (!apiKey) {
    throw new Error('GEMINI_API_KEY is not configured. Add it in .dev.vars for local testing and Cloudflare Pages environment variables for production.');
  }

  const model = String(env.GEMINI_MODEL || 'gemini-3-flash-preview').trim() || 'gemini-3-flash-preview';
  const response = await fetch('https://generativelanguage.googleapis.com/v1beta/interactions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-goog-api-key': apiKey,
      'Api-Revision': '2026-05-20'
    },
    body: JSON.stringify({
      model,
      input: prompt,
      response_format: {
        type: 'text',
        mime_type: 'application/json',
        schema: QUESTION_PAPER_SCHEMA
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
    throw new Error(`Gemini returned no readable text. Response keys: ${shape}`);
  }
  return extractJson(outputText);
}

function normalizeGeneratedPaper(paper, input) {
  const questions = Array.isArray(paper.questions) ? paper.questions : [];
  if (questions.length < 5) throw new Error('AI returned too few questions. Please try again.');

  return {
    ok: true,
    source: 'gemini-api',
    generatedAt: new Date().toISOString(),
    subject: input.subject,
    semester: input.semester,
    university: input.university,
    pattern: input.pattern,
    marks: input.marks,
    duration: input.duration,
    difficultyDistribution: input.difficulty,
    noRepetitionNote: paper.noRepetitionNote || (input.previousQuestions
      ? 'AI was instructed to avoid direct repetition from the supplied previous five-year questions.'
      : 'No previous-paper bank was supplied, so AI avoided generic/direct repeats; strict verification needs old papers.'),
    sectionInstructions: Array.isArray(paper.sectionInstructions) ? paper.sectionInstructions.slice(0, 5) : [],
    questions: questions.slice(0, 30),
    bloomSummary: Array.isArray(paper.bloomSummary) ? paper.bloomSummary.slice(0, 8) : [],
    coSummary: Array.isArray(paper.coSummary) ? paper.coSummary.slice(0, 8) : [],
    unitWeightage: Array.isArray(paper.unitWeightage) ? paper.unitWeightage.slice(0, 10) : [],
    moderationChecklist: Array.isArray(paper.moderationChecklist) ? paper.moderationChecklist.slice(0, 10) : []
  };
}

export async function onRequestPost({ request, env }) {
  try {
    const payload = await readJson(request);
    const input = validatePayload(payload);
    const prompt = buildPrompt(input);
    const paper = await callGemini(prompt, env);
    return jsonResponse(normalizeGeneratedPaper(paper, input));
  } catch (error) {
    return jsonResponse({ ok: false, error: error.message || 'Question paper generation failed.' }, error.status || 500);
  }
}
