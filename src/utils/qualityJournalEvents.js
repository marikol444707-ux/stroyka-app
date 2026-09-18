// In-memory invalidation only: no journal data, credentials or persistent cache.
export const QUALITY_JOURNAL_MUTATED = 'stroyka:quality-journal-mutated';
let revision = 0;
const pendingTokens = new Set();
let uncertain = false;

export const getQualityJournalRevision = () => revision;
export const getQualityJournalMutationState = () => ({
  revision, pendingTokens: [...pendingTokens], pendingCount: pendingTokens.size, uncertain,
});

export const qualityJournalMutationIssue = () => {
  if (uncertain) return 'Результат сохранения журнала неизвестен. Требуется проверка оператором; печать и диагностика заблокированы.';
  if (pendingTokens.size) return 'Сохранение журнала ещё выполняется. Печать и диагностика заблокированы.';
  return '';
};

// Call after a confirmed write, before applying the editor's onSuccess update.
// Listeners invalidate stale GETs synchronously and reload their current scope.
export const notifyQualityJournalMutation = () => {
  revision += 1;
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(QUALITY_JOURNAL_MUTATED));
};

export const beginQualityJournalMutation = () => {
  const token = Symbol('quality-journal-mutation');
  pendingTokens.add(token);
  notifyQualityJournalMutation();
  return token;
};

// Only a confirmed response or an explicitly known non-commit may release the
// pending barrier. No later save or GET can resolve an uncertain server outcome.
export const finishQualityJournalMutation = (token, outcome = {}) => {
  if (!pendingTokens.delete(token)) return;
  if (outcome.uncertain === true || (outcome.confirmed !== true && outcome.uncertain !== false)) uncertain = true;
  notifyQualityJournalMutation();
};
