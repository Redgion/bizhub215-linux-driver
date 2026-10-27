#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Private user profile for the experimental native bizhub 215 SANE backend."""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def address(value):
    # The legacy SANE backend's net: parser supports IPv4, not IPv6 literals.
    return str(ipaddress.IPv4Address(value))


def receive(stream, size):
    out = bytearray()
    while len(out) < size:
        part = stream.recv(size - len(out))
        if not part:
            raise ValueError("scanner disconnected before completing its reply")
        out.extend(part)
    return bytes(out)


def probe(host, port=4567):
    """Only greeting + error-status query, never a start/settings command."""
    host = address(host)
    with socket.create_connection((host, port), timeout=5) as stream:
        stream.settimeout(5)
        greeting = receive(stream, 3)
        if greeting == b"\x04\x00\x01":
            raise ValueError("scanner is busy")
        if greeting != b"\x04\x00\x00":
            raise ValueError("unexpected native scanner greeting")
        stream.sendall(b"\x04\x01\x00\x20\xcb")
        if receive(stream, 3) != b"\x04\x02\x00":
            raise ValueError("scanner did not accept the bizhub 215 model identifier")
        try:
            command = (b"\x03\x09" + struct.pack("<I", 1) + b"\x00").ljust(64, b"\x00")
            stream.sendall(command)
            result = receive(stream, 1)[0]
        finally:
            stream.sendall(b"\x04\x03\x00")
        if result != 0:
            raise ValueError("scanner reports a non-ready status: " + str(result))
    return "native scanner is ready; no image acquisition was started"


def locations(home=None):
    home = Path(home) if home else Path.home()
    return (home / ".config/bizhub215-scanner",
            home / ".local/lib/bizhub215-scanner",
            home / ".local/share/applications/bizhub215-scanner.desktop")


def write_new(path, data, mode):
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError("refusing a symlink in the profile destination")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, "wb") as out:
        out.write(data)


def desktop_quote(value):
    # Desktop Entry Exec quoting differs from shell quoting; % is a field code.
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'


def setup(host, library, home=None):
    if os.geteuid() == 0:
        raise ValueError("set up the scanner as your normal desktop user, never with sudo")
    host = address(host)
    library = Path(library)
    if not library.is_file() or library.is_symlink():
        raise ValueError("a regular, locally built scanner library is required")
    config, runtime, desktop = locations(home)
    if config.exists() or runtime.exists() or desktop.exists():
        raise ValueError("scanner profile already exists; remove it deliberately before replacing")
    for destination in (config, runtime, desktop):
        if any(p.is_symlink() for p in (destination, *destination.parents)):
            raise ValueError("refusing a symlink in the profile destination")
    created = []
    try:
        config.mkdir(parents=True, mode=0o700)
        runtime.mkdir(parents=True, mode=0o700)
        entries = {
            config / "dll.conf": (b"magicolor\n", 0o600),
            config / "magicolor.conf": (("request-timeout 5000\nscan-data-timeout 20000\nnet " + host + " 0x20cb\n").encode(), 0o600),
            config / "profile.json": (json.dumps({"printer": host}).encode(), 0o600),
            runtime / "sane/libsane-magicolor.so.1": (library.read_bytes(), 0o700),
            runtime / "km215_scan.py": (Path(__file__).read_bytes(), 0o600),
        }
        command = "/usr/bin/python3 " + desktop_quote(runtime / "km215_scan.py") + " gui"
        entry = ("[Desktop Entry]\nType=Application\nName=bizhub 215 Scanner\n"
                 "Name[ru]=Сканер bizhub 215\nComment=Open the scanner; scanning starts only on your command\n"
                 "Icon=scanner\nTerminal=false\nCategories=Graphics;Scanning;\nExec=" + command + "\n")
        entries[desktop] = (entry.encode(), 0o644)
        for path, (data, mode) in entries.items():
            write_new(path, data, mode)
            created.append(path)
        print("Added a private scanner profile and menu shortcut. No CUPS changes; no scan started.")
    except Exception:
        for path in reversed(created):
            path.unlink()
        for path in (runtime / "sane", runtime, config):
            try:
                path.rmdir()
            except OSError:
                pass
        raise


def profile_environment(home=None):
    config, runtime, _ = locations(home)
    host = address(json.loads((config / "profile.json").read_text())["printer"])
    env = dict(os.environ)
    env["SANE_CONFIG_DIR"] = str(config)
    # Do not load other user-specified scanner libraries into the GUI.
    env["LD_LIBRARY_PATH"] = str(runtime / "sane")
    env.pop("SANE_AIRSCAN_DEVICE", None)
    return host, env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("probe", help="query native status only; does not scan")
    p.add_argument("--printer", required=True)
    p = sub.add_parser("setup", help="create only a private user scanner profile")
    p.add_argument("--printer", required=True)
    p.add_argument("--library", type=Path)
    p.add_argument("--manifest", type=Path)
    sub.add_parser("options", help="read scanner capabilities without scanning")
    sub.add_parser("gui", help="open Skanpage or Document Scanner; no automatic scan")
    args = parser.parse_args()
    if args.action == "probe":
        print(probe(args.printer))
    elif args.action == "setup":
        library = args.library
        if library is None:
            manifest = args.manifest or ROOT / "build/scanner/manifest.json"
            record = json.loads(manifest.read_text())
            library = Path(record["library"])
            if hashlib.sha256(library.read_bytes()).hexdigest() != record["library_sha256"]:
                raise ValueError("built scanner library checksum changed")
        setup(args.printer, library)
    else:
        host, env = profile_environment()
        device = "magicolor:net:" + host + "?model=0x20cb"
        if args.action == "options":
            subprocess.run(["scanimage", "-A", "-d", device], env=env, check=True, timeout=25)
        elif shutil.which("skanpage"):
            os.execvpe("skanpage", ["skanpage", "-d", device], env)
        elif shutil.which("simple-scan"):
            os.execvpe("simple-scan", ["simple-scan", device], env)
        else:
            raise ValueError("install Skanpage or simple-scan from your distribution")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print("Scanner: " + str(error), file=sys.stderr)
        sys.exit(1)
