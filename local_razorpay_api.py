"""
Local Razorpay API server for Learn With Hemant

Use this only for local testing when npx/wrangler is not available.

It runs these endpoints on http://localhost:8787:
- POST /api/razorpay/order
- POST /api/razorpay/verify
- POST /api/question-paper-generate

Before running, create .dev.vars in the same folder as this file:

RAZORPAY_KEY_ID=rzp_live_xxxxx
RAZORPAY_KEY_SECRET=your_secret_key
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3-flash-preview

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
import re
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


def clean_string(value: Any, fallback: str, max_length: int = 2000) -> str:
    text = str(value or "").strip()
    return (text or fallback)[:max_length]


def validate_question_paper_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    marks = int(float(payload.get("marks") or 70))
    if marks < 30 or marks > 100:
        raise RuntimeError("Marks must be between 30 and 100.")

    return {
        "subject": clean_string(payload.get("subject"), "DBMS", 120),
        "semester": clean_string(payload.get("semester"), "5th", 40),
        "university": clean_string(payload.get("university"), "AKTU", 40),
        "pattern": clean_string(payload.get("pattern"), "AKTU 2026", 80),
        "marks": marks,
        "duration": clean_string(payload.get("duration"), "3 Hours", 40),
        "difficulty": clean_string(payload.get("difficulty"), "Easy:Medium:Hard = 30:40:30", 120),
        "unitTopics": clean_string(payload.get("unitTopics"), "Generate balanced unit-wise topics suitable for the subject.", 3500),
        "previousQuestions": clean_string(payload.get("previousQuestions"), "", 5000),
    }


def build_question_paper_prompt(input_data: Dict[str, Any]) -> str:
    if input_data["previousQuestions"]:
        prior_block = "Previous 5-year questions to avoid direct repetition:\n" + input_data["previousQuestions"]
    else:
        prior_block = "No previous-year question bank was pasted. Avoid overused textbook-style wording and create fresh applied variations."

    return f"""You are a senior Indian university exam paper setter and internal moderator.
Generate a NEW dynamic question paper. Do not reuse fixed or template questions.

Inputs:
Subject: {input_data['subject']}
Semester: {input_data['semester']}
University: {input_data['university']}
Pattern: {input_data['pattern']}
Total marks: {input_data['marks']}
Time: {input_data['duration']}
Difficulty distribution: {input_data['difficulty']}
Unit-wise topics / syllabus:
{input_data['unitTopics']}

{prior_block}

Strict output rules:
- Return valid JSON only.
- Use this JSON shape exactly: {{"ok": true, "subject": string, "semester": string, "university": string, "pattern": string, "marks": number, "duration": string, "difficultyDistribution": string, "noRepetitionNote": string, "sectionInstructions": [{{"section": string, "instruction": string}}], "questions": [{{"section": string, "text": string, "marks": number, "unit": string, "co": string, "bloom": string, "difficulty": string, "answerScheme": [string]}}], "bloomSummary": [{{"bloomLevel": string, "purpose": string, "marks": string}}], "coSummary": [{{"co": string, "coverage": string}}], "unitWeightage": [{{"unit": string, "marks": number, "questionCount": number}}], "moderationChecklist": [{{"checkPoint": string, "status": string, "remarks": string}}]}}
- Total question marks must equal {input_data['marks']}.
- Use sections A, B and C.
- For a 70-mark paper, prefer: Section A = 10 questions × 2 marks, Section B = 5 questions × 6 marks, Section C = 2 questions × 10 marks.
- Map every question to a unit, CO1-CO5, Bloom level K1-K5 with label, difficulty, marks, and answerScheme points.
- Keep Easy:Medium:Hard close to the requested ratio.
- Include unitWeightage, bloomSummary, coSummary and moderationChecklist.
- Mention no-repetition status honestly. If no previous questions were supplied, say AI avoided generic/direct repeats but strict verification needs a previous-paper bank.
- Questions must be original, exam-ready and aligned with {input_data['university']}/{input_data['pattern']} tone."""


def extract_json_object(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise RuntimeError("Empty Gemini response.")
    try:
        return json.loads(raw)
    except Exception:
        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, re.I)
        if fenced:
            return json.loads(fenced.group(1))
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            raise RuntimeError("Gemini response did not contain JSON.")
        return json.loads(match.group(0))


def read_gemini_text(data: Dict[str, Any]) -> str:
    for key in ("output_text", "outputText", "text"):
        if str(data.get(key, "")).strip():
            return str(data[key]).strip()

    response = data.get("response") if isinstance(data.get("response"), dict) else {}
    for key in ("output_text", "outputText", "text"):
        if str(response.get(key, "")).strip():
            return str(response[key]).strip()

    parts = []
    for step in data.get("steps", []) or []:
        if isinstance(step, dict) and step.get("type") not in (None, "model_output"):
            continue
        for item in (step.get("content") or step.get("outputs") or []) if isinstance(step, dict) else []:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
    if "".join(parts).strip():
        return "\n".join([p for p in parts if p]).strip()

    for output in data.get("outputs", []) or []:
        if isinstance(output, str):
            parts.append(output)
        elif isinstance(output, dict):
            if isinstance(output.get("text"), str):
                parts.append(output["text"])
            elif isinstance(output.get("content"), list):
                parts.extend(str(part.get("text") or "") for part in output["content"] if isinstance(part, dict))
    return "\n".join([p for p in parts if p]).strip()


def normalize_question_paper(paper: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    questions = paper.get("questions") if isinstance(paper.get("questions"), list) else []
    if len(questions) < 5:
        raise RuntimeError("Gemini returned too few questions. Please try again.")

    return {
        "ok": True,
        "source": "gemini-api-local",
        "generatedAt": __import__("datetime").datetime.now().isoformat(),
        "subject": input_data["subject"],
        "semester": input_data["semester"],
        "university": input_data["university"],
        "pattern": input_data["pattern"],
        "marks": input_data["marks"],
        "duration": input_data["duration"],
        "difficultyDistribution": input_data["difficulty"],
        "noRepetitionNote": paper.get("noRepetitionNote") or ("AI was instructed to avoid direct repetition from supplied previous-year questions." if input_data["previousQuestions"] else "No previous-paper bank was supplied, so AI avoided generic/direct repeats; strict verification needs old papers."),
        "sectionInstructions": (paper.get("sectionInstructions") or [])[:5],
        "questions": questions[:30],
        "bloomSummary": (paper.get("bloomSummary") or [])[:8],
        "coSummary": (paper.get("coSummary") or [])[:8],
        "unitWeightage": (paper.get("unitWeightage") or [])[:10],
        "moderationChecklist": (paper.get("moderationChecklist") or [])[:10],
    }


def call_gemini_question_paper(input_data: Dict[str, Any]) -> Dict[str, Any]:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing. Add it to .dev.vars in this same folder, then restart python local_razorpay_api.py")

    model = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview").strip() or "gemini-3-flash-preview"
    body = {
        "model": model,
        "input": build_question_paper_prompt(input_data),
        "response_format": {"type": "text", "mime_type": "application/json"},
    }
    req = Request(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
            "Api-Revision": "2026-05-20",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=120) as res:
            data = json.loads(res.read().decode("utf-8"))
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini API error {e.code}: {detail[:260]}")

    output_text = read_gemini_text(data)
    paper = extract_json_object(output_text)
    return normalize_question_paper(paper, input_data)


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

            if self.path == "/api/question-paper-generate":
                return self.generate_question_paper()

            return self.send_json({"ok": False, "error": "Not found"}, 404)

        except Exception as e:
            return self.send_json({"ok": False, "error": str(e)}, 500)

    def generate_question_paper(self) -> None:
        payload = self.read_json()
        input_data = validate_question_paper_payload(payload)
        result = call_gemini_question_paper(input_data)
        return self.send_json(result)

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
    print(f"Local API running on http://localhost:{PORT}")
    print("Available: /api/razorpay/order, /api/razorpay/verify, /api/question-paper-generate")
    print("Keep this terminal open while testing http://localhost:8000/")
    HTTPServer(("localhost", PORT), Handler).serve_forever()
