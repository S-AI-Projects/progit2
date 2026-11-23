#!/usr/bin/env python3
import json,pathlib,subprocess,sys,tempfile
ROOT=pathlib.Path(__file__).resolve().parent
def run(args,cwd,ok=True):
 p=subprocess.run(args,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if ok:p.check_returncode()
 return p
def exercise(omit=False):
 with tempfile.TemporaryDirectory(prefix='R31-T028-') as td:
  r=pathlib.Path(td);run(['git','init','-q','-b','main'],r)
  for k,v in [('user.name','Course Student'),('user.email','student@example.invalid')]:run(['git','config',k,v],r)
  (r/'notes.txt').write_text('alpha\n');run(['git','add','.'],r);run(['git','commit','-qm','A'],r)
  (r/'notes.txt').write_text('alpha\nbeta\n');run(['git','commit','-qam','B'],r);b=run(['git','rev-parse','HEAD'],r).stdout.strip()
  run(['git','branch','topic',b],r)
  (r/'todo.txt').write_text('one\n');run(['git','add','.'],r);run(['git','commit','-qm','C'],r)
  c=run(['git','rev-parse','main'],r).stdout.strip()
  if not omit: run(['git','update-ref','refs/heads/review',b],r)
  review=run(['git','rev-parse','refs/heads/review'],r,ok=False)
  assert review.returncode==0, 'decisive git update-ref command was omitted or failed'
  assert review.stdout.strip()==b, 'review ref does not point to B'
  assert run(['git','rev-parse','main'],r).stdout.strip()==c, 'main moved unexpectedly'
  log=run(['git','log','--pretty=oneline','main'],r).stdout
  assert all(msg in log for msg in ['A','B','C'])
  assert run(['git','status','--porcelain'],r).stdout==''
  return {'commit_B':b,'main_C':c,'review_ref':review.stdout.strip(),'log_main':log.splitlines(),'status':'clean'}
if '--omit-update-ref' in sys.argv:
 exercise(omit=True)
 raise SystemExit(0)
actual=exercise()
missing=subprocess.run([sys.executable,__file__,'--omit-update-ref'],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
assert missing.returncode!=0, 'omitting git update-ref unexpectedly passed'
actual['omitted_command_exit']=missing.returncode
versions={'git':subprocess.check_output(['git','--version'],text=True).strip(),'python':subprocess.check_output(['python3','--version'],text=True).strip()}
(ROOT/'results.json').write_text(json.dumps({'inputs':'temporary main history A/B/C; update refs/heads/review to captured B; run omitted-command mutation','expected':'review=B; main=C; log contains A/B/C; omitted update-ref exits nonzero','actual':actual,'tool_versions':versions},indent=2)+'\n')
print(json.dumps(actual,indent=2))
