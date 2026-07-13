import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Calculator,
  Camera,
  Check,
  ChevronRight,
  Clock,
  FileText,
  House,
  Image,
  MapPin,
  Package,
  QrCode,
  Settings,
  ShieldCheck,
} from 'lucide-react';
import './PublicSitePage.css';
import {
  PUBLIC_SITE_OPERATOR,
  PROJECT_EXAMPLE_STATUS,
  publicFunnelSteps,
  projectFilters,
  workProofItems,
  trustItems,
  faqItems,
  referenceDirections,
  getReferenceProjectCards,
  findReferenceProjectByCode,
  getProjectMediaOptions,
  getProjectSpecs,
  getProjectLayoutGroups,
  getReferenceObjectCard,
  getProjectMediaSequence,
  ProjectConceptThumb,
  ProjectCardMediaPreview,
  ProjectConceptVisual,
  partnerTypes,
  publicCalcDefaults
} from '../features/public-site/publicSiteContent';
import { PublicSiteCalculatorSection } from '../features/public-site/PublicSiteCalculatorSection';
import { PublicLayoutRequestEditor } from '../features/public-site/PublicLayoutRequestEditor';
import { usePublicSiteCalculator } from '../features/public-site/usePublicSiteCalculator';
import { usePublicSiteProjects } from '../features/public-site/usePublicSiteProjects';
import { usePublicSiteLeadForms } from '../features/public-site/usePublicSiteLeadForms';
const PublicSitePage = ({ onLogin }) => {
  const [calc, setCalc] = useState(publicCalcDefaults);
  const [selectedReferenceId, setSelectedReferenceId] = useState(referenceDirections[0].id);
  const [selectedReferenceExample, setSelectedReferenceExample] = useState(getReferenceProjectCards(referenceDirections[0])[0].title);
  const [selectedReferenceMediaId, setSelectedReferenceMediaId] = useState('render-front');
  const [isReferenceMirrored, setIsReferenceMirrored] = useState(false);
  const [referenceActionMessage, setReferenceActionMessage] = useState('');
  const [isLayoutRequestOpen, setIsLayoutRequestOpen] = useState(false);
  const deepLinkedReferenceRef = useRef(false);

  const {
    sitePricingRules,
    leadFileUploadsEnabled,
    hasPublishedProjects,
    projectCategory,
    filteredProjects,
    selectedProject,
    selectedPhoto,
    selectedPhotoIndex,
    setSelectedPhotoIndex,
    chooseProjectCategory,
    chooseProject,
  } = usePublicSiteProjects();

  const { result, updateCalc, getReferenceProjectEstimate } = usePublicSiteCalculator({
    calc,
    setCalc,
    sitePricingRules,
  });

  const selectedReference = referenceDirections.find((item) => item.id === selectedReferenceId) || referenceDirections[0];
  const selectedReferenceProjects = getReferenceProjectCards(selectedReference);
  const selectedReferenceProject = selectedReferenceProjects.find((project) => project.title === selectedReferenceExample) || selectedReferenceProjects[0];
  const selectedReferenceSpecs = getProjectSpecs(selectedReference, selectedReferenceProject);
  const selectedReferenceLayoutGroups = getProjectLayoutGroups(selectedReference, selectedReferenceProject);
  const selectedReferenceMediaOptions = getProjectMediaOptions(selectedReference, selectedReferenceProject);
  const selectedReferenceMedia = selectedReferenceMediaOptions.find((item) => item.id === selectedReferenceMediaId) || selectedReferenceMediaOptions[0];
  const selectedReferenceMediaIndex = Math.max(0, selectedReferenceMediaOptions.findIndex((item) => item.id === selectedReferenceMedia?.id));
  const selectedReferenceEstimate = getReferenceProjectEstimate(selectedReference, selectedReferenceProject);
  const selectedReferenceObjectCard = getReferenceObjectCard(selectedReference, selectedReferenceProject, selectedReferenceEstimate);
  const selectedReferenceRenderCount = selectedReferenceMediaOptions.filter((item) => item.role === 'render' || item.kind === 'render').length;
  const selectedReferencePlanCount = selectedReferenceMediaOptions.filter((item) => item.role === 'plan' || item.kind === 'plan').length;
  const selectedReferenceAssetSummary = [
    { icon: Camera, label: '3D ракурсы', value: `${Math.max(1, selectedReferenceRenderCount)} шт.` },
    { icon: FileText, label: 'Планировка', value: `${Math.max(1, selectedReferencePlanCount)} шт.` },
    { icon: Calculator, label: 'Ориентир', value: selectedReferenceEstimate.fromLabel },
    { icon: Check, label: 'Действие', value: 'в расчет' },
  ];
  const selectedReferenceDecisionFacts = [
    ['Направление', selectedReference.title],
    ['Проект', selectedReferenceProject?.code || 'карточка'],
    ['Ориентир', selectedReferenceEstimate.fromLabel],
    ['Медиа', `${selectedReferenceMediaOptions.length} вида`],
  ];
  const selectedReferenceDeepLink = selectedReferenceProject?.code
    ? `/?project=${encodeURIComponent(selectedReferenceProject.code)}#projects`
    : '/#projects';
  const selectedReferencePublicUrl = `https://stroyka26.pro${selectedReferenceDeepLink}`;
  const selectedLeadProject = {
    status: PROJECT_EXAMPLE_STATUS,
    directionId: selectedReference.id,
    directionTitle: selectedReference.title,
    projectCode: selectedReferenceProject?.code || '',
    projectTitle: selectedReferenceProject?.title || selectedReference.title,
    projectArea: selectedReferenceProject?.area || '',
    projectFloors: selectedReferenceProject?.floors || '',
    projectLayout: selectedReferenceProject?.layout || selectedReference.text,
    projectVisuals: selectedReferenceProject?.visuals || '',
    projectUrl: selectedReferencePublicUrl,
    estimateRange: selectedReferenceEstimate.rangeLabel,
    estimateFrom: selectedReferenceEstimate.fromLabel,
    mediaCount: selectedReferenceMediaOptions.length,
    media: selectedReferenceMediaOptions.map((item) => ({
      id: item.id,
      label: item.label,
      role: item.role,
      src: item.src || '',
    })),
  };

  const {
    lead,
    setLead,
    leadConsent,
    setLeadConsent,
    leadWebsite,
    setLeadWebsite,
    sent,
    leadSending,
    leadError,
    leadFiles,
    chooseLeadFiles,
    partnerLead,
    setPartnerLead,
    partnerConsent,
    setPartnerConsent,
    partnerWebsite,
    setPartnerWebsite,
    partnerSending,
    partnerSent,
    partnerError,
    submitLead,
    submitPartnerLead,
  } = usePublicSiteLeadForms({
    result,
    selectedLeadProject,
    onLeadFilesChanged: (count) => setCalc((current) => ({ ...current, files: count })),
  });

  const scrollTo = useCallback((id) => {
    if (typeof document === 'undefined') return;
    const element = document.getElementById(id);
    if (element) element.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, []);

  const scrollToCurrentHash = useCallback(() => {
    if (typeof window === 'undefined') return;
    const id = decodeURIComponent(window.location.hash.replace(/^#/, ''));
    if (!id) return;
    [0, 120, 420].forEach((delay) => {
      setTimeout(() => scrollTo(id), delay);
    });
  }, [scrollTo]);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    scrollToCurrentHash();
    window.addEventListener('hashchange', scrollToCurrentHash);
    return () => window.removeEventListener('hashchange', scrollToCurrentHash);
  }, [scrollToCurrentHash]);

  const chooseReference = useCallback((direction, project = getReferenceProjectCards(direction)[0], scrollTarget = '') => {
    const projectCard = typeof project === 'string'
      ? getReferenceProjectCards(direction).find((item) => item.title === project) || { title: project, calcPatch: {} }
      : project;
    setSelectedReferenceId(direction.id);
    setSelectedReferenceExample(projectCard.title);
    setSelectedReferenceMediaId('render-front');
    setIsReferenceMirrored(false);
    setIsLayoutRequestOpen(false);
    setCalc((current) => ({ ...current, ...direction.calcPatch, ...(projectCard.calcPatch || {}) }));
    setLead((current) => ({
      ...current,
      comment: `Интересует: ${direction.title}. Проект: ${projectCard.title}. Формат объекта: ${getReferenceObjectCard(direction, projectCard, getReferenceProjectEstimate(direction, projectCard)).format}. Планировка: ${projectCard.layout || direction.text}. Ссылка на карточку: https://stroyka26.pro/?project=${encodeURIComponent(projectCard.code || '')}#projects`,
    }));
    if (scrollTarget === 'calculator' || scrollTarget === true) {
      setTimeout(() => scrollTo('calculator'), 0);
    }
    if (scrollTarget === 'catalog') {
      setTimeout(() => document.querySelector('.public-project-catalog')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0);
    }
  }, [getReferenceProjectEstimate, scrollTo, setLead]);

  useEffect(() => {
    if (deepLinkedReferenceRef.current) return;
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    const projectCode = params.get('project') || params.get('ref');
    const match = findReferenceProjectByCode(projectCode);
    if (!match) return;
    deepLinkedReferenceRef.current = true;
    chooseReference(match.direction, match.project, 'catalog');
  }, [chooseReference]);

  const chooseSimilarReferenceProject = () => {
    const currentIndex = selectedReferenceProjects.findIndex((project) => project.title === selectedReferenceProject?.title);
    const nextProject = selectedReferenceProjects[(currentIndex + 1) % selectedReferenceProjects.length] || selectedReferenceProjects[0];
    chooseReference(selectedReference, nextProject);
    setReferenceActionMessage(`Открыт похожий проект: ${nextProject.title}`);
    setTimeout(() => scrollTo('selected-project-preview'), 0);
  };

  const toggleReferenceMirror = () => {
    const nextValue = !isReferenceMirrored;
    setSelectedReferenceMediaId('render-front');
    setIsReferenceMirrored(nextValue);
    setReferenceActionMessage(nextValue ? 'Зеркальный вариант включён' : 'Обычный вариант восстановлен');
    setTimeout(() => scrollTo('selected-project-preview'), 0);
  };

  const openLayoutRequest = () => {
    setIsLayoutRequestOpen(true);
    setReferenceActionMessage('Укажите, что нужно изменить в планировке');
    setTimeout(() => scrollTo('public-layout-request-editor'), 80);
  };

  const applyLayoutRequest = ({ spaces, bathrooms, garage, notes }) => {
    const isHouseLayout = selectedReference.calcPatch?.type === 'house';
    const spacesText = isHouseLayout
      ? `${spaces} ${spaces === 1 ? 'спальня' : spaces > 1 && spaces < 5 ? 'спальни' : 'спален'}`
      : `${spaces} ${spaces === 1 ? 'комната / зона' : spaces > 1 && spaces < 5 ? 'комнаты / зоны' : 'комнат / зон'}`;
    setCalc((current) => ({ ...current, ...selectedReference.calcPatch, ...(selectedReferenceProject?.calcPatch || {}) }));
    setLead((current) => ({
      ...current,
      comment: [
        `Нужна доработка планировки. Направление: ${selectedReference.title}.`,
        `Проект: ${selectedReferenceProject?.title || selectedReference.title}.`,
        `Пожелания: ${spacesText}, ${bathrooms} ${bathrooms === 1 ? 'санузел' : bathrooms > 1 && bathrooms < 5 ? 'санузла' : 'санузлов'}${isHouseLayout ? `, ${garage ? 'гараж нужен' : 'гараж не нужен'}` : ''}.`,
        notes ? `Дополнительно: ${notes}.` : '',
        `Исходная планировка: ${selectedReferenceProject?.layout || selectedReference.text}`,
      ].filter(Boolean).join(' '),
    }));
    setIsLayoutRequestOpen(false);
    setReferenceActionMessage('Запрос на изменение планировки добавлен в заявку');
    setTimeout(() => scrollTo('request'), 0);
  };

  const calculateSelectedReference = () => {
    setReferenceActionMessage('Проект передан в калькулятор');
    chooseReference(selectedReference, selectedReferenceProject, 'calculator');
  };


  return (
    <main className="public-site">
      <section
        className="public-hero"
        style={{ '--public-hero-image': 'url("/site-assets/projects/h2-01/facade.webp")' }}
      >
        <header className="public-nav">
          <button className="public-brand" type="button" onClick={() => scrollTo('top')}>
            <span>Строй</span><strong>Ка</strong>
          </button>
          <nav className="public-nav-links" aria-label="Навигация по сайту">
            <button type="button" onClick={() => scrollTo('directions')}>Направления</button>
            <button type="button" onClick={() => scrollTo('projects')}>Проекты</button>
            <button type="button" onClick={() => scrollTo('calculator')}>Калькулятор</button>
            <button type="button" onClick={() => scrollTo('process')}>Как работаем</button>
            <button type="button" onClick={() => scrollTo('objects')}>Работы</button>
            <button type="button" onClick={() => scrollTo('request')}>Заявка</button>
          </nav>
          <button className="public-login" type="button" onClick={onLogin}>Вход в ERP</button>
        </header>

        <div id="top" className="public-hero-content">
          <div className="public-hero-copy">
            <p className="public-eyebrow">Строительная компания с цифровым контролем</p>
            <h1>Строим с понятной сметой и цифровым паспортом объекта</h1>
            <p className="public-lead">
              Расчёт стоимости, фотоотчёты, этапы работ, материалы и гарантия
              ведутся в одной системе.
            </p>
            <div className="public-hero-actions">
              <button className="public-primary" type="button" onClick={() => scrollTo('directions')}>
                Выбрать проект
                <ChevronRight size={18} />
              </button>
              <button className="public-secondary" type="button" onClick={() => scrollTo('calculator')}>
                Рассчитать стоимость
              </button>
            </div>
            <div className="public-hero-flow" aria-label="Путь клиента на сайте">
              {publicFunnelSteps.map((step) => (
                <button key={step.number} type="button" onClick={() => scrollTo(step.target)}>
                  <b>{step.number}</b>
                  <span>
                    <strong>{step.title}</strong>
                    <small>{step.text}</small>
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="public-hero-tools">
          <PublicSiteCalculatorSection
            calc={calc}
            updateCalc={updateCalc}
            result={result}
            scrollTo={scrollTo}
            leadFileUploadsEnabled={leadFileUploadsEnabled}
            leadFiles={leadFiles}
            chooseLeadFiles={chooseLeadFiles}
          />

          <section id="passport" className="public-passport" aria-label="Цифровой паспорт объекта">
            <div className="public-passport-top">
              <div>
                <p className="public-tool-kicker">Пример контроля</p>
                <h2>Цифровой паспорт объекта</h2>
              </div>
              <div className="public-passport-status">
                <Check size={15} />
                Гарантия активна
              </div>
            </div>

            <div className="public-object-card">
              <div>
                <strong>Дом 142 м2, Михайловск</strong>
                <span><MapPin size={14} /> Этап: тёплый контур</span>
              </div>
              <b>68%</b>
            </div>

            <div className="public-passport-line">
              {['Смета', 'Материалы', 'Работы', 'Приёмка', 'Гарантия'].map((item, index) => (
                <div className={index < 3 ? 'done' : ''} key={item}>
                  <i />
                  <span>{item}</span>
                </div>
              ))}
            </div>

            <div className="public-passport-grid">
              <div className="public-passport-photo">
                <img
                  src="https://images.unsplash.com/photo-1503387762-592deb58ef4e?auto=format&fit=crop&w=700&q=80"
                  alt="Фотоотчёт со строительного объекта"
                />
                <span>Фотоотчёт за сегодня</span>
              </div>
              <div className="public-proof-list">
                <p><Package size={16} /> Материалы приняты: 12 позиций</p>
                <p><FileText size={16} /> Этапы подтверждены: 4</p>
                <p><Clock size={16} /> Отклонений по сроку нет</p>
                <p><QrCode size={16} /> QR-проверка паспорта</p>
              </div>
            </div>
          </section>
        </div>
      </section>

      <section id="services" className="public-section public-services">
        <div className="public-section-head">
          <p className="public-eyebrow dark">Что делаем</p>
          <h2>Берём объект от расчёта до гарантии</h2>
        </div>
        <div className="public-service-row">
          {[
            ['Строительство домов', 'Коробка, тёплый контур, под ключ'],
            ['Ремонт и реконструкция', 'Квартиры, дома, коммерческие помещения'],
            ['Инженерные системы', 'Электрика, вода, отопление, вентиляция'],
            ['Контроль объекта', 'Фото, этапы, материалы, гарантия'],
          ].map(([title, text]) => (
            <article className="public-service" key={title}>
              <Settings size={20} />
              <h3>{title}</h3>
              <p>{text}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="trust" className="public-section public-trust">
        <div className="public-section-head">
          <p className="public-eyebrow dark">Почему удобно</p>
          <h2>Сайт связан с рабочим процессом, а не просто собирает телефоны</h2>
          <p>
            Клиент выбирает проект и отправляет его в расчёт, а команда получает
            понятную заявку с контекстом: что выбрано, какой ориентир стоимости и какие файлы приложены.
          </p>
        </div>
        <div className="public-trust-grid">
          {trustItems.map((item) => (
            <article className="public-trust-card" key={item.title}>
              <span><item.icon size={18} /></span>
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="objects" className="public-section public-objects">
        {hasPublishedProjects && <>
          <div className="public-section-head">
            <p className="public-eyebrow dark">Объекты</p>
            <h2>Галерея выполненных и текущих объектов</h2>
            <p>Опубликованные фотографии, этапы и показатели объектов.</p>
          </div>

        <div className="public-gallery-tabs" aria-label="Фильтр проектов">
          {projectFilters.map((filter) => (
            <button
              className={projectCategory === filter.value ? 'active' : ''}
              type="button"
              key={filter.value}
              onClick={() => chooseProjectCategory(filter.value)}
            >
              {filter.label}
            </button>
          ))}
        </div>

        <div className="public-gallery">
          <article className="public-gallery-feature">
            <div className="public-gallery-image">
              <img src={selectedPhoto} alt={selectedProject.title} />
              <div className="public-gallery-image-badge">
                <Camera size={16} />
                {selectedProject.images.length} фото в объекте
              </div>
            </div>
            <div className="public-gallery-thumbs">
              {selectedProject.images.map((imageUrl, index) => (
                <button
                  className={selectedPhotoIndex === index ? 'active' : ''}
                  type="button"
                  key={imageUrl}
                  onClick={() => setSelectedPhotoIndex(index)}
                  aria-label={`Фото ${index + 1}: ${selectedProject.title}`}
                >
                  <img src={imageUrl} alt="" />
                </button>
              ))}
            </div>
          </article>

          <aside className="public-gallery-info">
            <div className="public-gallery-info-top">
              <div>
                <p className="public-tool-kicker">Выбранный проект</p>
                <h3>{selectedProject.title}</h3>
                <span><MapPin size={14} /> {selectedProject.location} · {selectedProject.year}</span>
              </div>
              <strong>{selectedProject.progress}%</strong>
            </div>

            <div className="public-gallery-progress">
              <i style={{ width: `${selectedProject.progress}%` }} />
            </div>

            <div className="public-gallery-metrics">
              <div><span>Площадь</span><b>{selectedProject.area}</b></div>
              <div><span>Срок</span><b>{selectedProject.term}</b></div>
              <div><span>Бюджет</span><b>{selectedProject.price}</b></div>
              <div><span>Этап</span><b>{selectedProject.stage}</b></div>
            </div>

            <div className="public-gallery-proof">
              <p><Image size={16} /> {selectedProject.result}</p>
              <p><ShieldCheck size={16} /> {selectedProject.passport}</p>
              <p><QrCode size={16} /> Можно открыть цифровой паспорт объекта</p>
            </div>

            <div className="public-gallery-tags">
              {selectedProject.tags.map((tag) => <span key={tag}>{tag}</span>)}
            </div>
          </aside>
        </div>

        <div className="public-project-strip">
          {filteredProjects.map((project) => (
            <button
              className={selectedProject.id === project.id ? 'active' : ''}
              type="button"
              key={project.id}
              onClick={() => chooseProject(project.id)}
            >
              <img src={project.images[0]} alt="" />
              <span>
                <b>{project.title}</b>
                <small>{project.area} · {project.stage}</small>
              </span>
            </button>
          ))}
        </div>
        </>}

        <div id="work-proof" className="public-work-proof">
          <div className="public-section-head compact">
            <p className="public-eyebrow dark">Наши работы</p>
            <h2>Показываем не только красивый финал, а доказательства выполнения</h2>
            <p>
              Для сайта отдельно выводятся реальные работы и понятные этапы:
              фото, ход работ, материалы, результат и паспорт объекта.
            </p>
          </div>
          <div className="public-work-grid">
            {workProofItems.map((item) => (
              <article className="public-work-card" key={item.title}>
                <img src={item.image} alt={item.title} />
                <div>
                  <span><item.icon size={15} /> {item.metric}</span>
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                </div>
              </article>
            ))}
          </div>
        </div>

        <div id="directions" className="public-reference-board">
          <div className="public-section-head compact">
            <p className="public-eyebrow dark">Идеи для проекта</p>
            <h2>15 направлений и готовые проектные карточки</h2>
            <p>
              Это не выполненные объекты, а понятные проект-идеи для заявки. Клиент выбирает
              направление, готовую планировку и отправляет ее в расчет.
            </p>
          </div>
          <div className="public-reference-layout">
            <div className="public-reference-grid" aria-label="Направления проектов">
              {referenceDirections.map((item) => {
                const isActive = selectedReference.id === item.id;
                const projectCards = getReferenceProjectCards(item);
                const directionEstimate = getReferenceProjectEstimate(item, projectCards[0]);
                const mediaCount = getProjectMediaSequence(item, projectCards[0]).length;
                const planCount = getProjectMediaSequence(item, projectCards[0])
                  .filter((media) => media.role === 'plan' || media.kind === 'plan').length;
                return (
                  <button
                    className={isActive ? 'public-reference-card active' : 'public-reference-card'}
                    key={item.id}
                    type="button"
                    onClick={() => chooseReference(item, projectCards[0], 'catalog')}
                    aria-pressed={isActive}
                  >
                    <ProjectConceptThumb direction={item} project={projectCards[0]} />
                    <span className="public-reference-count">{projectCards.length} проекта</span>
                    <span className="public-reference-price">{directionEstimate.fromLabel}</span>
                    <span className="public-reference-media-note">{mediaCount} вида · {planCount} план</span>
                    <h3>{item.title}</h3>
                    <p>{item.text}</p>
                    <div>
                      {item.tags.map((tag) => <span key={tag}>{tag}</span>)}
                    </div>
                    <span className="public-reference-open">Смотреть проекты</span>
                  </button>
                );
              })}
            </div>

	            <section id="projects" className="public-project-catalog" aria-label="Готовые проекты выбранного направления">
	              <div className="public-project-catalog-head">
	                <div>
	                  <p>Открытое направление</p>
	                  <h3>{selectedReference.title}</h3>
	                  <span>{selectedReference.text}</span>
	                </div>
	                <div className="public-project-catalog-badges" aria-label="Состав направления">
	                  <strong>{selectedReferenceProjects.length} проекта</strong>
                    <span>{selectedReferenceMediaOptions.length} вида</span>
                    <span>{selectedReferencePlanCount} план</span>
	                </div>
	              </div>
                <div className="public-project-decision-bar">
                  <div className="public-project-decision-copy">
                    <span>Выбрано для расчета</span>
                    <strong>{selectedReferenceProject?.title || selectedReference.title}</strong>
                    <small>{selectedReferenceProject?.layout || selectedReference.text}</small>
                  </div>
                  <div className="public-project-decision-facts" aria-label="Кратко по выбранному проекту">
                    {selectedReferenceDecisionFacts.map(([label, value]) => (
                      <span key={label}>
                        <small>{label}</small>
                        <b>{value}</b>
                      </span>
                    ))}
                  </div>
                  <div className="public-project-decision-actions">
                    <a
                      className="public-secondary dark public-project-share-link"
                      href={selectedReferenceDeepLink}
                    >
                      Ссылка
                    </a>
                    <button
                      className="public-secondary dark"
                      type="button"
                      onClick={() => chooseReference(selectedReference, selectedReferenceProject, 'calculator')}
                    >
                      К расчету
                    </button>
                    <button
                      className="public-primary"
                      type="button"
                      onClick={() => {
                        chooseReference(selectedReference, selectedReferenceProject);
                        setTimeout(() => scrollTo('request'), 0);
                      }}
                    >
                      Оставить заявку
                    </button>
                  </div>
                </div>
	              <div className="public-project-catalog-main">
	                <div className="public-project-visual-column">
	                  <div className="public-project-thumb-grid" aria-label="Варианты проекта">
	                    {selectedReferenceProjects.map((project) => {
	                      const projectEstimate = getReferenceProjectEstimate(selectedReference, project);
                        const projectMediaSequence = getProjectMediaSequence(selectedReference, project).slice(0, 4);
	                      return (
	                        <button
	                          className={selectedReferenceProject?.title === project.title ? 'active' : ''}
                          type="button"
	                          key={project.code}
	                          onClick={() => chooseReference(selectedReference, project)}
	                        >
	                          <ProjectCardMediaPreview direction={selectedReference} project={project} />
	                          <span className="public-project-card-copy">
	                            <b>{project.code}</b>
	                            <span className="public-project-card-status">{PROJECT_EXAMPLE_STATUS}</span>
	                            <strong>{project.title}</strong>
	                            <small>{project.area} · {project.floors}</small>
	                            <span className="public-project-card-price">Примерная стоимость: {projectEstimate.rangeLabel}</span>
                              <span className="public-project-card-sequence">
                                {projectMediaSequence.map((media) => (
                                  <i key={media.id}>
                                    <b>{media.number}</b>
                                    {media.compactLabel}
                                  </i>
                                ))}
                              </span>
	                            <em>{project.visuals}</em>
	                          </span>
	                        </button>
	                      );
	                    })}
	                  </div>
	                  <div
                      id="selected-project-preview"
                      className={isReferenceMirrored ? 'public-project-hero-visual mirrored' : 'public-project-hero-visual'}
                    >
	                    <ProjectConceptVisual
	                      direction={selectedReference}
	                      project={selectedReferenceProject}
	                      media={selectedReferenceMedia}
	                    />
                    {(selectedReferenceMedia?.kind === 'render' || selectedReferenceMedia?.role === 'render') && (
	                      <>
	                        <span className="public-project-ready-ribbon">Проект-идея</span>
	                        <span className="public-project-discount">10%</span>
	                      </>
	                    )}
                      <span className="public-project-media-counter">
                        {selectedReferenceMediaIndex + 1} / {selectedReferenceMediaOptions.length}
                        <b>{selectedReferenceMedia?.label || 'Визуал'}</b>
                      </span>
	                  </div>
                    <div className="public-project-media-head">
                      <span>Состав проекта</span>
                      <strong>{selectedReferenceMediaOptions.length} материала для просмотра</strong>
                    </div>
	                  <div className="public-project-media-strip" aria-label="Медиа проекта">
	                    {selectedReferenceMediaOptions.map((media, index) => (
	                      <button
	                        className={selectedReferenceMedia.id === media.id ? 'active' : ''}
	                        type="button"
	                        key={media.id}
	                        onClick={() => setSelectedReferenceMediaId(media.id)}
	                      >
                          <span className="public-project-media-option-visual">
                            <ProjectConceptVisual
                              direction={selectedReference}
                              project={selectedReferenceProject}
                              media={media}
                            />
                            <b>{index + 1}</b>
                          </span>
	                        <span>{media.label}</span>
	                      </button>
	                    ))}
	                  </div>
                    <div className="public-project-asset-summary" aria-label="Комплектация карточки проекта">
                      {selectedReferenceAssetSummary.map((item) => {
                        const AssetIcon = item.icon;
                        return (
                          <span key={item.label}>
                            <AssetIcon size={15} />
                            <small>{item.label}</small>
                            <b>{item.value}</b>
                          </span>
                        );
                      })}
                    </div>
	                </div>

                <div className="public-project-spec-column">
                  <p className="public-tool-kicker">Каталог готовых проектов</p>
                  <h3>{selectedReferenceProject?.title || selectedReference.title}</h3>
                  <p>{selectedReferenceProject?.layout || selectedReference.text}</p>
                  <div className="public-project-layout-card">
                    <span>Планировочное решение</span>
                    {selectedReferenceLayoutGroups.map((group) => (
                      <div key={group.title}>
                        <strong>{group.title}</strong>
                        <ul>
                          {group.items.map((item) => (
                            <li key={item}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                  <div className="public-project-cost-panel">
                    <span>Примерная стоимость этого проекта</span>
                    <strong>{selectedReferenceEstimate.rangeLabel}</strong>
                    <small>Ориентир для сайта. Точная сумма зависит от замера, проекта, грунтов, материалов и комплектации.</small>
                  </div>
                  <div className="public-generated-object-card">
                    <div className="public-generated-object-head">
                      <span>{selectedReferenceObjectCard.status}</span>
                      <b>{selectedReferenceObjectCard.code}</b>
                    </div>
                    <h4>{selectedReferenceObjectCard.format}</h4>
                    <p>{selectedReferenceObjectCard.summary}</p>
                    <div className="public-generated-object-facts">
                      {selectedReferenceObjectCard.facts.map(([label, value]) => (
                        <span key={label}>
                          <small>{label}</small>
                          <strong>{value}</strong>
                        </span>
                      ))}
                    </div>
                    <div className="public-generated-object-flow">
                      {selectedReferenceObjectCard.stages.map((stage, index) => (
                        <span key={stage}>
                          <b>{index + 1}</b>
                          {stage}
                        </span>
                      ))}
                    </div>
                    <div className="public-generated-object-output">
                      {selectedReferenceObjectCard.deliverables.map((item) => (
                        <span key={item}>
                          <Check size={14} />
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                  <dl className="public-project-spec-list">
                    {selectedReferenceSpecs.map(([label, value]) => (
                      <div key={label}>
                        <dt>{label}</dt>
                        <dd>{value}</dd>
                      </div>
                    ))}
                  </dl>
                  <button
                    className="public-project-outline"
                    type="button"
                    aria-pressed={isReferenceMirrored}
                    onClick={toggleReferenceMirror}
                  >
                    {isReferenceMirrored ? 'Вернуть обычный вариант' : 'Показать зеркальный вариант'}
                  </button>
                  <button
                    className="public-project-editor"
                    type="button"
                    aria-expanded={isLayoutRequestOpen}
                    aria-controls="public-layout-request-editor"
                    onClick={openLayoutRequest}
                  >
                    Изменить планировку в заявке
                  </button>
                  {isLayoutRequestOpen && (
                    <PublicLayoutRequestEditor
                      key={selectedReferenceProject?.code || selectedReference.id}
                      projectTitle={selectedReferenceProject?.title || selectedReference.title}
                      initialSpaces={selectedReference.calcPatch?.type === 'house'
                        ? Number(selectedReferenceProject?.calcPatch?.bedrooms) || Number.parseInt(selectedReferenceSpecs.find(([label]) => label === 'Количество спален')?.[1], 10) || 3
                        : Number(selectedReferenceProject?.calcPatch?.rooms) || 1}
                      initialBathrooms={Number(selectedReferenceProject?.calcPatch?.bathrooms) || 1}
                      initialGarage={String(selectedReferenceSpecs.find(([label]) => label === 'Гараж')?.[1] || '').toLowerCase() === 'есть'}
                      isHouseLayout={selectedReference.calcPatch?.type === 'house'}
                      onApply={applyLayoutRequest}
                      onCancel={() => setIsLayoutRequestOpen(false)}
                    />
                  )}
                  <button className="public-project-outline" type="button" onClick={chooseSimilarReferenceProject}>
                    Похожие по виду ({Math.max(3, selectedReferenceProjects.length)})
                  </button>
                  <p className="public-project-action-status" role="status" aria-live="polite">
                    {referenceActionMessage}
                  </p>
                  <button
                    className="public-primary public-reference-cta"
                    type="button"
                    onClick={calculateSelectedReference}
                  >
                    Рассчитать такой проект
                    <ChevronRight size={18} />
                  </button>
                </div>
              </div>
            </section>
          </div>
        </div>
      </section>

      <section id="process" className="public-section public-process">
        <div className="public-section-head">
          <p className="public-eyebrow dark">Как ведём объект</p>
          <h2>Заявка сразу превращается в управляемую стройку</h2>
        </div>
        <div className="public-process-grid">
          {[
            ['1', 'Заявка', 'Клиент оставляет расчёт и контакты'],
            ['2', 'Смета', 'Команда уточняет объём и стоимость'],
            ['3', 'Стройка', 'Работы, материалы и фото ведутся в ERP'],
            ['4', 'Паспорт и гарантия', 'Клиент получает историю объекта'],
          ].map(([num, title, text]) => (
            <article className="public-process-item" key={title}>
              <b>{num}</b>
              <h3>{title}</h3>
              <p>{text}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="faq" className="public-section public-faq">
        <div className="public-section-head">
          <p className="public-eyebrow dark">Частые вопросы</p>
          <h2>Чтобы перед заявкой было понятно, что именно считается</h2>
        </div>
        <div className="public-faq-grid">
          {faqItems.map((item) => (
            <article className="public-faq-card" key={item.question}>
              <h3>{item.question}</h3>
              <p>{item.answer}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="suppliers" className="public-section public-suppliers">
        <div className="public-supplier-copy">
          <p className="public-eyebrow dark">Партнёрам</p>
          <h2>Поставщик, мастер, бригада или субподрядчик сначала оставляет заявку на проверку</h2>
          <p>
            Мы не создаём активный доступ с публичного сайта автоматически. Заявка попадает
            в CRM, директор или ответственный сотрудник проверяет данные и только потом
            выдаёт кабинет, договор или приглашение.
          </p>
          <div className="public-partner-types">
            {partnerTypes.map((item) => (
              <button
                key={item.value}
                type="button"
                className={partnerLead.type === item.value ? 'active' : ''}
                onClick={() => setPartnerLead({ ...partnerLead, type: item.value })}
              >
                <span><item.icon size={15} /> {item.label}</span>
                <small>{item.note}</small>
              </button>
            ))}
          </div>
        </div>
        <form className="public-partner-form" onSubmit={submitPartnerLead}>
          <label className="public-honeypot" aria-hidden="true">
            Сайт
            <input
              value={partnerWebsite}
              onChange={(event) => setPartnerWebsite(event.target.value)}
              autoComplete="off"
              tabIndex={-1}
            />
          </label>
          <label>
            Компания или ФИО
            <input value={partnerLead.name} onChange={(event) => setPartnerLead({ ...partnerLead, name: event.target.value })} placeholder="Название или имя" />
          </label>
          <label>
            Телефон
            <input value={partnerLead.phone} onChange={(event) => setPartnerLead({ ...partnerLead, phone: event.target.value })} placeholder="+7" required />
          </label>
          <label>
            Email
            <input type="email" value={partnerLead.email} onChange={(event) => setPartnerLead({ ...partnerLead, email: event.target.value })} placeholder="mail@company.ru" />
          </label>
          <label>
            ИНН
            <input inputMode="numeric" value={partnerLead.inn} onChange={(event) => setPartnerLead({ ...partnerLead, inn: event.target.value })} placeholder="Для проверки компании или ИП" />
          </label>
          <label>
            Регион работы
            <input value={partnerLead.region} onChange={(event) => setPartnerLead({ ...partnerLead, region: event.target.value })} placeholder="Ставропольский край" />
          </label>
          <label>
            Специализация
            <input value={partnerLead.specialization} onChange={(event) => setPartnerLead({ ...partnerLead, specialization: event.target.value })} placeholder="Материалы или виды работ" />
          </label>
          <label>
            Дополнительная информация
            <textarea value={partnerLead.comment} onChange={(event) => setPartnerLead({ ...partnerLead, comment: event.target.value })} placeholder="Опыт, условия работы, примеры объектов" />
          </label>
          <label className="public-consent">
            <input
              type="checkbox"
              checked={partnerConsent}
              onChange={(event) => setPartnerConsent(event.target.checked)}
            />
            <span>
              Даю согласие на обработку данных для проверки заявки и понимаю,
              что кабинет не создаётся автоматически.
            </span>
          </label>
          <button className="public-primary" type="submit" disabled={partnerSending || !partnerConsent}>
            {partnerSending ? 'Отправляем...' : 'Отправить на проверку'}
          </button>
          <button className="public-secondary dark" type="button" onClick={onLogin}>Уже есть доступ</button>
          {partnerSent && <p className="public-form-success">Заявка отправлена в CRM на проверку.</p>}
          {partnerError && <p className="public-form-error">{partnerError}</p>}
        </form>
      </section>

      <section id="request" className="public-section public-request">
        <div>
          <p className="public-eyebrow dark">Точная смета</p>
          <h2>Оставьте заявку на расчёт</h2>
          <p>
            После отправки выбранный проект, параметры расчёта и ваши контакты
            сразу появятся в CRM у менеджера.
          </p>
        </div>
        <form className="public-request-form" onSubmit={submitLead}>
          <div className="public-request-selected">
            <span>В заявку попадёт</span>
            <strong>{selectedLeadProject.projectTitle}</strong>
            <small>
              {selectedLeadProject.directionTitle} · {selectedLeadProject.projectCode || 'проект'} · {selectedLeadProject.estimateRange}
            </small>
            <button type="button" onClick={() => scrollTo('projects')}>Изменить проект</button>
          </div>
          <label className="public-honeypot" aria-hidden="true">
            Сайт
            <input
              value={leadWebsite}
              onChange={(event) => setLeadWebsite(event.target.value)}
              autoComplete="off"
              tabIndex={-1}
            />
          </label>
          <label>
            Имя
            <input value={lead.name} onChange={(event) => setLead({ ...lead, name: event.target.value })} placeholder="Как к вам обращаться" />
          </label>
          <label>
            Телефон
            <input value={lead.phone} onChange={(event) => setLead({ ...lead, phone: event.target.value })} placeholder="+7" required />
          </label>
          <label>
            Комментарий
            <textarea value={lead.comment} onChange={(event) => setLead({ ...lead, comment: event.target.value })} placeholder="Адрес, сроки, что нужно построить" />
          </label>
          <label className="public-consent">
            <input
              type="checkbox"
              checked={leadConsent}
              onChange={(event) => setLeadConsent(event.target.checked)}
            />
            <span>
              Даю согласие на обработку имени, телефона, комментария и параметров расчёта
              для ответа на заявку. С{' '}
              <button
                className="public-consent-link"
                type="button"
                onClick={(event) => {
                  event.preventDefault();
                  scrollTo('privacy');
                }}
              >
                политикой обработки персональных данных
              </button>{' '}
              ознакомлен.
            </span>
          </label>
          <button className="public-primary" type="submit" disabled={leadSending || !leadConsent}>
            {leadSending ? 'Отправляем...' : 'Отправить заявку'}
          </button>
          {sent && <p className="public-form-success">Заявка отправлена в CRM. Менеджер или директор увидит её в разделе заявок.</p>}
          {leadError && <p className="public-form-error">{leadError}</p>}
        </form>
      </section>

      <section id="privacy" className="public-section public-legal">
        <div className="public-section-head">
          <p className="public-eyebrow dark">Юридическая информация</p>
          <h2>Политика обработки персональных данных</h2>
          <p>
            Заявки с сайта передаются в CRM только для обратной связи, расчёта и подготовки предложения.
            Полные реквизиты исполнителя фиксируются в договоре и коммерческом предложении.
          </p>
        </div>
        <div className="public-legal-grid">
          <article>
            <h3>Что обрабатываем</h3>
            <p>
              Имя, телефон, комментарий к заявке, параметры предварительного расчёта,
              технические данные отправки формы и источник заявки.
            </p>
          </article>
          <article>
            <h3>Зачем</h3>
            <p>
              Чтобы ответить на обращение, подготовить расчёт, связать заявку с CRM
              и не потерять историю общения с клиентом.
            </p>
          </article>
          <article>
            <h3>Согласие</h3>
            <p>
              Заявка отправляется только после отметки согласия. Отозвать согласие можно
              через контакт оператора, указанный в этом разделе.
            </p>
          </article>
          <article>
            <h3>Реклама</h3>
            <p>
              Рекламные сообщения и массовые рассылки не отправляются без отдельного
              согласия пользователя.
            </p>
          </article>
        </div>
        <div className="public-legal-note">
          <strong>Не является публичной офертой.</strong>
          Предварительные расчёты на сайте носят информационный характер.
          Итоговая цена, сроки, состав работ и материалов фиксируются в договоре и смете.
        </div>
        <div className="public-requisites">
          <span>Оператор: {PUBLIC_SITE_OPERATOR.name}</span>
          <span>Сайт: {PUBLIC_SITE_OPERATOR.site}</span>
          <span>По персональным данным: {PUBLIC_SITE_OPERATOR.privacyEmail}</span>
          <span>Заявки: {PUBLIC_SITE_OPERATOR.leadEmail}</span>
          <span><a href="/project-catalog.html">Каталог проектов</a></span>
          <span><a href="/privacy.html">Политика</a></span>
          <span><a href="/terms.html">Условия</a></span>
          <span><a href="/contacts.html">Контакты</a></span>
        </div>
      </section>

      <nav className="public-mobile-actions" aria-label="Быстрые действия">
        <button type="button" onClick={() => scrollTo('projects')}>
          <House size={18} />
          Проекты
        </button>
        <button className="primary" type="button" onClick={() => scrollTo('request')}>
          <Calculator size={18} />
          Заявка
        </button>
      </nav>
    </main>
  );
};

export default PublicSitePage;
