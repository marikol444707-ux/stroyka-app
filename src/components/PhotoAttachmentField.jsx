import React from 'react';
import { Camera, Image as ImageIcon, ImageOff, LoaderCircle, X } from 'lucide-react';

import useProtectedFileObjectUrl from '../features/uploads/useProtectedFileObjectUrl';


function photoFrameStyle(compact, C) {
  const size = compact ? '54px' : '70px';
  return {
    width: size,
    height: size,
    boxSizing: 'border-box',
    borderRadius: '7px',
    border: '1px solid ' + (C?.border || '#cbd5e1'),
  };
}

function AttachmentPhotoImage({src, setShowPhotoModal, compact, C}) {
  return (
    <img
      src={src}
      alt="Прикрепленное фото"
      onClick={() => setShowPhotoModal && setShowPhotoModal(src)}
      style={{...photoFrameStyle(compact, C), objectFit: 'cover', cursor: 'pointer'}}
    />
  );
}

function ProtectedAttachmentPhotoPreview({url, fileSrc, setShowPhotoModal, compact, C}) {
  const {src, loading, error} = useProtectedFileObjectUrl(url, fileSrc);
  const frameStyle = photoFrameStyle(compact, C);

  if (loading) {
    return (
      <div
        role="status"
        aria-label="Фото загружается"
        style={{...frameStyle, display: 'flex', alignItems: 'center', justifyContent: 'center', color: C?.textMuted || '#64748b', backgroundColor: C?.bg || 'transparent'}}
      >
        <LoaderCircle size={compact ? 14 : 16}/>
      </div>
    );
  }

  if (error || !src) {
    return (
      <div
        role="status"
        aria-label="Фото недоступно"
        title={error}
        style={{...frameStyle, display: 'flex', alignItems: 'center', justifyContent: 'center', color: C?.danger || C?.textMuted || '#64748b', backgroundColor: C?.bg || 'transparent'}}
      >
        <ImageOff size={compact ? 14 : 16}/>
      </div>
    );
  }

  return <AttachmentPhotoImage src={src} setShowPhotoModal={setShowPhotoModal} compact={compact} C={C}/>;
}

function AttachmentPhotoPreview({url, fileSrc, setShowPhotoModal, protectedPreview, compact, C}) {
  if (protectedPreview) {
    return (
      <ProtectedAttachmentPhotoPreview
        url={url}
        fileSrc={fileSrc}
        setShowPhotoModal={setShowPhotoModal}
        compact={compact}
        C={C}
      />
    );
  }
  const src = typeof fileSrc === 'function' ? fileSrc(url) : url;
  return <AttachmentPhotoImage src={src} setShowPhotoModal={setShowPhotoModal} compact={compact} C={C}/>;
}

export default function PhotoAttachmentField({
  C,
  btnG,
  value = '',
  onChange,
  appendPhotos,
  fileSrc,
  setShowPhotoModal,
  projectName = '',
  context = 'photos',
  title = 'Фото',
  emptyText = 'Фото не прикреплены',
  compact = false,
  protectedPreview = false,
}) {
  const galleryRef = React.useRef(null);
  const cameraRef = React.useRef(null);
  const urls = String(value || '').split(',').map(url => url.trim()).filter(Boolean);
  const baseButton = btnG || {
    border: '1px solid #cbd5e1',
    backgroundColor: 'transparent',
    color: C?.text || '#0f172a',
    borderRadius: '8px',
    cursor: 'pointer',
  };
  const handleFiles = async files => {
    const list = Array.from(files || []).filter(Boolean);
    if (!list.length || !appendPhotos) return;
    const nextValue = await appendPhotos(value, list, {projectName, context});
    if (nextValue !== undefined && onChange) onChange(nextValue || '');
  };

  const removePhoto = index => {
    if (onChange) onChange(urls.filter((_, itemIndex) => itemIndex !== index).join(','));
  };

  return (
    <div style={{padding: compact ? '8px' : '10px', border: '1px solid ' + (C?.border || '#cbd5e1'), borderRadius: '8px', backgroundColor: C?.bg || 'transparent'}}>
      <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap', marginBottom: urls.length ? '8px' : 0}}>
        <b style={{fontSize: compact ? '11px' : '12px', color: C?.text || '#0f172a'}}>{title}{urls.length ? ' (' + urls.length + ')' : ''}</b>
        <div style={{display: 'flex', gap: '6px', flexWrap: 'wrap'}}>
          <button type="button" onClick={() => galleryRef.current?.click()} style={{...baseButton, padding: compact ? '5px 8px' : '6px 10px', fontSize: compact ? '10px' : '11px', display: 'inline-flex', alignItems: 'center', gap: '5px'}}>
            <ImageIcon size={12}/>Галерея
          </button>
          <button type="button" onClick={() => cameraRef.current?.click()} style={{...baseButton, padding: compact ? '5px 8px' : '6px 10px', fontSize: compact ? '10px' : '11px', display: 'inline-flex', alignItems: 'center', gap: '5px'}}>
            <Camera size={12}/>Камера
          </button>
        </div>
      </div>
      <input ref={galleryRef} type="file" accept="image/*" multiple style={{display: 'none'}} onChange={async event => { await handleFiles(event.target.files); event.target.value = ''; }}/>
      <input ref={cameraRef} type="file" accept="image/*" capture="environment" style={{display: 'none'}} onChange={async event => { await handleFiles(event.target.files); event.target.value = ''; }}/>
      {urls.length === 0 ? (
        <p style={{color: C?.textMuted || '#64748b', fontSize: '11px', margin: compact ? '6px 0 0' : '8px 0 0'}}>{emptyText}</p>
      ) : (
        <div style={{display: 'flex', gap: '6px', flexWrap: 'wrap'}}>
          {urls.map((url, index) => (
            <div key={url + index} style={{position: 'relative'}}>
              <AttachmentPhotoPreview
                url={url}
                fileSrc={fileSrc}
                setShowPhotoModal={setShowPhotoModal}
                protectedPreview={protectedPreview}
                compact={compact}
                C={C}
              />
              <button type="button" onClick={() => removePhoto(index)} style={{position: 'absolute', top: '-5px', right: '-5px', width: '18px', height: '18px', borderRadius: '50%', border: 'none', backgroundColor: 'rgba(220,38,38,0.95)', color: 'white', cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
                <X size={11}/>
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
