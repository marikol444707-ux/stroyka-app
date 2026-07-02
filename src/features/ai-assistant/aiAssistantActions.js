export const createAiAssistantActions = ({
  API,
  aiChat,
  aiMessage,
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
  const callAI = async (prompt, conversational) => {
    setAiLoading(true);
    try {
      let messages;
      if (conversational) {
        messages = [...aiChat.map((m) => ({ role: m.role, content: m.content })), { role: 'user', content: prompt }];
      } else {
        messages = [{ role: 'user', content: prompt }];
      }
      const res = await fetch(API + '/ai-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages }),
      });
      const data = await res.json();
      const text = data.response || data.text || 'Нет ответа';
      setAiLoading(false);
      return text;
    } catch (e) {
      setAiLoading(false);
      return '';
    }
  };

  const sendAiMessage = async () => {
    if (!aiMessage.trim()) return;
    const userMsg = { role: 'user', content: aiMessage, time: new Date().toLocaleTimeString('ru-RU') };
    setAiChat((prev) => [...prev, userMsg]);
    setAiMessage('');
    const response = await callAI(aiMessage, true);
    const assistantMsg = { role: 'assistant', content: response, time: new Date().toLocaleTimeString('ru-RU') };
    setAiChat((prev) => [...prev, assistantMsg]);
    setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
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
