#!/usr/bin/env python3
import json,os,pathlib,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parent
def run(args,cwd=None,env=None,ok=True):
 p=subprocess.run(args,cwd=cwd,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if ok:p.check_returncode()
 return p
with tempfile.TemporaryDirectory(prefix='R31-T025-') as td:
 root=pathlib.Path(td);src=root/'src';src.mkdir();run(['git','init','-q','-b','main'],src)
 for k,v in [('user.name','Course Student'),('user.email','student@example.invalid')]:run(['git','config',k,v],src)
 (src/'notes.txt').write_text('alpha\n');run(['git','add','.'],src);run(['git','commit','-qm','A'],src)
 (src/'notes.txt').write_text('alpha\nbeta\n');run(['git','commit','-qam','B'],src)
 b=run(['git','rev-parse','HEAD'],src).stdout.strip();run(['git','branch','topic',b],src)
 (src/'todo.txt').write_text('one\n');run(['git','add','.'],src);run(['git','commit','-qm','C'],src)
 bare=root/'project.git';run(['git','clone','-q','--bare',str(src),str(bare)])
 run(['git','--git-dir',str(bare),'update-server-info'])
 static=(bare/'info/refs').read_text();head=run(['git','--git-dir',str(bare),'rev-parse','refs/heads/main']).stdout.strip()
 assert head in static and 'refs/heads/main' in static
 env=os.environ.copy();env.update({'GIT_PROJECT_ROOT':str(root),'GIT_HTTP_EXPORT_ALL':'1','PATH_INFO':'/project.git/info/refs','REQUEST_URI':'/git/project.git/info/refs?service=git-upload-pack','REQUEST_METHOD':'GET','QUERY_STRING':'service=git-upload-pack','SERVER_PROTOCOL':'HTTP/1.1','CONTENT_LENGTH':'0','HTTP_HOST':'localhost','SCRIPT_NAME':'/git'})
 smart=run(['git','http-backend'],env=env).stdout
 assert 'Content-Type: application/x-git-upload-pack-advertisement' in smart
 assert '# service=git-upload-pack' in smart and 'refs/heads/main' in smart and head in smart
 assert 'refs/heads/topic' in static
 actual={'bare_main':head,'dumb_info_refs_contains_main':head in static and 'refs/heads/main' in static,'smart_content_type':'application/x-git-upload-pack-advertisement' in smart,'smart_announcement':'# service=git-upload-pack' in smart,'smart_includes_main_ref':head in smart,'dumb_ref_listing':static.strip()}
versions={'git':subprocess.check_output(['git','--version'],text=True).strip(),'python':subprocess.check_output(['python3','--version'],text=True).strip()}
(ROOT/'results.json').write_text(json.dumps({'inputs':'local bare repository; update-server-info; invoke git http-backend info/refs GET','expected':'static dumb refs listing differs from smart CGI service advertisement; both expose main tip','actual':actual,'tool_versions':versions},indent=2)+'\n')
print(json.dumps(actual,indent=2))
