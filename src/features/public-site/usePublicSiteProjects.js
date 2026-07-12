import { useEffect, useMemo, useState } from 'react';
import { API } from '../../api';
import {
  normalizeSiteProject,
  publicProjects,
} from './publicSiteContent';

export const usePublicSiteProjects = () => {
  const [siteProjects, setSiteProjects] = useState(publicProjects);
  const [projectCategory, setProjectCategory] = useState('all');
  const [selectedProjectId, setSelectedProjectId] = useState(publicProjects[0].id);
  const [selectedPhotoIndex, setSelectedPhotoIndex] = useState(0);
  const [sitePricingRules, setSitePricingRules] = useState([]);
  const [leadFileUploadsEnabled, setLeadFileUploadsEnabled] = useState(false);
  const [hasPublishedProjects, setHasPublishedProjects] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const loadSitePricing = async () => {
      try {
        const response = await fetch(API + '/site/pricing');
        if (!response.ok) return;
        const data = await response.json();
        if (cancelled) return;
        setSitePricingRules(Array.isArray(data.rules) ? data.rules : []);
        setLeadFileUploadsEnabled(data.capabilities?.leadFileUploads === true);
      } catch (_) {
        // Если backend ещё не обновлён, калькулятор работает по локальным дефолтам.
      }
    };
    const loadSiteProjects = async () => {
      try {
        const response = await fetch(API + '/site/projects');
        if (!response.ok) return;
        const data = await response.json();
        if (cancelled || !Array.isArray(data) || data.length === 0) return;
        const normalized = data.map(normalizeSiteProject);
        setSiteProjects(normalized);
        setHasPublishedProjects(true);
        setSelectedProjectId(normalized[0].id);
        setSelectedPhotoIndex(0);
      } catch (_) {
        // Если backend ещё не обновлён или опубликованных объектов нет, оставляем демо-галерею.
      }
    };
    loadSitePricing();
    loadSiteProjects();
    return () => { cancelled = true; };
  }, []);

  const filteredProjects = useMemo(() => (
    projectCategory === 'all'
      ? siteProjects
      : siteProjects.filter((project) => project.category === projectCategory)
  ), [projectCategory, siteProjects]);

  const selectedProject = filteredProjects.find((project) => project.id === selectedProjectId)
    || filteredProjects[0]
    || siteProjects[0]
    || publicProjects[0];
  const selectedPhoto = selectedProject.images[selectedPhotoIndex] || selectedProject.images[0];

  const chooseProjectCategory = (category) => {
    const nextProjects = category === 'all'
      ? siteProjects
      : siteProjects.filter((project) => project.category === category);
    setProjectCategory(category);
    setSelectedProjectId(nextProjects[0]?.id || siteProjects[0]?.id || publicProjects[0].id);
    setSelectedPhotoIndex(0);
  };

  const chooseProject = (projectId) => {
    setSelectedProjectId(projectId);
    setSelectedPhotoIndex(0);
  };

  return {
    sitePricingRules,
    leadFileUploadsEnabled,
    hasPublishedProjects,
    projectCategory,
    filteredProjects,
    selectedProject,
    selectedPhoto,
    selectedPhotoIndex,
    setSelectedPhotoIndex,
    chooseProjectCategory,
    chooseProject,
  };
};
