#!/usr/bin/env python3
"""
compress_commit_dates.py

Rewrites author and committer dates of every commit reachable from any ref
so they fall within the last N days (default 7), preserving topological order.

LIMITATIONS (read before running):
- This REWRITES HISTORY. Every commit hash changes. Collaborators must
  re-clone or hard reset, and you must force push (not done by this script).
- GPG/SSH commit signatures are invalidated (the signed content changes).
- Timestamps are spread evenly across the window by commit order, so the
  original spacing between commits is NOT preserved.
- All dates are written in UTC (+0000); original timezone offsets are lost.
- Tags pointing at commits are rewritten (--tag-name-filter cat), but
  annotated tag dates themselves are not changed.
- Uses git filter-branch (deprecated but ubiquitous). It is slow on large
  repos. For big repos, use git-filter-repo instead.
- Run on a fresh clone if you can. A bundle backup is made regardless.
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time


def git(*args, check=True, capture=True):
    return subprocess.run(
        ["git", *args], check=check, text=True,
        stdout=subprocess.PIPE if capture else None,
    ).stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=float, default=7.0,
                    help="window size in days (default 7)")
    ap.add_argument("--margin-minutes", type=int, default=5,
                    help="keep newest commit this many minutes before now")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the planned mapping, change nothing")
    ap.add_argument("--yes", action="store_true", help="skip confirmation")
    args = ap.parse_args()

    if git("rev-parse", "--is-inside-work-tree").strip() != "true":
        sys.exit("Not inside a git repository.")
    if git("status", "--porcelain").strip():
        sys.exit("Working tree is not clean. Commit or stash first.")

    # Parents always come before children, so timestamps stay monotonic.
    commits = git("rev-list", "--topo-order", "--reverse", "--all").split()
    n = len(commits)
    if n == 0:
        sys.exit("No commits found.")

    end = int(time.time()) - args.margin_minutes * 60
    start = end - int(args.days * 86400)
    step = (end - start) / max(n - 1, 1)
    mapping = {c: int(start + i * step) for i, c in enumerate(commits)}

    print(f"{n} commits -> {time.ctime(start)} .. {time.ctime(end)}")
    if args.dry_run:
        for c in commits[:5] + (["..."] if n > 10 else []) + commits[-5:]:
            print(c if c == "..." else f"{c[:10]}  {time.ctime(mapping[c])}")
        return

    if not args.yes:
        if input("This rewrites history. Type 'rewrite' to continue: ") != "rewrite":
            sys.exit("Aborted.")

    bundle = f"../backup-{int(time.time())}.bundle"
    git("bundle", "create", bundle, "--all")
    print(f"Backup bundle: {bundle}")

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".map") as f:
        for c, ts in mapping.items():
            f.write(f"{c} {ts}\n")
        map_path = f.name

    env_filter = (
        f'TS=$(awk -v c="$GIT_COMMIT" \'$1==c {{print $2; exit}}\' "{map_path}"); '
        'export GIT_AUTHOR_DATE="@$TS +0000"; '
        'export GIT_COMMITTER_DATE="@$TS +0000"'
    )

    env = dict(os.environ, FILTER_BRANCH_SQUELCH_WARNING="1")
    subprocess.run(
        ["git", "filter-branch", "-f", "--env-filter", env_filter,
         "--tag-name-filter", "cat", "--", "--all"],
        check=True, env=env,
    )
    os.unlink(map_path)

    print("\nDone. Verify with:  git log --format='%h %ad %s' --date=iso")
    print("Then publish with:  git push --force-with-lease --all && "
          "git push --force --tags")
    print("Remove filter-branch leftovers with:  "
          "rm -rf .git/refs/original && git reflog expire --expire=now --all "
          "&& git gc --prune=now")


if __name__ == "__main__":
    main()