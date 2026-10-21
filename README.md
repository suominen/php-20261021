# PHP2Shell (CVE-2026-109618, CVE-2026-109619) tracking site

Source for the PHP2Shell patch-status tracker: a single-page site
recording which distributions have shipped the PHP security releases
of 2026-10-21 that fix CVE-2026-109618 and CVE-2026-109619, branch by
branch.

## Where the facts live

Everything about the vulnerabilities — the advisories, the fixed
version per PHP branch, and current per-distribution patch
status — belongs to the tracker page, not to this README:

- **Rendered:** <https://kimmo.cloud/php-20261021/>
- **Source:** [`site/content/_index.md`](site/content/_index.md)

Edit that file; everything else in this repo is build infrastructure.

None of it is restated here on purpose.  The tracker page is revised as
distributions ship fixes — for the actively updated trackers, up to
twice daily by the auto-update agent — so any copy kept in this
README would silently rot.  Resist re-adding a summary.

Deployment plan and current setup state live in
[`WEBSITE.md`](WEBSITE.md).

## Local development

Requires Hugo ≥ 0.146.0 (the standard edition suffices: no Sass or image
processing in this site) and Go (for Hugo Modules to fetch the PaperMod
theme).

### With Nix (recommended)

```sh
nix develop          # dev shell: hugo, go, resvg + fonts, and every lookup tool
cd site
hugo server          # local preview at http://localhost:1313/php-20261021/
```

If you use [direnv](https://direnv.net/), `direnv allow` once and the
dev shell auto-activates whenever you `cd` into the repo.

### Without Nix

Install Hugo ≥ 0.146.0 and Go ≥ 1.24 yourself (`CLAUDE.md` § "Build
environment" has the `go install` recipe), then:

```sh
cd site
hugo server          # http://localhost:1313/php-20261021/
```

## Build and publish

```sh
make build       # local build into site/public/
make dist        # build, then rsync to haig:/php-20261021/
make banner      # re-rasterise the social banner SVG → PNG (needs resvg + the banner fonts)
make check       # run the lookup-helper tests
```

`make dist` runs `make build` first. `make banner` is only needed after
editing `site/assets/php-20261021-tracker.svg`; the rendered PNG is
committed.

## Lookup helpers

PHP ships several branches at once, and a distribution's package
version does not say which upstream PHP release it builds. Three
helpers read that out of each ecosystem's own source — never by running
`php`:

```sh
./scripts/debian-versions
```

```sh
./scripts/pkgsrc-versions
```

```sh
./scripts/nixpkgs-versions
```

Each prints one tab-separated line per distribution release and PHP
branch: the package, the upstream PHP release it builds, whether it is
the release's default PHP, and any tracked advisory ids backported on
top. `debian-versions` reads the branch per suite from `php-defaults`
and the PHP release from the package changelog; `pkgsrc-versions`
reads `lang/php/phpversion.mk` in the local pkgsrc clone;
`nixpkgs-versions` reads the `phpXY` attributes at each channel's
revision in the local nixpkgs clone. `-h` explains each one's output
in full. The advisory ids they search for are listed in
`scripts/tracked-ids`.

## Dating a fix

A row's *Fixed since* is the date the fix actually shipped, derived
from the source that shipped it — never the day it was noticed. For the
NixOS and nixpkgs channels that derivation is a script:

```sh
./scripts/nixos-first-shipped nixos-unstable <nixpkgs-commit>
```

It lists the channel's published releases, finds the earliest one built
from a revision containing the commit, and prints that release and its
publication date. Debian dates come from the changelog or
snapshot.debian.org, pkgsrc dates from the history of
`lang/php/phpversion.mk`.

## Repo layout

```
.
├── flake.nix              # Nix dev environment (build, banner, publish, lookup tools)
├── .envrc                 # direnv hook → `use flake`
├── .gitignore
├── Makefile               # `make build`, `make dist`, `make banner`, `make check`
├── LICENSE                # CC BY 4.0
├── README.md              # this file
├── CLAUDE.md              # project instructions for Claude Code
├── WEBSITE.md             # publication plan / decisions log
├── scripts/               # auto-update driver + prompt, and the lookup helpers
├── systemd/               # user-level timer + service units
├── tests/                 # tests for the lookup helpers
└── site/                  # Hugo project
    ├── hugo.toml
    ├── content/
    │   └── _index.md      # the tracker (single page)
    ├── assets/css/extended/custom.css      # PaperMod CSS overrides
    ├── assets/php-20261021-tracker.svg     # social-banner source (→ make banner)
    ├── static/php-20261021-tracker.png     # rendered OpenGraph banner (committed)
    ├── layouts/partials/  # PaperMod overrides (post_meta, extend_footer)
    ├── layouts/shortcodes/details.html     # collapsible verification log
    ├── go.mod, go.sum     # Hugo Modules — pulls PaperMod theme
    └── …                  # standard Hugo skeleton
```

## License

[CC BY 4.0](LICENSE) — share and adapt with attribution.
