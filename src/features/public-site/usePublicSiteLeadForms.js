import { useState } from 'react';
import { API } from '../../api';
import {
  PUBLIC_CONSENT_VERSION,
  formatMoney,
  partnerTypes,
} from './publicSiteContent';
import { mergePublicLeadFiles, uploadPublicLeadFiles } from './publicLeadFiles';

export const usePublicSiteLeadForms = ({ result, selectedLeadProject, onLeadFilesChanged }) => {
  const [lead, setLead] = useState({ name: '', phone: '', comment: '' });
  const [leadConsent, setLeadConsent] = useState(false);
  const [leadWebsite, setLeadWebsite] = useState('');
  const [sent, setSent] = useState(false);
  const [leadSending, setLeadSending] = useState(false);
  const [leadError, setLeadError] = useState('');
  const [leadFiles, setLeadFiles] = useState([]);
  const [leadFileError, setLeadFileError] = useState('');
  const [partnerLead, setPartnerLead] = useState({
    type: 'supplier',
    name: '',
    phone: '',
    email: '',
    inn: '',
    region: '',
    specialization: '',
    comment: '',
  });
  const [partnerConsent, setPartnerConsent] = useState(false);
  const [partnerWebsite, setPartnerWebsite] = useState('');
  const [partnerSending, setPartnerSending] = useState(false);
  const [partnerSent, setPartnerSent] = useState(false);
  const [partnerError, setPartnerError] = useState('');

  const chooseLeadFiles = (fileList) => {
    setLeadFileError('');
    try {
      const files = mergePublicLeadFiles(leadFiles, fileList);
      setLeadFiles(files);
      onLeadFilesChanged?.(files.length);
    } catch (error) {
      setLeadFileError(error.message || 'Не удалось выбрать файлы');
    }
  };

  const removeLeadFile = (index) => {
    setLeadFileError('');
    const nextFiles = leadFiles.filter((_, fileIndex) => fileIndex !== index);
    setLeadFiles(nextFiles);
    onLeadFilesChanged?.(nextFiles.length);
  };

  const submitLead = async (event) => {
    event.preventDefault();
    if (leadSending) return;
    setLeadError('');
    if (!leadConsent) {
      setLeadError('Подтвердите согласие на обработку персональных данных.');
      return;
    }
    setLeadSending(true);
    try {
      const attachmentTokens = leadFiles.length
        ? await uploadPublicLeadFiles(leadFiles, API)
        : [];
      const response = await fetch(API + '/site/leads', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...lead,
          source: 'Сайт',
          budget: result.max || result.min || 0,
          page: 'public-site',
          legalSource: typeof window !== 'undefined' ? window.location.href : 'public-site',
          referrer: typeof document !== 'undefined' ? document.referrer : '',
          userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : '',
          submittedAt: new Date().toISOString(),
          utm: typeof window !== 'undefined'
            ? Object.fromEntries(new URLSearchParams(window.location.search).entries())
            : {},
          consentAccepted: leadConsent,
          consentVersion: PUBLIC_CONSENT_VERSION,
          website: leadWebsite,
          calculation: {
            typeLabel: result.typeLabel,
            summary: result.summary,
            rangeText: `${formatMoney(result.min)} - ${formatMoney(result.max)} ₽`,
          },
          selectedProject: selectedLeadProject,
          attachmentTokens,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || 'Не удалось отправить заявку');
      }
      setSent(true);
      setLead({ name: '', phone: '', comment: '' });
      setLeadConsent(false);
      setLeadWebsite('');
      setLeadFiles([]);
      setLeadFileError('');
      onLeadFilesChanged?.(0);
    } catch (error) {
      setLeadError(error.message || 'Не удалось отправить заявку');
    } finally {
      setLeadSending(false);
    }
  };

  const submitPartnerLead = async (event) => {
    event.preventDefault();
    if (partnerSending) return;
    setPartnerError('');
    setPartnerSent(false);
    if (!partnerConsent) {
      setPartnerError('Подтвердите согласие на обработку персональных данных.');
      return;
    }
    setPartnerSending(true);
    try {
      const partnerType = partnerTypes.find((item) => item.value === partnerLead.type) || partnerTypes[0];
      const response = await fetch(API + '/site/leads', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: partnerLead.name || partnerType.label,
          phone: partnerLead.phone,
          email: partnerLead.email,
          comment: [
            'Тип заявки: ' + partnerType.label,
            partnerLead.inn ? 'ИНН: ' + partnerLead.inn : '',
            partnerLead.region ? 'Регион: ' + partnerLead.region : '',
            partnerLead.specialization ? 'Специализация: ' + partnerLead.specialization : '',
            partnerLead.comment ? 'Комментарий: ' + partnerLead.comment : '',
            'Заявка только на проверку. Активный доступ не выдавать автоматически.',
          ].filter(Boolean).join('\n'),
          source: 'Сайт: партнерская заявка',
          budget: 0,
          page: 'public-site-partners',
          legalSource: typeof window !== 'undefined' ? window.location.href : 'public-site-partners',
          referrer: typeof document !== 'undefined' ? document.referrer : '',
          userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : '',
          submittedAt: new Date().toISOString(),
          consentAccepted: partnerConsent,
          consentVersion: PUBLIC_CONSENT_VERSION,
          website: partnerWebsite,
          partnerType: partnerLead.type,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || 'Не удалось отправить заявку');
      }
      setPartnerSent(true);
      setPartnerLead({
        type: 'supplier',
        name: '',
        phone: '',
        email: '',
        inn: '',
        region: '',
        specialization: '',
        comment: '',
      });
      setPartnerConsent(false);
      setPartnerWebsite('');
    } catch (error) {
      setPartnerError(error.message || 'Не удалось отправить заявку');
    } finally {
      setPartnerSending(false);
    }
  };

  return {
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
    leadFileError,
    chooseLeadFiles,
    removeLeadFile,
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
  };
};
