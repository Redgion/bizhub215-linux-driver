#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Inspect release contents and metadata, without installing or running packages."""
import argparse
import hashlib
import io
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import zipfile
from check_public import findings
from build_release import ROOT

MAX_BYTES = 32 * 1024 * 1024


def check(name, data):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('unsafe release member path')
    reasons = findings(name.encode()) + findings(data)
    if reasons:
        # Do not echo matched private data or a possibly private member name.
        raise ValueError('release member privacy issue: ' + ', '.join(sorted(set(reasons))))
    if path.suffix.lower() in {'.dll', '.exe', '.prn', '.pcap', '.png', '.jpg'}:
        raise ValueError('private/vendor material must not be distributed')
    if path.name.startswith('libsane-') or path.name == 'km215-jbig-test':
        raise ValueError('development/test library must not be distributed')
    if path.name == 'km215-jbig' and b'jbg_dec_init' in data:
        raise ValueError('test decoder in production helper')


def tar_members(data):
    count = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:*') as archive:
        if sum(m.size for m in archive.getmembers()) > MAX_BYTES:
            raise ValueError('expanded release too large')
        for entry in archive:
            if entry.isdir():
                continue
            if not entry.isfile():
                raise ValueError('unexpected link/special release entry')
            check(entry.name, archive.extractfile(entry).read())
            count += 1
    return count


def cpio_members(data):
    offset, count = 0, 0
    while offset + 110 <= len(data):
        header = data[offset:offset+110]
        if header[:6] not in (b'070701', b'070702'):
            raise ValueError('unexpected RPM payload format')
        fields = [int(header[6+i*8:14+i*8], 16) for i in range(13)]
        mode, uid, gid, size, namesize = fields[1], fields[2], fields[3], fields[6], fields[11]
        offset += 110
        if namesize < 1 or offset + namesize > len(data):
            raise ValueError('truncated RPM payload')
        name = data[offset:offset+namesize-1].decode('utf-8')
        offset = (offset + namesize + 3) & ~3
        if name == 'TRAILER!!!':
            return count
        if size > MAX_BYTES or offset + size > len(data):
            raise ValueError('invalid RPM payload size')
        content = data[offset:offset+size]
        offset = (offset + size + 3) & ~3
        if uid or gid:
            raise ValueError('non-root owner in release package')
        kind = mode & 0o170000
        if kind == 0o040000:
            continue
        if kind != 0o100000:
            raise ValueError('unexpected RPM payload entry')
        if name.endswith('.tar.gz'):
            count += tar_members(content)
        else:
            check(name, content)
            count += 1
    raise ValueError('missing RPM payload trailer')


def verify(path):
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        raise ValueError('release asset too large')
    if path.name.endswith('.tar.gz'):
        return tar_members(data)
    if path.suffix == '.zip':
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if sum(x.file_size for x in archive.infolist()) > MAX_BYTES:
                raise ValueError('expanded ZIP too large')
            for entry in archive.infolist():
                check(entry.filename, archive.read(entry))
            return len(archive.infolist())
    if path.suffix == '.deb':
        for option in ('--field', '--ctrl-tarfile', '--fsys-tarfile'):
            result = subprocess.check_output(['dpkg-deb', option, str(path)], timeout=30)
            if option == '--field':
                check('package-metadata', result)
            else:
                tar_members(result)
        return 1
    if path.suffix == '.rpm':
        metadata = subprocess.check_output(['rpm', '-qp', '--qf',
            '%{NAME}\n%{VERSION}\n%{PACKAGER}\n%{VENDOR}\n%{BUILDHOST}\n%{DESCRIPTION}\n', str(path)], timeout=30)
        check('package-metadata', metadata)
        payload = subprocess.check_output(['rpm2cpio', str(path)], timeout=30)
        if len(payload) > MAX_BYTES:
            raise ValueError('expanded RPM too large')
        return cpio_members(payload)
    raise ValueError('unexpected asset format')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-checksums', action='store_true')
    args = parser.parse_args()
    version = (ROOT / 'VERSION').read_text().strip()
    paths = sorted(p for p in (ROOT / 'dist').iterdir()
                   if version in p.name and p.name.endswith(('.tar.gz', '.zip', '.deb', '.rpm')))
    if not paths:
        raise ValueError('no release assets')
    total = sum(verify(p) for p in paths)
    if args.write_checksums:
        (ROOT / 'dist/SHA256SUMS').write_text(''.join(
            hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n' for p in paths))
    print(f'Inspected {len(paths)} assets and {total} entries; no privacy findings')


if __name__ == '__main__':
    main()
