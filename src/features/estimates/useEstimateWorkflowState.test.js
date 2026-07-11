import { act, renderHook } from '@testing-library/react';

import { useEstimateWorkflowState } from './useEstimateWorkflowState';


describe('useEstimateWorkflowState', () => {
  test('clears estimate chat and version state when the company context changes', () => {
    const { result, rerender } = renderHook(
      ({ contextKey }) => useEstimateWorkflowState(contextKey),
      { initialProps: { contextKey: 'company:1' } },
    );

    act(() => {
      result.current.setShowEstimateChat(true);
      result.current.setEstimateChatMessages([{ id: 1, content: 'Компания 1' }]);
      result.current.setEstimateChatInput('Черновик');
      result.current.setEstimateChatLoading(true);
      result.current.setShowVersionHistory(true);
      result.current.setEstimateVersions([{ id: 11 }]);
      result.current.setSelectedVersionsToCompare([11]);
    });
    const previousRequestId = result.current.estimateChatRequestRef.current;

    rerender({ contextKey: 'company:2' });

    expect(result.current.showEstimateChat).toBe(false);
    expect(result.current.estimateChatMessages).toEqual([]);
    expect(result.current.estimateChatInput).toBe('');
    expect(result.current.estimateChatLoading).toBe(false);
    expect(result.current.showVersionHistory).toBe(false);
    expect(result.current.estimateVersions).toEqual([]);
    expect(result.current.selectedVersionsToCompare).toEqual([]);
    expect(result.current.estimateChatRequestRef.current).toBeGreaterThan(previousRequestId);
  });

  test('invalidates chat and version requests when the selected estimate changes', () => {
    const { result, rerender } = renderHook(
      ({ contextKey, estimateId }) => useEstimateWorkflowState(contextKey, estimateId),
      { initialProps: { contextKey: 'company:1', estimateId: 7 } },
    );
    const previousChatRequestId = result.current.estimateChatRequestRef.current;
    const previousVersionRequestId = result.current.estimateVersionRequestRef.current;

    rerender({ contextKey: 'company:1', estimateId: 8 });

    expect(result.current.estimateChatRequestRef.current).toBeGreaterThan(previousChatRequestId);
    expect(result.current.estimateVersionRequestRef.current).toBeGreaterThan(previousVersionRequestId);
    expect(result.current.showEstimateChat).toBe(false);
    expect(result.current.showVersionHistory).toBe(false);
  });
});
