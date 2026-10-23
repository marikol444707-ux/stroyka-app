import { useCallback, useLayoutEffect, useMemo, useState } from 'react';

const initialAiMessages = [{
  role: 'assistant',
  content: 'Привет! Я ИИ помощник СтройКа. Могу ответить на вопросы по вашим объектам, сметам, складу и финансам. Спрашивайте!',
}];

const emptyConversation = (scope) => ({scope, chat: [], message: '', loading: false});

export function useAiAssistantState({user, companyContext} = {}) {
  const contextLoading = Boolean(companyContext?.loading);
  const scope = user?.id ? JSON.stringify([
    user.id, companyContext?.mode, companyContext?.selectedCompanyId, contextLoading,
  ]) : '';
  const [conversation, setConversation] = useState(() => emptyConversation(scope));
  // Mask the old scope during render, before layout-effect cleanup runs.
  const current = conversation.scope === scope ? conversation : emptyConversation(scope);
  const aiRequestSession = useMemo(() => ({scope, active: false, pending: false, controller: null}), [scope]);
  useLayoutEffect(() => {
    aiRequestSession.active = Boolean(scope) && !contextLoading;
    setConversation(emptyConversation(scope));
    return () => {
      aiRequestSession.active = false;
      aiRequestSession.controller?.abort();
    };
  }, [scope, contextLoading, aiRequestSession]);
  const updateConversation = useCallback((field, value) => {
    setConversation(previous => previous.scope === scope ? {
      ...previous, [field]: typeof value === 'function' ? value(previous[field]) : value,
    } : previous);
  }, [scope]);
  const setAiChat = useCallback(value => updateConversation('chat', value), [updateConversation]);
  const setAiMessage = useCallback(value => updateConversation('message', value), [updateConversation]);
  const setAiLoading = useCallback(value => updateConversation('loading', value), [updateConversation]);
  const {chat: aiChat, message: aiMessage, loading: aiLoading} = current;
  const [aiMessages, setAiMessages] = useState(initialAiMessages);
  const [aiInput, setAiInput] = useState('');
  const [directorAgentQuestion, setDirectorAgentQuestion] = useState('');
  const [directorAgentAnswer, setDirectorAgentAnswer] = useState('');
  const [directorAgentSteps, setDirectorAgentSteps] = useState([]);
  const [directorAgentLoading, setDirectorAgentLoading] = useState(false);
  const [directorAgentError, setDirectorAgentError] = useState('');

  return {
    aiChat,
    aiInput,
    aiLoading,
    aiMessage,
    aiMessages,
    aiRequestSession,
    directorAgentAnswer,
    directorAgentError,
    directorAgentLoading,
    directorAgentQuestion,
    directorAgentSteps,
    setAiChat,
    setAiInput,
    setAiLoading,
    setAiMessage,
    setAiMessages,
    setDirectorAgentAnswer,
    setDirectorAgentError,
    setDirectorAgentLoading,
    setDirectorAgentQuestion,
    setDirectorAgentSteps,
  };
}
