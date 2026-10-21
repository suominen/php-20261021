# PHP2Shell (CVE-2026-109618, CVE-2026-109619) Tracking — Claude Code Context

This repository contains a living tracking document for **PHP2Shell**,
two critical remote code execution vulnerabilities in PHP's request
lifecycle, fixed by the PHP security releases of **2026-10-21**:
**8.5.12, 8.4.27, 8.3.36, and 8.2.35**, one per supported branch.

| CVE | Advisory | Title | CVSS 4.0 |
|---|---|---|---|
| CVE-2026-109618 | GHSA-w8hw-w9fx-j79w | RCE via OOM corruption | 9.2 critical |
| CVE-2026-109619 | GHSA-6wmf-4rv5-p3rp | RCE via stale global state | 9.2 critical |

Both are vulnerable `< 8.2.35`, `< 8.3.36`, `< 8.4.27`, `< 8.5.12`,
and fixed by one Core change ("Avoid state corruption via bailout").
8.1 and older are end of life: just as vulnerable, with no new
releases — only minimal source backports for 7.4, 8.0, and 8.1 as
php-src branches — and never given rows.

- **Advisories:** <https://github.com/php/php-src/security/advisories>.
  The pages are JS-rendered; read them through the REST API instead:
  `https://api.github.com/repos/php/php-src/security-advisories/<GHSA-id>`.
  They are the fact source for versions, scores, SAPI exposure, and
  the configuration mitigations.
- **ChangeLog:** <https://www.php.net/ChangeLog-8.php> (sections
  `#8.5.12`, `#8.4.27`, `#8.3.36`, `#8.2.35`). It dates the releases
  22 Oct 2026, a day after php.net's release index and the advisories;
  the tracker uses 2026-10-21.
- **php.net security advisory:**
  <https://www.php.net/archive/2026.php#2026-10-21-5> — who is at risk
  (every SAPI serving web requests, highest on `mod_php`), the EOL
  source backports, and php.net's own mitigation wording.
- **CVE records:** at seed CVE-2026-109618 was published by the PHP CNA
  (matching its advisory) and CVE-2026-109619 still 404'd in the CVE
  Services API. The GHSA API stays the fact source for versions.
- **Disclosure:** the details leaked on 2026-10-20, a day before the
  scheduled release; PHP published at 13:34 UTC on 2026-10-21, ahead
  of its 14:00 UTC schedule. Cloudflare reported early attacks before
  the release (via Sansec); watchTowr and Huntress had seen none (via
  SecurityWeek). Only a screenshot of an exploit tool has been
  reported. Distributions and LTS vendors received the patches in
  advance (per php.net), so distro fixes may land quickly. Don't claim
  more than a source does, and update the Summary's *Exploitation* and *KEV
  listed* rows when a source moves.

The ChangeLog lists the two as one fix, and every fixed release carries
both. The ids the lookup helpers search for are listed once in
`scripts/tracked-ids`.

The rendered site is published at <https://kimmo.cloud/php-20261021/>.

This tracker was cloned from the archived PHP 2026-09-24 tracker
(`~/src/php-20260924`), keeping its PHP-shaped lookup helpers, and
moved to the template's merged *Patch status* layout (see below).

## Your task

Keep `site/content/_index.md` (the canonical tracker) up to date as the
tracked distributions pick up PHP 8.5.12 / 8.4.27 / 8.3.36 / 8.2.35 or
backport the fix.

**In an interactive session**, rebuild with `make build` and publish
with `make dist` — publishing is externally visible, so ask first.
**In the scheduled headless run**, do neither: edit and commit onto the
`auto-update` branch and stop. `make` is deliberately absent from that
run's allowlist, and the publish happens later, from a human-reviewed
merge.

A scheduled background agent runs against this repo to refresh the
tracker on its own. If you find the file has been edited since you
last looked, that's likely why — re-read before assuming stale state.

To retire (archive) this tracker — when every tracked distribution has
shipped a fix, or the bug is otherwise no longer worth active tracking —
follow `~/src/cve-tracker-template/LIFECYCLE.md` § "Retiring a tracker".

## Repo layout

```
.
├── site/                                        # Hugo project
│   ├── content/_index.md                        # the tracker — single source of truth
│   ├── hugo.toml                                # config (subpath baseURL — don't break)
│   ├── assets/css/extended/custom.css           # CSS overrides (PaperMod extension point)
│   ├── assets/php-20261021-tracker.svg          # social-banner source (rasterised by `make banner`)
│   ├── static/php-20261021-tracker.png          # rendered OpenGraph banner (committed)
│   ├── layouts/partials/post_meta.html          # overrides PaperMod: adds labels + lastmod
│   ├── layouts/partials/extend_footer.html      # client-side table grouping + status tagging + code-copy
│   ├── layouts/shortcodes/details.html          # collapsible-section shortcode (verification log)
│   └── go.mod, go.sum                           # Hugo Modules — pulls PaperMod theme
├── scripts/                                     # auto-update agent: prompt + driver + lookups
│   ├── auto-update                              # wrapper invoked by the systemd timer
│   ├── auto-update-prompt.txt                   # prompt fed to headless Claude
│   ├── debian-versions                          # Debian: branch per suite + PHP release from the changelog
│   ├── nixpkgs-versions                         # nixpkgs: php82..php85 per channel/branch
│   ├── pkgsrc-versions                          # pkgsrc: lang/php82..85 identifiers per branch
│   ├── tracked-ids                              # the advisory/CVE ids the helpers search for
│   ├── nixos-first-shipped                      # dates a channel's flip (see below)
│   ├── alas-cve                                 # kernel-tracker helper; unused here, carried from the template
│   └── check-shape                              # prose and log size check (`make check`)
├── tests/                                       # helper tests (`make check`)
├── systemd/                                     # user-level timer + service units
│   ├── php-20261021-tracker-update.service      # runs scripts/auto-update
│   └── php-20261021-tracker-update.timer        # twice daily, 05:50 and 17:50
├── flake.nix, .envrc                            # Nix dev shell: hugo + go + git + resvg + curl
├── Makefile                                     # `make build`, `make dist`, `make banner`, `make check`
├── LICENSE                                      # CC BY 4.0
├── README.md                                    # user-facing project README
├── WEBSITE.md                                   # publication plan / decisions log
└── CLAUDE.md                                    # this file
```

## The tracker file (`site/content/_index.md`) — important constraints

- It has Hugo front-matter with these required fields: `title`,
  `description`, `layout: "single"`, `date` (published), `lastmod` (last
  updated). Keep all five; the rendering depends on them.
- There is no H1 in the body — Hugo emits the title from front-matter
  via PaperMod's single-post layout. Don't add an H1 back.
- The TOC is generated by PaperMod's auto-TOC (`ShowToc = true` +
  `UseHugoToc = true` in `hugo.toml`). Don't add a manual TOC.
- The "Last updated" date lives in the `lastmod` front-matter field.
  Bump it on every content edit; leave it alone on a no-op run.
- The `cover:` front-matter block points at `php-20261021-tracker.png`
  and feeds the OpenGraph / Twitter / RSS social image. Keep it;
  `hiddenInSingle: true` keeps the image out of the rendered page body.
- **The tracker is for its human readers, not for you.** Write every
  section for the operator deciding whether their PHP is exposed —
  which SAPIs are exposed, per-distro status, what to do. Keep
  out anything that only explains how the tracker is *built*:
  row-inclusion policy, verdict-axis or column mechanics, and tracking
  methodology. Those live here in `CLAUDE.md`. State the
  reader-relevant *fact*, never the policy behind it.
- **Per-distro `###` prose: shape and budget.** Open a section with one
  or two sentences; put anything enumerable (advisories, kernel series,
  streams, flake refs) in a bullet list; give every other idea its own
  short paragraph — none longer than about eight rendered lines. Before
  adding a sentence, check that it says something no table cell says:
  never restate a row's version, date, verdict, or *Status* note.
  Provenance (commit SHAs, "confirmed via …", mirror lag) belongs in the
  verification log. **When a row flips, rewrite the section to describe
  the current state** — never append "now fixed" / "has now" sentences to
  the old text. The section should read as if written fresh today.
- **Verification log: one fact per sub-bullet.** Log entries are one
  top-level bullet per source, with a terse bold lead naming the source
  or method — at most four lines, no facts — followed by one fact per
  nested sub-bullet of at most six lines. When a run learns something
  new, add or edit a sub-bullet; never extend the lead or append a
  clause to a neighbouring sub-bullet. Name each pairing explicitly
  rather than relying on the order of an `A / B` list.
  `scripts/check-shape` (run by `make check`) enforces these limits and
  the eight-line limit on per-distro paragraphs and bullets. The
  auto-update wrapper runs it too, on every run in which the worktree's
  page differs from `origin/main`, and fails the unit when the page is
  over budget.
- **One command per fenced code block, no inline comments.** Each `sh`
  fence holds a single command with nothing after it on the line, so
  PaperMod's copy button yields something runnable. Clarifying notes go
  in the prose *before* the block.

## Update workflow

1. Edit `site/content/_index.md` (or any file under `site/`).
2. Optional: `cd site && hugo server` for a local live preview at
   <http://localhost:1313/php-20261021/>.
3. `make build` — emits to `site/public/` (gitignored).
4. `make dist` — runs `make build`, then rsyncs `site/public/` with
   `--delete` to `haig:/php-20261021/`, which the server's restricted
   rsync resolves to
   `~/.www/sites/kimmo.cloud/htdocs/php-20261021/`. The short form in
   the `Makefile` is not a typo; don't "fix" it to the full path.
   Publishing is externally visible — in an interactive session ask
   before running it, and never run it from the headless job.

`make check` runs the helper tests under `tests/`; run it after any
change to `scripts/`.

## Social banner

The OpenGraph / social-preview image is **generated**, not hand-edited:

- Source: `site/assets/php-20261021-tracker.svg` (a 1200×630 SVG — the
  standard OG size). Edit this.
- Output: `site/static/php-20261021-tracker.png`, produced by
  `make banner` (which runs `resvg`). Hugo copies it from `static/`
  into `public/` and PaperMod references it via the `cover:`
  front-matter.

The PNG is committed so `make build` / `make dist` never need a
rasteriser. Run `make banner` only after editing the SVG, then commit
the regenerated PNG.

`make banner` needs `resvg` and the **Roboto** and **Liberation Mono**
fonts. The Nix flake provides `resvg`; on Debian, `apt install
fonts-roboto fonts-liberation` provides the fonts. resvg's `Fallback
from Roboto` warnings mean the SVG asked for something the Roboto faces
can't supply — only weights Roboto ships (400/500/700/900, *not* 800),
and only glyphs it covers (plain Latin text; no arrows or other
symbols — draw those as SVG `<path>`/`<polygon>`).

## What flips a verdict — both CVEs, and only that

A row's verdict is one question: does this PHP build carry the fix for
**both** CVE-2026-109618 and CVE-2026-109619? Every row's PHP branch is
affected by both, so a row is Fixed only when both fixes are in; a
backport of one but not the other leaves it `:x: Vulnerable`, with a
Status note naming the one still missing (`Vulnerable —
CVE-2026-109619 unpatched`).

The threshold is the fixed release of **the row's own branch**:
**8.2.35**, **8.3.36**, **8.4.27**, or **8.5.12**. The thresholds vary
row by row, so a vulnerable row's Status note names its threshold
(`Vulnerable — needs 8.4.27`) whenever no fix has arrived at all.

How to recognise a fix, by source:

- **A release at or past the branch's threshold.** nixpkgs and pkgsrc
  build pristine upstream tarballs, and Debian normally imports each
  upstream point release, so the version is the whole verdict —
  nothing needs to name a CVE.
- **A distro backport.** A changelog entry or patch naming either CVE
  or GHSA id (the helpers report the ids from `scripts/tracked-ids`
  they find), or the Debian security tracker's per-CVE pages once they
  exist. A Debian LTS upload may backport onto an older release.

Exposure — which SAPI serves PHP (`mod_php`, FPM, FrankenPHP, LSAPI),
whether session upload progress is on, `memory_limit`,
`fatal_error_backtraces` — is reader guidance for the Summary, the
*Who is exposed* subsection, and Mitigation. It is **never** a column
or a `:warning: Mitigated` verdict: no distro ships a default that
removes the bug, and PHP's advisories call every configuration change
incomplete.

The combined *Patch status* table is the **single source** for every
row's versions, dates, and status — upstream and distros alike.
Columns: `Distribution | Release | Current version | First fixed |
Fixed since | Status`, with `{.distros}` on the line **immediately
after** the table. Upstream PHP is the **first** "distribution",
labelled `PHP`, one row per supported branch (`8.5`, then descending);
its prose lives in the `### PHP` subsection. Distribution rows are
**one per (release, PHP branch) pair**, the branch named in the
*Release* cell after an em dash, with the release's default branch
marked `(default)`: `` `nixos-unstable` — `php85` (default) ``,
`` 13 (trixie) — `php8.4` (default) ``. Do not split the table per
branch or per ecosystem, and do not add a column per CVE.

The version cells hold versions only, in the form the distribution
uses:

- **PHP:** the upstream release, `8.4.27`.
- **Debian:** the source package version, `8.4.26-1~deb13u1` (the
  source name is in the *Release* cell).
- **pkgsrc:** the identifier `pkg_info -e` prints, `php84-8.4.26nb2`.
- **NixOS / nixpkgs:** the attribute's PHP version, `8.4.26`.

The verdict lives in *Status* as the emoji **plus a one-word verdict**
and an optional short note after an em dash; longer caveats go in the
`###` prose.

### When a distribution changes branch

Distributions move to newer PHP branches over the tracker's life —
sid's `php-defaults` may switch to 8.5, a quarterly pkgsrc branch or a
nixpkgs revision may drop 8.2 (nixpkgs `master` already has, see the
NixOS recipe). The helpers report every branch they find and which one
is the default, so watch for:

- **A new branch in a tracked release** (e.g. `php8.5` migrating into
  sid): add a row for it within that release, judged against its own
  branch's fixed release, with a verification-log sub-bullet saying
  when it appeared. Pre-release branches (`php86`, 8.6.0RCs) are not
  supported releases and get no row.
- **The default moving** (`php-defaults`, nixpkgs' `php = …`,
  pkgsrc's `PHP_VERSION_DEFAULT`): move the `(default)` marker and
  reorder the release's rows so the default comes first. The rows'
  verdicts don't change.
- **A branch leaving a release** (the helper prints `absent`, or a
  Debian suite stops listing the source): keep the row, frozen at its
  final verdict and *Current version*, and say in the prose that the
  release no longer carries that branch. Remove it only if it was
  never fixed *and* the user agrees.

### Row order inside the table

Rows sharing a **Distribution** value must be **contiguous**.
`layouts/partials/extend_footer.html` renders each consecutive run as
one group heading row, so a row inserted between two `nixpkgs` rows
renders the label twice and breaks the grouping.

Group order: PHP, Debian, pkgsrc, NixOS, nixpkgs. Within a group:

- **PHP:** `8.5`, `8.4`, `8.3`, `8.2`.
- **Debian:** sid → forky → 13 (trixie) → 12 (bookworm).
- **pkgsrc:** `pkgsrc-current` first, then the quarterly branches
  **descending**.
- **NixOS:** channels paired with their `-small` gate
  (`nixos-unstable`, `nixos-unstable-small`, `nixos-26.05`,
  `nixos-26.05-small`).
- **nixpkgs:** `master` branch, then `release-26.05` branch, then
  `nixpkgs-unstable`.

Within each release or channel: the default branch first, then the
other branches **descending** (8.5, 8.3, 8.2 under a default of 8.4).
The nixpkgs group reads as the fix flowing downstream, so *Fixed
since* should come out non-decreasing there. The NixOS pairs are a
deliberate exception to date order: the `-small` gate usually leads
its sibling by a day or two. Don't "fix" that.

## Routine run scope — live Current version, sticky verdict columns

The **Current version** column is **live**: refresh it for **every**
row on every run — upstream point releases and distro package versions
alike — and record any movement. A Current-version bump alone is a
real content change: commit it and bump `lastmod`. The **verdict
columns are sticky**: *First fixed*, *Fixed since*, and *Status*
change **only** when a row actually flips (see *What flips a
verdict*). A version bump that does not carry the fix moves the
*Current version* cell and **nothing else** (a still-vulnerable row's
`needs …` note stays, since the threshold does not move).

**Live versions appear only in the *Patch status* table.** Never
repeat a row's *Current version* value in the `###` prose or the
verification log. Prose and log name branches (`the 8.4 branch`) and
sticky facts (first-fixed builds, ship/migration dates) only; a log
entry records the *source and method* for a live value (e.g.
"*Current version* from `scripts/debian-versions`"), never the value
itself. A sticky fact that happens to equal today's live value stays
— it is recorded for the event, not refreshed.

**Never record NixOS channel git-revisions** (the
`channels.nixos.org/<channel>/git-revision` pins) in the tracker — they
advance on nearly every run.

## Conventions for status entries

A *Status* cell is the emoji plus its one-word verdict, optionally
followed by an em dash and a short note. A note must add information
the row's other columns do not: don't restate the verdict (`Vulnerable
— no fix yet` just repeats `Vulnerable`) or the version already shown.
Keep a note only when it adds something — the threshold a row needs
(`needs 8.4.27`), the CVE a partial backport still lacks, an advisory
(`DSA-…`, `DLA-…`) or pkgsrc pull-up ticket. The verdicts:

- `:white_check_mark: Fixed` — the build carries both fixes
  (confirmed, not merely announced): set *First fixed* to the first
  fixed build and set *Fixed since*.
- `:warning: Staged` — the fix is committed but not yet in the
  user-facing channel. For example, a Debian upload accepted into
  unstable that the archive does not carry yet (the security tracker
  already names it as the fixed version), or a pkgsrc pull-up
  requested but not yet committed to the quarterly branch. Staged is
  **not** a fix — *First fixed* and *Fixed since* stay `—`, and the
  prose or log names what is staged where.
- `:x: Vulnerable` — at least one of the two fixes is missing from the
  build.
- `:grey_question: Unverified` — not yet verified.

There is no `:warning: Mitigated` and no `:heavy_minus_sign: Not
affected`: every supported branch is affected, and every mitigation is
an operator configuration change.

- The table is the single source for its rows' columns. Per-distro
  prose is for notes that don't fit a table — don't restate a row's
  columns there, and don't add a parallel table that duplicates it.
- A value column holds the value, not a verdict word — don't write
  "fixed" / "vulnerable" / "patched" in a version cell.

### "First fixed" and "Fixed since" columns

Both are **sticky**, set when a row flips to fixed, and stay `—` while
the row is vulnerable, staged, or unverified. *First fixed* is the
first release or package build carrying both fixes — the release
itself for the `PHP` rows. *Fixed since* is the date it first held
(see *"Fixed since" is derived, never "today"* below). Only touch
either if the verdict flips again or the recorded first-fixed build
turns out to have been wrong.

### Verification log

Update the `## Verification log` section in place — edit the relevant
`#### Upstream` / `#### Distributions` sub-bullet rather than appending
a new line per re-check. The log carries no dates of its own — the
`lastmod` front-matter is the document's only recency marker; don't
write verification dates inline. Method/source attribution without a
date is fine (e.g. `(via scripts/debian-versions)`).

The log records **facts**, not run outcomes. Never write "no change",
"unchanged from prior run", or similar prose anywhere in the tracker —
an entry that is still accurate reports that by staying untouched.

## "Fixed since" is derived, never "today"

A row's *Fixed since* is the date the fix **actually became available**
in that release, derived from the source that shipped it. It is not the
date the agent noticed, and not the date of the run.

| Ecosystem | Derive from |
|---|---|
| PHP | the release date in php.net's release index (`https://www.php.net/releases/?json&version=8.4`); the ChangeLog's section dates can differ by a day |
| Debian | sid: the changelog entry of the fixing upload, or the fixed version's `first_seen` in <https://snapshot.debian.org/>; forky: the testing-migration date (see the Debian recipe); stable: the DSA/DLA or point-release date |
| pkgsrc | the commit date of the `lang/phpXY: update to …` commit (or backport patch) on that branch — see the pkgsrc recipe |
| NixOS / nixpkgs | `scripts/nixos-first-shipped` for channels; the date the fix landed on the branch (its first-parent merge) for the `master` / `release-26.05` branch rows |

For a row fixed by a backport of one CVE followed later by the other,
the date is the one on which the **second** fix arrived.

Once set, the date is **sticky**. Use `—` while a row is vulnerable,
staged, or unverified. If a date genuinely cannot be derived, record
the first-observation date and say so in the verification log.

## Dating a NixOS channel flip — `scripts/nixos-first-shipped`

A channel's git-revision pointer only says where the channel is *now*.
`nixos-first-shipped` lists the channel's published releases, finds
the earliest whose revision contains a given nixpkgs commit, and
reports that release's publication date.

All four PHP branches live in one file, so one commit usually bumps
several of them. **Pick the commit by subject, not by recency**:

```sh
git -C ~/src/nixos/nixpkgs log --format='%H %cd %s' --date=short origin/master -- pkgs/development/interpreters/php/default.nix
```

The wanted commit is the one whose subject names the bump for the
row's branch (`php84: 8.4.26 -> 8.4.27`, or a combined
`php: 8.2.35, 8.3.36, 8.4.27, 8.5.12`); each PHP branch can have its
own commit, and each nixpkgs branch has its own SHA. Then date each
channel:

```sh
~/src/php-20261021/scripts/nixos-first-shipped nixos-unstable <commit>
```

| Channels | Branch to read the SHA from |
|---|---|
| `nixos-unstable`, `nixos-unstable-small`, `nixpkgs-unstable` | `origin/master` |
| `nixos-26.05`, `nixos-26.05-small` | `origin/release-26.05` |

Release-branch channels ship the **backport**, not the `master` commit.

**Invoke every helper under `scripts/` by that absolute
primary-checkout path, never as `./scripts/…`.** A routine run
executes inside the auto-update worktree, where `scripts/` is
agent-writable on the `auto-update` branch; the wrapper's guard only
compares it against `origin/main` once at start-up, so only the
primary checkout's copy is reliably the reviewed one.

## Upstream PHP — php.net

PHP has no local clone; the four `PHP` rows come from php.net's
release index, which serves JSON per branch:

```sh
curl -fsSL 'https://www.php.net/releases/?json&version=8.4'
```

*Current version* is its `version`; `date` is that release's date.
All four rows were fixed at seed: *First fixed* `8.5.12` / `8.4.27` /
`8.3.36` / `8.2.35`, *Fixed since* 2026-10-21. Only *Current version*
moves after that. A later point release is not a verdict change
unless the advisories' patched versions move.

## Distros tracked

Intentionally narrow: Debian, NetBSD/pkgsrc, and NixOS, as in the
sibling trackers. Other distros (Rocky / Amazon / Ubuntu / Arch /
Fedora / Proxmox) are out of scope (the user decided this at seed) and
should not be added.

| Rows | Source of truth |
|---|---|
| Debian sid, forky, 13 (trixie), 12 (bookworm) — one row per suite and packaged `php8.X` | `scripts/debian-versions`, plus the security tracker's per-CVE pages |
| pkgsrc `pkgsrc-current`, `pkgsrc-2026Q3` × `lang/php82`…`lang/php85` | `scripts/pkgsrc-versions` against the local clone |
| NixOS `nixos-unstable`, `nixos-unstable-small`, `nixos-26.05`, `nixos-26.05-small` × `php82`…`php85` | `scripts/nixpkgs-versions` at each channel's revision |
| nixpkgs `master`, `release-26.05` branches and `nixpkgs-unstable` × `php82`…`php85` | `scripts/nixpkgs-versions` |

Debian bookworm is in LTS; its PHP updates arrive as DLAs from the LTS
team, into `bookworm-security`. PHP 8.3 never reached a Debian release
(it was only ever in experimental), and `php8.5` is only in
experimental, which is not tracked.

`nixos-25.11` is superseded by 26.05 and is not tracked; when 26.11
releases, the 26.05 rows move up the same way.

**New pkgsrc quarterly branches.** `pkgsrc-2026Q3` was cut on
2026-09-21, before the releases; it had taken 8.4.26 and 8.5.11 by
pullup when this tracker was seeded. When `pkgsrc-2026Q4` is cut, add its
rows above `pkgsrc-2026Q3`, add it to `BRANCHES` in
`scripts/pkgsrc-versions` in an interactive session (the headless agent
cannot edit `scripts/`), and retire the oldest quarterly's rows only if
they have already flipped — still-vulnerable rows stay. The same goes
for `CHANNELS` in `scripts/nixpkgs-versions` when 26.11 releases.

**No rows for a release/channel already dead when the tracker was
seeded**, no rows for PHP branches already end-of-life (8.1 and
older), and no row for a branch a release had already dropped
(`php82` on nixpkgs `master`, removed 2026-10-21 in merge `00e46e05`,
nixpkgs#575757). The unstable channels and `nixpkgs-unstable` will
drop `php82` as they advance past that merge: their `php82` rows then
follow *A branch leaving a release*. A release that goes end-of-life *while tracked* keeps its rows,
frozen at their final verdict.

## Build environment

- Hugo **≥ 0.146.0** (PaperMod's minimum); the standard edition
  suffices. Debian apt is too old: `go install
  github.com/gohugoio/hugo@latest`, kept current with `gup update` (see
  `~/src/cve-tracker-template/NEW-TRACKER.md` § "Host prerequisites
  (Debian)").
- Go (any recent version) — for Hugo Modules to pull PaperMod, and to
  build Hugo itself.
- `make check` needs `python3` and `git`; `scripts/debian-versions`
  also needs the host's `dpkg` (for `dpkg --compare-versions`), present
  on any Debian host — the script sets its own `PATH`, so a dev-shell
  copy would not be seen.
- `xz` (Debian package `xz-utils`) on the auto-update host — decompresses
  snapshot.debian.org's past `dists/testing` indexes when dating a
  forky fix.
- The Nix flake provides these for an interactive shell: `nix develop`
  (or `cd` in if direnv is set up). The timer service runs on the host
  `PATH`, though, so the auto-update host still needs the apt packages
  — the `apt install` line in `NEW-TRACKER.md` § "Host prerequisites
  (Debian)" lists them.

## Auto-update worktree

The auto-update job works in a dedicated git worktree at
`~/src/auto-update/php-20261021`, checked out on a single long-lived
branch named `auto-update`. The wrapper merges `origin/main` forward
into that branch on each run, then hands off to headless Claude, which
commits any tracker changes back onto `auto-update` only. The agent
must not create per-run branches, switch branches, push, or open PRs —
merges of `auto-update` into `main` are done manually by the user.

The wrapper runs `git fetch origin` under `set -eu`, so `main` must be
on `origin` before the timer is worth enabling. A freshly seeded
tracker must `git remote add origin
https://github.com/suominen/php-20261021.git` and publish `main` there
first — a push is a breakpoint, so the user runs it.

One-time setup (from the primary checkout at `~/src/php-20261021`):

```
git worktree add -b auto-update ~/src/auto-update/php-20261021 main
```

The systemd units ship in `systemd/`. Wiring the timer means
symlinking both units into `~/.config/systemd/user/` with `ln -sr` and
enabling the timer:

```
ln -sr ~/src/php-20261021/systemd/php-20261021-tracker-update.service \
       ~/src/php-20261021/systemd/php-20261021-tracker-update.timer \
       ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now php-20261021-tracker-update.timer
```

The timer fires twice daily at `05:50` and `17:50` — a slot no other
tracker uses, so the
shared `~/src/nixos/nixpkgs` and `~/src/netbsd/pkgsrc` clones are not
fetched simultaneously. Verify the live set with
`systemctl --user list-timers | grep tracker` before changing it.

**The timer runs the wrapper from the primary checkout, not from the
worktree.** `ExecStart` points at `<primary>/scripts/auto-update`, and
the wrapper reads its prompt from there too, so what executes is always
code you have reviewed and merged to `main`. The agent can commit to
`auto-update`, so anything under `scripts/`, `.claude/`, `CLAUDE.md`,
or `.mcp.json` on that branch is untrusted: after merging `origin/main`
forward the wrapper refuses to run if any of them differs from
`origin/main`, and it refuses outright if it was invoked from inside
the worktree at all.

The service unit adds a kernel-level backstop — `ProtectSystem=strict`
with a short `ReadWritePaths` list (the worktree, the `.git`
directories git has to update, and `~/.claude/session-env`). Each
repository's `.git/hooks` and `.git/config` are handed back as
`ReadOnlyPaths`.

A refusal is a stop-and-look rather than something to clear
reflexively. Inspect it with `git -C ~/src/auto-update/php-20261021
diff origin/main -- scripts .claude CLAUDE.md .mcp.json` before doing
anything else.

To run a refresh immediately (the same path the timer takes):

```
systemctl --user start php-20261021-tracker-update.service
```

It is a `oneshot`, so the command blocks until the run finishes; follow
its output with `journalctl --user -u php-20261021-tracker-update`.
Run the trackers **one at a time**, never in parallel — they share the
reference clones under `~/src`.

## Tearing down the auto-update

Unwire it in this order — `systemctl disable` needs the unit
definition to still be resolvable when it runs.

1. **Disable the timer first**, while the unit symlinks are still in
   place:

   ```
   systemctl --user disable --now php-20261021-tracker-update.timer
   ```

2. **Remove the service symlink** (the `.timer` link is already gone
   after step 1):

   ```
   rm ~/.config/systemd/user/php-20261021-tracker-update.service
   ```

3. **Reload** so the running user manager drops the units:

   ```
   systemctl --user daemon-reload
   ```

4. **Clear the failed residue**:

   ```
   systemctl --user reset-failed php-20261021-tracker-update.timer
   ```

If the definition symlinks were removed *before* disabling, delete
`~/.config/systemd/user/timers.target.wants/php-20261021-tracker-update.timer`
directly, then reload and `reset-failed` as above.

Finally, remove the worktree and its branch (from the primary checkout
at `~/src/php-20261021`):

```
git worktree remove ~/src/auto-update/php-20261021
git branch -d auto-update
```

## Debian verification recipe

Debian packages PHP as one versioned source per branch (`php8.2`,
`php8.4`, …). The unversioned `php*` packages come from
`php-defaults`, whose version (`93`, `96`, `99`, and `2:8.4+96` for
the binaries) carries no PHP release at all; its `debian/rules`
`PHP_DEFAULT_VERSION` names the branch. One command does the whole
lookup:

```sh
~/src/php-20261021/scripts/debian-versions
```

It prints, per suite and per `php8.X` source the suite carries (the
default first), a tab-separated
`<suite> <source> <version> <php> <default|-> <ids|->` line:

- `<suite>` is `<suite>-security` when the security archive carries
  a newer version than the main archive — the apt-installable one —
  otherwise the plain suite. When both hold the same version the
  tracker's page lists only the plain suite, and so does the helper.
- `<php>` is the upstream PHP release, taken from the newest
  `New upstream version X.Y.Z` line of that version's changelog and
  cross-checked against the version string. `?` means the changelog
  could not be read or disagreed (a warning says which) — read the
  changelog yourself before recording anything.
- `<ids>` are tracked advisory ids named in changelog entries *above*
  that upstream line: fixes backported onto that release.

It fails loudly if a page cannot be fetched, a page no longer parses,
or a suite's default source is missing; don't paper over a failure by
guessing.

**Verdict.** A row whose `<php>` is at or past its branch's fixed
release (8.2.35 / 8.4.27 / 8.5.12) is fixed. Below it, the row is
fixed only if backports cover both CVEs: cross-check the `<ids>`
column and the security tracker's per-CVE pages —

```
WebFetch https://security-tracker.debian.org/tracker/CVE-2026-109618
```

— for CVE-2026-109618 and CVE-2026-109619. Neither page existed when
the tracker was seeded (a 404 is not a verdict). One of the two
backported is still `:x: Vulnerable`, with the missing CVE named.

Each Debian row's *Fixed since* is the date that **suite** first
carried the version that closes both. For sid that is the
upload date, from the changelog trailer or the fixed version's
`first_seen`:

```
curl -fsSL 'https://snapshot.debian.org/mr/package/php8.4/<version>/srcfiles?fileinfo=1'
```

Both of those date the upload to unstable, which is **not** forky's
date: the build reaches testing only after the age delay and
autopkgtests, often a week or more later. Never copy sid's date to
forky. forky's date is the UTC day the fixed version entered testing.
The `php8.4 <version> MIGRATED to testing` entry on the package news page
narrows it down, but the entry can be dated a day late:

```
curl -fsSL 'https://tracker.debian.org/pkg/php8.4/news/'
```

Confirm the day on snapshot.debian.org, which keeps every past state of
testing. Read testing's version at a UTC timestamp `<ts>` (e.g.
`20261005T120000Z`), and bisect until the change falls within one UTC
day:

```
curl -fsSL 'https://snapshot.debian.org/archive/debian/<ts>/dists/testing/main/source/Sources.xz' | xz -dc | grep -A1500 -x 'Package: php8.4' | grep -m1 '^Version:'
```

If snapshot does not show the migration yet, record the date the run
first saw forky at the fixed version and say so in the verification
log. A stable suite's date is its DSA/DLA, or the point release that
carried the fix.

sid is the canary; forky inherits via the usual sid → testing
migration; trixie advances via DSAs, bookworm via DLAs.

## pkgsrc verification recipe

pkgsrc (the NetBSD package collection; also used on SmartOS, macOS via
pkgin, etc.) lives in a local clone at `~/src/netbsd/pkgsrc`. Two
branches are tracked: `origin/trunk` (= `pkgsrc-current`) and the
current quarterly `origin/pkgsrc-2026Q3`. Quarterly branches receive
updates by pullup, so they can lag trunk by weeks.

Every PHP branch is its own package, `lang/php82` … `lang/php85`, but
**the PHP version is not in the package's Makefile**: all of them read
`PHPxx_VERSION` from `lang/php/phpversion.mk`, which also sets
`PHP_VERSION_DEFAULT`. The package is named
`${PHP_PKG_PREFIX}-${PHP_VERSION}` (`php84-8.4.27`), plus `nbN` when
`lang/phpXY/Makefile` sets `PKGREVISION` — which bumps for many
reasons besides security patches (the 2026Q3 `nb1` is a PCRE2
rebuild). One command assembles all of it:

```sh
~/src/php-20261021/scripts/pkgsrc-versions
```

It prints `<branch> <package> <identifier> <php> <default|-> <ids|->`
per branch and PHP package; `<ids>` lists tracked advisory ids named in
the package's `patches/`. The version decides unless `<ids>` is
non-empty, in which case read the patches for every applicable
advisory. An `absent` row means the branch does not carry that
package.

The script reads the clone through its `origin/...` refs and never
fetches; it warns if the clone was not fetched in the last 24 hours.

Derive a flip's *Fixed since* from the branch's history of
`phpversion.mk`, picking the commit that set the row's version by
**content**, not by subject or recency — quarterly commits are titled
`Pullup ticket #NNNN … lang/php84: Security fix`, and trunk subjects
are not reliable either (`lang/php84: udpate to 8.4.26`):

```sh
git -C ~/src/netbsd/pkgsrc log --format='%h %ad %s' --date=short -G '^PHP84_VERSION=.*8\.4\.27' origin/pkgsrc-2026Q3 -- lang/php/phpversion.mk
```

If `~/src/netbsd/pkgsrc` is missing, fail loudly rather than guessing.

### The clone is the source; a commit mail is a one-off exception

The git clone is the only pkgsrc source to check. Don't poll
`mail-index.netbsd.org`, don't read the CVS tree, and don't go looking
for a newer source when the clone reports a row as vulnerable.

If the git conversion is down, a commit mail **the user hands over**
may confirm an update the clone cannot show yet; cite it in the
tracker. Once a fact is recorded that way it outranks a lagging clone:
if a row is ahead of what `scripts/pkgsrc-versions` reports, believe
the tracker and leave the row alone.

## NixOS channel verification recipe

nixpkgs builds all four PHP branches from
`pkgs/development/interpreters/php/default.nix`, one
`phpXY = mkPhp { version = …; hash = …; }` block each, sharing
`generic.nix`; `pkgs/top-level/all-packages.nix` sets the default
(`php = php85;` on `master` at seed, `php84` on `release-26.05`).
`master` also carries `php86` (8.6.0 release candidates), which the
helper does not report and the tracker does not row.
One command reads every tracked channel and branch at its current
revision:

```sh
~/src/php-20261021/scripts/nixpkgs-versions
```

It prints `<channel> <attribute> <php> <default|-> <ids|->` for
`branch:master`, `branch:release-26.05`, the four NixOS channels, and
`nixpkgs-unstable`, following each channel's `channels.nixos.org`
pointer. Pass channel names or `branch:<name>` arguments to check a
subset. `<ids>` lists tracked ids named inside the attribute's block,
then — prefixed `generic:` — ids named in shared code, which may still
be gated to some branches: read the expression before trusting either.
It fails loudly on a parse problem and warns on a stale clone. A
channel that has moved past the clone's last fetch prints
`unresolved` rows and the script exits 3 after the rest: record
nothing for that channel this run, and never read it as `absent`.
Exit 1 is a failure, possibly after some rows: record nothing from
it.

The `branch:master` and `branch:release-26.05` rows exist because a
flake input pinned to `github:NixOS/nixpkgs/<branch>` resolves to that
branch; an input following a *channel* name is answered by that
channel's rows. **A branch row's *Fixed since* is the date the bump
landed on that branch**, not a channel release date, and not the bump
commit's own date: a PR or staging merge can land days later (php85's
8.5.11 bump was committed 2026-09-24 and merged into `master`
2026-09-27). Read the branch's first-parent history; its entry for the
bump is the merge that brought it in, or the commit if pushed
directly:

```sh
git -C ~/src/nixos/nixpkgs log --first-parent --format='%h %cd %s' --date=short origin/master -- pkgs/development/interpreters/php/
```

The branch dates also bound the channel dates.

Verdict: `<php>` at or past the branch's fixed release is fixed; a
patch named after the ids on an older base needs both CVEs covered,
else it stays Vulnerable with the missing CVE named.

Never record channel git-revisions in the tracker. The **release
name** reported by `scripts/nixos-first-shipped` belongs in the
verification log.

If `~/src/nixos/nixpkgs` is missing, fail loudly rather than guessing.

## Key sources to monitor

| Source | URL |
|---|---|
| PHP 8 ChangeLog | <https://www.php.net/ChangeLog-8.php> |
| Release announcements | <https://www.php.net/releases/8_5_12.php>, `8_4_27`, `8_3_36`, `8_2_35` |
| Release index (JSON) | <https://www.php.net/releases/?json&version=8.4> (per branch) |
| php-src advisories (API) | <https://api.github.com/repos/php/php-src/security-advisories> |
| CVE Services API | <https://cveawg.mitre.org/api/cve/CVE-2026-109618> (and CVE-2026-109619) |
| NVD API (JSON — the NVD web pages are JS-only) | <https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2026-109618> |
| CISA KEV catalog (JSON) | <https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json> |
| Debian security tracker | <https://security-tracker.debian.org/tracker/CVE-2026-109618> (per CVE), `/tracker/source-package/php8.4` (per source) |
| Debian changelogs | <https://tracker.debian.org/pkg/php8.4> |
| NixOS security tracker | <https://tracker.security.nixos.org/> |
| NixOS channel pointers | <https://channels.nixos.org/nixos-unstable/git-revision> (and the other channels) |
| pkgsrc — `lang/php/phpversion.mk` (GitHub mirror) | <https://github.com/NetBSD/pkgsrc/blob/trunk/lang/php/phpversion.mk> |

Prefer plain-text and JSON endpoints and the Debian tracker's HTML over
JS-rendered SPAs — those return nothing to WebFetch, and reading one
falsely sees "no advisory". The GitHub advisory pages, the NVD web
pages, and the NixOS security tracker are all SPAs: link them, but take
the facts from the APIs and the local clones.

When the CVE records are published in the CVE List, check whether they
change anything the tracker states (scores, CWEs, affected ranges) and
update the Summary and verification log; the GitHub advisories stay
the primary source for fixed versions.

## Known harmless warnings during build

PaperMod's templates still call `.Language.LanguageDirection` and
`.Language.LanguageCode`, which Hugo deprecated in 0.158.0. The build
emits `WARN deprecated:` lines for both. Upstream theme issue — don't
try to fix it in this repo.

## License

The tracker content is licensed under **CC BY 4.0** (see `LICENSE` at
the repo root). Copyright © 2026 Kimmo Suominen. The site footer
credits both the author and the licence.
