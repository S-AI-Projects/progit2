import os, shutil, stat, subprocess, sys, tempfile
from pathlib import Path

GIT = shutil.which("git")     # absolute path, so runs with a restricted PATH can still start git
LOG = []

def run(cwd, *args, check=True, env=None):
    # "-c color.ui=never" lives only on this command line: it is never written to any config file
    return subprocess.run([GIT, "-c", "color.ui=never", *args], cwd=cwd, env=env,
                          capture_output=True, text=True, check=check)

def git(cwd, *args):
    return run(cwd, *args).stdout.rstrip("\n")

def expect(label, actual, expected):
    LOG.append(f"{label}\n  expected: {expected!r}\n  actual:   {actual!r}")
    assert actual == expected, f"FAILED: {label}: expected {expected!r}, got {actual!r}"

def global_config():
    """Snapshot of the user's REAL global Git config, to prove the test never touches it."""
    r = subprocess.run([GIT, "config", "--global", "--list"], capture_output=True, text=True)
    return (r.returncode, r.stdout)

def probe():
    """Prerequisites of the guide's `git clone hg::<path> <dest>`: reported, not required to pass."""
    return {"hg (Mercurial)": shutil.which("hg"), "git-remote-hg": shutil.which("git-remote-hg")}

def run_once():
    before = global_config()
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        tmp = root

        # ---- Source repo: branch main, commits A, B, C, branch topic at B -----------------
        src = root / "src"
        src.mkdir()
        git(src, "init", "-b", "main")

        # PREREQUISITE: required config. Set LOCALLY (inside this temp repo) and nowhere else.
        git(src, "config", "--local", "user.name", "Course Student")
        git(src, "config", "--local", "user.email", "student@example.invalid")
        git(src, "config", "--local", "commit.gpgsign", "false")
        expect("identity is stored in the repo's LOCAL config",
               git(src, "config", "--local", "--get", "user.email"), "student@example.invalid")
        expect("the local config file lives inside the temp repo",
               (src / ".git" / "config").read_text().count("student@example.invalid"), 1)

        (src / "notes.txt").write_text("alpha\n")
        git(src, "add", "notes.txt"); git(src, "commit", "-m", "A")
        a = git(src, "rev-parse", "HEAD")
        with open(src / "notes.txt", "a") as f: f.write("beta\n")
        git(src, "commit", "-am", "B")
        b = git(src, "rev-parse", "HEAD")
        (src / "todo.txt").write_text("one\n")
        git(src, "add", "todo.txt"); git(src, "commit", "-m", "C")
        c = git(src, "rev-parse", "HEAD")
        git(src, "branch", "topic", b)

        expect("all 3 commits have the required author",
               set(git(src, "log", "--format=%an <%ae>").split("\n")),
               {"Course Student <student@example.invalid>"})
        expect("three commits exist", git(src, "rev-list", "--count", "HEAD"), "3")

        # ---- PREREQUISITE: repository state is visible and correct ------------------------
        expect("current branch is main", git(src, "symbolic-ref", "--short", "HEAD"), "main")
        expect("main is at C", git(src, "rev-parse", "main"), c)
        expect("topic is at B", git(src, "rev-parse", "topic"), b)
        expect("nothing is staged", git(src, "diff", "--cached", "--name-only"), "")
        expect("working tree is clean", git(src, "status", "--short"), "")

        # staged changes are VISIBLE when present, and gone again once unstaged
        (src / "scratch.txt").write_text("x\n")
        git(src, "add", "scratch.txt")
        expect("a staged file shows up in `diff --cached`", git(src, "diff", "--cached", "--name-only"), "scratch.txt")
        expect("and in `status --short`", git(src, "status", "--short"), "A  scratch.txt")
        git(src, "rm", "--cached", "-q", "scratch.txt")
        (src / "scratch.txt").unlink()
        expect("after unstaging, the tree is clean again", git(src, "status", "--short"), "")

        # ---- The guide's second command, executed for real --------------------------------
        short = lambda sha: git(src, "rev-parse", "--short", sha)
        out = git(src, "log", "--oneline", "--graph", "--decorate").split("\n")
        expect("`git log --oneline --graph --decorate` prints 3 lines", len(out), 3)
        expect("line 1: C is HEAD on main", out[0], f"* {short(c)} (HEAD -> main) C")
        expect("line 2: B carries the topic branch", out[1], f"* {short(b)} (topic) B")
        expect("line 3: A has no decoration", out[2], f"* {short(a)} A")

        # ---- The guide's first command: git clone hg::<path> <dest> ------------------------
        hello = root / "hello"          # stands in for /tmp/hello   (a Mercurial repository)
        dest = root / "hello-git"       # stands in for /tmp/hello-git
        expect("PREREQUISITE: destination does not exist yet", dest.exists(), False)

        # Git needs to find ITS OWN folder to launch a helper, so we keep that folder on PATH.
        # The test is only meaningful if no real git-remote-hg sits in Git's own folders.
        git_dir = str(Path(GIT).parent)
        exec_dir = git(root, "--exec-path")
        real_nearby = shutil.which("git-remote-hg", path=git_dir) or shutil.which("git-remote-hg", path=exec_dir)

        if real_nearby:
            LOG.append(f"SKIPPED the missing/present helper cases: a real git-remote-hg exists at {real_nearby}")
        else:
            # PREREQUISITE git-remote-hg, case 1: MISSING (PATH holds only Git's own folder)
            env_missing = {**os.environ, "PATH": git_dir, "GIT_TERMINAL_PROMPT": "0"}
            expect("control: git itself runs in that restricted environment",
                   run(root, "--version", env=env_missing, check=False).returncode, 0)
            bad = run(root, "clone", f"hg::{hello}", str(dest), env=env_missing, check=False)
            expect("MISSING SETUP: `git clone hg::...` exits non-zero without git-remote-hg",
                   bad.returncode != 0, True)
            expect("MISSING SETUP: no destination directory is left behind", dest.exists(), False)

            # PREREQUISITE git-remote-hg, case 2: PRESENT (a tiny stand-in that only records its arguments)
            bindir = root / "helper-bin"
            bindir.mkdir()
            marker = root / "helper-called.txt"
            helper = bindir / "git-remote-hg"
            helper.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > "{marker}"\nexit 1\n')
            helper.chmod(helper.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            expect("the stand-in helper is executable", os.access(helper, os.X_OK), True)
            env_present = {**os.environ, "PATH": str(bindir) + os.pathsep + git_dir, "GIT_TERMINAL_PROMPT": "0"}
            bad2 = run(root, "clone", f"hg::{hello}", str(dest), env=env_present, check=False)
            expect("PRESENT HELPER: git found git-remote-hg and ran it", marker.exists(), True)
            helper_args = marker.read_text().split("\n")
            expect("PRESENT HELPER: it received the address that follows `hg::`", helper_args[1], str(hello))
            expect("the stand-in aborts on purpose, so the clone still exits non-zero", bad2.returncode != 0, True)
            expect("and still no destination directory is left behind", dest.exists(), False)

        expect("the source repo was not changed by any of this", git(src, "rev-parse", "main"), c)

    expect("temporary directory was removed", tmp.exists(), False)
    expect("the user's GLOBAL git config is untouched", global_config(), before)

PREREQS = """
PREREQUISITES of `git clone hg::<path> <dest>` and what covers each
  1. Mercurial installed (hg)              -> probed and REPORTED below (not required to pass)
  2. git-remote-hg on PATH and executable  -> asserted missing (clone fails) and present (git runs it)
  3. destination path must not exist       -> asserted before and after the failed clones
  4. repo state: branch main, nothing staged, clean tree, topic at B
                                           -> asserted, plus a staged file made visible then removed
  5. config: identity and commit.gpgsign   -> set with `git config --local` only; global config snapshot
                                              is asserted unchanged
"""

if __name__ == "__main__":
    run_once(); run_once()
    p = probe()
    ver = subprocess.run([GIT, "--version"], capture_output=True, text=True).stdout.strip()
    lines = [f"Tools: {ver}; Python {sys.version.split()[0]}", PREREQS, "ENVIRONMENT PROBE (reported, not asserted):"]
    for name, path in p.items():
        lines.append(f"  {name}: {path or 'NOT FOUND - missing setup; the real hg:: clone cannot run on this computer'}")
    out = Path(__file__).parent / "results.txt"
    out.write_text("\n".join(lines) + "\n\n" + "\n".join(LOG) + "\n")
    print("ALL CHECKS PASSED (ran twice).")
    print(PREREQS)
    print("ENVIRONMENT PROBE:")
    for name, path in p.items():
        print(f"  {name}: {path or 'NOT FOUND  <-- missing setup (the real `git clone hg::...` cannot run here)'}")
    print("Results saved to", out)