import { estimateHasLoadedSections } from '../../utils/estimateUtils';

export const projectMaterialEstimateDetailsToLoad = ({
  project,
  activeEstimatesForProject,
}) => {
  if (!project || typeof activeEstimatesForProject !== 'function') return [];

  const seen = new Set();
  return ['Заказчик', 'Материалы']
    .flatMap(kind => activeEstimatesForProject(project, kind) || [])
    .filter(estimate => {
      const key = String(estimate?.id || '');
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return !estimateHasLoadedSections(estimate);
    });
};
