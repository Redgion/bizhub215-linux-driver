#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build source-only release archives from an explicit public allowlist."""
import gzip
import hashlib
import io
from pathlib import Path
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIRS = ("src", "tools", "cups", "tests", "docs", ".github")
PUBLIC_FILES = ("README.md", "LICENSE", "NOTICE", "VERSION", "CHANGELOG.md", ".gitignore",
                "Makefile", "install.sh", "uninstall.sh")


def sources():
    paths = [ROOT / name for name in PUBLIC_FILES]
    for directory in PUBLIC_DIRS:
        paths.extend(p for p in (ROOT / directory).rglob("*")
                     if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
    for path in paths:
        if path.is_symlink() or path.suffix.lower() in {".dll", ".exe", ".prn", ".pcap", ".zip"}:
            raise ValueError(f"non-public or binary material in release: {path.name}")
    return sorted(paths)


def main():
    version = (ROOT / "VERSION").read_text().strip()
    prefix = f"bizhub215-linux-driver-{version}"
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    paths = sources()
    from check_public import scan
    scan(paths)
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w") as tar:
        for path in paths:
            info = tarfile.TarInfo(f"{prefix}/{path.relative_to(ROOT).as_posix()}")
            data = path.read_bytes()
            info.size = len(data)
            info.mode = 0o755 if path.suffix == ".sh" or path.name == "km215-pdftogdi" else 0o644
            info.mtime = 0
            tar.addfile(info, io.BytesIO(data))
    tarpath = dist / f"{prefix}.tar.gz"
    with tarpath.open("wb") as out:
        with gzip.GzipFile(filename="", mode="wb", fileobj=out, mtime=0) as gz:
            gz.write(archive.getvalue())
    zippath = dist / f"{prefix}.zip"
    with zipfile.ZipFile(zippath, "w", compression=zipfile.ZIP_DEFLATED) as zip:
        for path in paths:
            info = zipfile.ZipInfo(f"{prefix}/{path.relative_to(ROOT).as_posix()}")
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if path.suffix == ".sh" else 0o100644) << 16
            zip.writestr(info, path.read_bytes())
    checksums = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n"
                        for p in (tarpath, zippath))
    (dist / "SHA256SUMS").write_text(checksums)
    print(f"Built {len(paths)} public source files into {tarpath.name} and {zippath.name}")


if __name__ == "__main__":
    main()
