# Native network scanning for bizhub 215

Hardware confirmed: two real flatbed A4 scans at 150 dpi, Gray and Color,
saved as valid PNG images (1240×1754). Skanpage opened the configured device;
the user confirmed that the scanner and settings were visible. This is separate
evidence from printer/CUPS success. The images and raw logs remain private.

## Why a native backend

The device advertises WSD and reports capabilities to sane-airscan, but the
tested firmware returned an empty MTOM image attachment and an overstated HTTP
Content-Length. Neither Gray/RGB JPEG nor a full A4 TIFF ticket produced image
data. No scanner motion was observed. Merely listing that WSD service is not
working scan support.

The native service uses TCP 4567 and the same 03/04 command family as SANE's
open magicolor backend. The bizhub profile uses model ID 0x20cb with big-endian
identification, a 13-byte settings block and a five-byte length/status header
before each image block. Image dimensions are bounded before multiplication;
short or failed block acknowledgements are rejected. Row padding returned by
the device is removed before exposing image pixels to the frontend.

Our patch extends the GPL SANE implementation; it does not contain translated
Windows functions or vendor binaries. Limited static inspection of the supplied
driver was used to identify model/protocol differences. This is not described
as a clean-room process. Existing provenance/legal limits still apply.

Primary open-source references:
- [SANE magicolor source, version 1.4.0](https://gitlab.com/sane-project/backends/-/blob/1.4.0/backend/magicolor.c).
- [Backend author's protocol documentation](https://wiki.kainhofer.com/hardware/magicolor_scan).
- [Official SANE release](https://gitlab.com/sane-project/backends/-/releases/1.4.0).

## Private setup

Install your distribution's C compiler, make, patch, pkg-config, SANE CLI
(`scanimage`) and Skanpage or simple-scan. The network-only build does not
require scanner USB or SNMP development libraries.

```sh
sh install.sh --setup-scanner --printer 192.0.2.10
```

Replace the example with your device's IPv4 address. Run as a normal user,
not with sudo. The guided mode asks before building and before creating files.
It stores source/build files in `~/.cache/bizhub215-scanner` by default and
does not install or start a daemon. The source archive SHA-256 is pinned:
`f99205c903dfe2fb8990f0c531232c9a00ec9c2c66ac7cb0ce50b4af9f407a72`.

Advanced offline build from an already downloaded official archive:

```sh
python3 tools/build_scanner.py --build --archive sane-backends-1.4.0.tar.gz
python3 tools/km215_scan.py setup --printer 192.0.2.10
```

Open **bizhub 215 Scanner** / **Сканер bizhub 215** in your application menu.
The shortcut supplies the private SANE configuration and backend search path;
opening an unrelated normal Skanpage shortcut does not necessarily use them.
The default is flatbed, A4, Gray, 150 dpi. Start scans yourself with the app.

User files:
- `~/.config/bizhub215-scanner`: private address/profile, mode 700/600.
- `~/.local/lib/bizhub215-scanner`: isolated backend and launcher.
- `~/.local/share/applications/bizhub215-scanner.desktop`: menu shortcut.

No CUPS queues, default printer, system scanner libraries, firewall rules,
network shares or MFP settings are changed. The GUI chooses the output folder;
no images are uploaded. Native TCP scanning has no transport encryption, so use
a trusted network. Debug traces can contain image data and private identifiers;
never post them without review. The source archive excludes builds and traces.

## Limits and removal

Only flatbed A4/150 dpi Gray and Color are physically verified on the tested
device/firmware. The profile exposes 300 dpi and A3 geometry, but those have
not been hardware verified. ADF, duplex, USB and other models are not enabled
or claimed supported. The profile intentionally has no USB/automatic discovery.

Close the scanner app before removing the private profile. Remove only the
three named user paths above after reviewing their contents; the cache/source
may be kept for reproducibility. Do not remove system SANE packages or other
scanner configurations. Images saved through the GUI are separate and should
be retained. Existing files are not overwritten by setup.

Scanner support is included from v0.4.0. Print setup and scanner setup are
independent; an existing working printer installation can be kept.

Native packages include the scanner setup scripts and source patch, not a
precompiled SANE library. After installing an RPM/DEB, run as your desktop user:

```sh
python3 /usr/lib/bizhub215/tools/manage_install.py --setup-scanner --printer 192.0.2.10
```

The downloaded, patched SANE source is retained in the user's build cache,
including its original GPL notices. No vendor driver files are downloaded.
