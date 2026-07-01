import { _normalizeUnit, normalizeMeasure, toNum } from './measureUtils';
import { materialLookupText } from './materialMatchUtils';
import {
  journalRoomLinkKey,
  materialControlDescription,
  materialControlMarker,
  roomControlDescription,
  roomControlMarker,
} from './aiControlDescriptionUtils';

const ROOM_RELEVANT_JOURNAL_WORDS = [
  'стен',
  'потол',
  'пол',
  'окн',
  'двер',
  'откос',
  'штукатур',
  'шпатлев',
  'шпаклев',
  'окрас',
  'облицов',
  'плит',
  'стяж',
  'линолеум',
  'плинтус',
  'кабель',
  'розет',
  'выключ',
  'светильник',
];

export const buildMaterialControlTaskDescriptorsForProject = ({
  projectName,
  reason = 'Фоновая проверка материалов',
  materialControlSummaryForProject,
  materialNormControlSummaryForProject,
  materialNameKey = materialLookupText,
  materialAliasCandidates = () => [],
  hasActiveEstimator = () => false,
}) => {
  if (!projectName) return [];
  const summary = materialControlSummaryForProject(projectName);
  const normSummary = materialNormControlSummaryForProject(projectName);
  const mk = (kind, row, title, assignedRole, actionType, extraPayload = {}) => {
    const marker = materialControlMarker(kind, projectName, row.name, row.unit);
    return {
      marker,
      projectName,
      title,
      description: materialControlDescription(kind, projectName, row, reason),
      assignedRole,
      actionLabel: 'Открыть материалы',
      actionPayload: {
        type: actionType,
        marker,
        projectName,
        materialName: row.name || '',
        unit: row.unit || '',
        reason,
        ...extraPayload,
      },
    };
  };
  const descriptors = [];
  summary.toBuyRows
    .filter(row => row.toBuy > 0 && materialNameKey(row.name))
    .sort((a, b) => b.toBuy - a.toBuy)
    .slice(0, 5)
    .forEach(row => descriptors.push(mk(
      'purchase',
      row,
      'Докупить материал: ' + projectName + ' — ' + (row.name || 'материал'),
      'снабженец',
      'material_purchase_review',
    )));
  summary.outsideRows
    .filter(row => materialNameKey(row.name))
    .sort((a, b) => (b.supplied + b.used) - (a.supplied + a.used))
    .slice(0, 3)
    .forEach(row => {
      const candidate = materialAliasCandidates(projectName, row)[0] || null;
      const rowWithCandidate = candidate ? { ...row, aliasCandidate: candidate } : row;
      descriptors.push(mk(
        'outside',
        rowWithCandidate,
        candidate
          ? 'Проверить сопоставление материала: ' + projectName + ' — ' + (row.name || 'материал') + ' → ' + candidate.name
          : 'Материал вне сметы: ' + projectName + ' — ' + (row.name || 'материал'),
        hasActiveEstimator() ? 'сметчик' : 'директор',
        'material_outside_estimate_review',
        candidate ? {
          aliasCandidate: {
            projectName,
            aliasName: row.aliases?.[0] || row.name || '',
            canonicalName: candidate.name || '',
            canonicalUnit: candidate.unit || row.unit || '',
            score: candidate.score || 0,
          },
        } : {},
      ));
    });
  summary.usedWithoutIssueRows
    .filter(row => row.usedWithoutIssue > 0 && materialNameKey(row.name))
    .sort((a, b) => b.usedWithoutIssue - a.usedWithoutIssue)
    .slice(0, 3)
    .forEach(row => descriptors.push(mk(
      'writeoff',
      row,
      'Проверить списание сверх выдачи: ' + projectName + ' — ' + (row.name || 'материал'),
      'прораб',
      'material_writeoff_review',
    )));
  normSummary.overRows
    .filter(row => row.overQty > 0 && materialNameKey(row.name))
    .sort((a, b) => b.overQty - a.overQty)
    .slice(0, 3)
    .forEach(row => descriptors.push(mk(
      'norm_over',
      row,
      'Проверить перерасход по норме: ' + projectName + ' — ' + (row.name || 'материал'),
      'прораб',
      'material_norm_over_review',
    )));
  normSummary.withoutNormRows
    .filter(row => row.withoutNormQty > 0 && materialNameKey(row.name))
    .sort((a, b) => b.withoutNormQty - a.withoutNormQty)
    .slice(0, 3)
    .forEach(row => descriptors.push(mk(
      'without_norm',
      row,
      'Добавить норму или проверить списание: ' + projectName + ' — ' + (row.name || 'материал'),
      hasActiveEstimator() ? 'сметчик' : 'директор',
      'material_without_norm_review',
    )));
  return descriptors.slice(0, 15);
};

export const buildMaterialControlSignatureForProject = ({
  projectName,
  materialControlSummaryForProject,
  materialNormControlSummaryForProject,
}) => {
  const summary = materialControlSummaryForProject(projectName);
  const normSummary = materialNormControlSummaryForProject(projectName);
  const qtySum = (rows, field) => Math.round(rows.reduce((sum, row) => sum + toNum(row[field]), 0) * 1000) / 1000;
  return [
    summary.toBuyRows.length,
    qtySum(summary.toBuyRows, 'toBuy'),
    summary.outsideRows.length,
    summary.usedWithoutIssueRows.length,
    qtySum(summary.usedWithoutIssueRows, 'usedWithoutIssue'),
    normSummary.totalOverRows,
    normSummary.totalOverRecords,
    normSummary.totalWithoutNormRows,
    normSummary.totalWithoutNormRecords,
  ].join('|');
};

export const buildRoomRelevantJournalRows = ({
  projectName,
  workJournal = [],
  materialNameKey = materialLookupText,
}) => (workJournal || [])
  .filter(row => (row.project || '') === projectName && (row.status || '') !== 'Отклонено')
  .filter(row => {
    const unit = _normalizeUnit(normalizeMeasure(toNum(row.quantity), row.unit).unit || row.unit || '');
    const text = materialNameKey([row.description, row.sectionName, row.comment].filter(Boolean).join(' '));
    return ['м2', 'м', 'шт'].includes(unit) || ROOM_RELEVANT_JOURNAL_WORDS.some(word => text.includes(word));
  });

export const buildUnlinkedRoomJournalRows = ({
  projectName,
  roomWorks = [],
  workJournal = [],
  materialNameKey = materialLookupText,
}) => {
  const linked = new Set((roomWorks || [])
    .filter(row => (row.project || '') === projectName)
    .map(journalRoomLinkKey));
  return buildRoomRelevantJournalRows({ projectName, workJournal, materialNameKey })
    .filter(row => !linked.has(journalRoomLinkKey(row)));
};

export const buildRoomControlTaskDescriptorsForProject = ({
  projectName,
  reason = 'Фоновая проверка помещений',
  rooms = [],
  roomWorks = [],
  workJournal = [],
  roomCompleteness,
  materialNameKey = materialLookupText,
}) => {
  if (!projectName) return [];
  const projectRooms = (rooms || []).filter(room => room.project === projectName);
  const descriptors = [];
  const badRooms = projectRooms
    .map(room => ({ room, check: roomCompleteness(room) }))
    .filter(item => item.check.status !== 'Обмер полный');
  if (projectRooms.length === 0) {
    const marker = roomControlMarker('measurements', projectName);
    descriptors.push({
      marker,
      projectName,
      title: 'Добавить помещения и обмеры: ' + projectName,
      description: 'Автоконтроль помещений после события: ' + reason + '.\nОбъект: ' + projectName + '.\n\nВ объекте нет помещений. Без помещений система не сможет сверять фактические работы со стенами, полом, потолком, окнами, дверями и откосами.\n\nЧто сделать: открыть `Проект / Обмеры` или `Помещения`, загрузить проект/обмер или создать помещения вручную.',
      assignedRole: 'прораб',
      actionLabel: 'Открыть обмеры',
      actionPayload: { type: 'room_measurement_review', marker, projectName, reason },
    });
  } else if (badRooms.length > 0) {
    const marker = roomControlMarker('measurements', projectName);
    descriptors.push({
      marker,
      projectName,
      title: 'Уточнить обмеры: ' + projectName + ' — ' + badRooms.length + ' помещ.',
      description: roomControlDescription('measurements', projectName, badRooms, reason),
      assignedRole: 'прораб',
      actionLabel: 'Открыть помещения',
      actionPayload: { type: 'room_measurement_review', marker, projectName, reason, count: badRooms.length },
    });
  }

  const unlinked = buildUnlinkedRoomJournalRows({ projectName, roomWorks, workJournal, materialNameKey });
  if (projectRooms.length > 0 && unlinked.length > 0) {
    const marker = roomControlMarker('work_links', projectName);
    descriptors.push({
      marker,
      projectName,
      title: 'Привязать ЖПР к помещениям: ' + projectName + ' — ' + unlinked.length + ' зап.',
      description: roomControlDescription('work_links', projectName, unlinked, reason),
      assignedRole: 'прораб',
      actionLabel: 'Открыть ЖПР',
      actionPayload: { type: 'work_room_link_review', marker, projectName, reason, count: unlinked.length },
    });
  }
  return descriptors;
};

export const buildRoomControlSignatureForProject = ({
  projectName,
  rooms = [],
  roomWorks = [],
  workJournal = [],
  roomCompleteness,
  materialNameKey = materialLookupText,
}) => {
  const projectRooms = (rooms || []).filter(room => room.project === projectName);
  const badRooms = projectRooms.map(room => roomCompleteness(room)).filter(check => check.status !== 'Обмер полный');
  const unlinked = buildUnlinkedRoomJournalRows({ projectName, roomWorks, workJournal, materialNameKey });
  return [
    projectRooms.length,
    badRooms.length,
    badRooms.map(check => check.status + ':' + check.issues.join(',')).join(';'),
    unlinked.length,
    unlinked.slice(0, 40).map(row => row.id || journalRoomLinkKey(row)).join(','),
  ].join('|');
};
