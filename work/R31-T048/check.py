import os, subprocess, sys, tempfile
from pathlib import Path

ENV = {**os.environ,
       "GIT_AUTHOR_NAME": "Course Student", "GIT_AUTHOR_EMAIL": "student@example.invalid",
       "GIT_COMMITTER_NAME": "Course Student", "GIT_COMMITTER_EMAIL": "student@example.invalid"}
LOG = []

def run(cwd, *args, check=True):
    # check=True: any failing child git command raises CalledProcessError (failure is propagated)
    return subprocess.run(["git", *args], cwd=cwd, env=ENV,
                          capture_output=True, text=True, check=check)

def git(cwd, *args):
    return run(cwd, *args).stdout.rstrip("\n")

def expect(label, actual, expected):
    LOG.append(f"{label}\n  expected: {expected!r}\n  actual:   {actual!r}")
    assert actual == expected, f"FAILED: {label}: expected {expected!r}, got {actual!r}"

def scenario(omit_clone=False):
    """The guide's shell sequence:  git clone <url>  ->  git remote  (-v).
    Runs entirely inside a temporary directory that is removed afterwards.
    Returns the path of that directory so the caller can check it was cleaned up."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        tmp_path = root

        # Source repo: commits A, B, C on main and branch topic at B
        src = root / "src"
        src.mkdir()
        git(src, "init", "-b", "main")
        (src / "notes.txt").write_text("alpha\n")
        git(src, "add", "notes.txt"); git(src, "commit", "-m", "A")
        with open(src / "notes.txt", "a") as f: f.write("beta\n")
        git(src, "commit", "-am", "B")
        b = git(src, "rev-parse", "HEAD")
        (src / "todo.txt").write_text("one\n")
        git(src, "add", "todo.txt"); git(src, "commit", "-m", "C")
        c = git(src, "rev-parse", "HEAD")
        git(src, "branch", "topic", b)

        # The "server": a second LOCAL bare repository, reached through a file:// URL
        server = root / "server.git"
        git(root, "init", "--bare", "-b", "main", str(server))
        url = server.as_uri()
        expect("remote is a local file:// URL", url.startswith("file:///"), True)
        git(src, "push", url, "main", "topic")
        expect("server main is C", git(server, "rev-parse", "refs/heads/main"), c)
        expect("server topic is B", git(server, "rev-parse", "refs/heads/topic"), b)

        # --- The guide's sequence ---------------------------------------------------
        work = root / "ticgit"
        if omit_clone:
            # DELIBERATE OMISSION of the decisive command (git clone): just make an empty repo instead
            work.mkdir()
            git(work, "init", "-b", "main")
        else:
            git(root, "clone", url, "ticgit")                 # $ git clone <url> ticgit

        # $ git remote
        expect("`git remote` lists exactly: origin", git(work, "remote"), "origin")

        # $ git remote -v
        verbose = git(work, "remote", "-v").split("\n")
        expect("`git remote -v` shows the fetch URL", f"origin\t{url} (fetch)" in verbose, True)
        expect("`git remote -v` shows the push URL", f"origin\t{url} (push)" in verbose, True)

        # --- State facts that make the clone observable ------------------------------
        expect("clone wrote the default fetch refspec",
               git(work, "config", "--get", "remote.origin.fetch"), "+refs/heads/*:refs/remotes/origin/*")
        expect("origin/main equals the server's main (C)", git(work, "rev-parse", "origin/main"), c)
        expect("origin/topic equals the server's topic (B)", git(work, "rev-parse", "origin/topic"), b)
        expect("local main tracks origin/main",
               git(work, "rev-parse", "--abbrev-ref", "main@{upstream}"), "origin/main")
        expect("clone made NO local topic branch (only origin/topic)",
               git(work, "branch", "--list", "topic"), "")
        expect("checked-out branch is main", git(work, "symbolic-ref", "--short", "HEAD"), "main")
        expect("working tree clean", git(work, "status", "--short"), "")
    return tmp_path

def main():
    # 1) The guide, executed for real
    p1 = scenario()
    expect("temporary directory was cleaned up (run 1)", p1.exists(), False)
    p2 = scenario()
    expect("temporary directory was cleaned up (run 2)", p2.exists(), False)
    expect("each run used its own isolated directory", p1 != p2, True)

    # 2) A failing child command is propagated, not swallowed
    with tempfile.TemporaryDirectory() as d:
        try:
            git(Path(d), "remote", "show", "no-such-remote")      # not a repo -> git exits non-zero
            propagated = False
        except subprocess.CalledProcessError as e:
            propagated = e.returncode != 0
    expect("a failing child command raises CalledProcessError (non-zero exit propagated)", propagated, True)

    # 3) The test FAILS when the guide's decisive command (git clone) is deliberately omitted
    try:
        scenario(omit_clone=True)
        failed = False
    except AssertionError:
        failed = True
    expect("OMISSION TEST: leaving out `git clone` makes the check FAIL", failed, True)

def mutation_main():
    """Used only by the exit-code demo: runs the scenario WITHOUT git clone and lets the failure escape."""
    scenario(omit_clone=True)

if __name__ == "__main__":
    if "--omit-clone" in sys.argv:
        mutation_main()          # an AssertionError escapes -> Python exits with a non-zero status
    else:
        main()
        # Prove the process-level contract: the omitted-clone run exits non-zero
        r = subprocess.run([sys.executable, __file__, "--omit-clone"], capture_output=True, text=True)
        expect("PROCESS EXIT: `check.py --omit-clone` exits NON-ZERO", r.returncode != 0, True)
        expect("PROCESS EXIT: and reports an AssertionError", "AssertionError" in r.stderr, True)
        ver = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip()
        out = Path(__file__).parent / "results.txt"
        out.write_text(f"Tools: {ver}; Python {sys.version.split()[0]}\n\n" + "\n".join(LOG) + "\n")
        print("ALL CHECKS PASSED (guide ran twice; omission of git clone makes the test fail).")
        print("Results saved to", out)