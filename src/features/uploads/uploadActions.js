export const createUploadActions = ({
  API,
  activePage,
  activeProjectTab,
  expandedProject,
  masterProjectId,
  projects,
}) => {
  const uploadPhoto = async (file, meta = {}) => {
    const projectFromExpanded = (projects || []).find(pr => String(pr.id) === String(expandedProject))?.name || '';
    const projectFromMaster = (projects || []).find(pr => String(pr.id) === String(masterProjectId))?.name || '';
    const projectName = meta.projectName || meta.project || projectFromExpanded || projectFromMaster || '';
    const context = meta.context || activeProjectTab || activePage || 'general';
    const fd = new FormData();
    fd.append('file', file);
    if (projectName) fd.append('projectName', projectName);
    if (context) fd.append('context', context);
    try {
      const res = await fetch(API + '/upload-photo', { method: 'POST', body: fd });
      const data = await res.json();
      return data.url;
    } catch {
      return '';
    }
  };

  const uploadMultiplePhotos = async (files, meta = {}) => {
    const urls = [];
    for (const f of Array.from(files || [])) {
      const u = await uploadPhoto(f, meta);
      if (u) urls.push(u);
    }
    return urls.join(',');
  };

  const appendPhotos = async (existing, files, meta = {}) => {
    const added = await uploadMultiplePhotos(files, meta);
    if (!added) return existing || '';
    return existing ? existing + ',' + added : added;
  };

  return {
    appendPhotos,
    uploadMultiplePhotos,
    uploadPhoto,
  };
};
