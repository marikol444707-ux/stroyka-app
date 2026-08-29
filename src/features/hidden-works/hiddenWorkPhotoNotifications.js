const hiddenWorkItemKey = (estimate, sectionIndex, itemIndex, item) => String(
  item?.estimateItemKey
  || item?.estimate_item_key
  || item?.workKey
  || item?.work_key
  || item?.key
  || item?.id
  || (String(estimate?.id || '') + ':' + sectionIndex + ':' + itemIndex)
).trim();

const lower = value => String(value || '').trim().toLowerCase();

export const buildHiddenWorkPhotoNotifications = ({
  user,
  estimatesList = [],
  brigadeContracts = [],
  brigadeContractItems = [],
  workJournal = [],
} = {}) => {
  if (!user || !['мастер', 'субподрядчик', 'бригадир'].includes(user.role)) return [];

  const recipient = {
    recipientUserId: user.id,
    recipientName: user.name || '',
    type: 'work',
    title: 'Фотоотчёт обязателен',
    icon: '📷',
    color: '#f97316',
    read: false,
    time: 'До подтверждения',
  };
  const userName = lower(user.name);
  const userBrigade = lower(user.brigade);
  const userId = String(user.id ?? '').trim();
  const belongsToUser = row => {
    const ownerId = String(
      row?.contractorId ?? row?.contractor_id ?? row?.masterId ?? row?.master_id ?? ''
    ).trim();
    if (ownerId) return Boolean(userId && ownerId === userId);
    const ownerName = lower(
      row?.brigadeName ?? row?.brigade_name ?? row?.masterName ?? row?.master_name
    );
    return Boolean(ownerName && (ownerName === userName || ownerName === userBrigade));
  };
  const userContractIds = new Set(
    (Array.isArray(brigadeContracts) ? brigadeContracts : [])
      .filter(belongsToUser)
      .map(contract => String(contract.id ?? '').trim())
      .filter(Boolean)
  );
  const contractItems = Array.isArray(brigadeContractItems) ? brigadeContractItems : [];
  const journalRows = Array.isArray(workJournal) ? workJournal : [];
  const result = [];

  journalRows.forEach(row => {
    const rowMasterId = String(row.masterId ?? row.master_id ?? '').trim();
    const belongsToUser = (
      (rowMasterId && userId && rowMasterId === userId)
      || (userName && lower(row.masterName ?? row.master_name) === userName)
    );
    const status = lower(row.status);
    if (
      belongsToUser
      && Boolean(row.hiddenWork ?? row.hidden_work)
      && !String(row.photoUrl ?? row.photo_url ?? '').trim()
      && !['подтверждено', 'отклонено', 'аннулировано'].includes(status)
    ) {
      result.push({
        ...recipient,
        id: 'hidden-work-photo:journal:' + row.id,
        text: 'Скрытая работа «' + (row.description || 'Без названия') + '» на объекте «' + (row.project || '—') + '» требует фото до подтверждения.',
      });
    }
  });

  const journalKeys = new Set(journalRows.map(row => String(row.estimateItemKey ?? row.estimate_item_key ?? '').trim()).filter(Boolean));
  (Array.isArray(estimatesList) ? estimatesList : []).forEach(estimate => {
    if (lower(estimate.status || 'Активная') !== 'активная') return;
    const projectName = estimate.projectName || estimate.project_name || '';
    const workPackage = estimate.workPackage || estimate.work_package || 'Основная';
    (estimate.sections || []).forEach((section, sectionIndex) => {
      (section.items || []).forEach((item, itemIndex) => {
        if (!Boolean(item.hiddenWork ?? item.hidden_work)) return;
        const quantity = Number(item.quantity || 0);
        const done = Number(item.doneQuantity ?? item.done_quantity ?? 0);
        if (quantity > 0 && done >= quantity) return;
        const itemKey = hiddenWorkItemKey(estimate, sectionIndex, itemIndex, item);
        if (journalKeys.has(itemKey)) return;
        const namedToUser = (
          (userName && lower(item.brigadeName ?? item.brigade_name) === userName)
          || (userBrigade && lower(item.brigadeName ?? item.brigade_name) === userBrigade)
        );
        const assignedByContract = contractItems.some(contractItem => {
          const contractId = String(contractItem.contractId ?? contractItem.contract_id ?? '').trim();
          if (!(contractId && userContractIds.has(contractId)) && !belongsToUser(contractItem)) return false;
          const sameProject = !String(contractItem.projectName ?? contractItem.project_name ?? '').trim()
            || String(contractItem.projectName ?? contractItem.project_name).trim() === String(projectName).trim();
          const samePackage = !String(contractItem.workPackage ?? contractItem.work_package ?? '').trim()
            || String(contractItem.workPackage ?? contractItem.work_package).trim() === String(workPackage).trim();
          const contractKey = String(contractItem.estimateItemKey ?? contractItem.estimate_item_key ?? '').trim();
          const sameKey = itemKey && contractKey && itemKey === contractKey;
          const sameName = lower(contractItem.name ?? contractItem.description) === lower(item.name ?? item.description);
          return sameProject && samePackage && (sameKey || sameName);
        });
        if (!namedToUser && !assignedByContract) return;
        result.push({
          ...recipient,
          id: 'hidden-work-photo:estimate:' + estimate.id + ':' + itemKey,
          text: 'Работа «' + (item.name || item.description || 'Без названия') + '» на объекте «' + (projectName || '—') + '» скрытая: перед отправкой приложите фотоотчёт.',
        });
      });
    });
  });

  return result;
};
