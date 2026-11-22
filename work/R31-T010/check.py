"""
R31-T010 check.py
=================
Verifies predictions and real Git state resulting from cloning a multi-branch
repository (client-p4 / Git Fusion workflow):

Predictions tested:
  1. Local branch: only refs/heads/main exists pointing to commit C;
     no local refs/heads/topic exists.
  2. Remote-tracking branch: refs/remotes/origin/topic exists and points
     to commit B.
  3. Working tree / HEAD: HEAD points to commit C; index and worktree are clean.
  4. Worktree contents: contains notes.txt ("alpha\nbeta\n") and todo.txt ("one\n").
  5. Branch listing: git branch -a reports * main and origin remotes.

Fixture (temporary, local only – no network):
  - repo: branch main, 3 commits (A, B, C), topic at B
  - bare.git: local bare repository acting as remote origin
  - clone: clean clone from bare.git via file:// URL
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
        repo, sha_a, sha_b, sha_c = make_fixture(tmpdir, base_ts)

        # Create bare origin repo with initial branch main
        bare = os.path.join(tmpdir, "bare.git")
        git(["init", "--bare", "--initial-branch=main", bare], cwd=tmpdir)
        git(["remote", "add", "origin", f"file://{bare}"], cwd=repo)
        git(["push", "origin", "main", "topic"], cwd=repo)

        # Execute: clone from bare remote
        clone_dir = os.path.join(tmpdir, "clone")
        git(["clone", f"file://{bare}", clone_dir], cwd=tmpdir)

        # ── Assert 1: local refs/heads/main exists; local topic does not ──
        local_main = git(["rev-parse", "refs/heads/main"], cwd=clone_dir).stdout.strip()
        local_topic = git(["rev-parse", "--verify", "refs/heads/topic"], cwd=clone_dir, check=False)
        ok1 = (local_main == sha_c) and (local_topic.returncode != 0)
        lines.append(("PASS" if ok1 else "FAIL") +
                     ": local refs/heads/main created at commit C and refs/heads/topic does not exist")
        assert ok1, f"Trial {trial}: local main or topic ref prediction failed"

        # ── Assert 2: remote tracking origin/topic exists at commit B ──
        rt_topic = git(["rev-parse", "refs/remotes/origin/topic"], cwd=clone_dir).stdout.strip()
        ok2 = (rt_topic == sha_b)
        lines.append(("PASS" if ok2 else "FAIL") +
                     ": remote tracking refs/remotes/origin/topic created and points to commit B")
        assert ok2, f"Trial {trial}: origin/topic prediction failed, got {rt_topic}, expected {sha_b}"

        # ── Assert 3: clone HEAD points to commit C; index/worktree clean ──
        head_sha = git(["rev-parse", "HEAD"], cwd=clone_dir).stdout.strip()
        status_out = git(["status", "--porcelain"], cwd=clone_dir).stdout.strip()
        ok3 = (head_sha == sha_c) and (status_out == "")
        lines.append(("PASS" if ok3 else "FAIL") +
                     ": clone HEAD points to commit C with a clean working tree and index")
        assert ok3, f"Trial {trial}: HEAD ({head_sha}) or status ({status_out}) mismatch"

        # ── Assert 4: worktree files match commit C ────────────────────
        notes_text = pathlib.Path(clone_dir, "notes.txt").read_text()
        todo_text = pathlib.Path(clone_dir, "todo.txt").read_text()
        ok4 = (notes_text == "alpha\nbeta\n") and (todo_text == "one\n")
        lines.append(("PASS" if ok4 else "FAIL") +
                     ": worktree files match commit C containing notes.txt and todo.txt")
        assert ok4, f"Trial {trial}: file contents mismatch in clone worktree"

        # ── Assert 5: git branch -a lists active main and remotes ───────
        branches = git(["branch", "-a"], cwd=clone_dir).stdout.strip()
        has_active_main = "* main" in branches
        has_origin_topic = "remotes/origin/topic" in branches
        has_origin_main = "remotes/origin/main" in branches
        ok5 = has_active_main and has_origin_topic and has_origin_main
        lines.append(("PASS" if ok5 else "FAIL") +
                     ": git branch -a lists active local main and remote tracking branches")
        assert ok5, f"Trial {trial}: git branch -a output mismatch: {branches}"

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
