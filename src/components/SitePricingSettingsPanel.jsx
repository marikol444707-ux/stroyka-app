import React, { useEffect, useMemo, useState } from 'react';
import { Check, RefreshCw } from 'lucide-react';

const groupOrder = [
  'house_wall',
  'house_package',
  'repair_object',
  'repair_condition',
  'repair_level',
  'material_mode',
  'commerce_type',
  'commerce_level',
  'reconstruction_scope',
];

export default function SitePricingSettingsPanel({ API, C, card, inp, btnO, btnG }) {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(false);
  const [savingId, setSavingId] = useState(null);
  const [message, setMessage] = useState('');

  const loadRules = async () => {
    setLoading(true);
    setMessage('');
    try {
      const response = await fetch(API + '/site-price-rules');
      const data = await response.json().catch(() => []);
      if (!response.ok) throw new Error(data.detail || 'Не удалось загрузить прайс сайта');
      setRules(Array.isArray(data) ? data : []);
    } catch (error) {
      setMessage(error.message || 'Не удалось загрузить прайс сайта');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRules();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const groupedRules = useMemo(() => {
    const byGroup = new Map();
    rules.forEach((rule) => {
      const key = rule.groupKey || 'other';
      if (!byGroup.has(key)) byGroup.set(key, []);
      byGroup.get(key).push(rule);
    });
    return [...byGroup.entries()].sort((a, b) => {
      const ai = groupOrder.indexOf(a[0]);
      const bi = groupOrder.indexOf(b[0]);
      return (ai < 0 ? 999 : ai) - (bi < 0 ? 999 : bi);
    });
  }, [rules]);

  const updateLocalRule = (id, patch) => {
    setRules((current) => current.map((rule) => (rule.id === id ? { ...rule, ...patch } : rule)));
  };

  const saveRule = async (rule) => {
    setSavingId(rule.id);
    setMessage('');
    try {
      const response = await fetch(API + '/site-price-rules/' + rule.id, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          label: rule.label,
          value: rule.value,
          unit: rule.unit,
          enabled: rule.enabled !== false,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Не удалось сохранить правило');
      updateLocalRule(rule.id, data);
      setMessage('Прайс сайта обновлен');
    } catch (error) {
      setMessage(error.message || 'Не удалось сохранить правило');
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div>
      <div style={{ ...card, padding: '18px', marginBottom: '14px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div>
            <h3 style={{ color: C.text, margin: '0 0 6px', fontSize: '16px' }}>Прайс публичного калькулятора</h3>
            <p style={{ color: C.textSec, margin: 0, fontSize: '12px' }}>
              Эти ставки использует сайт в предварительном расчете. Итоговая цена всё равно фиксируется сметой и договором.
            </p>
          </div>
          <button onClick={loadRules} style={btnG} disabled={loading}>
            <RefreshCw size={14} />{loading ? 'Обновляю' : 'Обновить'}
          </button>
        </div>
        {message && (
          <p style={{ color: message.includes('Не удалось') ? C.danger : C.success, margin: '12px 0 0', fontSize: '12px', fontWeight: 700 }}>
            {message}
          </p>
        )}
      </div>

      {groupedRules.map(([groupKey, items]) => (
        <section key={groupKey} style={{ ...card, padding: '14px', marginBottom: '12px' }}>
          <h4 style={{ color: C.accent, margin: '0 0 10px', fontSize: '13px' }}>
            {items[0]?.groupLabel || groupKey}
          </h4>
          <div style={{ display: 'grid', gap: '8px' }}>
            {items.map((rule) => (
              <div
                key={rule.id}
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                  gap: '8px',
                  alignItems: 'center',
                  padding: '8px',
                  border: '1px solid ' + C.border,
                  borderRadius: '8px',
                  background: C.bg,
                }}
              >
                <input
                  value={rule.label || ''}
                  onChange={(event) => updateLocalRule(rule.id, { label: event.target.value })}
                  style={{ ...inp, marginBottom: 0, fontSize: '12px' }}
                />
                <input
                  type="number"
                  step="any"
                  value={rule.value ?? ''}
                  onChange={(event) => updateLocalRule(rule.id, { value: event.target.value })}
                  style={{ ...inp, marginBottom: 0, fontSize: '12px' }}
                />
                <input
                  value={rule.unit || ''}
                  onChange={(event) => updateLocalRule(rule.id, { unit: event.target.value })}
                  placeholder={rule.valueType === 'multiplier' ? 'коэф.' : 'ед.'}
                  style={{ ...inp, marginBottom: 0, fontSize: '12px' }}
                />
                <label style={{ color: C.textSec, fontSize: '12px', display: 'flex', gap: '6px', alignItems: 'center' }}>
                  <input
                    type="checkbox"
                    checked={rule.enabled !== false}
                    onChange={(event) => updateLocalRule(rule.id, { enabled: event.target.checked })}
                  />
                  Активно
                </label>
                <button onClick={() => saveRule(rule)} disabled={savingId === rule.id} style={{ ...btnO, padding: '7px 10px', fontSize: '12px' }}>
                  <Check size={13} />{savingId === rule.id ? 'Сохр.' : 'Сохранить'}
                </button>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
