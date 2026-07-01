import { _normalizeUnit, fmtMeasure, normalizeMeasure, toNum } from './measureUtils';

export const calcWindowArea = (windowRow) => Number(windowRow.width || 0) * Number(windowRow.height || 0);

export const calcWindowReveals = (windowRow) => {
  const depth = Number(windowRow.reveal_depth || windowRow.revealDepth || 0) / 100;
  const width = Number(windowRow.width || 0);
  const height = Number(windowRow.height || 0);
  return Math.round((width * depth + height * depth * 2) * 100) / 100;
};

export const calcDoorArea = (doorRow) => Number(doorRow.width || 0) * Number(doorRow.height || 0);

export const calcDoorReveals = (doorRow) => {
  const depth = Number(doorRow.reveal_depth || doorRow.revealDepth || 0) / 100;
  const width = Number(doorRow.width || 0);
  const height = Number(doorRow.height || 0);
  return Math.round((width * depth + height * depth * 2) * 100) / 100;
};

export const roomIdOf = (row) => Number(row?.roomId ?? row?.room_id ?? 0);

export const getRoomNetWall = (room, roomWindows = [], roomDoors = []) => {
  const wins = roomWindows.filter(w => Number(w.room_id) === Number(room.id));
  const doors = roomDoors.filter(d => Number(d.room_id) === Number(room.id));
  const winArea = wins.reduce((s, w) => s + calcWindowArea(w), 0);
  const doorArea = doors.reduce((s, d) => s + calcDoorArea(d), 0);
  return Math.max(0, Math.round((toNum(room.wallArea) - winArea - doorArea) * 100) / 100);
};

export const roomCompleteness = (room, roomWindows = [], roomDoors = [], colors = {}) => {
  const wins = roomWindows.filter(w => Number(w.room_id) === Number(room.id));
  const doors = roomDoors.filter(d => Number(d.room_id) === Number(room.id));
  const issues = [];
  if (toNum(room.floorArea) <= 0) issues.push('нет площади пола');
  if (toNum(room.wallArea) <= 0) issues.push('нет площади стен');
  if (toNum(room.ceilingArea) <= 0) issues.push('нет площади потолка');
  if (toNum(room.height) <= 0) issues.push('нет высоты');
  wins.forEach(w => {
    const name = w.name || 'окно';
    if (toNum(w.width) <= 0 || toNum(w.height) <= 0) issues.push(name + ': нет размера');
    if (toNum(w.reveal_depth || w.revealDepth) <= 0) issues.push(name + ': нет глубины откоса');
  });
  doors.forEach(d => {
    const name = d.name || 'дверь';
    if (toNum(d.width) <= 0 || toNum(d.height) <= 0) issues.push(name + ': нет размера');
    if (toNum(d.reveal_depth || d.revealDepth) <= 0) issues.push(name + ': нет глубины откоса');
  });
  const grossWall = toNum(room.wallArea);
  const openingsArea = wins.reduce((s, w) => s + calcWindowArea(w), 0) + doors.reduce((s, d) => s + calcDoorArea(d), 0);
  if (grossWall > 0 && openingsArea > grossWall) issues.push('проёмы больше площади стен');
  const hasBaseMiss = issues.some(x => x.startsWith('нет площади') || x === 'нет высоты');
  if (!issues.length) return {status: 'Обмер полный', issues, color: colors.success, bg: colors.successLight, border: colors.successBorder};
  if (hasBaseMiss) return {status: 'Не хватает данных', issues, color: colors.warning, bg: colors.warningLight, border: colors.warningBorder};
  return {status: 'Проверить проёмы', issues, color: colors.info, bg: colors.infoLight, border: colors.infoBorder};
};

export const getRoomWindowRevealsTotal = (room, roomWindows = []) =>
  roomWindows.filter(w => Number(w.room_id) === Number(room.id)).reduce((s, w) => s + calcWindowReveals(w), 0);

export const getRoomDoorRevealsTotal = (room, roomDoors = []) =>
  roomDoors.filter(d => Number(d.room_id) === Number(room.id)).reduce((s, d) => s + calcDoorReveals(d), 0);

export const roomSurfaceArea = (room, surface = 'Стены', roomWindows = [], roomDoors = []) => {
  if (!room) return 0;
  if (surface === 'Потолок') return toNum(room.ceilingArea);
  if (surface === 'Пол') return toNum(room.floorArea);
  if (surface === 'Откосы оконные') return getRoomWindowRevealsTotal(room, roomWindows);
  if (surface === 'Откосы дверные') return getRoomDoorRevealsTotal(room, roomDoors);
  if (surface === 'Стены') return getRoomNetWall(room, roomWindows, roomDoors);
  return 0;
};

export const buildRoomMeasurementCheck = ({
  projectName,
  roomId,
  surface,
  quantity,
  unit,
  description = '',
  rooms = [],
  roomWindows = [],
  roomDoors = [],
  roomWorks = [],
  materialNameKey = (value) => String(value || '').trim().toLowerCase(),
}) => {
  if (!roomId) return null;
  const room = rooms.find(r => Number(r.id) === Number(roomId));
  if (!room) return null;
  const normalized = normalizeMeasure(quantity, unit);
  if (_normalizeUnit(normalized.unit) !== 'м2') return null;
  const normalizedSurface = surface || 'Стены';
  const limit = roomSurfaceArea(room, normalizedSurface, roomWindows, roomDoors);
  if (limit <= 0) return null;
  const workKey = materialNameKey(description);
  const doneInRoom = (roomWorks || [])
    .filter(w => Number(roomIdOf(w)) === Number(room.id))
    .filter(w => (w.project || '') === (projectName || ''))
    .filter(w => (w.surface || 'Стены') === normalizedSurface)
    .filter(w => (w.status || '') !== 'Отклонено')
    .filter(w => !workKey || materialNameKey(w.description) === workKey)
    .reduce((sum, w) => {
      const n = normalizeMeasure(w.quantity, w.unit);
      return _normalizeUnit(n.unit) === 'м2' ? sum + n.qty : sum;
    }, 0);
  const requested = Math.max(0, normalized.qty);
  const total = doneInRoom + requested;
  return {room, surface: normalizedSurface, limit, doneInRoom, requested, total, over: Math.max(0, total - limit), pct: Math.round(total / limit * 100)};
};

export const roomMeasurementMessage = (check) => {
  if (!check) return '';
  const left = Math.max(0, check.limit - check.doneInRoom);
  return check.over > 0
    ? 'По обмеру «' + check.room.name + ' / ' + check.surface + '» доступно ' + fmtMeasure(check.limit, 'м2') + ', уже учтено ' + fmtMeasure(check.doneInRoom, 'м2') + ', вводите ' + fmtMeasure(check.requested, 'м2') + '. Превышение ' + fmtMeasure(check.over, 'м2') + '. Обновите фактический обмер или оформите изменение к смете.'
    : 'Обмер: ' + check.room.name + ' / ' + check.surface + ' — осталось ' + fmtMeasure(left, 'м2') + ', после отправки будет ' + fmtMeasure(check.total, 'м2') + ' из ' + fmtMeasure(check.limit, 'м2') + '.';
};
