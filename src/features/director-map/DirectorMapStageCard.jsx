import React from 'react';
import { ExternalLink, Link2, Search } from 'lucide-react';
import { formatMoneyShort, getDefaultActionDisabled, getSignalTone } from './directorMapRules';

function DetailCell({ label, value }) {
  return (
    <div className="dm-kv">
      <span>{label}</span>
      <b>{value}</b>
    </div>
  );
}

function ActionButton({ icon: Icon, children, disabled, onClick }) {
  return (
    <button
      type="button"
      className="dm-action-button"
      disabled={disabled}
      onClick={disabled ? undefined : onClick}
    >
      <Icon size={15} aria-hidden="true" />
      {children}
    </button>
  );
}

export default function DirectorMapStageCard({ item, onAction }) {
  if (!item) return null;
  const disabled = getDefaultActionDisabled(onAction);
  const handleAction = action => {
    if (typeof onAction === 'function') onAction({ action, item });
  };

  return (
    <aside className="dm-section dm-stage-card" aria-live="polite">
      <div className="dm-section-head">
        <div>
          <h2>Карточка выбранного этапа</h2>
          <p>{item.title}</p>
        </div>
      </div>
      <div className="dm-stage-body">
        <div className="dm-stage-title">
          <h3>{item.title}</h3>
          <span className={`dm-pill dm-tone-${item.reviewState === 'needs_review' ? 'warning' : 'success'}`}>
            {item.reviewState === 'needs_review' ? 'проверить связи' : 'связи спокойные'}
          </span>
        </div>

        <div className="dm-kv-grid">
          <DetailCell label="Пакет" value={item.workPackage} />
          <DetailCell label="Зона" value={item.zone} />
          <DetailCell label="Ответственный" value={item.responsible} />
          <DetailCell label="Факт" value={`${item.factProgress}% из ${item.plannedProgress}%`} />
          <DetailCell label="План денег" value={`${formatMoneyShort(item.money.plan)} ₽`} />
          <DetailCell label="Факт денег" value={`${formatMoneyShort(item.money.fact)} ₽`} />
        </div>

        <div className="dm-signal-list">
          {item.signals.length ? item.signals.map(signal => (
            <div key={signal.id} className={`dm-signal dm-tone-${getSignalTone(signal)}`}>
              <b>{signal.title}</b>
              {signal.explanation ? <span>{signal.explanation}</span> : null}
            </div>
          )) : (
            <div className="dm-signal dm-tone-info">
              <b>Критичных сигналов нет</b>
              <span>Этап можно использовать как рабочий ориентир.</span>
            </div>
          )}
        </div>

        <div className="dm-action-row">
          <ActionButton icon={ExternalLink} disabled={disabled} onClick={() => handleAction('open_source')}>
            Открыть источник
          </ActionButton>
          <ActionButton icon={Search} disabled={disabled} onClick={() => handleAction('review_link')}>
            Проверить связь
          </ActionButton>
          <ActionButton icon={Link2} disabled={disabled} onClick={() => handleAction('create_task')}>
            Создать задачу
          </ActionButton>
        </div>
      </div>
    </aside>
  );
}
