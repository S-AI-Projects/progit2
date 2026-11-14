import os, subprocess, sys, tempfile
from pathlib import Path

ENV = {**os.environ,
       "GIT_AUTHOR_NAME": "Course Student", "GIT_AUTHOR_EMAIL": "student@example.invalid",
       "GIT_COMMITTER_NAME": "Course Student", "GIT_COMMITTER_EMAIL": "student@example.invalid"}
LOG = []
FILE = "sample data/release notes.txt"   # directory AND file both contain a space

def run(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, env=ENV,
                          capture_output=True, text=True, check=check)

def git(cwd, *args):
    return run(cwd, *args).stdout.rstrip("\n")

def expect(label, actual, expected):
    LOG.append(f"{label}\n  expected: {expected!r}\n  actual:   {actual!r}")
    assert actual == expected, f"FAILED: {label}: expected {expected!r}, got {actual!r}"

def unmerged(repo):
    out = git(repo, "diff", "--name-only", "--diff-filter=U", "-z")
    return [p for p in out.split("\0") if p]

def run_once():
    with tempfile.TemporaryDirectory() as d:
        repo = Path(d) / "repo"
        repo.mkdir()
        git(repo, "init", "-b", "main")
        git(repo, "config", "rerere.enabled", "true")      # LOCAL to this temp repo only
        expect("rerere enabled (local config)", git(repo, "config", "--get", "rerere.enabled"), "true")

        # Required history: A, B, C on main and branch topic at B
        (repo / "notes.txt").write_text("alpha\n")
        git(repo, "add", "notes.txt"); git(repo, "commit", "-m", "A")
        with open(repo / "notes.txt", "a") as f: f.write("beta\n")
        git(repo, "commit", "-am", "B")
        b = git(repo, "rev-parse", "HEAD")
        (repo / "todo.txt").write_text("one\n")
        git(repo, "add", "todo.txt"); git(repo, "commit", "-m", "C")
        git(repo, "branch", "topic", b)

        # Shared base file inside a directory with a space, reachable from both branches
        git(repo, "switch", "topic")
        (repo / "sample data").mkdir()
        (repo / FILE).write_text("release: draft\n")
        git(repo, "add", "--", FILE); git(repo, "commit", "-m", "R0 base file")
        git(repo, "switch", "main")
        git(repo, "merge", "-m", "M0 bring base file into main", "topic")

        # Path quoting: unquoted path in a shell splits at the spaces; quoted path works
        bad = subprocess.run(f"git ls-files {FILE}", shell=True, cwd=repo, env=ENV, capture_output=True, text=True)
        expect("unquoted path: shell splits it into 3 words and git acts on the WRONG file (notes.txt)", bad.stdout.strip(), "notes.txt")
        good = subprocess.run(f'git ls-files "{FILE}"', shell=True, cwd=repo, env=ENV, capture_output=True, text=True)
        expect("quoted path: git finds the exact intended file", good.stdout.strip(), FILE)

        # Conflicting edits of the same line on each side
        git(repo, "switch", "topic")
        (repo / FILE).write_text("release: topic\n")
        git(repo, "commit", "-am", "T1 topic edit")
        git(repo, "switch", "main")
        (repo / FILE).write_text("release: main\n")
        git(repo, "commit", "-am", "M1 main edit")
        main_before = git(repo, "rev-parse", "HEAD")

        # 1st merge: conflict. rerere records the PREIMAGE (the conflicted file)
        r = run(repo, "merge", "topic", check=False)
        expect("first merge conflicts (non-zero exit)", r.returncode, 1)
        expect("conflict is in the spaced path", unmerged(repo), [FILE])
        expect("rerere reports it is tracking that path (spaces preserved)",
               git(repo, "rerere", "status"), FILE)
        rr = repo / ".git" / "rr-cache"
        ids = sorted(p.name for p in rr.iterdir())
        expect("rerere stored exactly one conflict id (computed, not hard-coded)", len(ids), 1)
        rr_id = ids[0]
        expect("preimage saved", (rr / rr_id / "preimage").exists(), True)
        expect("postimage not saved yet", (rr / rr_id / "postimage").exists(), False)

        # Resolve by hand; `--` makes git treat what follows as a path, never a revision
        (repo / FILE).write_text("release: resolved\n")
        git(repo, "add", "--", FILE)
        git(repo, "commit", "-m", "Merge topic (resolved by hand)")
        expect("rerere recorded the POSTIMAGE (the resolution)", (rr / rr_id / "postimage").exists(), True)
        resolved_tree = git(repo, "rev-parse", "HEAD^{tree}")

        # Undo the merge, then redo it: rerere should resolve it automatically
        git(repo, "reset", "--hard", "HEAD^")
        expect("reset moved main back before the merge", git(repo, "rev-parse", "HEAD"), main_before)
        r2 = run(repo, "merge", "topic", check=False)
        expect("second merge still stops (rerere does not auto-commit)", r2.returncode, 1)
        expect("rerere announces it reused the recorded resolution",
               f"Resolved '{FILE}' using previous resolution." in r2.stderr, True)
        expect("file already has the recorded resolution", (repo / FILE).read_text(), "release: resolved\n")
        expect("no conflict markers left in the file", "<<<<<<<" in (repo / FILE).read_text(), False)
        expect("rerere has nothing left to resolve", git(repo, "rerere", "status"), "")
        expect("path is still unmerged in the index until you `git add` it", unmerged(repo), [FILE])
        git(repo, "add", "--", FILE)
        git(repo, "commit", "-m", "Merge topic (reused resolution)")
        expect("same final tree as the hand-resolved merge", git(repo, "rev-parse", "HEAD^{tree}"), resolved_tree)

        # Filename vs revision ambiguity: a file called `topic` clashes with branch `topic`
        (repo / "topic").write_text("i am a file, not a branch\n")
        amb = run(repo, "diff", "topic", check=False)
        expect("`git diff topic` is ambiguous (revision AND filename) -> error", amb.returncode, 128)
        expect("error text names the ambiguity", "ambiguous argument 'topic'" in amb.stderr, True)
        as_rev = run(repo, "diff", "topic", "--", check=False)
        expect("`git diff topic --` means: topic is a revision (exit 0 or 1, no error)", as_rev.returncode in (0, 1), True)
        as_path = git(repo, "status", "--short", "--", "topic")
        expect("`-- topic` means: topic is a file", as_path, "?? topic")
        return resolved_tree

if __name__ == "__main__":
    run_once(); run_once()
    ver = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip()
    out = Path(__file__).parent / "results.txt"
    out.write_text(f"Tools: {ver}; Python {sys.version.split()[0]}\n\n" + "\n".join(LOG) + "\n")
    print("ALL CHECKS PASSED (ran twice). Results saved to", out)
