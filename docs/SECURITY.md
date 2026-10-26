# Security and privacy

Experimental CUPS 2.x filter. Keep CUPS, Ghostscript and JBIG-KIT updated through
your distribution. Passing tests is not a security certification.

The filter sends `USERNAME=linux`. It ignores the submitting account and title
when constructing the device stream. No telemetry, document upload, automatic
test print or background updater is implemented. CUPS and the printer keep their
own metadata/logs; PDF page content itself may contain personal information.
RAW TCP 9100 has no transport encryption: use a trusted network.

PDF input and encoded output each have a 64 MiB limit, with up to 200 pages
and a 60-second document-processing budget. Rasters are consumed one at a time
from a pipe, not accumulated on disk. The renderer has a 512 MiB address-space
limit, 45-second CPU limit, 64 MiB per-file limit and 64-descriptor limit.
Renderer stderr is discarded rather than accumulated without bounds.
On exit, error or cancellation the renderer process group is killed and reaped.
No output reaches the backend until the whole document has been encoded.
These per-process limits do not replace an OS sandbox or an administrator's
aggregate quotas across concurrent jobs and renderer internal temporary files.

The installed helper is encode-only. `make test` builds a separate test decoder
that validates the supported single-plane BIH before initializing JBIG-KIT,
and enforces CPU/memory limits. Never redistribute that test executable across
JBIG-KIT ABI changes without recompilation. JBIG-KIT 2.2 changed the decoder
state ABI; do not manually replace system shared libraries.

Source installation executes code from the unpacked source directory with
administrator permission. Use a verified archive in a directory owned by you
and protected from other users. Sources must be regular files and not writable
by other users; symlink sources and existing destination files are rejected.
This is not protection against a malicious administrator or a compromised
source owner. The installer does not manage upgrades or send print jobs.

## Publishing without private machine data

`python3 tools/check_public.py` scans the release allowlist for private paths,
private addresses, unexpected email addresses and credential-like strings.
Optional private terms can be passed in `KM215_PRIVATE_TERMS` (newline separated)
without committing those terms. Review fixtures, package metadata, commit author
and committer emails, tags, releases, CI logs/artifacts and screenshots as well.
Repository URLs intentionally identify the public hosting account; this is not
anonymous hosting. Third-party license notices must not be stripped for privacy.

Use a GitHub noreply email for future commits, including API-created commits.
Rewriting branches/tags cannot revoke old downloads, clones, forks or cached
commit URLs. [GitHub documents these limits](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).
