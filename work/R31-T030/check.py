#!/usr/bin/env python3
import hashlib,json,os,pathlib,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parent
def run(args,cwd,env):
 return subprocess.run(args,cwd=cwd,env=env,text=True,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout.strip()
with tempfile.TemporaryDirectory(prefix='R31-T030-') as td:
 r=pathlib.Path(td);r.mkdir(exist_ok=True);env=os.environ.copy();env.update({'GIT_CONFIG_GLOBAL':str(r/'no-global-config'),'GIT_CONFIG_NOSYSTEM':'1'})
 run(['git','init','-q','-b','main'],r,env)
 run(['git','config','--local','user.name','Course Student'],r,env);run(['git','config','--local','user.email','student@example.invalid'],r,env)
 (r/'notes.txt').write_text('alpha\n');run(['git','add','.'],r,env);run(['git','commit','-qm','A'],r,env)
 (r/'notes.txt').write_text('alpha\nbeta\n');run(['git','commit','-qam','B'],r,env);b=run(['git','rev-parse','HEAD'],r,env);run(['git','branch','topic',b],r,env)
 (r/'todo.txt').write_text('one\n');run(['git','add','.'],r,env);run(['git','commit','-qm','C'],r,env)
 (r/'settings.txt').write_text('mode=review\n');run(['git','add','settings.txt'],r,env);run(['git','commit','-qm','Known good settings'],r,env)
 saved_tree=run(['git','rev-parse','HEAD^{tree}'],r,env);saved_name=run(['git','config','--local','--get','user.name'],r,env)
 global_path=pathlib.Path(env['GIT_CONFIG_GLOBAL']);global_before=hashlib.sha256(global_path.read_bytes() if global_path.exists() else b'').hexdigest()
 (r/'settings.txt').write_text('mode=mistake\n');run(['git','config','--local','user.name','Mistaken Name'],r,env)
 run(['git','restore','--source=HEAD','--worktree','--','settings.txt'],r,env)
 run(['git','config','--local','user.name',saved_name],r,env)
 restored=(r/'settings.txt').read_text();name=run(['git','config','--local','--get','user.name'],r,env)
 restored_tree=run(['git','write-tree'],r,env);head_tree=run(['git','rev-parse','HEAD^{tree}'],r,env);status=run(['git','status','--porcelain'],r,env)
 global_after=hashlib.sha256(global_path.read_bytes() if global_path.exists() else b'').hexdigest()
 assert restored=='mode=review\n' and name==saved_name
 assert restored_tree==head_tree==saved_tree and status=='' and global_before==global_after
 actual={'saved_tree':saved_tree,'restored_tree':restored_tree,'file':restored,'user_name_restored':name,'status':'clean','global_config_unchanged':global_before==global_after}
versions={'git':subprocess.check_output(['git','--version'],text=True).strip(),'python':subprocess.check_output(['python3','--version'],text=True).strip()}
(ROOT/'results.json').write_text(json.dumps({'inputs':'known-good commit; local user.name saved; tracked settings.txt edited; local setting changed incorrectly; restore file and setting','expected':'file, tree and local setting match recovery point; global config unchanged','actual':actual,'tool_versions':versions},indent=2)+'\n')
print(json.dumps(actual,indent=2))
