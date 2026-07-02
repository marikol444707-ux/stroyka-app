export const createChatActions = ({
  API,
  loadProjectChat,
  setCompanyChatMessage,
  setCompanyMessages,
  setProjectChatMessage,
  user,
}) => {
  const sendCompanyChatMessage = async (text, photoUrl) => {
    if (!text && !photoUrl) return;
    try {
      await fetch(API + '/messages', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          chatType: 'company',
          projectId: null,
          authorId: user.id,
          authorName: user.name,
          authorRole: user.role,
          text,
          photoUrl,
        }),
      });
      const msgs = await fetch(API + '/messages').then(r => r.json()).catch(() => []);
      setCompanyMessages(Array.isArray(msgs) ? msgs : []);
    } catch (e) {
      const msg = {
        id: Date.now(),
        text,
        photo_url: photoUrl,
        author_name: user.name,
        author_role: user.role,
        created_at: new Date().toISOString(),
      };
      setCompanyMessages(prev => [...prev, msg]);
    }
    setCompanyChatMessage('');
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
  };
};
