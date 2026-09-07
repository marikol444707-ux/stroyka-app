import { useCallback, useRef, useState } from 'react';

export default function useAsyncSubmit(
  action,
  failureMessage = 'Не удалось выполнить действие. Проверьте результат перед повторной отправкой.',
) {
  const inFlight = useRef(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');

  const submit = useCallback(async (...args) => {
    // State alone cannot block a second call before React renders the disabled UI.
    if (inFlight.current) return;
    inFlight.current = true;
    setPending(true);
    setError('');
    try {
      return await action(...args);
    } catch (failure) {
      setError(String(failure?.message || failureMessage));
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }, [action, failureMessage]);

  return {submit, pending, error};
}
