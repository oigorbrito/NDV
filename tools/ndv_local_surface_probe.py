#!/usr/bin/env python3
"""Probe local execution surface without downloading models or using credentials.

The probe is intentionally read-only. It inventories machine/runtime facts needed
for NDV free/local executor screening and writes a JSON report.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def run(argv: list[str], timeout: float = 5.0) -> dict[str, Any]:
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=timeout)
        return {
            "available": True,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except FileNotFoundError:
        return {"available": False, "returncode": None, "stdout": "", "stderr": "not found"}
    except subprocess.TimeoutExpired:
        return {"available": True, "returncode": 124, "stdout": "", "stderr": "timeout"}


def get_total_memory_bytes() -> int | None:
    if sys.platform.startswith("linux"):
        try:
            text = Path("/proc/meminfo").read_text(encoding="utf-8")
            for line in text.splitlines():
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) * 1024
        except Exception:
            return None
    if sys.platform == "darwin":
        r = run(["sysctl", "-n", "hw.memsize"])
        if r["returncode"] == 0 and r["stdout"].isdigit():
            return int(r["stdout"])
    if os.name == "nt":
        r = run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"])
        try:
            return int(r["stdout"].strip()) if r["returncode"] == 0 else None
        except ValueError:
            return None
    return None


def probe_nvidia() -> dict[str, Any]:
    if not shutil.which("nvidia-smi"):
        return {"available": False, "gpus": []}
    r = run([
        "nvidia-smi",
        "--query-gpu=name,memory.total,driver_version",
        "--format=csv,noheader,nounits",
    ])
    gpus = []
    if r["returncode"] == 0:
        for line in r["stdout"].splitlines():
            parts = [x.strip() for x in line.split(",")]
            if len(parts) >= 3:
                gpus.append({"name": parts[0], "memory_total_mib": parts[1], "driver_version": parts[2]})
    return {"available": True, "gpus": gpus, "probe": r}


def http_json(url: str, timeout: float = 2.0) -> tuple[bool, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return True, json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return False, {"error": type(exc).__name__, "message": str(exc)}


def probe_ollama() -> dict[str, Any]:
    cli = run(["ollama", "--version"])
    ok, tags = http_json("http://127.0.0.1:11434/api/tags")
    models = []
    if ok and isinstance(tags, dict):
        for item in tags.get("models", []):
            if isinstance(item, dict):
                details = item.get("details") if isinstance(item.get("details"), dict) else {}
                models.append({
                    "name": item.get("name") or item.get("model"),
                    "digest": item.get("digest"),
                    "size_bytes": item.get("size"),
                    "modified_at": item.get("modified_at"),
                    "parameter_size": details.get("parameter_size"),
                    "quantization_level": details.get("quantization_level"),
                    "family": details.get("family"),
                })
    return {
        "cli": cli,
        "api_reachable": ok,
        "api_detail": None if ok else tags,
        "models": models,
    }


def classify(report: dict[str, Any]) -> dict[str, Any]:
    ollama = report["ollama"]
    if not ollama["cli"]["available"]:
        return {"status": "S0_ENVIRONMENT_BLOCKED", "reason": "ollama CLI not installed"}
    if not ollama["api_reachable"]:
        return {"status": "S0_ENVIRONMENT_BLOCKED", "reason": "ollama runtime API not reachable"}
    if not ollama["models"]:
        return {"status": "S0_DOWNLOAD_REQUIRED", "reason": "runtime available but no installed model discovered"}
    return {
        "status": "S0_LOCAL_SURFACE_DISCOVERED",
        "reason": "one or more installed models discovered; each model still requires executor-level qualification",
        "installed_model_count": len(ollama["models"]),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    report: dict[str, Any] = {
        "schema_id": "ndv-local-surface-probe-v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "downloads_performed": False,
        "credentials_used": False,
        "machine": {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python": sys.version,
            "logical_cpu_count": os.cpu_count(),
            "total_memory_bytes": get_total_memory_bytes(),
        },
        "nvidia": probe_nvidia(),
        "ollama": probe_ollama(),
    }
    report["classification"] = classify(report)

    encoded = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
