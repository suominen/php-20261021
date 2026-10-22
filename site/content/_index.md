---
title: "PHP2Shell (CVE-2026-109618, CVE-2026-109619) — unauthenticated PHP RCE"
description: "PHP2Shell: two critical (CVSS 4.0 9.2) remote code execution flaws in PHP's request lifecycle, fixed in PHP 8.5.12, 8.4.27, 8.3.36, and 8.2.35 — upstream, Debian, pkgsrc, and NixOS patch status tracker"
layout: "single"
date: 2026-10-21
lastmod: 2026-10-22
cover:
  image: "php-20261021-tracker.png"
  alt: "PHP2Shell (CVE-2026-109618, CVE-2026-109619) — patch status tracker"
  hiddenInSingle: true
---

## Summary

| Field | Detail |
|---|---|
| CVEs | [CVE-2026-109618][ghsa-w8hw] (RCE via OOM corruption) and [CVE-2026-109619][ghsa-6wmf] (RCE via stale global state) |
| Severity | **9.2 critical** (CVSS 4.0) for both, scored by PHP |
| Impact | Unauthenticated remote code execution as the web server's PHP worker account |
| Affected | Every PHP release before 8.2.35, 8.3.36, 8.4.27, and 8.5.12 — PHP 8.1 and older are end of life: no new releases, only [minimal source backports](#php) |
| Fixed in | PHP **8.5.12**, **8.4.27**, **8.3.36**, and **8.2.35**, released 2026-10-21 |
| Exposure | Every PHP serving web requests — PHP-FPM, `mod_php`, php-cgi, FrankenPHP, LiteSpeed; risk highest on `mod_php` — see [Who is exposed](#who-is-exposed) |
| Disclosure | Details leaked on 2026-10-20, a day ahead of the scheduled release |
| KEV listed | no |
| Exploitation | Cloudflare reports early attacks; watchTowr and Huntress had seen none early on 2026-10-21. Only a screenshot of an exploit tool has been reported |
{.summary}

PHP2Shell is the name the two vulnerabilities picked up after the
leak. Both live in PHP's own request handling, below any framework or
application. CVE-2026-109618 needs nothing from the application at
all: on `mod_php`, the multipart body parsing that runs before any
script starts is enough.

> :warning: **Updating is the only complete fix.** PHP's advisories
> say so for both CVEs. The configuration changes under
> [Mitigation](#mitigation) narrow the confirmed attack paths but
> leave others open. Each branch has its own fixed release: a host on
> PHP 8.4 needs 8.4.27, not 8.5.12.

## The vulnerabilities

| Advisory | CVE | Mechanism | CVSS 4.0 | Fixed in |
|---|---|---|---|---|
| [GHSA-w8hw-w9fx-j79w][ghsa-w8hw] | CVE-2026-109618 | Out-of-memory bailout via `longjmp()` leaves request memory in an invalid state that shutdown then reads | 9.2 critical | all four |
| [GHSA-6wmf-4rv5-p3rp][ghsa-6wmf] | CVE-2026-109619 | Worker-global state still pointing into a freed request heap is used by the next request before it initialises | 9.2 critical | all four |

Both advisories credit the same four reporters (`lcfr-hax`,
`sagitzadik-wiz`, `tomash-areion`, `amyb-oai`). The fix, in the
ChangeLog as "Avoid state corruption via bailout", is one Core change
in all four releases. 8.3.36 and 8.2.35 contain nothing else. 8.5.12
and 8.4.27 also carry their branches' regular bug fixes.

### CVE-2026-109618 — OOM corruption

PHP aborts a request that runs out of memory by `longjmp()`-ing out
of whatever it was doing. Some code makes request memory reachable
before it is fully initialised, and an allocation failure at that
point leaves it invalid for request shutdown to read.

An attacker can reach the memory limit while staying inside PHP's
apparent request limits, through multipart parsing:

- a multipart body without a usable declared length, which passes the
  `post_max_size` check and keeps supplying data
- an unbounded number of headers in a multipart part, far larger in
  memory than on the wire
- empty file controls, which don't count towards `max_file_uploads`,
  with nested field names multiplying the work

### CVE-2026-109619 — stale global state

PHP keeps error, session, object, and extension state in worker
globals. A fatal error — including running out of memory, or `Maximum
execution time exceeded` — can abandon an operation before it resets
that state, and a warning during shutdown can repopulate it after it
was cleared, leaving it pointing into the request heap after it is
freed. A later request on the same worker then uses it before its own
initialisation replaces it.

The advisory confirms two such early consumers:

- **INI diagnostics before request start** — a warning or deprecation
  from per-directory settings (`.htaccess`, Apache `php_value`, or
  `PHP_VALUE` sent by a FastCGI frontend). Silencing it with
  `error_reporting`, `@`, or `display_errors` does not help.
- **Session upload progress** — enabled by default, and reached
  without the application calling `session_start()`.

On PHP 8.5, `fatal_error_backtraces` — on by default — supplies the
producer behind the confirmed `mod_php` exploit.

### Who is exposed

PHP's advisory names every installation serving web requests as at
risk, including PHP-FPM, Apache `mod_php`, php-cgi, FrankenPHP, and
LiteSpeed. What has been demonstrated differs by SAPI:

- **Apache `mod_php`** — confirmed RCE for both, CVE-2026-109618 with
  default PHP input and memory limits, before any application code
  runs. PHP rates the risk highest here.
- **PHP-FPM** — CVE-2026-109619 validated through session upload
  progress after an application-level fatal error. CVE-2026-109618 is
  susceptible by source analysis, but no complete FPM exploit has been
  shown.
- **FrankenPHP** — likely susceptible to CVE-2026-109618, as it runs
  request shutdown unconditionally like `mod_php`.
- **LiteSpeed (LSAPI)** — modelled on FPM, so CVE-2026-109618 exploits
  are likely application-specific; a conditional candidate for
  CVE-2026-109619, as it can apply environment INI values early.

## Patch status

A row is **Fixed** once its package carries its PHP branch's
2026-10-21 release or later, or a backport of the fix. *Current
version* is what the release ships today; *First fixed* is the first
build that closed both CVEs. Where a release offers several PHP
branches, the one its unversioned `php` selects is marked *default*.
Debian versions are the apt-installable value, from the
`<suite>-security` archive where it carries the package.

| Distribution | Release | Current version | First fixed | Fixed since | Status |
|---|---|---|---|---|---|
| PHP | 8.5 | `8.5.12` | `8.5.12` | 2026-10-21 | :white_check_mark: Fixed |
| PHP | 8.4 | `8.4.27` | `8.4.27` | 2026-10-21 | :white_check_mark: Fixed |
| PHP | 8.3 | `8.3.36` | `8.3.36` | 2026-10-21 | :white_check_mark: Fixed |
| PHP | 8.2 | `8.2.35` | `8.2.35` | 2026-10-21 | :white_check_mark: Fixed |
| Debian | sid — `php8.4` (default) | `8.4.26-1` | — | — | :warning: Staged — 8.4.27-1 uploaded |
| Debian | forky (testing) — `php8.4` (default) | `8.4.26-1` | — | — | :x: Vulnerable — needs 8.4.27 |
| Debian | 13 (trixie) — `php8.4` (default) | `8.4.27-1~deb13u1` | `8.4.27-1~deb13u1` | 2026-10-21 | :white_check_mark: Fixed — DSA-6574-1 |
| Debian | 12 (bookworm) — `php8.2` (default) | `8.2.35-1~deb12u1` | `8.2.35-1~deb12u1` | 2026-10-21 | :white_check_mark: Fixed — DLA-4848-1 |
| pkgsrc | `pkgsrc-current` — `php84` (default) | `php84-8.4.27` | `php84-8.4.27` | 2026-10-21 | :white_check_mark: Fixed |
| pkgsrc | `pkgsrc-current` — `php85` | `php85-8.5.12` | `php85-8.5.12` | 2026-10-21 | :white_check_mark: Fixed |
| pkgsrc | `pkgsrc-current` — `php83` | `php83-8.3.36` | `php83-8.3.36` | 2026-10-21 | :white_check_mark: Fixed |
| pkgsrc | `pkgsrc-current` — `php82` | `php82-8.2.35` | `php82-8.2.35` | 2026-10-21 | :white_check_mark: Fixed |
| pkgsrc | `pkgsrc-2026Q3` — `php84` (default) | `php84-8.4.27` | `php84-8.4.27` | 2026-10-21 | :white_check_mark: Fixed — pullup #7309 |
| pkgsrc | `pkgsrc-2026Q3` — `php85` | `php85-8.5.12` | `php85-8.5.12` | 2026-10-21 | :white_check_mark: Fixed — pullup #7310 |
| pkgsrc | `pkgsrc-2026Q3` — `php83` | `php83-8.3.36` | `php83-8.3.36` | 2026-10-21 | :white_check_mark: Fixed — pullup #7308 |
| pkgsrc | `pkgsrc-2026Q3` — `php82` | `php82-8.2.35` | `php82-8.2.35` | 2026-10-21 | :white_check_mark: Fixed — pullup #7307 |
| NixOS | `nixos-unstable` — `php85` (default) | `8.5.11` | — | — | :x: Vulnerable — needs 8.5.12 |
| NixOS | `nixos-unstable` — `php84` | `8.4.26` | — | — | :x: Vulnerable — needs 8.4.27 |
| NixOS | `nixos-unstable` — `php83` | `8.3.35` | — | — | :x: Vulnerable — needs 8.3.36 |
| NixOS | `nixos-unstable` — `php82` | `8.2.34` | — | — | :x: Vulnerable — needs 8.2.35 |
| NixOS | `nixos-unstable-small` — `php85` (default) | `8.5.12` | `8.5.12` | 2026-10-21 | :white_check_mark: Fixed |
| NixOS | `nixos-unstable-small` — `php84` | `8.4.27` | `8.4.27` | 2026-10-21 | :white_check_mark: Fixed |
| NixOS | `nixos-unstable-small` — `php83` | `8.3.36` | `8.3.36` | 2026-10-21 | :white_check_mark: Fixed |
| NixOS | `nixos-unstable-small` — `php82` | `8.2.34` | — | — | :x: Vulnerable — needs 8.2.35 |
| NixOS | `nixos-26.05` — `php84` (default) | `8.4.26` | — | — | :x: Vulnerable — needs 8.4.27 |
| NixOS | `nixos-26.05` — `php85` | `8.5.11` | — | — | :x: Vulnerable — needs 8.5.12 |
| NixOS | `nixos-26.05` — `php83` | `8.3.35` | — | — | :x: Vulnerable — needs 8.3.36 |
| NixOS | `nixos-26.05` — `php82` | `8.2.34` | — | — | :x: Vulnerable — needs 8.2.35 |
| NixOS | `nixos-26.05-small` — `php84` (default) | `8.4.27` | `8.4.27` | 2026-10-21 | :white_check_mark: Fixed |
| NixOS | `nixos-26.05-small` — `php85` | `8.5.12` | `8.5.12` | 2026-10-21 | :white_check_mark: Fixed |
| NixOS | `nixos-26.05-small` — `php83` | `8.3.36` | `8.3.36` | 2026-10-21 | :white_check_mark: Fixed |
| NixOS | `nixos-26.05-small` — `php82` | `8.2.35` | `8.2.35` | 2026-10-21 | :white_check_mark: Fixed |
| nixpkgs | `master` branch — `php85` (default) | `8.5.12` | `8.5.12` | 2026-10-21 | :white_check_mark: Fixed |
| nixpkgs | `master` branch — `php84` | `8.4.27` | `8.4.27` | 2026-10-21 | :white_check_mark: Fixed |
| nixpkgs | `master` branch — `php83` | `8.3.36` | `8.3.36` | 2026-10-21 | :white_check_mark: Fixed |
| nixpkgs | `release-26.05` branch — `php84` (default) | `8.4.27` | `8.4.27` | 2026-10-21 | :white_check_mark: Fixed |
| nixpkgs | `release-26.05` branch — `php85` | `8.5.12` | `8.5.12` | 2026-10-21 | :white_check_mark: Fixed |
| nixpkgs | `release-26.05` branch — `php83` | `8.3.36` | `8.3.36` | 2026-10-21 | :white_check_mark: Fixed |
| nixpkgs | `release-26.05` branch — `php82` | `8.2.35` | `8.2.35` | 2026-10-21 | :white_check_mark: Fixed |
| nixpkgs | `nixpkgs-unstable` — `php85` (default) | `8.5.11` | — | — | :x: Vulnerable — needs 8.5.12 |
| nixpkgs | `nixpkgs-unstable` — `php84` | `8.4.26` | — | — | :x: Vulnerable — needs 8.4.27 |
| nixpkgs | `nixpkgs-unstable` — `php83` | `8.3.35` | — | — | :x: Vulnerable — needs 8.3.36 |
| nixpkgs | `nixpkgs-unstable` — `php82` | `8.2.34` | — | — | :x: Vulnerable — needs 8.2.35 |
{.distros}

### PHP

PHP supports four branches, each with its own fixed release. 8.4 and
8.5 are in active support; 8.2 and 8.3 receive security fixes only.

PHP 8.1 and every older branch are past end of life. They are just as
vulnerable — the exploit tool shown in the leak claims every release
since 5.4.0 — and get no new releases. Given the severity, PHP
published minimal source backports for [7.4][bp-74], [8.0][bp-80],
and [8.1][bp-81] for those building from source; otherwise a host
needs a vendor that backports the fix, or a supported branch.

### Debian

Debian ships one PHP branch per release, as a versioned source
package: `php8.2` in bookworm, `php8.4` in trixie, forky, and sid. The
unversioned `php`, `php-cli`, and `php-fpm` packages come from
`php-defaults` and only pull in the branch's packages, so look at the
`php8.X-*` packages for the PHP release a host runs.

Debian's PHP maintainer normally imports each upstream point release,
security uploads to the stable suites included. Bookworm is in its LTS
period, so its PHP updates come as DLAs from the LTS team, into
`bookworm-security`.

### pkgsrc

pkgsrc (NetBSD's package collection, also used on SmartOS, macOS via
pkgin, and elsewhere) packages every PHP branch side by side as
`lang/php82` through `lang/php85`; the installed package is named
after the branch (`php84-8.4.26`). `PHP_VERSION_DEFAULT` selects the
branch PHP-dependent packages build against — 8.4 on both tracked
branches.

`pkgsrc-2026Q3` is the quarterly branch most pkgsrc hosts run; it
takes fixes from `pkgsrc-current` by pullup. An `nbN` suffix comes
from the package's `PKGREVISION`, which bumps for many reasons besides
security patches, so on its own it says nothing about this fix.

### NixOS

nixpkgs builds every branch from one expression,
`pkgs/development/interpreters/php/default.nix`, as the attributes
`php82` through `php85`. The unversioned `php` is `php85` on unstable
and `php84` on 26.05. The NixOS `services.phpfpm` module uses
`pkgs.php` unless a pool sets its own `phpPackage`.

PHP 8.2 was removed from unstable on 2026-10-21, after its last
release there: `master` and `nixos-unstable-small` no longer carry
`php82`, and `nixos-unstable` and `nixpkgs-unstable` will drop it as
they advance. A host on `php82` from unstable gets no fix and has to
move to a newer branch.

#### Flake users

A flake input like `github:NixOS/nixpkgs/nixos-unstable` resolves to
the **git branch** of that name, which the channel bot advances to
exactly the revision the channel publishes, so an input following a
channel name is answered by that channel's rows.

Two branches have no channel gating them and will carry the fix
earlier — they are listed above as `master` and `release-26.05`:

- `github:NixOS/nixpkgs/master` — the fix's first appearance anywhere
  in nixpkgs, the moment it is merged.
- `github:NixOS/nixpkgs/release-26.05` — the ungated 26.05 branch,
  ahead of the `nixos-26.05` channel by however long Hydra takes.

## Detection

Check the installed package rather than the running interpreter: a
host can carry several PHP branches, and the web server's may not be
the one on `PATH`. Both bugs are exploited through the web server's
PHP, so check that one first.

### Debian

List the PHP packages dpkg knows about, with their state and version:

```sh
dpkg-query -W -f='${db:Status-Abbrev} ${Package} ${Version}\n' 'php8*'
```

Lines starting `ii` are installed. The branch is in the package name
(`php8.4-fpm`) and the upstream PHP release is the version up to the
last `-`. Compare it with the row for your suite above.

### pkgsrc

```sh
pkg_info -e 'php8[0-9]-[0-9]*'
```

The output is `php<branch>-<version>` plus any `nb<PKGREVISION>`
suffix — for example `php84-8.4.26nb2`. Cross-reference it against
the pkgsrc rows above.

### NixOS

Query the PHP versions in the current system closure:

```sh
nix-store -q --requisites /run/current-system | grep -- '-php-[0-9]'
```

Each store path ends in the PHP version it builds (`php-8.4.26`, or
`php-8.4.26-dev` for the development output). Cross-reference against
your channel's rows above; a project built from a flake or a
`nix-shell` carries its own PHP, pinned by its own nixpkgs input.

### Which SAPI serves PHP

Apache with `mod_php` carries the highest risk, but PHP-FPM is
exposed too, so a host without `mod_php` still needs the update. On
Debian, `a2query -m` lists the enabled Apache modules; a `php8.X`
module there means `mod_php`:

```sh
a2query -m
```

## Mitigation

Upgrade to your branch's fixed release — or to a distribution package
that carries it — as soon as one is available. None of the following
is a complete fix; PHP's advisories list them as ways to narrow the
confirmed attack paths until the update is installed.

- **Disable session upload progress.** Set
  `session.upload_progress.enabled=0` administratively and restart
  every worker. It closes the confirmed session path of
  CVE-2026-109619 on both `mod_php` and FPM, and the advisory suggests
  keeping it off after updating if unused.
- **PHP 8.5: disable fatal error backtraces.** Set
  `fatal_error_backtraces=0` administratively and restart every
  worker. This removes
  the producer behind the confirmed CVE-2026-109619 RCE on `mod_php`.
- **Remove the predictable memory limit.** Setting
  `memory_limit=-1` administratively removes the controllable
  out-of-memory condition the confirmed CVE-2026-109618 exploit uses.
  Check that no pool, directory, or application setting restores a
  finite limit. Do **not** use `RLIMIT_AS` or `RLIMIT_DATA` instead —
  they make allocations fail, which triggers the vulnerable path.
- **Shrink the request limits.** Set a low `post_max_size` — PHP
  suggests 8M without file uploads, 32M with them, with
  `upload_max_filesize` below it — and reduce
  `max_input_nesting_level`. An application that takes no
  `multipart/form-data` can have the frontend reject that content
  type outright.
- **Bound requests at the frontend.** Limit decoded body size, input
  fields, multipart parts, headers, and nesting depth, including for
  requests without a usable `Content-Length`.
- **Avoid per-request INI diagnostics.** Remove obsolete or invalid
  directives from `.htaccess`, Apache `php_value`/`php_flag`, and any
  `PHP_VALUE`/`PHP_ADMIN_VALUE` a FastCGI frontend sends; prefer
  `php.ini` or FPM pool settings, which apply at startup.

"Administratively" means where applications can't override it:
`php.ini`, `php_admin_value`/`php_admin_flag` in each FPM pool or the
Apache configuration — not `ini_set()` or an FPM `.user.ini`. `pm.max_requests=1`
stops a worker from serving the second request CVE-2026-109619 needs,
at a performance cost.

A web application firewall in front of PHP — Cloudflare has deployed
managed rules — helps only if the origin accepts no traffic that
bypasses it.

## Verification log

Every verdict in the table above is backed by a checkable source. This
log records the provenance — the advisory, repository index, or git
reference that established each fact — so any row can be audited or
reproduced. Most readers never need it.

{{< details summary="Full verification log" >}}
#### Upstream

- **Releases** (via php.net's release index, the
  [PHP 8 changelog][changelog], and the announcements for
  [8.5.12][rel-8512], [8.4.27][rel-8427], [8.3.36][rel-8336], and
  [8.2.35][rel-8235]):
  - php.net's release index dates all four 2026-10-21; each
    announcement calls its release "a security release".
  - The changelog dates all four sections 22 Oct 2026, a day after the
    release index and the advisories.
  - Every release lists "Fixed GHSA-w8hw-w9fx-j79w,
    GHSA-6wmf-4rv5-p3rp (Avoid state corruption via bailout)" under
    Core.
  - 8.3.36 and 8.2.35 list nothing else; 8.5.12 and 8.4.27 also carry
    their branches' regular bug fixes.
- **GitHub advisories** (via the GitHub REST API,
  `api.github.com/repos/php/php-src/security-advisories`, since the
  advisory pages render only through JavaScript):
  - GHSA-w8hw-w9fx-j79w (CVE-2026-109618) published
    2026-10-21T13:34:25Z; GHSA-6wmf-4rv5-p3rp (CVE-2026-109619)
    published 2026-10-21T13:34:13Z.
  - Both list vulnerable `< 8.2.35`, `< 8.3.36`, `< 8.4.27`, and
    `< 8.5.12`, patched in 8.2.35, 8.3.36, 8.4.27, and 8.5.12.
  - Both score
    `CVSS:4.0/AV:N/AC:H/AT:P/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N`,
    9.2 critical; no CVSS 3.1 score.
  - Both list CWE-416, CWE-755, CWE-824, CWE-1325, and CWE-1419.
  - SAPI exposure and the configuration mitigations are as quoted
    under [Who is exposed](#who-is-exposed) and
    [Mitigation](#mitigation).
- **php.net security advisory** (via the [21 Oct news
  item][php-advisory]):
  - Names PHP-FPM, `mod_php`, php-cgi, FrankenPHP, and LiteSpeed as at
    risk, highest on `mod_php`.
  - Linux distributions and LTS vendors received the patches in
    advance.
  - Minimal source backports for 7.4, 8.0, and 8.1, as
    `PHP-<branch>-CVE-2026-109618-109619` branches in php-src.
  - Remi's repository would not have updates on 2026-10-21.
- **Advance notice** (via the [php.net news item][php-notice]):
  - Posted 2026-10-20, scheduling the release for 2026-10-21 14:00
    UTC, earlier if details became public or exploitation appeared.
- **CVE records** (via the CVE Services API, `cveawg.mitre.org`):
  - CVE-2026-109618 published 2026-10-21T13:48:34Z by the PHP CNA,
    matching its advisory's CVSS 4.0 vector and CWEs.
  - The record credits Ryan at Calif.io and Wiz as reporters and
    OpenAI as finder.
  - CVE-2026-109619 published 2026-10-21T13:54:43Z by the PHP CNA,
    matching its advisory's CVSS 4.0 vector and CWEs.
  - The CVE-2026-109619 record credits Wiz, Ryan at Calif.io, and
    OpenAI as reporters.
- **KEV**: neither CVE ID is in CISA's catalog.
- **Exploitation** (via [Sansec][sansec] and
  [SecurityWeek][securityweek]):
  - Sansec reports Cloudflare seeing early attacks from 2026-10-21
    07:43 UTC, before the release, and deploying WAF rules.
  - SecurityWeek reports watchTowr and Huntress had seen no
    exploitation in the wild, and watchTowr believes it reproduced
    CVE-2026-109618.
  - Sansec reports only a screenshot of an exploit tool named
    PHP2Shell, credited to Calif.IO, leaked with the details.

#### Distributions

- **Debian** (via `scripts/debian-versions`, reading the security
  tracker's source-package pages, `php-defaults`' `debian/rules`, and
  the package changelogs on tracker.debian.org):
  - Default branch per suite: `PHP_DEFAULT_VERSION` in the suite's
    `php-defaults` `debian/rules`.
  - Branch per suite: `php8.2` in bookworm, `php8.4` in trixie, forky,
    and sid.
  - *Current version* is each suite's apt-installable version;
    `trixie-security` and `bookworm-security` carry newer versions
    than the main archive.
  - The `trixie-security` and `bookworm-security` uploads name both
    CVEs in their changelog entry for the new upstream release.
  - sid and forky: no tracked advisory id in any changelog entry.
- **Debian security tracker** (per-CVE pages):
  - trixie fixed by DSA-6574-1 and bookworm by DLA-4848-1, both
    covering CVE-2026-109618 and CVE-2026-109619.
  - sid: `php8.4` 8.4.27-1 uploaded to unstable (Debian bug 1151516),
    first seen in the `debian` archive 2026-10-22T02:24:52Z, not yet
    in the Sources index `scripts/debian-versions` reads.
  - forky still listed vulnerable; it has not inherited the pending
    sid upload.
- **Debian fix dates** (changelog trailers on tracker.debian.org,
  cross-checked with snapshot.debian.org's `first_seen`):
  - trixie: the `8.4.27-1~deb13u1` upload, 2026-10-21; first seen in
    `debian-security` at 13:41 UTC.
  - bookworm: the `8.2.35-1~deb12u1` LTS upload, 2026-10-21; first
    seen in `debian-security` at 14:03 UTC.
- **pkgsrc** (via `scripts/pkgsrc-versions` against the local clone):
  - Versions from `lang/php/phpversion.mk`; `PHP_VERSION_DEFAULT` 84
    on both branches.
  - No tracked advisory id in any `patches/` directory on either
    branch.
  - `pkgsrc-current`: `lang/php82` … `lang/php85` updated to the
    fixed releases on 2026-10-21 (commits `61a8fd285d89`,
    `81523dc73c3b`, `626f1e402f79`, `38031f5b8cc1`).
  - `pkgsrc-2026Q3`: pullup tickets #7307 (`php82`), #7308 (`php83`),
    #7309 (`php84`), and #7310 (`php85`), committed 2026-10-21.
- **NixOS / nixpkgs** (via `scripts/nixpkgs-versions` against the
  local clone at each channel's revision pointer):
  - Versions from the `php82` … `php85` blocks of
    `pkgs/development/interpreters/php/default.nix`.
  - The default is `php85` on `master`, `nixpkgs-unstable`, and the
    unstable channels, and `php84` on `release-26.05` and the 26.05
    channels.
  - `php82` was removed from `master` on 2026-10-21, in merge
    `00e46e05` (nixpkgs#575757).
  - No tracked advisory id in `default.nix` or `generic.nix`.
  - `master`: the bump for `php83`, `php84`, and `php85` landed on
    2026-10-21 in merge `c53532a93865` (nixpkgs#576853).
  - `release-26.05`: the bump for all four branches landed on
    2026-10-21 in merge `8c259fc0dd1f` (nixpkgs#576865).
  - `nixos-unstable-small`: first shipped the fix in release
    `nixos-26.11pre1098711.c53532a93865`, 2026-10-21, which no longer
    carries `php82` (via `scripts/nixos-first-shipped`).
  - `nixos-26.05-small`: first shipped the fix in release
    `nixos-26.05.12372.8c259fc0dd1f`, 2026-10-21 (via
    `scripts/nixos-first-shipped`).
- **NixOS security tracker** ([tracker.security.nixos.org][nixos-sec])
  — a JS-rendered application, linked for readers.
{{< /details >}}

## References

| Source | URL |
|---|---|
| [GHSA-w8hw-w9fx-j79w — CVE-2026-109618][ghsa-w8hw] | <https://github.com/php/php-src/security/advisories/GHSA-w8hw-w9fx-j79w> |
| [GHSA-6wmf-4rv5-p3rp — CVE-2026-109619][ghsa-6wmf] | <https://github.com/php/php-src/security/advisories/GHSA-6wmf-4rv5-p3rp> |
| [PHP 8 ChangeLog][changelog] | <https://www.php.net/ChangeLog-8.php> |
| [PHP 8.5.12 release announcement][rel-8512] | <https://www.php.net/releases/8_5_12.php> |
| [PHP 8.4.27 release announcement][rel-8427] | <https://www.php.net/releases/8_4_27.php> |
| [PHP 8.3.36 release announcement][rel-8336] | <https://www.php.net/releases/8_3_36.php> |
| [PHP 8.2.35 release announcement][rel-8235] | <https://www.php.net/releases/8_2_35.php> |
| [php.net — Security advisory: Critical remote code execution vulnerabilities][php-advisory] | <https://www.php.net/archive/2026.php#2026-10-21-5> |
| [php.net — Upcoming Critical PHP Security Release][php-notice] | <https://www.php.net/archive/2026.php#2026-10-20-1> |
| [PHP 7.4 source backport][bp-74] | <https://github.com/php/php-src/tree/PHP-7.4-CVE-2026-109618-109619> |
| [PHP 8.0 source backport][bp-80] | <https://github.com/php/php-src/tree/PHP-8.0-CVE-2026-109618-109619> |
| [PHP 8.1 source backport][bp-81] | <https://github.com/php/php-src/tree/PHP-8.1-CVE-2026-109618-109619> |
| [php-src security advisories][ghsa-index] | <https://github.com/php/php-src/security/advisories> |
| [Sansec — Critical PHP RCE: CVE-2026-109618 and CVE-2026-109619][sansec] | <https://sansec.io/research/php2shell> |
| [SecurityWeek — PHP2Shell: Mass Exploitation Looms][securityweek] | <https://www.securityweek.com/php2shell-mass-exploitation-looms-for-leaked-critical-php-flaws/> |
| [Debian security tracker — `php8.4`][debian-php84] | <https://security-tracker.debian.org/tracker/source-package/php8.4> |
| [Debian security tracker — `php8.2`][debian-php82] | <https://security-tracker.debian.org/tracker/source-package/php8.2> |
| [pkgsrc — `lang/php/phpversion.mk` (GitHub mirror)][pkgsrc-phpversion] | <https://github.com/NetBSD/pkgsrc/blob/trunk/lang/php/phpversion.mk> |
| [nixpkgs — PHP expressions][nixpkgs-php] | <https://github.com/NixOS/nixpkgs/blob/master/pkgs/development/interpreters/php/default.nix> |
| [NixOS security tracker][nixos-sec] | <https://tracker.security.nixos.org/> |
{.references}

[ghsa-w8hw]:          https://github.com/php/php-src/security/advisories/GHSA-w8hw-w9fx-j79w
[ghsa-6wmf]:          https://github.com/php/php-src/security/advisories/GHSA-6wmf-4rv5-p3rp
[changelog]:          https://www.php.net/ChangeLog-8.php
[rel-8512]:           https://www.php.net/releases/8_5_12.php
[rel-8427]:           https://www.php.net/releases/8_4_27.php
[rel-8336]:           https://www.php.net/releases/8_3_36.php
[rel-8235]:           https://www.php.net/releases/8_2_35.php
[php-advisory]:       https://www.php.net/archive/2026.php#2026-10-21-5
[php-notice]:         https://www.php.net/archive/2026.php#2026-10-20-1
[bp-74]:              https://github.com/php/php-src/tree/PHP-7.4-CVE-2026-109618-109619
[bp-80]:              https://github.com/php/php-src/tree/PHP-8.0-CVE-2026-109618-109619
[bp-81]:              https://github.com/php/php-src/tree/PHP-8.1-CVE-2026-109618-109619
[ghsa-index]:         https://github.com/php/php-src/security/advisories
[sansec]:             https://sansec.io/research/php2shell
[securityweek]:       https://www.securityweek.com/php2shell-mass-exploitation-looms-for-leaked-critical-php-flaws/
[debian-php84]:       https://security-tracker.debian.org/tracker/source-package/php8.4
[debian-php82]:       https://security-tracker.debian.org/tracker/source-package/php8.2
[pkgsrc-phpversion]:  https://github.com/NetBSD/pkgsrc/blob/trunk/lang/php/phpversion.mk
[nixpkgs-php]:        https://github.com/NixOS/nixpkgs/blob/master/pkgs/development/interpreters/php/default.nix
[nixos-sec]:          https://tracker.security.nixos.org/
