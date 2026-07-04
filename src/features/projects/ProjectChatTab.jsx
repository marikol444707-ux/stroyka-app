import React from 'react';

export default function ProjectChatTab({
  C,
  btnG,
  btnO,
  fileSrc,
  inp,
  loadProjectChat,
  project,
  projectChatMessage,
  projectChatMessages,
  roleColor,
  sendProjectChatMessage,
  setProjectChatMessage,
  setShowPhotoModal,
  user,
}) {
  const messages = projectChatMessages[project.name] || [];

  return (
    <div>
      <b style={{ color: C.text, display: 'block', marginBottom: '15px' }}>Чат проекта</b>
      <div style={{ backgroundColor: C.bg, borderRadius: '12px', padding: '15px', minHeight: '250px', maxHeight: '350px', overflowY: 'auto', marginBottom: '15px', display: 'flex', flexDirection: 'column', gap: '10px', border: '1.5px solid ' + C.border }}>
        {messages.length === 0 ? (
          <p style={{ color: C.textMuted, textAlign: 'center', margin: 'auto', fontSize: '13px' }}>Нет сообщений</p>
        ) : messages.map(message => {
          const isMe = message.authorName === user.name;
          const messagePhoto = fileSrc(message.photoUrl || message.photo_url);

          return (
            <div key={message.id} style={{ display: 'flex', justifyContent: isMe ? 'flex-end' : 'flex-start' }}>
              <div style={{ maxWidth: '80%', backgroundColor: isMe ? C.accent : C.bgWhite, color: isMe ? 'white' : C.text, padding: '10px 14px', borderRadius: isMe ? '16px 16px 4px 16px' : '16px 16px 16px 4px', border: '1.5px solid ' + (isMe ? C.accent : C.border) }}>
                {!isMe && (
                  <div style={{ fontSize: '11px', fontWeight: '700', color: roleColor(message.authorRole), marginBottom: '4px' }}>
                    {message.authorName}
                  </div>
                )}
                {message.text && <p style={{ margin: 0, fontSize: '13px' }}>{message.text}</p>}
                {messagePhoto && <img src={messagePhoto} alt="" style={{ width: '180px', borderRadius: '8px', display: 'block', marginTop: '6px', cursor: 'pointer' }} onClick={() => setShowPhotoModal(messagePhoto)} />}
                <div style={{ fontSize: '10px', color: isMe ? 'rgba(255,255,255,0.7)' : C.textMuted, marginTop: '4px', textAlign: 'right' }}>
                  {message.createdAt ? new Date(message.createdAt).toLocaleTimeString('ru-RU') : ''}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <div style={{ display: 'flex', gap: '8px' }}>
        <input
          placeholder="Написать..."
          value={projectChatMessage}
          onChange={event => setProjectChatMessage(event.target.value)}
          onKeyDown={event => event.key === 'Enter' && sendProjectChatMessage(project.name, projectChatMessage, '')}
          style={{ ...inp, marginBottom: 0, flex: 1 }}
        />
        <button
          onClick={() => {
            if (!projectChatMessages[project.name]) loadProjectChat(project.name);
            sendProjectChatMessage(project.name, projectChatMessage, '');
          }}
          style={btnO}
        >
          ➤
        </button>
      </div>
      {!projectChatMessages[project.name] && (
        <button onClick={() => loadProjectChat(project.name)} style={{ ...btnG, marginTop: '8px', fontSize: '12px' }}>
          Загрузить чат
        </button>
      )}
    </div>
  );
}
