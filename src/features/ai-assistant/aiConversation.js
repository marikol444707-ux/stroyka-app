// Keep these limits aligned with the construction mode of POST /ai-chat.
export const AI_MAX_MESSAGES = 20;
export const AI_MAX_MESSAGE_CHARS = 8000;
export const AI_MAX_TOTAL_CHARS = 24000;

export function buildAiConversationMessages(history, question) {
  if (typeof question !== 'string' || !question.trim()) throw new Error('Введите вопрос');
  if (question.length > AI_MAX_MESSAGE_CHARS) throw new Error('Вопрос слишком длинный: максимум 8000 символов');

  // Only completed user/assistant turns are context. Never include UI errors,
  // pending requests, metadata, privileged roles, or a second copy of this send.
  const pairs = [];
  const messages = Array.isArray(history) ? history : [];
  for (let index = 1; index < messages.length; index += 1) {
    const user = messages[index - 1];
    const assistant = messages[index];
    if (user?.role !== 'user' || assistant?.role !== 'assistant') continue;
    const pair = [user, assistant];
    if (pair.some(message => message.error || typeof message.content !== 'string'
      || !message.content.trim() || message.content.length > AI_MAX_MESSAGE_CHARS)) continue;
    pairs.push(pair.map(({role, content}) => ({role, content})));
  }

  const result = [{role: 'user', content: question}];
  let chars = question.length;
  for (let index = pairs.length - 1; index >= 0; index -= 1) {
    const pair = pairs[index];
    const pairChars = pair[0].content.length + pair[1].content.length;
    if (result.length + 2 > AI_MAX_MESSAGES || chars + pairChars > AI_MAX_TOTAL_CHARS) break;
    result.unshift(...pair);
    chars += pairChars;
  }
  return result;
}
