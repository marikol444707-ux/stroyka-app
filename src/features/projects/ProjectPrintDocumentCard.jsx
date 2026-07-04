import React from 'react';

export default function ProjectPrintDocumentCard({
  C,
  Eye,
  btnO,
  card,
  description,
  icon,
  openLabel,
  onOpen,
  title,
}) {
  return (
    <div>
      <div style={{ ...card, padding: '24px', textAlign: 'center' }}>
        <div style={{ fontSize: '40px', marginBottom: '10px' }}>{icon}</div>
        <b style={{ color: C.text, fontSize: '15px', display: 'block', marginBottom: '6px' }}>{title}</b>
        <p style={{ color: C.textMuted, fontSize: '12px', margin: '0 0 16px' }}>{description}</p>
        <button onClick={onOpen} style={btnO}>
          <Eye size={14} />🖨 Открыть {openLabel}
        </button>
      </div>
    </div>
  );
}
