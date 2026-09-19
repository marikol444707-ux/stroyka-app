import {useCallback,useEffect,useRef,useState} from 'react';

export default function useSupplierTeam(API,user) {
 const scope=`${API}:${user?.id}:${user?.role}`;
 const current=useRef(scope);current.current=scope;
 const generation=useRef(0);
 const [state,setState]=useState({scope,status:'loading',suppliers:[]});
 const reload=useCallback(async()=>{
  const run=++generation.current;
  setState({scope,status:'loading',suppliers:[]});
  try {
   const response=await fetch(API+'/supplier-team',{cache:'no-store'});
   const data=await response.json().catch(()=>null);
   if(current.current!==scope||run!==generation.current)return;
   if(response.status===404){setState({scope,status:'legacy',suppliers:[]});return;}
   if(!response.ok||!Array.isArray(data))throw new Error(data?.detail||'Не удалось загрузить команду');
   const customerResponse=await fetch(API+'/supplier-team/customers',{cache:'no-store'});
   const customers=await customerResponse.json();
   if(!customerResponse.ok||!Array.isArray(customers))throw new Error('Не удалось загрузить назначения');
   if(current.current===scope&&run===generation.current)setState({scope,status:'ready',suppliers:data,customers});
  }catch(error){if(current.current===scope&&run===generation.current)setState({scope,status:'error',suppliers:[],error:error.message});}
 },[API,scope]);
 useEffect(()=>{const counter=generation;current.current=scope;reload();window.addEventListener('focus',reload);return()=>{current.current=null;counter.current++;window.removeEventListener('focus',reload);};},[reload,scope]);
 return {...(state.scope===scope?state:{status:'loading',suppliers:[]}),reload};
}
