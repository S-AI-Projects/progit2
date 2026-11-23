#!/usr/bin/env python3
import json,pathlib,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parent
def run(args,cwd,ok=True):
 p=subprocess.run(args,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if ok:p.check_returncode()
 return p
with tempfile.TemporaryDirectory(prefix='R31-T027-') as td:
 root=pathlib.Path(td);repo=root/'repo';repo.mkdir();run(['git','init','-q','-b','main'],repo)
 for k,v in [('user.name','Course Student'),('user.email','student@example.invalid')]:run(['git','config','--local',k,v],repo)
 (repo/'notes.txt').write_text('alpha\n');run(['git','add','.'],repo);run(['git','commit','-qm','A'],repo)
 (repo/'notes.txt').write_text('alpha\nbeta\n');run(['git','commit','-qam','B'],repo)
 b=run(['git','rev-parse','HEAD'],repo).stdout.strip();run(['git','branch','topic',b],repo)
 (repo/'todo.txt').write_text('one\n');run(['git','add','.'],repo);run(['git','commit','-qm','C'],repo)
 run(['git','switch','-q','topic'],repo);(repo/'review.txt').write_text('reviewed patch\n');run(['git','add','.'],repo);run(['git','commit','-qm','Add review note'],repo)
 patch=run(['git','format-patch','-1','--stdout'],repo).stdout
 patchfile=root/'patch.mbox';patchfile.write_text(patch)
 run(['git','switch','-q','main'],repo);base=run(['git','rev-parse','HEAD'],repo).stdout.strip();clean=run(['git','status','--porcelain'],repo).stdout
 assert clean=='' and run(['git','config','--local','user.email'],repo).stdout.strip()=='student@example.invalid'
 am=run(['git','am',str(patchfile)],repo);after=run(['git','rev-parse','HEAD'],repo).stdout.strip()
 assert after!=base and (repo/'review.txt').read_text()=='reviewed patch\n'
 assert run(['git','status','--porcelain'],repo).stdout==''
 assert run(['git','show','-s','--format=%an <%ae> %cn <%ce>', 'HEAD'],repo).stdout.strip()=='Course Student <student@example.invalid> Course Student <student@example.invalid>'
 actual={'target_branch':'main','pre_apply_clean':clean=='','base_before':base,'head_after':after,'review_file':(repo/'review.txt').read_text(),'status_after':'clean','commit_identity':run(['git','show','-s','--format=%an <%ae> %cn <%ce>','HEAD'],repo).stdout.strip()}
versions={'git':subprocess.check_output(['git','--version'],text=True).strip(),'python':subprocess.check_output(['python3','--version'],text=True).strip()}
(ROOT/'results.json').write_text(json.dumps({'inputs':'topic B creates email patch; main C clean; local committer identity set; git am applies patch','expected':'only main advances by new commit; patch file is present; final worktree is clean','actual':actual,'tool_versions':versions},indent=2)+'\n')
print(json.dumps(actual,indent=2))
