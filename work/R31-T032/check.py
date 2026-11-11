
import os
import subprocess
import tempfile
import json
import platform
import sys
from pathlib import Path


AUTHOR = {
    "GIT_AUTHOR_NAME": "Course Student",
    "GIT_AUTHOR_EMAIL": "student@example.invalid",
    "GIT_COMMITTER_NAME": "Course Student",
    "GIT_COMMITTER_EMAIL": "student@example.invalid",
}


def git(repo, *args):
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        env={**os.environ, **AUTHOR},
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def main():
    with tempfile.TemporaryDirectory(prefix="refspec-") as temp:
        root = Path(temp)
        local = root / "local"
        remote = root / "remote.git"

        local.mkdir()

        # Create the local repository.
        git(local, "init", "-b", "main")
        git(local, "config", "user.name", "Course Student")
        git(local, "config", "user.email", "student@example.invalid")

        # Commit A: create notes.txt.
        (local / "notes.txt").write_text("alpha\n")
        git(local, "add", "notes.txt")
        git(local, "commit", "-m", "A: add alpha")

        commit_a = git(local, "rev-parse", "HEAD")

        # Commit B: append beta.
        with (local / "notes.txt").open("a") as file:
            file.write("beta\n")

        git(local, "add", "notes.txt")
        git(local, "commit", "-m", "B: add beta")

        commit_b = git(local, "rev-parse", "HEAD")

        # Create topic at B.
        git(local, "branch", "topic", commit_b)

        # Commit C: create todo.txt.
        (local / "todo.txt").write_text("one\n")
        git(local, "add", "todo.txt")
        git(local, "commit", "-m", "C: add todo")

        commit_c = git(local, "rev-parse", "HEAD")

        # Create a second local bare repository.
        git(root, "clone", "--bare", str(local), str(remote))

        # Capture state before adding the remote.
        head_before = git(local, "symbolic-ref", "HEAD")
        main_before = git(local, "rev-parse", "refs/heads/main")
        topic_before = git(local, "rev-parse", "refs/heads/topic")
        index_before = git(local, "ls-files", "--stage")
        status_before = git(local, "status", "--porcelain")
        files_before = {
            "notes.txt": (local / "notes.txt").read_text(),
            "todo.txt": (local / "todo.txt").read_text(),
        }

        check(main_before == commit_c, "main points to commit C")
        check(topic_before == commit_b, "topic points to commit B")
        check(commit_a != commit_b != commit_c, "A, B and C are distinct commits")

        # Add the bare repository as origin.
        remote_url = remote.resolve().as_uri()
        git(local, "remote", "add", "origin", remote_url)

        # Check the configured fetch refspec.
        fetch_config = git(
            local, "config", "--get", "remote.origin.fetch"
        )
        check(
            fetch_config == "+refs/heads/*:refs/remotes/origin/*",
            "origin has the default fetch refspec",
        )

        # remote add must not create remote-tracking refs.
        remote_refs_after_add = git(
            local, "for-each-ref", "--format=%(refname)",
            "refs/remotes/origin"
        )
        check(
            remote_refs_after_add == "",
            "remote add creates no remote-tracking refs",
        )

        # Check local Git state did not change.
        check(
            git(local, "symbolic-ref", "HEAD") == head_before,
            "HEAD is unchanged after remote add",
        )
        check(
            git(local, "rev-parse", "refs/heads/main") == main_before,
            "main is unchanged after remote add",
        )
        check(
            git(local, "rev-parse", "refs/heads/topic") == topic_before,
            "topic is unchanged after remote add",
        )
        check(
            git(local, "ls-files", "--stage") == index_before,
            "index is unchanged after remote add",
        )
        check(
            git(local, "status", "--porcelain") == status_before,
            "working tree status is unchanged after remote add",
        )
        check(
            files_before == {
                "notes.txt": (local / "notes.txt").read_text(),
                "todo.txt": (local / "todo.txt").read_text(),
            },
            "working-tree file contents are unchanged",
        )

        print("\nRunning git fetch origin...")
        git(local, "fetch", "origin")

        # Fetch creates remote-tracking refs.
        origin_main = git(local, "rev-parse", "refs/remotes/origin/main")
        origin_topic = git(local, "rev-parse", "refs/remotes/origin/topic")

        check(origin_main == commit_c, "origin/main points to commit C")
        check(origin_topic == commit_b, "origin/topic points to commit B")

        # Fetch does not move local branches or change the working tree.
        check(
            git(local, "rev-parse", "refs/heads/main") == main_before,
            "local main remains unchanged after fetch",
        )
        check(
            git(local, "rev-parse", "refs/heads/topic") == topic_before,
            "local topic remains unchanged after fetch",
        )
        check(
            git(local, "symbolic-ref", "HEAD") == head_before,
            "HEAD remains unchanged after fetch",
        )
        check(
            git(local, "ls-files", "--stage") == index_before,
            "index remains unchanged after fetch",
        )
        check(
            git(local, "status", "--porcelain") == status_before,
            "working tree remains clean after fetch",
        )


        evidence = {
            "task": "R31-T032",
            "scenario": {
                "commits": {
                    "A": commit_a,
                    "B": commit_b,
                    "C": commit_c,
                },
                "branches": {
                    "main": commit_c,
                    "topic": commit_b,
                },
                "remote": "local bare repository using file://",
                "fetch_refspec": "+refs/heads/*:refs/remotes/origin/*",
            },
            "expected_results": {
                "after_remote_add": "No remote-tracking refs created",
                "after_fetch": {
                    "origin/main": commit_c,
                    "origin/topic": commit_b,
                },
                "local_branches_unchanged": True,
                "head_unchanged": True,
                "index_unchanged": True,
                "working_tree_clean": True,
            },
            "actual_results": {
                "origin/main": origin_main,
                "origin/topic": origin_topic,
                "head": git(local, "symbolic-ref", "HEAD"),
                "main": git(local, "rev-parse", "refs/heads/main"),
                "topic": git(local, "rev-parse", "refs/heads/topic"),
                "working_tree": git(local, "status", "--porcelain"),
            },
            "tool_versions": {
                "python": platform.python_version(),
                "git": git(local, "--version"),
            },
            "result": "PASS",
        }

        evidence_path = Path(__file__).resolve().parent / "evidence.json"
        evidence_path.write_text(
            json.dumps(evidence, indent=2) + "\n"
        )
        print(f"Evidence saved to {evidence_path}")
print("\nAll refspec checks passed!")


if __name__ == "__main__":
    main()
