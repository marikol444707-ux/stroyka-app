import { buildAiConversationMessages } from './aiConversation';

export const createAiAssistantActions = ({
  API,
  aiChat,
  aiMessage,
  aiRequestSession,
  chatEndRef,
  directorAgentLoading,
  directorAgentQuestion,
  setAiChat,
  setAiLoading,
  setAiMessage,
  setDirectorAgentAnswer,
  setDirectorAgentError,
  setDirectorAgentLoading,
  setDirectorAgentQuestion,
  setDirectorAgentSteps,
}) => {
  const sendAiMessage = async () => {
    if (!aiMessage.trim() || !aiRequestSession?.active || aiRequestSession.pending) return;
    let messages;
    try {
      messages = buildAiConversationMessages(aiChat, aiMessage);
    } catch (error) {
      setAiChat(previous => [...previous, {role: 'assistant', content: error.message, error: true}]);
      return;
    }
    // The session object survives rerenders, closing the repeated-click window.
    const controller = new AbortController();
    aiRequestSession.controller = controller;
    aiRequestSession.pending = true;
    const isCurrent = () => aiRequestSession.active && !controller.signal.aborted;
    setAiChat(previous => [...previous, {role: 'user', content: aiMessage, time: new Date().toLocaleTimeString('ru-RU')}]);
    setAiMessage('');
    setAiLoading(true);
    try {
      const res = await fetch(API + '/ai-chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        signal: controller.signal,
        body: JSON.stringify({mode: 'construction', messages}),
      });
      const data = await res.json();
      if (!res.ok || data?.ok === false) throw new Error('Не удалось получить ответ. Попробуйте ещё раз.');
      const response = data.response || data.text;
      if (typeof response !== 'string' || !response.trim()) throw new Error('Получен пустой ответ. Попробуйте ещё раз.');
      if (!isCurrent()) return;
      setAiChat(previous => [...previous, {role: 'assistant', content: response, time: new Date().toLocaleTimeString('ru-RU')}]);
    } catch (error) {
      if (!isCurrent() || error?.name === 'AbortError') return;
      setAiChat(previous => [...previous, {role: 'assistant', content: 'Не удалось получить ответ. Попробуйте ещё раз.', error: true}]);
    } finally {
      aiRequestSession.pending = false;
      if (aiRequestSession.controller === controller) aiRequestSession.controller = null;
      if (isCurrent()) {
        setAiLoading(false);
        setTimeout(() => {
          if (isCurrent()) chatEndRef.current?.scrollIntoView?.({behavior: 'smooth', block: 'end'});
        }, 100);
      }
    }
  };

  const askDirectorAgent = async (questionOverride = '') => {
    const question = String(questionOverride || directorAgentQuestion || '').trim();
    if (!question || directorAgentLoading) return;
    setDirectorAgentQuestion(question);
    setDirectorAgentLoading(true);
    setDirectorAgentError('');
    setDirectorAgentAnswer('');
    setDirectorAgentSteps([]);
    try {
      const res = await fetch(API + '/director-agent/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || data.error || 'Ошибка запроса');
      setDirectorAgentAnswer(data.answer || 'Ответ пустой');
      setDirectorAgentSteps(Array.isArray(data.steps) ? data.steps : []);
    } catch (e) {
      setDirectorAgentError(e.message || 'Не удалось получить ответ');
    } finally {
      setDirectorAgentLoading(false);
    }
  };

  return {
    askDirectorAgent,
    sendAiMessage,
  };
};
