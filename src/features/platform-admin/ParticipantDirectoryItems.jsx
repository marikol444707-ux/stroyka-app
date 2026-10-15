const roles = {
  директор:'Директор',зам_директора:'Заместитель директора',бухгалтер:'Бухгалтер',
  главный_инженер:'Главный инженер',сметчик:'Сметчик',прораб:'Прораб',
  снабженец:'Снабженец',кладовщик:'Кладовщик',мастер:'Мастер',
  субподрядчик:'Субподрядчик',бригадир:'Бригадир',заказчик:'Заказчик',
  технадзор:'Технадзор',стройконтроль:'Стройконтроль',менеджер_crm:'Менеджер CRM',поставщик:'Поставщик',
};
export const membershipStates = {active:'Членство включено',inactive:'Членство отключено',disabled:'Аккаунт или компания отключены',review:'Нужна проверка роли'};
export const invitationStates = {pending:'Срок не истёк',used:'Использовано',expired:'Срок истёк',review:'Нужна проверка'};
const date = value => value?new Date(value).toLocaleDateString('ru-RU'):'Не указана';

export const directoryTabs = {
  participants:{label:'Поставщики',path:'/participants',searchLabel:'Название или ИНН',idKey:'id',empty:'Поставщики этой организации пока не подключены.'},
  memberships:{label:'Сотрудники и роли',path:'/participant-memberships',searchLabel:'Имя или роль',statusLabel:'Состояние членства',states:membershipStates,idKey:'membershipId',empty:'Подтверждённых членств в этой организации пока нет.'},
  invitations:{label:'Приглашения',path:'/participant-invitations',statusLabel:'Состояние приглашения',states:invitationStates,idKey:'inviteId',empty:'Сохранённых приглашений этой организации пока нет.'},
  tickets:{label:'Проблемы и обращения',path:'/participant-tickets',statusLabel:'Статус обращения',idKey:'id',empty:'Обращений этой организации пока нет.'},
};

export function MembershipItem({item}) {
  return <>
    <strong>{item.name||'Имя не указано'}</strong>
    <span>{roles[item.role]||'Неизвестная роль'}</span>
    <span>{membershipStates[item.status]||'Состояние неизвестно'}</span>
    {item.activeRoleCount>1&&<span>Несколько включённых ролей в этой компании — нужно проверить выбор роли.</span>}
    <details><summary>Данные связи</summary><p>Членство: {item.membershipId} · Пользователь: {item.userId}</p></details>
  </>;
}

export function InvitationItem({item}) {
  return <>
    <strong>Приглашение №{item.inviteId}</strong>
    <span>{item.purpose==='supplier_registration'?'Регистрация поставщика':'Членство в компании'}</span>
    <span>{roles[item.role]||'Неизвестная роль'} · {invitationStates[item.status]||'Состояние неизвестно'}</span>
    <span>Действует до: {date(item.expiresAt)}</span>
    <details><summary>Дата создания</summary><p>{date(item.createdAt)}</p></details>
  </>;
}
