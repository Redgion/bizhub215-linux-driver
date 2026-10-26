# Changelog

## 0.3.0 — first public release

- Native C JBIG helper and Python PDF-to-GDI/JBIG CUPS filter.
- Hardware-confirmed A4 monochrome, 600 dpi, simplex printing on Fedora 44.
- KDE `print-scaling=auto-fit` compatibility.
- Full PDF handling up to 200 pages, validated locally.
- Guided source installer for apt, dnf, pacman and zypper families.
- CUPS directory detection, non-root builds, explicit installation prompts,
  safe staging, uninstall manifest, no automatic test printing.
- Portable non-empty username instead of a machine-specific name.
- Source archives, checksums, CI and native package build recipes.

The private development snapshots 0.1/0.2 were not public releases. No
historical public versions or cross-distribution hardware results are claimed.
# 0.3.1

- Stream PDF rasters instead of saving hundreds of uncompressed pages.
- Limit renderer address space, CPU, file size, descriptors, elapsed time and
  final encoded job size; kill the renderer process group on error/cancellation.
- Send the constant `linux` instead of the submitting CUPS account name.
- Remove development account names from fixtures and tests.
- Keep decoding in a separately built local test helper, never in installed packages.
- Reject unsupported JBIG headers before entering the test decoder.
- Use exclusive installation writes and reject unsafe installation sources.
- Document GPL scope, reverse-engineering provenance and remaining legal limits.

