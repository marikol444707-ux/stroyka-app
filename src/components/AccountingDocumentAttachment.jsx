import React, {useState} from 'react';
import {FileText} from 'lucide-react';
import useProtectedFileObjectUrl from '../features/uploads/useProtectedFileObjectUrl';
import SupplierDocumentButton from '../features/uploads/SupplierDocumentButton';

export default function AccountingDocumentAttachment({url, fileSrc, onPhoto, C}) {
  const {src, loading, error, contentType} = useProtectedFileObjectUrl(url, fileSrc);
  const [failedSource, setFailedSource] = useState('');
  const frame = {border:'1px solid '+C.border, background:C.bg, borderRadius:'8px',
    padding:'8px', color:C.text, display:'inline-flex', alignItems:'center', gap:'6px'};
  if (loading) return <span role="status" style={frame}>Загрузка файла…</span>;
  if (error || !src) return <span role="alert" style={frame}>Файл недоступен. Проверьте доступ к документу.</span>;
  const image = contentType ? contentType.startsWith('image/') :
    /\.(jpe?g|png|gif|webp|bmp|avif|heic)(?:[?#]|$)/i.test(url);
  if (image && failedSource !== src) return (
    <button type="button" aria-label="Открыть фото накладной" style={frame}
      onClick={() => onPhoto && onPhoto(src)}>
      <img src={src} alt="Фото накладной" onError={() => setFailedSource(src)}
        style={{width:'72px',height:'72px',objectFit:'cover',borderRadius:'6px'}}/>
    </button>
  );
  const pdf = contentType === 'application/pdf' || /\.pdf(?:[?#]|$)/i.test(url);
  return <div style={{display:'flex',flexDirection:'column',gap:'4px'}}>
    {pdf && <SupplierDocumentButton url={url} fileSrc={fileSrc} label="Открыть документ"/>}
    {image && <span role="status" style={{color:C.textMuted}}>Превью недоступно</span>}
    <a href={src} download={pdf ? 'Накладная.pdf' : ''} style={frame}><FileText size={18}/>
      {pdf ? 'Скачать PDF' : 'Скачать файл'}
    </a>
  </div>;
}
