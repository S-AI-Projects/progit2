import os, subprocess, sys, tempfile
from pathlib import Path

ENV = {**os.environ,
       "GIT_AUTHOR_NAME": "Course Student", "GIT_AUTHOR_EMAIL": "student@example.invalid",
       "GIT_COMMITTER_NAME": "Course Student", "GIT_COMMITTER_EMAIL": "student@example.invalid"}
LOG = []

def run(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, env=ENV,
                          capture_output=True, text=True, check=check)

def git(cwd, *args):
    return run(cwd, *args).stdout.rstrip("\n")

def expect(label, actual, expected):
    LOG.append(f"{label}\n  expected: {expected!r}\n  actual:   {actual!r}")
    assert actual == expected, f"FAILED: {label}: expected {expected!r}, got {actual!r}"

def run_once():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)

        # 1) A second LOCAL bare repository acts as the submodule's remote (no public remote)
        sub_bare = root / "sub.git"
        git(root, "init", "--bare", "-b", "main", str(sub_bare))
        seed = root / "seed"
        seed.mkdir()
        git(seed, "init", "-b", "main")
        (seed / "lib.txt").write_text("library\n")
        git(seed, "add", "lib.txt"); git(seed, "commit", "-m", "lib v1")
        sub_head = git(seed, "rev-parse", "HEAD")
        git(seed, "push", sub_bare.as_uri(), "main")
        url = sub_bare.as_uri()
        expect("submodule remote is a local file:// URL", url.startswith("file:///"), True)

        # 2) Superproject: commits A, B, C on main and branch topic at B
        repo = root / "super"
        repo.mkdir()
        git(repo, "init", "-b", "main")
        (repo / "notes.txt").write_text("alpha\n")
        git(repo, "add", "notes.txt"); git(repo, "commit", "-m", "A")
        with open(repo / "notes.txt", "a") as f: f.write("beta\n")
        git(repo, "commit", "-am", "B")
        b = git(repo, "rev-parse", "HEAD")
        (repo / "todo.txt").write_text("one\n")
        git(repo, "add", "todo.txt"); git(repo, "commit", "-m", "C")
        c = git(repo, "rev-parse", "HEAD")
        git(repo, "branch", "topic", b)

        # 3) Current branch is topic; default branch is main
        git(repo, "switch", "topic")
        expect("current branch is topic", git(repo, "symbolic-ref", "--short", "HEAD"), "topic")
        expect("main is at C before", git(repo, "rev-parse", "main"), c)
        expect("topic is at B before", git(repo, "rev-parse", "topic"), b)

        # 4) THE OPERATION: git submodule add (file:// needs protocol.file.allow=always)
        git(repo, "-c", "protocol.file.allow=always", "submodule", "add", url, "libs/sub")

        # Facts: what changed
        expect("add only stages: HEAD of topic did not move yet", git(repo, "rev-parse", "topic"), b)
        expect("main (unrelated ref) did not move", git(repo, "rev-parse", "main"), c)
        expect("still on topic", git(repo, "symbolic-ref", "--short", "HEAD"), "topic")
        expect("status shows .gitmodules and the submodule staged",
               git(repo, "status", "--short"), "A  .gitmodules\nA  libs/sub")
        mode, sha = git(repo, "ls-files", "-s", "libs/sub").split()[:2]
        expect("index stores libs/sub as a gitlink (mode 160000)", mode, "160000")
        expect("gitlink points at the submodule's commit", sha, sub_head)
        expect(".gitmodules records the local URL",
               git(repo, "config", "-f", ".gitmodules", "submodule.libs/sub.url"), url)
        expect(".gitmodules records no branch (none requested)",
               run(repo, "config", "-f", ".gitmodules", "submodule.libs/sub.branch", check=False).returncode != 0, True)
        expect("submodule's origin is the local bare repo",
               git(repo / "libs" / "sub", "remote", "get-url", "origin"), url)
        expect("submodule checked out the REMOTE's default branch (main), not 'topic'",
               git(repo / "libs" / "sub", "symbolic-ref", "--short", "HEAD"), "main")

        # 5) Commit on topic: only topic moves
        git(repo, "commit", "-m", "add submodule")
        new_topic = git(repo, "rev-parse", "topic")
        expect("topic advanced (intended ref changed)", new_topic != b, True)
        expect("topic's parent is B", git(repo, "rev-parse", "topic^"), b)
        expect("main still at C (unrelated ref fixed)", git(repo, "rev-parse", "main"), c)
        expect("main's tree has no .gitmodules",
               ".gitmodules" in git(repo, "ls-tree", "-r", "--name-only", "main").split("\n"), False)
        expect("topic's tree has .gitmodules",
               ".gitmodules" in git(repo, "ls-tree", "-r", "--name-only", "topic").split("\n"), True)
        expect("status clean after commit", git(repo, "status", "--short"), "")
        return git(repo, "ls-tree", "-r", "--name-only", "topic")

if __name__ == "__main__":
    t1, t2 = run_once(), run_once()
    assert t1 == t2, "results differ between runs"
    ver = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip()
    out = Path(__file__).parent / "results.txt"
    out.write_text(f"Tools: {ver}; Python {sys.version.split()[0]}\n\n" + "\n".join(LOG) + "\n")
    print("ALL CHECKS PASSED (ran twice). Results saved to", out)
