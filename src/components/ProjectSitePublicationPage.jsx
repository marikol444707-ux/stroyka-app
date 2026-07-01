import React, { useEffect, useMemo, useState } from 'react';
import { Check, Globe2, Image, Radio, Save } from 'lucide-react';

const PUBLIC_CATEGORIES = [
  { value: 'house', label: 'Дом' },
  { value: 'repair', label: 'Ремонт' },
  { value: 'commerce', label: 'Коммерция' },
  { value: 'reconstruction', label: 'Реконструкция' },
];

const AI_STATUSES = [
  'Не обработано',
  'Нужно улучшить',
  'AI-версия готова',
  'Проверено директором',
];

export default function ProjectSitePublicationPage({
  C,
  badge,
  btnG,
  btnO,
  card,
  inp,
  isMobile,
  projects = [],
  projectSiteDraft,
  updateProjectSiteDraft,
  saveProjectSitePublication,
}) {
  const activeProjects = useMemo(
    () => (projects || []).filter(project => !project.archived),
    [projects]
  );
  const [selectedProjectId, setSelectedProjectId] = useState('');

  useEffect(() => {
    if (!activeProjects.length) {
      setSelectedProjectId('');
      return;
    }
    if (!selectedProjectId || !activeProjects.some(project => String(project.id) === String(selectedProjectId))) {
      setSelectedProjectId(String(activeProjects[0].id));
    }
  }, [activeProjects, selectedProjectId]);

  const selectedProject = activeProjects.find(project => String(project.id) === String(selectedProjectId)) || activeProjects[0];
  const draft = selectedProject && typeof projectSiteDraft === 'function' ? projectSiteDraft(selectedProject) : null;
  const visibleCount = activeProjects.filter(project => project.publicShowOnSite).length;
  const liveCount = activeProjects.filter(project => project.publicIsLive).length;
  const needsPhotoCount = activeProjects.filter(project => !project.publicMainImageUrl && project.publicShowOnSite).length;
  const field = {...inp, marginBottom: 0};
  const textarea = {...field, minHeight: '82px', resize: 'vertical', fontFamily: 'inherit'};
  const patch = patchValue => selectedProject && updateProjectSiteDraft(selectedProject.id, patchValue);

  if (!activeProjects.length) {
    return (
      <div style={{...card, padding: '34px', textAlign: 'center', color: C.textMuted}}>
        <Globe2 size={44} style={{opacity: 0.35, marginBottom: '12px'}} />
        <b style={{display: 'block', color: C.text, marginBottom: '6px'}}>Нет активных объектов</b>
        <span>Создайте объект, потом здесь появятся настройки публикации на сайт.</span>
      </div>
    );
  }

  return (
    <div>
      <div style={{display: 'flex', justifyContent: 'space-between', gap: '14px', alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: '16px'}}>
        <div>
          <h2 style={{margin: 0, color: C.text, fontSize: isMobile ? '22px' : '28px', lineHeight: 1.15}}>🌐 Действия по сайту</h2>
          <p style={{margin: '8px 0 0', color: C.textSec, maxWidth: '880px', lineHeight: 1.45}}>
            Здесь ведём только публичную карточку объекта: что можно показывать на сайте, какие фото подготовлены и какой статус у публикации.
          </p>
        </div>
        <div style={{display: 'flex', gap: '8px', flexWrap: 'wrap'}}>
          <span style={badge(C.success, C.successLight, C.successBorder)}><Globe2 size={14}/>Показывается: {visibleCount}</span>
          <span style={badge(C.info, C.infoLight, C.infoBorder)}><Radio size={14}/>Живые: {liveCount}</span>
          {needsPhotoCount > 0 && <span style={badge(C.warning, C.warningLight, C.warningBorder)}><Image size={14}/>Без главного фото: {needsPhotoCount}</span>}
        </div>
      </div>

      <div style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '320px minmax(0, 1fr)', gap: '14px', alignItems: 'start'}}>
        <div style={{...card, padding: '14px'}}>
          <b style={{color: C.text, display: 'block', marginBottom: '10px'}}>Объекты</b>
          <select value={selectedProjectId} onChange={event => setSelectedProjectId(event.target.value)} style={{...field, marginBottom: '12px'}}>
            {activeProjects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
          <div style={{display: 'flex', flexDirection: 'column', gap: '8px'}}>
            {activeProjects.map(project => {
              const isActive = String(project.id) === String(selectedProject?.id);
              return (
                <button
                  key={project.id}
                  type="button"
                  onClick={() => setSelectedProjectId(String(project.id))}
                  style={{
                    ...btnG,
                    width: '100%',
                    justifyContent: 'space-between',
                    textAlign: 'left',
                    backgroundColor: isActive ? C.accentLight : C.bg,
                    borderColor: isActive ? C.accentBorder : C.border,
                    color: C.text,
                  }}
                >
                  <span style={{minWidth: 0}}>
                    <b style={{display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>{project.name}</b>
                    <span style={{display: 'block', fontSize: '11px', color: C.textSec, marginTop: '2px'}}>
                      {project.publicShowOnSite ? 'Показывается' : 'Скрыт'} · {project.publicAiStatus || 'Не обработано'}
                    </span>
                  </span>
                  <span style={{color: project.publicIsLive ? C.info : C.textMuted, fontSize: '16px'}}>●</span>
                </button>
              );
            })}
          </div>
        </div>

        {selectedProject && draft && (
          <div style={{
            ...card,
            padding: isMobile ? '14px' : '18px',
            backgroundColor: draft.publicShowOnSite ? C.successLight : C.bgWhite,
            border: '1.5px solid ' + (draft.publicShowOnSite ? C.successBorder : C.border),
          }}>
            <div style={{display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: '14px'}}>
              <div>
                <b style={{color: C.text, fontSize: '16px'}}>{selectedProject.name}</b>
                <p style={{margin: '5px 0 0', color: C.textSec, fontSize: '12px', lineHeight: 1.45}}>
                  Наружу уйдут только эти публичные поля и выбранные фото. Внутренние деньги, документы и клиентские данные не публикуются.
                </p>
              </div>
              <div style={{display: 'flex', gap: '8px', flexWrap: 'wrap'}}>
                <label style={{...badge(draft.publicShowOnSite ? C.success : C.textSec, draft.publicShowOnSite ? C.successLight : C.bg, C.border), cursor: 'pointer'}}>
                  <input type="checkbox" checked={!!draft.publicShowOnSite} onChange={event => patch({publicShowOnSite: event.target.checked})} style={{margin: 0}}/> Показывать
                </label>
                <label style={{...badge(draft.publicIsLive ? C.info : C.textSec, draft.publicIsLive ? C.infoLight : C.bg, C.border), cursor: 'pointer'}}>
                  <input type="checkbox" checked={!!draft.publicIsLive} onChange={event => patch({publicIsLive: event.target.checked})} style={{margin: 0}}/> Живой объект
                </label>
              </div>
            </div>

            <div style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'repeat(4, minmax(0, 1fr))', gap: '10px'}}>
              <input placeholder="Публичное название" value={draft.publicTitle || ''} onChange={event => patch({publicTitle: event.target.value})} style={field}/>
              <select value={draft.publicCategory || 'house'} onChange={event => patch({publicCategory: event.target.value})} style={field}>
                {PUBLIC_CATEGORIES.map(category => <option key={category.value} value={category.value}>{category.label}</option>)}
              </select>
              <input placeholder="Город / район" value={draft.publicLocation || ''} onChange={event => patch({publicLocation: event.target.value})} style={field}/>
              <input placeholder="Площадь, например 142 м2" value={draft.publicArea || ''} onChange={event => patch({publicArea: event.target.value})} style={field}/>
              <input placeholder="Год" value={draft.publicYear || ''} onChange={event => patch({publicYear: event.target.value})} style={field}/>
              <input placeholder="Этап для сайта" value={draft.publicStage || ''} onChange={event => patch({publicStage: event.target.value})} style={field}/>
              <input placeholder="Прогресс %" type="number" min="0" max="100" value={draft.publicProgress || 0} onChange={event => patch({publicProgress: event.target.value})} style={field}/>
              <input placeholder="Срок, например 5 месяцев" value={draft.publicTerm || ''} onChange={event => patch({publicTerm: event.target.value})} style={field}/>
              <input placeholder="Бюджет для сайта, если можно показывать" value={draft.publicPriceLabel || ''} onChange={event => patch({publicPriceLabel: event.target.value})} style={field}/>
              <input placeholder="Теги через запятую" value={draft.publicTagsText || ''} onChange={event => patch({publicTagsText: event.target.value})} style={field}/>
              <select value={draft.publicAiStatus || 'Не обработано'} onChange={event => patch({publicAiStatus: event.target.value})} style={field}>
                {AI_STATUSES.map(status => <option key={status}>{status}</option>)}
              </select>
              <input placeholder="Главное фото URL" value={draft.publicMainImageUrl || ''} onChange={event => patch({publicMainImageUrl: event.target.value})} style={field}/>
            </div>

            <div style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: '10px', marginTop: '10px'}}>
              <textarea placeholder="Короткое описание для сайта" value={draft.publicSummary || ''} onChange={event => patch({publicSummary: event.target.value})} style={textarea}/>
              <textarea placeholder="Что сделали / результат" value={draft.publicResult || ''} onChange={event => patch({publicResult: event.target.value})} style={textarea}/>
              <textarea placeholder="Что есть в цифровом паспорте" value={draft.publicPassport || ''} onChange={event => patch({publicPassport: event.target.value})} style={textarea}/>
              <textarea placeholder="Заметки по AI-фото: что улучшить, что скрыть, какие фото выбрать" value={draft.publicAiNotes || ''} onChange={event => patch({publicAiNotes: event.target.value})} style={textarea}/>
              <textarea placeholder="Оригинальные фото, по одной ссылке в строке" value={draft.publicOriginalImagesText || ''} onChange={event => patch({publicOriginalImagesText: event.target.value})} style={{...textarea, minHeight: '104px'}}/>
              <textarea placeholder="AI-фото для сайта, по одной ссылке в строке" value={draft.publicEnhancedImagesText || ''} onChange={event => patch({publicEnhancedImagesText: event.target.value})} style={{...textarea, minHeight: '104px'}}/>
            </div>

            <div style={{display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '14px', alignItems: 'center'}}>
              <button type="button" onClick={() => saveProjectSitePublication(selectedProject)} style={btnO}><Save size={14}/>Сохранить публикацию</button>
              <span style={{fontSize: '12px', color: C.textSec}}><Check size={13} style={{verticalAlign: '-2px'}}/> AI-фото пока сохраняем как подготовленную версию. Реальную обработку подключим отдельным шагом.</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
