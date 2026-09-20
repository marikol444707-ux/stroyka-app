import React, {useEffect, useRef, useState} from 'react';

// Fetch on demand so each download rechecks the current server authority.
export default function SupplyFileLink({url, fileSrc = value => value, children}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const controller = useRef(null);
  useEffect(() => {setError(''); setBusy(false); return () => controller.current?.abort();}, [url]);
  if (!url) return null;
  const valid = /^\/tenant-files\/[1-9]\d*\/content$/.test(url) || /^\/uploads\//.test(url);
  return <span style={{display:'inline-block', marginRight:12}}>
    <button type="button" disabled={busy} onClick={async () => {
      setError('');
      if (!valid) {setError('Ссылка устарела. Попросите отправителя прикрепить файл заново.'); return;}
      const request = new AbortController();
      controller.current = request;
      setBusy(true);
      try {
        const response = await fetch(fileSrc(url), {credentials:'include', cache:'no-store', signal:request.signal});
        if (!response.ok) throw new Error(response.status === 403 ? 'Доступ к файлу отозван или не предоставлен.' : 'Не удалось скачать файл. Повторите попытку.');
        const blob = await response.blob();
        if (request.signal.aborted) return;
        const objectUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        const encoded = response.headers?.get('Content-Disposition')?.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
        let name = 'документ';
        try {if (encoded) name = decodeURIComponent(encoded);} catch { /* safe fallback */ }
        link.href = objectUrl; link.download = name; document.body.appendChild(link); link.click(); link.remove();
        setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      } catch (e) {if (e.name !== 'AbortError') setError(e.message);}
      finally {if (!request.signal.aborted) setBusy(false);}
    }}>{busy ? 'Загрузка…' : children}</button>
    {error && <span role="alert" style={{display:'block'}}>{error}</span>}
  </span>;
}
