import React from 'react';
import { AlertTriangle, MessageCircle } from 'lucide-react';


const EXPIRING_STATES = new Set(['payment_expiring', 'trial_expiring']);
const EXPIRED_STATES = new Set(['payment_expired', 'trial_expired', 'overdue']);

const dayWord = (value) => {
  const days = Math.abs(Number(value || 0));
  const lastTwo = days % 100;
  if (lastTwo >= 11 && lastTwo <= 14) return 'дней';
  if (days % 10 === 1) return 'день';
  if (days % 10 >= 2 && days % 10 <= 4) return 'дня';
  return 'дней';
};

const formatDate = (value) => {
  if (!value) return '';
  const parsed = new Date(`${String(value).slice(0, 10)}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return '';
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(parsed);
};

export default function SubscriptionExpiryNotice({ company, role, onOpenChat } = {}) {
  const state = company?.billingState || {};
  const status = state.status || '';
  if (role !== 'директор' || (!EXPIRING_STATES.has(status) && !EXPIRED_STATES.has(status))) {
    return null;
  }

  const expired = EXPIRED_STATES.has(status);
  const daysLeft = Math.max(0, Number(state.daysLeft || 0));
  const endDate = company?.plan === 'demo' ? company?.trialUntil : company?.planExpiresAt;
  const formattedEndDate = formatDate(endDate);
  const title = expired
    ? 'Подписка закончилась'
    : daysLeft === 0
      ? 'Подписка заканчивается сегодня'
      : `Подписка закончится через ${daysLeft} ${dayWord(daysLeft)}`;
  const description = expired
    ? 'Продлите тариф, чтобы сохранить доступ к рабочим функциям компании. Свяжитесь с владельцем аккаунта или поддержкой.'
    : `Продлите тариф${formattedEndDate ? ` до ${formattedEndDate}` : ''}, чтобы работа компании не прерывалась. Свяжитесь с владельцем аккаунта или поддержкой.`;

  return (
    <section
      aria-live="polite"
      style={{
        marginTop: '16px',
        marginBottom: '16px',
        padding: '16px 18px',
        borderRadius: '18px',
        border: `1px solid ${expired ? 'rgba(248,113,113,.5)' : 'rgba(251,191,36,.48)'}`,
        background: expired ? 'rgba(127,29,29,.35)' : 'rgba(120,53,15,.34)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '14px',
        flexWrap: 'wrap',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', minWidth: 0 }}>
        <AlertTriangle size={22} color={expired ? '#fca5a5' : '#fbbf24'} aria-hidden="true" />
        <div>
          <div style={{ color: expired ? '#fecaca' : '#fde68a', fontWeight: 900, fontSize: '16px' }}>
            {title}
          </div>
          <div style={{ color: '#cbd5e1', fontSize: '13px', lineHeight: 1.45, marginTop: '4px' }}>
            {description}
          </div>
        </div>
      </div>
      {typeof onOpenChat === 'function' && (
        <button
          type="button"
          onClick={onOpenChat}
          style={{
            border: '1px solid rgba(251,191,36,.42)',
            background: 'rgba(30,41,59,.8)',
            color: '#f8fafc',
            borderRadius: '12px',
            padding: '10px 14px',
            fontWeight: 800,
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '7px',
          }}
        >
          <MessageCircle size={16} aria-hidden="true" /> Открыть чат
        </button>
      )}
    </section>
  );
}
