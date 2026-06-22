/**
 * Razorpay API Worker update for Learn With Hemant
 *
 * Deploy this code to your existing Razorpay API Worker, not to the static website Worker.
 *
 * Your working payment-test page succeeds because it sends amount: 1.
 * The Apply form fails because it sends amount: 99 / 199 / 499 and the old Worker rejects them.
 *
 * Routes:
 * POST /api/razorpay/order
 * POST /api/razorpay/verify
 *
 * Required Worker secrets:
 * RAZORPAY_KEY_ID
 * RAZORPAY_KEY_SECRET
 * REPORT_TOKEN_SECRET (optional but recommended; fallback is RAZORPAY_KEY_SECRET)
 */

const ALLOWED_AMOUNTS = new Set([
  1,      // test payment
  99,     // WordPress registration
  199,    // basic / web development registration
  499,    // Magento / live project / deployment / payment gateway
  4999,   // existing course amount
  6999,   // existing course amount
  7999,   // existing course amount
  19999   // existing live project amount
]);

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === 'OPTIONS') {
      return jsonResponse(null, 204);
    }

    if (request.method === 'POST' && url.pathname === '/api/razorpay/order') {
      return createOrder(request, env);
    }

    if (request.method === 'POST' && url.pathname === '/api/razorpay/verify') {
      return verifyAndCapture(request, env);
    }

    return jsonResponse({ ok: false, error: 'Not found' }, 404);
  }
};

async function createOrder(request, env) {
  try {
    const payload = await request.json();
    const amount = Number(payload.amount);

    if (!isAllowedAmount(amount)) {
      return jsonResponse({
        ok: false,
        error: `Invalid amount. ₹${amount} is not enabled for Learn With Hemant payments.`
      }, 400);
    }

    requireRazorpaySecrets(env);

    const orderPayload = {
      amount: amount * 100,
      currency: 'INR',
      receipt: 'lwh_' + Date.now(),
      payment_capture: 1,
      notes: {
        course: String(payload.course || ''),
        plan: String(payload.plan || ''),
        name: String(payload.name || ''),
        phone: String(payload.phone || ''),
        email: String(payload.email || ''),
        score: String(payload.score || ''),
        reportId: String(payload.reportId || ''),
        source: String(payload.source || ''),
        website: 'learnwithhemant.com'
      }
    };

    const response = await razorpayFetch(env, 'https://api.razorpay.com/v1/orders', {
      method: 'POST',
      body: JSON.stringify(orderPayload)
    });

    const data = await response.json();

    if (!response.ok) {
      return jsonResponse({
        ok: false,
        error: data.error?.description || 'Could not create Razorpay order.'
      }, 400);
    }

    return jsonResponse({
      ok: true,
      order_id: data.id,
      amount: data.amount,
      currency: data.currency || 'INR',
      receipt: data.receipt
    });
  } catch (error) {
    return jsonResponse({ ok: false, error: error.message || 'Order creation failed.' }, 500);
  }
}

async function verifyAndCapture(request, env) {
  try {
    const payload = await request.json();
    const amount = Number(payload.amount);

    if (!isAllowedAmount(amount)) {
      return jsonResponse({
        ok: false,
        error: `Invalid amount. ₹${amount} is not enabled for Learn With Hemant payments.`
      }, 400);
    }

    requireRazorpaySecrets(env);

    const orderId = String(payload.razorpay_order_id || '');
    const paymentId = String(payload.razorpay_payment_id || '');
    const signature = String(payload.razorpay_signature || '');

    if (!orderId || !paymentId || !signature) {
      return jsonResponse({ ok: false, error: 'Missing Razorpay verification details.' }, 400);
    }

    const expectedSignature = await hmacSha256(orderId + '|' + paymentId, env.RAZORPAY_KEY_SECRET);

    if (expectedSignature !== signature) {
      return jsonResponse({ ok: false, error: 'Payment signature verification failed.' }, 400);
    }

    const statusResponse = await razorpayFetch(env, `https://api.razorpay.com/v1/payments/${paymentId}`, {
      method: 'GET'
    });

    let payment = await statusResponse.json();

    if (!statusResponse.ok) {
      return jsonResponse({
        ok: false,
        error: payment.error?.description || 'Could not fetch payment status.'
      }, 400);
    }

    if (payment.status === 'authorized') {
      const captureResponse = await razorpayFetch(env, `https://api.razorpay.com/v1/payments/${paymentId}/capture`, {
        method: 'POST',
        body: JSON.stringify({
          amount: amount * 100,
          currency: 'INR'
        })
      });

      payment = await captureResponse.json();

      if (!captureResponse.ok) {
        return jsonResponse({
          ok: false,
          error: payment.error?.description || 'Payment verification passed, but capture failed.'
        }, 400);
      }
    }

    let unlockToken = '';
    if (amount === 99 && payload.reportId) {
      unlockToken = await signToken({
        type: 'advanced-resume-report',
        amount: 99,
        reportId: String(payload.reportId),
        paymentId,
        exp: Date.now() + 24 * 60 * 60 * 1000
      }, env.REPORT_TOKEN_SECRET || env.RAZORPAY_KEY_SECRET);
    }

    return jsonResponse({
      ok: true,
      razorpay_order_id: orderId,
      razorpay_payment_id: paymentId,
      payment_status: payment.status || 'captured',
      capture_status: payment.status || 'captured',
      unlock_token: unlockToken
    });
  } catch (error) {
    return jsonResponse({ ok: false, error: error.message || 'Payment verification failed.' }, 500);
  }
}

function isAllowedAmount(amount) {
  return Number.isFinite(amount) && amount > 0 && ALLOWED_AMOUNTS.has(amount);
}

function requireRazorpaySecrets(env) {
  if (!env.RAZORPAY_KEY_ID || !env.RAZORPAY_KEY_SECRET) {
    throw new Error('Razorpay Worker secrets are not configured.');
  }
}

async function razorpayFetch(env, url, options) {
  const auth = btoa(env.RAZORPAY_KEY_ID + ':' + env.RAZORPAY_KEY_SECRET);

  return fetch(url, {
    ...options,
    headers: {
      'Authorization': 'Basic ' + auth,
      'Content-Type': 'application/json',
      ...(options && options.headers ? options.headers : {})
    }
  });
}

async function hmacSha256(message, secret) {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );

  const signature = await crypto.subtle.sign('HMAC', key, encoder.encode(message));
  return [...new Uint8Array(signature)]
    .map(byte => byte.toString(16).padStart(2, '0'))
    .join('');
}

async function signToken(payload, secret) {
  const body = base64UrlEncode(JSON.stringify(payload));
  const sigBytes = await hmacSha256Bytes(body, secret);
  const sig = bytesToBase64Url(sigBytes);
  return `${body}.${sig}`;
}

async function hmacSha256Bytes(message, secret) {
  const encoder = new TextEncoder();
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

function base64UrlEncode(value) {
  return bytesToBase64Url(new TextEncoder().encode(value));
}

function bytesToBase64Url(bytes) {
  let binary = '';
  bytes.forEach(byte => { binary += String.fromCharCode(byte); });
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

function jsonResponse(data, status = 200) {
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json'
  };

  if (data === null) {
    return new Response(null, { status, headers });
  }

  return new Response(JSON.stringify(data), { status, headers });
}
