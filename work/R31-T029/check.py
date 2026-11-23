#!/usr/bin/env python3
import json,pathlib,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parent
def run(args,cwd):return subprocess.run(args,cwd=cwd,text=True,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout.strip()
with tempfile.TemporaryDirectory(prefix='R31-T029-') as td:
 r=pathlib.Path(td);run(['git','init','-q','-b','main'],r)
 for k,v in [('user.name','Course Student'),('user.email','student@example.invalid')]:run(['git','config',k,v],r)
 (r/'notes.txt').write_text('alpha\n');run(['git','add','.'],r);run(['git','commit','-qm','A'],r)
 (r/'notes.txt').write_text('alpha\nbeta\n');run(['git','commit','-qam','B'],r);b=run(['git','rev-parse','HEAD'],r);run(['git','branch','topic',b],r)
 (r/'todo.txt').write_text('one\n');run(['git','add','.'],r);run(['git','commit','-qm','C'],r);c=run(['git','rev-parse','HEAD'],r)
 run(['git','reset','--mixed',b],r)
 head=run(['git','rev-parse','HEAD'],r);index_tree=run(['git','write-tree'],r);b_tree=run(['git','rev-parse','B^{tree}'],r) if False else run(['git','rev-parse',b+'^{tree}'],r)
 committed_tree=run(['git','rev-parse','HEAD^{tree}'],r);listing=run(['git','ls-tree','-r','HEAD'],r);status=run(['git','status','--short'],r)
 topic=run(['git','rev-parse','topic'],r)
 assert head==b and index_tree==b_tree==committed_tree
 assert 'todo.txt' not in listing and (r/'todo.txt').read_text()=='one\n'
 assert status=='?? todo.txt' and topic==b
 actual={'main_before':c,'main_after':head,'index_tree':index_tree,'B_tree':b_tree,'head_tree':committed_tree,'ls_tree_HEAD':listing,'todo_worktree':(r/'todo.txt').read_text(),'status':status,'topic':topic}
versions={'git':subprocess.check_output(['git','--version'],text=True).strip(),'python':subprocess.check_output(['python3','--version'],text=True).strip()}
(ROOT/'results.json').write_text(json.dumps({'inputs':'main=C; topic=B; git reset --mixed B','expected':'main and index move to B; worktree keeps todo.txt; todo is untracked; topic unchanged','actual':actual,'tool_versions':versions},indent=2)+'\n')
print(json.dumps(actual,indent=2))
