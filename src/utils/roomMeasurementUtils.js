import { fmtMeasure } from './measureUtils';

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

export const roomMeasurementMessage = (check) => {
  if (!check) return '';
  const left = Math.max(0, check.limit - check.doneInRoom);
  return check.over > 0
    ? 'По обмеру «' + check.room.name + ' / ' + check.surface + '» доступно ' + fmtMeasure(check.limit, 'м2') + ', уже учтено ' + fmtMeasure(check.doneInRoom, 'м2') + ', вводите ' + fmtMeasure(check.requested, 'м2') + '. Превышение ' + fmtMeasure(check.over, 'м2') + '. Обновите фактический обмер или оформите изменение к смете.'
    : 'Обмер: ' + check.room.name + ' / ' + check.surface + ' — осталось ' + fmtMeasure(left, 'м2') + ', после отправки будет ' + fmtMeasure(check.total, 'м2') + ' из ' + fmtMeasure(check.limit, 'м2') + '.';
};
