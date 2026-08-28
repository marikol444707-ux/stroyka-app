import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import {
  createEstimateItemForm,
  createEstimateSectionForm,
  createFromEstimateForm,
  createGenerateEstimateForm,
  createGeneratePricelistForm,
  createNewEstimateForm,
} from './estimateInitialForms';

export function useEstimateWorkflowState(companyContextKey = '', selectedEstimateId = null) {
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
  const [estimateChatHistoryLoading, setEstimateChatHistoryLoading] = useState(false);
  const [estimateChatLoading, setEstimateChatLoading] = useState(false);
  const estimateChatActiveEstimateIdRef = useRef(null);
  const estimateChatHistoryLoadingRef = useRef(false);
  const estimateChatRequestRef = useRef(0);
  const estimateVersionRequestRef = useRef(0);
  const [showGenerateEstimate, setShowGenerateEstimate] = useState(false);
  const [generateForm, setGenerateForm] = useState(createGenerateEstimateForm);
  const [generating, setGenerating] = useState(false);
  const [showGeneratePricelist, setShowGeneratePricelist] = useState(false);
  const [generatePricelistForm, setGeneratePricelistForm] = useState(createGeneratePricelistForm);
  const [generatingPricelist, setGeneratingPricelist] = useState(false);
  const [showFromEstimate, setShowFromEstimate] = useState(false);
  const [fromEstimateForm, setFromEstimateForm] = useState(createFromEstimateForm);
  const [creatingFromEstimate, setCreatingFromEstimate] = useState(false);
  const [showWorkAssignment, setShowWorkAssignment] = useState(false);
  const [newEstimateSection, setNewEstimateSection] = useState(createEstimateSectionForm);
  const [newEstimateItem, setNewEstimateItem] = useState(createEstimateItemForm);

  useLayoutEffect(() => {
    estimateChatRequestRef.current += 1;
    estimateVersionRequestRef.current += 1;
    estimateChatActiveEstimateIdRef.current = null;
    estimateChatHistoryLoadingRef.current = false;
  }, [companyContextKey, selectedEstimateId]);

  useEffect(() => {
    setShowEstimateChat(false);
    setEstimateChatMessages([]);
    setEstimateChatInput('');
    setEstimateChatHistoryLoading(false);
    setEstimateChatLoading(false);
    setShowVersionHistory(false);
    setEstimateVersions([]);
    setSelectedVersionsToCompare([]);
  }, [companyContextKey, selectedEstimateId]);

  return {
    creatingFromEstimate,
    estimateChatActiveEstimateIdRef, estimateChatHistoryLoading, estimateChatHistoryLoadingRef,
    estimateChatInput, estimateChatLoading,
    estimateChatMessages, estimateChatRequestRef, estimateIssueFocusKey, estimateVersionRequestRef,
    estimateVersions, executionPriceFillPercent, fromEstimateForm, generateForm,
    generatePricelistForm, generating, generatingPricelist, importValidating,
    importValidationWarnings, newEstimate, newEstimateItem,
    newEstimateSection, selectedVersionsToCompare, setCreatingFromEstimate,
    setEstimateChatHistoryLoading,
    setEstimateChatInput,
    setEstimateChatLoading, setEstimateChatMessages, setEstimateIssueFocusKey,
    setEstimateVersions, setExecutionPriceFillPercent, setFromEstimateForm, setGenerateForm,
    setGeneratePricelistForm, setGenerating, setGeneratingPricelist, setImportValidating,
    setImportValidationWarnings, setNewEstimate, setNewEstimateItem,
    setNewEstimateSection, setSelectedVersionsToCompare, setShowEstimateChat,
    setShowEstimateIssuesOnly, setShowEstimateWorkSummary, setShowFromEstimate,
    setShowGenerateEstimate, setShowGeneratePricelist, setShowVersionHistory,
    setShowWorkAssignment, showEstimateChat, showEstimateIssuesOnly,
    showEstimateWorkSummary, showFromEstimate, showGenerateEstimate, showGeneratePricelist,
    showVersionHistory, showWorkAssignment,
  };
}
