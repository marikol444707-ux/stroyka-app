export const sitePublicationListText = (value) => (
  Array.isArray(value) ? value.join('\n') : String(value || '')
);

export const projectSitePublicationDraft = (project = {}, draftByProjectId = {}) => {
  if (project.id && draftByProjectId[project.id]) return draftByProjectId[project.id];
  return {
    publicShowOnSite: !!project.publicShowOnSite,
    publicIsLive: !!project.publicIsLive,
    publicStatus: project.publicStatus || 'Черновик',
    publicTitle: project.publicTitle || project.name || '',
    publicCategory: project.publicCategory || 'house',
    publicLocation: project.publicLocation || '',
    publicArea: project.publicArea || '',
    publicYear: project.publicYear || String(new Date().getFullYear()),
    publicStage: project.publicStage || project.status || '',
    publicProgress: project.publicProgress ?? project.progress ?? 0,
    publicPriceLabel: project.publicPriceLabel || '',
    publicTerm: project.publicTerm || project.deadline || '',
    publicSummary: project.publicSummary || '',
    publicResult: project.publicResult || '',
    publicPassport: project.publicPassport || '',
    publicTagsText: sitePublicationListText(project.publicTags),
    publicImagesText: sitePublicationListText(project.publicImages),
    publicOriginalImagesText: sitePublicationListText(project.publicOriginalImages),
    publicEnhancedImagesText: sitePublicationListText(project.publicEnhancedImages),
    publicMainImageUrl: project.publicMainImageUrl || '',
    publicAiStatus: project.publicAiStatus || 'Не обработано',
    publicAiNotes: project.publicAiNotes || '',
  };
};

export const projectSitePublicationPayload = (project = {}, draft = {}) => ({
  publicShowOnSite: !!draft.publicShowOnSite,
  publicIsLive: !!draft.publicIsLive,
  publicStatus: draft.publicStatus || 'Черновик',
  publicTitle: draft.publicTitle || project.name,
  publicCategory: draft.publicCategory || 'house',
  publicLocation: draft.publicLocation || '',
  publicArea: draft.publicArea || '',
  publicYear: draft.publicYear || '',
  publicStage: draft.publicStage || '',
  publicProgress: Number(draft.publicProgress || 0),
  publicPriceLabel: draft.publicPriceLabel || '',
  publicTerm: draft.publicTerm || '',
  publicSummary: draft.publicSummary || '',
  publicResult: draft.publicResult || '',
  publicPassport: draft.publicPassport || '',
  publicTags: draft.publicTagsText || '',
  publicImages: draft.publicImagesText || '',
  publicOriginalImages: draft.publicOriginalImagesText || '',
  publicEnhancedImages: draft.publicEnhancedImagesText || '',
  publicMainImageUrl: draft.publicMainImageUrl || '',
  publicAiStatus: draft.publicAiStatus || 'Не обработано',
  publicAiNotes: draft.publicAiNotes || '',
});
