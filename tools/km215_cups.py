#!/usr/bin/python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""CUPS PDF filter: A4, 600 dpi, simplex, one copy; stdout is print data."""
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile

from km215_job import MAX_SIZE, pdf_to_job


def options_check(copies, options):
    if copies != "1":
        raise ValueError("only one copy per job is currently supported")
    opts = dict(item.split("=", 1) if "=" in item else (item, "true")
                for item in shlex.split(options))
    for key, allowed in {
        "sides": {"one-sided"}, "Duplex": {"None", "False", "Off"},
        "PageSize": {"A4"}, "PageRegion": {"A4"},
        "Resolution": {"600dpi"}, "number-up": {"1"},
        "printer-resolution": {"600dpi", "600x600dpi"},
        "orientation-requested": {"3"},
        "print-scaling": {"auto", "auto-fit", "fit"},
    }.items():
        if key in opts and opts[key] not in allowed:
            raise ValueError(f"unsupported setting: {key}={opts[key]}")
    if "media" in opts and opts["media"] not in {"A4", "iso_a4_210x297mm"}:
        raise ValueError("only A4 media is supported")
    for key in ("page-ranges", "page-set", "outputorder", "mirror"):
        if key in opts:
            raise ValueError(f"{key} is not supported by this filter yet")


def cancelled(*_):
    raise InterruptedError("job cancelled")


def main():
    signal.signal(signal.SIGTERM, cancelled)
    if len(sys.argv) not in (6, 7):
        raise ValueError("expected CUPS job-id user title copies options [PDF-file]")
    options_check(sys.argv[4], sys.argv[5])
    with tempfile.TemporaryDirectory(prefix="km215-cups-") as tmp:
        if len(sys.argv) == 7:
            source = Path(sys.argv[6])
        else:
            source = Path(tmp) / "input.pdf"
            with source.open("xb") as out:
                total = 0
                while chunk := sys.stdin.buffer.read(65536):
                    total += len(chunk)
                    if total > MAX_SIZE:
                        raise ValueError("PDF exceeds 64 MiB limit")
                    out.write(chunk)
        # No bytes reach a backend until all rendering/encoding succeeded.
        with tempfile.TemporaryFile() as job:
            # Printer framing needs a nonempty value, not the submitting identity.
            count = pdf_to_job(source, job)
            job.seek(0)
            shutil.copyfileobj(job, sys.stdout.buffer)
        print(f"INFO: Encoded {count} page(s); physical printing requires confirmation", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"ERROR: bizhub215: {error}", file=sys.stderr)
        sys.exit(1)
