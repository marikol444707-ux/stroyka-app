import React from 'react';

export default function EstimateSaveNotice({state}) {
  if (!state || state.status === 'idle') return null;
  const failed = state.status === 'conflict' || state.status === 'error';
  const text = failed ? state.error : {
    dirty: 'Есть несохранённые изменения', saving: 'Сохранение…', saved: 'Изменения сохранены',
  }[state.status];
  return <p role={failed ? 'alert' : 'status'} style={{color: failed ? '#b42318' : 'inherit', padding: '8px 0'}}>{text}</p>;
}
