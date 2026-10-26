#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build a native RPM or DEB in the current distribution; never install it."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
NAME = "bizhub215-linux-driver"


def payload(stage):
    mapping = {
        "build/km215-jbig": "usr/lib/bizhub215/build/km215-jbig",
        "tools/km215_job.py": "usr/lib/bizhub215/tools/km215_job.py",
        "tools/km215_cups.py": "usr/lib/bizhub215/tools/km215_cups.py",
        "cups/km215-pdftogdi": "usr/lib/cups/filter/km215-pdftogdi",
        "cups/KonicaMinolta-bizhub215-custom.ppd": "usr/share/cups/model/KonicaMinolta-bizhub215-custom.ppd",
        "LICENSE": "usr/share/doc/bizhub215-linux-driver/LICENSE",
        "NOTICE": "usr/share/doc/bizhub215-linux-driver/NOTICE",
        "README.md": "usr/share/doc/bizhub215-linux-driver/README.md",
    }
    for src, dst in mapping.items():
        dest = stage / dst
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / src, dest)
        if src == "cups/km215-pdftogdi":
            dest.write_text(dest.read_text().replace("/usr/local/lib/bizhub215", "/usr/lib/bizhub215"))
        dest.chmod(0o755 if src in {"build/km215-jbig", "cups/km215-pdftogdi"} else 0o644)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("format", choices=["deb", "rpm"])
    args = parser.parse_args()
    # A shared source directory may contain a helper from another distribution.
    subprocess.run(["make", "clean"], cwd=ROOT, check=True)
    subprocess.run(["make", "test"], cwd=ROOT, check=True)
    version = (ROOT / "VERSION").read_text().strip()
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    if args.format == "deb":
        arch = subprocess.check_output(["dpkg", "--print-architecture"], text=True).strip()
        with tempfile.TemporaryDirectory(prefix="km215-deb-") as tmp:
            stage = Path(tmp) / "package"
            payload(stage)
            control = stage / "DEBIAN"
            control.mkdir()
            (control / "control").write_text(
                f"Package: {NAME}\nVersion: {version}\nArchitecture: {arch}\n"
                "Maintainer: bizhub215-linux-driver contributors <noreply@github.com>\n"
                "Section: text\nPriority: optional\n"
                "Depends: python3 (>= 3.8), ghostscript, cups, libc6 (>= 2.34), libjbig0 (>= 2.0)\n"
                "Description: Unofficial GDI/JBIG driver for Konica Minolta bizhub 215\n"
                " A4 monochrome CUPS 2.x PDF filter. Does not create queues or print jobs.\n")
            (control / "preinst").write_text(
                "#!/bin/sh\nset -eu\n"
                "if [ -e /usr/lib/cups/filter/km215-pdftogdi ] && "
                "! dpkg-query -W -f='${Status}' bizhub215-linux-driver 2>/dev/null | grep -q 'installed'; then\n"
                " echo 'An unmanaged bizhub215 installation already exists; remove it deliberately first.' >&2\n exit 1\nfi\n")
            (control / "preinst").chmod(0o755)
            target = dist / f"{NAME}_{version}_ubuntu24.04_{arch}.deb"
            subprocess.run(["dpkg-deb", "--root-owner-group", "--build", str(stage), str(target)], check=True)
    else:
        with tempfile.TemporaryDirectory(prefix="km215-rpm-") as tmp:
            top = Path(tmp)
            for directory in ("BUILD", "BUILDROOT", "RPMS", "SOURCES", "SPECS", "SRPMS"):
                (top / directory).mkdir()
            subprocess.run(["python3", "tools/build_release.py"], cwd=ROOT, check=True)
            shutil.copyfile(dist / f"{NAME}-{version}.tar.gz", top / "SOURCES" / f"{NAME}-{version}.tar.gz")
            spec = top / "SPECS/driver.spec"
            spec.write_text(f"""Name: {NAME}
Version: {version}
Release: 1%{{?dist}}
Summary: Unofficial GDI/JBIG driver for Konica Minolta bizhub 215
License: GPL-2.0-or-later
Source0: {NAME}-{version}.tar.gz
BuildRequires: gcc, make, python3, ghostscript, cups-devel, jbigkit-devel
Requires: python3 >= 3.8, ghostscript, cups, jbigkit-libs
%description
A4 monochrome CUPS 2.x PDF filter. No automatic queues or print jobs.
%prep
%autosetup
%build
%make_build
%check
make test
%install
mkdir -p %{{buildroot}}/usr/lib/bizhub215/build %{{buildroot}}/usr/lib/bizhub215/tools %{{buildroot}}/usr/lib/cups/filter %{{buildroot}}/usr/share/cups/model
install -m755 build/km215-jbig %{{buildroot}}/usr/lib/bizhub215/build/
install -m644 tools/km215_job.py tools/km215_cups.py %{{buildroot}}/usr/lib/bizhub215/tools/
sed 's@/usr/local/lib/bizhub215@/usr/lib/bizhub215@g' cups/km215-pdftogdi > %{{buildroot}}/usr/lib/cups/filter/km215-pdftogdi
chmod 755 %{{buildroot}}/usr/lib/cups/filter/km215-pdftogdi
install -m644 cups/KonicaMinolta-bizhub215-custom.ppd %{{buildroot}}/usr/share/cups/model/
%pre
if [ -e /usr/lib/cups/filter/km215-pdftogdi ] && ! rpm -q {NAME} >/dev/null 2>&1; then
 echo 'An unmanaged bizhub215 installation exists; remove it deliberately first.' >&2
 exit 1
fi
%files
%license LICENSE
%doc README.md NOTICE
/usr/lib/bizhub215
/usr/lib/cups/filter/km215-pdftogdi
/usr/share/cups/model/KonicaMinolta-bizhub215-custom.ppd
""")
            subprocess.run(["rpmbuild", "-ba", "--define", f"_topdir {top}", str(spec)], check=True)
            for path in [*(top / "RPMS").rglob("*.rpm"), *(top / "SRPMS").glob("*.rpm")]:
                shutil.copyfile(path, dist / path.name)
    print("Built native package(s) in dist; no system files or queues changed.")


if __name__ == "__main__":
    main()
