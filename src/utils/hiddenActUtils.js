export const actStatusForJournalWork = (work, hiddenActs = []) => {
  if (!work?.hiddenWork) return null;
  const act = (hiddenActs || []).find(item => (
    item.projectName === work.project
    && (item.workName || '').trim() === (work.description || '').trim()
  ));
  if (!act) return { status: 'none', icon: '❓', tip: 'АОСР не найден' };
  if (act.status === 'Подписан') return { status: 'signed', icon: '✅', tip: 'АОСР подписан', act };
  return { status: 'draft', icon: '⏳', tip: 'АОСР черновик — ждёт подписей', act };
};
