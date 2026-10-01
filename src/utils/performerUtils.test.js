import { findUserForStaff, performerMissingRequisites } from './performerUtils';
import { buildPerformerContractHtml } from './contractTemplates';

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

describe('legal entity contractor requisites', () => {
  const companyPerformer = {
    fullName: 'ООО Исполнитель', inn: '1234567890', kpp: '123456789',
    ogrn: '1234567890123', legalAddress: 'Ставрополь', bankAccount: '40702',
    bankName: 'Банк', signatoryName: 'Иванов И.И.', signatoryPosition: 'Директор',
    signatoryBasis: 'Устава', contractType: 'ООО',
  };

  it('requires the legal identity and signer of an ООО', () => {
    expect(performerMissingRequisites({...companyPerformer, signatoryName: ''}, 'ООО'))
      .toContain('ФИО подписанта');
  });

  it('prints the legal signer and registration details', () => {
    const result = buildPerformerContractHtml({
      company: 'ООО Заказчик', performer: companyPerformer,
      contract: {id: 71, contractorType: 'ООО', projectName: 'Лицей'},
    });
    expect(result).toContain('в лице <b>Иванов И.И.</b>');
    expect(result).toContain('<td>КПП</td><td>123456789</td>');
    expect(result).toContain('_____________/Иванов И.И.');
  });
});
