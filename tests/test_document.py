# SPDX-License-Identifier: GPL-2.0-or-later
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import os
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import km215_job as job
import km215_cups as cups


class DocumentTests(unittest.TestCase):
    def test_single_page_protocol_regression(self):
        framed = job.encode(b"P4\n4960 7016\n" + bytes(job.RASTER_BYTES))
        self.assertEqual(b"".join(job.join_pages([framed])), framed)

    def test_two_page_pdf_filter_file_and_stdin(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "two.pdf"
            subprocess.run(["/usr/bin/gs", "-q", "-dSAFER", "-dBATCH", "-dNOPAUSE",
                            "-sDEVICE=pdfwrite", f"-sOutputFile={pdf}",
                            str(ROOT / "tests/fixtures/two-pages.ps")], check=True)
            args = [sys.executable, str(ROOT / "tools/km215_cups.py"),
                    "1", "private-test-user", "private-test-title", "1", "PageSize=A4 sides=one-sided print-scaling=auto-fit"]
            file_job = subprocess.run([*args, str(pdf)], capture_output=True, check=True, timeout=60)
            stdin_job = subprocess.run(args, input=pdf.read_bytes(), capture_output=True, check=True, timeout=60)
            self.assertEqual(file_job.stdout, stdin_job.stdout)
            self.assertNotIn(b"private-test-user", file_job.stdout)
            self.assertNotIn(b"private-test-title", file_job.stdout)
            self.assertIn(b"USERNAME=linux\r\n", file_job.stdout)
            pages = job.extract_pages(file_job.stdout)
            self.assertEqual(len(pages), 2)
            self.assertNotEqual(job.extract(pages[0])[1], job.extract(pages[1])[1])
            for page in pages:
                _, encoded = job.extract(page)
                decoded = subprocess.run([str(ROOT / "build/km215-jbig-test"), "decode"], input=encoded,
                                         capture_output=True, check=True)
                self.assertEqual(len(decoded.stdout), 4349920)
            self.assertEqual(file_job.stdout.count(b"@PJL EOJ\r\n"), 1)
            with self.assertRaises(ValueError):
                job.extract_pages(file_job.stdout[:-5])

    def test_failure_emits_no_print_data(self):
        args = [sys.executable, str(ROOT / "tools/km215_cups.py"), "1", "test-user", "bad", "1", ""]
        result = subprocess.run(args, input=b"not pdf", capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")

    def test_reject_unsupported_options(self):
        for opts in ("sides=two-sided-long-edge", "PageSize=Letter", "page-ranges=2-3", "number-up=2",
                     "orientation-requested=4", "printer-resolution=300dpi"):
            with self.assertRaises(ValueError):
                cups.options_check("1", opts)
        with self.assertRaises(ValueError):
            cups.options_check("2", "")

    def test_kde_auto_fit_scaling_is_accepted(self):
        cups.options_check("1", "PageSize=A4 print-scaling=auto-fit")

    def test_staging_install_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = [sys.executable, str(ROOT / "tools/manage_install.py"), "--stage", tmp]
            subprocess.run(args, capture_output=True, check=True)
            installed = Path(tmp) / "usr/lib/cups/filter/km215-pdftogdi"
            before = installed.read_bytes()
            second = subprocess.run(args, capture_output=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(installed.read_bytes(), before)

    def test_staging_install_rejects_symlink_parent(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            (Path(tmp) / "usr").symlink_to(other, target_is_directory=True)
            result = subprocess.run([sys.executable, str(ROOT / "tools/manage_install.py"), "--stage", tmp],
                                    capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(list(Path(other).iterdir()), [])

    def test_raster_reader_deadline_and_header_bound(self):
        readfd, writefd = os.pipe()
        with os.fdopen(readfd, "rb") as stream:
            reader = job.RasterReader(stream, time.monotonic() + 0.02)
            try:
                with self.assertRaisesRegex(ValueError, "time limit"):
                    reader.page()
            finally:
                reader.selector.close()
                os.close(writefd)

    def test_page_and_output_limits_emit_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "two.pdf"
            subprocess.run(["/usr/bin/gs", "-q", "-dSAFER", "-dBATCH", "-dNOPAUSE",
                            "-sDEVICE=pdfwrite", f"-sOutputFile={pdf}",
                            str(ROOT / "tests/fixtures/two-pages.ps")], check=True)
            for setting, value in (("MAX_PAGES", 1), ("MAX_JOB_SIZE", 100)):
                out = io.BytesIO()
                with mock.patch.object(job, setting, value):
                    with self.assertRaises(ValueError):
                        job.pdf_to_job(pdf, out)
                self.assertEqual(out.getvalue(), b"")


if __name__ == "__main__":
    unittest.main()
