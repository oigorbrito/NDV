#!/usr/bin/env python3
"""Parse Codex exec --json JSONL usage without coercing missing telemetry to zero."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

USAGE_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)


def parse_lines(text: str) -> dict[str, Any]:
    totals = {field: 0 for field in USAGE_FIELDS}
    seen = 0
    thread_ids: list[str] = []
    failed_events: list[dict[str, Any]] = []
    error_events: list[dict[str, Any]] = []

    for lineno, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed JSONL at line {lineno}: {exc.msg}") from exc
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            raise ValueError(f"invalid Codex event at line {lineno}")
        etype = event["type"]
        if etype == "thread.started":
            tid = event.get("thread_id")
            if isinstance(tid, str) and tid:
                thread_ids.append(tid)
        elif etype == "turn.completed":
            usage = event.get("usage")
            if not isinstance(usage, dict):
                raise ValueError(f"turn.completed missing usage at line {lineno}")
            for field in USAGE_FIELDS:
                value = usage.get(field)
                if not isinstance(value, int) or isinstance(value, bool):
                    raise ValueError(f"turn.completed usage.{field} missing/non-integer at line {lineno}")
                if value < 0:
                    raise ValueError(f"turn.completed usage.{field} negative at line {lineno}")
                totals[field] += value
            seen += 1
        elif etype == "turn.failed":
            failed_events.append(event)
        elif etype == "error":
            error_events.append(event)

    authoritative = seen > 0
    result: dict[str, Any] = {
        "schema_id": "ndv-p1-wp07-codex-usage-v1",
        "status": "AUTHORITATIVE" if authoritative else "MISSING",
        "turn_completed_count": seen,
        "thread_ids": thread_ids,
        "turn_failed_count": len(failed_events),
        "error_event_count": len(error_events),
        "usage": totals if authoritative else {field: None for field in USAGE_FIELDS},
        "total_system_tokens_component": (
            totals["input_tokens"] + totals["output_tokens"]
            if authoritative else None
        ),
        "cached_input_tokens_recorded_separately": totals["cached_input_tokens"] if authoritative else None,
        "cache_write_input_tokens_recorded_separately": totals["cache_write_input_tokens"] if authoritative else None,
        "reasoning_output_tokens_recorded_separately": totals["reasoning_output_tokens"] if authoritative else None,
        "missing_telemetry_is_zero": False,
        "treatment_execution_inferred": False,
        "holdout_access": "NONE",
    }
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("jsonl", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    try:
        result = parse_lines(args.jsonl.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(json.dumps({"status":"FAIL","reason":"ACCOUNTING_INTEGRITY_FAILURE","detail":str(exc)}, indent=2))
        return 2
    if args.out:
        if args.out.exists():
            raise SystemExit(f"refusing overwrite: {args.out}")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
