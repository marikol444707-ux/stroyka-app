import { act, renderHook } from '@testing-library/react';
import useSupplierRequestSelection from './useSupplierRequestSelection';
afterEach(()=>window.history.replaceState({},'', '/'));
it('restores a deep link, preserves unrelated params and responds to browser navigation',()=>{
  window.history.replaceState({},'', '/app?from=max&supplyRequestId=31');
  const {result,unmount}=renderHook(()=>useSupplierRequestSelection());
  expect(result.current[0]).toBe('31');
  act(()=>result.current[1](42));
  expect(window.location.search).toBe('?from=max&supplyRequestId=42');
  window.history.replaceState({},'', '/app?from=max&supplyRequestId=31');
  act(()=>window.dispatchEvent(new PopStateEvent('popstate')));
  expect(result.current[0]).toBe('31');
  unmount();
  const restored=renderHook(()=>useSupplierRequestSelection());
  expect(restored.result.current[0]).toBe('31');
  act(()=>restored.result.current[1](''));
  expect(window.location.search).toBe('?from=max');
});
it('ignores malformed ids',()=>{
  window.history.replaceState({},'', '/app?supplyRequestId=bad');
  expect(renderHook(()=>useSupplierRequestSelection()).result.current[0]).toBe('');
});
