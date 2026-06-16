import React from 'react';
import { CheckCircle } from 'lucide-react';

export default function EstimateSelectedStatusActions({selectedEstimate, btnGr, btnG, setEstimateStatusRemote, showLeadership = false}) {
  return (
    <>
      {showLeadership && selectedEstimate.status!=='Активная'&&(
        <button onClick={()=>setEstimateStatusRemote(selectedEstimate,'Активная')} style={btnGr}>
          <CheckCircle size={14}/>Активной
        </button>
      )}
      {showLeadership && selectedEstimate.status==='Архив'&&(
        <button onClick={()=>setEstimateStatusRemote(selectedEstimate,'Черновик')} style={btnG}>
          ↩ Черновик
        </button>
      )}
    </>
  );
}
