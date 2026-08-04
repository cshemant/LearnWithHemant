#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "jobs" / "invalid-job-urls.json"
TARGET = ROOT / "functions" / "_data" / "invalid-job-paths.js"


def normalize(path: str) -> str:
    path = "/" + str(path or "").strip().strip("/") + "/"
    while "//" in path:
        path = path.replace("//", "/")
    return path


def main() -> None:
    payload = json.loads(SOURCE.read_text(encoding="utf-8")) if SOURCE.exists() else {"paths": []}
    paths = sorted({normalize(p) for p in payload.get("paths", []) if str(p).strip()})
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    values = ", ".join(json.dumps(p) for p in paths)
    TARGET.write_text(
        "// Generated from jobs/invalid-job-urls.json. Do not add normal expired job URLs here.\n"
        f"export const INVALID_JOB_PATHS = new Set([{values}]);\n",
        encoding="utf-8",
    )
    print(f"[OK] Synced {len(paths)} confirmed invalid job URLs to Cloudflare 410 middleware")


if __name__ == "__main__":
    main()
