import React, { useMemo, useState } from 'react';
import { Banknote, Building2, CalendarDays } from 'lucide-react';
import { formatCompactMoney } from './publicSiteContent';
import {
  calculatePublicProjectFinancing,
  serializePublicProjectFinancing,
} from './publicProjectFinancing';

const formatRange = (min, max) => `${formatCompactMoney(min)} - ${formatCompactMoney(max)}`;

export const PublicProjectFinancing = ({ estimate, selectedFinancing, onApply }) => {
  const [mode, setMode] = useState('mortgage');
  const [mortgage, setMortgage] = useState({ downPaymentPercent: 20, term: 20, annualRate: 20 });
  const [installment, setInstallment] = useState({ downPaymentPercent: 30, term: 12 });
  const values = mode === 'mortgage' ? mortgage : installment;
  const calculation = useMemo(() => calculatePublicProjectFinancing({
    mode,
    estimateMin: estimate?.min,
    estimateMax: estimate?.max,
    ...values,
  }), [estimate?.max, estimate?.min, mode, values]);
  const isSelected = selectedFinancing?.mode === calculation.mode
    && selectedFinancing?.monthlyMin === calculation.monthlyMin
    && selectedFinancing?.monthlyMax === calculation.monthlyMax;

  const updateValue = (field, value) => {
    const setter = mode === 'mortgage' ? setMortgage : setInstallment;
    const limits = field === 'downPaymentPercent'
      ? [0, 90]
      : field === 'annualRate'
        ? [0, 50]
        : mode === 'mortgage'
          ? [1, 30]
          : [2, 36];
    const number = Number(value);
    const nextValue = Math.min(limits[1], Math.max(limits[0], Number.isFinite(number) ? number : limits[0]));
    setter((current) => ({ ...current, [field]: nextValue }));
  };

  const applyFinancing = () => {
    onApply?.(serializePublicProjectFinancing(calculation, formatCompactMoney));
  };

  return (
    <section className="public-project-financing" aria-label="Ипотека и рассрочка">
      <div className="public-project-financing-head">
        <span aria-hidden="true"><Banknote size={18} /></span>
        <div>
          <h4>Ипотека и рассрочка</h4>
          <p>Сравните предварительный ежемесячный платёж</p>
        </div>
      </div>

      <div className="public-project-financing-modes" role="radiogroup" aria-label="Вариант финансирования">
        <button
          type="button"
          role="radio"
          aria-checked={mode === 'mortgage'}
          className={mode === 'mortgage' ? 'active' : ''}
          onClick={() => setMode('mortgage')}
        >
          <Building2 size={16} />
          Ипотека
        </button>
        <button
          type="button"
          role="radio"
          aria-checked={mode === 'installment'}
          className={mode === 'installment' ? 'active' : ''}
          onClick={() => setMode('installment')}
        >
          <CalendarDays size={16} />
          Рассрочка
        </button>
      </div>

      <div className="public-project-financing-fields">
        <label>
          <span>Первоначальный взнос, %</span>
          <input
            type="number"
            min="0"
            max="90"
            step="1"
            aria-label="Первоначальный взнос, %"
            value={values.downPaymentPercent}
            onChange={(event) => updateValue('downPaymentPercent', event.target.value)}
          />
        </label>
        <label>
          <span>{mode === 'mortgage' ? 'Срок, лет' : 'Срок, месяцев'}</span>
          <input
            type="number"
            min={mode === 'mortgage' ? 1 : 2}
            max={mode === 'mortgage' ? 30 : 36}
            step="1"
            aria-label={mode === 'mortgage' ? 'Срок ипотеки, лет' : 'Срок рассрочки, месяцев'}
            value={values.term}
            onChange={(event) => updateValue('term', event.target.value)}
          />
        </label>
        {mode === 'mortgage' && (
          <label>
            <span>Примерная ставка, % годовых</span>
            <input
              type="number"
              min="0"
              max="50"
              step="0.1"
              aria-label="Примерная ставка, % годовых"
              value={values.annualRate}
              onChange={(event) => updateValue('annualRate', event.target.value)}
            />
          </label>
        )}
      </div>

      <div className="public-project-financing-result">
        <span>Предварительный платёж</span>
        <strong>{formatRange(calculation.monthlyMin, calculation.monthlyMax)} <small>в месяц</small></strong>
        <dl>
          <div><dt>Первый взнос</dt><dd>{formatRange(calculation.downPaymentMin, calculation.downPaymentMax)}</dd></div>
          <div><dt>Остаток</dt><dd>{formatRange(calculation.financedMin, calculation.financedMax)}</dd></div>
          <div><dt>Срок</dt><dd>{calculation.termLabel}</dd></div>
        </dl>
      </div>

      <p className="public-project-financing-note">
        {mode === 'mortgage'
          ? 'Это не предложение банка и не обещание одобрения. Ставку и условия клиент указывает для примерного расчёта.'
          : 'Сумма разделена равными частями без учёта возможного удорожания и комиссий. Условия рассрочки подтверждаются отдельно в договоре.'}
      </p>
      <button className="public-project-financing-apply" type="button" onClick={applyFinancing}>
        {mode === 'mortgage' ? 'Добавить ипотеку в заявку' : 'Добавить рассрочку в заявку'}
      </button>
      {isSelected && (
        <p className="public-project-financing-selected">
          {mode === 'mortgage' ? 'Ипотека добавлена в заявку' : 'Рассрочка добавлена в заявку'}
        </p>
      )}
    </section>
  );
};
