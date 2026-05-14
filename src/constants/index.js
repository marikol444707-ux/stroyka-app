// Константы приложения СтройКа

export const API = window.location.hostname==='localhost'?'http://localhost:8001':'http://192.168.1.82:8001';
export const daysInMonth = Array.from({length: 31}, (_, i) => String(i + 1));

export const requestPushPermission = async () => {
  if (!('Notification' in window)) return false;
  if (Notification.permission === 'granted') return true;
  const permission = await Notification.requestPermission();
  return permission === 'granted';
};

export const sendPushNotification = (title, body) => {
  if (Notification.permission === 'granted') {
    new Notification('🏗️ ' + title, { body, icon: '/favicon.ico' });
  }
};

export const doPrint = (content) => {
  const iframe = document.createElement('iframe');
  iframe.style.cssText = 'position:fixed;top:0;left:0;width:0;height:0;border:none;';
  document.body.appendChild(iframe);
  const doc = iframe.contentDocument || iframe.contentWindow.document;
  doc.open();
  doc.write('<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{font-family:Arial,sans-serif;padding:30px;font-size:12px;color:#000}table{width:100%;border-collapse:collapse;margin:15px 0}td,th{border:1px solid #333;padding:6px;text-align:left}th{background:#f5f5f5}h2{text-align:center;margin-bottom:5px}p{margin:4px 0}.signatures{display:flex;justify-content:space-between;margin-top:40px}.sig{text-align:center;width:30%}.sig-line{border-top:1px solid #333;margin-top:30px;padding-top:5px}@media print{body{padding:15px}}</style></head><body>'+content+'</body></html>');
  doc.close();
  setTimeout(() => { iframe.contentWindow.focus(); iframe.contentWindow.print(); setTimeout(() => document.body.removeChild(iframe), 2000); }, 300);
};

export const generateQR = (text) => {
  const size = 150;
  const url = `https://api.qrserver.com/v1/create-qr-code/?size=${size}x${size}&data=${encodeURIComponent(text)}`;
  return url;
};

export const PreviewModal = ({content, title, onClose}) => (
  <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.6)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:3000}}>
    <div style={{backgroundColor:'white',borderRadius:'16px',width:'820px',maxWidth:'95%',maxHeight:'90vh',display:'flex',flexDirection:'column',boxShadow:'0 20px 60px rgba(0,0,0,0.2)'}}>
      <div style={{padding:'16px 24px',borderBottom:'1px solid #e5e7eb',display:'flex',justifyContent:'space-between',alignItems:'center',backgroundColor:'#f9fafb',borderRadius:'16px 16px 0 0'}}>
        <b style={{color:'#111827',fontSize:'15px'}}>{'📄 '+title}</b>
        <div style={{display:'flex',gap:'10px'}}>
          <button onClick={()=>doPrint(content)} style={{padding:'8px 20px',background:'linear-gradient(135deg,#f97316,#ea580c)',color:'white',border:'none',borderRadius:'8px',cursor:'pointer',fontSize:'14px',fontWeight:'600',display:'flex',alignItems:'center',gap:'6px'}}><Printer size={14}/>Распечатать</button>
          <button onClick={onClose} style={{padding:'8px 16px',backgroundColor:'#6b7280',color:'white',border:'none',borderRadius:'8px',cursor:'pointer',display:'flex',alignItems:'center',gap:'6px'}}><X size={14}/>Закрыть</button>
        </div>
      </div>
      <div style={{flex:1,overflowY:'auto',padding:'24px',backgroundColor:'white',borderRadius:'0 0 16px 16px'}}>
        <div style={{fontFamily:'Arial',fontSize:'12px',lineHeight:'1.6'}} dangerouslySetInnerHTML={{__html:content}}/>
      </div>
    </div>
  </div>
);

export const ROLES = {
  директор: ['dashboard','projects','clients','warehouse','staff','users','pricelists','suppliers','accounting','analytics','personnel','crm','activitylog','companychat','estimates','weather','settings'],
  зам_директора: ['dashboard','projects','clients','warehouse','staff','pricelists','suppliers','analytics','accounting','personnel','crm','activitylog','companychat','estimates','weather','settings'],
  главный_инженер: ['dashboard','projects','warehouse','staff','companychat','estimates','weather'],
  прораб: ['dashboard','projects','warehouse','suppliers','staff','companychat','weather'],
  кладовщик: ['warehouse','suppliers','companychat'],
  бухгалтер: ['dashboard','accounting','personnel','companychat','settings'],
  снабженец: ['warehouse','suppliers','companychat'],
  стройконтроль: ['projects','companychat'],
  менеджер_crm: ['crm','companychat'],
  сметчик: ['estimates','projects','accounting','companychat'],
  субподрядчик: ['works','materials','history','documents','companychat'],
  мастер: ['works','materials','history','documents','companychat'],
  технадзор: ['projects','companychat'],
  заказчик: ['client_view'],
  поставщик: ['supplier_view'],
};

export const ROLE_LABELS = {
  директор:'👑 Директор', зам_директора:'🏢 Зам. директора',
  главный_инженер:'⚙️ Гл. инженер', прораб:'🔨 Прораб',
  кладовщик:'📦 Кладовщик', бухгалтер:'💰 Бухгалтер',
  снабженец:'🚛 Снабженец', стройконтроль:'🔍 Стройконтроль',
  менеджер_crm:'🤝 Менеджер CRM', мастер:'👷 Мастер',
  сметчик:'📊 Сметчик', субподрядчик:'🔩 Субподрядчик',
  технадзор:'🔎 Технадзор', заказчик:'🏠 Заказчик', поставщик:'🏭 Поставщик',
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

export const EXPENSE_CATEGORIES = [
  {id:'materials',label:'Материалы',color:'#f97316'},
  {id:'works',label:'Работы/Бригады',color:'#10b981'},
  {id:'delivery',label:'Доставка материалов',color:'#3b82f6'},
  {id:'fuel',label:'Топливо и транспорт',color:'#06b6d4'},
  {id:'equipment',label:'Аренда техники',color:'#8b5cf6'},
  {id:'tools',label:'Инструменты и оснастка',color:'#7c3aed'},
  {id:'docs',label:'Документация и разрешения',color:'#0891b2'},
  {id:'electricity',label:'Электроэнергия на объекте',color:'#f59e0b'},
  {id:'utilities',label:'Коммунальные расходы',color:'#84cc16'},
  {id:'food',label:'Питание рабочих',color:'#f43f5e'},
  {id:'accountable',label:'Подотчётные расходы',color:'#d97706'},
  {id:'unexpected',label:'Непредвиденные затраты',color:'#ef4444'},
  {id:'other',label:'Прочее',color:'#6b7280'},
];

export const MATERIAL_CATEGORIES = [
  'Сыпучие материалы','Бетон и растворы','Кирпич и блоки','Металлопрокат и арматура','Опалубка и леса',
  'Кровельные материалы','Фасадные материалы','Утеплители и изоляция','Гидроизоляция','Пароизоляция',
  'Окна ПВХ','Окна алюминиевые','Двери входные','Двери межкомнатные','Ворота и шлагбаумы',
  'Штукатурные смеси','Шпаклёвки','Краски и лаки','Обои','Плитка и керамогранит',
  'Ламинат и паркет','Линолеум и ковролин','Натяжные потолки','Гипсокартон и профиль','Панели и вагонка',
  'Кабель и провод','Розетки и выключатели','Щиты и автоматы','Светильники и лампы','Кабель-каналы и трубы',
  'Трубы водоснабжения','Трубы канализации','Фитинги и соединения','Смесители и краны','Унитазы и раковины',
  'Ванны и душевые','Счётчики воды','Насосы',
  'Котлы и горелки','Радиаторы','Трубы отопления','Тёплый пол','Арматура отопления',
  'Вентиляционные трубы','Решётки и диффузоры','Вентиляторы','Кондиционеры',
  'Видеонаблюдение','Домофоны','Интернет и TV кабель','Охранная сигнализация','Пожарная сигнализация',
  'Электроинструмент','Ручной инструмент','Строительное оборудование','СИЗ',
  'Крепёж','Герметики и пены','Клеи и мастики','Спецодежда','Прочее'
];

export const UNITS = ['шт','мешок','м','м2','м3','кг','т','л','рулон','лист','упак','компл','пог.м','ящик','бутылка','банка','труба','секция','пара','набор','пачка','флакон','ведро','бухта'];
export const PROJECT_TABS = ['Общее','Этапы','График','Смета','Журнал','Помещения','Чек-листы','Непредвиденные','Наряды','Материалы','Чат','Финансы','Предписания','Журнал ТБ'];
export const CRM_STAGES = ['Новый','Переговоры','КП отправлено','Договор','Отказ'];
export const SUPPLIER_CATEGORIES = [
  'Сыпучие и бетон','Кровельные','Металл и арматура','Отделочные','Сантехника','Электрика',
  'Инструмент','Утеплители','Окна и двери','Отопление','Вентиляция','Слаботочные системы','Прочее'
];
export const SURFACES = ['Стены','Потолок','Пол','Откосы оконные','Откосы дверные','Фасад','Цоколь'];
export const TOOL_STATUSES = ['На складе','На объекте','У мастера','На ремонте','Списан'];
export const VAT_OPTIONS = ['Без НДС','С НДС 22%'];
export const CEILING_TYPES = ['Простой','Гипсокартон','Натяжной','Армстронг','Реечный'];
export const WALL_MATERIALS = ['Штукатурка','Плитка','Гипсокартон','Панели','Обои','Покраска'];
export const FLOOR_MATERIALS = ['Стяжка','Плитка','Ламинат','Паркет','Линолеум','Наливной пол'];
export const WINDOW_TYPES = ['ПВХ','Алюминий','Дерево','Комбинированное'];
export const DOOR_TYPES = ['Деревянная','ПВХ','Алюминий','Металлическая','МДФ'];
export const DOOR_PURPOSES = ['Входная','Межкомнатная','Балконная','Техническая'];
export const REVEAL_MATERIALS = ['Штукатурка','Гипсокартон','ПВХ панели','Алюминиевые','Деревянные','Плитка','МДФ','Камень'];
export const PAYMENT_TYPES = ['Наличный расчёт','Безналичный расчёт','Перевод на карту','Аванс наличный','Аванс безналичный'];
export const WEATHER_CONDITIONS = ['Ясно','Облачно','Пасмурно','Дождь','Снег','Гроза','Туман','Ветер'];
export const STAGE_STATUSES = ['Не начат','В работе','Завершён','Заморожен','Просрочен'];
export const CHECKLIST_TEMPLATES = {
  'Приёмка фундамента': ['Проверка геометрии фундамента','Проверка армирования','Проверка гидроизоляции','Проверка отметок','Фото фиксация','Подпись прораба','Подпись технадзора','Акт освидетельствования'],
  'Приёмка стен': ['Проверка вертикальности','Проверка горизонтальности','Проверка перевязки','Проверка швов','Фото фиксация','Подпись прораба','Подпись технадзора','Акт освидетельствования'],
  'Приёмка кровли': ['Проверка стропил','Проверка обрешётки','Проверка кровельного материала','Проверка примыканий','Фото фиксация','Подпись прораба'],
  'Приёмка электрики': ['Проверка кабельных трасс','Проверка щита','Проверка заземления','Замер сопротивления изоляции','Фото фиксация','Акт'],
  'Приёмка сантехники': ['Проверка трубопроводов','Опрессовка','Проверка канализации','Фото фиксация','Акт'],
  'Сдача объекта': ['Уборка объекта','Все работы завершены','Документация готова','Ключи переданы','Подпись заказчика','Фото объекта'],
};

export const TB_INSTRUCTIONS = {
  'Вводный инструктаж': '<h3>ВВОДНЫЙ ИНСТРУКТАЖ ПО ОХРАНЕ ТРУДА</h3><p>1. Работник обязан соблюдать правила внутреннего трудового распорядка.</p><p>2. Запрещается появляться на рабочем месте в состоянии алкогольного опьянения.</p><p>3. Работник обязан использовать средства индивидуальной защиты (СИЗ).</p><p>4. При несчастном случае немедленно сообщить руководителю.</p><p>5. Запрещается работать неисправным инструментом.</p>',
  'Первичный инструктаж': '<h3>ПЕРВИЧНЫЙ ИНСТРУКТАЖ НА РАБОЧЕМ МЕСТЕ</h3><p>1. Ознакомление с рабочим местом и оборудованием.</p><p>2. Порядок подготовки рабочего места к работе.</p><p>3. Безопасные методы и приёмы выполнения работ.</p><p>4. Средства индивидуальной защиты на данном рабочем месте.</p><p>5. Действия при возникновении аварийной ситуации.</p>',
  'Пожарная безопасность': '<h3>ИНСТРУКТАЖ ПО ПОЖАРНОЙ БЕЗОПАСНОСТИ</h3><p>1. Запрещается курить в неотведённых местах.</p><p>2. Знать расположение первичных средств пожаротушения.</p><p>3. При пожаре вызвать 101, сообщить руководителю, эвакуироваться.</p>',
  'Электробезопасность': '<h3>ИНСТРУКТАЖ ПО ЭЛЕКТРОБЕЗОПАСНОСТИ</h3><p>1. Запрещается работать с неисправной электропроводкой.</p><p>2. При поражении током — отключить питание, вызвать скорую (103).</p><p>3. Использовать диэлектрические перчатки при работе с электрооборудованием.</p>',
  'Работы на высоте': '<h3>ИНСТРУКТАЖ ПО РАБОТАМ НА ВЫСОТЕ</h3><p>1. Работы на высоте от 1.8м выполнять со страховочной привязью.</p><p>2. Запрещается работать на высоте при скорости ветра более 15 м/с.</p><p>3. Запрещается работать на высоте в одиночку.</p>',
  'Повторный инструктаж': '<h3>ПОВТОРНЫЙ ИНСТРУКТАЖ ПО ОХРАНЕ ТРУДА</h3><p>1. Повторение основных правил охраны труда на объекте.</p><p>2. Разбор нарушений, допущенных за прошедший период.</p><p>3. Порядок действий при несчастном случае или аварии.</p>',
};

