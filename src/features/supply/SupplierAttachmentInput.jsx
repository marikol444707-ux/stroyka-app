import React, {useEffect, useRef, useState} from 'react';

export default function SupplierAttachmentInput({offerId, uploadPhoto, onUploaded, label, attached, onBusy}) {
  const generation = useRef(0);
  const uploadKey = `${offerId}:${label}`;
  const mounted = useRef(true);
  useEffect(() => {mounted.current=true; generation.current++; setBusy(false); setError(''); return () => {mounted.current=false; onBusy?.(false, uploadKey);};}, [offerId, onBusy, uploadKey]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  return <div>
    <label>{busy ? 'Загрузка…' : attached ? 'Файл прикреплён' : label}
      <input type="file" accept=".pdf,image/*" disabled={busy} aria-label={label} onChange={async event => {
        const file = event.target.files[0];
        event.target.value = '';
        if (!file) return;
        const started = generation.current;
        const current = () => mounted.current && generation.current === started;
        setBusy(true); onBusy?.(true, uploadKey); setError('');
        try {
          const url = await uploadPhoto(file, {supplierOfferId:offerId, projectScoped:false, context:'supplier-offers'});
          if (!url) throw new Error('Не удалось загрузить файл. Повторите попытку.');
          if (current()) onUploaded(url);
        } catch (e) {if (current()) setError(e.message || 'Не удалось загрузить файл.');}
        finally {if (current()) {setBusy(false); onBusy?.(false, uploadKey);}}
      }}/>
    </label>
    {error && <p role="alert">{error}</p>}
  </div>;
}
