Experimental Linux GDI/JBIG printing implementation, GPL-2.0-or-later.

Security and privacy update:
- CUPS identity and document title are not placed into the printer stream;
  the protocol uses the constant `USERNAME=linux`.
- PDF pages stream through bounded memory instead of accumulating raster files.
- Renderer resource limits, a document deadline, job-size checks and cancellation cleanup.
- Installed helper is encode-only; the guarded decoder stays in local tests.
- Stronger source installation checks and exclusive writes.
- Explicit licensing/provenance notes; this is not vendor legal approval.

Download a source archive, unpack it, and run as a regular user:

```sh
sh install.sh --setup --printer 192.0.2.10
```

Replace the example address with your printer address. Dependencies, system
installation and queue creation require confirmation. No test print is sent.
RPM is for Fedora 44 x86_64; DEB is for Ubuntu 24.04 amd64. Other Linux systems
should build from source against their own distribution libraries.

16 local tests pass. Compression of the hardware-confirmed single-page reference
remains identical; changing to the anonymous protocol identity has not been
physically retested. No new hardware test is claimed for this release.

Supported scope: CUPS 2.x, A4 monochrome, 600 dpi, portrait, simplex, one copy.
Input PDF and encoded job each up to 64 MiB; up to 200 pages with a 60-second
processing deadline. Performance limits may reject otherwise valid large jobs.
Multi-page framing is locally tested, not separately confirmed on two physical sheets.

SHA256SUMS covers the attached source archives and native packages. Windows
executables, private development files and test decoder binaries are not shipped
as runtime components. See docs/SECURITY.md and docs/LICENSING.md for limits.
