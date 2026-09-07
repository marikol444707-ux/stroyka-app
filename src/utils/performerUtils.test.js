import { findUserForStaff } from './performerUtils';

describe('findUserForStaff', () => {
  it('prefers the exact company membership link over legacy name matching', () => {
    const result = findUserForStaff(
      {
        id: 5,
        name: 'Директор',
        accessUserId: 42,
        accessEmail: 'director@example.test',
        accessRole: 'директор',
      },
      [
        { id: 9, name: 'Директор', email: 'wrong@example.test' },
        { id: 42, name: 'Основной аккаунт', email: 'director@example.test' },
      ],
    );

    expect(result.id).toBe(42);
    expect(result.email).toBe('director@example.test');
  });

  it('returns exact access data even when the global users list is unavailable', () => {
    expect(findUserForStaff({
      id: 5,
      accessUserId: 42,
      accessEmail: 'director@example.test',
      accessRole: 'директор',
      accessAssignedProjects: ['Объект'],
      accessAssignedPackages: ['Раздел'],
    }, [])).toEqual({
      id: 42,
      email: 'director@example.test',
      role: 'директор',
      assignedProjects: ['Объект'],
      assignedPackages: ['Раздел'],
    });
  });
});
