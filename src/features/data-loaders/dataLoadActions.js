export function projectChatCacheKey(companyId, projectName) {
  const id = Number(companyId);
  const name = String(projectName || '').trim();
  if (!Number.isInteger(id) || id <= 0 || !name) return '';
  return `${id}:${name}`;
}

export function projectChatFeed(cache, companyId, projectName) {
  const key = projectChatCacheKey(companyId, projectName);
  if (!key || !Array.isArray(cache?.[key])) {
    return {key, messages: [], loaded: false};
  }
  return {key, messages: cache[key], loaded: true};
}

export const createDataLoadActions = ({
  API,
  companyId,
  setChecklistItems,
  setMasterProfile,
  setPricelistItems,
  setProjectChatMessages,
  setShowProfileForm,
  user,
}) => {
  const loadMasterProfile = async () => {
    try {
      const profile = await fetch(API + '/master-profile/' + user.id).then(r => r.json());
      setMasterProfile(profile);
      if (!profile.profileCompleted) setShowProfileForm(true);
    } catch (e) {}
  };

  const loadPricelistItems = async (plId) => {
    const items = await fetch(API + '/pricelists/' + plId + '/items').then(r => r.json());
    setPricelistItems(items);
  };

  const loadProjectChat = async (projectName) => {
    const key = projectChatCacheKey(companyId, projectName);
    if (!key) return [];
    try {
      const msgs = await fetch(API + '/project-chat/' + encodeURIComponent(projectName)).then(r => r.json()).catch(() => []);
      const list = Array.isArray(msgs) ? msgs : [];
      setProjectChatMessages(prev => ({ ...prev, [key]: list }));
      return list;
    } catch (e) {
      return [];
    }
  };

  const loadChecklistItems = async (checklistId) => {
    try {
      const items = await fetch(API + '/checklist-items/' + checklistId).then(r => r.json()).catch(() => []);
      setChecklistItems(prev => ({ ...prev, [checklistId]: Array.isArray(items) ? items : [] }));
    } catch (e) {}
  };

  return {
    loadChecklistItems,
    loadMasterProfile,
    loadPricelistItems,
    loadProjectChat,
  };
};
