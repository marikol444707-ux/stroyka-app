import React from 'react';
import { CheckCircle2, MapPin, TriangleAlert } from 'lucide-react';
import {
  getPublicPlotCheckSummary,
  publicPlotCheckOptions,
} from './publicPlotCheck';

const PlotSelect = ({ label, field, value, options, onChange }) => (
  <label className="public-field">
    <span>{label}</span>
    <select value={value} onChange={(event) => onChange(field, event.target.value)}>
      {Object.entries(options).map(([optionValue, optionLabel]) => (
        <option value={optionValue} key={optionValue}>{optionLabel}</option>
      ))}
    </select>
  </label>
);

export const PublicPlotCheckPanel = ({ value, onChange }) => {
  const summary = getPublicPlotCheckSummary(value);

  return (
    <section className="public-plot-check" aria-label="Предварительная проверка участка">
      <div className="public-plot-check-head">
        <span><MapPin size={18} /></span>
        <div>
          <h3>Что известно об участке</h3>
          <p>Ответы не меняют цену автоматически, но помогут инженеру проверить посадку дома и подготовительные работы.</p>
        </div>
        <strong>{summary.completed} из {summary.total}</strong>
      </div>

      <div className="public-plot-check-grid">
        <PlotSelect label="Статус участка" field="status" value={value.status} options={publicPlotCheckOptions.status} onChange={onChange} />
        <PlotSelect label="Подъезд для техники" field="access" value={value.access} options={publicPlotCheckOptions.access} onChange={onChange} />
        <PlotSelect label="Рельеф" field="relief" value={value.relief} options={publicPlotCheckOptions.relief} onChange={onChange} />
        <PlotSelect label="Коммуникации" field="utilities" value={value.utilities} options={publicPlotCheckOptions.utilities} onChange={onChange} />
      </div>

      <div className="public-plot-surveys">
        <label>
          <input type="checkbox" checked={value.geologyReady} onChange={(event) => onChange('geologyReady', event.target.checked)} />
          Геология уже есть
        </label>
        <label>
          <input type="checkbox" checked={value.geodesyReady} onChange={(event) => onChange('geodesyReady', event.target.checked)} />
          Геодезия уже есть
        </label>
      </div>

      <div className={summary.ready ? 'public-plot-check-result ready' : 'public-plot-check-result'}>
        {summary.ready ? <CheckCircle2 size={17} /> : <TriangleAlert size={17} />}
        <p>
          <b>{summary.ready ? 'Основные данные указаны.' : 'До точной сметы нужно проверить:'}</b>{' '}
          {!summary.ready && summary.reviewItems.join(', ')}
        </p>
      </div>
    </section>
  );
};
