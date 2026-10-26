# Installation

The source archive is the cross-distribution option. It compiles the C helper
against the local JBIG-KIT, so it does not depend on a Fedora-specific binary ABI.

## Guided installation

```sh
sh install.sh --setup --printer 192.0.2.10
```

Use your own printer IP. The installer asks before dependency installation,
before copying system files and before creating the dedicated queue. Source
compilation and tests run as your normal user. It does not print a test page.
Ensure the system CUPS service is running before queue creation; the installer
does not change service startup, firewall rules, SELinux policy or sharing.

## Dependencies if installed manually

Debian/Ubuntu/Mint:

```sh
sudo apt-get install build-essential python3 ghostscript cups libcups2-dev libjbig-dev
```

Fedora:

```sh
sudo dnf install gcc make python3 ghostscript cups cups-devel jbigkit-devel
```

Arch/Manjaro:

```sh
sudo pacman -S --needed base-devel python ghostscript cups jbigkit
```

openSUSE:

```sh
sudo zypper install gcc make python3 ghostscript cups cups-devel libjbig-devel
```

Package availability varies by distribution/version; only official enabled
repositories are used. On unsupported systems install equivalent dependencies
manually. Immutable distributions require an administrator-managed deployment.

## Build, stage, install

```sh
make test
sh install.sh --stage /absolute/new/staging-root
sudo sh install.sh --install-system
```

Filter and PPD paths come from `cups-config --serverbin/--datadir`; private
files go in `/usr/local/lib/bizhub215`. Existing targets and symlink targets
are rejected. Executables have mode 755, Python/data files mode 644.
On SELinux systems restorecon restores the normal file contexts. Do not
disable SELinux if something fails: inspect the audit log first.

The physical printer's GDI path was confirmed by printing, but the exact board
part number was not confirmed. Universal PCL/PostScript drivers did not work
for the tested configuration; this driver uses PJL plus JBIG raster data.

## Troubleshooting

- `unsupported setting`: use A4, 600 dpi, simplex, portrait, one copy;
  `print-scaling=auto-fit` is supported.
- `driver already installed`: do not overwrite an unknown installation.
  Preserve the current source/manifest, remove old files deliberately, then install.
- `cannot list CUPS queues`: start/check CUPS using your distribution's normal tools.
- No physical page: do not repeatedly resubmit the same job. Check the printer's
  screen and report firmware, OS, package version, options and job state.
- A completed CUPS job is not proof of a physical page.

## Uninstall

Check pending jobs first. The source installer leaves queues untouched:

```sh
sudo sh uninstall.sh
```

Optional deletion of the dedicated queue: `sudo lpadmin -x Konica_215_Custom`.
Never delete unrelated queues. Native packages must be removed using the same
package manager that installed them.
