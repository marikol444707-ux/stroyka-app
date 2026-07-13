import React, { useState } from 'react';
import { Check, X } from 'lucide-react';

const clampCount = (value, fallback) => {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(12, Math.max(0, parsed));
};

export const PublicLayoutRequestEditor = ({
  projectTitle,
  initialSpaces = 3,
  initialBathrooms = 1,
  initialGarage = false,
  initialNotes = '',
  isHouseLayout = true,
  onApply,
  onCancel,
}) => {
  const [spaces, setSpaces] = useState(initialSpaces);
  const [bathrooms, setBathrooms] = useState(initialBathrooms);
  const [garage, setGarage] = useState(initialGarage);
  const [notes, setNotes] = useState(initialNotes);

  return (
    <section
      id="public-layout-request-editor"
      className="public-layout-request-editor"
      aria-label="Пожелания к планировке"
    >
      <div className="public-layout-request-head">
        <div>
          <strong>Пожелания к планировке</strong>
          <small>{projectTitle}</small>
        </div>
        <button type="button" onClick={onCancel} aria-label="Закрыть параметры планировки" title="Закрыть">
          <X size={18} />
        </button>
      </div>

      <div className="public-layout-request-grid">
        <label>
          <span>{isHouseLayout ? 'Спален' : 'Комнат / зон'}</span>
          <input
            type="number"
            min="0"
            max="12"
            value={spaces}
            onChange={(event) => setSpaces(clampCount(event.target.value, initialSpaces))}
          />
        </label>
        <label>
          <span>Санузлов</span>
          <input
            type="number"
            min="0"
            max="12"
            value={bathrooms}
            onChange={(event) => setBathrooms(clampCount(event.target.value, initialBathrooms))}
          />
        </label>
      </div>

      {isHouseLayout && (
        <label className="public-layout-request-check">
          <input type="checkbox" checked={garage} onChange={(event) => setGarage(event.target.checked)} />
          <span>Нужен гараж</span>
        </label>
      )}

      <label className="public-layout-request-notes">
        <span>Дополнительные пожелания</span>
        <textarea
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          maxLength={800}
          placeholder="Например: постирочная, кабинет, выход на террасу"
        />
      </label>

      <div className="public-layout-request-actions">
        <button className="public-secondary dark" type="button" onClick={onCancel}>Отмена</button>
        <button
          className="public-primary"
          type="button"
          onClick={() => onApply({ spaces, bathrooms, garage: isHouseLayout && garage, notes: notes.trim() })}
        >
          <Check size={17} />
          Добавить в заявку
        </button>
      </div>
    </section>
  );
};
