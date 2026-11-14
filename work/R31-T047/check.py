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

        # Local repo: commits A, B, C on main and branch topic at B
        repo = root / "repo"
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

        # The "server": a second LOCAL bare repository, reached through a file:// URL
        server = root / "server.git"
        git(root, "init", "--bare", "-b", "main", str(server))
        url = server.as_uri()
        expect("remote is a local file:// URL", url.startswith("file:///"), True)
        git(repo, "push", url, "main", "topic")     # push by URL: creates NO remote-tracking refs locally
        server_main = git(server, "rev-parse", "refs/heads/main")
        server_topic = git(server, "rev-parse", "refs/heads/topic")
        expect("server main is C", server_main, c)
        expect("server topic is B", server_topic, b)

        # The guide's first step: git remote add origin <url>
        git(repo, "remote", "add", "origin", url)
        expect("git remote add wrote the URL", git(repo, "config", "--get", "remote.origin.url"), url)
        expect("git remote add wrote the DEFAULT fetch refspec (refs/heads/* -> refs/remotes/origin/*)",
               git(repo, "config", "--get", "remote.origin.fetch"), "+refs/heads/*:refs/remotes/origin/*")

        # VIOLATED PRECONDITION: no `git fetch` yet, so refs/remotes/origin/* does not exist
        expect("no remote-tracking refs exist yet", git(repo, "for-each-ref", "refs/remotes"), "")
        bad = run(repo, "log", "origin/main", check=False)
        expect("BAD CASE: `git log origin/main` exits non-zero (command not applicable yet)", bad.returncode != 0, True)
        expect("BAD CASE: it printed no commits", bad.stdout, "")
        expect("BAD CASE: origin/main cannot be resolved",
               run(repo, "rev-parse", "--verify", "--quiet", "origin/main", check=False).returncode != 0, True)
        expect("failing command changed nothing: local main still C", git(repo, "rev-parse", "main"), c)
        expect("failing command changed nothing: local topic still B", git(repo, "rev-parse", "topic"), b)

        # SMALLEST CORRECTION: `git fetch origin` (not pull: pull would also merge)
        fx = run(repo, "fetch", "origin")
        expect("REPAIR: git fetch origin succeeds (exit 0)", fx.returncode, 0)
        expect("fetch wrote refs/remotes/origin/main = server's main",
               git(repo, "rev-parse", "refs/remotes/origin/main"), server_main)
        expect("fetch wrote refs/remotes/origin/topic = server's topic",
               git(repo, "rev-parse", "refs/remotes/origin/topic"), server_topic)
        names = git(repo, "for-each-ref", "--format=%(refname)", "refs/remotes").split("\n")
        expect("origin/main and origin/topic exist as remote-tracking refs",
               {"refs/remotes/origin/main", "refs/remotes/origin/topic"} <= set(names), True)
        expect("no other branch refs appeared (newer Git may also add origin/HEAD, which is fine)",
               set(names) - {"refs/remotes/origin/HEAD"}, {"refs/remotes/origin/main", "refs/remotes/origin/topic"})

        good = run(repo, "log", "--format=%s", "origin/main", check=False)
        expect("REPAIRED: `git log origin/main` now succeeds (exit 0)", good.returncode, 0)
        expect("REPAIRED: it lists C, B, A", good.stdout.strip(), "C\nB\nA")

        # Fetch is read-only for local work: nothing local moved
        expect("local main untouched by fetch", git(repo, "rev-parse", "main"), c)
        expect("local topic untouched by fetch", git(repo, "rev-parse", "topic"), b)
        expect("HEAD still on main", git(repo, "symbolic-ref", "--short", "HEAD"), "main")
        expect("working tree clean", git(repo, "status", "--short"), "")
        return git(repo, "log", "--format=%s", "origin/main")

if __name__ == "__main__":
    a, b = run_once(), run_once()
    assert a == b
    ver = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip()
    out = Path(__file__).parent / "results.txt"
    out.write_text(f"Tools: {ver}; Python {sys.version.split()[0]}\n\n" + "\n".join(LOG) + "\n")
    print("ALL CHECKS PASSED (ran twice). Results saved to", out)