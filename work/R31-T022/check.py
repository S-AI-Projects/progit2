#!/usr/bin/env python3
import json, pathlib, subprocess, tempfile
ROOT = pathlib.Path(__file__).resolve().parent
def run(args, cwd): return subprocess.run(args, cwd=cwd, text=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()
with tempfile.TemporaryDirectory(prefix='R31-T022-') as td:
    repo=pathlib.Path(td); run(['git','init','-q','-b','main'],repo)
    run(['git','config','user.name','Course Student'],repo); run(['git','config','user.email','student@example.invalid'],repo)
    (repo/'notes.txt').write_text('alpha\nbeta\n'); run(['git','add','.'],repo); run(['git','commit','-qm','C'],repo)
    head_before=run(['git','rev-parse','HEAD'],repo)
    (repo/'notes.txt').write_text('alpha\nbeta\nv2\n'); run(['git','add','notes.txt'],repo)
    index_blob=run(['git','rev-parse',':notes.txt'],repo)
    (repo/'notes.txt').write_text('alpha\nbeta\nv3\n')
    head_after=run(['git','rev-parse','HEAD'],repo)
    branch=run(['git','symbolic-ref','--short','HEAD'],repo)
    status=run(['git','status','--short'],repo)
    tree_index=run(['git','write-tree'],repo)
    assert branch=='main' and head_before==head_after
    assert run(['git','show','HEAD:notes.txt'],repo)=='alpha\nbeta'
    assert run(['git','show',':notes.txt'],repo)=='alpha\nbeta\nv2'
    assert (repo/'notes.txt').read_text()=='alpha\nbeta\nv3\n'
    assert status=='MM notes.txt', status
    actual={'branch':branch,'head':head_after,'index_tree':tree_index,'index_blob':index_blob,'status':status,'working_file':(repo/'notes.txt').read_text()}
versions={'git':subprocess.check_output(['git','--version'],text=True).strip(),'python':subprocess.check_output(['python3','--version'],text=True).strip()}
(ROOT/'results.json').write_text(json.dumps({'inputs':'commit C; stage notes.txt v2; leave v3 unstaged','expected':'HEAD unchanged; index contains v2; worktree contains v3; status MM','actual':actual,'tool_versions':versions},indent=2)+'\n')
print(json.dumps(actual,indent=2))
