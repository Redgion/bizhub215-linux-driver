# Protocol notes

The public implementation was developed by static analysis of an original
Windows GDI driver for bizhub 195/215/235 (ONG8 family, 2.1.0.0), then validated
by a physical A4 print and normal KDE/CUPS printing on Fedora 44.
Vendor binaries are not distributed or loaded by this project.

The stream consists of a PJL document envelope, per-page PJL settings, and
length-delimited JBIG data. `DRIVERTYPE=GDI`, `COMPRESS=JBIG`, a non-empty
`USERNAME`, `PAGESTATUS=START/END`, and `IMAGELEN=N` delimit the stream.
Read exactly N binary bytes after each IMAGELEN command: printable command-like
bytes can occur inside compressed data. Buffers are at most 32768 bytes.

JBIG BIH: DL=0, D=0, P=1, MX=0, MY=0, order=3, options=0x48
(LRLTWO | TPBON). Width, height and L0 are big-endian; L0 equals page height.
The current raster is 4960x7016 at 600 dpi, using the successful A4 prototype.
JBIG-KIT supplies the native Linux codec. Local encode/decode tests verify
pixel-exact reconstruction; they alone do not prove hardware compatibility.

Private development's empty username produced no page; a non-empty username
then printed correctly. This is an observed two-trial difference, not a
controlled repeated experiment that excludes all other factors. The public
filter uses the constant `linux`; it does not transmit the CUPS account name.

The first page and KDE/CUPS use were physically confirmed. Multi-page framing
is tested locally only. Other models, USB, duplex, scanning, alternate media,
exact hardware margins and other firmware revisions are not claimed verified.
