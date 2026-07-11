import { buildEstimateChatContext } from '../../utils/estimateChatUtils';


export function createEstimateChatActions({
  API,
  alertFn = window.alert,
  buildContext = buildEstimateChatContext,
  estimateChatActiveEstimateIdRef,
  estimateChatHistoryLoading,
  estimateChatHistoryLoadingRef,
  estimateChatInput,
  estimateChatLoading,
  estimateChatMessages,
  estimateChatRequestRef,
  fetchFn = fetch,
  readApiResult,
  selectedEstimate,
  setEstimateChatHistoryLoading,
  setEstimateChatInput,
  setEstimateChatLoading,
  setEstimateChatMessages,
  setShowEstimateChat,
}) {
  const requestRef = estimateChatRequestRef || { current: 0 };
  const activeEstimateRef = estimateChatActiveEstimateIdRef || { current: null };
  const historyLoadingRef = estimateChatHistoryLoadingRef || { current: false };
  const setHistoryLoading = (value) => {
    historyLoadingRef.current = value;
    setEstimateChatHistoryLoading(value);
  };
  const nextRequestId = () => {
    requestRef.current += 1;
    return requestRef.current;
  };
  const isCurrentRequest = (requestId) => requestRef.current === requestId;

  const handleOpenSelectedEstimateChat = async () => {
    if (!selectedEstimate?.id) return false;
    if (estimateChatLoading && activeEstimateRef.current === selectedEstimate.id) {
      setShowEstimateChat(true);
      return true;
    }
    const requestId = nextRequestId();
    const estimateId = selectedEstimate.id;
    setEstimateChatMessages([]);
    setEstimateChatInput('');
    setEstimateChatLoading(false);
    setHistoryLoading(true);
    setShowEstimateChat(true);
    try {
      const history = await readApiResult(await fetchFn(API + '/estimates/' + estimateId + '/chat-history'));
      if (!isCurrentRequest(requestId)) return false;
      setEstimateChatMessages(Array.isArray(history) ? history : []);
      return true;
    } catch (error) {
      if (isCurrentRequest(requestId)) setEstimateChatMessages([]);
      return false;
    } finally {
      if (isCurrentRequest(requestId)) setHistoryLoading(false);
    }
  };

  const sendEstimateChatMessage = async () => {
    if (
      !selectedEstimate?.id
      || !String(estimateChatInput || '').trim()
      || estimateChatLoading
      || estimateChatHistoryLoading
      || historyLoadingRef.current
    ) return false;
    const requestId = nextRequestId();
    const estimateId = selectedEstimate.id;
    activeEstimateRef.current = estimateId;
    const message = String(estimateChatInput).trim();
    const localHistory = [
      ...(Array.isArray(estimateChatMessages) ? estimateChatMessages : []),
      { role: 'user', content: message, id: Date.now() },
    ];
    setEstimateChatInput('');
    setEstimateChatMessages(localHistory);
    setEstimateChatLoading(true);
    try {
      const data = await readApiResult(await fetchFn(API + '/estimate-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          estimateId,
          message,
          context: buildContext(selectedEstimate),
          history: (Array.isArray(estimateChatMessages) ? estimateChatMessages : []).map((item) => ({
            role: item.role,
            content: item.content,
          })),
        }),
      }));
      if (!isCurrentRequest(requestId)) return false;
      setEstimateChatMessages([
        ...localHistory,
        {
          role: 'assistant',
          content: data?.response || 'Ошибка ответа',
          id: data?.assistantMessageId || Date.now() + 1,
        },
      ]);
      return true;
    } catch (error) {
      if (!isCurrentRequest(requestId)) return false;
      setEstimateChatMessages([
        ...localHistory,
        { role: 'assistant', content: 'Ошибка соединения', id: Date.now() + 1 },
      ]);
      return false;
    } finally {
      if (isCurrentRequest(requestId)) {
        activeEstimateRef.current = null;
        setEstimateChatLoading(false);
      }
    }
  };

  const clearEstimateChatHistory = async () => {
    if (!selectedEstimate?.id || estimateChatHistoryLoading || historyLoadingRef.current) return false;
    const requestId = nextRequestId();
    activeEstimateRef.current = null;
    try {
      await readApiResult(await fetchFn(API + '/estimates/' + selectedEstimate.id + '/chat-history', {
        method: 'DELETE',
      }));
      if (!isCurrentRequest(requestId)) return false;
      setEstimateChatMessages([]);
      setEstimateChatInput('');
      setEstimateChatLoading(false);
      return true;
    } catch (error) {
      if (isCurrentRequest(requestId)) {
        setEstimateChatLoading(false);
        alertFn('Не удалось очистить чат: ' + (error?.message || 'ошибка запроса'));
      }
      return false;
    }
  };

  return {
    clearEstimateChatHistory,
    handleOpenSelectedEstimateChat,
    sendEstimateChatMessage,
  };
}
