"""`pos` — command-line interface for a Personal OS vault."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

from . import __version__, budget, doctor, graph, init, metrics, privacy
from .vault import Vault, VaultError


def _vault(args) -> Vault:
    return Vault.load(args.vault) if args.vault else Vault.discover()


def cmd_check(args) -> int:
    vault = _vault(args)
    try:
        rows = graph.validate(vault)
    except graph.GraphError as exc:
        print(f"block graph ERROR:\n{exc}", file=sys.stderr)
        return 1
    if args.staged:
        changed = graph.staged_paths(vault)
        today = date.today().isoformat()
        if args.stamp:
            stamped = graph.stamp_changed_owners(vault, changed, today)
            if stamped:
                subprocess.run(["git", "-C", str(vault.root), "add", "--", *stamped], check=True)
                print("stamped `updated:` on: " + ", ".join(stamped))
                rows = graph.validate(vault)
        stale = graph.stale_changed_owners(vault, changed, today)
        if stale:
            print(f"block graph ERROR: changed owners must set `updated: {today}`: {', '.join(stale)}", file=sys.stderr)
            return 1
        impacts = graph.reverse_dependencies(vault, changed)
        if impacts:
            print("semantic propagation review: " + ", ".join(impacts))
    output = graph.render(vault, rows)
    if args.write and graph.write_snapshot(vault, output):
        print(f"updated {vault.cfg('generated_snapshot')}")
    if args.check_fresh and not graph.snapshot_is_fresh(vault, output):
        print(f"block graph ERROR: generated snapshot is stale: {vault.cfg('generated_snapshot')}", file=sys.stderr)
        return 1
    external = len(vault.registry.get("external_blocks", []))
    print(f"block graph valid: {len(rows)} local + {external} external blocks")
    return 0


def cmd_doctor(args) -> int:
    findings = doctor.run(_vault(args))
    if args.json:
        print(json.dumps([f.as_dict() for f in findings], ensure_ascii=False, indent=2))
    else:
        counts = {s: sum(f.severity == s for f in findings) for s in ("error", "warn", "info")}
        for f in findings:
            if f.severity != "info" or args.verbose:
                print(f"[{f.severity:5}] {f.check:15} {f.message}")
        hidden = "" if args.verbose or not counts["info"] else " (info hidden, use -v)"
        print(f"doctor: {counts['error']} error, {counts['warn']} warn, {counts['info']} info{hidden}")
    return 1 if any(f.severity == "error" for f in findings) else 0


def cmd_budget(args) -> int:
    report = budget.measure(_vault(args))
    if args.json:
        print(json.dumps({"total": report.total, "target": report.target, "max": report.maximum,
                          "status": report.status, "items": [i.__dict__ for i in report.items]}, indent=2))
    else:
        for item in report.items:
            mark = "" if item.present else "  (missing)"
            print(f"{item.tokens:>7,}  {item.source}{mark}")
        print(f"{report.total:>7,}  total (estimate) — target {report.target:,}, max {report.maximum:,}: {report.status}")
    return 1 if report.status == "over" else 0


def cmd_metrics(args) -> int:
    data = metrics.collect(_vault(args))
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_scan(args) -> int:
    root = Path(args.root or ".").resolve()
    path = privacy.resolve_denylist(args.denylist)
    if args.patterns_only:
        terms = []
    elif path.is_file():
        terms = privacy.load_denylist(path)
    elif args.allow_missing_denylist:
        print("privacy scan: no private denylist found; pattern rules only", file=sys.stderr)
        terms = []
    else:
        print(f"privacy scan BLOCK: private denylist not found at {path}\n"
              "Create it (one term per line, outside the repo) or set PRIVACY_DENYLIST.", file=sys.stderr)
        return 2
    scanned, findings = privacy.scan_repo(root, terms, staged=args.staged, paths=args.paths)
    if findings:
        print(f"privacy scan BLOCK: {len(findings)} finding(s) in {scanned} file(s)", file=sys.stderr)
        for f in findings:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"privacy scan clean: {scanned} file(s), {len(terms)} private terms, {len(privacy.SECRET_PATTERNS)} secret rules")
    return 0


def cmd_init(args) -> int:
    try:
        created = init.scaffold(Path(args.target), owner=args.owner, git=not args.no_git, force=args.force)
    except FileExistsError as exc:
        print(f"init ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"created {len(created)} files in {Path(args.target).resolve()}")
    print("next: open it in Obsidian, then start your agent inside the folder (see README.md there)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pos", description="Personal OS — a local-first memory layer for AI agents.")
    parser.add_argument("--version", action="version", version=f"pos {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def with_vault(p):
        p.add_argument("--vault", help="vault root (default: discover from the current directory)")
        return p

    p = with_vault(sub.add_parser("check", help="validate the block graph and refresh the generated state"))
    p.add_argument("--write", action="store_true", help="refresh the generated snapshot")
    p.add_argument("--check", dest="check_fresh", action="store_true", help="fail if the snapshot is stale")
    p.add_argument("--staged", action="store_true", help="validate freshness of staged owner changes")
    p.add_argument("--stamp", action="store_true", help="with --staged: auto-stamp `updated:` and re-stage")
    p.set_defaults(func=cmd_check)

    p = with_vault(sub.add_parser("doctor", help="deterministic health check"))
    p.add_argument("--json", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true", help="also print info-level findings")
    p.set_defaults(func=cmd_doctor)

    p = with_vault(sub.add_parser("budget", help="estimate the token cost of session orientation"))
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_budget)

    p = with_vault(sub.add_parser("metrics", help="aggregate-only metrics, safe to publish"))
    p.add_argument("--out", help="write JSON to this file")
    p.set_defaults(func=cmd_metrics)

    p = sub.add_parser("scan", help="privacy gate: secrets, e-mails, home paths, private denylist")
    p.add_argument("paths", nargs="*")
    p.add_argument("--root", help="repo root (default: current directory)")
    p.add_argument("--staged", action="store_true", help="scan the git index (pre-commit)")
    p.add_argument("--denylist", help="private denylist file (default: $PRIVACY_DENYLIST or ~/.config/personal-os/denylist.txt)")
    p.add_argument("--allow-missing-denylist", action="store_true", help="CI mode: pattern rules only if no denylist")
    p.add_argument("--patterns-only", action="store_true", help="skip the denylist (e.g. inside the private vault itself)")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("init", help="scaffold a new vault from the starter kit")
    p.add_argument("target")
    p.add_argument("--owner", default="Your Name", help="name used in the kit's templates")
    p.add_argument("--no-git", action="store_true")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except VaultError as exc:
        print(f"pos ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
