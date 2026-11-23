#!/usr/bin/env python3
import json,pathlib,shutil,subprocess,tempfile,os
ROOT=pathlib.Path(__file__).resolve().parent
def run(args,cwd=None,env=None,ok=True):
 p=subprocess.run(args,cwd=cwd,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if ok:p.check_returncode()
 return p
with tempfile.TemporaryDirectory(prefix='R31-T026-') as td:
 r=pathlib.Path(td);run(['git','init','-q','-b','main'],r)
 for k,v in [('user.name','Course Student'),('user.email','student@example.invalid')]:run(['git','config',k,v],r)
 (r/'notes.txt').write_text('alpha\n');run(['git','add','.'],r);run(['git','commit','-qm','A'],r)
 (r/'notes.txt').write_text('alpha\nbeta\n');run(['git','commit','-qam','B'],r)
 b=run(['git','rev-parse','HEAD'],r).stdout.strip();run(['git','branch','topic',b],r)
 (r/'todo.txt').write_text('one\n');run(['git','add','.'],r);run(['git','commit','-qm','C'],r)
 before=run(['git','rev-parse','HEAD'],r).stdout.strip();empty_path=dict(os.environ);empty_path['PATH']=''
 bad=run(['/bin/sh','-c','gitk --all'],r,env=empty_path,ok=False)
 assert bad.returncode==127 and 'gitk' in bad.stderr
 fallback=run(['git','log','--graph','--oneline','--decorate','--all'],r)
 assert fallback.returncode==0 and 'A' in fallback.stdout and 'B' in fallback.stdout and 'C' in fallback.stdout
 after=run(['git','rev-parse','HEAD'],r).stdout.strip();status=run(['git','status','--porcelain'],r).stdout
 assert before==after and status==''
 actual={'trigger':'PATH intentionally hides gitk','failure_exit':bad.returncode,'failure_category':'command not found','fallback_exit':fallback.returncode,'fallback_shows_history':all(c in fallback.stdout for c in ['A','B','C']),'head_unchanged':before==after,'status':'clean'}
versions={'git':subprocess.check_output(['git','--version'],text=True).strip(),'python':subprocess.check_output(['python3','--version'],text=True).strip(),'gitk_discoverable_on_host':str(bool(shutil.which('gitk')))}
(ROOT/'results.json').write_text(json.dumps({'inputs':'main with commits A/B/C; invoke gitk with PATH empty then git log fallback','expected':'missing helper exits 127; text fallback succeeds without changing repository state','actual':actual,'tool_versions':versions},indent=2)+'\n')
print(json.dumps(actual,indent=2))
