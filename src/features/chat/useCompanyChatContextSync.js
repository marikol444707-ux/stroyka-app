import {useCallback, useEffect, useRef} from 'react';

const positiveId = (value) => {
  const number = Number(value);
  return Number.isInteger(number) && number > 0 ? number : null;
};

const responseError = async (response, fallback) => {
  const payload = await response.json().catch(() => ({}));
  const detail = typeof payload?.detail === 'string' ? payload.detail.trim() : '';
  return detail || `${fallback} (HTTP ${response.status})`;
};

export function useCompanyChatContextSync({
  API,
  companyContext,
  notify,
  setCompanyMessages,
  user,
}) {
  const sequenceRef = useRef(0);
  const controllerRef = useRef(null);
  const contextKeyRef = useRef('');
  const notifyRef = useRef(notify);
  notifyRef.current = notify;

  const companyId = positiveId(companyContext?.selectedCompanyId);
  const userId = positiveId(user?.id);
  const canUseCompanyChat = Boolean(
    userId
      && !companyContext?.loading
      && companyContext?.mode === 'company'
      && companyId,
  );
  const contextKey = canUseCompanyChat ? `${userId}:${companyId}` : '';
  contextKeyRef.current = contextKey;

  const reloadCompanyMessages = useCallback(async () => {
    if (!contextKey) {
      setCompanyMessages([]);
      return false;
    }

    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    const sequence = ++sequenceRef.current;
    try {
      const response = await fetch((API || '') + '/messages', {signal: controller.signal});
      if (!response.ok) {
        throw new Error(await responseError(response, 'Не удалось загрузить чат компании'));
      }
      const payload = await response.json();
      if (!Array.isArray(payload)) {
        throw new Error('Сервер вернул некорректный список сообщений');
      }
      if (sequence !== sequenceRef.current || contextKeyRef.current !== contextKey) return false;
      setCompanyMessages(payload);
      return true;
    } catch (error) {
      if (error?.name === 'AbortError') return false;
      if (sequence !== sequenceRef.current || contextKeyRef.current !== contextKey) return false;
      notifyRef.current?.(error?.message || 'Не удалось загрузить чат компании', 'chat');
      return false;
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null;
    }
  }, [API, contextKey, setCompanyMessages]);

  const isCompanyChatContextCurrent = useCallback(
    (key) => Boolean(key) && contextKeyRef.current === key,
    [],
  );

  useEffect(() => {
    sequenceRef.current += 1;
    controllerRef.current?.abort();
    controllerRef.current = null;
    setCompanyMessages([]);
    if (!contextKey) return undefined;

    reloadCompanyMessages();
    return () => {
      sequenceRef.current += 1;
      controllerRef.current?.abort();
      controllerRef.current = null;
    };
  }, [contextKey, reloadCompanyMessages, setCompanyMessages]);

  return {
    canUseCompanyChat,
    companyChatContextKey: contextKey,
    isCompanyChatContextCurrent,
    reloadCompanyMessages,
  };
}
