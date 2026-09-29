import React, {useEffect, useRef, useState} from 'react';
import {API} from '../../api';
import useCustomerCommands from './useCustomerCommands';

export default function CustomerFileSubmission({project,user,refresh,C,btnG}) {
  const [open,setOpen]=useState(false),[subject,setSubject]=useState(''),[body,setBody]=useState('');
  const [file,setFile]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[success,setSuccess]=useState('');
  const owner=useRef({active:true,busy:false});
  const companyId=project.companyId ?? project.company_id;
  const command=useCustomerCommands({scope:`${user.id}:${companyId}:${project.id}`,companyId,refresh});
  useEffect(()=>{const current=owner.current;current.active=true;return()=>{current.active=false;current.controller?.abort();};},[]);
  const blocked=busy || command.blocked;
  async function upload(selected) {
    if(!selected || owner.current.busy || command.blocked)return;
    setError('');setSuccess('');setFile(null);
    if(selected.size>50*1024*1024){setError('Файл должен быть не больше 50 МБ.');return;}
    const current=owner.current;current.busy=true;setBusy(true);
    const controller=new AbortController();current.controller=controller;
    const timeout=setTimeout(()=>controller.abort(),60000);
    try {
      const form=new FormData();form.append('file',selected);form.append('projectId',String(project.id));form.append('context','customer-request');
      const response=await fetch(API+'/upload-photo',{method:'POST',body:form,credentials:'include',signal:controller.signal,
        headers:{'X-Company-Id':String(companyId),'X-Company-Mode':'company'}});
      const data=await response.json();
      const match=/^\/tenant-files\/([1-9]\d*)\/content$/.exec(data.contentUrl || '');
      if(!response.ok || !match || Number(data.companyId)!==Number(companyId) || Number(data.projectId)!==Number(project.id))throw new Error('Upload rejected');
      if(current.active){setFile({id:Number(match[1]),name:selected.name});setSubject(value=>value || selected.name);}
    } catch (_) {if(current.active)setError('Файл не загружен. Попробуйте ещё раз.');}
    finally {clearTimeout(timeout);current.busy=false;if(current.active)setBusy(false);}
  }
  const input={boxSizing:'border-box',display:'block',width:'100%',margin:'8px 0 12px',padding:10,borderRadius:8,border:`1px solid ${C.border}`,background:C.bg,color:C.text};
  return <div style={{margin:'16px 0'}}>
    {!open && <button type="button" style={btnG} onClick={()=>{setOpen(true);setSuccess('');}}>Отправить файл</button>}
    {open && <form onSubmit={async event=>{
      event.preventDefault();if(blocked || owner.current.busy || !file || !subject.trim())return;
      await command.run('/customer-files/send',{method:'POST',body:{projectId:project.id,fileId:file.id,subject:subject.trim(),body:body.trim()},
        onSuccess:()=>{setFile(null);setSubject('');setBody('');setOpen(false);setSuccess('Файл отправлен. Он доступен в переписке объекта.');}});
    }}>
      <p>Файл получит компания, ведущая этот объект.</p>
      <label>Файл (до 50 МБ)<input type="file" disabled={blocked} style={{display:'block',maxWidth:'100%',margin:'8px 0 12px'}}
        onChange={event=>{upload(event.target.files?.[0]);event.target.value='';}}/></label>
      {busy && <p role="status">Загрузка файла…</p>}
      {file && <p>{file.name}</p>}
      <label>Название<input required maxLength={255} disabled={blocked} value={subject} onChange={event=>setSubject(event.target.value)} style={input}/></label>
      <label>Комментарий (необязательно)<textarea maxLength={10000} disabled={blocked} value={body} onChange={event=>setBody(event.target.value)} style={input}/></label>
      <button type="submit" style={btnG} disabled={blocked || !file || !subject.trim()}>Отправить</button>{' '}
      <button type="button" style={btnG} disabled={blocked} onClick={()=>setOpen(false)}>Закрыть</button>
    </form>}
    {(error || command.error) && <p role="alert">{command.error || error}</p>}
    {success && <p role="status">{success}</p>}
  </div>;
}
