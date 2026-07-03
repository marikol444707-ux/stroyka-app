import { useState } from 'react';
import {
  createDistributeBrigadeForm,
  createEstimateItemForm,
  createEstimateSectionForm,
  createFromEstimateForm,
  createGenerateEstimateForm,
  createGeneratePricelistForm,
  createNewEstimateForm,
} from './estimateInitialForms';

export function useEstimateWorkflowState() {
  const [newEstimate, setNewEstimate] = useState(createNewEstimateForm);
  const [showVersionHistory, setShowVersionHistory] = useState(false);
  const [estimateVersions, setEstimateVersions] = useState([]);
  const [selectedVersionsToCompare, setSelectedVersionsToCompare] = useState([]);
  const [importValidationWarnings, setImportValidationWarnings] = useState([]);
  const [importValidating, setImportValidating] = useState(false);
  const [estimateIssueFocusKey, setEstimateIssueFocusKey] = useState('');
  const [showEstimateIssuesOnly, setShowEstimateIssuesOnly] = useState(false);
  const [showEstimateWorkSummary, setShowEstimateWorkSummary] = useState(false);
  const [executionPriceFillPercent, setExecutionPriceFillPercent] = useState(50);
  const [showEstimateChat, setShowEstimateChat] = useState(false);
  const [estimateChatMessages, setEstimateChatMessages] = useState([]);
  const [estimateChatInput, setEstimateChatInput] = useState('');
  const [estimateChatLoading, setEstimateChatLoading] = useState(false);
  const [showGenerateEstimate, setShowGenerateEstimate] = useState(false);
  const [generateForm, setGenerateForm] = useState(createGenerateEstimateForm);
  const [generating, setGenerating] = useState(false);
  const [showGeneratePricelist, setShowGeneratePricelist] = useState(false);
  const [generatePricelistForm, setGeneratePricelistForm] = useState(createGeneratePricelistForm);
  const [generatingPricelist, setGeneratingPricelist] = useState(false);
  const [showFromEstimate, setShowFromEstimate] = useState(false);
  const [fromEstimateForm, setFromEstimateForm] = useState(createFromEstimateForm);
  const [creatingFromEstimate, setCreatingFromEstimate] = useState(false);
  const [showDistribute, setShowDistribute] = useState(false);
  const [showWorkAssignment, setShowWorkAssignment] = useState(false);
  const [distributeAssignments, setDistributeAssignments] = useState({});
  const [distributeBrigades, setDistributeBrigades] = useState([]);
  const [newDistributeBrigade, setNewDistributeBrigade] = useState(createDistributeBrigadeForm);
  const [distributing, setDistributing] = useState(false);
  const [newEstimateSection, setNewEstimateSection] = useState(createEstimateSectionForm);
  const [newEstimateItem, setNewEstimateItem] = useState(createEstimateItemForm);

  return {
    creatingFromEstimate, distributeAssignments, distributeBrigades, distributing,
    estimateChatInput, estimateChatLoading, estimateChatMessages, estimateIssueFocusKey,
    estimateVersions, executionPriceFillPercent, fromEstimateForm, generateForm,
    generatePricelistForm, generating, generatingPricelist, importValidating,
    importValidationWarnings, newDistributeBrigade, newEstimate, newEstimateItem,
    newEstimateSection, selectedVersionsToCompare, setCreatingFromEstimate,
    setDistributeAssignments, setDistributeBrigades, setDistributing, setEstimateChatInput,
    setEstimateChatLoading, setEstimateChatMessages, setEstimateIssueFocusKey,
    setEstimateVersions, setExecutionPriceFillPercent, setFromEstimateForm, setGenerateForm,
    setGeneratePricelistForm, setGenerating, setGeneratingPricelist, setImportValidating,
    setImportValidationWarnings, setNewDistributeBrigade, setNewEstimate, setNewEstimateItem,
    setNewEstimateSection, setSelectedVersionsToCompare, setShowDistribute, setShowEstimateChat,
    setShowEstimateIssuesOnly, setShowEstimateWorkSummary, setShowFromEstimate,
    setShowGenerateEstimate, setShowGeneratePricelist, setShowVersionHistory,
    setShowWorkAssignment, showDistribute, showEstimateChat, showEstimateIssuesOnly,
    showEstimateWorkSummary, showFromEstimate, showGenerateEstimate, showGeneratePricelist,
    showVersionHistory, showWorkAssignment,
  };
}
