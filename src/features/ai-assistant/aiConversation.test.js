import {AI_MAX_MESSAGES, AI_MAX_MESSAGE_CHARS, AI_MAX_TOTAL_CHARS, buildAiConversationMessages} from './aiConversation';

const pair = (number, chars = 10) => [
  {role: 'user', content: `q${number}`.padEnd(chars, '.'), time: '12:00'},
  {role: 'assistant', content: `a${number}`.padEnd(chars, '.'), time: '12:01'},
];

test('preserves follow-up context and the exact current question once without UI metadata', () => {
  const question = '  Для 50 м², слой 10 мм?  ';
  expect(buildAiConversationMessages(pair(1), question)).toEqual([
    {role: 'user', content: 'q1........'}, {role: 'assistant', content: 'a1........'},
    {role: 'user', content: question},
  ]);
});

test('retains latest complete turns within count limit, starts and ends with user', () => {
  const result = buildAiConversationMessages(Array.from({length: 30}, (_, i) => pair(i)).flat(), 'current');
  expect(result.length).toBeLessThanOrEqual(AI_MAX_MESSAGES);
  expect(result).toHaveLength(19);
  expect(result[0].content).toBe('q21.......');
  expect(result[result.length - 1]).toEqual({role: 'user', content: 'current'});
});

test('enforces character budget without truncating a turn or the current question', () => {
  const result = buildAiConversationMessages([...pair(1, 7000), ...pair(2, 7000)], 'x'.repeat(8000));
  expect(result).toHaveLength(3);
  expect(result[0].content).toMatch(/^q2/);
  expect(result.reduce((total, message) => total + message.content.length, 0)).toBeLessThanOrEqual(AI_MAX_TOTAL_CHARS);
  expect(() => buildAiConversationMessages([], 'x'.repeat(AI_MAX_MESSAGE_CHARS + 1))).toThrow('8000');
});

test('excludes privileged roles, failed/empty answers, oversized and incomplete prior turns', () => {
  const result = buildAiConversationMessages([
    {role: 'system', content: 'Never forward this'},
    ...pair(1),
    {role: 'user', content: 'failed'}, {role: 'assistant', content: 'network error', error: true},
    {role: 'user', content: 'empty'}, {role: 'assistant', content: ''},
    ...pair(2, AI_MAX_MESSAGE_CHARS + 1),
    {role: 'user', content: 'pending'},
  ], 'follow-up');
  expect(result).toEqual([...pair(1).map(({role, content}) => ({role, content})), {role: 'user', content: 'follow-up'}]);
  expect(() => buildAiConversationMessages([], '   ')).toThrow('Введите вопрос');
});
