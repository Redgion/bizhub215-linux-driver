# SPDX-License-Identifier: GPL-2.0-or-later
"""Optional native backend integration against localhost only, never a real MFP."""
import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import threading
import unittest

LIBRARY = os.environ.get("KM215_SCANNER_LIBRARY")


@unittest.skipUnless(LIBRARY, "set KM215_SCANNER_LIBRARY to test the built native backend")
class NativeBackendTests(unittest.TestCase):
    def run_backend(self, scan, short_ack=False, dimensions=(512, 2, 128, 2)):
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(("127.0.0.1", 4567))
        except OSError:
            server.close()
            self.skipTest("localhost port 4567 is occupied or restricted")
        server.listen(1)
        server.settimeout(10)
        commands, errors = [], []
        def worker():
            try:
                with server.accept()[0] as client:
                    client.settimeout(5)
                    def read(size):
                        data = b""
                        while len(data) < size:
                            part = client.recv(size-len(data))
                            if not part: raise EOFError()
                            data += part
                        return data
                    client.sendall(bytes.fromhex("040000"))
                    self.assertEqual(read(5), bytes.fromhex("04010020cb"))
                    client.sendall(bytes.fromhex("040200"))
                    while True:
                        first = read(2)
                        if first == bytes.fromhex("0403"):
                            read(1)
                            break
                        packet = first + read(62)
                        self.assertEqual(packet[0], 3)
                        command = packet[1]
                        commands.append(command)
                        if command == 0x09:
                            client.sendall(b"\0")
                        elif command == 0x0b:
                            client.sendall(struct.pack("<4H", *dimensions))
                        elif command in (0x0d, 0x12):
                            client.sendall(bytes(11))
                        elif command == 0x0e:
                            size = struct.unpack_from("<I", packet, 6)[0]
                            self.assertEqual(size, 1024)
                            client.sendall(b"\0" + struct.pack("<H", size-1 if short_ack else size) + bytes(2))
                            if not short_ack:
                                client.sendall((bytes(range(128)) + b"\x7f"*384)*2)
                        elif command == 0x0c:
                            self.assertEqual(struct.unpack_from("<I", packet, 2)[0], 13)
                        elif command not in (0x08, 0x0a, 0x0c):
                            raise ValueError("unexpected protocol command")
            except Exception as error:
                errors.append(error)
            finally:
                server.close()
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                profile = Path(tmp)
                (profile / "dll.conf").write_text("magicolor\n")
                env = dict(os.environ, SANE_CONFIG_DIR=str(profile),
                           LD_LIBRARY_PATH=str(Path(LIBRARY).resolve().parent))
                args = ["scanimage", "-d", "magicolor:net:127.0.0.1?model=0x20cb"]
                args += ["--mode", "Gray", "--resolution", "150", "--format=pnm"] if scan else ["-A"]
                result = subprocess.run(args, capture_output=True, env=env, timeout=10)
        finally:
            thread.join(timeout=6)
            server.close()
        if errors: raise errors[0]
        self.assertFalse(thread.is_alive())
        if short_ack or dimensions != (512, 2, 128, 2):
            self.assertGreater(result.returncode, 0)
        else:
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        return result.stdout, commands

    def test_capability_query_never_starts_acquisition(self):
        data, commands = self.run_backend(False)
        self.assertIn(b"150|300", data)
        self.assertIn(b"Flatbed", data)
        self.assertNotIn(0x08, commands)

    def test_gray_scan_removes_device_row_padding(self):
        data, commands = self.run_backend(True)
        self.assertIn(0x08, commands)
        self.assertIn(0x0e, commands)
        self.assertTrue(data.startswith(b"P5\n"))
        self.assertTrue(data.endswith(bytes(range(128))*2))

    def test_short_block_ack_fails_without_waiting_for_missing_bytes(self):
        data, commands = self.run_backend(True, short_ack=True)
        self.assertIn(0x0e, commands)
        self.assertLess(len(data), 256)

    def test_invalid_image_dimensions_fail_before_reading_pixels(self):
        # Device-controlled zero stride caused division by zero; RGB width larger
        # than the stride could read outside the per-line allocation.
        for dimensions in ((0, 2, 128, 2), (512, 0, 128, 0),
                           (512, 2, 0, 2), (64, 2, 128, 2),
                           (65535, 2, 128, 2), (8192, 8192, 8192, 8192)):
            with self.subTest(dimensions=dimensions):
                data, commands = self.run_backend(True, dimensions=dimensions)
                self.assertNotIn(0x0e, commands)
                self.assertLess(len(data), 256)
