"""Privacy gate for a public repo derived from a private vault.

The public repo is built by allowlist: nothing is copied from the private vault
except reviewed code. This scanner is the second line of defence. It blocks:

* secret-shaped tokens (API keys, private keys, GitHub/Slack/AWS tokens, JWTs),
* e-mail addresses outside an explicit allowlist,
* absolute home-directory paths,
* any term from a private denylist (people, clients, places, private projects).

The denylist itself is private and lives OUTSIDE the repo
(default `~/.config/personal-os/denylist.txt`, override with `PRIVACY_DENYLIST`),
so the list of things you must not publish is never published.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DENYLIST = Path("~/.config/personal-os/denylist.txt")

SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "api key (sk-)": re.compile(r"sk-[A-Za-z0-9_-]{32,}"),
    "stripe live key": re.compile(r"sk_live_[A-Za-z0-9]{20,}"),
    "github token": re.compile(r"\b(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}"),
    "aws access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "slack token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
EMAIL_ALLOW = re.compile(r"(@example\.(com|org|net)|@users\.noreply\.github\.com|^noreply@[a-z0-9.-]+)$", re.I)
HOME_PATH = re.compile(r"/(?:Users|home)/(?!you\b|<)[A-Za-z0-9._-]+")

SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".woff", ".woff2"}
# Files that must describe the patterns they detect.
PATTERN_DOCS = {"personal_os/privacy.py", "tests/test_privacy.py"}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    sample: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}: {self.sample}"


def mask(value: str) -> str:
    """Enough to locate the hit, never the full secret or term."""
    if len(value) <= 4:
        return value[0] + "***"
    return value[:2] + "***" + value[-1]


def load_denylist(path: Path) -> list[str]:
    return [
        line.strip().casefold()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def resolve_denylist(explicit: str | None = None) -> Path:
    return Path(explicit or os.environ.get("PRIVACY_DENYLIST") or DEFAULT_DENYLIST).expanduser()


def scan_text(rel: str, text: str, denylist: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    pattern_rules = rel not in PATTERN_DOCS
    for lineno, line in enumerate(text.splitlines(), start=1):
        if pattern_rules:
            for rule, pattern in SECRET_PATTERNS.items():
                findings += [Finding(rel, lineno, f"secret: {rule}", mask(m.group(0))) for m in pattern.finditer(line)]
            findings += [Finding(rel, lineno, "absolute home path", mask(m.group(0))) for m in HOME_PATH.finditer(line)]
            for m in EMAIL.finditer(line):
                if not EMAIL_ALLOW.search(m.group(0)):
                    findings.append(Finding(rel, lineno, "e-mail address", mask(m.group(0))))
        folded = line.casefold()
        findings += [Finding(rel, lineno, "denylisted term", mask(term)) for term in denylist if term in folded]
    return findings


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def iter_files(root: Path, staged: bool = False, paths: list[str] | None = None):
    """Yield (relative path, text). Staged mode reads blobs from the index, not the working tree."""
    if paths:
        names = paths
    elif staged:
        names = _git(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR").stdout.decode().splitlines()
    else:
        names = _git(root, "ls-files", "--cached", "--others", "--exclude-standard").stdout.decode().splitlines()
    for name in names:
        if Path(name).suffix.lower() in SKIP_SUFFIXES:
            continue
        try:
            data = _git(root, "show", f":{name}").stdout if staged and not paths else (root / name).read_bytes()
        except (OSError, subprocess.CalledProcessError):
            continue
        if b"\0" in data[:4096]:
            continue
        yield name, data.decode("utf-8", errors="replace")


def scan_repo(root: Path, denylist: list[str], staged: bool = False, paths: list[str] | None = None):
    findings: list[Finding] = []
    scanned = 0
    for rel, text in iter_files(root, staged, paths):
        scanned += 1
        findings += scan_text(rel, text, denylist)
    return scanned, findings
