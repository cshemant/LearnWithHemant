export function jsonResponse(data, status = 200) {
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store'
  };

  if (data === null) {
    return new Response(null, { status, headers });
  }

  return new Response(JSON.stringify(data), { status, headers });
}

export function handleOptions() {
  return jsonResponse(null, 204);
}

export async function readJson(request) {
  const contentType = request.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    throw new Error('Request must be JSON.');
  }
  return request.json();
}
