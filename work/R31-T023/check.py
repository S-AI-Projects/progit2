#!/usr/bin/env python3
import json,pathlib,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parent
def run(args,cwd,ok=True):
 p=subprocess.run(args,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if ok: p.check_returncode()
 return p
with tempfile.TemporaryDirectory(prefix='R31-T023-') as td:
 r=pathlib.Path(td);run(['git','init','-q','-b','main'],r)
 for k,v in [('user.name','Course Student'),('user.email','student@example.invalid')]:run(['git','config',k,v],r)
 (r/'notes.txt').write_text('alpha\n');run(['git','add','.'],r);run(['git','commit','-qm','A'],r)
 (r/'notes.txt').write_text('alpha\nbeta\n');run(['git','commit','-qam','B'],r)
 b=run(['git','rev-parse','HEAD'],r).stdout.strip();run(['git','branch','topic',b],r)
 (r/'todo.txt').write_text('one\n');run(['git','add','.'],r);run(['git','commit','-qm','C'],r)
 main=run(['git','rev-parse','main'],r).stdout.strip();topic=run(['git','rev-parse','topic'],r).stdout.strip()
 run(['git','switch','-q','topic'],r)
 current=run(['git','grep','one'],r,ok=False)
 explicit=run(['git','grep','one','main'],r)
 assert current.returncode==1 and current.stdout==''
 assert explicit.returncode==0 and explicit.stdout.strip()=='main:todo.txt:one'
 after_main=run(['git','rev-parse','main'],r).stdout.strip();after_topic=run(['git','rev-parse','topic'],r).stdout.strip()
 branch=run(['git','branch','--show-current'],r).stdout.strip()
 assert branch=='topic' and (main,topic)==(after_main,after_topic)
 assert run(['git','status','--porcelain'],r).stdout==''
 actual={'current_branch':branch,'git_grep_one_exit':current.returncode,'git_grep_main_output':explicit.stdout.strip(),'main_before_after':main,'topic_before_after':topic,'status':'clean'}
versions={'git':subprocess.check_output(['git','--version'],text=True).strip(),'python':subprocess.check_output(['python3','--version'],text=True).strip()}
(ROOT/'results.json').write_text(json.dumps({'inputs':'main=C with todo.txt=one; topic=B; current checkout topic','expected':'current-tree search has no match; explicit main search finds todo.txt; refs unchanged','actual':actual,'tool_versions':versions},indent=2)+'\n')
print(json.dumps(actual,indent=2))
