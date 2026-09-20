import { useCallback, useEffect, useRef } from 'react';
import { customerProject } from './projectSelection';

const resources = {
  documents: ['/project-documents', 'setProjectDocuments'],
  letters: ['/project-letters', 'setProjectLetters'],
  warranty: ['/warranty-defects', 'setWarrantyDefects'],
};

export const customerRecordsScope = (user, companyId, projectId = user?.project_id ?? user?.projectId ?? '') => [
  user?.id, companyId, projectId, user?.project_name ?? user?.projectName ?? '',
].join(':');

export default function useCustomerRecordsLoader(ctx) {
  const companyId = Number(ctx.companyContext?.selectedCompanyId);
  const project = customerProject(ctx.customerProjects, { ...ctx.user, company_id: companyId });
  const projectId = Number(project?.id);
  const enabled = ctx.user?.role === 'заказчик' && Number.isSafeInteger(companyId) && companyId > 0
    && ctx.companyContext?.mode === 'company' && !ctx.companyContext?.loading
    && Number.isSafeInteger(projectId) && projectId > 0;
  const scope = enabled ? customerRecordsScope(ctx.user, companyId, projectId) : '';
  const latest = useRef(ctx);
  latest.current = ctx;
  const lifecycle = useRef({ scope, generation: 0, pending: new Set() });
  if (lifecycle.current.scope !== scope) lifecycle.current = { scope, generation: 0, pending: new Set() };

  const reload = useCallback(async () => {
    const owner = lifecycle.current;
    if (!scope || owner.scope !== scope) throw new Error('Выберите компанию для загрузки документов.');
    const generation = ++owner.generation;
    const current = () => lifecycle.current === owner && owner.generation === generation && !owner.closed;
    const inputs = latest.current;
    const writeState = (kind, status, error = '') => {
      if (current()) inputs.setCustomerRecordsLoadState?.(previous => ({ ...previous, [kind]: { scope, status, error } }));
    };
    const results = await Promise.all(Object.entries(resources).map(async ([kind, [path, setter]]) => {
      if (current()) inputs[setter]?.([]);
      writeState(kind, 'loading');
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 20000);
      const pending = { controller, timer };
      owner.pending.add(pending);
      try {
        const response = await fetch(inputs.API + path, { signal: controller.signal, credentials: 'include',
          headers: { 'X-Company-Id': String(companyId), 'X-Company-Mode': 'company' } });
        const rows = await response.json();
        if (!response.ok || !Array.isArray(rows)) throw new Error('Не удалось загрузить раздел. Повторите загрузку.');
        if (rows.some(row => !row || Number(row.companyId) !== companyId || Number(row.projectId) !== projectId
            || (kind === 'warranty' ? Number(row.createdByUserId) !== Number(inputs.user.id) : row.side !== 'customer'))) {
          throw new Error('Сервер не подтвердил принадлежность данных. Повторите загрузку.');
        }
        if (current()) {
          inputs[setter]?.(rows);
          writeState(kind, 'ready');
        }
        return current();
      } catch (error) {
        writeState(kind, 'error', error.name === 'AbortError' ? 'Сервер не ответил вовремя. Повторите загрузку.' : error.message);
        return false;
      } finally {
        clearTimeout(timer);
        owner.pending.delete(pending);
      }
    }));
    if (!results.every(Boolean)) throw new Error('Обновить документы и обращения не удалось. Проверьте данные перед повторной отправкой.');
  }, [scope, companyId, projectId]);

  useEffect(() => {
    const owner = lifecycle.current;
    owner.closed = false;
    if (scope) reload().catch(() => {});
    else if (latest.current.user?.role === 'заказчик') {
      latest.current.setCustomerRecordsLoadState?.({});
      for (const [, setter] of Object.values(resources)) latest.current[setter]?.([]);
    }
    return () => {
      owner.closed = true;
      for (const pending of owner.pending) { clearTimeout(pending.timer); pending.controller.abort(); }
      owner.pending.clear();
    };
  }, [scope, reload]);
  return reload;
}
