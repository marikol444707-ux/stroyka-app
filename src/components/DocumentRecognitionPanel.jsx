import React from 'react';
import { Check, FileText, Upload, Wand2 } from 'lucide-react';
import { API as DEFAULT_API } from '../api';

const FIELDS = [
  ['docType', 'Тип документа'],
  ['number', 'Номер'],
  ['docDate', 'Дата'],
  ['counterpartyName', 'Контрагент'],
  ['legalForm', 'Тип'],
  ['inn', 'ИНН'],
  ['kpp', 'КПП'],
  ['ogrn', 'ОГРН'],
  ['bank', 'Банк'],
  ['bik', 'БИК'],
  ['bankAccount', 'Расчетный счет'],
  ['corrAccount', 'Корр. счет'],
  ['signerName', 'Подписант'],
  ['signerBasis', 'Основание'],
  ['amount', 'Сумма'],
  ['workType', 'Вид работ'],
  ['contractSubject', 'Предмет договора'],
];

const cleanPatch = (patch) => Object.fromEntries(
  Object.entries(patch || {}).filter(([, value]) => value !== undefined && value !== null && value !== '')
);

export default function DocumentRecognitionPanel({
  API = DEFAULT_API,
  C,
  card,
  inp,
  btnG,
  btnO,
  btnB,
  uploadPhoto,
  fileSrc,
  projectName = '',
  context = 'document-recognition',
  entityType = '',
  currentFields = {},
  onApplyLead,
  onApplyProjectDocument,
  onCreateCrmDocument,
}) {
  const [fileUrl, setFileUrl] = React.useState('');
  const [text, setText] = React.useState('');
  const [loading, setLoading] = React.useState(false);
  const [result, setResult] = React.useState(null);

  const extracted = result?.extracted || {};
  const visibleFields = FIELDS.filter(([key]) => extracted[key]);
  const hasActions = result && (onApplyLead || onApplyProjectDocument || onCreateCrmDocument);

  const uploadDocument = async (file) => {
    if (!file || !uploadPhoto) return;
    setLoading(true);
    const url = await uploadPhoto(file, {
      projectName: projectName || currentFields?.name || 'Документы',
      context,
    });
    setLoading(false);
    if (url) setFileUrl(url);
  };

  const analyze = async () => {
    if (!fileUrl && !text.trim()) {
      alert('Загрузите файл или вставьте текст документа');
      return;
    }
    setLoading(true);
    const res = await fetch(API + '/document-recognition/analyze', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        context,
        entityType,
        projectName,
        fileUrl,
        text,
        currentFields,
      }),
    }).catch(() => null);
    const data = await res?.json().catch(() => null);
    setLoading(false);
    if (!res?.ok || !data?.ok) {
      alert(data?.detail || data?.error || 'Не удалось распознать документ');
      return;
    }
    setResult(data);
  };

  const applyLead = () => {
    const patch = cleanPatch(result?.suggestedLeadPatch);
    if (Object.keys(patch).length && onApplyLead) onApplyLead(patch);
  };

  const applyProjectDocument = () => {
    const patch = cleanPatch(result?.suggestedProjectDocument);
    if (Object.keys(patch).length && onApplyProjectDocument) onApplyProjectDocument(patch);
  };

  const createCrmDocument = () => {
    const patch = cleanPatch(result?.suggestedCrmDocument);
    if (Object.keys(patch).length && onCreateCrmDocument) onCreateCrmDocument(patch);
  };

  return (
    <div style={{...card, padding: '14px', marginTop: '12px', border: '1.5px solid ' + C.accentBorder, backgroundColor: C.card}}>
      <div style={{display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'flex-start', flexWrap: 'wrap'}}>
        <div>
          <b style={{color: C.text, fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px'}}>
            <Wand2 size={15}/>Распознавание документа
          </b>
          <p style={{color: C.textMuted, fontSize: '12px', margin: '4px 0 0', lineHeight: 1.45}}>
            Реквизиты, паспортные данные, договоры и приложения попадут в черновик полей перед сохранением.
          </p>
        </div>
        <span style={{fontSize: '11px', color: C.textMuted}}>
          {result?.source === 'ai' ? 'ИИ' : result?.source === 'heuristic' ? 'Правила' : 'Черновик'}
        </span>
      </div>

      <div style={{display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '10px', alignItems: 'center'}}>
        <label style={{...btnG, cursor: 'pointer', margin: 0}}>
          <Upload size={14}/>{fileUrl ? 'Файл загружен' : 'Загрузить документ'}
          <input type="file" accept=".pdf,.doc,.docx,.txt,.rtf,image/*" style={{display: 'none'}} onChange={e => uploadDocument(e.target.files?.[0])}/>
        </label>
        {fileUrl && fileSrc && (
          <a href={fileSrc(fileUrl)} target="_blank" rel="noreferrer" style={{...btnB, textDecoration: 'none'}}>
            <FileText size={14}/>Открыть
          </a>
        )}
        <button onClick={analyze} disabled={loading} style={btnO}>
          <Wand2 size={14}/>{loading ? 'Распознаем...' : 'Распознать'}
        </button>
      </div>

      <textarea
        placeholder="Если файл сканированный, вставьте сюда распознанный текст или текст договора/реквизитов"
        value={text}
        onChange={e => setText(e.target.value)}
        style={{...inp, marginTop: '10px', minHeight: '72px', resize: 'vertical'}}
      />

      {result?.warnings?.length > 0 && (
        <div style={{marginTop: '8px', padding: '8px 10px', borderRadius: '8px', backgroundColor: C.warningLight, border: '1px solid ' + C.warningBorder}}>
          {result.warnings.map((warning, idx) => (
            <p key={idx} style={{margin: idx ? '4px 0 0' : 0, color: C.warning, fontSize: '11px', lineHeight: 1.35}}>{warning}</p>
          ))}
        </div>
      )}

      {visibleFields.length > 0 && (
        <div style={{marginTop: '10px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: '8px'}}>
          {visibleFields.map(([key, label]) => (
            <div key={key} style={{padding: '8px', border: '1px solid ' + C.border, borderRadius: '8px', minWidth: 0}}>
              <span style={{fontSize: '10px', color: C.textMuted, display: 'block', marginBottom: '3px'}}>{label}</span>
              <b style={{fontSize: '12px', color: C.text, overflowWrap: 'anywhere', whiteSpace: 'pre-wrap'}}>{String(extracted[key])}</b>
            </div>
          ))}
        </div>
      )}

      {hasActions && (
        <div style={{display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '10px'}}>
          {onApplyLead && <button onClick={applyLead} style={btnG}><Check size={14}/>Заполнить карточку</button>}
          {onCreateCrmDocument && <button onClick={createCrmDocument} style={btnG}><FileText size={14}/>Добавить в документы CRM</button>}
          {onApplyProjectDocument && <button onClick={applyProjectDocument} style={btnG}><Check size={14}/>Заполнить документ объекта</button>}
        </div>
      )}
    </div>
  );
}
