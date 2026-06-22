import { jsonResponse, handleOptions, readJson } from '../_utils/http.js';
import { analyzeResume, validateResumeText } from '../_utils/resume-analyzer.js';
import { sha256Hex } from '../_utils/security.js';

export async function onRequestOptions() {
  return handleOptions();
}

export async function onRequestPost({ request }) {
  try {
    const payload = await readJson(request);
    const text = validateResumeText(payload.text || '');
    const report = analyzeResume(text, { includeAdvanced: false });
    const reportId = (await sha256Hex(text)).slice(0, 24);

    return jsonResponse({
      ok: true,
      ...report,
      reportId,
      protectedBy: 'cloudflare-pages-function'
    });
  } catch (error) {
    return jsonResponse({ ok: false, error: error.message || 'Resume scoring failed.' }, error.status || 500);
  }
}
