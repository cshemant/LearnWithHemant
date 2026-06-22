const encoder = new TextEncoder();

export async function sha256Hex(value) {
  const digest = await crypto.subtle.digest('SHA-256', encoder.encode(String(value || '')));
  return [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, '0')).join('');
}

export async function hmacSha256Hex(message, secret) {
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const signature = await crypto.subtle.sign('HMAC', key, encoder.encode(message));
  return [...new Uint8Array(signature)].map(byte => byte.toString(16).padStart(2, '0')).join('');
}

async function hmacSha256Bytes(message, secret) {
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const signature = await crypto.subtle.sign('HMAC', key, encoder.encode(message));
  return new Uint8Array(signature);
}

function bytesToBase64Url(bytes) {
  let binary = '';
  bytes.forEach(byte => { binary += String.fromCharCode(byte); });
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

function base64UrlToBytes(value) {
  const base64 = String(value || '').replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(String(value || '').length / 4) * 4, '=');
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function base64UrlEncodeText(value) {
  return bytesToBase64Url(encoder.encode(value));
}

function base64UrlDecodeText(value) {
  return new TextDecoder().decode(base64UrlToBytes(value));
}

export async function signToken(payload, secret) {
  if (!secret) throw new Error('REPORT_TOKEN_SECRET is not configured.');
  const body = base64UrlEncodeText(JSON.stringify(payload));
  const sig = bytesToBase64Url(await hmacSha256Bytes(body, secret));
  return `${body}.${sig}`;
}

export async function verifyToken(token, secret) {
  if (!secret) throw new Error('REPORT_TOKEN_SECRET is not configured.');
  const [body, sig] = String(token || '').split('.');
  if (!body || !sig) throw new Error('Invalid unlock token.');
  const expected = bytesToBase64Url(await hmacSha256Bytes(body, secret));
  if (expected !== sig) throw new Error('Unlock token verification failed.');
  const payload = JSON.parse(base64UrlDecodeText(body));
  if (payload.exp && Date.now() > Number(payload.exp)) throw new Error('Unlock token expired. Please unlock the report again.');
  return payload;
}

export function getReportTokenSecret(env) {
  return env.REPORT_TOKEN_SECRET || env.RAZORPAY_KEY_SECRET || '';
}
