import { jsonResponse, handleOptions, readJson } from '../_utils/http.js';
import { analyzeResume, validateResumeText } from '../_utils/resume-analyzer.js';
import { getReportTokenSecret, sha256Hex, verifyToken } from '../_utils/security.js';

export async function onRequestOptions() {
  return handleOptions();
}

export async function onRequestPost({ request, env }) {
  try {
    const payload = await readJson(request);
    const text = validateResumeText(payload.text || '');
    const reportId = (await sha256Hex(text)).slice(0, 24);
    const tokenPayload = await verifyToken(payload.unlockToken, getReportTokenSecret(env));

    if (tokenPayload.type !== 'advanced-resume-report' || Number(tokenPayload.amount) !== 99) {
      return jsonResponse({ ok: false, error: 'This payment token is not valid for Advanced Resume Report.' }, 403);
    }

    if (tokenPayload.reportId && tokenPayload.reportId !== reportId) {
      return jsonResponse({ ok: false, error: 'This unlock token belongs to a different resume scan. Please scan and unlock again.' }, 403);
    }

    const report = analyzeResume(text, { includeAdvanced: true });

    return jsonResponse({
      ok: true,
      advancedUnlocked: true,
      reportId,
      advancedSections: report.advancedSections
    });
  } catch (error) {
    return jsonResponse({ ok: false, error: error.message || 'Advanced report generation failed.' }, error.status || 500);
  }
}
