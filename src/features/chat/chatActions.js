export const createChatActions = ({
  API,
  canUseCompanyChat,
  companyChatContextKey,
  isCompanyChatContextCurrent,
  loadProjectChat,
  notify,
  reloadCompanyMessages,
  setCompanyChatMessage,
  setShowChatPanelRaw,
  setProjectChatMessage,
  showChatPanel,
  unreadMessagesCount,
  user,
}) => {
  const contextIsCurrent = (key) => (
    typeof isCompanyChatContextCurrent === 'function'
      ? isCompanyChatContextCurrent(key)
      : true
  );
  const readError = async (response, fallback) => {
    const payload = await response.json().catch(() => ({}));
    const detail = typeof payload?.detail === 'string' ? payload.detail.trim() : '';
    return detail || `${fallback} (HTTP ${response.status})`;
  };

  const setShowChatPanel = (val) => {
    const next = typeof val === 'function' ? val(showChatPanel) : val;
    setShowChatPanelRaw(next);
    if (!next || !user || unreadMessagesCount <= 0) return Promise.resolve(false);
    if (!canUseCompanyChat) {
      notify?.('Для чата выберите конкретную компанию', 'chat');
      return Promise.resolve(false);
    }
    return (async () => {
      const contextKeyAtRequest = companyChatContextKey;
      try {
        const response = await fetch(API + '/messages/mark-read', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({chatType: 'company'}),
        });
        if (!response.ok) {
          throw new Error(await readError(response, 'Не удалось отметить сообщения прочитанными'));
        }
        if (contextIsCurrent(contextKeyAtRequest)) await reloadCompanyMessages?.();
        return true;
      } catch (error) {
        notify?.(
          `Не удалось отметить сообщения прочитанными: ${error?.message || 'ошибка соединения'}`,
          'chat',
        );
        return false;
      }
    })();
  };

  const sendCompanyChatMessage = async (text, photoUrl) => {
    if (!text && !photoUrl) return false;
    if (!canUseCompanyChat) {
      notify?.('Для чата выберите конкретную компанию', 'chat');
      return false;
    }
    const contextKeyAtRequest = companyChatContextKey;
    try {
      const response = await fetch(API + '/messages', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          chatType: 'company',
          projectId: null,
          text,
          photoUrl,
        }),
      });
      if (!response.ok) {
        throw new Error(await readError(response, 'Не удалось отправить сообщение'));
      }
      if (contextIsCurrent(contextKeyAtRequest)) {
        await reloadCompanyMessages?.();
        if (contextIsCurrent(contextKeyAtRequest)) setCompanyChatMessage('');
      }
      return true;
    } catch (error) {
      notify?.(`Не удалось отправить сообщение: ${error?.message || 'ошибка соединения'}`, 'chat');
      return false;
    }
  };

  const sendProjectChatMessage = async (projectName, text, photoUrl) => {
    if (!text && !photoUrl) return;
    try {
      await fetch(API + '/project-chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          projectName,
          authorId: user.id,
          authorName: user.name,
          authorRole: user.role,
          text,
          photoUrl,
        }),
      });
      await loadProjectChat(projectName);
    } catch (e) {}
    setProjectChatMessage('');
  };

  return {
    sendCompanyChatMessage,
    sendProjectChatMessage,
    setShowChatPanel,
  };
};
