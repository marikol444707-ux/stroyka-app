"""One-shot owner-operated public procurement review on the dedicated Jev host."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
from uuid import uuid4
try:
    from scripts.jev_eis_documents import validate_notice
except ImportError:
    from jev_eis_documents import validate_notice


def run(notice):
    number=validate_notice(notice)
    if os.geteuid()!=0:raise PermissionError('Dedicated host owner only')
    root=Path(__file__).resolve().parent.parent
    runtime=json.loads(Path('/var/lib/stroyka-jev-tools/documents-runtime.json').read_text())
    image=runtime['image']
    if not re.fullmatch(r'sha256:[a-f0-9]{64}',image):raise ValueError('Unpinned document runtime')
    target=Path('/var/lib/stroyka-jev-tools/document-reviews')/number/('snapshot-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8])
    target.mkdir(parents=True,mode=0o700);os.chown(target,10001,10001)
    def container(script,args,network,timeout):
        name='stroyka-eis-review-'+uuid4().hex
        command=['docker','run','--rm','--name',name,'--network',network,'--user','10001:10001',
          '--cap-drop','ALL','--security-opt','no-new-privileges','--memory','1g','--pids-limit','256',
          '--read-only','--tmpfs','/tmp:rw,nosuid,nodev,size=512m','--env','PYTHONPATH=/tools',
          '--mount','type=bind,src='+str(root)+',dst=/tools,readonly',
          '--mount','type=bind,src='+str(root/'dev_control/certificates/russian-trusted-root.pem')+',dst=/cert/root.pem,readonly',
          '--mount','type=bind,src='+str(target)+',dst=/review',
          '--entrypoint','python3',image,'/tools/scripts/'+script,*args]
        try:
            process=subprocess.run(command,capture_output=True,text=True,timeout=timeout)
            if process.returncode:raise RuntimeError('Document step failed: '+script)
        finally:subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=10)
    try:
        container('jev_eis_documents.py',['--notice',notice,'--output','/review'],'bridge',600)
        container('jev_eis_document_report.py',['/review'],'none',360)
        review=json.loads((target/'review.json').read_text())
        selected=[]
        for unit in review['evidence']:
            candidate={k:unit[k] for k in ['id','category','source','locator','text']};candidate['text']=candidate['text'][:1600]
            if len(selected)>=65 or len(json.dumps(selected+[candidate],ensure_ascii=False))>65000:break
            selected.append(candidate)
        payload={'notice_number':number,'evidence':selected}
        code=(root/'scripts/jev_eis_document_model.py').read_text()
        try:
            process=subprocess.run(['docker','exec','-i','--env','DOCUMENT_REVIEW_MODEL='+runtime['text_model'],'stroyka-jev-control','python3','-c',code],
                input=json.dumps(payload,ensure_ascii=False),capture_output=True,text=True,timeout=90)
            response=json.loads(process.stdout)
        except Exception as exc:response={'ok':False,'status':'summary_unavailable','error_type':type(exc).__name__}
        (target/'model-response.json').write_text(json.dumps(response,ensure_ascii=False,indent=2))
        (target/'model-input.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
        container('jev_eis_document_report.py',['/review','--apply-model'],'none',60)
        review=json.loads((target/'review.json').read_text())
        result={'ok':review['complete_text_extraction'] and review['snapshot_consistent'] and review['ai_status']=='grounded',
          'status':review['overall_status'],'notice_number':number,'snapshot':str(target),
          'documents':len(review['documents']),'ai_status':review['ai_status'],
          'issues':review['issues'],'estimate_complete_check':False,'company_eligibility':review['company_eligibility']}
    except Exception as exc:
        result={'ok':False,'status':'review_incomplete','snapshot':str(target),'error_type':type(exc).__name__}
    (target/'run-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    return result
