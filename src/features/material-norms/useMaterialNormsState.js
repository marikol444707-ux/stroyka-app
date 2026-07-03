import { useState } from 'react';
import { EMPTY_MATERIAL_NORM_FORM } from '../../utils/materialNormUtils';

export function useMaterialNormsState() {
  const [materialNormSearch, setMaterialNormSearch] = useState('');
  const [materialNormsPage, setMaterialNormsPage] = useState({
    search: '',
    hasMore: false,
    loading: false,
    error: '',
  });
  const [materialNormSuggestions, setMaterialNormSuggestions] = useState([]);
  const [materialNormPreviewSuggestions, setMaterialNormPreviewSuggestions] = useState([]);
  const [materialNormNotice, setMaterialNormNotice] = useState(null);
  const [materialNormSuggestionLoading, setMaterialNormSuggestionLoading] = useState(false);
  const [materialNormCoverageProject, setMaterialNormCoverageProject] = useState('');
  const [newMaterialNorm, setNewMaterialNorm] = useState(EMPTY_MATERIAL_NORM_FORM);
  const [editingMaterialNormId, setEditingMaterialNormId] = useState(null);
  const [estimateSearch, setEstimateSearch] = useState('');
  const [estimateProjectFilter, setEstimateProjectFilter] = useState('');
  const [showArchivedEstimates, setShowArchivedEstimates] = useState(false);

  return {
    editingMaterialNormId,
    estimateProjectFilter,
    estimateSearch,
    materialNormCoverageProject,
    materialNormNotice,
    materialNormPreviewSuggestions,
    materialNormSearch,
    materialNormSuggestionLoading,
    materialNormSuggestions,
    materialNormsPage,
    newMaterialNorm,
    setEditingMaterialNormId,
    setEstimateProjectFilter,
    setEstimateSearch,
    setMaterialNormCoverageProject,
    setMaterialNormNotice,
    setMaterialNormPreviewSuggestions,
    setMaterialNormSearch,
    setMaterialNormSuggestionLoading,
    setMaterialNormSuggestions,
    setMaterialNormsPage,
    setNewMaterialNorm,
    setShowArchivedEstimates,
    showArchivedEstimates,
  };
}
