import React from 'react';
import { Check, X } from 'lucide-react';

export default function EstimateCreateActions({btnO, btnG, onCreate, onCancel}) {
  return (
    <div style={{display:'flex',gap:'8px',marginTop:'12px'}}>
      <button onClick={onCreate} style={btnO}>
        <Check size={14}/>Создать
      </button>
      <button onClick={onCancel} style={btnG}>
        <X size={14}/>Отмена
      </button>
    </div>
  );
}
