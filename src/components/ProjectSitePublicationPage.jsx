import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Check, Globe2, Image, Megaphone, Plus, Radio, RefreshCw, Save, Send } from 'lucide-react';

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
  API,
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
  const [marketingChannels, setMarketingChannels] = useState([]);
  const [marketingPublications, setMarketingPublications] = useState([]);
  const [marketingLoading, setMarketingLoading] = useState(false);
  const [channelForm, setChannelForm] = useState({ chatId: '', title: '', campaignCode: '' });
  const [marketingForm, setMarketingForm] = useState({
    title: '',
    body: '',
    projectId: '',
    publicationUrl: '',
    channelId: '',
    targetSite: true,
    targetMax: true,
    utmCampaign: '',
  });

  const loadMarketing = useCallback(async () => {
    if (!API) return;
    setMarketingLoading(true);
    try {
      const [channelsBody, publicationsBody] = await Promise.all([
        fetch(API + '/messenger-channels?provider=max&channel_type=marketing').then(r => r.ok ? r.json() : {items: []}).catch(() => ({items: []})),
        fetch(API + '/marketing-publications?limit=30').then(r => r.ok ? r.json() : {items: []}).catch(() => ({items: []})),
      ]);
      const channels = Array.isArray(channelsBody.items) ? channelsBody.items : [];
      setMarketingChannels(channels);
      setMarketingPublications(Array.isArray(publicationsBody.items) ? publicationsBody.items : []);
      setMarketingForm(prev => ({
        ...prev,
        channelId: prev.channelId || (channels[0]?.id ? String(channels[0].id) : ''),
      }));
    } finally {
      setMarketingLoading(false);
    }
  }, [API]);

  useEffect(() => {
    loadMarketing();
  }, [loadMarketing]);

  const fillMarketingFromProject = () => {
    if (!selectedProject) return;
    const publicTitle = draft?.publicTitle || selectedProject.name || '';
    setMarketingForm(prev => ({
      ...prev,
      title: publicTitle,
      body: draft?.publicSummary || draft?.publicResult || '',
      projectId: String(selectedProject.id || ''),
      publicationUrl: `https://stroyka26.pro/?project=${selectedProject.id || ''}#projects`,
      utmCampaign: prev.utmCampaign || `project-${selectedProject.id || 'site'}`,
    }));
  };

  const createMarketingChannel = async () => {
    const chatId = channelForm.chatId.trim();
    if (!chatId) {
      alert('Укажите MAX chatId канала');
      return;
    }
    await fetch(API + '/messenger-channels', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        provider: 'max',
        chatId,
        title: channelForm.title || chatId,
        channelType: 'marketing',
        sourceLabel: 'MAX маркетинг',
        campaignCode: channelForm.campaignCode || '',
        enabled: true,
      }),
    });
    setChannelForm({ chatId: '', title: '', campaignCode: '' });
    await loadMarketing();
  };

  const createMarketingPublication = async () => {
    if (!marketingForm.title.trim()) {
      alert('Укажите заголовок публикации');
      return;
    }
    const channelIds = marketingForm.targetMax && marketingForm.channelId ? [Number(marketingForm.channelId)] : [];
    await fetch(API + '/marketing-publications', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        title: marketingForm.title,
        body: marketingForm.body,
        projectId: marketingForm.projectId || null,
        publicationUrl: marketingForm.publicationUrl,
        targetSite: marketingForm.targetSite,
        targetMax: marketingForm.targetMax,
        channelIds,
        utmCampaign: marketingForm.utmCampaign,
      }),
    });
    setMarketingForm(prev => ({ ...prev, title: '', body: '', publicationUrl: '' }));
    await loadMarketing();
  };

  const publishMarketingPublication = async (publication) => {
    const channelIds = publication.channelIds?.length
      ? publication.channelIds
      : marketingForm.channelId
        ? [Number(marketingForm.channelId)]
        : [];
    const res = await fetch(API + '/marketing-publications/' + publication.id + '/publish', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        targetSite: publication.targetSite,
        targetMax: publication.targetMax,
        channelIds,
      }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      alert(data.detail || 'Не удалось поставить публикацию');
      return;
    }
    await loadMarketing();
  };

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

      <div style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'minmax(0, 1.2fr) minmax(320px, 0.8fr)', gap: '14px', alignItems: 'start', marginTop: '16px'}}>
        <div style={{...card, padding: isMobile ? '14px' : '18px'}}>
          <div style={{display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', alignItems: 'center', marginBottom: '12px'}}>
            <div>
              <b style={{color: C.text, fontSize: '16px'}}><Megaphone size={16} style={{verticalAlign: '-3px'}}/> Маркетинговые публикации</b>
              <p style={{margin: '5px 0 0', color: C.textSec, fontSize: '12px'}}>Посты для сайта и MAX-каналов с UTM-метками, чтобы заявки возвращались в CRM.</p>
            </div>
            <button type="button" onClick={loadMarketing} style={btnG}><RefreshCw size={14}/>{marketingLoading ? 'Обновление' : 'Обновить'}</button>
          </div>

          <div style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'repeat(2, minmax(0, 1fr))', gap: '10px'}}>
            <input placeholder="Заголовок поста" value={marketingForm.title} onChange={event => setMarketingForm(prev => ({...prev, title: event.target.value}))} style={field}/>
            <select value={marketingForm.projectId} onChange={event => setMarketingForm(prev => ({...prev, projectId: event.target.value}))} style={field}>
              <option value="">Без привязки к объекту</option>
              {activeProjects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}
            </select>
            <input placeholder="Ссылка публикации" value={marketingForm.publicationUrl} onChange={event => setMarketingForm(prev => ({...prev, publicationUrl: event.target.value}))} style={field}/>
            <input placeholder="UTM кампания" value={marketingForm.utmCampaign} onChange={event => setMarketingForm(prev => ({...prev, utmCampaign: event.target.value}))} style={field}/>
            <select value={marketingForm.channelId} onChange={event => setMarketingForm(prev => ({...prev, channelId: event.target.value}))} style={field}>
              <option value="">MAX-канал не выбран</option>
              {marketingChannels.map(channel => <option key={channel.id} value={channel.id}>{channel.title || channel.chatId}</option>)}
            </select>
            <div style={{display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center'}}>
              <label style={{...badge(marketingForm.targetSite ? C.success : C.textSec, marketingForm.targetSite ? C.successLight : C.bg, C.border), cursor: 'pointer'}}>
                <input type="checkbox" checked={marketingForm.targetSite} onChange={event => setMarketingForm(prev => ({...prev, targetSite: event.target.checked}))} style={{margin: 0}}/> Сайт
              </label>
              <label style={{...badge(marketingForm.targetMax ? C.info : C.textSec, marketingForm.targetMax ? C.infoLight : C.bg, C.border), cursor: 'pointer'}}>
                <input type="checkbox" checked={marketingForm.targetMax} onChange={event => setMarketingForm(prev => ({...prev, targetMax: event.target.checked}))} style={{margin: 0}}/> MAX
              </label>
            </div>
            <textarea placeholder="Текст публикации" value={marketingForm.body} onChange={event => setMarketingForm(prev => ({...prev, body: event.target.value}))} style={{...textarea, minHeight: '108px', gridColumn: isMobile ? 'auto' : 'span 2'}}/>
          </div>

          <div style={{display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '12px'}}>
            <button type="button" onClick={fillMarketingFromProject} style={btnG}><Globe2 size={14}/>Из объекта</button>
            <button type="button" onClick={createMarketingPublication} style={btnO}><Plus size={14}/>Создать пост</button>
          </div>

          <div style={{display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '14px'}}>
            {marketingPublications.length === 0 && <span style={{fontSize: '12px', color: C.textMuted}}>Публикаций пока нет.</span>}
            {marketingPublications.map(publication => (
              <div key={publication.id} style={{border: '1px solid ' + C.border, borderRadius: '8px', padding: '10px', backgroundColor: C.bg}}>
                <div style={{display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap'}}>
                  <div style={{minWidth: 0}}>
                    <b style={{display: 'block', color: C.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>{publication.title}</b>
                    <span style={{display: 'block', color: C.textSec, fontSize: '12px', marginTop: '2px'}}>
                      {publication.status} · {publication.utmCampaign || 'без UTM'}{publication.projectName ? ' · ' + publication.projectName : ''}
                    </span>
                  </div>
                  <button type="button" onClick={() => publishMarketingPublication(publication)} style={btnO}><Send size={14}/>Опубликовать</button>
                </div>
                {publication.body && <p style={{margin: '8px 0 0', color: C.textSec, fontSize: '12px', lineHeight: 1.45}}>{publication.body}</p>}
              </div>
            ))}
          </div>
        </div>

        <div style={{...card, padding: isMobile ? '14px' : '18px'}}>
          <b style={{color: C.text, fontSize: '16px'}}>MAX-каналы</b>
          <div style={{display: 'grid', gap: '8px', marginTop: '10px'}}>
            <input placeholder="MAX chatId" value={channelForm.chatId} onChange={event => setChannelForm(prev => ({...prev, chatId: event.target.value}))} style={field}/>
            <input placeholder="Название канала" value={channelForm.title} onChange={event => setChannelForm(prev => ({...prev, title: event.target.value}))} style={field}/>
            <input placeholder="Кампания по умолчанию" value={channelForm.campaignCode} onChange={event => setChannelForm(prev => ({...prev, campaignCode: event.target.value}))} style={field}/>
            <button type="button" onClick={createMarketingChannel} style={btnO}><Plus size={14}/>Добавить канал</button>
          </div>
          <div style={{display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '12px'}}>
            {marketingChannels.length === 0 && <span style={{fontSize: '12px', color: C.textMuted}}>Маркетинговые MAX-каналы не привязаны.</span>}
            {marketingChannels.map(channel => (
              <div key={channel.id} style={{border: '1px solid ' + C.border, borderRadius: '8px', padding: '9px', backgroundColor: C.bg}}>
                <b style={{display: 'block', color: C.text}}>{channel.title || channel.chatId}</b>
                <span style={{display: 'block', color: C.textSec, fontSize: '12px', marginTop: '2px'}}>{channel.chatId}{channel.campaignCode ? ' · ' + channel.campaignCode : ''}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
