import { useEffect, useState } from 'react';

const readId = () => {
  const value = new URL(window.location.href).searchParams.get('supplyRequestId');
  return /^[1-9]\d*$/.test(value || '') ? value : '';
};
export default function useSupplierRequestSelection() {
  const [selected, setSelected] = useState(readId);
  useEffect(()=>{
    const update = () => setSelected(readId());
    window.addEventListener('popstate',update);
    return ()=>window.removeEventListener('popstate',update);
  },[]);
  const select = id => {
    const url = new URL(window.location.href);
    if (id) url.searchParams.set('supplyRequestId', String(id));
    else url.searchParams.delete('supplyRequestId');
    window.history.pushState(window.history.state, '', url);
    setSelected(id ? String(id) : '');
  };
  return [selected, select];
}
