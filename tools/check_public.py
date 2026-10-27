#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Scan public release sources without echoing any matched private values."""
import ipaddress
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = [ipaddress.ip_network(x) for x in
            ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]


def findings(data):
    text = data.decode("utf-8", errors="replace")
    problems = set()
    if re.search(r"/(?:home|Users)/[A-Za-z0-9_.-]+/", text):
        problems.add("personal filesystem path")
    for candidate in re.findall(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])", text):
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if address.is_private and not address.is_loopback and not any(address in net for net in EXAMPLES):
            problems.add("non-example private address")
    if re.search(r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![0-9a-f])", text):
        problems.add("hardware address requires manual review")
    for email in re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text):
        domain = email.rsplit("@", 1)[1].lower()
        if domain not in {"gnu.org", "fsf.org", "github.com", "users.noreply.github.com", "example.invalid"}:
            problems.add("email requires manual review")
    if re.search(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----)", text):
        problems.add("credential-like value")
    for term in os.environ.get("KM215_PRIVATE_TERMS", "").splitlines():
        if term.strip() and term.casefold() in text.casefold():
            problems.add("private denylist match")
    return sorted(problems)


def scan(paths):
    failures = []
    for path in paths:
        for reason in findings(path.read_bytes()):
            failures.append((str(path.relative_to(ROOT)), reason))
    if failures:
        for path, reason in failures:
            print(f"FAIL {path}: {reason}")
        raise ValueError("public source privacy scan failed")
    print(f"Privacy scan passed: {len(paths)} public files; manual metadata review still required")


if __name__ == "__main__":
    from build_release import sources
    scan(sources())
