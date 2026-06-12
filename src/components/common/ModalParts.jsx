import React from 'react';
import { X } from 'lucide-react';
import { closeButtonStyle, statusPillStyle, textareaStyle } from '../../utils/modalStyles';

export function ModalTitleBlock({title, subtitle, C}) {
  return (
    <div>
      <b style={{color: C.text, fontSize: '16px', display: 'block'}}>{title}</b>
      {subtitle ? <span style={{fontSize: '12px', color: C.textSec}}>{subtitle}</span> : null}
    </div>
  );
}

export function ModalHeaderActions({status, statusVariant = 'warning', onClose, C, btnG}) {
  return (
    <div style={{display: 'flex', alignItems: 'center', gap: '10px'}}>
      {status ? <span style={statusPillStyle(C, statusVariant)}>{status}</span> : null}
      <button onClick={onClose} style={closeButtonStyle(btnG)}>
        <X size={14}/>
      </button>
    </div>
  );
}

export function AiNotice({show, noticeStyle, iconStyle, textStyle, children}) {
  if (!show) return null;
  return (
    <div style={noticeStyle}>
      <span style={iconStyle}>🤖</span>
      <span style={textStyle}>{children}</span>
    </div>
  );
}

export function SummaryCell({label, children, labelStyle, valueStyle}) {
  return (
    <div>
      <p style={labelStyle}>{label}</p>
      <b style={valueStyle}>{children}</b>
    </div>
  );
}

export function TextareaField({label, value, onChange, placeholder, inputStyle, labelStyle, minHeight}) {
  return (
    <>
      <label style={labelStyle}>{label}</label>
      <textarea
        value={value || ''}
        onChange={event => onChange(event.target.value)}
        placeholder={placeholder}
        style={textareaStyle(inputStyle, minHeight)}
      />
    </>
  );
}
