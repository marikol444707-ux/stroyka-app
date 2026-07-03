import { useState } from 'react';

const initialAiMessages = [{
  role: 'assistant',
  content: 'Привет! Я ИИ помощник СтройКа. Могу ответить на вопросы по вашим объектам, сметам, складу и финансам. Спрашивайте!',
}];

export function useAiAssistantState() {
  const [aiMessages, setAiMessages] = useState(initialAiMessages);
  const [aiInput, setAiInput] = useState('');
  const [aiLoading, setAiLoading] = useState(false);
  const [aiChat, setAiChat] = useState([]);
  const [aiMessage, setAiMessage] = useState('');
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
