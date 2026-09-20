export const createUploadActions = ({
  API,
  activePage,
  activeProjectTab,
  expandedProject,
  masterProjectId,
  projects,
}) => {
  const uploadPhoto = async (file, meta = {}) => {
    const projectScoped = meta.projectScoped !== false;
    const projectFromExpanded = projectScoped
      ? (projects || []).find(pr => String(pr.id) === String(expandedProject))?.name || ''
      : '';
    const projectFromMaster = projectScoped
      ? (projects || []).find(pr => String(pr.id) === String(masterProjectId))?.name || ''
      : '';
    const projectName = projectScoped
      ? meta.projectName || meta.project || projectFromExpanded || projectFromMaster || ''
      : '';
    const explicitProjectId = projectScoped ? meta.projectId || meta.project_id || '' : '';
    const projectMatches = (projects || []).filter(pr => String(pr.name || '') === String(projectName));
    const projectId = explicitProjectId || (projectMatches.length === 1 ? projectMatches[0].id : '');
    const context = meta.context || activeProjectTab || activePage || 'general';
    const fd = new FormData();
    fd.append('file', file);
    if (meta.supplierOfferId) fd.append('supplierOfferId', String(meta.supplierOfferId));
    if (projectName) fd.append('projectName', projectName);
    if (projectId) fd.append('projectId', String(projectId));
    if (context) fd.append('context', context);
    try {
      const uploadPath = meta.supplierOfferId ? '/supplier-offers/' + meta.supplierOfferId + '/files' : '/upload-photo';
      const res = await fetch(API + uploadPath, { method: 'POST', body: fd });
      if (res.ok === false) return '';
      const data = await res.json();
      return data.contentUrl || data.url;
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
