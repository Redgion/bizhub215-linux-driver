# SPDX-License-Identifier: GPL-2.0-or-later
import importlib.util
from pathlib import Path
import random
import struct
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("job", ROOT / "tools/km215_job.py")
job = importlib.util.module_from_spec(spec)
spec.loader.exec_module(job)


class CodecTests(unittest.TestCase):
    def test_username_is_nonempty_and_cannot_inject_pjl(self):
        self.assertEqual(job.safe_username(""), "linux")
        self.assertEqual(job.safe_username("\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c"), "linux")
        hostile = job.safe_username("user\r\n@PJL SET COPIES=999")
        self.assertNotIn("\r", hostile)
        self.assertNotIn("\n", hostile)
        self.assertNotIn("=", hostile)
        self.assertEqual(len(job.safe_username("x" * 200)), 32)

    def codec(self, args, raw, check=True):
        codec = ROOT / "build/km215-jbig-test" if args == ["decode"] else job.CODEC
        return subprocess.run([str(codec), *args], input=raw,
                              capture_output=True, check=check, timeout=30)

    def test_bih_matches_disassembly_and_lossless_pixels(self):
        rng = random.Random(215)
        for width, height in ((8, 1), (256, 120), (4960, 7016)):
            size = width // 8 * height
            # A4 rectangle plus blank background, and high entropy on small pages.
            raster = bytearray(size)
            if width == 4960:
                for y in range(100, 300):
                    raster[y*(width//8)+20:y*(width//8)+80] = b"\xff" * 60
            else:
                raster[:] = rng.randbytes(size)
            encoded = self.codec(["encode", str(width), str(height)], raster).stdout
            expected = struct.pack(">BBBBIIIBBBB", 0, 0, 1, 0, width, height, height, 0, 0, 3, 0x48)
            self.assertEqual(encoded[:20], expected)
            decoded = self.codec(["decode"], encoded)
            self.assertEqual(decoded.stdout, raster)
            self.assertEqual(decoded.stderr.strip(), f"{width} {height}".encode())

    def test_framing_multiple_blocks_binary_commands_and_corruption(self):
        # Binary payload can contain bytes resembling commands; lengths govern parsing.
        header = struct.pack(">BBBBIIIBBBB", 0, 0, 1, 0, 4960, 7016, 7016, 0, 0, 3, 0x48)
        payload = header + (b"@PJL SET PAGESTATUS=END\r\n\x00\xff" * 3000)
        framed = job.wrap(payload, 4960, 7016)
        settings, recovered = job.extract(framed)
        self.assertEqual(recovered, payload)
        self.assertEqual(settings[b"PAPERWIDTH"], b"4960")
        self.assertEqual(settings[b"USERNAME"], b"linux")
        self.assertGreater(framed.count(b"@PJL SET IMAGELEN="), 1)
        with self.assertRaises(ValueError):
            job.extract(framed.replace(b"IMAGELEN=32768", b"IMAGELEN=32767", 1))
        with self.assertRaises(ValueError):
            job.extract(framed[:-4])

    def test_pbm_first_pixel_can_be_whitespace(self):
        self.assertEqual(job.pbm_read(b"P4\n# test\n8 1\n\x0a"), (8, 1, b"\x0a"))
        self.assertEqual(job.pbm_read(b"P4\r\n8 1\r\n\x20"), (8, 1, b"\x20"))
        with self.assertRaises(ValueError):
            job.pbm_read(b"P4\n8 1\n")

    def test_invalid_codec_input(self):
        for args, raw in ((["encode", "0", "1"], b""),
                          (["encode", "8", "2"], b"\0"),
                          (["encode", "8", "1"], b"\0\0"),
                          (["decode"], b"not jbig")):
            self.assertNotEqual(self.codec(args, raw, check=False).returncode, 0)

    def test_production_codec_has_no_decoder(self):
        p = subprocess.run([str(job.CODEC), "decode"], input=b"", capture_output=True)
        self.assertEqual(p.returncode, 2)

    def test_decoder_rejects_hostile_header_before_allocation(self):
        for planes, width, height, layers in ((255, 4960, 7016, 0),
                                              (1, 0xffffffff, 1, 0),
                                              (1, 8, 1, 31)):
            header = struct.pack(">BBBBIIIBBBB", 0, layers, planes, 0,
                                 width, height, height, 0, 0, 3, 0x48)
            p = self.codec(["decode"], header, check=False)
            self.assertEqual(p.returncode, 2)
            self.assertEqual(p.stdout, b"")


if __name__ == "__main__":
    unittest.main()
