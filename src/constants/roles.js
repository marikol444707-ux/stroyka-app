export const ROLES = {
  директор: ['dashboard','projects','clients','warehouse','staff','pricelists','supply','accounting','analytics','personnel','crm','activitylog','companychat','estimates','settings','myexpenses'],
  зам_директора: ['dashboard','projects','clients','warehouse','staff','pricelists','supply','analytics','accounting','personnel','crm','activitylog','companychat','estimates','settings','myexpenses'],
  главный_инженер: ['dashboard','projects','warehouse','staff','companychat','estimates','weather','myexpenses'],
  прораб: ['projects','supply','companychat','weather','myexpenses'],
  кладовщик: ['warehouse','supply','companychat','myexpenses'],
  бухгалтер: ['dashboard','accounting','supply','personnel','companychat','settings','myexpenses'],
  снабженец: ['warehouse','supply','companychat','myexpenses'],
  стройконтроль: ['projects','companychat','myexpenses'],
  менеджер_crm: ['crm','companychat'],
  сметчик: ['estimates','projects','accounting','companychat'],
  субподрядчик: ['works','materials','history','documents','supply','companychat','myexpenses'],
  мастер: ['works','materials','history','documents','supply','companychat','myexpenses'],
  технадзор: ['projects','companychat','myexpenses'],
  заказчик: ['client_view'],
  поставщик: ['supplier_view'],
  system_owner: ['system_view'],
};

export const ROLE_LABELS = {
  директор:'👑 Директор', зам_директора:'🏢 Зам. директора',
  главный_инженер:'⚙️ Гл. инженер', прораб:'🔨 Прораб',
  кладовщик:'📦 Кладовщик', бухгалтер:'💰 Бухгалтер',
  снабженец:'🚛 Снабженец', стройконтроль:'🔍 Стройконтроль',
  менеджер_crm:'🤝 Менеджер CRM', мастер:'👷 Мастер',
  сметчик:'📊 Сметчик', субподрядчик:'🔩 Субподрядчик',
  технадзор:'🔎 Технадзор', заказчик:'🏠 Заказчик', поставщик:'🏭 Поставщик',
  system_owner:'⚙️ Владелец платформы',
};

export const ROLE_GROUPS = [
  {key:'руководство',label:'Руководство',roles:['директор','зам_директора'],color:'#f97316'},
  {key:'инженер',label:'Инженерный состав',roles:['главный_инженер','прораб'],color:'#8b5cf6'},
  {key:'контроль',label:'Стройконтроль',roles:['стройконтроль'],color:'#06b6d4'},
  {key:'рабочие',label:'Мастера',roles:['мастер'],color:'#ec4899'},
  {key:'субподрядчики',label:'Субподрядчики',roles:['субподрядчик'],color:'#f59e0b'},
  {key:'снабжение',label:'Снабжение',roles:['кладовщик','снабженец'],color:'#10b981'},
  {key:'бухгалтерия',label:'Бухгалтерия',roles:['бухгалтер'],color:'#6b7280'},
  {key:'сметчики',label:'Сметчики',roles:['сметчик'],color:'#3b82f6'},
  {key:'crm',label:'CRM',roles:['менеджер_crm'],color:'#8b5cf6'},
  {key:'технадзор',label:'Технадзор',roles:['технадзор'],color:'#ef4444'},
  {key:'заказчики',label:'Заказчики',roles:['заказчик'],color:'#06b6d4'},
  {key:'поставщики',label:'Поставщики',roles:['поставщик'],color:'#f59e0b'},
];
