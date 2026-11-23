#!/usr/bin/env python3
import json,pathlib,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parent
def run(args,cwd,ok=True):
 p=subprocess.run(args,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if ok:p.check_returncode()
 return p
with tempfile.TemporaryDirectory(prefix='R31-T024-') as td:
 r=pathlib.Path(td);run(['git','init','-q','-b','main'],r)
 for k,v in [('user.name','Course Student'),('user.email','student@example.invalid')]:run(['git','config',k,v],r)
 (r/'notes.txt').write_text('alpha\n');run(['git','add','.'],r);run(['git','commit','-qm','A'],r)
 (r/'notes.txt').write_text('alpha\nbeta\n');run(['git','commit','-qam','B'],r);b=run(['git','rev-parse','HEAD'],r).stdout.strip();run(['git','branch','topic',b],r)
 (r/'todo.txt').write_text('one\n');run(['git','add','.'],r);run(['git','commit','-qm','C'],r)
 d=r/'sample data';d.mkdir();f=d/'release notes.txt';f.write_text('approved\n')
 run(['git','add','--','sample data/release notes.txt'],r);run(['git','commit','-qm','Add release notes'],r)
 clean_head=run(['git','rev-parse','HEAD'],r).stdout.strip()
 f.write_text('mistaken edit\n')
 staged=run(['git','add','--','sample data/release notes.txt'],r)
 status=run(['git','status','--short'],r).stdout.strip()
 assert status=='M  "sample data/release notes.txt"',repr(status)
 run(['git','restore','--source=main','--staged','--worktree','--','sample data/release notes.txt'],r)
 restored=f.read_text();head=run(['git','rev-parse','HEAD'],r).stdout.strip();status_after=run(['git','status','--porcelain'],r).stdout
 assert restored=='approved\n' and head==clean_head and status_after==''
 actual={'path':'sample data/release notes.txt','staged_status':status,'restored_contents':restored,'head_unchanged':head==clean_head,'final_status':'clean'}
versions={'git':subprocess.check_output(['git','--version'],text=True).strip(),'python':subprocess.check_output(['python3','--version'],text=True).strip()}
(ROOT/'results.json').write_text(json.dumps({'inputs':'tracked file with spaces; edit and stage it; restore from main with -- path separator','expected':'path stays one argument, restore returns committed contents and leaves branch ref unchanged','actual':actual,'tool_versions':versions},indent=2)+'\n')
print(json.dumps(actual,indent=2))
