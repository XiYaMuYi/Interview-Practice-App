#!/usr/bin/env python
"""CLI health check — calls /health/ready and prints readable results.

Usage:
    python scripts/health_check.py              # readable summary
    python scripts/health_check.py --json       # raw JSON output
    python scripts/health_check.py --quiet      # only output if unhealthy
"""

import argparse
import json
import sys
import urllib.request
import urllib.error


BASE_URL = "http://localhost:8000"
ENDPOINT = "/health/ready"


def fetch_health(timeout: float = 5.0) -> dict:
    url = f"{BASE_URL}{ENDPOINT}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def format_readable(data: dict) -> str:
    lines = []
    status = data.get("status", "unknown")
    lines.append(f"Overall: {status.upper()}")
    lines.append("")

    checks = data.get("checks", {})
    for name, detail in checks.items():
        icon = "OK" if detail.get("status") == "ok" else "FAIL"
        ms = detail.get("duration_ms", "?")
        desc = detail.get("detail", "")
        lines.append(f"  [{icon}] {name}: {desc} ({ms}ms)")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Health check for Interview Practice App")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--quiet", action="store_true", help="Only output if unhealthy")
    args = parser.parse_args()

    data = fetch_health()

    if args.json:
        print(json.dumps(data, indent=2))
        sys.exit(0 if data.get("status") == "ready" else 1)

    output = format_readable(data)

    if args.quiet:
        if data.get("status") == "ready":
            sys.exit(0)
        print(output)
        sys.exit(1)

    print(output)
    sys.exit(0 if data.get("status") == "ready" else 1)


if __name__ == "__main__":
    main()
