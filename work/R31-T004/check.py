"""
R31-T004 check.py
=================
Verifies branch-and-remote-tracking semantics when pushing a topic branch
while main is the remote default branch.

Fixture (temporary, local only – no network):
  - repo:     a normal git repo with branch main (3 commits) + branch topic (at B)
  - bare.git: a local bare repo added as "origin" via file:// URL

Assertions (>= 3 meaningful state facts):
  1. refs/heads/main stays at commit C after pushing topic
  2. refs/remotes/origin/main stays at commit C after pushing topic
  3. bare repo HEAD still symrefs refs/heads/main (remote default unchanged)
  4. refs/remotes/origin/topic created and equals commit B
  5. topic's upstream is configured as refs/remotes/origin/topic
"""

import os
import subprocess
import tempfile
import pathlib

WORK_DIR = pathlib.Path(__file__).parent
ACTUAL   = WORK_DIR / "actual.txt"


def run(cmd, cwd, env=None):
    merged = {**os.environ, **(env or {})}
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, check=True, env=merged
    )


def git(args, cwd, env=None):
    return run(["git"] + args, cwd=cwd, env=env)


def run_once(trial: int, results: list):
    base_ts = 1_000_000_000

    env_a = {
        "GIT_AUTHOR_DATE":    f"{base_ts + 0} +0000",
        "GIT_COMMITTER_DATE": f"{base_ts + 0} +0000",
        "GIT_AUTHOR_NAME":    "Course Student",
        "GIT_AUTHOR_EMAIL":   "student@example.invalid",
        "GIT_COMMITTER_NAME": "Course Student",
        "GIT_COMMITTER_EMAIL":"student@example.invalid",
    }
    env_b = {**env_a,
        "GIT_AUTHOR_DATE":    f"{base_ts + 1} +0000",
        "GIT_COMMITTER_DATE": f"{base_ts + 1} +0000",
    }
    env_c = {**env_a,
        "GIT_AUTHOR_DATE":    f"{base_ts + 2} +0000",
        "GIT_COMMITTER_DATE": f"{base_ts + 2} +0000",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        repo = os.path.join(tmpdir, "repo")
        bare = os.path.join(tmpdir, "bare.git")

        # ── Initialise repo ──────────────────────────────────────────────
        git(["init", "--initial-branch=main", repo], cwd=tmpdir)
        cfg = ["config"]
        git(cfg + ["user.email", "student@example.invalid"], cwd=repo)
        git(cfg + ["user.name",  "Course Student"],          cwd=repo)

        # Commit A
        pathlib.Path(repo, "notes.txt").write_text("alpha\n")
        git(["add", "notes.txt"], cwd=repo)
        git(["commit", "-m", "A: add notes.txt"], cwd=repo, env=env_a)

        # Commit B – topic will point here
        pathlib.Path(repo, "notes.txt").write_text("alpha\nbeta\n")
        git(["add", "notes.txt"], cwd=repo)
        git(["commit", "-m", "B: append beta"], cwd=repo, env=env_b)
        sha_b = git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()
        git(["branch", "topic"], cwd=repo)   # topic at B

        # Commit C (only on main)
        pathlib.Path(repo, "todo.txt").write_text("one\n")
        git(["add", "todo.txt"], cwd=repo)
        git(["commit", "-m", "C: add todo.txt"], cwd=repo, env=env_c)
        sha_c = git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()

        # ── Bare remote ──────────────────────────────────────────────────
        git(["init", "--bare", "--initial-branch=main", bare], cwd=tmpdir)
        git(["remote", "add", "origin", f"file://{bare}"], cwd=repo)

        # Push main first (establish remote default)
        git(["push", "-u", "origin", "main"], cwd=repo)

        # Switch to topic and push with tracking
        git(["checkout", "topic"], cwd=repo)
        git(["push", "-u", "origin", "topic"], cwd=repo)

        # ── Assertions ───────────────────────────────────────────────────
        lines = []

        # 1. Local main still at C
        local_main = git(["rev-parse", "refs/heads/main"], cwd=repo).stdout.strip()
        ok1 = local_main == sha_c
        status1 = "PASS" if ok1 else "FAIL"
        lines.append(f"{status1}: refs/heads/main unchanged at commit C after topic push")
        assert ok1, f"Trial {trial}: local main moved! expected {sha_c}, got {local_main}"

        # 2. Remote-tracking main still at C
        rt_main = git(["rev-parse", "refs/remotes/origin/main"], cwd=repo).stdout.strip()
        ok2 = rt_main == sha_c
        status2 = "PASS" if ok2 else "FAIL"
        lines.append(f"{status2}: refs/remotes/origin/main unchanged at commit C after topic push")
        assert ok2, f"Trial {trial}: origin/main moved! expected {sha_c}, got {rt_main}"

        # 3. Bare repo HEAD still symrefs refs/heads/main
        bare_head = pathlib.Path(bare, "HEAD").read_text().strip()
        ok3 = bare_head == "ref: refs/heads/main"
        status3 = "PASS" if ok3 else "FAIL"
        lines.append(f"{status3}: bare repo HEAD symref still points to refs/heads/main")
        assert ok3, f"Trial {trial}: bare HEAD changed! got '{bare_head}'"

        # 4. origin/topic created and points to B
        rt_topic = git(["rev-parse", "refs/remotes/origin/topic"], cwd=repo).stdout.strip()
        ok4 = rt_topic == sha_b
        status4 = "PASS" if ok4 else "FAIL"
        lines.append(f"{status4}: refs/remotes/origin/topic created and points to commit B")
        assert ok4, f"Trial {trial}: origin/topic wrong! expected {sha_b}, got {rt_topic}"

        # 5. topic upstream configured as refs/remotes/origin/topic
        upstream = git(
            ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "topic@{upstream}"],
            cwd=repo
        ).stdout.strip()
        ok5 = upstream == "origin/topic"
        status5 = "PASS" if ok5 else "FAIL"
        lines.append(f"{status5}: topic upstream configured as refs/remotes/origin/topic")
        assert ok5, f"Trial {trial}: topic upstream wrong! got '{upstream}'"

        results.extend(lines)
        return lines


def main():
    results = []
    for trial in (1, 2):
        trial_lines = run_once(trial, [])
        results.append(f"=== Trial {trial} ===")
        results.extend(trial_lines)
        results.append("")

    ACTUAL.write_text("\n".join(results) + "\n")
    print("\n".join(results))
    print(f"All assertions passed. Output written to {ACTUAL}")


if __name__ == "__main__":
    main()
