#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Portable source installer. Default action is a read-only installation plan."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import stat

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = Path("/usr/local/lib/bizhub215")
MANIFEST = PRIVATE / "installed.json"
QUEUE = "Konica_215_Custom"


def dependencies():
    data = {}
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                data[key] = value.strip('"')
    except OSError:
        pass
    ids = {data.get("ID", ""), *data.get("ID_LIKE", "").split()}
    if ids & {"debian", "ubuntu", "linuxmint", "pop"}:
        return ["apt-get", "install", "build-essential", "python3", "ghostscript", "cups", "libcups2-dev", "libjbig-dev"]
    if ids & {"fedora", "rhel", "centos", "rocky", "almalinux"}:
        return ["dnf", "install", "gcc", "make", "python3", "ghostscript", "cups", "cups-devel", "jbigkit-devel"]
    if ids & {"arch", "manjaro", "endeavouros"}:
        return ["pacman", "-S", "--needed", "base-devel", "python", "ghostscript", "cups", "jbigkit"]
    if ids & {"opensuse", "opensuse-leap", "opensuse-tumbleweed", "suse"}:
        return ["zypper", "install", "gcc", "make", "python3", "ghostscript", "cups", "cups-devel", "libjbig-devel"]
    return None


def cups_paths():
    if not shutil.which("cups-config"):
        raise ValueError("cups-config is missing; install CUPS development dependencies")
    def query(option):
        return subprocess.check_output(["cups-config", option], text=True).strip()
    if not query("--version").startswith("2."):
        raise ValueError("this PPD driver requires CUPS 2.x; CUPS 3 is not supported")
    serverbin = Path(query("--serverbin"))
    datadir = Path(query("--datadir"))
    if not serverbin.is_absolute() or not datadir.is_absolute():
        raise ValueError("CUPS reported relative paths")
    return serverbin, datadir


def files(serverbin, datadir):
    return {
        "build/km215-jbig": PRIVATE / "build/km215-jbig",
        "tools/km215_job.py": PRIVATE / "tools/km215_job.py",
        "tools/km215_cups.py": PRIVATE / "tools/km215_cups.py",
        "cups/km215-pdftogdi": serverbin / "filter/km215-pdftogdi",
        "cups/KonicaMinolta-bizhub215-custom.ppd": datadir / "model/KonicaMinolta-bizhub215-custom.ppd",
    }


def secure_path(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError(f"refusing symlink target: {path}")


def source_bytes(path):
    for parent in (ROOT, *path.relative_to(ROOT).parents):
        directory = parent if parent == ROOT else ROOT / parent
        if directory.is_symlink() or directory.stat().st_mode & 0o022:
            raise ValueError("source directory must not be writable by other users")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022:
            raise ValueError("source must be a regular file protected against other users")
        if info.st_size > 8 * 1024 * 1024:
            raise ValueError("installation source too large")
        return source.read(8 * 1024 * 1024 + 1)


def install(prefix):
    serverbin, datadir = cups_paths()
    mapping = files(serverbin, datadir)
    contents = {source: source_bytes(ROOT / source) for source in mapping}
    def target(path):
        return prefix / str(path).lstrip("/")
    private = target(PRIVATE)
    if private.exists():
        raise ValueError("driver already installed; use its uninstall command before changing versions")
    for source, dest in mapping.items():
        if not (ROOT / source).is_file():
            raise ValueError(f"missing {source}: build as a normal user first")
        secure_path(target(dest))
        if target(dest).exists():
            raise ValueError(f"refusing overwrite: {dest}")
    installed = []
    manifest = target(MANIFEST)
    try:
        for source, dest in mapping.items():
            dest = target(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            secure_path(dest)
            data = contents[source]
            if source == "cups/km215-pdftogdi" and prefix != Path("/"):
                data = data.replace(str(PRIVATE).encode(), str(private).encode())
            with dest.open("xb") as out:
                installed.append(dest)
                out.write(data)
                os.fchmod(out.fileno(), 0o755 if source in {"build/km215-jbig", "cups/km215-pdftogdi"} else 0o644)
        for directory in (private, private / "tools", private / "build"):
            directory.chmod(0o755)
        record = {"version": (ROOT / "VERSION").read_text().strip(),
                  "files": [str(x) for x in mapping.values()],
                  "serverbin": str(serverbin), "datadir": str(datadir)}
        with manifest.open("x") as out:
            installed.append(manifest)
            json.dump(record, out, indent=2)
        manifest.chmod(0o644)
        restorecon = shutil.which("restorecon")
        if prefix == Path("/") and restorecon:
            subprocess.run([restorecon, "-F", *map(str, installed)], check=True)
    except Exception:
        for item in reversed(installed):
            item.unlink()
        for directory in (private / "tools", private / "build", private):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise
    print(f"Installed driver under {prefix}. No queues changed; no jobs sent.")


def uninstall():
    secure_path(MANIFEST)
    record = json.loads(MANIFEST.read_text())
    expected = [str(x) for x in files(Path(record["serverbin"]), Path(record["datadir"])).values()]
    if record["files"] != expected:
        raise ValueError("invalid installation manifest")
    # Require the external filter/PPD to live under the local CUPS paths.
    current = files(*cups_paths())
    if expected != [str(x) for x in current.values()]:
        raise ValueError("CUPS installation paths changed; inspect manifest before removal")
    for path in [*map(Path, expected), MANIFEST]:
        secure_path(path)
    for path in [*map(Path, expected), MANIFEST]:
        path.unlink(missing_ok=True)
    for path in (PRIVATE / "tools", PRIVATE / "build", PRIVATE):
        try:
            path.rmdir()
        except OSError:
            pass
    print("Removed only driver files. Source and printer queues remain unchanged.")


def elevate(command):
    if shutil.which("sudo"):
        return ["sudo", *command]
    if shutil.which("pkexec"):
        return ["pkexec", *command]
    raise ValueError("sudo/pkexec missing; ask your administrator to run the printed system command")


def setup_scanner(printer):
    if os.geteuid() == 0:
        raise ValueError("configure the scanner as your normal desktop user")
    if not printer:
        raise ValueError("--setup-scanner requires --printer with the scanner IPv4 address")
    ipaddress.IPv4Address(printer)
    from km215_scan import setup as scanner_setup
    from build_scanner import build as scanner_build
    import hashlib
    cache = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "bizhub215-scanner"
    manifest = cache / "manifest.json"
    print("Scanner setup uses a private SANE backend and user menu entry; it does not change CUPS.")
    print("Needs cc, make, patch, pkg-config, scanimage and Skanpage or simple-scan.")
    if not manifest.exists():
        print("Downloads checksum-pinned official GPL SANE 1.4.0 source and builds only its network backend.")
        if input("Build this optional scanner backend? [y/N] ").lower() != "y":
            return
        scanner_build(destination=cache)
    record = json.loads(manifest.read_text())
    library = Path(record["library"])
    if (hashlib.sha256(library.read_bytes()).hexdigest() != record["library_sha256"] or
        hashlib.sha256((ROOT / "scanner/sane-1.4.0-bizhub215.patch").read_bytes()).hexdigest() != record["patch_sha256"]):
        raise ValueError("scanner build differs from this source; preserve and rebuild its cache deliberately")
    if input("Add a private scanner profile and menu shortcut? [y/N] ").lower() == "y":
        scanner_setup(printer, library)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--setup", action="store_true", help="guided dependencies, native build, installation and optional queue")
    mode.add_argument("--setup-scanner", action="store_true", help="build a private native scanner backend and menu shortcut")
    mode.add_argument("--install-system", action="store_true")
    mode.add_argument("--uninstall-system", action="store_true")
    mode.add_argument("--stage", type=Path)
    parser.add_argument("--printer", help="printer IPv4/IPv6 address for optional queue creation")
    args = parser.parse_args()
    if args.printer:
        address = ipaddress.ip_address(args.printer)
    if args.setup_scanner:
        setup_scanner(args.printer)
    elif args.stage:
        prefix = args.stage.absolute()
        if prefix == Path("/"):
            raise ValueError("use --install-system for system installation")
        install(prefix)
    elif args.install_system or args.uninstall_system:
        if os.geteuid() != 0:
            raise ValueError("system changes require root")
        os.environ["PATH"] = "/usr/sbin:/usr/bin:/sbin:/bin"
        uninstall() if args.uninstall_system else install(Path("/"))
    elif args.setup:
        if os.geteuid() == 0:
            raise ValueError("run --setup as a normal user; native build must not run as root")
        if sys.version_info < (3, 8):
            raise ValueError("Python 3.8 or newer required")
        deps = dependencies()
        if deps:
            print("Optional dependency installation:", " ".join(elevate(deps)))
            if input("Install these packages using your distribution repository? [y/N] ").lower() == "y":
                subprocess.run(elevate(deps), check=True)
        subprocess.run(["make", "test"], cwd=ROOT, check=True)
        print("System installation adds only private bizhub215 files; existing targets will not be overwritten.")
        if input("Install driver files? [y/N] ").lower() != "y":
            return
        subprocess.run(elevate([sys.executable, str(Path(__file__).resolve()), "--install-system"]), check=True)
        serverbin, datadir = cups_paths()
        subprocess.run(["cupstestppd", str(datadir / "model/KonicaMinolta-bizhub215-custom.ppd")], check=True)
        if args.printer:
            # A failed server connection must not be interpreted as an absent queue.
            env = dict(os.environ, LC_ALL="C")
            listing = subprocess.run(["lpstat", "-p"], text=True, capture_output=True, env=env)
            # CUPS returns 1 for an empty configured printer list as well as connection errors.
            if listing.returncode and "No destinations added" not in (listing.stdout + listing.stderr):
                raise ValueError("cannot list CUPS queues; ensure CUPS is running before queue creation")
            if any(line.startswith(f"printer {QUEUE} ") for line in listing.stdout.splitlines()):
                raise ValueError(f"{QUEUE} already exists; refusing to modify it")
            host = f"[{address}]" if address.version == 6 else str(address)
            command = ["lpadmin", "-p", QUEUE, "-E", "-v", f"socket://{host}:9100",
                       "-P", str(datadir / "model/KonicaMinolta-bizhub215-custom.ppd"),
                       "-o", "printer-is-shared=false", "-o", "printer-error-policy=abort-job",
                       "-o", "PageSize=A4", "-o", "Resolution=600dpi", "-o", "Duplex=None"]
            print("Optional queue creation:", " ".join(command))
            if input("Create this queue without changing the default printer? [y/N] ").lower() == "y":
                subprocess.run(elevate(command), check=True)
        print("Finished. No test print was sent. Select A4, simplex, one copy.")
    else:
        print("bizhub215-linux-driver", (ROOT / "VERSION").read_text().strip())
        print("Guided install: sh install.sh --setup [--printer PRINTER_IP]")
        print("Optional scanner: sh install.sh --setup-scanner --printer PRINTER_IP")
        print("Native build: make test; stage: sh install.sh --stage PATH")
        deps = dependencies()
        print("Dependencies:", " ".join(deps) if deps else "C compiler, make, Python>=3.8, Ghostscript, CUPS 2.x development files, JBIG-KIT development files")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError, EOFError) as error:
        print(f"Installation failed: {error}", file=sys.stderr)
        sys.exit(1)
