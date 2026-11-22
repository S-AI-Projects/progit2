"""
R31-T005 check.py
=================
Verifies git stash push path-quoting behaviour with filenames and directories
that contain spaces.

Fixture (temporary, local only – no network):
  - repo: normal git repo, branch main, 3 commits (A, B, C), topic at B
  - "release notes.txt"  -- a tracked file modified after commit C
  - "sample data/"       -- an untracked directory created after commit C

Assertions (>= 3 meaningful state facts):
  1. After `git stash push -- "release notes.txt"`, the file is absent from diff
  2. After `git stash pop`, the file is restored with its correct content
  3. After `git stash push -u -- "sample data/"`, that dir is gone from worktree
  4. Stash list is empty after the pop (stash was consumed, not just applied)
  5. Working tree has no staged changes after the pop
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
    """Create the standard 3-commit repo fixture."""
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

    # Commit B – topic branch will point here
    pathlib.Path(repo, "notes.txt").write_text("alpha\nbeta\n")
    git(["add", "notes.txt"], cwd=repo)
    git(["commit", "-m", "B: append beta"], cwd=repo, env=env_b)
    git(["branch", "topic"], cwd=repo)

    # Commit C – only on main
    pathlib.Path(repo, "todo.txt").write_text("one\n")
    git(["add", "todo.txt"], cwd=repo)
    git(["commit", "-m", "C: add todo.txt"], cwd=repo, env=env_c)

    return repo


def run_once(trial: int):
    base_ts = 1_000_000_000
    lines   = []

    with tempfile.TemporaryDirectory() as tmpdir:
        repo = make_fixture(tmpdir, base_ts)

        # ── Set up space-containing paths ─────────────────────────────
        release_notes = pathlib.Path(repo, "release notes.txt")
        sample_data   = pathlib.Path(repo, "sample data")
        sample_file   = sample_data / "data.csv"

        # Create and commit "release notes.txt" so it is tracked
        release_notes.write_text("v1.0 release\n")
        git(["add", "release notes.txt"], cwd=repo)
        git(["commit", "-m", "D: add release notes"], cwd=repo)

        # Modify "release notes.txt" (dirty tracked file)
        release_notes.write_text("v1.0 release\nv1.1 pending\n")

        # Create untracked "sample data/" directory
        sample_data.mkdir()
        sample_file.write_text("col1,col2\n1,2\n")

        # ── Assert 1: stash the space-containing tracked file ─────────
        git(["stash", "push", "--", "release notes.txt"], cwd=repo)

        diff_out = git(["diff", "--name-only"], cwd=repo).stdout
        ok1 = "release notes.txt" not in diff_out
        lines.append(("PASS" if ok1 else "FAIL") +
                     ': "release notes.txt" absent from diff after quoted stash push')
        assert ok1, f"Trial {trial}: file still in diff after stash: {diff_out!r}"

        # ── Assert 2: pop restores the file with correct content ───────
        git(["stash", "pop"], cwd=repo)
        content = release_notes.read_text()
        ok2 = "v1.1 pending" in content
        lines.append(("PASS" if ok2 else "FAIL") +
                     ': "release notes.txt" restored with correct content after stash pop')
        assert ok2, f"Trial {trial}: file content wrong after pop: {content!r}"

        # ── Assert 3: stash untracked space-containing directory ───────
        git(["stash", "push", "-u", "--", "sample data/"], cwd=repo)
        ok3 = not sample_data.exists()
        lines.append(("PASS" if ok3 else "FAIL") +
                     ': "sample data/" directory removed from working tree after -u stash')
        assert ok3, f"Trial {trial}: sample data/ still exists after stash -u"

        # ── Assert 4: stash list is empty after pop ────────────────────
        # pop the directory stash first
        git(["stash", "pop"], cwd=repo)
        stash_list = git(["stash", "list"], cwd=repo).stdout.strip()
        ok4 = stash_list == ""
        lines.append(("PASS" if ok4 else "FAIL") +
                     ": stash list is empty after stash pop")
        assert ok4, f"Trial {trial}: stash list not empty: {stash_list!r}"

        # ── Assert 5: no staged changes after pop ─────────────────────
        status = git(["status", "--porcelain"], cwd=repo).stdout
        staged = [l for l in status.splitlines() if l and l[0] not in (' ', '?')]
        ok5 = len(staged) == 0
        lines.append(("PASS" if ok5 else "FAIL") +
                     ": working tree has no staged changes after stash pop")
        assert ok5, f"Trial {trial}: unexpected staged changes: {staged}"

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
