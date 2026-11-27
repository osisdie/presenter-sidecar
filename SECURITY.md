# Security policy

## Reporting a vulnerability

Please report security problems privately through
[GitHub security advisories](https://github.com/osisdie/presenter-sidecar/security/advisories/new)
("Report a vulnerability"). Do not open a public issue for them.

Include what you found, how to reproduce it, and the version (`CHANGELOG.md`).
You will get an answer in the advisory thread.

## Supported versions

Only the latest release receives fixes.

## Design notes

- The panel server binds to `127.0.0.1` only, checks the `Host` header (DNS rebinding) and requires
  an `X-Panel: 1` header on every POST (cross-site requests from web pages cannot add it without a
  CORS preflight, which the server never approves).
- The optional AI helper runs the Claude Code CLI read-only: only `Read`, `Grep` and `Glob`; shell,
  edit, write and web tools are disallowed; `.env*`, key files, `.git/`, `config.json` and `logs/`
  are denied in the CLI's permission settings.
- `cdp_url` must be a loopback address. A browser started with `--remote-debugging-port` can be
  fully controlled by any local process; only enable it for a browser profile used for presenting.
- `notes_files`, `pacing_file` and `content_root` are trusted paths: `config.json` is the presenter's
  own file, so `..` and absolute paths are allowed and the panel serves whatever they name (only those
  files, only to `127.0.0.1`). Do not load a `config.json` you have not read.
See the "Privacy and security" section of `README.md` for details.
