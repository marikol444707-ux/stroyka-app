import React from 'react';
import useProtectedFileObjectUrl from '../features/uploads/useProtectedFileObjectUrl';

function WorkPhoto({url, fileSrc, onOpen, index, gallery, title}) {
  const {src, loading, error} = useProtectedFileObjectUrl(url, fileSrc);
  const label = 'Фото работы ' + (index + 1);
  if (loading) return <span role="status">Загрузка фото…</span>;
  if (error || !src) return <span role="alert">Фото недоступно</span>;
  return <button type="button" aria-label={label} title={title}
    onClick={() => onOpen(src)} style={{padding: 2, cursor: 'pointer'}}>
    {gallery ? <img src={src} alt={label} style={{width: 80, height: 80, objectFit: 'cover'}}/> : '📷'}
  </button>;
}

export default function WorkJournalPhotos({urls, ...props}) {
  return String(urls || '').split(',').map(url => url.trim()).filter(Boolean).map((url, index) => (
    <WorkPhoto key={url + index} {...props} {...{url, index}}/>
  ));
}
