import { INVALID_JOB_PATHS } from "../_data/invalid-job-paths.js";

function normalizedPath(url) {
  const pathname = new URL(url).pathname.replace(/\/{2,}/g, "/");
  return pathname.endsWith("/") ? pathname : `${pathname}/`;
}

export async function onRequest(context) {
  const path = normalizedPath(context.request.url);
  if (!INVALID_JOB_PATHS.has(path)) {
    return context.next();
  }

  const body = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,follow"><title>Job URL Removed</title></head><body><main style="max-width:720px;margin:60px auto;padding:24px;font-family:Arial,sans-serif"><h1>410 — Job URL Removed</h1><p>This URL was confirmed as invalid, duplicate or incorrectly generated. Expired legitimate job pages are retained in the archive instead.</p><p><a href="/jobs/">View active government jobs</a> · <a href="/jobs/faculty-jobs/">View active faculty jobs</a></p></main></body></html>`;
  return new Response(body, {
    status: 410,
    headers: {
      "content-type": "text/html; charset=UTF-8",
      "cache-control": "public, max-age=3600",
    },
  });
}
