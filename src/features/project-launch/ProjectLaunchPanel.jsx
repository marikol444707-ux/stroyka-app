import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  FileCheck2,
  FileText,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from 'lucide-react';
import {
  createProjectLaunchDraft,
  fetchProjectLaunchDrafts,
  fetchProjectLaunchReadiness,
  rejectProjectLaunchDraft,
} from './projectLaunchApi';

const statusLabels = {
  draft: 'Черновик',
  reviewed: 'Проверен',
  applied: 'Применен',
  rejected: 'Отклонен',
};

const text = value => String(value || '').trim();
const money = value => {
  const amount = Number(value || 0);
  return amount ? Math.round(amount).toLocaleString('ru-RU') + ' ₽' : '-';
};

function ProjectLaunchPanel({
  API,
  C,
  card,
  btnB,
  btnG,
  btnO,
  btnR,
  project,
  projectDocuments = [],
  estimates = [],
  isMobile = false,
  onOpenDocuments,
  onOpenEstimate,
}) {
  const [readiness, setReadiness] = useState(null);
  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [selectedDocumentId, setSelectedDocumentId] = useState('');

  const projectName = project?.name || project?.projectName || '';
  const contractDocs = useMemo(() => {
    const docs = (projectDocuments || []).filter(doc => {
      const type = text(doc.docType || doc.doc_type).toLowerCase();
      return type.includes('договор') || type.includes('контракт') || type.includes('соглаш');
    });
    return docs.length ? docs : projectDocuments;
  }, [projectDocuments]);

  const selectedDocument = useMemo(() => {
    const selected = contractDocs.find(doc => String(doc.id) === String(selectedDocumentId));
    return selected || contractDocs[0] || null;
  }, [contractDocs, selectedDocumentId]);

  const load = useCallback(async () => {
    if (!projectName) return;
    setLoading(true);
    setError('');
    try {
      const [nextReadiness, nextDrafts] = await Promise.all([
        fetchProjectLaunchReadiness(API, projectName),
        fetchProjectLaunchDrafts(API, projectName),
      ]);
      setReadiness(nextReadiness);
      setDrafts(nextDrafts);
      if (!selectedDocumentId && contractDocs[0]?.id) setSelectedDocumentId(String(contractDocs[0].id));
    } catch (e) {
      setError(e.message || 'Не удалось загрузить запуск объекта.');
    } finally {
      setLoading(false);
    }
  }, [API, contractDocs, projectName, selectedDocumentId]);

  useEffect(() => {
    load();
  }, [load]);

  const createDraft = async () => {
    setCreating(true);
    setError('');
    try {
      const doc = selectedDocument;
      const draft = await createProjectLaunchDraft(API, {
        projectName,
        sourceDocumentId: doc?.id || null,
        sourceFileUrl: doc?.scanUrl || doc?.scan_url || '',
        sourceFileName: doc ? [doc.docType || doc.doc_type || 'Документ', doc.number ? '№ ' + doc.number : ''].filter(Boolean).join(' ') : '',
        sourceFileType: doc?.docType || doc?.doc_type || '',
        extracted: {
          documentTitle: doc?.docType || doc?.doc_type || '',
          number: doc?.number || '',
          docDate: doc?.docDate || doc?.doc_date || '',
          counterpartyName: doc?.counterparty || '',
          amount: doc?.amount || '',
          notes: doc?.notes || '',
        },
        projectPatch: {
          name: projectName,
          client: project?.client || '',
          budget: project?.budget || 0,
          deadline: project?.deadline || '',
        },
        counterparty: {
          name: doc?.counterparty || project?.client || '',
          type: 'customer',
        },
        contractTerms: {
          contractNumber: doc?.number || '',
          contractDate: doc?.docDate || doc?.doc_date || '',
          contractSum: doc?.amount || project?.budget || 0,
          counterpartyName: doc?.counterparty || project?.client || '',
        },
        estimateDraft: {
          estimatesCount: estimates.length,
          status: 'not_created',
        },
        findings: [],
        tasks: [],
        warnings: [
          {type: 'manual_draft', message: 'Черновик создан из текущих данных объекта и документа. Рабочие сущности не изменены.'},
        ],
        confidence: doc ? 0.55 : 0.25,
      });
      setDrafts(prev => draft ? [draft, ...prev.filter(item => item.id !== draft.id)] : prev);
      await load();
    } catch (e) {
      setError(e.message || 'Не удалось создать черновик запуска.');
    } finally {
      setCreating(false);
    }
  };

  const rejectDraft = async draft => {
    const reason = window.prompt('Причина отклонения черновика запуска', 'Неактуальный черновик');
    if (reason === null) return;
    setError('');
    try {
      const updated = await rejectProjectLaunchDraft(API, draft.id, reason);
      setDrafts(prev => prev.map(item => item.id === draft.id ? updated : item));
      await load();
    } catch (e) {
      setError(e.message || 'Не удалось отклонить черновик запуска.');
    }
  };

  const checks = readiness?.checks || [];
  const readyCount = checks.filter(item => item.ok).length;
  const readyPercent = checks.length ? Math.round(readyCount / checks.length * 100) : 0;
  const activeDrafts = drafts.filter(draft => draft.status !== 'rejected');

  const pill = (ok) => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: '5px',
    borderRadius: '999px',
    padding: '5px 9px',
    fontSize: '11px',
    fontWeight: 800,
    color: ok ? C.success : C.warning,
    backgroundColor: ok ? C.successLight : C.warningLight,
    border: '1px solid ' + (ok ? C.successBorder : C.warningBorder),
  });

  return (
    <div style={{display:'grid',gap:'14px'}}>
      <div style={{...card,padding:isMobile?'14px':'18px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.accentBorder}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'12px',flexWrap:'wrap',marginBottom:'14px'}}>
          <div>
            <p style={{margin:'0 0 4px',color:C.textSec,fontSize:'12px',fontWeight:800,letterSpacing:0,textTransform:'uppercase'}}>AI-досье объекта</p>
            <h3 style={{margin:0,color:C.text,fontSize:isMobile?'18px':'22px'}}>Запуск объекта</h3>
            <p style={{margin:'6px 0 0',color:C.textSec,fontSize:'13px',lineHeight:1.45}}>
              Проверяет, хватает ли данных для старта: заказчик, бюджет, срок, договор, смета и черновики распознавания. Рабочие данные не меняются автоматически.
            </p>
          </div>
          <button type="button" onClick={load} disabled={loading} style={{...btnG,padding:'8px 12px',fontSize:'12px',opacity:loading?0.65:1}}>
            <RefreshCw size={14}/>{loading ? 'Обновляю' : 'Обновить'}
          </button>
        </div>

        {error && (
          <div style={{padding:'10px 12px',borderRadius:'10px',backgroundColor:C.dangerLight,border:'1.5px solid '+C.dangerBorder,color:C.danger,fontSize:'13px',marginBottom:'12px'}}>
            {error}
          </div>
        )}

        <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'220px 1fr',gap:'12px',alignItems:'stretch'}}>
          <div style={{padding:'14px',borderRadius:'12px',backgroundColor:C.bg,border:'1.5px solid '+C.border}}>
            <div style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'8px'}}>
              <ClipboardCheck size={18} color={readiness?.ready ? C.success : C.warning}/>
              <b style={{color:C.text,fontSize:'14px'}}>Готовность</b>
            </div>
            <div style={{fontSize:'34px',fontWeight:900,color:readiness?.ready ? C.success : C.warning,lineHeight:1}}>
              {readyPercent}%
            </div>
            <p style={{margin:'6px 0 0',color:C.textSec,fontSize:'12px'}}>{readyCount} из {checks.length || 0} блоков заполнено</p>
          </div>

          <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'repeat(3,minmax(0,1fr))',gap:'8px'}}>
            {checks.map(check => (
              <div key={check.key} style={{padding:'10px',borderRadius:'10px',backgroundColor:check.ok?C.successLight:C.warningLight,border:'1px solid '+(check.ok?C.successBorder:C.warningBorder)}}>
                <span style={pill(check.ok)}>
                  {check.ok ? <CheckCircle2 size={13}/> : <AlertTriangle size={13}/>}
                  {check.ok ? 'Есть' : 'Нужно'}
                </span>
                <b style={{display:'block',marginTop:'7px',color:C.text,fontSize:'13px'}}>{check.label}</b>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'1fr 1fr 1fr',gap:'10px'}}>
        <div style={{...card,padding:'14px',backgroundColor:C.bg}}>
          <FileText size={18} color={C.info}/>
          <p style={{margin:'8px 0 3px',color:C.textSec,fontSize:'11px'}}>Документы объекта</p>
          <b style={{color:C.text,fontSize:'18px'}}>{readiness?.documentsCount ?? projectDocuments.length}</b>
          <button type="button" onClick={onOpenDocuments} style={{...btnB,width:'100%',justifyContent:'center',marginTop:'10px',fontSize:'12px'}}>Открыть реестр</button>
        </div>
        <div style={{...card,padding:'14px',backgroundColor:C.bg}}>
          <FileCheck2 size={18} color={C.success}/>
          <p style={{margin:'8px 0 3px',color:C.textSec,fontSize:'11px'}}>Сметы</p>
          <b style={{color:C.text,fontSize:'18px'}}>{readiness?.estimatesCount ?? estimates.length}</b>
          <button type="button" onClick={onOpenEstimate} style={{...btnB,width:'100%',justifyContent:'center',marginTop:'10px',fontSize:'12px'}}>Открыть смету</button>
        </div>
        <div style={{...card,padding:'14px',backgroundColor:C.bg}}>
          <ShieldCheck size={18} color={activeDrafts.length ? C.accent : C.textMuted}/>
          <p style={{margin:'8px 0 3px',color:C.textSec,fontSize:'11px'}}>AI-черновики</p>
          <b style={{color:C.text,fontSize:'18px'}}>{activeDrafts.length}</b>
          <p style={{margin:'8px 0 0',color:C.textMuted,fontSize:'11px',lineHeight:1.35}}>Черновики не меняют рабочие данные до подтверждения.</p>
        </div>
      </div>

      <div style={{...card,padding:isMobile?'14px':'16px',backgroundColor:C.bgWhite}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'12px',flexWrap:'wrap',marginBottom:'12px'}}>
          <div>
            <b style={{color:C.text,fontSize:'15px'}}>Создать черновик запуска</b>
            <p style={{margin:'4px 0 0',color:C.textSec,fontSize:'12px'}}>Берем текущий объект и выбранный договор/документ. Применения в объект пока нет.</p>
          </div>
          <button type="button" onClick={createDraft} disabled={creating} style={{...btnO,padding:'9px 13px',fontSize:'12px',opacity:creating?0.65:1}}>
            <ClipboardCheck size={14}/>{creating ? 'Создаю' : 'Создать черновик'}
          </button>
        </div>

        <select
          value={selectedDocumentId}
          onChange={event => setSelectedDocumentId(event.target.value)}
          style={{width:'100%',padding:'10px 12px',borderRadius:'10px',border:'1.5px solid '+C.border,backgroundColor:C.bg,color:C.text,fontSize:'13px'}}
        >
          {contractDocs.length === 0 && <option value="">Документов пока нет</option>}
          {contractDocs.map(doc => (
            <option key={doc.id} value={doc.id}>
              {(doc.docType || doc.doc_type || 'Документ') + (doc.number ? ' № ' + doc.number : '') + (doc.counterparty ? ' · ' + doc.counterparty : '') + (doc.amount ? ' · ' + money(doc.amount) : '')}
            </option>
          ))}
        </select>
      </div>

      <div style={{...card,padding:isMobile?'14px':'16px',backgroundColor:C.bgWhite}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',marginBottom:'12px'}}>
          <b style={{color:C.text,fontSize:'15px'}}>Черновики запуска</b>
          <span style={{color:C.textSec,fontSize:'12px'}}>{drafts.length} шт.</span>
        </div>
        {drafts.length === 0 ? (
          <div style={{padding:'18px',borderRadius:'12px',backgroundColor:C.bg,border:'1.5px dashed '+C.border,textAlign:'center',color:C.textSec,fontSize:'13px'}}>
            Черновиков пока нет. Создайте первый из договора или другого документа объекта.
          </div>
        ) : (
          <div style={{display:'grid',gap:'8px'}}>
            {drafts.map(draft => {
              const rejected = draft.status === 'rejected';
              const statusOk = draft.status === 'reviewed' || draft.status === 'applied';
              return (
                <div key={draft.id} style={{padding:'12px',borderRadius:'12px',backgroundColor:rejected?C.dangerLight:C.bg,border:'1.5px solid '+(rejected?C.dangerBorder:C.border)}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                    <div style={{flex:1,minWidth:'220px'}}>
                      <span style={pill(statusOk && !rejected)}>
                        {rejected ? <XCircle size={13}/> : <ShieldCheck size={13}/>}
                        {statusLabels[draft.status] || draft.status}
                      </span>
                      <b style={{display:'block',marginTop:'7px',color:C.text,fontSize:'13px'}}>
                        {draft.sourceFileName || draft.extracted?.documentTitle || 'Черновик запуска #' + draft.id}
                      </b>
                      <p style={{margin:'4px 0 0',color:C.textSec,fontSize:'12px',lineHeight:1.4}}>
                        {(draft.counterparty?.name || draft.extracted?.counterpartyName || project?.client || 'Контрагент не выделен') + ' · ' +
                        money(draft.contractTerms?.contractSum || draft.extracted?.amount || project?.budget)}
                      </p>
                      {Array.isArray(draft.warnings) && draft.warnings.length > 0 && (
                        <p style={{margin:'6px 0 0',color:C.warning,fontSize:'11px',lineHeight:1.4}}>
                          {draft.warnings[0]?.message || 'Есть предупреждения'}
                        </p>
                      )}
                    </div>
                    {!rejected && (
                      <button type="button" onClick={() => rejectDraft(draft)} style={{...btnR,padding:'6px 10px',fontSize:'11px'}}>
                        <XCircle size={13}/>Отклонить
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default ProjectLaunchPanel;
