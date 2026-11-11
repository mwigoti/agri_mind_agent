#!/usr/bin/env python3
import argparse
import os
import shlex
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone


# ---------------------------------------------------------------- helpers

def git(*args, check=True):
    """Run git and return stdout as text."""
    return subprocess.run(
        ["git", *args], check=check, text=True, stdout=subprocess.PIPE
    ).stdout


def ref_exists(ref):
    return subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", ref]
    ).returncode == 0


def parse_day(s, tz, end_of_day):
    d = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=tz)
    if end_of_day:
        d = d + timedelta(days=1) - timedelta(seconds=1)
    return int(d.timestamp())


def remote_branches(remote):
    """Return [(branch_name, full_ref)] for every branch on the remote."""
    prefix = f"refs/remotes/{remote}/"
    out = []
    for ref in git("for-each-ref", "--format=%(refname)", prefix).split():
        name = ref[len(prefix):]
        if name == "HEAD":
            continue
        out.append((name, ref))
    return out


def delete_backup_refs():
    for ref in git("for-each-ref", "--format=%(refname)", "refs/original").split():
        git("update-ref", "-d", ref)


def tip_trees():
    """Map every local branch and tag to the tree id of its tip."""
    trees = {}
    fmt = "%(refname)"
    for ref in git("for-each-ref", "--format=" + fmt,
                   "refs/heads", "refs/tags").split():
        trees[ref] = git("rev-parse", f"{ref}^{{tree}}").strip()
    return trees


def all_stamps(*revs):
    out = git("log", *revs, "--format=%at %ct").split("\n")
    return [int(x) for line in out if line.strip() for x in line.split()]


# ---------------------------------------------------------------- mapping

def build_mapping(commits, start, end, mode):
    n = len(commits)
    if mode == "even":
        step = (end - start) / max(n - 1, 1)
        return {c: int(start + i * step) for i, c in enumerate(commits)}

    # proportional: scale existing committer timestamps into the window
    out = git("log", "--branches", "--tags", "--format=%H %ct").split("\n")
    orig = {l.split()[0]: int(l.split()[1]) for l in out if l.strip()}
    missing = [c for c in commits if c not in orig]
    if missing:  # only possible in --dry-run with not-yet-created branches
        extra = git("log", "--no-walk", *missing, "--format=%H %ct").split("\n")
        orig.update({l.split()[0]: int(l.split()[1]) for l in extra if l.strip()})
    lo = min(orig[c] for c in commits)
    hi = max(orig[c] for c in commits)
    span = max(hi - lo, 1)
    mapping, prev = {}, start
    for c in commits:  # topological order, parents first
        ts = start + int((orig[c] - lo) / span * (end - start))
        ts = min(max(ts, prev), end)
        mapping[c] = ts
        prev = ts
    return mapping


# ------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(
    description="Rewrite all commit dates on all branches and tags into a fixed window."
)
    ap.add_argument("--start", default="2026-10-12", help="first day, YYYY-MM-DD")
    ap.add_argument("--end", default="2026-10-15", help="last day, YYYY-MM-DD (inclusive)")
    ap.add_argument("--tz-hours", type=int, default=3, help="UTC offset in whole hours (default +3)")
    ap.add_argument("--mode", choices=["even", "proportional"], default="even")
    ap.add_argument("--remote", default="origin", help="remote to mirror and push to (default origin)")
    ap.add_argument("--dry-run", action="store_true", help="show the plan, change nothing")
    ap.add_argument("--yes", action="store_true", help="skip confirmation prompts")
    ap.add_argument("--push", action="store_true",
                    help="force push all branches and tags, then fetch --prune")
    args = ap.parse_args()

    tz = timezone(timedelta(hours=args.tz_hours))
    start = parse_day(args.start, tz, False)
    end = parse_day(args.end, tz, True)
    if end <= start:
        sys.exit("--end must be after --start.")
    if end > time.time():
        sys.exit("The window ends in the future. Choose a window in the past.")
    offset = f"{args.tz_hours:+03d}00"

    if git("rev-parse", "--is-inside-work-tree", check=False).strip() != "true":
        sys.exit("Not inside a git repository.")
    os.chdir(git("rev-parse", "--show-toplevel").strip())
    if git("status", "--porcelain").strip():
        sys.exit("Working tree is not clean. Commit or stash first.")

    # --- step 1: make sure every remote branch has a local branch
    to_create, diverged = [], []
    for name, ref in remote_branches(args.remote):
        local = f"refs/heads/{name}"
        if not ref_exists(local):
            to_create.append((name, ref))
        elif git("rev-parse", local).strip() != git("rev-parse", ref).strip():
            diverged.append(name)
    for name in diverged:
        print(f"WARNING: local '{name}' differs from {args.remote}/{name}. "
              f"The LOCAL version will be rewritten and (with --push) overwrite the remote.")

    rev_args = ["--branches", "--tags"]
    if args.dry_run:
        # do not touch the repo, but still include the remote-only branches in the plan
        rev_args += [ref for _, ref in to_create]
        for name, ref in to_create:
            print(f"[dry-run] would create local branch '{name}' from {ref}")
    else:
        for name, ref in to_create:
            subprocess.run(["git", "branch", "--track", name, ref], check=True)
            print(f"Created local branch '{name}' from {ref}")

    # --- step 4: plan the new timestamps
    commits = git("rev-list", "--topo-order", "--reverse", *rev_args).split()
    n = len(commits)
    if n == 0:
        sys.exit("No commits found.")
    mapping = build_mapping(commits, start, end, args.mode)

    fmt = lambda t: datetime.fromtimestamp(t, tz).strftime("%Y-%m-%d %H:%M:%S %z")
    print(f"{n} commits ({args.mode}) -> {fmt(start)} .. {fmt(end)}")
    if args.dry_run:
        shown = commits if n <= 10 else commits[:5] + ["..."] + commits[-5:]
        for c in shown:
            print(c if c == "..." else f"{c[:10]}  {fmt(mapping[c])}")
        print("Dry run only. Nothing was changed.")
        return

    if not args.yes:
        if input("This rewrites history. Type 'rewrite' to continue: ") != "rewrite":
            sys.exit("Aborted.")

    # --- steps 2 and 3: clear old backups, then back up everything
    delete_backup_refs()
    bundle = os.path.abspath(os.path.join("..", f"backup-{int(time.time())}.bundle"))
    git("bundle", "create", bundle, "--all")
    print(f"Backup bundle: {bundle}")

    trees_before = tip_trees()
    count_before = int(git("rev-list", "--count", "--branches", "--tags").strip())

    # --- step 5: rewrite
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".map") as f:
        for c, ts in mapping.items():
            f.write(f"{c} {ts}\n")
        map_path = f.name

    env_filter = (
        f"TS=$(awk -v c=\"$GIT_COMMIT\" '$1==c {{print $2; exit}}' {shlex.quote(map_path)}); "
        f"export GIT_AUTHOR_DATE=\"$TS {offset}\"; "
        f"export GIT_COMMITTER_DATE=\"$TS {offset}\""
    )
    env = dict(os.environ, FILTER_BRANCH_SQUELCH_WARNING="1")
    try:
        subprocess.run(
            ["git", "filter-branch", "-f", "--env-filter", env_filter,
             "--tag-name-filter", "cat", "--", "--branches", "--tags"],
            check=True, env=env,
        )
    finally:
        os.unlink(map_path)

    delete_backup_refs()
    git("reflog", "expire", "--expire=now", "--all")
    git("gc", "--prune=now", "--quiet")

    # --- step 6: verify
    problems = []
    count_after = int(git("rev-list", "--count", "--branches", "--tags").strip())
    if count_after != count_before:
        problems.append(f"commit count changed: {count_before} -> {count_after}")
    bad = [t for t in all_stamps("--branches", "--tags") if not (start <= t <= end)]
    if bad:
        problems.append(f"{len(bad)} author/committer timestamps outside the window")
    trees_after = tip_trees()
    changed = [r for r in trees_before if trees_before[r] != trees_after.get(r)]
    if changed:
        problems.append(f"file content changed on: {', '.join(changed)}")
    if problems:
        sys.exit("VERIFY FAILED:\n  " + "\n  ".join(problems) +
                 f"\nRestore with: git clone {bundle} restored")
    print(f"Verified: {n} commits, all dates inside the window, "
          f"all {len(trees_after)} branch/tag tips have identical file trees.")

    # --- step 7: optional push
    if not args.push:
        r = args.remote
        print(f"Not pushed. Publish with:\n  git push --force {r} --all\n"
              f"  git push --force {r} --tags\n  git fetch --prune {r}")
        return
    if not args.yes:
        if input(f"Force push ALL branches and tags to '{args.remote}'? Type 'push': ") != "push":
            sys.exit("Rewrite kept locally. Push skipped.")
    git("push", "--force", args.remote, "--all")
    git("push", "--force", args.remote, "--tags")
    git("fetch", "--prune", args.remote)
    print(f"Force pushed all branches and tags to {args.remote} and refreshed its tracking refs.")

    leftover = [t for t in all_stamps("--all") if not (start <= t <= end)]
    if leftover:
        print(f"NOTE: {len(leftover)} timestamps reachable from other refs (stash, notes, "
              f"or non-branch remote refs) are still outside the window. "
              f"Find them with: git for-each-ref --contains <hash>")


if __name__ == "__main__":
    main()