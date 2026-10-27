# SPDX-License-Identifier: GPL-2.0-or-later
import importlib.util
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import km215_scan as scan


class FakeStream:
    def __init__(self, data):
        self.data = bytearray(data)
        self.sent = []
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def settimeout(self, value): pass
    def recv(self, size):
        # Exercise fragmented network reads, including a three-byte greeting.
        value = bytes(self.data[:1])
        del self.data[:1]
        return value
    def sendall(self, data): self.sent.append(data)


class ScannerTests(unittest.TestCase):
    def test_probe_never_sends_acquisition_command(self):
        stream = FakeStream(bytes.fromhex("04000004020000"))
        with mock.patch.object(scan.socket, "create_connection", return_value=stream):
            self.assertIn("ready", scan.probe("192.0.2.10"))
        self.assertEqual(stream.sent[0], bytes.fromhex("04010020cb"))
        self.assertEqual(len(stream.sent[1]), 64)
        self.assertEqual(stream.sent[1][:2], bytes.fromhex("0309"))
        self.assertEqual(stream.sent[-1], bytes.fromhex("040300"))
        self.assertFalse(any(x.startswith(bytes.fromhex("0308")) for x in stream.sent))

    def test_busy_and_truncated_handshake_are_rejected(self):
        for data in (bytes.fromhex("040001"), bytes.fromhex("0400")):
            with mock.patch.object(scan.socket, "create_connection", return_value=FakeStream(data)):
                with self.assertRaises(ValueError): scan.probe("192.0.2.10")

    def test_reject_host_and_command_injection(self):
        for value in ("example.invalid", "192.0.2.10\nnet another", "127.0.0.1; true", "::1"):
            with self.assertRaises(ValueError): scan.address(value)

    def test_profile_is_private_and_does_not_replace_existing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            library = home / "backend.so"
            library.write_bytes(b"test locally built library")
            scan.setup("192.0.2.10", library, home)
            config, runtime, desktop = scan.locations(home)
            self.assertEqual(stat.S_IMODE(config.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((config / "magicolor.conf").stat().st_mode), 0o600)
            self.assertIn("0x20cb", (config / "magicolor.conf").read_text())
            self.assertNotIn("0308", desktop.read_text())
            before = desktop.read_bytes()
            with self.assertRaises(ValueError): scan.setup("192.0.2.11", library, home)
            self.assertEqual(desktop.read_bytes(), before)
            host, env = scan.profile_environment(home)
            self.assertEqual(host, "192.0.2.10")
            self.assertEqual(env["LD_LIBRARY_PATH"], str(runtime / "sane"))

    def test_profile_rejects_symlink_parent(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            home = Path(tmp)
            (home / ".config").symlink_to(other, target_is_directory=True)
            library = home / "backend.so"
            library.write_bytes(b"test")
            with self.assertRaises(ValueError): scan.setup("192.0.2.10", library, home)
            self.assertEqual(list(Path(other).iterdir()), [])


if __name__ == "__main__": unittest.main()
