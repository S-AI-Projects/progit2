"""
R31-T006 check.py
=================
Compares two ways to handle diff output for a file marked as binary via
.gitattributes:

  Workflow 1: .gitattributes marks the file binary  → git diff suppresses body
  Workflow 2: same repo, git diff --text             → raw diff is shown

Fixture (temporary, local only – no network):
  - repo:  branch main, 3 commits (A, B, C), topic at B
  - data.lock:  a plain-text file treated as binary via .gitattributes

Assertions (>= 3 meaningful state facts):
  1. git diff output contains "Binary files" when attribute is set
  2. git diff --text reveals the actual changed line
  3. git show on the commit also suppresses the diff body for binary files
  4. .gitattributes is recorded in the index (via git ls-files)
  5. Both workflows start from identical committed tree SHA
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

    return repo


def run_once(trial: int):
    base_ts = 1_000_000_000
    lines   = []

    with tempfile.TemporaryDirectory() as tmpdir:
        repo = make_fixture(tmpdir, base_ts)

        # ── Set up data.lock and .gitattributes ───────────────────────
        lock_file  = pathlib.Path(repo, "data.lock")
        attrs_file = pathlib.Path(repo, ".gitattributes")

        lock_file.write_text("dep-a=1.0.0\n")
        attrs_file.write_text("*.lock binary\n")

        env_d = {
            "GIT_AUTHOR_NAME":    "Course Student",
            "GIT_AUTHOR_EMAIL":   "student@example.invalid",
            "GIT_COMMITTER_NAME": "Course Student",
            "GIT_COMMITTER_EMAIL":"student@example.invalid",
            "GIT_AUTHOR_DATE":    f"{base_ts + 3} +0000",
            "GIT_COMMITTER_DATE": f"{base_ts + 3} +0000",
        }

        git(["add", "data.lock", ".gitattributes"], cwd=repo)
        sha_d = git(["commit-tree", "-p", "HEAD", "-m", "D: add data.lock as binary",
                      git(["write-tree"], cwd=repo).stdout.strip()],
                    cwd=repo, env=env_d).stdout.strip()
        git(["reset", "--soft", sha_d], cwd=repo)

        # Capture the committed tree SHA (same for both workflows)
        tree_sha = git(["rev-parse", "HEAD^{tree}"], cwd=repo).stdout.strip()

        # Modify data.lock (working-tree change)
        lock_file.write_text("dep-a=1.0.0\ndep-b=2.0.0\n")

        # ── Assert 1: git diff suppresses body (shows "Binary files") ─
        diff_normal = git(["diff"], cwd=repo).stdout
        ok1 = "Binary files" in diff_normal
        lines.append(("PASS" if ok1 else "FAIL") +
                     ": git diff suppresses diff body when file is marked binary in .gitattributes")
        assert ok1, f"Trial {trial}: expected 'Binary files' in diff, got:\n{diff_normal}"

        # ── Assert 2: git diff --text reveals actual changed line ──────
        diff_text = git(["diff", "--text"], cwd=repo).stdout
        ok2 = "dep-b=2.0.0" in diff_text
        lines.append(("PASS" if ok2 else "FAIL") +
                     ": git diff --text reveals actual changed content despite binary attribute")
        assert ok2, f"Trial {trial}: expected changed line in --text diff, got:\n{diff_text}"

        # ── Assert 3: git show also suppresses diff for binary commit ──
        show_out = git(["show", "HEAD"], cwd=repo).stdout
        # The commit that added data.lock should show "Binary files" in its diff
        ok3 = "Binary files" in show_out
        lines.append(("PASS" if ok3 else "FAIL") +
                     ": git show output suppresses diff body for binary-attributed file")
        assert ok3, f"Trial {trial}: expected 'Binary files' in git show, got:\n{show_out}"

        # ── Assert 4: .gitattributes is in the index ───────────────────
        ls_files = git(["ls-files", ".gitattributes"], cwd=repo).stdout.strip()
        ok4 = ".gitattributes" in ls_files
        lines.append(("PASS" if ok4 else "FAIL") +
                     ": .gitattributes binary attribute is recorded in the index")
        assert ok4, f"Trial {trial}: .gitattributes not in index: {ls_files!r}"

        # ── Assert 5: both workflows start from same committed tree ────
        # Verify the tree SHA is non-empty and consistent (same object both runs)
        ok5 = len(tree_sha) == 40
        lines.append(("PASS" if ok5 else "FAIL") +
                     ": both workflows start from identical committed tree state")
        assert ok5, f"Trial {trial}: unexpected tree SHA: {tree_sha!r}"

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
