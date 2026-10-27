#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build an isolated network-only SANE magicolor backend with a bizhub 215 profile."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://gitlab.com/-/project/429008/uploads/843c156420e211859e974f78f64c3ea3/sane-backends-1.4.0.tar.gz"
SOURCE_SHA256 = "f99205c903dfe2fb8990f0c531232c9a00ec9c2c66ac7cb0ce50b4af9f407a72"
BUILD = ROOT / "build/scanner"
PATCH = ROOT / "scanner/sane-1.4.0-bizhub215.patch"


def unpack(archive, destination):
    with tarfile.open(archive, "r:gz") as source:
        members = source.getmembers()
        if sum(m.size for m in members) > 160 * 1024 * 1024:
            raise ValueError("source archive too large")
        for member in members:
            path = Path(member.name)
            if path.is_absolute() or ".." in path.parts or not (member.isfile() or member.isdir()):
                raise ValueError("unsafe source archive entry")
        # Extract only regular files/directories, never links or special files.
        for member in members:
            target = destination / member.name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as out, source.extractfile(member) as data:
                    shutil.copyfileobj(data, out)
                target.chmod(member.mode & 0o755)
                # Release-generated configure/Makefile timestamps must stay ordered;
                # otherwise make unnecessarily tries to invoke autotools.
                os.utime(target, (member.mtime, member.mtime))


def build(archive=None, destination=None):
    build_root = Path(destination) if destination else BUILD
    if os.geteuid() == 0:
        raise ValueError("build as a regular user, never with sudo")
    if build_root.exists():
        raise ValueError("scanner build directory already exists; preserve or remove it deliberately before rebuilding")
    build_root.mkdir(parents=True, mode=0o700)
    if archive:
        data = Path(archive).read_bytes()
    else:
        with urllib.request.urlopen(SOURCE_URL, timeout=30) as response:
            data = response.read(16 * 1024 * 1024 + 1)
    if len(data) > 16 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError("official SANE source checksum mismatch")
    archive_path = build_root / "sane-backends-1.4.0.tar.gz"
    archive_path.write_bytes(data)
    unpack(archive_path, build_root)
    source = build_root / "sane-backends-1.4.0"
    subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(PATCH)], cwd=source, check=True)
    compile_dir = build_root / "compile"
    compile_dir.mkdir()
    env = dict(os.environ, BACKENDS="magicolor",
               CFLAGS="-O2 -g0 -fstack-protector-strong -D_FORTIFY_SOURCE=2 "
                      + "-ffile-prefix-map=" + str(ROOT) + "=/usr/src/bizhub215 "
                      + "-ffile-prefix-map=" + str(build_root) + "=/usr/src/sane-bizhub215")
    options = ["--without-" + x for x in ("usb", "snmp", "avahi", "systemd", "gphoto2", "v4l", "libcurl", "poppler-glib")]
    # Configure does not install anything; fixed compiled paths avoid home-path leaks.
    subprocess.run([str(source / "configure"), "--prefix=/usr", "--libdir=/usr/lib",
                    "--disable-nls", "--disable-preload", "--disable-locking", *options],
                   cwd=compile_dir, env=env, check=True)
    for directory, targets in (("lib", []), ("sanei", []), ("backend", ["libsane-magicolor.la"])):
        subprocess.run(["make", "-C", directory, "-j2", *targets], cwd=compile_dir, check=True)
    library = compile_dir / "backend/.libs/libsane-magicolor.so.1.4.0"
    if not library.is_file():
        raise ValueError("expected scanner library was not built")
    (build_root / "manifest.json").write_text(json.dumps({
        "source_sha256": SOURCE_SHA256,
        "patch_sha256": hashlib.sha256(PATCH.read_bytes()).hexdigest(),
        "library": str(library),
        "library_sha256": hashlib.sha256(library.read_bytes()).hexdigest(),
    }, indent=2))
    print("Built an isolated scanner backend. No system libraries replaced; no scan started.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--archive", type=Path, help="optional already downloaded official source archive")
    parser.add_argument("--build-dir", type=Path, help="new writable build directory; useful with installed packages")
    args = parser.parse_args()
    if args.build:
        try:
            build(args.archive, args.build_dir)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            parser.exit(1, str(error) + "\n")
    else:
        print("Optional build: python3 tools/build_scanner.py --build")
        print("Needs cc, make, patch, pkg-config; downloads checksum-pinned GPL SANE source.")
