import React from 'react';

const FEATURE_FLAG = 'REACT_APP_SUPPLIER_MATERIAL_CAPABILITY_RUNTIME_ENABLED';
const SHA256 = /^[0-9a-f]{64}$/;
const PROOF_KEYS = new Set([
  'publicProofVersion', 'state', 'requestId', 'requestItemIndex',
  'subjectCount', 'subjects', 'materialEligibilityProven',
  'selectionAllowed', 'sendAllowed', 'blockers',
]);
const SUBJECT_KEYS = new Set([
  'companySupplierLinkId', 'supplierId', 'confirmationSubjectSha256',
  'proofState', 'confirmationAssertionId', 'revocationAssertionId',
]);
const RECEIPT_KEYS = new Set([
  'writeVersion', 'eventKind', 'state', 'companySupplierLinkId',
  'supplierId', 'confirmationSubjectSha256', 'assertionId',
  'revokesAssertionId', 'writesAttempted', 'committed',
]);
const PROOF_STATES = new Set([
  'proof_complete', 'proof_partial', 'confirmation_required',
  'no_candidates', 'needs_review',
]);
const BLOCKERS = new Set([
  'supply_supplier_material_evidence_invalid',
  'supply_supplier_material_confirmation_required',
  'supply_supplier_material_proof_partial',
  'supply_supplier_material_dependency_invalid',
  'supply_supplier_no_active_company_links',
]);

const exactKeys = (value, keys) => value && typeof value === 'object'
  && !Array.isArray(value)
  && Object.keys(value).length === keys.size
  && Object.keys(value).every(key => keys.has(key));
const positiveInt = value => Number.isInteger(value) && value > 0;
const nonNegativeInt = value => Number.isInteger(value) && value >= 0;
const nullablePositiveInt = value => value === null || positiveInt(value);

const normalizeSubject = value => {
  if (!exactKeys(value, SUBJECT_KEYS)) return null;
  const state = value.proofState;
  if (
    !positiveInt(value.companySupplierLinkId)
    || !positiveInt(value.supplierId)
    || typeof value.confirmationSubjectSha256 !== 'string'
    || !SHA256.test(value.confirmationSubjectSha256)
    || !['missing', 'confirmed', 'revoked'].includes(state)
    || !nullablePositiveInt(value.confirmationAssertionId)
    || !nullablePositiveInt(value.revocationAssertionId)
    || (state === 'missing' && (value.confirmationAssertionId !== null || value.revocationAssertionId !== null))
    || (state === 'confirmed' && (!positiveInt(value.confirmationAssertionId) || value.revocationAssertionId !== null))
    || (state === 'revoked' && (!positiveInt(value.confirmationAssertionId) || !positiveInt(value.revocationAssertionId)))
  ) return null;
  return { ...value };
};

const normalizeProof = (value, requestId, requestItemIndex) => {
  if (
    !exactKeys(value, PROOF_KEYS)
    || value.publicProofVersion !== 1
    || !PROOF_STATES.has(value.state)
    || value.requestId !== requestId
    || value.requestItemIndex !== requestItemIndex
    || !Array.isArray(value.subjects)
    || value.subjects.length > 100
    || value.subjectCount !== value.subjects.length
    || typeof value.materialEligibilityProven !== 'boolean'
    || value.selectionAllowed !== false
    || value.sendAllowed !== false
    || !Array.isArray(value.blockers)
    || !value.blockers.every(code => typeof code === 'string' && BLOCKERS.has(code))
  ) return null;
  const subjects = value.subjects.map(normalizeSubject);
  if (subjects.some(subject => !subject)) return null;
  return { ...value, subjects };
};

const normalizeReceipt = (value, eventKind) => {
  if (
    !exactKeys(value, RECEIPT_KEYS)
    || value.writeVersion !== 1
    || value.eventKind !== eventKind
    || !['confirmed', 'already_confirmed', 'revoked', 'already_revoked'].includes(value.state)
    || !positiveInt(value.companySupplierLinkId)
    || !positiveInt(value.supplierId)
    || typeof value.confirmationSubjectSha256 !== 'string'
    || !SHA256.test(value.confirmationSubjectSha256)
    || !positiveInt(value.assertionId)
    || !nullablePositiveInt(value.revokesAssertionId)
    || !Number.isInteger(value.writesAttempted)
    || typeof value.committed !== 'boolean'
  ) return null;
  return { ...value };
};

const safeJson = response => response.json().catch(() => ({}));

export default function MaterialCapabilityProofPanel({
  API = '',
  C = {},
  requestId,
  requestItemIndex,
  materialName,
  suppliers = [],
  companyContext = {},
}) {
  const enabled = process.env[FEATURE_FLAG] === 'true'
    && companyContext?.mode === 'company'
    && positiveInt(
      companyContext?.selectedCompanyId
      || companyContext?.selectedCompany?.companyId,
    )
    && companyContext?.selectedCompany?.role === 'директор'
    && positiveInt(requestId)
    && nonNegativeInt(requestItemIndex);
  const [proof, setProof] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState('');
  const [action, setAction] = React.useState(null);
  const [acknowledged, setAcknowledged] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const submittingRef = React.useRef(false);

  const proofUrl = `${API || ''}/supply-requests/${requestId}/items/${requestItemIndex}/material-capability-proof`;

  const loadProof = React.useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await fetch(proofUrl);
      const data = await safeJson(response);
      if (!response.ok) throw new Error('proof unavailable');
      const normalized = normalizeProof(data, requestId, requestItemIndex);
      if (!normalized) throw new Error('proof invalid');
      setProof(normalized);
    } catch (_error) {
      setProof(null);
      setError('Не удалось получить доказуемый статус. Обновите проверку.');
    } finally {
      setLoading(false);
    }
  }, [proofUrl, requestId, requestItemIndex]);

  if (!enabled) return null;

  const supplierName = supplierId => {
    const supplier = suppliers.find(item => item?.id === supplierId);
    return supplier?.name || `Поставщик #${supplierId}`;
  };

  const closeAction = () => {
    setAction(null);
    setAcknowledged(false);
  };

  const submitAction = async () => {
    if (!action || submittingRef.current) return;
    if (action.kind === 'confirm' && !acknowledged) return;
    submittingRef.current = true;
    setSubmitting(true);
    setError('');
    const subject = action.subject;
    const isConfirm = action.kind === 'confirm';
    const url = isConfirm
      ? `${API || ''}/supply-requests/${requestId}/items/${requestItemIndex}/material-capability-confirmations`
      : `${API || ''}/supplier-material-capability-confirmations/${subject.confirmationAssertionId}/revocations`;
    const body = isConfirm ? {
      companySupplierLinkId: subject.companySupplierLinkId,
      supplierId: subject.supplierId,
      confirmationSubjectSha256: subject.confirmationSubjectSha256,
    } : {};
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await safeJson(response);
      if (response.ok && !normalizeReceipt(data, isConfirm ? 'confirmed' : 'revoked')) {
        throw new Error('receipt invalid');
      }
      if (!response.ok && response.status !== 409) {
        throw new Error('write unavailable');
      }
    } catch (_error) {
      setError('Действие не подтверждено сервером. Статус перечитан.');
    } finally {
      closeAction();
      submittingRef.current = false;
      setSubmitting(false);
      await loadProof();
    }
  };

  const panelStyle = {
    marginTop: '10px', padding: '12px', borderRadius: '8px',
    border: `1.5px solid ${C.infoBorder || C.border || '#ddd'}`,
    backgroundColor: C.infoLight || C.bg || '#f7f7f7',
  };
  const buttonStyle = {
    border: `1px solid ${C.border || '#ccc'}`, borderRadius: '6px',
    padding: '5px 9px', cursor: 'pointer', background: C.bgWhite || '#fff',
    color: C.text || '#111', fontSize: '11px',
  };

  return (
    <section aria-label="Доказуемость поставщика по материалу" style={panelStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap' }}>
        <div>
          <b style={{ color: C.text || '#111', fontSize: '12px' }}>Доказуемость поставщика</b>
          <div style={{ color: C.textSec || '#555', fontSize: '11px', marginTop: '2px' }}>{materialName || 'Материал'}</div>
        </div>
        <button type="button" onClick={loadProof} disabled={loading || submitting} style={buttonStyle}>
          {loading ? 'Проверяю…' : 'Проверить доказуемость'}
        </button>
      </div>

      {error && <div role="alert" style={{ color: C.danger || '#b00020', fontSize: '11px', marginTop: '8px' }}>{error}</div>}
      {proof && proof.subjects.length === 0 && (
        <p style={{ color: C.textSec || '#555', fontSize: '11px', marginBottom: 0 }}>Подтверждаемых поставщиков пока нет.</p>
      )}
      {proof && proof.subjects.map(subject => (
        <div key={subject.confirmationSubjectSha256} style={{ marginTop: '9px', paddingTop: '9px', borderTop: `1px solid ${C.border || '#ddd'}` }}>
          <b style={{ color: C.text || '#111', fontSize: '12px' }}>{supplierName(subject.supplierId)}</b>
          {subject.proofState === 'missing' && (
            <div style={{ marginTop: '5px' }}>
              <span style={{ color: C.warning || '#8a5b00', fontSize: '11px' }}>Подтверждение отсутствует</span>{' '}
              <button type="button" onClick={() => { setAction({ kind: 'confirm', subject }); setAcknowledged(false); }} style={buttonStyle}>Подтвердить поставщика</button>
            </div>
          )}
          {subject.proofState === 'confirmed' && (
            <div style={{ marginTop: '5px' }}>
              <span style={{ color: C.success || '#267326', fontSize: '11px' }}>Подтверждение #{subject.confirmationAssertionId}</span>{' '}
              <button type="button" onClick={() => setAction({ kind: 'revoke', subject })} style={buttonStyle}>Отозвать подтверждение</button>
            </div>
          )}
          {subject.proofState === 'revoked' && (
            <div style={{ color: C.textSec || '#555', fontSize: '11px', marginTop: '5px' }}>
              <b>Подтверждение отозвано</b> · подтверждение #{subject.confirmationAssertionId} · событие отзыва #{subject.revocationAssertionId}
            </div>
          )}
        </div>
      ))}

      {action?.kind === 'confirm' && (
        <div role="dialog" aria-label="Подтверждение возможности поставщика" style={panelStyle}>
          <p style={{ fontSize: '12px', marginTop: 0 }}>Будет добавлено одно неизменяемое подтверждение. Это не выбирает поставщика и не отправляет запрос КП.</p>
          <label style={{ display: 'block', fontSize: '11px', marginBottom: '8px' }}>
            <input type="checkbox" checked={acknowledged} onChange={event => setAcknowledged(event.target.checked)} />{' '}
            Подтверждаю возможность поставки этого точного материала
          </label>
          <button type="button" onClick={submitAction} disabled={!acknowledged || submitting} style={buttonStyle}>Подтвердить доказуемость</button>{' '}
          <button type="button" onClick={closeAction} disabled={submitting} style={buttonStyle}>Отмена</button>
        </div>
      )}
      {action?.kind === 'revoke' && (
        <div role="dialog" aria-label="Отзыв подтверждения" style={panelStyle}>
          <p style={{ fontSize: '12px', marginTop: 0 }}>Будет добавлено новое неизменяемое событие отзыва; исходное подтверждение не удаляется.</p>
          <button type="button" onClick={submitAction} disabled={submitting} style={buttonStyle}>Подтвердить отзыв</button>{' '}
          <button type="button" onClick={closeAction} disabled={submitting} style={buttonStyle}>Отмена</button>
        </div>
      )}
    </section>
  );
}
