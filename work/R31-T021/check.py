#!/usr/bin/env python3
"""Compare path and file:// clones using isolated local repositories."""
import json
import os
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent

def run(args, cwd=None, env=None):
    return subprocess.run(args, cwd=cwd, env=env, text=True, check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()

def verify_clone(root, url, label):
    dest = root / label
    run(["git", "clone", "--quiet", url, str(dest)])
    head = run(["git", "rev-parse", "HEAD"], dest)
    branch = run(["git", "branch", "--show-current"], dest)
    notes = (dest / "notes.txt").read_text()
    todo = (dest / "todo.txt").read_text()
    topic = run(["git", "rev-parse", "refs/remotes/origin/topic"], dest)
    assert branch == "main", branch
    assert notes == "alpha\nbeta\n" and todo == "one\n"
    assert topic == expected["topic"]
    assert run(["git", "status", "--porcelain"], dest) == ""
    return {"head": head, "branch": branch, "notes": notes, "todo": todo,
            "origin_topic": topic, "status": "clean"}

with tempfile.TemporaryDirectory(prefix="R31-T021-") as td:
    root = pathlib.Path(td)
    source = root / "source"
    source.mkdir()
    run(["git", "init", "-q", "-b", "main"], source)
    run(["git", "config", "user.name", "Course Student"], source)
    run(["git", "config", "user.email", "student@example.invalid"], source)
    (source / "notes.txt").write_text("alpha\n")
    run(["git", "add", "notes.txt"], source); run(["git", "commit", "-qm", "A"], source)
    (source / "notes.txt").write_text("alpha\nbeta\n")
    run(["git", "commit", "-qam", "B"], source)
    b = run(["git", "rev-parse", "HEAD"], source)
    run(["git", "branch", "topic", b], source)
    (source / "todo.txt").write_text("one\n")
    run(["git", "add", "todo.txt"], source); run(["git", "commit", "-qm", "C"], source)
    bare = root / "project.git"
    run(["git", "clone", "--quiet", "--bare", str(source), str(bare)])
    run(["git", "--git-dir", str(bare), "symbolic-ref", "HEAD", "refs/heads/main"])
    run(["git", "--git-dir", str(bare), "fetch", "--quiet", str(source), "refs/heads/topic:refs/heads/topic"])
    expected = {"topic": run(["git", "--git-dir", str(bare), "rev-parse", "refs/heads/topic"])}
    path_result = verify_clone(root, str(bare), "path-clone")
    file_result = verify_clone(root, bare.as_uri(), "file-url-clone")
    assert path_result["head"] == file_result["head"]
    assert path_result["origin_topic"] == file_result["origin_topic"]
    actual = {"path_clone": path_result, "file_url_clone": file_result,
              "source_commits": {"B": b, "C": run(["git", "rev-parse", "HEAD"], source)}}

versions = {"git": run(["git", "--version"]), "python": run(["python3", "--version"])}
(ROOT / "results.json").write_text(json.dumps({"inputs": {"branch": "main", "author": "Course Student <student@example.invalid>", "commits": ["A: notes.txt=alpha", "B: notes.txt+=beta", "C: todo.txt=one"], "clones": ["local path", "file:// URL"]}, "expected": "both clones have identical main HEAD, topic remote ref, files and clean worktree", "actual": actual, "tool_versions": versions}, indent=2) + "\n")
print(json.dumps(actual, indent=2))
