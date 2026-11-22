"""
R31-T009 check.py
=================
Verifies prerequisites and state transitions for fetching and checking out
pull request refs locally from a remote origin:
  1. Repository state: clean worktree and index on branch main
  2. Local config: remote.origin.fetch refspec configured locally
  3. Isolation: global Git config is completely untouched
  4. Fetch: creates local tracking ref refs/remotes/origin/pr/1 pointing to B
  5. Checkout: switches to pr/1 with expected tree state

Fixture (temporary, local only – no network):
  - repo: branch main, 3 commits (A, B, C), topic at B
  - bare.git: local bare repo acting as origin
  - bare.git has simulated PR ref refs/pull/1/head pointing to commit B
"""

import os
import subprocess
import tempfile
import pathlib

WORK_DIR = pathlib.Path(__file__).parent
ACTUAL   = WORK_DIR / "actual.txt"


def run(cmd, cwd, env=None, check=True):
    merged = {**os.environ, **(env or {})}
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, check=check, env=merged
    )


def git(args, cwd, env=None, check=True):
    return run(["git"] + args, cwd=cwd, env=env, check=check)


def make_fixture(tmpdir, base_ts):
    repo = os.path.join(tmpdir, "repo")
    env_base = {
        "GIT_AUTHOR_NAME":    "Course Student",
        "GIT_AUTHOR_EMAIL":   "student@example.invalid",
        "GIT_COMMITTER_NAME": "Course Student",
        "GIT_COMMITTER_EMAIL":"student@example.invalid",
    }
    env_a = {**env_base,
        "GIT_AUTHOR_DATE":    f"{base_ts + 0} +0000",
        "GIT_COMMITTER_DATE": f"{base_ts + 0} +0000",
    }
    env_b = {**env_base,
        "GIT_AUTHOR_DATE":    f"{base_ts + 1} +0000",
        "GIT_COMMITTER_DATE": f"{base_ts + 1} +0000",
    }
    env_c = {**env_base,
        "GIT_AUTHOR_DATE":    f"{base_ts + 2} +0000",
        "GIT_COMMITTER_DATE": f"{base_ts + 2} +0000",
    }

    git(["init", "--initial-branch=main", repo], cwd=tmpdir)
    git(["config", "user.email", "student@example.invalid"], cwd=repo)
    git(["config", "user.name",  "Course Student"],          cwd=repo)

    # Commit A
    pathlib.Path(repo, "notes.txt").write_text("alpha\n")
    git(["add", "notes.txt"], cwd=repo)
    git(["commit", "-m", "A: add notes.txt"], cwd=repo, env=env_a)
    sha_a = git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()

    # Commit B – topic at B
    pathlib.Path(repo, "notes.txt").write_text("alpha\nbeta\n")
    git(["add", "notes.txt"], cwd=repo)
    git(["commit", "-m", "B: append beta"], cwd=repo, env=env_b)
    sha_b = git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()
    git(["branch", "topic"], cwd=repo)

    # Commit C – only on main
    pathlib.Path(repo, "todo.txt").write_text("one\n")
    git(["add", "todo.txt"], cwd=repo)
    git(["commit", "-m", "C: add todo.txt"], cwd=repo, env=env_c)
    sha_c = git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()

    return repo, sha_a, sha_b, sha_c


def run_once(trial: int):
    base_ts = 1_000_000_000
    lines   = []

    with tempfile.TemporaryDirectory() as tmpdir:
        # Snapshot global config before run
        global_before = git(["config", "--global", "--list"], cwd=tmpdir, check=False).stdout

        repo, sha_a, sha_b, sha_c = make_fixture(tmpdir, base_ts)

        # Create bare origin repo
        bare = os.path.join(tmpdir, "bare.git")
        git(["init", "--bare", "--initial-branch=main", bare], cwd=tmpdir)
        git(["remote", "add", "origin", f"file://{bare}"], cwd=repo)
        git(["push", "-u", "origin", "main"], cwd=repo)

        # In bare repo, simulate GitHub creating a PR ref from topic branch (commit B)
        git(["update-ref", "refs/pull/1/head", sha_b], cwd=bare)

        # ── Precondition check 1: clean status & branch main ─────────
        status = git(["status", "--porcelain"], cwd=repo).stdout.strip()
        current_branch = git(["branch", "--show-current"], cwd=repo).stdout.strip()
        ok1 = (status == "") and (current_branch == "main")
        lines.append(("PASS" if ok1 else "FAIL") +
                     ": clean working tree and index on branch main before fetch")
        assert ok1, f"Trial {trial}: dirty repo or not on main: {status!r}, branch: {current_branch}"

        # ── Precondition check 2: add local refspec & verify global untouched ─
        git(["config", "--add", "remote.origin.fetch", "+refs/pull/*/head:refs/remotes/origin/pr/*"], cwd=repo)
        local_refspecs = git(["config", "--get-all", "remote.origin.fetch"], cwd=repo).stdout.strip().splitlines()
        has_pr_refspec = "+refs/pull/*/head:refs/remotes/origin/pr/*" in local_refspecs

        global_after = git(["config", "--global", "--list"], cwd=tmpdir, check=False).stdout
        global_untouched = (global_before == global_after)

        ok2 = has_pr_refspec and global_untouched
        lines.append(("PASS" if ok2 else "FAIL") +
                     ": local config contains PR refspec and global config is untouched")
        assert ok2, f"Trial {trial}: refspec missing or global config modified"

        # ── Step 3: git fetch origin creates tracking ref for PR ───────
        git(["fetch", "origin"], cwd=repo)
        pr1_sha = git(["rev-parse", "refs/remotes/origin/pr/1"], cwd=repo).stdout.strip()
        ok3 = (pr1_sha == sha_b)
        lines.append(("PASS" if ok3 else "FAIL") +
                     ": git fetch creates refs/remotes/origin/pr/1 pointing to commit B")
        assert ok3, f"Trial {trial}: expected origin/pr/1 at {sha_b}, got {pr1_sha}"

        # ── Step 4: git checkout pr/1 ──────────────────────────────────
        git(["checkout", "pr/1"], cwd=repo)
        checked_out_branch = git(["branch", "--show-current"], cwd=repo).stdout.strip()
        head_sha = git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()
        ok4 = (checked_out_branch == "pr/1") and (head_sha == sha_b)
        lines.append(("PASS" if ok4 else "FAIL") +
                     ": git checkout pr/1 switches to pr/1 at commit B")
        assert ok4, f"Trial {trial}: checkout failed: branch {checked_out_branch}, HEAD {head_sha}"

        # ── Step 5: worktree state matches commit B ───────────────────
        notes_text = pathlib.Path(repo, "notes.txt").read_text()
        has_todo = pathlib.Path(repo, "todo.txt").exists()
        ok5 = ("alpha\nbeta\n" in notes_text) and (not has_todo)
        lines.append(("PASS" if ok5 else "FAIL") +
                     ": worktree on pr/1 contains notes.txt and lacks todo.txt")
        assert ok5, f"Trial {trial}: worktree mismatch on pr/1"

    return lines


def main():
    results = []
    for trial in (1, 2):
        trial_lines = run_once(trial)
        results.append(f"=== Trial {trial} ===")
        results.extend(trial_lines)
        results.append("")

    ACTUAL.write_text("\n".join(results) + "\n")
    print("\n".join(results))
    print(f"All assertions passed. Output written to {ACTUAL}")


if __name__ == "__main__":
    main()
