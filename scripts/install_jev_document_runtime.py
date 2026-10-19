"""Install only the dedicated Jev document runtime; never the Stroyka application."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile

BASE='sha256:8c231608d909734fee19e3ce851ca1725fd6e4e84f20fb5f8a4288a06823ef0d'


def install(text_model):
    if os.geteuid()!=0 or socket.gethostname()!='stroyka-dev-agent.local':raise PermissionError('Dedicated Jev host only')
    if not re.fullmatch(r'[a-zA-Z0-9_./:-]{1,150}',text_model):raise ValueError('Invalid model identifier')
    root=Path(__file__).resolve().parent.parent
    inspected=subprocess.check_output(['docker','image','inspect',BASE,'--format','{{.Id}}'],text=True).strip()
    if inspected!=BASE:raise ValueError('Browser base image changed')
    dockerfile=root/'dev_control/eis_documents/Dockerfile'
    digest=hashlib.sha256(dockerfile.read_bytes()).hexdigest()
    tag='stroyka-eis-documents:runtime-'+digest[:12]
    subprocess.run(['docker','tag',BASE,'stroyka-eis-documents:reviewed-browser-base'],check=True)
    subprocess.run(['docker','build','--pull=false','-t',tag,'-f',str(dockerfile),str(dockerfile.parent)],check=True)
    image=subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}'],text=True).strip()
    command=['docker','run','--rm','--network','none','--read-only','--user','10001:10001',
             '--cap-drop','ALL','--security-opt','no-new-privileges','--memory','1g',
             '--tmpfs','/tmp:rw,nosuid,nodev,size=512m','--env','PYTHONPATH=/tools',
             '--mount','type=bind,src='+str(root)+',dst=/tools,readonly',image,
             '-m','unittest','scripts.test_jev_eis_documents','-v']
    subprocess.run(command,check=True,timeout=180)
    destination=Path('/var/lib/stroyka-jev-tools/documents-runtime.json')
    destination.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    content={'image':image,'base_image':BASE,'dockerfile_sha256':digest,'text_model':text_model}
    with tempfile.NamedTemporaryFile(mode='w',dir=destination.parent,delete=False) as f:
        tmp=Path(f.name);os.chmod(tmp,0o600);json.dump(content,f,indent=2)
    tmp.replace(destination)
    print(json.dumps({'ok':True,'image':image,'document_tests_passed':True,'text_model':text_model}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--text-model',default='openai/gpt-4.1-mini');args=parser.parse_args();install(args.text_model)
