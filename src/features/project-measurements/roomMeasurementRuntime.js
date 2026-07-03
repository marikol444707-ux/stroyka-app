import {
  buildRoomMeasurementCheck,
  getRoomNetWall as calculateRoomNetWall,
  roomCompleteness as calculateRoomCompleteness,
  roomMeasurementMessage,
} from '../../utils/roomMeasurementUtils';

export function createRoomMeasurementRuntime({
  C,
  materialNameKey,
  roomDoors,
  roomWindows,
  roomWorks,
  rooms,
}) {
  const getRoomNetWall = (room) => calculateRoomNetWall(room, roomWindows, roomDoors);
  const roomCompleteness = (room) => calculateRoomCompleteness(room, roomWindows, roomDoors, C);
  const roomMeasurementCheck = (projectName, roomId, surface, quantity, unit, description = '') => buildRoomMeasurementCheck({
    projectName,
    roomId,
    surface,
    quantity,
    unit,
    description,
    rooms,
    roomWindows,
    roomDoors,
    roomWorks,
    materialNameKey,
  });

  return {
    getRoomNetWall,
    roomCompleteness,
    roomMeasurementCheck,
    roomMeasurementMessage,
  };
}
