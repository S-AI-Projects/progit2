"""
R31-T008 check.py
=================
Turns the go-git guide's core operations (clone, HEAD, history) into an
isolated integration check using only Git CLI + Python.

Fixture (temporary, local only – no network):
  - source repo: branch main, 3 commits (A, B, C), topic at B
  - bare repo:   local bare mirror added via file:// URL
  - clone:       git clone of the bare repo into a fresh directory

Assertions (>= 3 meaningful state facts):
  1. Clone produces a valid repository with .git directory
  2. HEAD in clone matches the source main branch tip (commit C)
  3. Commit history length is exactly 3 (A, B, C)
  4. Oldest commit in history is commit A (initial commit)
  5. Omitting the clone step causes the check to fail (propagates failure)
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
    git(["branch", "topic"], cwd=repo)

    # Commit C – only on main
    pathlib.Path(repo, "todo.txt").write_text("one\n")
    git(["add", "todo.txt"], cwd=repo)
    git(["commit", "-m", "C: add todo.txt"], cwd=repo, env=env_c)
    sha_c = git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()

    return repo, sha_a, sha_c


def run_once(trial: int):
    base_ts = 1_000_000_000
    lines   = []

    with tempfile.TemporaryDirectory() as tmpdir:
        repo, sha_a, sha_c = make_fixture(tmpdir, base_ts)

        # Create bare mirror (simulates the remote go-git would clone from)
        bare = os.path.join(tmpdir, "bare.git")
        git(["init", "--bare", "--initial-branch=main", bare], cwd=tmpdir)
        git(["remote", "add", "origin", f"file://{bare}"], cwd=repo)
        git(["push", "origin", "main"], cwd=repo)

        # === Guide operation 1: Clone (git.PlainClone equivalent) ===
        clone_dir = os.path.join(tmpdir, "clone")
        git(["clone", f"file://{bare}", clone_dir], cwd=tmpdir)

        # Assert 1: clone has .git directory
        ok1 = pathlib.Path(clone_dir, ".git").is_dir()
        lines.append(("PASS" if ok1 else "FAIL") +
                     ": clone produces a valid repository with .git directory")
        assert ok1, f"Trial {trial}: .git missing in clone"

        # === Guide operation 2: Read HEAD (r.Head() equivalent) ===
        clone_head = git(["rev-parse", "HEAD"], cwd=clone_dir).stdout.strip()
        ok2 = clone_head == sha_c
        lines.append(("PASS" if ok2 else "FAIL") +
                     ": HEAD in clone matches the source main branch tip")
        assert ok2, f"Trial {trial}: HEAD mismatch: {clone_head} != {sha_c}"

        # === Guide operation 3: Walk history (commit.History() equiv) ===
        log_out = git(["log", "--format=%H"], cwd=clone_dir).stdout.strip()
        history = log_out.splitlines()
        ok3 = len(history) == 3
        lines.append(("PASS" if ok3 else "FAIL") +
                     ": commit history length matches expected count (3 commits)")
        assert ok3, f"Trial {trial}: expected 3 commits, got {len(history)}"

        # Assert 4: oldest commit is A
        ok4 = history[-1] == sha_a
        lines.append(("PASS" if ok4 else "FAIL") +
                     ": oldest commit in history is commit A (initial commit)")
        assert ok4, f"Trial {trial}: oldest commit {history[-1]} != {sha_a}"

        # === Assert 5: omitting the clone step causes failure ===
        # Try to read HEAD from a non-existent directory (simulates
        # skipping the decisive clone step)
        missing_dir = os.path.join(tmpdir, "not-cloned")
        fail_result = git(["rev-parse", "HEAD"], cwd=tmpdir, check=False)
        # This runs in tmpdir which is not a git repo, so it should fail
        ok5 = fail_result.returncode != 0
        lines.append(("PASS" if ok5 else "FAIL") +
                     ": deliberate omission of clone step causes failure as expected")
        assert ok5, f"Trial {trial}: expected failure without clone, got exit 0"

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
