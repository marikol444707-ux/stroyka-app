import {useEffect, useState} from 'react';


const EMPTY_PROTECTED_STATE = {
  sourceUrl: '',
  src: '',
  loading: false,
  error: '',
};

export const isProtectedTenantFileUrl = value => {
  const url = String(value || '').trim();
  return /^\/tenant-files\/[1-9]\d*\/content\/?$/.test(url);
};

export default function useProtectedFileObjectUrl(fileUrl, fileSrc = value => value) {
  const rawUrl = String(fileUrl || '').trim();
  const resolvedUrl = rawUrl && typeof fileSrc === 'function' ? fileSrc(rawUrl) : rawUrl;
  const protectedFile = isProtectedTenantFileUrl(rawUrl);
  const [protectedState, setProtectedState] = useState(EMPTY_PROTECTED_STATE);

  useEffect(() => {
    if (!protectedFile || !resolvedUrl) return undefined;

    const controller = new AbortController();
    let objectUrl = '';
    setProtectedState({sourceUrl: resolvedUrl, src: '', loading: true, error: ''});

    const load = async () => {
      try {
        const response = await fetch(resolvedUrl, {
          credentials: 'include',
          cache: 'no-store',
          signal: controller.signal,
        });
        if (!response.ok) throw new Error('HTTP ' + response.status);
        const blob = await response.blob();
        if (controller.signal.aborted) return;
        objectUrl = URL.createObjectURL(blob);
        setProtectedState({sourceUrl: resolvedUrl, src: objectUrl, loading: false, error: ''});
      } catch (error) {
        if (controller.signal.aborted) return;
        setProtectedState({
          sourceUrl: resolvedUrl,
          src: '',
          loading: false,
          error: error?.message || 'Не удалось загрузить защищенный файл',
        });
      }
    };

    load();
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [protectedFile, resolvedUrl]);

  if (!protectedFile) return {src: resolvedUrl, loading: false, error: ''};
  if (protectedState.sourceUrl !== resolvedUrl) return {src: '', loading: true, error: ''};
  return {
    src: protectedState.src,
    loading: protectedState.loading,
    error: protectedState.error,
  };
}
