import React from 'react';
import { Archive, CheckCircle } from 'lucide-react';

export default function EstimateSelectedStatusActions({selectedEstimate, btnGr, btnG, setEstimateStatusRemote}) {
  return (
    <>
      {selectedEstimate.status!=='Активная'&&(
        <button onClick={()=>setEstimateStatusRemote(selectedEstimate,'Активная')} style={btnGr}>
          <CheckCircle size={14}/>Активной
        </button>
      )}
      {selectedEstimate.status!=='Архив'&&(
        <button onClick={()=>setEstimateStatusRemote(selectedEstimate,'Архив')} style={btnG}>
          <Archive size={14}/>В архив
        </button>
      )}
      {selectedEstimate.status==='Архив'&&(
        <button onClick={()=>setEstimateStatusRemote(selectedEstimate,'Черновик')} style={btnG}>
          ↩ Черновик
        </button>
      )}
    </>
  );
}
