import React from 'react';
import useProtectedFileObjectUrl from '../features/uploads/useProtectedFileObjectUrl';

export default function ExpenseReceiptPhoto({url, fileSrc, onOpen, style}) {
  const {src, loading, error} = useProtectedFileObjectUrl(url, fileSrc);
  if (loading) return <span role="status">Загрузка чека…</span>;
  if (error || !src) return <span role="alert">Фото чека недоступно</span>;
  return <img src={src} alt="Фото чека" style={style} onClick={() => onOpen?.(src)}/>;
}
