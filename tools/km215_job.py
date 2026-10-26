#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Experimental offline A4/600 dpi encoder recovered from ONG8 driver."""
import argparse
from pathlib import Path
import struct
import subprocess
import tempfile
import shutil
import re
import os
import resource
import selectors
import signal
import time

ROOT = Path(__file__).resolve().parents[1]
CODEC = ROOT / "build/km215-jbig"
UEL = b"\x1b%-12345X"
A4 = (4960, 7016)
MAX_SIZE = 64 * 1024 * 1024
MAX_JOB_SIZE = 64 * 1024 * 1024
MAX_PAGES = 200
JOB_SECONDS = 60
RASTER_BYTES = ((A4[0] + 7) // 8) * A4[1]


def child_limits():
    """Called only by this single-threaded filter's subprocess launcher."""
    for kind, value in ((resource.RLIMIT_AS, 512 * 1024 * 1024),
                        (resource.RLIMIT_CPU, 45),
                        (resource.RLIMIT_FSIZE, MAX_SIZE),
                        (resource.RLIMIT_NOFILE, 64),
                        (resource.RLIMIT_CORE, 0)):
        _, hard = resource.getrlimit(kind)
        limit = value if hard == resource.RLIM_INFINITY else min(value, hard)
        resource.setrlimit(kind, (limit, limit))


def stop_process(process):
    # Includes children that survive their direct parent; always reap the parent.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


class RasterReader:
    """Bounded pipe reads governed by a deadline even when the renderer stalls."""
    def __init__(self, stream, deadline):
        self.stream = stream
        self.deadline = deadline
        self.buffer = bytearray()
        self.selector = selectors.DefaultSelector()
        self.selector.register(stream, selectors.EVENT_READ)
        os.set_blocking(stream.fileno(), False)

    def more(self):
        left = self.deadline - time.monotonic()
        if left <= 0 or not self.selector.select(left):
            raise ValueError("document processing time limit exceeded")
        chunk = os.read(self.stream.fileno(), 65536)
        self.buffer.extend(chunk)
        return bool(chunk)

    def line(self, allow_eof=False):
        while True:
            end = self.buffer.find(b"\n")
            if end >= 0:
                if end > 1024:
                    raise ValueError("raster header too long")
                out = bytes(self.buffer[:end+1])
                del self.buffer[:end+1]
                return out
            if len(self.buffer) > 1024:
                raise ValueError("raster header too long")
            if not self.more():
                if allow_eof and not self.buffer:
                    return b""
                raise ValueError("truncated raster header")

    def page(self):
        magic = self.line(allow_eof=True)
        if not magic:
            return None
        if magic != b"P4\n":
            raise ValueError("invalid renderer output")
        header = bytearray(magic)
        while True:
            line = self.line()
            header.extend(line)
            if len(header) > 4096:
                raise ValueError("raster header too long")
            if not line.startswith(b"#"):
                break
        if line.split() != [str(x).encode() for x in A4]:
            raise ValueError("unexpected raster dimensions")
        while len(self.buffer) < RASTER_BYTES:
            if not self.more():
                raise ValueError("truncated page raster")
        raster = bytes(self.buffer[:RASTER_BYTES])
        del self.buffer[:RASTER_BYTES]
        return bytes(header) + raster


def pbm_read(data):
    """Read one P4 page, preserving whitespace-valued first raster bytes."""
    pos = 0
    tokens = []
    while len(tokens) < 3:
        while pos < len(data):
            if data[pos] in b" \t\r\n\v\f":
                pos += 1
            elif data[pos] == 35:
                end = data.find(b"\n", pos)
                if end < 0:
                    raise ValueError("unterminated PBM comment")
                pos = end + 1
            else:
                break
        start = pos
        while pos < len(data) and data[pos] not in b" \t\r\n\v\f#":
            pos += 1
        if pos == start:
            raise ValueError("truncated PBM header")
        tokens.append(data[start:pos])
    if tokens[0] != b"P4" or not tokens[1].isdigit() or not tokens[2].isdigit():
        raise ValueError("expected binary P4 PBM")
    w, h = map(int, tokens[1:])
    if not 0 < w <= 16384 or not 0 < h <= 16384:
        raise ValueError("invalid raster dimensions")
    if pos >= len(data) or data[pos] not in b" \t\r\n\v\f":
        raise ValueError("missing PBM raster separator")
    pos += 2 if data[pos:pos+2] == b"\r\n" else 1
    raw = data[pos:]
    if len(raw) != ((w + 7) // 8) * h:
        raise ValueError("expected exactly one complete PBM page")
    return w, h, raw


def line(key, value):
    return f"@PJL SET {key}={value}\r\n".encode("ascii")


def safe_username(value):
    value = re.sub(r"[^A-Za-z0-9_.-]", "_", value)[:32]
    return value if value.strip("_") else "linux"


def wrap(jbig, width, height, username="linux"):
    expected = struct.pack(">BBBBIIIBBBB", 0, 0, 1, 0, width, height, height, 0, 0, 3, 0x48)
    if not jbig.startswith(expected):
        raise ValueError("JBIG BIH differs from recovered Windows profile")
    job = bytearray(UEL + b"@PJL\r\n")
    # Simplex/no-cover/no-account-tracking path. Exact source addresses in docs.
    for key, value in (("DRIVERTYPE", "GDI"), ("COMPRESS", "JBIG"),
                       ("USERNAME", safe_username(username)), ("COVER", "OFF"), ("HOLD", "OFF"),
                       ("SECTION", "OFF"), ("MEDIATYPE", "PLAIN"),
                       ("MEDIASOURCE", "AUTO"), ("PAGESTATUS", "START"),
                       ("ORIENTATION", "PORTRAIT"), ("COPIES", "1"),
                       ("DUPLEX", "OFF"), ("RESOLUTION", "600"),
                       ("PAPERWIDTH", width), ("PAPERLENGTH", height), ("PAPER", "A4")):
        job.extend(line(key, value))
    for offset in range(0, len(jbig), 32768):
        chunk = jbig[offset:offset+32768]
        job.extend(line("IMAGELEN", len(chunk)))
        job.extend(chunk)
    job.extend(line("PAGESTATUS", "END") + b"@PJL EOJ\r\n" + UEL + b"\r\n")
    return bytes(job)


def extract(job):
    """Strictly parse our single-page profile, respecting binary lengths."""
    if not job.startswith(UEL + b"@PJL\r\n"):
        raise ValueError("invalid job prefix")
    pos = len(UEL + b"@PJL\r\n")
    blocks = []
    header = {}
    while pos < len(job):
        end = job.find(b"\r\n", pos)
        if end < 0:
            raise ValueError("truncated command")
        command = job[pos:end]
        pos = end + 2
        if command == b"@PJL SET PAGESTATUS=END":
            if job[pos:] != b"@PJL EOJ\r\n" + UEL + b"\r\n" or not blocks:
                raise ValueError("invalid job trailer")
            return header, b"".join(blocks)
        prefix = b"@PJL SET "
        if not command.startswith(prefix) or b"=" not in command:
            raise ValueError("invalid command")
        key, value = command[len(prefix):].split(b"=", 1)
        if key == b"IMAGELEN":
            if not value.isdigit() or not 0 < int(value) <= 32768:
                raise ValueError("invalid block length")
            size = int(value)
            if pos + size > len(job):
                raise ValueError("truncated binary block")
            blocks.append(job[pos:pos+size])
            pos += size
        else:
            if blocks or key in header:
                raise ValueError("unexpected or duplicate header")
            header[key] = value
    raise ValueError("missing job trailer")


def encode(pbm, username="linux", timeout=JOB_SECONDS):
    w, h, raw = pbm_read(pbm)
    if (w, h) != A4:
        raise ValueError(f"prototype requires A4 raster {A4[0]}x{A4[1]}")
    result = subprocess.run([str(CODEC), "encode", str(w), str(h)], input=raw,
                            capture_output=True, check=True, timeout=timeout,
                            preexec_fn=child_limits)
    return wrap(result.stdout, w, h, username)


def join_pages(jobs):
    """One document envelope; repeat recovered page commands for each page."""
    marker = line("MEDIATYPE", "PLAIN")
    trailer = b"@PJL EOJ\r\n" + UEL + b"\r\n"
    head = None
    for job in jobs:
        extract(job)
        prefix, sep, page = job.partition(marker)
        if not sep or not page.endswith(trailer):
            raise ValueError("unexpected page profile")
        if head is None:
            head = prefix
            yield head
        elif head != prefix:
            raise ValueError("document settings changed between pages")
        yield sep + page[:-len(trailer)]
    if head is None:
        raise ValueError("document has no pages")
    yield trailer


def extract_pages(data):
    """Return complete per-page jobs, respecting IMAGELEN binary boundaries."""
    marker = line("MEDIATYPE", "PLAIN")
    prefix, sep, _ = data.partition(marker)
    if not sep or not data.startswith(UEL + b"@PJL\r\n"):
        raise ValueError("invalid document header")
    trailer = b"@PJL EOJ\r\n" + UEL + b"\r\n"
    pos = start = len(prefix)
    pages = []
    while pos < len(data):
        if data[pos:] == trailer:
            if not pages or start != pos:
                raise ValueError("empty or unfinished document")
            return pages
        end = data.find(b"\r\n", pos)
        if end < 0:
            raise ValueError("truncated command")
        command = data[pos:end]
        pos = end+2
        if command.startswith(b"@PJL SET IMAGELEN="):
            value = command.split(b"=", 1)[1]
            if not value.isdigit() or not 0 < int(value) <= 32768:
                raise ValueError("invalid binary block length")
            pos += int(value)
            if pos > len(data):
                raise ValueError("truncated binary block")
        elif command == b"@PJL SET PAGESTATUS=END":
            page = prefix + data[start:pos] + trailer
            extract(page)
            pages.append(page)
            start = pos
    raise ValueError("missing document trailer")


def pdf_to_job(source, destination, username="linux"):
    """Stream bounded rasters; never emit a partial job after a late failure."""
    source = Path(source).resolve()
    if source.stat().st_size > MAX_SIZE:
        raise ValueError("PDF exceeds 64 MiB limit")
    with source.open("rb") as pdf:
        if not pdf.read(1024).lstrip().startswith(b"%PDF-"):
            raise ValueError("expected a PDF document")
    deadline = time.monotonic() + JOB_SECONDS
    with tempfile.TemporaryDirectory(prefix="km215-") as tmp:
        env = {"PATH": "/usr/bin:/bin", "LANG": "C", "HOME": tmp, "TMPDIR": tmp}
        process = subprocess.Popen(["/usr/bin/gs", "-q", "-dSAFER", "-dBATCH", "-dNOPAUSE",
                        "-sDEVICE=pbmraw", "-r600", "-g4960x7016", "-dFIXEDMEDIA",
                        "-dPDFFitPage", f"-dLastPage={MAX_PAGES + 1}", "-sOutputFile=%stdout",
                        "-f", str(source)], stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env,
                       start_new_session=True, preexec_fn=child_limits)
        reader = None
        count = 0
        try:
            reader = RasterReader(process.stdout, deadline)
            def pages():
                nonlocal count
                while True:
                    page = reader.page()
                    if page is None:
                        break
                    count += 1
                    if count > MAX_PAGES:
                        raise ValueError("document page limit exceeded")
                    left = deadline - time.monotonic()
                    if left <= 0:
                        raise ValueError("document processing time limit exceeded")
                    yield encode(page, username, timeout=left)
                left = deadline - time.monotonic()
                if left <= 0 or process.wait(timeout=left) != 0:
                    raise ValueError("PDF renderer failed or reached a resource limit")
            with tempfile.TemporaryFile() as job:
                for part in join_pages(pages()):
                    if job.tell() + len(part) > MAX_JOB_SIZE:
                        raise ValueError("encoded document exceeds 64 MiB limit")
                    job.write(part)
                job.seek(0)
                shutil.copyfileobj(job, destination)
            return count
        finally:
            stop_process(process)
            if reader is not None:
                reader.selector.close()
            process.stdout.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--pdf", action="store_true", help="rasterize all PDF pages (maximum 200)")
    args = parser.parse_args()
    try:
        if args.pdf:
            with tempfile.TemporaryFile() as temp:
                count = pdf_to_job(args.input, temp)
                temp.seek(0)
                with args.output.open("xb") as out:
                    shutil.copyfileobj(temp, out)
            print(f"Created local job: {count} page(s). Multi-page physical printing unverified.")
            return
        else:
            if args.input.stat().st_size > MAX_SIZE:
                raise ValueError("input too large")
            job = encode(args.input.read_bytes())
        extract(job)
        with args.output.open("xb") as out:
            out.write(job)
        print(f"Created experimental job: {len(job)} bytes. Physical printing unverified.")
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()
