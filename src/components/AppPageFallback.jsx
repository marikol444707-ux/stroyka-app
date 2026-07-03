import React from 'react';

export default function AppPageFallback({ C, card, isMobile }) {
  return (
    <div style={{ padding: isMobile ? '18px' : '24px', color: C.text }}>
      <div style={{ ...card, padding: '18px', display: 'flex', alignItems: 'center', gap: '10px' }}>
        <span style={{ fontSize: '18px' }}>⏳</span>
        <div>
          <div style={{ fontWeight: 800 }}>Загружаю раздел</div>
          <div style={{ color: C.textSec, fontSize: '13px', marginTop: '3px' }}>
            Подгружаю только нужный экран, чтобы приложение быстрее открывалось на телефоне.
          </div>
        </div>
      </div>
    </div>
  );
}
