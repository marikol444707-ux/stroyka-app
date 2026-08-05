import {useEffect, useState} from 'react';


const EMPTY_STATE = {status: 'idle', data: null, error: ''};
const ENDPOINT = '/agent-jobs/director-daily-brief/latest';

const normalizePayload = (payload) => {
  if (!payload || typeof payload !== 'object') throw new Error('Некорректный ответ сервера');
  if (payload.available === false) return null;
  const brief = payload.brief;
  if (
    payload.available !== true
    || !Number.isInteger(Number(payload.jobId))
    || !brief
    || typeof brief !== 'object'
    || brief.schemaVersion !== 1
    || brief.mode !== 'deterministic_read_only'
    || !brief.summary
    || typeof brief.summary !== 'object'
    || !Array.isArray(brief.sections)
  ) {
    throw new Error('Некорректный ответ сервера');
  }
  return payload;
};

export function useLatestDirectorDailyBrief({
  API = '',
  enabled = false,
  companyContext = {},
  fallbackCompanyId = null,
} = {}) {
  const [state, setState] = useState(EMPTY_STATE);
  const contextLoading = Boolean(companyContext?.loading);
  const mode = companyContext?.mode || 'company';
  const companyId = Number(
    companyContext?.selectedCompanyId
    || companyContext?.selectedCompany?.companyId
    || companyContext?.defaultCompanyId
    || fallbackCompanyId
    || 0
  );

  useEffect(() => {
    if (!enabled) {
      setState(EMPTY_STATE);
      return undefined;
    }
    if (contextLoading) {
      setState({status: 'loading', data: null, error: ''});
      return undefined;
    }
    if (mode !== 'company' || !Number.isInteger(companyId) || companyId <= 0) {
      setState({status: 'select-company', data: null, error: ''});
      return undefined;
    }

    const controller = new AbortController();
    let active = true;
    setState({status: 'loading', data: null, error: ''});
    fetch((API || '') + ENDPOINT, {signal: controller.signal})
      .then(async (response) => {
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.detail || 'Не удалось загрузить сводку');
        return normalizePayload(payload);
      })
      .then((data) => {
        if (!active) return;
        setState(data
          ? {status: 'ready', data, error: ''}
          : {status: 'empty', data: null, error: ''});
      })
      .catch((error) => {
        if (!active || error?.name === 'AbortError') return;
        setState({
          status: 'error',
          data: null,
          error: error?.message || 'Не удалось загрузить сводку',
        });
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [API, companyId, contextLoading, enabled, mode]);

  return state;
}
