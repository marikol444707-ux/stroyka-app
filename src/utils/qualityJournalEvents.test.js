let events;
beforeEach(() => {
  jest.isolateModules(() => { events = require('./qualityJournalEvents'); });
});

test('begin invalidates synchronously and concurrent tokens finish independently', () => {
  const snapshots = [];
  const listener = () => snapshots.push(events.getQualityJournalMutationState());
  window.addEventListener(events.QUALITY_JOURNAL_MUTATED, listener);
  try {
    const first = events.beginQualityJournalMutation();
    const second = events.beginQualityJournalMutation();
    expect(snapshots[0]).toMatchObject({ revision: 1, pendingCount: 1, uncertain: false });
    expect(events.qualityJournalMutationIssue()).toMatch(/выполняется/);
    events.finishQualityJournalMutation(first, { confirmed: true, uncertain: false });
    expect(events.getQualityJournalMutationState().pendingTokens).toEqual([second]);
    events.finishQualityJournalMutation(second, { confirmed: false, uncertain: false });
    expect(events.qualityJournalMutationIssue()).toBe('');
    const revision = events.getQualityJournalRevision();
    events.finishQualityJournalMutation(first, { uncertain: true });
    expect(events.getQualityJournalRevision()).toBe(revision);
  } finally {
    window.removeEventListener(events.QUALITY_JOURNAL_MUTATED, listener);
  }
});

test.each([{ confirmed: false, uncertain: true }, undefined])('uncertain or unclassified finish remains sticky: %j', outcome => {
  events.finishQualityJournalMutation(events.beginQualityJournalMutation(), outcome);
  events.finishQualityJournalMutation(events.beginQualityJournalMutation(), { confirmed: true, uncertain: false });
  events.notifyQualityJournalMutation();
  expect(events.getQualityJournalMutationState()).toMatchObject({ pendingCount: 0, uncertain: true });
  expect(events.qualityJournalMutationIssue()).toMatch(/проверка оператором/);
});

test('state callers cannot remove pending tokens through a returned snapshot', () => {
  const token = events.beginQualityJournalMutation();
  events.getQualityJournalMutationState().pendingTokens.length = 0;
  expect(events.getQualityJournalMutationState().pendingCount).toBe(1);
  events.finishQualityJournalMutation(token, { confirmed: false, uncertain: false });
});
