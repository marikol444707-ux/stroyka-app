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
    const items = await fetch(API + '/pricelists/' + plId + '/items').then(r => r.json());
    setPricelistItems(items);
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
