import shutil, subprocess, sys, tempfile
from pathlib import Path

GIT = shutil.which("git")
LOG = []
EXPLAIN = []

def run(cwd, *args, check=True, binary=False):
    # these -c options exist only on the command line; nothing is written to any config file
    return subprocess.run([GIT, "-c", "color.ui=never", "-c", "status.showUntrackedFiles=normal", *args],
                          cwd=cwd, capture_output=True, text=not binary, check=check)

def git(cwd, *args):
    return run(cwd, *args).stdout.rstrip("\n")

def git_bytes(cwd, *args):
    return run(cwd, *args, binary=True).stdout

def blob_id_of(cwd, data):
    """The object id Git WILL give to a file with this exact content (content alone decides it)."""
    r = subprocess.run([GIT, "hash-object", "--stdin"], cwd=cwd, input=data, capture_output=True, check=True)
    return r.stdout.decode().strip()

def check(label, predicted, actual):
    """Compare a PREDICTION (made before running the command) with the REAL Git state."""
    LOG.append(f"{label}\n  predicted: {predicted!r}\n  actual:    {actual!r}")
    assert actual == predicted, f"FAILED: {label}: predicted {predicted!r}, got {actual!r}"

def run_once():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        tmp = root
        src = root / "repo"
        src.mkdir()
        git(src, "init", "-b", "main")

        # Config this exercise needs, set LOCALLY. autocrlf=false matters: otherwise Git could
        # silently convert the DOS line endings back and hide exactly what we want to see.
        git(src, "config", "--local", "user.name", "Course Student")
        git(src, "config", "--local", "user.email", "student@example.invalid")
        git(src, "config", "--local", "commit.gpgsign", "false")
        git(src, "config", "--local", "core.autocrlf", "false")
        check("core.autocrlf is false in this temp repo", "false", git(src, "config", "--local", "--get", "core.autocrlf"))

        # Required history: A, B, C on main and branch topic at B
        (src / "notes.txt").write_text("alpha\n")
        git(src, "add", "notes.txt"); git(src, "commit", "-m", "A")
        with open(src / "notes.txt", "a") as f: f.write("beta\n")
        git(src, "commit", "-am", "B")
        b = git(src, "rev-parse", "HEAD")
        (src / "todo.txt").write_text("one\n")
        git(src, "add", "todo.txt"); git(src, "commit", "-m", "C")
        c = git(src, "rev-parse", "HEAD")
        git(src, "branch", "topic", b)
        short = lambda sha: git(src, "rev-parse", "--short", sha)

        old_notes_blob = git(src, "rev-parse", "HEAD:notes.txt")
        todo_blob_in_c = git(src, "rev-parse", "HEAD:todo.txt")
        check("start: on branch main", "main", git(src, "symbolic-ref", "--short", "HEAD"))
        check("start: working tree clean", "", git(src, "status", "--short"))

        # =====================================================================================
        # STEP 1:  $ git checkout -b whitespace
        # PREDICT (before running): a new ref appears AT THE CURRENT COMMIT and HEAD follows it.
        # No file is touched, so the index and working tree stay exactly as they are.
        # =====================================================================================
        pred_ref_whitespace = c
        pred_head = "refs/heads/whitespace"
        pred_index_listing = git(src, "ls-files", "-s")          # index must not change
        run(src, "checkout", "-b", "whitespace")
        check("step 1: refs/heads/whitespace was created at C", pred_ref_whitespace, git(src, "rev-parse", "refs/heads/whitespace"))
        check("step 1: HEAD now points at refs/heads/whitespace", pred_head, git(src, "symbolic-ref", "HEAD"))
        check("step 1: main did not move", c, git(src, "rev-parse", "main"))
        check("step 1: topic did not move", b, git(src, "rev-parse", "topic"))
        check("step 1: index is unchanged", pred_index_listing, git(src, "ls-files", "-s"))
        check("step 1: working tree is still clean", "", git(src, "status", "--short"))

        # =====================================================================================
        # STEP 2:  convert notes.txt to DOS line endings (what `unix2dos` does) + add an untracked file
        # PREDICT: the new file content alone decides its blob id. Only the WORKING TREE changes.
        # `git diff` sees the change, but `git diff -b` ignores it (only a CR at each line end differs).
        # =====================================================================================
        dos_content = b"alpha\r\nbeta\r\n"
        pred_new_blob = blob_id_of(src, dos_content)             # predicted from the bytes, before writing
        pred_status = " M notes.txt\n?? scratch.txt"
        (src / "notes.txt").write_bytes(dos_content)
        (src / "scratch.txt").write_text("not tracked\n")
        check("step 2: status shows notes.txt modified (unstaged) and scratch.txt untracked",
              pred_status, git(src, "status", "--short"))
        check("step 2: the working-tree file hashes to the predicted blob",
              pred_new_blob, git(src, "hash-object", "notes.txt"))
        check("step 2: the INDEX still holds the old blob", old_notes_blob, git(src, "rev-parse", ":notes.txt"))
        check("step 2: refs did not move (whitespace still at C)", c, git(src, "rev-parse", "whitespace"))
        check("step 2: plain `git diff` lists notes.txt", "notes.txt", git(src, "diff", "--name-only"))
        check("step 2: `git diff` is NOT empty", True, git(src, "diff") != "")
        check("step 2: `git diff -b` IS empty (only line endings differ)", "", git(src, "diff", "-b"))

        # =====================================================================================
        # STEP 3:  $ git commit -am 'Convert notes.txt to DOS'
        # PREDICT: -a stages tracked changes only, then a NEW commit is created whose parent is C;
        # the branch ref whitespace moves from C to it; main and topic stay; notes.txt gets the
        # predicted blob; todo.txt keeps its old blob; untracked scratch.txt is left alone.
        # =====================================================================================
        pred_parent = c
        pred_status_after = "?? scratch.txt"
        pred_numstat = "2\t2\tnotes.txt"        # both lines of notes.txt change (a CR is added to each)
        run(src, "commit", "-am", "Convert notes.txt to DOS")
        d_commit = git(src, "rev-parse", "refs/heads/whitespace")
        check("step 3: whitespace moved to a NEW commit", True, d_commit != c)
        check("step 3: the new commit's parent is C", pred_parent, git(src, "rev-parse", "whitespace^"))
        check("step 3: HEAD still follows whitespace", pred_head, git(src, "symbolic-ref", "HEAD"))
        check("step 3: main did not move", c, git(src, "rev-parse", "main"))
        check("step 3: topic did not move", b, git(src, "rev-parse", "topic"))
        check("step 3: notes.txt in the new commit is the predicted blob",
              pred_new_blob, git(src, "rev-parse", "whitespace:notes.txt"))
        check("step 3: that blob really contains CRLF line endings",
              dos_content, git_bytes(src, "cat-file", "blob", "whitespace:notes.txt"))
        check("step 3: the INDEX now holds the predicted blob too", pred_new_blob, git(src, "rev-parse", ":notes.txt"))
        check("step 3: todo.txt kept its old blob (that object was not rewritten)",
              todo_blob_in_c, git(src, "rev-parse", "whitespace:todo.txt"))
        check("step 3: the commit tree differs from C's tree", True,
              git(src, "rev-parse", "whitespace^{tree}") != git(src, "rev-parse", "main^{tree}"))
        check("step 3: untracked scratch.txt was NOT committed (-a only takes tracked files)",
              pred_status_after, git(src, "status", "--short"))
        check("step 3: both lines of notes.txt changed", pred_numstat, git(src, "diff", "--numstat", "main", "whitespace"))
        check("step 3: `git diff main whitespace` is NOT empty", True, git(src, "diff", "main", "whitespace") != "")
        check("step 3: `git diff -b main whitespace` IS empty", "", git(src, "diff", "-b", "main", "whitespace"))
        check("step 3: commit message", "Convert notes.txt to DOS", git(src, "log", "-1", "--format=%s", "whitespace"))

        # ---- EXPLANATION, generated from the real state (names the objects that changed) ----
        tree_d = git(src, "rev-parse", "--short", "whitespace^{tree}")
        EXPLAIN[:] = [
            "EXPLANATION (generated from the real repository state, not typed in)",
            f"1. `git checkout -b whitespace` created the ref refs/heads/whitespace pointing at commit {short(c)} and moved HEAD onto it.",
            f"   No object was created. The index and working tree were untouched. main is still {short(c)} and topic is still {short(b)}.",
            f"2. Converting notes.txt to DOS line endings changed only the WORKING TREE: the file now hashes to blob {short(pred_new_blob)},",
            f"   while the index still holds blob {short(old_notes_blob)}. `git diff` shows that, but `git diff -b` prints nothing,",
            "   because the only difference is a carriage return at the end of each line.",
            f"3. `git commit -am` created commit {short(d_commit)} (parent {short(c)}, tree {tree_d}) and moved refs/heads/whitespace from {short(c)} to {short(d_commit)}.",
            f"   The index now holds blob {short(pred_new_blob)}, the very blob predicted in step 2 from the file's bytes alone.",
            f"   todo.txt kept blob {short(todo_blob_in_c)}; scratch.txt stayed untracked because -a only stages files Git already tracks.",
            "   main and topic did not move, so the whitespace-only change exists on one branch only.",
        ]
    check("temporary directory was removed", False, tmp.exists())
    return pred_new_blob

if __name__ == "__main__":
    first = run_once()
    second = run_once()
    check("a blob id depends only on content: identical in both runs", first, second)
    ver = subprocess.run([GIT, "--version"], capture_output=True, text=True).stdout.strip()
    out = Path(__file__).parent / "results.txt"
    out.write_text(f"Tools: {ver}; Python {sys.version.split()[0]}\n\n" + "\n".join(EXPLAIN) + "\n\n"
                   + "\n".join(LOG) + "\n")
    print("ALL CHECKS PASSED (ran twice).\n")
    print("\n".join(EXPLAIN))
    print("\nResults saved to", out)