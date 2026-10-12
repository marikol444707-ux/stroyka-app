import {useCallback,useEffect,useRef,useState} from 'react';

export default function useConnectionRequests(path,actorId='') {
  const scope=path+':'+actorId;
  const current=useRef(scope);current.current=scope;
  const generation=useRef(0);
  const request=useRef(null);
  const locked=useRef(false);
  const [offset,setOffset]=useState(0);
  const [state,setState]=useState({scope,items:[],status:'loading'});
  const [command,setCommand]=useState({scope,busy:false,error:'',notice:''});
  const reload=useCallback(async()=>{
    const run=++generation.current;
    request.current?.abort();
    const abort=new AbortController();request.current=abort;
    setState({scope,status:'loading',items:[]});
    try {
      const response=await fetch(path+'?limit=25&offset='+offset,{cache:'no-store',signal:abort.signal});
      const body=await response.json();
      if(!response.ok)throw new Error(typeof body.detail==='string'?body.detail:'Не удалось загрузить запросы');
      if(current.current===scope&&run===generation.current)setState({scope,status:'ready',...body});
    }catch(error){if(!abort.signal.aborted&&current.current===scope&&run===generation.current)setState({scope,status:'error',items:[],error:error.message});}
  },[path,scope,offset]);
  useEffect(()=>{
    const counter=generation;const pendingRequest=request;
    current.current=scope;locked.current=false;setCommand({scope,busy:false,error:'',notice:''});
    reload();window.addEventListener('focus',reload);
    return()=>{current.current=null;counter.current++;pendingRequest.current?.abort();window.removeEventListener('focus',reload);};
  },[scope,reload]);
  const send=async(url,body,notice,onChanged)=>{
    if(locked.current)return false;
    locked.current=true;setCommand({scope,busy:true,error:'',notice:''});
    try {
      const response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      const result=await response.json();
      if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:'Не удалось выполнить действие. Обновите список');
      if(current.current!==scope)return false;
      setCommand({scope,busy:true,error:'',notice});
      await reload();
      if(current.current!==scope)return false;
      await Promise.resolve().then(()=>onChanged?.()).catch(()=>{});
      return current.current===scope;
    }catch(error){if(current.current===scope)setCommand({scope,busy:true,error:error.message,notice:''});return false;}
    finally{if(current.current===scope){locked.current=false;setCommand(c=>({...c,busy:false}));}}
  };
  return {...(state.scope===scope?state:{status:'loading',items:[]}),
    ...(command.scope===scope?command:{busy:false,error:'',notice:''}),
    loadError:state.scope===scope?state.error:'',reload,send,offset,setOffset};
}
