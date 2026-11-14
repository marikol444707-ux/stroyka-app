// Action factories are rebuilt on render; keep request order with the stable setter.
const pricelistRequests = new WeakMap();

export const createDataLoadActions = ({
  API,
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
    const request = (pricelistRequests.get(setPricelistItems) || 0) + 1;
    pricelistRequests.set(setPricelistItems, request);
    setPricelistItems([]);
    if (!plId) return { items: [], error: '' };
    try {
      const response = await fetch(API + '/pricelists/' + plId + '/items');
      const items = await response.json();
      if (!response.ok || !Array.isArray(items)) {
        throw new Error(typeof items?.detail === 'string' ? items.detail : 'Не удалось загрузить прайс-лист');
      }
      if (request === pricelistRequests.get(setPricelistItems)) setPricelistItems(items);
      return { items, error: '' };
    } catch (error) {
      return { items: [], error: error.message || 'Не удалось загрузить прайс-лист' };
    }
  };

  const loadProjectChat = async (projectName) => {
    try {
      const msgs = await fetch(API + '/project-chat/' + encodeURIComponent(projectName)).then(r => r.json()).catch(() => []);
      setProjectChatMessages(prev => ({ ...prev, [projectName]: Array.isArray(msgs) ? msgs : [] }));
    } catch (e) {}
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
