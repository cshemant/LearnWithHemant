"""
Local Razorpay API server for Learn With Hemant

Use this only for local testing when npx/wrangler is not available.

It runs these endpoints on http://localhost:8787:
- POST /api/razorpay/order
- POST /api/razorpay/verify

Before running, create .dev.vars in the same folder as this file:

RAZORPAY_KEY_ID=rzp_live_xxxxx
RAZORPAY_KEY_SECRET=your_secret_key

Then run:
python local_razorpay_api.py

In another terminal, run the website:
python -m http.server 8000

Then open:
http://localhost:8000/apply/
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Dict, Any


ALLOWED_AMOUNTS = {1, 99, 199, 499, 4999, 6999, 7999, 19999}
PORT = 8787


def load_dev_vars() -> None:
    env_file = Path(".dev.vars")
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is missing. Add it to .dev.vars")
    return value


def razorpay_request(method: str, path: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    key_id = get_required_env("RAZORPAY_KEY_ID")
    key_secret = get_required_env("RAZORPAY_KEY_SECRET")
    auth = base64.b64encode(f"{key_id}:{key_secret}".encode("utf-8")).decode("ascii")

    body = None
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
    }

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    req = Request(
        "https://api.razorpay.com/v1" + path,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(req, timeout=30) as res:
            return json.loads(res.read().decode("utf-8"))
    except HTTPError as e:
        try:
            data = json.loads(e.read().decode("utf-8"))
            description = data.get("error", {}).get("description") or str(data)
        except Exception:
            description = e.reason
        raise RuntimeError(description)


class Handler(BaseHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return json.loads(raw or "{}")

    def send_json(self, data: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        try:
            if self.path == "/api/razorpay/order":
                return self.create_order()

            if self.path == "/api/razorpay/verify":
                return self.verify_and_capture()

            return self.send_json({"ok": False, "error": "Not found"}, 404)

        except Exception as e:
            return self.send_json({"ok": False, "error": str(e)}, 500)

    def create_order(self) -> None:
        payload = self.read_json()
        amount = int(float(payload.get("amount", 0)))

        if amount not in ALLOWED_AMOUNTS:
            return self.send_json(
                {"ok": False, "error": f"Invalid amount. ₹{amount} is not enabled locally."},
                400,
            )

        order_payload = {
            "amount": amount * 100,
            "currency": "INR",
            "receipt": "lwh_local_" + str(int(__import__("time").time())),
            "payment_capture": 1,
            "notes": {
                "course": str(payload.get("course", "")),
                "plan": str(payload.get("plan", "")),
                "name": str(payload.get("name", "")),
                "phone": str(payload.get("phone", "")),
                "email": str(payload.get("email", "")),
                "website": "learnwithhemant.com",
                "environment": "local-test",
            },
        }

        order = razorpay_request("POST", "/orders", order_payload)

        return self.send_json({
            "ok": True,
            "order_id": order.get("id"),
            "amount": order.get("amount"),
            "currency": order.get("currency", "INR"),
            "receipt": order.get("receipt"),
        })

    def verify_and_capture(self) -> None:
        payload = self.read_json()
        amount = int(float(payload.get("amount", 0)))

        if amount not in ALLOWED_AMOUNTS:
            return self.send_json(
                {"ok": False, "error": f"Invalid amount. ₹{amount} is not enabled locally."},
                400,
            )

        order_id = str(payload.get("razorpay_order_id", ""))
        payment_id = str(payload.get("razorpay_payment_id", ""))
        signature = str(payload.get("razorpay_signature", ""))

        if not order_id or not payment_id or not signature:
            return self.send_json({"ok": False, "error": "Missing Razorpay verification details."}, 400)

        key_secret = get_required_env("RAZORPAY_KEY_SECRET")
        expected = hmac.new(
            key_secret.encode("utf-8"),
            f"{order_id}|{payment_id}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            return self.send_json({"ok": False, "error": "Payment signature verification failed."}, 400)

        payment = razorpay_request("GET", f"/payments/{payment_id}")

        if payment.get("status") == "authorized":
            payment = razorpay_request(
                "POST",
                f"/payments/{payment_id}/capture",
                {"amount": amount * 100, "currency": "INR"},
            )

        return self.send_json({
            "ok": True,
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "payment_status": payment.get("status", "captured"),
            "capture_status": payment.get("status", "captured"),
        })


if __name__ == "__main__":
    load_dev_vars()
    print(f"Local Razorpay API running on http://localhost:{PORT}")
    print("Keep this terminal open while testing http://localhost:8000/apply/")
    HTTPServer(("localhost", PORT), Handler).serve_forever()
