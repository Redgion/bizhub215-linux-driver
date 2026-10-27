Native network scanning for Konica Minolta bizhub 215, plus the existing
GDI/JBIG CUPS printing filter. No Windows DLLs or Wine are required.

Verified on Fedora 44 KDE: two real flatbed A4 scans at 150 dpi, Gray and RGB,
and device/options visible in Skanpage. Images and device logs are private.
A3, 300 dpi, ADF, duplex and USB scanning are not hardware verified.

Download the source archive, unpack, and run as your regular desktop user:

```sh
sh install.sh --setup-scanner --printer 192.0.2.10
```

Replace the example address with your MFP IPv4 address. Install a C compiler,
make, patch, pkg-config, SANE CLI (scanimage), and Skanpage or simple-scan from
your distribution first. Setup downloads SHA-256-pinned official SANE source,
builds an isolated backend, and offers a private user profile/menu shortcut.
No CUPS changes or automatic scans occur. See docs/SCANNER.md.

For printing, use `sh install.sh --setup --printer 192.0.2.10` separately.
Keep an existing working printer installation if only adding the scanner.
RPM packages target Fedora 44 x86_64; DEB targets Ubuntu 24.04 amd64. Other
systems should build from source against their own distribution libraries.
A successful CUPS job is not evidence of physical output.

Security checks reject invalid/oversized image dimensions and inconsistent
image-block lengths, bound image allocation, and handle failed socket writes.
Native printer/scanner services lack transport encryption; use a trusted LAN.
No telemetry or uploaded documents; no private scan fixtures or vendor binaries
are distributed. GPL licensing/provenance notices remain in LICENSE and NOTICE.
Checksums cover all attached payloads; checksums are not an independent signature.
Passing tests is not a guarantee that the code has no vulnerabilities.
