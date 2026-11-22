"""
R31-T007 check.py
=================
Demonstrates and verifies the failure of `git merge --abort` when no merge
is in progress, and the corrected behaviour when a real conflict exists.

Fixture (temporary, local only – no network):
  - repo:  branch main, 3 commits (A, B, C), topic at B
  - Introduces a conflicting change on a whitespace branch to trigger a
    real merge conflict, confirming the precondition.

Assertions (>= 3 meaningful state facts):
  1. git merge --abort with no merge in progress exits non-zero
  2. The stderr mentions "MERGE_HEAD" or "no merge" (version-agnostic check)
  3. .git/MERGE_HEAD is absent before any merge is started
  4. .git/MERGE_HEAD is present during an active conflict
  5. git merge --abort during an active conflict exits zero (succeeds)
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

    # Commit B – topic at B
    pathlib.Path(repo, "notes.txt").write_text("alpha\nbeta\n")
    git(["add", "notes.txt"], cwd=repo)
    git(["commit", "-m", "B: append beta"], cwd=repo, env=env_b)
    git(["branch", "topic"], cwd=repo)

    # Commit C – only on main
    pathlib.Path(repo, "todo.txt").write_text("one\n")
    git(["add", "todo.txt"], cwd=repo)
    git(["commit", "-m", "C: add todo.txt"], cwd=repo, env=env_c)

    return repo, env_base


def run_once(trial: int):
    base_ts = 1_000_000_000
    lines   = []

    with tempfile.TemporaryDirectory() as tmpdir:
        repo, env_base = make_fixture(tmpdir, base_ts)

        # ── Assert 3: MERGE_HEAD absent before any merge ───────────────
        merge_head = pathlib.Path(repo, ".git", "MERGE_HEAD")
        ok3 = not merge_head.exists()
        lines.append(("PASS" if ok3 else "FAIL") +
                     ": .git/MERGE_HEAD absent before any merge is started")
        assert ok3, f"Trial {trial}: MERGE_HEAD existed before merge!"

        # ── Assert 1 & 2: abort with no merge in progress → non-zero ──
        result = git(["merge", "--abort"], cwd=repo, check=False)
        ok1 = result.returncode != 0
        lines.append(("PASS" if ok1 else "FAIL") +
                     ": git merge --abort with no merge in progress exits non-zero")
        assert ok1, f"Trial {trial}: expected non-zero exit, got 0"

        combined = (result.stderr + result.stdout).lower()
        ok2 = "merge_head" in combined or "no merge" in combined
        lines.append(("PASS" if ok2 else "FAIL") +
                     ': error output mentions MERGE_HEAD or "no merge"')
        assert ok2, f"Trial {trial}: unexpected error output: {result.stderr!r}"

        # ── Create a real conflict to test the repaired case ───────────
        # whitespace branch: change notes.txt differently
        env_w = {**env_base,
            "GIT_AUTHOR_DATE":    f"{base_ts + 3} +0000",
            "GIT_COMMITTER_DATE": f"{base_ts + 3} +0000",
        }
        git(["checkout", "-b", "whitespace"], cwd=repo)
        pathlib.Path(repo, "notes.txt").write_text("alpha\nbeta\ngamma\n")
        git(["add", "notes.txt"], cwd=repo)
        git(["commit", "-m", "W: add gamma on whitespace branch"], cwd=repo, env=env_w)

        # Back to main, make a conflicting change
        env_m = {**env_base,
            "GIT_AUTHOR_DATE":    f"{base_ts + 4} +0000",
            "GIT_COMMITTER_DATE": f"{base_ts + 4} +0000",
        }
        git(["checkout", "main"], cwd=repo)
        pathlib.Path(repo, "notes.txt").write_text("alpha\nbeta\ndelta\n")
        git(["add", "notes.txt"], cwd=repo)
        git(["commit", "-m", "M: add delta on main"], cwd=repo, env=env_m)

        # Trigger the conflict (check=False since merge will exit non-zero)
        git(["merge", "whitespace"], cwd=repo, check=False)

        # ── Assert 4: MERGE_HEAD now present ──────────────────────────
        ok4 = merge_head.exists()
        lines.append(("PASS" if ok4 else "FAIL") +
                     ": .git/MERGE_HEAD present during active merge conflict")
        assert ok4, f"Trial {trial}: MERGE_HEAD missing during conflict!"

        # ── Assert 5: abort during active conflict exits 0 ────────────
        abort_result = git(["merge", "--abort"], cwd=repo, check=False)
        ok5 = abort_result.returncode == 0
        lines.append(("PASS" if ok5 else "FAIL") +
                     ": git merge --abort during active conflict exits zero (success)")
        assert ok5, (f"Trial {trial}: abort failed: "
                     f"rc={abort_result.returncode} {abort_result.stderr!r}")

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
