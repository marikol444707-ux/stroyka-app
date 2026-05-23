import React, { useState, useEffect, useRef } from 'react';
import LoginPage from './pages/LoginPage';
import { LayoutDashboard, FolderKanban, Users, Package, Truck, DollarSign, UserCheck, Tag, MessageSquare, ScrollText, BarChart3, Handshake, ChevronRight, Bell, Search, LogOut, Plus, Edit2, Trash2, Eye, Printer, Check, X, ChevronDown, ChevronUp, ArrowLeft, Copy, Download, Upload, MapPin, CheckCircle, FileText, Briefcase, Archive, CloudSun, QrCode, Calculator, Settings, Scan, CreditCard, Bot, Camera } from 'lucide-react';

const API = window.location.hostname==='localhost'?'http://localhost:8001':'';
const daysInMonth = Array.from({length: 31}, (_, i) => String(i + 1));

const requestPushPermission = async () => {
  if (!('Notification' in window)) return false;
  if (Notification.permission === 'granted') return true;
  const permission = await Notification.requestPermission();
  return permission === 'granted';
};

const sendPushNotification = (title, body) => {
  if (Notification.permission === 'granted') {
    new Notification('🏗️ ' + title, { body, icon: '/favicon.ico' });
  }
};

const doPrint = (content) => {
  const iframe = document.createElement('iframe');
  iframe.style.cssText = 'position:fixed;top:0;left:0;width:0;height:0;border:none;';
  document.body.appendChild(iframe);
  const doc = iframe.contentDocument || iframe.contentWindow.document;
  doc.open();
  doc.write('<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{font-family:Arial,sans-serif;padding:30px;font-size:12px;color:#000}table{width:100%;border-collapse:collapse;margin:15px 0}td,th{border:1px solid #333;padding:6px;text-align:left}th{background:#f5f5f5}h2{text-align:center;margin-bottom:5px}p{margin:4px 0}.signatures{display:flex;justify-content:space-between;margin-top:40px}.sig{text-align:center;width:30%}.sig-line{border-top:1px solid #333;margin-top:30px;padding-top:5px}@media print{body{padding:15px}}</style></head><body>'+content+'</body></html>');
  doc.close();
  setTimeout(() => { iframe.contentWindow.focus(); iframe.contentWindow.print(); setTimeout(() => document.body.removeChild(iframe), 2000); }, 300);
};

const generateQR = (text) => {
  const size = 150;
  const url = `https://api.qrserver.com/v1/create-qr-code/?size=${size}x${size}&data=${encodeURIComponent(text)}`;
  return url;
};

const PreviewModal = ({content, title, onClose}) => (
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

const ROLES = {
  директор: ['dashboard','projects','clients','warehouse','staff','pricelists','suppliers','accounting','analytics','personnel','crm','activitylog','companychat','estimates','weather','settings'],
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

const ROLE_LABELS = {
  директор:'👑 Директор', зам_директора:'🏢 Зам. директора',
  главный_инженер:'⚙️ Гл. инженер', прораб:'🔨 Прораб',
  кладовщик:'📦 Кладовщик', бухгалтер:'💰 Бухгалтер',
  снабженец:'🚛 Снабженец', стройконтроль:'🔍 Стройконтроль',
  менеджер_crm:'🤝 Менеджер CRM', мастер:'👷 Мастер',
  сметчик:'📊 Сметчик', субподрядчик:'🔩 Субподрядчик',
  технадзор:'🔎 Технадзор', заказчик:'🏠 Заказчик', поставщик:'🏭 Поставщик',
};

const ROLE_GROUPS = [
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

const EXPENSE_CATEGORIES = [
  {id:'materials',label:'Материалы',color:'#f97316'},
  {id:'works',label:'Работы/Бригады',color:'#10b981'},
  {id:'delivery',label:'Доставка материалов',color:'#3b82f6'},
  {id:'fuel',label:'Топливо и транспорт',color:'#06b6d4'},
  {id:'equipment',label:'Аренда техники',color:'#8b5cf6'},
  {id:'tools',label:'Инструменты и оснастка',color:'#475569'},
  {id:'docs',label:'Документация и разрешения',color:'#0891b2'},
  {id:'electricity',label:'Электроэнергия на объекте',color:'#f59e0b'},
  {id:'utilities',label:'Коммунальные расходы',color:'#84cc16'},
  {id:'food',label:'Питание рабочих',color:'#f43f5e'},
  {id:'accountable',label:'Подотчётные расходы',color:'#d97706'},
  {id:'unexpected',label:'Непредвиденные затраты',color:'#ef4444'},
  {id:'other',label:'Прочее',color:'#6b7280'},
];

const MATERIAL_CATEGORIES = [
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

const UNITS = ['шт','мешок','м','м2','м3','кг','т','л','рулон','лист','упак','компл','пог.м','ящик','бутылка','банка','труба','секция','пара','набор','пачка','флакон','ведро','бухта'];
const CRM_STAGES = ['Новый','Переговоры','КП отправлено','Договор','Отказ'];
const SUPPLIER_CATEGORIES = [
  'Сыпучие и бетон','Кровельные','Металл и арматура','Отделочные','Сантехника','Электрика',
  'Инструмент','Утеплители','Окна и двери','Отопление','Вентиляция','Слаботочные системы','Прочее'
];
const SURFACES = ['Стены','Потолок','Пол','Откосы оконные','Откосы дверные','Фасад','Цоколь'];
const TOOL_STATUSES = ['На складе','На объекте','У мастера','На ремонте','Списан'];
const VAT_OPTIONS = ['Без НДС','С НДС 22%'];
const WINDOW_TYPES = ['ПВХ','Алюминий','Дерево','Комбинированное'];
const DOOR_TYPES = ['Деревянная','ПВХ','Алюминий','Металлическая','МДФ'];
const DOOR_PURPOSES = ['Входная','Межкомнатная','Балконная','Техническая'];
const REVEAL_MATERIALS = ['Штукатурка','Гипсокартон','ПВХ панели','Алюминиевые','Деревянные','Плитка','МДФ','Камень'];
const PAYMENT_TYPES = ['Наличный расчёт','Безналичный расчёт','Перевод на карту','Аванс наличный','Аванс безналичный'];
const WEATHER_CONDITIONS = ['Ясно','Облачно','Пасмурно','Дождь','Снег','Гроза','Туман','Ветер'];
const STAGE_STATUSES = ['Не начат','В работе','Завершён','Заморожен','Просрочен'];
const CHECKLIST_TEMPLATES = {
  'Приёмка фундамента': ['Проверка геометрии фундамента','Проверка армирования','Проверка гидроизоляции','Проверка отметок','Фото фиксация','Подпись прораба','Подпись технадзора','Акт освидетельствования'],
  'Приёмка стен': ['Проверка вертикальности','Проверка горизонтальности','Проверка перевязки','Проверка швов','Фото фиксация','Подпись прораба','Подпись технадзора','Акт освидетельствования'],
  'Приёмка кровли': ['Проверка стропил','Проверка обрешётки','Проверка кровельного материала','Проверка примыканий','Фото фиксация','Подпись прораба'],
  'Приёмка электрики': ['Проверка кабельных трасс','Проверка щита','Проверка заземления','Замер сопротивления изоляции','Фото фиксация','Акт'],
  'Приёмка сантехники': ['Проверка трубопроводов','Опрессовка','Проверка канализации','Фото фиксация','Акт'],
  'Сдача объекта': ['Уборка объекта','Все работы завершены','Документация готова','Ключи переданы','Подпись заказчика','Фото объекта'],
};

// Типы инструктажа по ГОСТ 12.0.004-2015
const TB_TYPES_GOST = [
  {value:'Вводный инструктаж',freq:'однократно при приёме',legal:'ГОСТ 12.0.004-2015 п.2.1.2'},
  {value:'Первичный инструктаж на рабочем месте',freq:'однократно перед началом работ',legal:'ГОСТ 12.0.004-2015 п.2.1.4'},
  {value:'Повторный инструктаж',freq:'не реже 1 раза в 6 месяцев (опасные работы — 3 мес)',legal:'ГОСТ 12.0.004-2015 п.2.1.5'},
  {value:'Внеплановый инструктаж',freq:'при изменении технологии, после ЧП, после длительного перерыва',legal:'ГОСТ 12.0.004-2015 п.2.1.6'},
  {value:'Целевой инструктаж',freq:'при разовых работах, ликвидации ЧС',legal:'ГОСТ 12.0.004-2015 п.2.1.7'},
];

const TB_INSTRUCTIONS = {
  'Вводный инструктаж': '<h3>ВВОДНЫЙ ИНСТРУКТАЖ ПО ОХРАНЕ ТРУДА</h3><p>1. Работник обязан соблюдать правила внутреннего трудового распорядка.</p><p>2. Запрещается появляться на рабочем месте в состоянии алкогольного опьянения.</p><p>3. Работник обязан использовать средства индивидуальной защиты (СИЗ).</p><p>4. При несчастном случае немедленно сообщить руководителю.</p><p>5. Запрещается работать неисправным инструментом.</p>',
  'Первичный инструктаж на рабочем месте': '<h3>ПЕРВИЧНЫЙ ИНСТРУКТАЖ НА РАБОЧЕМ МЕСТЕ</h3><p>1. Ознакомление с рабочим местом и оборудованием.</p><p>2. Порядок подготовки рабочего места к работе.</p><p>3. Безопасные методы и приёмы выполнения работ.</p><p>4. Средства индивидуальной защиты на данном рабочем месте.</p><p>5. Действия при возникновении аварийной ситуации.</p>',
  'Повторный инструктаж': '<h3>ПОВТОРНЫЙ ИНСТРУКТАЖ ПО ОХРАНЕ ТРУДА</h3><p>1. Повторение основных правил охраны труда на объекте.</p><p>2. Разбор нарушений, допущенных за прошедший период.</p><p>3. Порядок действий при несчастном случае или аварии.</p>',
  'Внеплановый инструктаж': '<h3>ВНЕПЛАНОВЫЙ ИНСТРУКТАЖ</h3><p>Проводится при изменении технологии, после несчастных случаев, при перерыве в работе более 30 дней (для опасных производств — 60 дней).</p>',
  'Целевой инструктаж': '<h3>ЦЕЛЕВОЙ ИНСТРУКТАЖ</h3><p>Проводится при разовых работах не по специальности, ликвидации последствий аварий, стихийных бедствий, проведении работ повышенной опасности.</p>',
  'Пожарная безопасность': '<h3>ИНСТРУКТАЖ ПО ПОЖАРНОЙ БЕЗОПАСНОСТИ</h3><p>1. Запрещается курить в неотведённых местах.</p><p>2. Знать расположение первичных средств пожаротушения.</p><p>3. При пожаре вызвать 101, сообщить руководителю, эвакуироваться.</p>',
  'Электробезопасность': '<h3>ИНСТРУКТАЖ ПО ЭЛЕКТРОБЕЗОПАСНОСТИ</h3><p>1. Запрещается работать с неисправной электропроводкой.</p><p>2. При поражении током — отключить питание, вызвать скорую (103).</p><p>3. Использовать диэлектрические перчатки при работе с электрооборудованием.</p>',
  'Работы на высоте': '<h3>ИНСТРУКТАЖ ПО РАБОТАМ НА ВЫСОТЕ</h3><p>1. Работы на высоте от 1.8м выполнять со страховочной привязью.</p><p>2. Запрещается работать на высоте при скорости ветра более 15 м/с.</p><p>3. Запрещается работать на высоте в одиночку.</p>',
};

const CONTRACTS = {
  'ГПХ': (company, master, contract) => {
    const req = company||{};
    const companyName = typeof company === 'string' ? company : (req.fullName||req.shortName||'_____');
    const director = typeof company === 'object' ? (req.directorName||'_____') : '_____';
    const basis = typeof company === 'object' ? (req.basis||'Устава') : 'Устава';
    return '<h2 style="text-align:center">ДОГОВОР ПОДРЯДА № '+contract.contractNumber+'</h2><p style="text-align:center">г. _____________ «____» _____________ 2026 г.</p><p><b>'+companyName+'</b> (Заказчик) в лице <b>'+director+'</b>, действующего на основании <b>'+basis+'</b>, и гр. <b>'+master.fullName+'</b>, ИНН: <b>'+master.inn+'</b> (Исполнитель), заключили настоящий Договор о нижеследующем:</p><h3>1. ПРЕДМЕТ ДОГОВОРА</h3><p>1.1. Исполнитель обязуется выполнить строительно-монтажные работы на объекте: <b>'+contract.project+'</b>.</p><p>1.2. Сроки выполнения работ: с <b>'+contract.startDate+'</b> по <b>'+contract.endDate+'</b>.</p><p>1.3. Конкретный перечень и объём работ определяется согласно прайс-листу.</p><h3>2. ПРАВА И ОБЯЗАННОСТИ СТОРОН</h3><p>2.1. Исполнитель обязан: выполнять работы качественно и в срок; соблюдать технику безопасности; устранять недостатки за свой счёт.</p><p>2.2. Заказчик обязан: обеспечить доступ на объект; принять работы по акту; произвести оплату в установленные сроки.</p><h3>3. СТОИМОСТЬ И ПОРЯДОК ОПЛАТЫ</h3><p>3.1. Стоимость работ определяется на основании актов выполненных работ.</p><p>3.2. Аванс составляет <b>30%</b> от стоимости работ.</p><p>3.3. Окончательный расчёт производится в течение <b>10 рабочих дней</b> после подписания акта.</p><p>3.4. Удержание <b>10%</b> гарантийного резерва до истечения гарантийного срока.</p><h3>4. ОТВЕТСТВЕННОСТЬ СТОРОН</h3><p>4.1. За нарушение сроков выполнения работ — неустойка <b>0,5% от стоимости работ за каждый день просрочки</b>.</p><p>4.2. За нарушение сроков оплаты — пени <b>0,1% за каждый день просрочки</b>.</p><h3>5. ГАРАНТИЙНЫЕ ОБЯЗАТЕЛЬСТВА</h3><p>5.1. Гарантийный срок на выполненные работы составляет <b>36 месяцев</b> с момента подписания акта.</p><h3>6. ФОРС-МАЖОР</h3><p>6.1. Стороны освобождаются от ответственности при наступлении обстоятельств непреодолимой силы (стихийные бедствия, военные действия, решения органов власти).</p><p>6.2. Сторона, для которой наступили форс-мажорные обстоятельства, обязана уведомить другую сторону в течение <b>3 рабочих дней</b>.</p><h3>7. РАЗРЕШЕНИЕ СПОРОВ</h3><p>7.1. Все споры решаются путём переговоров.</p><p>7.2. При недостижении согласия — в судебном порядке по месту нахождения Заказчика.</p><h3>8. ПРОЧИЕ УСЛОВИЯ</h3><p>8.1. Договор вступает в силу с момента подписания и действует до полного исполнения обязательств.</p><p>8.2. Все изменения и дополнения оформляются письменным соглашением.</p><table><tr><th>ЗАКАЗЧИК</th><th>ИСПОЛНИТЕЛЬ</th></tr><tr><td>'+companyName+'</td><td>'+master.fullName+'</td></tr><tr><td>ИНН: '+(typeof company==='object'?req.inn||'_______':'_______')+'</td><td>ИНН: '+master.inn+'</td></tr><tr><td>Р/с: '+(typeof company==='object'?req.rs||'_______':'_______')+'</td><td>Р/с: '+master.bankAccount+'</td></tr><tr><td>Банк: '+(typeof company==='object'?req.bankName||'_______':'_______')+'</td><td>Банк: '+master.bankName+'</td></tr><tr><td style="padding-top:40px">_____________/'+director+'</td><td style="padding-top:40px">_____________/'+master.fullName+'</td></tr></table>';
  },
  'Самозанятый': (company, master, contract) => {
    const companyName = typeof company === 'string' ? company : ((company||{}).fullName||(company||{}).shortName||'_____');
    const director = typeof company === 'object' ? ((company||{}).directorName||'_____') : '_____';
    return '<h2 style="text-align:center">ДОГОВОР ОКАЗАНИЯ УСЛУГ № '+contract.contractNumber+'</h2><p style="text-align:center">г. _____________ «____» _____________ 2026 г.</p><p><b>'+companyName+'</b> (Заказчик) и гр. <b>'+master.fullName+'</b>, ИНН: <b>'+master.inn+'</b>, являющийся плательщиком налога на профессиональный доход (Исполнитель), заключили настоящий Договор:</p><h3>1. ПРЕДМЕТ ДОГОВОРА</h3><p>1.1. Объект: <b>'+contract.project+'</b>. Сроки: '+contract.startDate+' — '+contract.endDate+'</p><h3>2. СТАТУС ИСПОЛНИТЕЛЯ</h3><p>2.1. Исполнитель является плательщиком НПД согласно ФЗ №422-ФЗ от 27.11.2018.</p><p>2.2. Исполнитель обязуется выдать чек через приложение "Мой налог".</p><h3>3. СТОИМОСТЬ И ПОРЯДОК ОПЛАТЫ</h3><p>3.1. Аванс <b>30%</b>. Остаток <b>70%</b> в течение <b>10 рабочих дней</b> после подписания акта.</p><h3>4. ОТВЕТСТВЕННОСТЬ</h3><p>4.1. Неустойка <b>0,5%/день</b>. Гарантия <b>12 месяцев</b>.</p><h3>5. ФОРС-МАЖОР</h3><p>5.1. Стороны освобождаются от ответственности при наступлении обстоятельств непреодолимой силы.</p><table><tr><th>ЗАКАЗЧИК</th><th>ИСПОЛНИТЕЛЬ (Самозанятый)</th></tr><tr><td>'+companyName+'</td><td>'+master.fullName+'</td></tr><tr><td>ИНН: '+(typeof company==='object'?((company||{}).inn||'_______'):'_______')+'</td><td>ИНН: '+master.inn+'</td></tr><tr><td style="padding-top:40px">_____________/'+director+'</td><td style="padding-top:40px">_____________/'+master.fullName+'</td></tr></table>';
  },
  'ИП': (company, master, contract) => {
    const companyName = typeof company === 'string' ? company : ((company||{}).fullName||(company||{}).shortName||'_____');
    const director = typeof company === 'object' ? ((company||{}).directorName||'_____') : '_____';
    return '<h2 style="text-align:center">ДОГОВОР ПОДРЯДА № '+contract.contractNumber+'</h2><p style="text-align:center">г. _____________ «____» _____________ 2026 г.</p><p>ИП <b>'+master.fullName+'</b>, ОГРНИП: <b>'+(master.ogrnip||'_____')+'</b>, ИНН: <b>'+master.inn+'</b> (Подрядчик) и <b>'+companyName+'</b> (Заказчик) заключили настоящий Договор:</p><h3>1. ПРЕДМЕТ ДОГОВОРА</h3><p>1.1. Объект: <b>'+contract.project+'</b>. Сроки: '+contract.startDate+' — '+contract.endDate+'</p><h3>2. СТОИМОСТЬ И ПОРЯДОК ОПЛАТЫ</h3><p>2.1. Аванс <b>30%</b>. Остаток <b>70%</b> в течение <b>10 рабочих дней</b>.</p><h3>3. ОТВЕТСТВЕННОСТЬ</h3><p>3.1. Неустойка <b>0,5%/день</b>. Гарантия <b>36 месяцев</b>.</p><h3>4. ФОРС-МАЖОР</h3><p>4.1. Стороны освобождаются от ответственности при наступлении обстоятельств непреодолимой силы.</p><h3>5. РАЗРЕШЕНИЕ СПОРОВ</h3><p>5.1. Споры решаются путём переговоров, при недостижении согласия — в арбитражном суде.</p><table><tr><th>ЗАКАЗЧИК</th><th>ПОДРЯДЧИК (ИП)</th></tr><tr><td>'+companyName+'</td><td>ИП '+master.fullName+'</td></tr><tr><td>ИНН: '+(typeof company==='object'?((company||{}).inn||'_______'):'_______')+'</td><td>ОГРНИП: '+(master.ogrnip||'_____')+'</td></tr><tr><td>Р/с: '+(typeof company==='object'?((company||{}).rs||'_______'):'_______')+'</td><td>Р/с: '+master.bankAccount+'</td></tr><tr><td style="padding-top:40px">_____________/'+director+'</td><td style="padding-top:40px">_____________/'+master.fullName+'</td></tr></table>';
  },
};

const PD_CONSENT_TEXT = (master) => '<h2 style="text-align:center">СОГЛАСИЕ НА ОБРАБОТКУ ПЕРСОНАЛЬНЫХ ДАННЫХ</h2><p>Я, <b>'+(master.fullName||'_________________________')+'</b>, паспорт: <b>'+(master.passport||'_________________________')+'</b>, ИНН: <b>'+(master.inn||'_________')+'</b>, в соответствии с Федеральным законом от 27.07.2006 № 152-ФЗ «О персональных данных», даю согласие на обработку моих персональных данных.</p><h3>Перечень персональных данных:</h3><p>— ФИО; — Паспортные данные; — ИНН; — Банковские реквизиты; — Номер телефона; — Специализация.</p><h3>Цели обработки:</h3><p>— Заключение и исполнение договоров; — Формирование актов; — Начисление вознаграждения; — Кадровый учёт.</p><h3>Срок действия:</h3><p>В течение всего срока сотрудничества и 5 лет после его окончания.</p><div class="signatures"><div class="sig"><div class="sig-line">Дата: _______________</div></div><div class="sig"><div class="sig-line">Подпись: _______________<br/>'+(master.fullName||'_________________________')+'</div></div></div>';

const POSITION_INSTRUCTIONS = {
  директор: '<h2 style="text-align:center">ДОЛЖНОСТНАЯ ИНСТРУКЦИЯ ДИРЕКТОРА</h2><p><b>1. ОБЩИЕ ПОЛОЖЕНИЯ</b></p><p>1.1. Директор является единоличным исполнительным органом. Стаж руководящей работы не менее 5 лет.</p><p><b>2. ОБЯЗАННОСТИ</b></p><p>2.1. Руководит производственно-хозяйственной деятельностью. 2.2. Обеспечивает выполнение обязательств. 2.3. Контролирует финансовую деятельность. 2.4. Подписывает договоры и финансовые документы.</p><p><b>3. ОТВЕТСТВЕННОСТЬ</b></p><p>3.1. Полная ответственность за результаты деятельности.</p>',
  прораб: '<h2 style="text-align:center">ДОЛЖНОСТНАЯ ИНСТРУКЦИЯ ПРОРАБА</h2><p><b>1. ОБЩИЕ ПОЛОЖЕНИЯ</b></p><p>1.1. Подчиняется директору. Высшее строительное образование, стаж не менее 3 лет.</p><p><b>2. ОБЯЗАННОСТИ</b></p><p>2.1. Руководит строительно-монтажными работами. 2.2. Ведёт журнал производства работ. 2.3. Контролирует качество работ. 2.4. Проводит инструктажи по ОТ.</p><p><b>3. ОТВЕТСТВЕННОСТЬ</b></p><p>3.1. Персональная ответственность за качество работ.</p>',
  мастер: '<h2 style="text-align:center">ДОЛЖНОСТНАЯ ИНСТРУКЦИЯ МАСТЕРА</h2><p><b>1. ОБЩИЕ ПОЛОЖЕНИЯ</b></p><p>1.1. Подчиняется прорабу. Опыт не менее 3 лет.</p><p><b>2. ОБЯЗАННОСТИ</b></p><p>2.1. Руководит работой бригады. 2.2. Ведёт учёт выполненных работ. 2.3. Обеспечивает соблюдение ОТ.</p><p><b>3. ОТВЕТСТВЕННОСТЬ</b></p><p>3.1. За качество работ бригады. 3.2. Полная материальная ответственность.</p>',
  бухгалтер: '<h2 style="text-align:center">ДОЛЖНОСТНАЯ ИНСТРУКЦИЯ БУХГАЛТЕРА</h2><p><b>1. ОБЩИЕ ПОЛОЖЕНИЯ</b></p><p>1.1. Подчиняется директору. Высшее экономическое образование.</p><p><b>2. ОБЯЗАННОСТИ</b></p><p>2.1. Ведёт бухгалтерский учёт. 2.2. Расчёты с работниками. 2.3. Контролирует расходование средств.</p><p><b>3. ОТВЕТСТВЕННОСТЬ</b></p><p>3.1. За достоверность отчётности.</p>',
  кладовщик: '<h2 style="text-align:center">ДОЛЖНОСТНАЯ ИНСТРУКЦИЯ КЛАДОВЩИКА</h2><p><b>1. ОБЩИЕ ПОЛОЖЕНИЯ</b></p><p>1.1. Подчиняется директору. Договор о полной материальной ответственности.</p><p><b>2. ОБЯЗАННОСТИ</b></p><p>2.1. Приём, хранение и отпуск материалов. 2.2. Ведёт учёт движения в системе. 2.3. Выдаёт материалы под подпись.</p><p><b>3. ОТВЕТСТВЕННОСТЬ</b></p><p>3.1. Полная материальная ответственность за все ТМЦ.</p>',
  снабженец: '<h2 style="text-align:center">ДОЛЖНОСТНАЯ ИНСТРУКЦИЯ СНАБЖЕНЦА</h2><p><b>1. ОБЩИЕ ПОЛОЖЕНИЯ</b></p><p>1.1. Подчиняется директору.</p><p><b>2. ОБЯЗАННОСТИ</b></p><p>2.1. Организует снабжение объектов. 2.2. Запрашивает и анализирует КП. 2.3. Контролирует поставки.</p><p><b>3. ОТВЕТСТВЕННОСТЬ</b></p><p>3.1. За своевременное обеспечение объектов.</p>',
  стройконтроль: '<h2 style="text-align:center">ДОЛЖНОСТНАЯ ИНСТРУКЦИЯ СТРОЙКОНТРОЛЯ</h2><p><b>1. ОБЩИЕ ПОЛОЖЕНИЯ</b></p><p>1.1. Назначается заказчиком согласно ст. 53 ГрК РФ.</p><p><b>2. ОБЯЗАННОСТИ</b></p><p>2.1. Контроль качества СМР. 2.2. Выдача предписаний. 2.3. Участие в освидетельствовании скрытых работ.</p><p><b>3. ПРАВА</b></p><p>3.1. Требовать устранения нарушений.</p>',
  сметчик: '<h2 style="text-align:center">ДОЛЖНОСТНАЯ ИНСТРУКЦИЯ СМЕТЧИКА</h2><p><b>1. ОБЩИЕ ПОЛОЖЕНИЯ</b></p><p>1.1. Подчиняется директору. Высшее строительное или экономическое образование.</p><p><b>2. ОБЯЗАННОСТИ</b></p><p>2.1. Составляет сметную документацию. 2.2. Проверяет КС-2 и КС-3. 2.3. Контролирует соответствие факта смете. 2.4. Работает с Гранд Сметой.</p><p><b>3. ОТВЕТСТВЕННОСТЬ</b></p><p>3.1. За достоверность сметной документации.</p>',
};

const WORK_NORMS = {
  'Штукатурка гипсовая 10мм': [{mat:'Штукатурка гипсовая',qty:8,unit:'кг'},{mat:'Грунтовка',qty:0.15,unit:'л'}],
  'Штукатурка гипсовая 20мм': [{mat:'Штукатурка гипсовая',qty:16,unit:'кг'},{mat:'Грунтовка',qty:0.15,unit:'л'}],
  'Стяжка ЦПС 50мм': [{mat:'Цемент М500',qty:12,unit:'кг'},{mat:'Песок',qty:0.035,unit:'м3'}],
  'Шпаклёвка финишная': [{mat:'Шпаклёвка финишная',qty:0.8,unit:'кг'},{mat:'Грунтовка',qty:0.1,unit:'л'}],
  'Покраска стен 2 слоя': [{mat:'Грунтовка',qty:0.1,unit:'л'},{mat:'Краска интерьерная',qty:0.35,unit:'л'}],
  'Укладка плитки на пол': [{mat:'Плиточный клей С1',qty:4,unit:'кг'},{mat:'Затирка',qty:0.3,unit:'кг'}],
  'Укладка плитки на стены': [{mat:'Плиточный клей С2',qty:6,unit:'кг'},{mat:'Затирка',qty:0.3,unit:'кг'}],
  'Укладка ламината': [{mat:'Подложка 3мм',qty:1.05,unit:'м2'}],
  'Кладка кирпича рядового': [{mat:'Кирпич рядовой',qty:400,unit:'шт'},{mat:'Цемент М500',qty:175,unit:'кг'}],
  'Кладка газобетона 200мм': [{mat:'Блок газобетон 200мм',qty:12.5,unit:'шт'},{mat:'Клей для газобетона',qty:3,unit:'кг'}],
};

const PRICELISTS_DATA = {
  'Земляные работы': [{name:'Разработка грунта вручную',unit:'м3'},{name:'Обратная засыпка',unit:'м3'},{name:'Планировка территории',unit:'м2'}],
  'Фундаментные работы': [{name:'Устройство опалубки',unit:'м2'},{name:'Вязка арматуры ø12',unit:'кг'},{name:'Заливка бетона М300',unit:'м3'}],
  'Кладочные работы': [{name:'Кладка кирпича рядового',unit:'м3'},{name:'Кладка газобетона 200мм',unit:'м2'}],
  'Кровельные работы': [{name:'Монтаж стропильной системы',unit:'м2'},{name:'Укладка металлочерепицы',unit:'м2'}],
  'Стяжка и полы': [{name:'Стяжка ЦПС 50мм',unit:'м2'},{name:'Укладка ламината',unit:'м2'},{name:'Укладка плитки на пол',unit:'м2'}],
  'Штукатурные работы': [{name:'Штукатурка гипсовая 10мм',unit:'м2'},{name:'Штукатурка гипсовая 20мм',unit:'м2'}],
  'Шпаклёвочные работы': [{name:'Шпаклёвка финишная',unit:'м2'},{name:'Шпаклёвка потолка',unit:'м2'}],
  'Малярные работы': [{name:'Покраска стен 2 слоя',unit:'м2'},{name:'Покраска потолка 2 слоя',unit:'м2'}],
  'Плиточные работы': [{name:'Укладка плитки на стены',unit:'м2'},{name:'Укладка керамогранита',unit:'м2'}],
  'Откосы': [{name:'Откосы оконные ПВХ',unit:'м2'},{name:'Откосы дверные штукатурка',unit:'м2'},{name:'Откосы оконные штукатурка',unit:'м2'}],
  'Электромонтажные работы': [{name:'Разводка кабеля ВВГнг 3х2.5',unit:'пог.м'},{name:'Установка розетки',unit:'шт'},{name:'Установка выключателя',unit:'шт'}],
  'Сантехнические работы': [{name:'Разводка труб ХВС ø20',unit:'пог.м'},{name:'Монтаж канализации ø110',unit:'пог.м'},{name:'Установка унитаза',unit:'шт'}],
  'Оконные и дверные работы': [{name:'Установка окна ПВХ до 1.5м2',unit:'шт'},{name:'Установка двери входной',unit:'шт'},{name:'Установка двери межкомнатной',unit:'шт'}],
  'Демонтажные работы': [{name:'Демонтаж стяжки',unit:'м2'},{name:'Демонтаж штукатурки',unit:'м2'},{name:'Вывоз мусора',unit:'м3'}],
};

const C = {
  bg:'#f8fafc', bgWhite:'#ffffff', bgGray:'#f1f5f9',
  border:'#e2e8f0', borderDark:'#cbd5e1',
  text:'#0f172a', textSec:'#64748b', textMuted:'#94a3b8',
  accent:'#f97316', accentDark:'#ea580c', accentLight:'#fff7ed', accentBorder:'#fed7aa',
  success:'#10b981', successLight:'#ecfdf5', successBorder:'#a7f3d0',
  danger:'#ef4444', dangerLight:'#fef2f2', dangerBorder:'#fecaca',
  warning:'#f59e0b', warningLight:'#fffbeb', warningBorder:'#fde68a',
  info:'#3b82f6', infoLight:'#eff6ff', infoBorder:'#bfdbfe',
  purple:'#8b5cf6', purpleLight:'#f5f3ff',
  sidebar:'#0f172a', sidebarHover:'#1e293b',
};

const inp = {width:'100%',padding:'10px 12px',marginBottom:'10px',border:'1.5px solid '+C.border,borderRadius:'8px',boxSizing:'border-box',fontSize:'14px',outline:'none',backgroundColor:C.bgWhite,color:C.text,transition:'border-color 0.2s'};
const btnO = {padding:'9px 18px',background:'linear-gradient(135deg,#f97316,#ea580c)',color:'white',border:'none',borderRadius:'8px',cursor:'pointer',fontSize:'13px',fontWeight:'600',display:'inline-flex',alignItems:'center',gap:'6px'};
const btnG = {padding:'7px 14px',backgroundColor:C.bgGray,color:C.textSec,border:'1.5px solid '+C.border,borderRadius:'8px',cursor:'pointer',fontSize:'13px',display:'inline-flex',alignItems:'center',gap:'6px'};
const btnR = {padding:'7px 14px',backgroundColor:C.dangerLight,color:C.danger,border:'1.5px solid '+C.dangerBorder,borderRadius:'8px',cursor:'pointer',fontSize:'13px',display:'inline-flex',alignItems:'center',gap:'6px'};
const btnGr = {padding:'7px 14px',backgroundColor:C.successLight,color:C.success,border:'1.5px solid '+C.successBorder,borderRadius:'8px',cursor:'pointer',fontSize:'13px',display:'inline-flex',alignItems:'center',gap:'6px'};
const btnB = {padding:'7px 14px',backgroundColor:C.infoLight,color:C.info,border:'1.5px solid '+C.infoBorder,borderRadius:'8px',cursor:'pointer',fontSize:'13px',display:'inline-flex',alignItems:'center',gap:'6px'};
const card = {backgroundColor:C.bgWhite,borderRadius:'12px',border:'1.5px solid '+C.border,overflow:'hidden'};
const badge = (color,bg,border) => ({backgroundColor:bg,color:color,border:'1.5px solid '+border,padding:'3px 10px',borderRadius:'20px',fontSize:'11px',fontWeight:'600',display:'inline-flex',alignItems:'center',gap:'4px'});
const tbl = {width:'100%',borderCollapse:'collapse',fontSize:'13px'};
const tblH = {padding:'8px 12px',backgroundColor:C.bg,color:C.textSec,fontWeight:'600',fontSize:'11px',textTransform:'uppercase',borderBottom:'1.5px solid '+C.border,textAlign:'left'};
const tblC = {padding:'8px 12px',borderBottom:'1px solid '+C.border,color:C.text,fontSize:'13px'};
function App() {
  const [isMobile, setIsMobile] = useState(typeof window !== 'undefined' && window.innerWidth < 768);
  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  const [user, setUser] = useState(null);
  const [page, setPage] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [regName, setRegName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regCode, setRegCode] = useState('');
  const [loginError, setLoginError] = useState('');
  const [activePage, setActivePage] = useState('dashboard');
  const [activeProjectTab, setActiveProjectTab] = useState('Общее');
  const [activeTabGroup, setActiveTabGroup] = useState(null);
  const [sidebarVisible, setSidebarVisible] = useState(false);
  const [projects, setProjects] = useState([]);
  const [clients, setClients] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [warehouseMain, setWarehouseMain] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [warehouseMovements, setWarehouseMovements] = useState([]);
  const [history, setHistory] = useState([]);
  const [staff, setStaff] = useState([]);
  const [piecework, setPiecework] = useState([]);
  const [users, setUsers] = useState([]);
  const [pricelists, setPricelists] = useState([]);
  const [pricelistItems, setPricelistItems] = useState([]);
  const [inviteCodes, setInviteCodes] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [supplyRequests, setSupplyRequests] = useState([]);
  const [supplierOffers, setSupplierOffers] = useState([]);
  const [supplyHistory, setSupplyHistory] = useState([]);
  const [workJournal, setWorkJournal] = useState([]);
  const [masterProfile, setMasterProfile] = useState(null);
  const [masterProfiles, setMasterProfiles] = useState([]);
  const [contracts, setContracts] = useState([]);
  const [interimActs, setInterimActs] = useState([]);
  const [timesheet, setTimesheet] = useState({});
  const [unexpectedWorksList, setUnexpectedWorksList] = useState([]);
  const [brigadeContracts, setBrigadeContracts] = useState([]);
  const [hiddenActs, setHiddenActs] = useState([]);
  const [editingAct, setEditingAct] = useState(null);
  const [editingJournal, setEditingJournal] = useState(null);
  const [journalFilter, setJournalFilter] = useState({from:'',to:'',masterName:'',sectionName:'',status:''});
  const [showJournalPrintDialog, setShowJournalPrintDialog] = useState(null);
  const [showJournalTableModal, setShowJournalTableModal] = useState(null);
  const [materialInspections, setMaterialInspections] = useState([]);
  const [editingInspection, setEditingInspection] = useState(null);
  const [cableJournal, setCableJournal] = useState([]);
  const [editingCable, setEditingCable] = useState(null);
  const [supervisorActs, setSupervisorActs] = useState([]);
  const [inspectionOrders, setInspectionOrders] = useState([]);
  const [newInspOrder, setNewInspOrder] = useState(null);
  const [auditLog, setAuditLog] = useState([]);
  const [journalView, setJournalView] = useState('daily');
  const [expenseReports, setExpenseReports] = useState([]);
  const [newExpenseReport, setNewExpenseReport] = useState(null);
  const [supplierInvoices, setSupplierInvoices] = useState([]);
  const [newSupplierInvoice, setNewSupplierInvoice] = useState(null);
  const [newSupervisorAct, setNewSupervisorAct] = useState({actType:'Осмотр',description:'',findings:'',recommendations:'',date:''});
  const [supervisorActPhoto, setSupervisorActPhoto] = useState('');
  const [prescriptionPhoto, setPrescriptionPhoto] = useState('');
  const [selectedBrigadeContract, setSelectedBrigadeContract] = useState(null);
  const [brigadeContractItems, setBrigadeContractItems] = useState([]);
  const [showBrigadeForm, setShowBrigadeForm] = useState(false);
  const [newBrigadeContract, setNewBrigadeContract] = useState({projectId:'',projectName:'',brigadeName:'',contractorType:'Своя бригада',contractorId:'',notes:'',pricelistId:''});
  const [newBrigadeItem, setNewBrigadeItem] = useState({name:'',unit:'м',quantity:'',priceSmeta:'',priceBrigade:'',estimateSection:''});
  const [brigadeCoef, setBrigadeCoef] = useState('0.6');
  const [masterReportPhotos, setMasterReportPhotos] = useState([]);
  const [supplierCatalog, setSupplierCatalog] = useState([]);
  const [showCatalogForm, setShowCatalogForm] = useState(false);
  const [newCatalogItem, setNewCatalogItem] = useState({materialName:'',unit:'шт',price:'',minQuantity:'1',deliveryDays:'3',notes:''});
  const [supplierTab, setSupplierTab] = useState('requests');
  const [supplierRequisites, setSupplierRequisites] = useState({companyName:'',inn:'',kpp:'',address:'',bank:'',bik:'',account:'',phone:'',email:'',priceUrl:''});
  const [materialTransfers, setMaterialTransfers] = useState([]);
  const [showTransferForm, setShowTransferForm] = useState(false);
  const [newTransfer, setNewTransfer] = useState({materialName:'',quantity:'',unit:'шт',toPerson:'',toPersonRole:'',fromLocation:'Основной склад',notes:'',transferDate:new Date().toISOString().split('T')[0]});
  const [sverkaModal, setSverkaModal] = useState(null);
  const [showAiChat, setShowAiChat] = useState(false);
  const [showMobileMenu, setShowMobileMenu] = useState(false);
  const [showQuickActions, setShowQuickActions] = useState(false);
  const [showChatPanel, setShowChatPanel] = useState(false);
  const [companyChatInput, setCompanyChatInput] = useState('');
  const [showScanInvoice, setShowScanInvoice] = useState(false);
  const [showScannedInvoiceForm, setShowScannedInvoiceForm] = useState(false);
  const [showReceiveDialog, setShowReceiveDialog] = useState(false);

  const openReceiveInvoice = (preselectedLocation) => {
    setNewInvoice({number:'',date:new Date().toISOString().split('T')[0],supplierId:'',isNewSupplier:false,newSupplierName:'',acceptedBy:user?.name||'',location:preselectedLocation||'',project:preselectedLocation&&preselectedLocation!=='Основной склад'?preselectedLocation:'',vat:'Без НДС',photos:[],items:[{name:'',quantity:'',unit:'шт',price:'',category:''}],supplier:'',totalWithVat:0});
    setShowReceiveDialog(true);
  };
  const [scanningInvoice, setScanningInvoice] = useState(false);
  const [projectPayments, setProjectPayments] = useState([]);
  const [accountablePayments, setAccountablePayments] = useState([]);
  const [showAccountableForm, setShowAccountableForm] = useState(false);
  const [newAccountable, setNewAccountable] = useState({givenTo:'',amount:'',paymentMethod:'Наличные',purpose:'',date:''});
  const [reportingPayment, setReportingPayment] = useState(null);
  const [newExpense, setNewExpense] = useState({description:'',amount:'',photoUrl:''});
  const [expenseSubmitting, setExpenseSubmitting] = useState(false);
  const [ownExpenses, setOwnExpenses] = useState([]);
  const [showOwnExpenseForm, setShowOwnExpenseForm] = useState(false);
  const [addExpenseProject, setAddExpenseProject] = useState('');
  const [showBalanceDetails, setShowBalanceDetails] = useState(false);
  const [customRoomTypes, setCustomRoomTypes] = useState(()=>{try{return JSON.parse(localStorage.getItem('customRoomTypes')||'[]');}catch{return [];}});
  const [manualExpenses, setManualExpenses] = useState([]);
  const [newManualExpense, setNewManualExpense] = useState({category:'materials',amount:'',note:'',date:''});
  const [newOwnExpense, setNewOwnExpense] = useState({projectName:'',description:'',amount:'',photoUrl:'',date:''});
  const [aiMessages, setAiMessages] = useState([{role:'assistant',content:'Привет! Я ИИ помощник СтройКа. Могу ответить на вопросы по вашим объектам, сметам, складу и финансам. Спрашивайте!'}]);
  const [aiInput, setAiInput] = useState('');
  const [checklists, setChecklists] = useState([]);
  const [checklistItems, setChecklistItems] = useState({});
  const [projectStages, setProjectStages] = useState([]);
  const [prescriptionsList, setPrescriptionsList] = useState([]);
  const [projectChatMessages, setProjectChatMessages] = useState({});
  const [companyMessages, setCompanyMessages] = useState([]);
  const [leads, setLeads] = useState([]);
  const [masterRatings, setMasterRatings] = useState({});
  const [activityLog, setActivityLog] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [archivedProjects, setArchivedProjects] = useState([]);
  const [tbJournal, setTbJournal] = useState([]);
  const [geoCheckins, setGeoCheckins] = useState([]);
  const [, setSignedDocs] = useState({});
  const [rooms, setRooms] = useState([]);
  const [, setRoomWorks] = useState([]);
  const [roomWindows, setRoomWindows] = useState([]);
  const [roomDoors, setRoomDoors] = useState([]);
  const [tools, setTools] = useState([]);
  const [toolHistory, setToolHistory] = useState([]);
  const [inventory, setInventory] = useState([]);
  const [pdConsents, setPdConsents] = useState([]);
  const [actPayments, setActPayments] = useState([]);
  const [weatherLog, setWeatherLog] = useState([]);
  const [estimatesList, setEstimatesList] = useState([]);
  const [companyRequisites, setCompanyRequisites] = useState({});
  const [companyDocuments, setCompanyDocuments] = useState([]);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiChat, setAiChat] = useState([]);
  const [aiMessage, setAiMessage] = useState('');
  const [pushEnabled, setPushEnabled] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [previewContent, setPreviewContent] = useState(null);
  const [previewTitle, setPreviewTitle] = useState('');
  const [globalSearch, setGlobalSearch] = useState('');
  const [showSearch, setShowSearch] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [showRoomForm, setShowRoomForm] = useState(false);
  const [showPiecework, setShowPiecework] = useState(false);
  const [showInvites, setShowInvites] = useState(false);
  const [showOffers, setShowOffers] = useState(null);
  const [showProfileForm, setShowProfileForm] = useState(false);
  const [showPhotoModal, setShowPhotoModal] = useState(null);
  const [showArchive, setShowArchive] = useState(false);
  const [showIssueToolModal, setShowIssueToolModal] = useState(null);
  const [showReturnToolModal, setShowReturnToolModal] = useState(null);
  const [showPayActModal, setShowPayActModal] = useState(null);
  const [showAiAssistant, setShowAiAssistant] = useState(false);
  const [showQRModal, setShowQRModal] = useState(null);
  const [consentChecked, setConsentChecked] = useState(false);
  const [accountingTab, setAccountingTab] = useState('summary');
  const [accountingDocProject, setAccountingDocProject] = useState('');
  const [suppliersTab, setSuppliersTab] = useState('active');
  const [personnelTab, setPersonnelTab] = useState('staff');
  const [warehouseTab, setWarehouseTab] = useState('objects');
  const [selectedWarehouseProject, setSelectedWarehouseProject] = useState(null);
  const [toolsTab, setToolsTab] = useState('list');
  const [estimatesTab, setEstimatesTab] = useState('list');
  const [weatherTab, setWeatherTab] = useState('log');
  const [settingsTab, setSettingsTab] = useState('requisites');
  const [rejectComment, setRejectComment] = useState('');
  const [rejectingEntry, setRejectingEntry] = useState(null);
  const [editingItem, setEditingItem] = useState(null);
  const [editingPlItem, setEditingPlItem] = useState(null);
  const [inlineEditPl, setInlineEditPl] = useState(null);
  const [inlineEditPrice, setInlineEditPrice] = useState('');
  const [editingWindow, setEditingWindow] = useState(null);
  const [editingDoor, setEditingDoor] = useState(null);
  const [selectedPricelist, setSelectedPricelist] = useState(null);
  const [selectedInventory, setSelectedInventory] = useState(null);
  const [selectedEstimate, setSelectedEstimate] = useState(null);
  const [selectedChecklist, setSelectedChecklist] = useState(null);
  const [expandedProject, setExpandedProject] = useState(null);
  const [projectAiSummaries, setProjectAiSummaries] = useState({});
  const [expandedClient, setExpandedClient] = useState(null);
  const [expandedGroup, setExpandedGroup] = useState(null);
  const [expandedMaster, setExpandedMaster] = useState(null);
  const [expandedMasterProject, setExpandedMasterProject] = useState(null);
  const [expandedPieceworkProject, setExpandedPieceworkProject] = useState(null);
  const [expandedRoom, setExpandedRoom] = useState(null);
  const [searchUser, setSearchUser] = useState('');
  const [newTask, setNewTask] = useState('');
  const [companyChatMessage, setCompanyChatMessage] = useState('');
  const [projectChatMessage, setProjectChatMessage] = useState('');
  const [masterProjectId, setMasterProjectId] = useState('');
  const [selectedWorks, setSelectedWorks] = useState({});
  const [companyName, setCompanyName] = useState('');
  const [issueToolData, setIssueToolData] = useState({masterName:'',project:'',issueType:'Временно'});
  const [returnToolCondition, setReturnToolCondition] = useState('Исправен');
  const [newPayment, setNewPayment] = useState({amount:'',paymentType:'Наличный расчёт',paidBy:'',date:'',notes:''});
  const [newPiecework, setNewPiecework] = useState({staffId:'',description:'',unit:'м2',quantity:'',pricePerUnit:'',project:''});
  const [newProject, setNewProject] = useState({name:'',client:'',status:'Планирование',budget:'',deadline:'',progress:0,tasks:[],pricelistId:null});
  const [newClient, setNewClient] = useState({name:'',phone:'',email:'',status:'Активный',notes:''});
  const [newWarehouse, setNewWarehouse] = useState({name:'',city:'',address:'',notes:''});
  const [newMovement, setNewMovement] = useState({materialName:'',fromLocation:'Основной склад',toLocation:'',quantity:'',unit:'шт',notes:'',selectedMaterials:[]});
  const [newInvoice, setNewInvoice] = useState({number:'',date:'',supplierId:'',isNewSupplier:false,newSupplierName:'',acceptedBy:'',location:'Основной склад',project:'',vat:'Без НДС',photos:[],items:[{name:'',quantity:'',unit:'шт',price:'',category:''}]});
  const [newStaff, setNewStaff] = useState({name:'',role:'',phone:'',salary:'',project:'',payType:'оклад',email:'',password:'',systemRole:'',lastName:'',firstName:'',middleName:'',birthDate:'',citizenship:'РФ',address:'',photoUrl:'',emailWork:'',emailPersonal:'',phoneExtra:'',passportSeries:'',passportNumber:'',passportIssuedBy:'',passportIssuedDate:'',inn:'',snils:'',specialization:'',category:'',employmentType:'',hiredDate:'',firedDate:'',status:'Активен',brigade:'',bankAccount:'',bankName:'',bankBik:'',bankCorr:'',ogrnip:'',cardNumber:'',signatureUrl:'',notes:''});
  const [staffExpandedSections, setStaffExpandedSections] = useState({access:false,docs:false,finance:false,extra:false});
  const [expandedStaffId, setExpandedStaffId] = useState(null);
  const [staffProfile, setStaffProfile] = useState(null);
  const [staffProfileLoading, setStaffProfileLoading] = useState(false);
  const [newStaffDoc, setNewStaffDoc] = useState({docType:'другое',title:'',fileUrl:'',signedAt:'',expiresAt:'',notes:''});
  const [showStaffDocForm, setShowStaffDocForm] = useState(false);

  const openStaffProfile = async (s) => {
    if (expandedStaffId === s.id) {setExpandedStaffId(null); setStaffProfile(null); return;}
    setExpandedStaffId(s.id);
    setStaffProfileLoading(true);
    try {
      const data = await fetch(API+'/staff/'+s.id+'/profile').then(r=>r.json());
      setStaffProfile(data);
    } catch(e) {setStaffProfile(null);}
    setStaffProfileLoading(false);
  };

  const addStaffDoc = async (staffId) => {
    if (!newStaffDoc.title) return alert('Укажите название документа');
    await fetch(API+'/staff/'+staffId+'/documents',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newStaffDoc,createdBy:user?.name||''})});
    const data = await fetch(API+'/staff/'+staffId+'/profile').then(r=>r.json());
    setStaffProfile(data);
    setNewStaffDoc({docType:'другое',title:'',fileUrl:'',signedAt:'',expiresAt:'',notes:''});
    setShowStaffDocForm(false);
  };
  const [newUser, setNewUser] = useState({name:'',email:'',password:'',role:'прораб'});
  const [newPricelist, setNewPricelist] = useState({name:'',description:'',forWho:'',coefficient:1.0});
  const [newPlItem, setNewPlItem] = useState({name:'',unit:'м2',price:'',category:''});
  const [newInviteRole, setNewInviteRole] = useState('мастер');
  const [newSupplier, setNewSupplier] = useState({name:'',phone:'',email:'',specialization:'',category:'Сыпучие и бетон',rating:5.0,status:'Активный'});
  const [newRequest, setNewRequest] = useState({items:[{materialName:'',quantity:'',unit:'шт'}],project:'',notes:'',selectedSuppliers:[],category:''});
  const [newOffer, setNewOffer] = useState({supplierId:'',pricePerUnit:'',deliveryDays:'',notes:''});
  const [newContract, setNewContract] = useState({masterId:'',masterName:'',contractType:'ГПХ',contractNumber:'',project:'',startDate:'',endDate:''});
  const [newAct, setNewAct] = useState({masterId:'',masterName:'',project:'',periodStart:'',periodEnd:''});
  const [newTool, setNewTool] = useState({name:'',inventoryNumber:'',cost:'',status:'На складе',location:'Основной склад',project:'',masterId:'',masterName:'',issueType:'',notes:''});
  const [newRoom, setNewRoom] = useState({project:'',name:'',floorArea:'',wallArea:'',ceilingArea:'',height:'',ceilingType:'Простой',wallMaterial:'Штукатурка',floorMaterial:'Стяжка',notes:''});
  const [newWindow, setNewWindow] = useState({roomId:'',name:'Окно 1',width:'',height:'',windowType:'ПВХ',revealDepth:'',revealMaterial:'Штукатурка'});
  const [newDoor, setNewDoor] = useState({roomId:'',name:'Дверь 1',width:'',height:'',doorType:'Деревянная',doorPurpose:'Межкомнатная',revealDepth:'',revealMaterial:'Штукатурка'});
  const [newInventory, setNewInventory] = useState({project:'',date:'',notes:''});
  const [newWeather, setNewWeather] = useState({projectName:'',date:'',temperature:'',condition:'Ясно',windSpeed:'',notes:''});
  const [newEstimate, setNewEstimate] = useState({projectId:'',projectName:'',name:'',version:'1.0',smetaType:'Заказчик',templateId:''});
  const [showVersionHistory, setShowVersionHistory] = useState(false);
  const [estimateVersions, setEstimateVersions] = useState([]);
  const [selectedVersionsToCompare, setSelectedVersionsToCompare] = useState([]);
  const [importValidationWarnings, setImportValidationWarnings] = useState([]);
  const [importValidating, setImportValidating] = useState(false);
  const [showEstimateChat, setShowEstimateChat] = useState(false);
  const [estimateChatMessages, setEstimateChatMessages] = useState([]);
  const [estimateChatInput, setEstimateChatInput] = useState('');
  const [estimateChatLoading, setEstimateChatLoading] = useState(false);
  const [showGenerateEstimate, setShowGenerateEstimate] = useState(false);
  const [generateForm, setGenerateForm] = useState({description:'',projectId:'',pricelistId:'',area:'',name:''});
  const [generating, setGenerating] = useState(false);
  const [showGeneratePricelist, setShowGeneratePricelist] = useState(false);
  const [generatePricelistForm, setGeneratePricelistForm] = useState({description:'',name:'',forWho:'',coefficient:1.0});
  const [generatingPricelist, setGeneratingPricelist] = useState(false);
  const [showFromEstimate, setShowFromEstimate] = useState(false);
  const [fromEstimateForm, setFromEstimateForm] = useState({estimateId:'',name:'',forWho:'',coefficient:1.0});
  const [creatingFromEstimate, setCreatingFromEstimate] = useState(false);
  const [showDistribute, setShowDistribute] = useState(false);
  const [distributeAssignments, setDistributeAssignments] = useState({});
  const [distributeBrigades, setDistributeBrigades] = useState([]);
  const [newDistributeBrigade, setNewDistributeBrigade] = useState({brigadeName:'',contractorType:'Своя бригада',pricelistId:''});
  const [distributing, setDistributing] = useState(false);

  const persistEstimate = async (est) => {
    if (!est || !est.id) return;
    try {
      await fetch(API+'/estimates/'+est.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(est)});
    } catch(e) {}
  };

  const sendEstimateChatMessage = async () => {
    if (!selectedEstimate || !estimateChatInput.trim() || estimateChatLoading) return;
    const msg = estimateChatInput.trim();
    setEstimateChatInput('');
    const localHistory = [...estimateChatMessages, {role:'user', content:msg, id:Date.now()}];
    setEstimateChatMessages(localHistory);
    setEstimateChatLoading(true);
    try {
      const fmt = (n) => Number(n||0).toLocaleString('ru-RU');
      let total = 0;
      const itemLines = (selectedEstimate.sections||[]).flatMap(s => (s.items||[]).map(i => {
        const work = Number(i.priceWork||0);
        const mat = Number(i.priceMaterial||0);
        const qty = Number(i.quantity||0);
        const sum = i.isImported ? work + mat : qty * (work + mat);
        total += sum;
        return '['+s.name+'] '+i.name+' | '+qty+' '+i.unit+' | работа '+work+'₽ материал '+mat+'₽ итого '+sum+'₽';
      }));
      const context = 'Смета "'+selectedEstimate.name+'"\nИтого: '+fmt(total)+' ₽\nПозиций: '+itemLines.length+'\n\nПОЗИЦИИ:\n'+itemLines.join('\n');
      const res = await fetch(API+'/estimate-chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({estimateId:selectedEstimate.id,message:msg,context,history:estimateChatMessages.map(m=>({role:m.role,content:m.content}))})});
      const data = await res.json();
      setEstimateChatMessages([...localHistory,{role:'assistant',content:data.response||'Ошибка ответа',id:data.assistantMessageId||Date.now()+1}]);
    } catch(err) {
      setEstimateChatMessages([...localHistory,{role:'assistant',content:'Ошибка соединения',id:Date.now()+1}]);
    }
    setEstimateChatLoading(false);
  };
  const [newEstimateSection, setNewEstimateSection] = useState({name:''});
  const [newEstimateItem, setNewEstimateItem] = useState({sectionId:'',name:'',unit:'м2',quantity:'',priceWork:'',priceMaterial:''});
  const [newStage, setNewStage] = useState({name:'',status:'Не начат',startDate:'',endDate:'',progress:0,responsible:'',notes:''});
  const [newChecklist, setNewChecklist] = useState({name:'',template:''});
  const [newChecklistItem, setNewChecklistItem] = useState('');
  const [newPrescription, setNewPrescription] = useState({number:'',violation:'',deadline:'',responsible:'',photoUrl:''});
  const [newUnexpected, setNewUnexpected] = useState({description:'',unit:'шт',quantity:'',price:'',notes:'',photoUrl:''});
  const [newCompanyDoc, setNewCompanyDoc] = useState({name:'',docType:'Устав',fileUrl:'',expiresAt:''});
  const [companyReqForm, setCompanyReqForm] = useState({fullName:'',shortName:'',inn:'',kpp:'',ogrn:'',legalAddress:'',actualAddress:'',phone:'',email:'',directorName:'',directorPosition:'Генеральный директор',basis:'Устава',bankName:'',bik:'',rs:'',ks:''});
  const [profileData, setProfileData] = useState({fullName:'',passport:'',inn:'',contractType:'ГПХ',bankAccount:'',bankName:'',phone:'',specialization:'',ogrnip:''});
  const [newLead, setNewLead] = useState({name:'',phone:'',email:'',source:'',budget:'',notes:'',stage:'Новый'});
  const [newTbEntry, setNewTbEntry] = useState({project:'',type:'Вводный инструктаж',participants:[],date:'',program:'',instructionText:'',aiLoading:false});
  const [newParticipant, setNewParticipant] = useState('');
  const notifRef = useRef(null);
  const sidebarRef = useRef(null);
  const chatEndRef = useRef(null);

  const showPreview = (content, title) => { setPreviewContent(content); setPreviewTitle(title); };

  const callAI = async (prompt, conversational) => {
    setAiLoading(true);
    try {
      let messages;
      if (conversational) {
        messages = [...aiChat.map(m=>({role:m.role,content:m.content})), {role:'user',content:prompt}];
      } else {
        messages = [{role:'user',content:prompt}];
      }
      const res = await fetch(API+'/ai-chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages})});
      const data = await res.json();
      const text = data.response || data.text || 'Нет ответа';
      setAiLoading(false);
      return text;
    } catch(e) { setAiLoading(false); return ''; }
  };

  const sendAiMessage = async () => {
    if (!aiMessage.trim()) return;
    const userMsg = {role:'user',content:aiMessage,time:new Date().toLocaleTimeString('ru-RU')};
    setAiChat(prev=>[...prev,userMsg]);
    setAiMessage('');
    const response = await callAI(aiMessage, true);
    const assistantMsg = {role:'assistant',content:response,time:new Date().toLocaleTimeString('ru-RU')};
    setAiChat(prev=>[...prev,assistantMsg]);
    setTimeout(()=>chatEndRef.current?.scrollIntoView({behavior:'smooth'}),100);
  };

  const getNotifPage = (type) => {
    const map = {work:'projects',material:'warehouse',stock:'warehouse',supply:'suppliers',delivery:'suppliers',invoice:'accounting',act:'accounting',contract:'accounting',unexpected:'dashboard',prescription:'projects',project:'projects',crm:'crm'};
    return map[type]||'dashboard';
  };

  const myNotifications = (notifs) => {
    if (!user) return notifs;
    if (['директор','зам_директора'].includes(user.role)) return notifs;
    if (user.role==='прораб') return notifs.filter(n=>['work','material','unexpected','prescription','supply'].includes(n.type));
    if (['мастер','субподрядчик'].includes(user.role)) return notifs.filter(n=>n.text&&n.text.includes(user.name));
    if (user.role==='бухгалтер') return notifs.filter(n=>['invoice','act','contract'].includes(n.type));
    if (['кладовщик','снабженец'].includes(user.role)) return notifs.filter(n=>['stock','supply','delivery'].includes(n.type));
    return notifs;
  };

  const notify = (text, type) => {
    const n = {id:Date.now(),text,type,time:new Date().toLocaleString('ru-RU'),read:false};
    setNotifications(prev=>{const updated=[n,...prev].slice(0,50);localStorage.setItem('notifications',JSON.stringify(updated));return updated;});
    if (pushEnabled) sendPushNotification('СтройКа', text);
  };

  const addActivity = (action) => {
    const entry = {id:Date.now(),action,user:user?user.name:'',role:user?user.role:'',time:new Date().toLocaleString('ru-RU')};
    setActivityLog(prev=>{const updated=[entry,...prev].slice(0,100);localStorage.setItem('activityLog',JSON.stringify(updated));return updated;});
  };

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (notifRef.current && !notifRef.current.contains(e.target)) setShowNotifications(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (user) {
      loadAll();
      if (['мастер','субподрядчик'].includes(user.role)) { loadMasterProfile(); setActivePage('works'); }
      const saved = localStorage.getItem('companyName'); if (saved) setCompanyName(saved);
      const keys = ['leads','masterRatings','activityLog','notifications','archivedProjects','tbJournal','geoCheckins','signedDocs','actPayments','weatherLog'];
      const setters = [setLeads,setMasterRatings,setActivityLog,setNotifications,setArchivedProjects,setTbJournal,setGeoCheckins,setSignedDocs,setActPayments,setWeatherLog];
      keys.forEach((k,i) => { const v=localStorage.getItem(k); if(v) setters[i](JSON.parse(v)); });
      requestPushPermission().then(granted => setPushEnabled(granted));
      const pingOnline = async () => {
        try {
          await fetch(API+'/online',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({userId:user.id,userName:user.name,userRole:user.role,lastSeen:new Date().toISOString()})});
        } catch(e){}
      };
      pingOnline();
      const pingInterval = setInterval(pingOnline, 30000);
      return ()=>clearInterval(pingInterval);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  const loadAll = async () => {
    try {
      const [p,c,m,winv,pp,acp,oe,me,wm,wmov,h,s,pw,u,pl,ic,sup,sr,so,sh,wj,mp,ct,ia,ro,rw,tl,th,inv,pdc,wh,cr,cd,ps,pcl,pres,uw,est,bc,hwa,mij,cbj,sva,inspO,expR,supI] = await Promise.all([
        fetch(API+'/projects').then(r=>r.json()),
        fetch(API+'/clients').then(r=>r.json()),
        fetch(API+'/materials').then(r=>r.json()),
        fetch(API+'/warehouse-invoices').then(r=>r.json()),
        fetch(API+'/project-payments').then(r=>r.json()).catch(()=>[]),
        fetch(API+'/accountable-payments').then(r=>r.json()).catch(()=>[]),
        fetch(API+'/own-expenses').then(r=>r.json()).catch(()=>[]),
        fetch(API+'/expenses').then(r=>r.json()).catch(()=>[]),
        fetch(API+'/warehouse-main').then(r=>r.json()),
        fetch(API+'/warehouse-movements').then(r=>r.json()),
        fetch(API+'/warehouse-history').then(r=>r.json()),
        fetch(API+'/staff').then(r=>r.json()),
        fetch(API+'/piecework').then(r=>r.json()),
        fetch(API+'/users').then(r=>r.json()),
        fetch(API+'/pricelists').then(r=>r.json()),
        fetch(API+'/invite-codes').then(r=>r.json()),
        fetch(API+'/suppliers').then(r=>r.json()),
        fetch(API+'/supply-requests').then(r=>r.json()),
        fetch(API+'/supplier-offers').then(r=>r.json()),
        fetch(API+'/supply-history').then(r=>r.json()),
        fetch(API+'/work-journal').then(r=>r.json()),
        fetch(API+'/master-profiles').then(r=>r.json()),
        fetch(API+'/contracts').then(r=>r.json()),
        fetch(API+'/interim-acts').then(r=>r.json()),
        fetch(API+'/rooms').then(r=>r.json()),
        fetch(API+'/room-works').then(r=>r.json()),
        fetch(API+'/tools').then(r=>r.json()),
        fetch(API+'/tool-history').then(r=>r.json()),
        fetch(API+'/inventory').then(r=>r.json()),
        fetch(API+'/pd-consents').then(r=>r.json()),
        fetch(API+'/warehouses').then(r=>r.json()).catch(()=>[]),
        fetch(API+'/company-requisites').then(r=>r.json()).catch(()=>({})),
        fetch(API+'/company-documents').then(r=>r.json()).catch(()=>[]),
        fetch(API+'/project-stages').then(r=>r.json()).catch(()=>[]),
        fetch(API+'/project-checklists').then(r=>r.json()).catch(()=>[]),
        fetch(API+'/prescriptions').then(r=>r.json()).catch(()=>[]),
        fetch(API+'/unexpected-works').then(r=>r.json()).catch(()=>[]),
        fetch(API+'/estimates').then(r=>r.json()).catch(()=>[]),
        fetch(API+'/brigade-contracts').then(r=>r.json()).catch(()=>[]),
        fetch(API+'/hidden-works-acts').then(r=>r.json()).catch(()=>[]),
        fetch(API+'/material-inspection').then(r=>r.json()).catch(()=>[]),
        fetch(API+'/cable-journal').then(r=>r.json()).catch(()=>[]),
        fetch(API+'/supervisor-acts').then(r=>r.json()).catch(()=>[]),
        fetch(API+'/inspection-orders').then(r=>r.json()).catch(()=>[]),
        fetch(API+'/expense-reports').then(r=>r.json()).catch(()=>[]),
        fetch(API+'/supplier-invoices').then(r=>r.json()).catch(()=>[]),
      ]);
      setProjects(p);setClients(c);setMaterials(m);setInvoices(Array.isArray(winv)?winv:[]);setProjectPayments(Array.isArray(pp)?pp:[]);setAccountablePayments(Array.isArray(acp)?acp:[]);setOwnExpenses(Array.isArray(oe)?oe:[]);setManualExpenses(Array.isArray(me)?me:[]);setWarehouseMain(wm);setWarehouseMovements(wmov);
      setHistory(h);setStaff(s);setPiecework(pw);setUsers(u);setPricelists(pl);
      setInviteCodes(ic);setSuppliers(sup);setSupplyRequests(sr);setSupplierOffers(so);
      setSupplyHistory(sh);setWorkJournal(wj);setMasterProfiles(mp);setContracts(ct);
      setInterimActs(ia);setRooms(ro);setRoomWorks(rw);setTools(tl);setToolHistory(th);
      setInventory(inv);setPdConsents(pdc);setWarehouses(Array.isArray(wh)?wh:[]);
      setCompanyRequisites(cr||{});setCompanyDocuments(Array.isArray(cd)?cd:[]);
      setProjectStages(Array.isArray(ps)?ps:[]);setChecklists(Array.isArray(pcl)?pcl:[]);
      setPrescriptionsList(Array.isArray(pres)?pres:[]);setUnexpectedWorksList(Array.isArray(uw)?uw:[]);setEstimatesList(Array.isArray(est)?est:[]);setBrigadeContracts(Array.isArray(bc)?bc:[]);setHiddenActs(Array.isArray(hwa)?hwa:[]);setMaterialInspections(Array.isArray(mij)?mij:[]);setCableJournal(Array.isArray(cbj)?cbj:[]);setSupervisorActs(Array.isArray(sva)?sva:[]);setInspectionOrders(Array.isArray(inspO)?inspO:[]);setExpenseReports(Array.isArray(expR)?expR:[]);setSupplierInvoices(Array.isArray(supI)?supI:[]);
      try {
        const [rwin,rdoor] = await Promise.all([
          fetch(API+'/room-windows').then(r=>r.json()).catch(()=>[]),
          fetch(API+'/room-doors').then(r=>r.json()).catch(()=>[]),
        ]);
        setRoomWindows(Array.isArray(rwin)?rwin:[]); setRoomDoors(Array.isArray(rdoor)?rdoor:[]);
      } catch(e) {}
      try {
        const msgs = await fetch(API+'/messages').then(r=>r.json()).catch(()=>[]);
        setCompanyMessages(Array.isArray(msgs)?msgs:[]);
      } catch(e) {}
      try {
        const mt = await fetch(API+'/material-transfers').then(r=>r.json()).catch(()=>[]);
        setMaterialTransfers(Array.isArray(mt)?mt:[]);
      } catch(e) {}
    } catch(e) { console.log('Load error:',e); }
  };

  const loadMasterProfile = async () => {
    try {
      const profile = await fetch(API+'/master-profile/'+user.id).then(r=>r.json());
      setMasterProfile(profile);
      if (!profile.profileCompleted) setShowProfileForm(true);
    } catch(e) {}
  };

  const loadPricelistItems = async (plId) => {
    const items = await fetch(API+'/pricelists/'+plId+'/items').then(r=>r.json());
    setPricelistItems(items);
  };

  const loadProjectChat = async (projectName) => {
    try {
      const msgs = await fetch(API+'/project-chat/'+encodeURIComponent(projectName)).then(r=>r.json()).catch(()=>[]);
      setProjectChatMessages(prev=>({...prev,[projectName]:Array.isArray(msgs)?msgs:[]}));
    } catch(e) {}
  };

  const loadChecklistItems = async (checklistId) => {
    try {
      const items = await fetch(API+'/checklist-items/'+checklistId).then(r=>r.json()).catch(()=>[]);
      setChecklistItems(prev=>({...prev,[checklistId]:Array.isArray(items)?items:[]}));
    } catch(e) {}
  };

  const uploadPhoto = async (file) => {
    const fd = new FormData(); fd.append('file',file);
    try { const res = await fetch(API+'/upload-photo',{method:'POST',body:fd}); const data = await res.json(); return data.url; } catch { return ''; }
  };

  const checkinGeo = () => {
    if (!navigator.geolocation) { alert('Геолокация не поддерживается'); return; }
    navigator.geolocation.getCurrentPosition((pos) => {
      const checkin = {id:Date.now(),userId:user.id,userName:user.name,lat:pos.coords.latitude,lng:pos.coords.longitude,time:new Date().toLocaleString('ru-RU'),date:new Date().toISOString().split('T')[0]};
      const updated = [...geoCheckins,checkin];
      setGeoCheckins(updated); localStorage.setItem('geoCheckins',JSON.stringify(updated));
      alert('Отметка зафиксирована: '+new Date().toLocaleTimeString('ru-RU'));
    }, () => alert('Не удалось получить геолокацию'));
  };

  const calcVat = (total, vatType) => {
    if (vatType==='С НДС 22%') return {base:Math.round(total/1.22*100)/100, vat:Math.round(total/1.22*0.22*100)/100, total};
    return {base:total, vat:0, total};
  };

  const calcWindowArea = (w) => Number(w.width||0)*Number(w.height||0);
  const calcWindowReveals = (w) => {
    const d = Number(w.reveal_depth||w.revealDepth||0)/100;
    const wd = Number(w.width||0);
    const ht = Number(w.height||0);
    return Math.round((wd*d + ht*d*2)*100)/100;
  };
  const calcDoorArea = (d) => Number(d.width||0)*Number(d.height||0);
  const calcDoorReveals = (d) => {
    const dep = Number(d.reveal_depth||d.revealDepth||0)/100;
    const wd = Number(d.width||0);
    const ht = Number(d.height||0);
    return Math.round((wd*dep + ht*dep*2)*100)/100;
  };

  const getRoomNetWall = (room) => {
    const wins = roomWindows.filter(w=>w.room_id===room.id);
    const doors = roomDoors.filter(d=>d.room_id===room.id);
    const winArea = wins.reduce((s,w)=>s+calcWindowArea(w),0);
    const doorArea = doors.reduce((s,d)=>s+calcDoorArea(d),0);
    return Math.max(0, Math.round((room.wallArea - winArea - doorArea)*100)/100);
  };

  const saveActPayment = async (actId) => {
    if (!newPayment.amount||!newPayment.date) { alert('Заполните сумму и дату'); return; }
    const act = interimActs.find(a=>a.id===actId);
    if (!act) return;
    const payment = {...newPayment,id:Date.now(),actId,amount:Number(newPayment.amount)};
    const updated = [...actPayments,payment];
    setActPayments(updated); localStorage.setItem('actPayments',JSON.stringify(updated));
    const totalPaid = updated.filter(p=>p.actId===actId).reduce((s,p)=>s+p.amount,0);
    const newStatus = totalPaid>=(act.totalAmount||0)?'Оплачен':'Частично оплачен';
    await fetch(API+'/interim-acts/'+actId,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:newStatus,paidAmount:totalPaid})});
    await loadAll();
    setNewPayment({amount:'',paymentType:'Наличный расчёт',paidBy:'',date:'',notes:''});
    setShowPayActModal(null);
  };

  const saveInvoiceNew = async () => {
    if (!newInvoice.number || newInvoice.items.filter(i=>i.name&&i.quantity).length===0) { alert('Заполните номер накладной и материалы'); return; }
    if (!newInvoice.location) { alert('Выберите куда оприходовать (основной склад или объект)'); return; }
    let supplierId = newInvoice.supplierId;
    if (newInvoice.isNewSupplier && newInvoice.newSupplierName) {
      const res = await fetch(API+'/suppliers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:newInvoice.newSupplierName,phone:'',email:'',specialization:'',category:'Прочее',rating:5.0,status:'Активный'})});
      const newSup = await res.json(); supplierId = newSup.id;
    }
    const validItems = newInvoice.items.filter(i=>i.name&&i.quantity);
    const totalBefore = validItems.reduce((s,i)=>s+Number(i.quantity)*Number(i.price||0),0);
    const vatCalc = calcVat(totalBefore, newInvoice.vat);
    for (const item of validItems) {
      if (newInvoice.location==='Основной склад') {
        const existing = warehouseMain.find(m=>m.name.toLowerCase()===item.name.toLowerCase());
        if (existing) await fetch(API+'/warehouse-main/'+existing.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...existing,quantity:existing.quantity+Number(item.quantity)})});
        else await fetch(API+'/warehouse-main',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:item.name,unit:item.unit,quantity:Number(item.quantity),price:Number(item.price||0),minQuantity:0,category:item.category||''})});
      } else {
        const existing = materials.find(m=>m.name.toLowerCase()===item.name.toLowerCase()&&m.project===newInvoice.location);
        if (existing) await fetch(API+'/materials/'+existing.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...existing,quantity:existing.quantity+Number(item.quantity)})});
        else await fetch(API+'/materials',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:item.name,unit:item.unit,quantity:Number(item.quantity),price:Number(item.price||0),minQuantity:0,project:newInvoice.location,category:item.category||''})});
      }
      await fetch(API+'/warehouse-history',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({material:item.name,type:'приход',quantity:Number(item.quantity),date:newInvoice.date||new Date().toISOString().split('T')[0],project:newInvoice.location==='Основной склад'?'Основной склад':newInvoice.project,issuedBy:newInvoice.acceptedBy||user.name,dateTime:new Date().toLocaleString('ru-RU')})});
    }
    const photoUrl = newInvoice.photos && newInvoice.photos.length>0 ? newInvoice.photos[0] : '';
    const inv = {id:Date.now(),number:newInvoice.number,date:newInvoice.date,supplierId:Number(supplierId)||0,supplierName:suppliers.find(s=>s.id===Number(supplierId))?.name||newInvoice.newSupplierName||'',acceptedBy:newInvoice.acceptedBy||user.name,location:newInvoice.location,project:newInvoice.project,vat:newInvoice.vat,photoUrl,photos:newInvoice.photos||[],items:validItems,totalBase:vatCalc.base,totalVat:vatCalc.vat,totalWithVat:vatCalc.total,status:'Принята',addedBy:user.name};
    await fetch(API+'/warehouse-invoices',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...inv,project:newInvoice.location!=='Основной склад'?newInvoice.location:''})});
    notify('Накладная №'+newInvoice.number+' принята','invoice');
    addActivity('Принята накладная №'+newInvoice.number);
    await loadAll();
    setNewInvoice({number:'',date:'',supplierId:'',isNewSupplier:false,newSupplierName:'',acceptedBy:'',location:'Основной склад',project:'',vat:'Без НДС',photos:[],items:[{name:'',quantity:'',unit:'шт',price:'',category:''}]});
    setShowForm(false);
    alert('Накладная принята!');
  };

  const applyWarehouseMovement = async () => {
    if (!newMovement.toLocation) { alert('Выберите куда переместить'); return; }
    const selected = newMovement.selectedMaterials||[];
    if (selected.length===0) { alert('Выберите материалы'); return; }
    for (const item of selected) {
      if (!item.quantity||Number(item.quantity)<=0) continue;
      await fetch(API+'/warehouse-movements',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({materialName:item.name,fromLocation:newMovement.fromLocation,toLocation:newMovement.toLocation,quantity:Number(item.quantity),unit:item.unit,date:new Date().toISOString().split('T')[0],createdBy:user.name,notes:newMovement.notes})});
      if (newMovement.fromLocation==='Основной склад') {
        const mat = warehouseMain.find(m=>m.name===item.name);
        if (mat) await fetch(API+'/warehouse-main/'+mat.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...mat,quantity:Math.max(0,mat.quantity-Number(item.quantity))})});
        const existing = materials.find(m=>m.name===item.name&&m.project===newMovement.toLocation);
        if (existing) await fetch(API+'/materials/'+existing.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...existing,quantity:existing.quantity+Number(item.quantity)})});
        else await fetch(API+'/materials',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:item.name,unit:item.unit,quantity:Number(item.quantity),price:item.price||0,minQuantity:0,project:newMovement.toLocation,category:item.category||''})});
      } else {
        const mat = materials.find(m=>m.name===item.name&&m.project===newMovement.fromLocation);
        if (mat) await fetch(API+'/materials/'+mat.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...mat,quantity:Math.max(0,mat.quantity-Number(item.quantity))})});
        if (newMovement.toLocation==='Основной склад') {
          const existing = warehouseMain.find(m=>m.name===item.name);
          if (existing) await fetch(API+'/warehouse-main/'+existing.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...existing,quantity:existing.quantity+Number(item.quantity)})});
          else await fetch(API+'/warehouse-main',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:item.name,unit:item.unit,quantity:Number(item.quantity),price:mat?.price||0,minQuantity:0,category:mat?.category||''})});
        } else {
          const existing = materials.find(m=>m.name===item.name&&m.project===newMovement.toLocation);
          if (existing) await fetch(API+'/materials/'+existing.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...existing,quantity:existing.quantity+Number(item.quantity)})});
          else await fetch(API+'/materials',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:item.name,unit:item.unit,quantity:Number(item.quantity),price:mat?.price||0,minQuantity:0,project:newMovement.toLocation,category:mat?.category||''})});
        }
      }
    }
    notify('Перемещение выполнено','material');
    await loadAll();
    setNewMovement({materialName:'',fromLocation:'Основной склад',toLocation:'',quantity:'',unit:'шт',notes:'',selectedMaterials:[]});
  };

  const buildMovementDoc = (movement, items) => {
    const req = companyRequisites||{};
    let html = '<h2 style="text-align:center">НАКЛАДНАЯ НА ВНУТРЕННЕЕ ПЕРЕМЕЩЕНИЕ (М-11)</h2>';
    html += '<p style="text-align:center">'+(req.fullName||req.shortName||companyName||'_____')+'</p>';
    html += '<table><tr><th>Откуда</th><td>'+movement.fromLocation+'</td><th>Куда</th><td>'+movement.toLocation+'</td></tr>';
    html += '<tr><th>Дата</th><td>'+new Date().toLocaleDateString('ru-RU')+'</td><th>Кто отправил</th><td>'+user.name+'</td></tr></table>';
    html += '<table><tr><th>N</th><th>Наименование</th><th>Ед.</th><th>Кол-во</th><th>Принял</th></tr>';
    items.forEach((item,i) => { html += '<tr><td>'+(i+1)+'</td><td>'+item.name+'</td><td>'+item.unit+'</td><td>'+item.quantity+'</td><td style="min-width:120px"></td></tr>'; });
    html += '</table><div class="signatures"><div class="sig"><div class="sig-line">Отпустил: '+user.name+'</div></div><div class="sig"><div class="sig-line">Принял: _______________</div></div><div class="sig"><div class="sig-line">Водитель: _______________</div></div></div>';
    return html;
  };

  const buildInventoryDoc = (inv, items) => {
    const req = companyRequisites||{};
    const totalShortage = items.filter(i=>i.difference<0).reduce((s,i)=>s+Math.abs(i.difference)*i.price,0);
    const totalSurplus = items.filter(i=>i.difference>0).reduce((s,i)=>s+i.difference*i.price,0);
    let html = '<h2 style="text-align:center">АКТ ИНВЕНТАРИЗАЦИИ № '+inv.id+'</h2>';
    html += '<p style="text-align:center">'+(req.fullName||req.shortName||companyName||'_____')+'</p>';
    html += '<table><tr><th>Объект</th><td>'+inv.project+'</td></tr><tr><th>Дата</th><td>'+inv.date+'</td></tr><tr><th>Провёл</th><td>'+(inv.created_by||inv.createdBy||'')+'</td></tr></table>';
    html += '<table><tr><th>N</th><th>Наименование</th><th>Ед.</th><th>По учёту</th><th>Факт</th><th>Разница</th><th>Цена</th><th>Сумма</th></tr>';
    items.forEach((item,i) => {
      const sum = Math.abs(item.difference||0)*Number(item.price||0);
      html += '<tr><td>'+(i+1)+'</td><td>'+item.materialName+'</td><td>'+item.unit+'</td><td>'+item.expected+'</td><td>'+item.actual+'</td><td style="color:'+(item.difference<0?'red':item.difference>0?'green':'black')+'">'+(item.difference>0?'+':'')+item.difference+'</td><td>'+Number(item.price||0).toLocaleString()+'</td><td>'+(item.difference!==0?sum.toLocaleString():'0')+'</td></tr>';
    });
    html += '</table><p><b>Итого недостача: '+totalShortage.toLocaleString()+' руб.</b></p><p><b>Итого излишек: '+totalSurplus.toLocaleString()+' руб.</b></p>';
    html += '<div class="signatures"><div class="sig"><div class="sig-line">Директор<br/>'+(req.directorName||'')+'</div></div><div class="sig"><div class="sig-line">Прораб</div></div><div class="sig"><div class="sig-line">Кладовщик</div></div><div class="sig"><div class="sig-line">Мастер</div></div></div>';
    return html;
  };

  const buildJPRContent = (projectName) => {
    const works = workJournal.filter(j=>j.project===projectName&&j.status==='Подтверждено');
    const project = projects.find(p=>p.name===projectName)||{};
    const req = companyRequisites||{};
    const orgName = req.fullName||req.shortName||companyName||'_____';
    const itr = users.filter(u=>['прораб','главный_инженер','стройконтроль'].includes(u.role));
    const acts = hiddenActs.filter(a=>a.projectName===projectName);
    const inspections = (materialInspections||[]).filter(mi=>mi.projectName===projectName);
    const prescs = (prescriptionsList||[]).filter(pr=>pr.projectName===projectName);
    const tb = (tbJournal||[]).filter(t=>t.project===projectName);
    const cables = (cableJournal||[]).filter(c=>c.projectName===projectName);
    const byDate = {};
    works.forEach(w => {
      if (!byDate[w.date]) byDate[w.date] = {};
      if (!byDate[w.date][w.masterName]) byDate[w.date][w.masterName] = [];
      byDate[w.date][w.masterName].push(w);
    });
    let html = '<style>'
      + '.jpr-title{text-align:center;font-weight:700;font-size:15px;margin:14px 0 4px}'
      + '.jpr-sub{text-align:center;font-size:12px;margin:0 0 16px;color:#444}'
      + '.jpr-section{margin-top:18px;border-top:1.5px solid #333;padding-top:8px}'
      + '.jpr-section h3{font-size:13px;margin:4px 0 8px;font-weight:700;color:#111}'
      + '.jpr-table{border-collapse:collapse;width:100%;font-size:11px;margin:6px 0}'
      + '.jpr-table th,.jpr-table td{border:1px solid #555;padding:4px 6px;vertical-align:top}'
      + '.jpr-table th{background:#f3f4f6;font-weight:600}'
      + '.jpr-row{display:grid;grid-template-columns:200px 1fr;gap:4px 10px;font-size:11px;margin:4px 0}'
      + '.jpr-sigs{margin-top:24px;display:grid;grid-template-columns:1fr 1fr;gap:30px}'
      + '.jpr-sig-line{border-bottom:1px solid #333;min-height:18px;font-size:12px;font-weight:600}'
      + '.jpr-sig-sub{font-size:9px;color:#555;margin-top:2px}'
      + '</style>';
    // Титульный лист
    html += '<div class="jpr-title">ОБЩИЙ ЖУРНАЛ РАБОТ</div>';
    html += '<div class="jpr-sub">по форме РД-11-05-2007 «Порядок ведения общего и (или) специального журнала учёта выполнения работ при строительстве»</div>';
    html += '<div class="jpr-row"><span><b>Объект капитального строительства:</b></span><span>'+(projectName||'____________')+'</span></div>';
    html += '<div class="jpr-row"><span><b>Местоположение:</b></span><span>'+(project.address||project.city||'____________')+'</span></div>';
    html += '<div class="jpr-row"><span><b>Застройщик (тех. заказчик):</b></span><span>'+(project.client||'____________')+'</span></div>';
    html += '<div class="jpr-row"><span><b>Лицо, осуществляющее строительство:</b></span><span>'+orgName+'</span></div>';
    html += '<div class="jpr-row"><span><b>Срок строительства:</b></span><span>'+(project.startDate||'__.__.____')+' — '+(project.deadline||'__.__.____')+'</span></div>';
    html += '<div class="jpr-row"><span><b>Дата составления журнала:</b></span><span>'+new Date().toLocaleDateString('ru-RU')+'</span></div>';
    // Раздел 1: Список ИТР
    html += '<div class="jpr-section"><h3>Раздел 1. Список инженерно-технического персонала, занятых строительством</h3>';
    html += '<table class="jpr-table"><tr><th>№</th><th>ФИО</th><th>Должность</th><th>Период работы</th></tr>';
    itr.forEach((u,i)=>{html+='<tr><td>'+(i+1)+'</td><td>'+(u.name||'')+'</td><td>'+(u.role||'')+'</td><td>—</td></tr>';});
    if (itr.length===0) html += '<tr><td colspan="4" style="text-align:center;color:#888">(не указаны)</td></tr>';
    html += '</table></div>';
    // Раздел 2: Сведения о стройконтроле застройщика
    html += '<div class="jpr-section"><h3>Раздел 2. Сведения о стройконтроле застройщика/заказчика</h3>';
    html += '<p style="font-size:11px;color:#444">Технический надзор / стройконтроль осуществляется лицами с подписями в АОСР и актах осмотра. См. раздел 3 настоящего журнала и Раздел 6 (АОСР).</p></div>';
    // Раздел 3: Выполнение работ
    html += '<div class="jpr-section"><h3>Раздел 3. Сведения о выполнении работ (по датам)</h3>';
    if (Object.keys(byDate).length === 0) {
      html += '<p style="color:#888;font-size:11px;text-align:center">Подтверждённых записей по проекту нет</p>';
    } else {
      Object.keys(byDate).sort().forEach(date => {
        const weather = weatherLog.find(w=>w.projectName===projectName&&w.date===date);
        html += '<p style="font-weight:700;margin-top:8px">'+date+(weather?' · 🌤 '+weather.condition+', '+weather.temperature+'°C':'')+'</p>';
        Object.keys(byDate[date]).forEach(masterName => {
          html += '<p style="font-size:11px;margin:3px 0;color:#444">Исполнитель: <b>'+masterName+'</b></p>';
          html += '<table class="jpr-table"><tr><th>№</th><th>Вид работ</th><th>Раздел сметы</th><th>Ед.</th><th>Кол-во</th><th>Нормативы</th><th>ИТР</th><th>Принял</th></tr>';
          byDate[date][masterName].forEach((wk,i)=>{html+='<tr><td>'+(i+1)+'</td><td>'+(wk.description||'')+(wk.unexpectedWorkId?' <b>🆕</b>':'')+(wk.hiddenWork?' <b>🔒</b>':'')+'</td><td>'+(wk.sectionName||'—')+'</td><td>'+(wk.unit||'')+'</td><td>'+(wk.quantity||0)+'</td><td>'+(wk.normatives||'—')+'</td><td>'+(wk.responsibleItr||'—')+'</td><td>'+(wk.confirmedBy||'')+'</td></tr>';});
          html += '</table>';
        });
      });
    }
    html += '</div>';
    // Раздел 4: Стройконтроль подрядчика
    html += '<div class="jpr-section"><h3>Раздел 4. Сведения о стройконтроле лица, осуществляющего строительство</h3>';
    html += '<p style="font-size:11px;color:#444">Контроль качества осуществляется ИТР генподрядчика. Зафиксированные предписания: '+prescs.length+' (см. Раздел 7).</p></div>';
    // Раздел 5: Входной контроль материалов
    html += '<div class="jpr-section"><h3>Раздел 5. Сведения о входном контроле материалов</h3>';
    if (inspections.length === 0) {
      html += '<p style="color:#888;font-size:11px;text-align:center">Записей входного контроля нет (ведётся в отдельном журнале СП 48.13330.2019)</p>';
    } else {
      html += '<table class="jpr-table"><tr><th>№</th><th>Дата</th><th>Материал</th><th>Поставщик</th><th>Партия</th><th>Сертификат</th><th>Результат</th></tr>';
      inspections.slice(0,30).forEach((mi,i)=>{html+='<tr><td>'+(i+1)+'</td><td>'+(mi.receivedAt||'')+'</td><td>'+(mi.materialName||'')+'</td><td>'+(mi.supplier||'')+'</td><td>'+(mi.batchNumber||'—')+'</td><td>'+(mi.certificateNumber||mi.passportNumber||'—')+'</td><td>'+(mi.visualInspectionResult||(mi.inspected?'Проверено':'—'))+'</td></tr>';});
      html += '</table>';
    }
    html += '</div>';
    // Раздел 6: Спецжурналы
    html += '<div class="jpr-section"><h3>Раздел 6. Перечень специальных журналов и актов</h3>';
    html += '<table class="jpr-table"><tr><th>Документ</th><th>Записей</th><th>Норматив</th></tr>';
    html += '<tr><td>АОСР — акты освидетельствования скрытых работ</td><td>'+acts.length+' ('+acts.filter(a=>a.status==='Подписан').length+' подписано)</td><td>СНиП 12-01-2004</td></tr>';
    html += '<tr><td>Журнал входного контроля материалов</td><td>'+inspections.length+'</td><td>СП 48.13330.2019</td></tr>';
    html += '<tr><td>Журнал кабельной продукции</td><td>'+cables.length+'</td><td>СП 76.13330, ПУЭ</td></tr>';
    html += '<tr><td>Журнал инструктажей ТБ</td><td>'+tb.length+'</td><td>ГОСТ 12.0.004-2015</td></tr>';
    html += '</table></div>';
    // Раздел 7: Замечания и предписания
    html += '<div class="jpr-section"><h3>Раздел 7. Сведения о замечаниях и предписаниях контролирующих органов</h3>';
    if (prescs.length === 0) {
      html += '<p style="color:#888;font-size:11px;text-align:center">Предписаний нет</p>';
    } else {
      html += '<table class="jpr-table"><tr><th>№</th><th>Дата</th><th>Кем выдано</th><th>Описание нарушения</th><th>Срок</th><th>Статус</th></tr>';
      prescs.forEach((pr,i)=>{html+='<tr><td>'+(i+1)+'</td><td>'+(pr.deadline||'')+'</td><td>'+(pr.issuedBy||'')+' ('+(pr.issuedByRole||'')+')</td><td>'+(pr.violation||pr.description||'')+'</td><td>'+(pr.deadline||'')+'</td><td>'+(pr.status||'')+'</td></tr>';});
      html += '</table>';
    }
    html += '</div>';
    // Подписи
    html += '<div class="jpr-sigs">';
    html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Ответственный за ведение журнала (производитель работ):</div><div class="jpr-sig-line"></div><div class="jpr-sig-sub">(должность, ФИО, подпись)</div></div>';
    html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Представитель застройщика (технадзора):</div><div class="jpr-sig-line"></div><div class="jpr-sig-sub">(должность, ФИО, подпись)</div></div>';
    html += '</div>';
    html += '<p style="margin-top:18px;font-size:10px;color:#666;text-align:center">Журнал ведётся в соответствии с РД-11-05-2007 и СП 48.13330.2019 «Организация строительства». Является обязательным документом исполнительной документации.</p>';
    return html;
  };

  const buildActContent = (act) => {
    const profile = masterProfiles.find(p=>p.userId===act.masterId);
    const req = companyRequisites||{};
    const companyNameDoc = req.fullName||req.shortName||companyName||'_____';
    const mw = workJournal.filter(j=>j.masterId===act.masterId&&j.project===act.project&&j.status==='Подтверждено');
    const payments = actPayments.filter(p=>p.actId===act.id);
    const toolDeductions = tools.filter(t=>t.masterName===act.masterName&&t.issueType==='В счёт зарплаты').reduce((s,t)=>s+t.cost,0);
    let html = '<h2 style="text-align:center">АКТ ВЫПОЛНЕННЫХ РАБОТ № '+act.id+'</h2>';
    html += '<p>Заказчик: <b>'+companyNameDoc+'</b> | Исполнитель: <b>'+act.masterName+'</b></p>';
    html += '<p>Объект: <b>'+act.project+'</b> | Период: '+act.periodStart+' — '+act.periodEnd+'</p>';
    if (profile) html += '<p>ИНН: '+profile.inn+' | '+profile.bankName+' | Р/с: '+profile.bankAccount+'</p>';
    html += '<table><tr><th>N</th><th>Работа</th><th>Помещение</th><th>Ед.</th><th>Кол-во</th><th>Цена</th><th>Сумма</th></tr>';
    mw.forEach((wk,i) => { html += '<tr><td>'+(i+1)+'</td><td>'+wk.description+'</td><td>'+(wk.roomName||'—')+'</td><td>'+wk.unit+'</td><td>'+wk.quantity+'</td><td>'+(wk.pricePerUnit||0).toLocaleString()+'</td><td>'+(wk.total||0).toLocaleString()+'</td></tr>'; });
    const totalAmt=act.totalAmount||0; const paidAmt=act.paidAmount||0;
    html += '<tr><td colspan="6"><b>ИТОГО начислено:</b></td><td><b>'+totalAmt.toLocaleString()+' руб.</b></td></tr>';
    if (toolDeductions>0) html += '<tr><td colspan="6">Удержания (инструмент):</td><td style="color:red">-'+toolDeductions.toLocaleString()+' руб.</td></tr>';
    html += '<tr><td colspan="6"><b>К выплате:</b></td><td><b>'+(totalAmt-toolDeductions).toLocaleString()+' руб.</b></td></tr>';
    if (payments.length>0) {
      html += '<tr><td colspan="7"><b>История оплат:</b></td></tr>';
      payments.forEach(p => { html += '<tr><td colspan="3">'+p.date+'</td><td colspan="2">'+p.paymentType+'</td><td>'+p.paidBy+'</td><td>'+p.amount.toLocaleString()+' руб.</td></tr>'; });
    }
    html += '<tr><td colspan="6">Оплачено:</td><td>'+paidAmt.toLocaleString()+' руб.</td></tr>';
    html += '<tr><td colspan="6"><b>Остаток:</b></td><td><b style="color:red">'+(totalAmt-toolDeductions-paidAmt).toLocaleString()+' руб.</b></td></tr></table>';
    html += '<div class="signatures"><div class="sig"><div class="sig-line">Выполнил<br/>'+act.masterName+'</div></div><div class="sig"><div class="sig-line">Принял (прораб)</div></div><div class="sig"><div class="sig-line">'+companyNameDoc+'<br/>'+(req.directorName||'')+'</div></div></div>';
    return html;
  };

  const showKS2 = async (project) => {
    const bcs = brigadeContracts.filter(bc=>bc.projectName===project.name);
    let allBrigadeItems = [];
    for(const bc of bcs){
      const res = await fetch(API+'/brigade-contract-items/'+bc.id);
      const items = await res.json();
      allBrigadeItems = [...allBrigadeItems, ...items.filter(i=>i.doneQuantity>0)];
    }
    const pw = workJournal.filter(j=>j.project===project.name&&j.status==='Подтверждено');
    const sourceItems = allBrigadeItems.length>0
      ? allBrigadeItems.map(item=>({description:item.name,unit:item.unit,quantity:item.doneQuantity,pricePerUnit:Number(item.priceSmeta||0),total:Math.round(item.doneQuantity*Number(item.priceSmeta||0))}))
      : pw.filter(j=>!j.unexpectedWorkId);
    const unexpectedItems = pw.filter(j=>j.unexpectedWorkId).map(j=>({description:j.description,unit:j.unit,quantity:j.quantity,pricePerUnit:Number(j.pricePerUnit||0),total:Math.round(Number(j.quantity||0)*Number(j.pricePerUnit||0))}));
    const req = companyRequisites||{};
    let html = '<h2 style="text-align:center">УНИФИЦИРОВАННАЯ ФОРМА КС-2</h2><h3 style="text-align:center">АКТ О ПРИЁМКЕ ВЫПОЛНЕННЫХ РАБОТ</h3>';
    html += '<table><tr><th>Организация</th><td>'+(req.fullName||companyName||'')+'</td><th>Объект</th><td>'+project.name+'</td></tr></table>';
    html += '<h3>Раздел 1. Основные работы (по смете)</h3>';
    html += '<table><tr><th>N</th><th>Наименование работ</th><th>Ед.</th><th>Кол-во</th><th>Цена</th><th>Сумма</th></tr>';
    sourceItems.forEach((wk,i)=>{html+='<tr><td>'+(i+1)+'</td><td>'+wk.description+'</td><td>'+wk.unit+'</td><td>'+wk.quantity+'</td><td>'+Number(wk.pricePerUnit).toLocaleString()+'</td><td>'+Number(wk.total).toLocaleString()+'</td></tr>';});
    const mainTotal=sourceItems.reduce((s,wk)=>s+Number(wk.total||0),0);
    html += '<tr><td colspan="5"><b>Итого по разделу 1:</b></td><td><b>'+mainTotal.toLocaleString()+' руб.</b></td></tr></table>';
    if(unexpectedItems.length>0){
      html += '<h3>Раздел 2. Дополнительные работы (доп.соглашения)</h3>';
      html += '<table><tr><th>N</th><th>Наименование работ</th><th>Ед.</th><th>Кол-во</th><th>Цена</th><th>Сумма</th></tr>';
      unexpectedItems.forEach((wk,i)=>{html+='<tr><td>'+(i+1)+'</td><td>'+wk.description+'</td><td>'+wk.unit+'</td><td>'+wk.quantity+'</td><td>'+Number(wk.pricePerUnit).toLocaleString()+'</td><td>'+Number(wk.total).toLocaleString()+'</td></tr>';});
      const unxTotal=unexpectedItems.reduce((s,wk)=>s+Number(wk.total||0),0);
      html += '<tr><td colspan="5"><b>Итого по разделу 2:</b></td><td><b>'+unxTotal.toLocaleString()+' руб.</b></td></tr></table>';
      html += '<p style="text-align:right;font-size:14px"><b>ВСЕГО к оплате: '+(mainTotal+unxTotal).toLocaleString()+' руб.</b></p>';
    } else {
      html += '<p style="text-align:right;font-size:14px"><b>ВСЕГО к оплате: '+mainTotal.toLocaleString()+' руб.</b></p>';
    }
    html += '<div class="signatures"><div class="sig"><div class="sig-line">Сдал: '+(req.directorName||'')+'</div></div><div class="sig"><div class="sig-line">Принял:</div></div></div>';
    showPreview(html,'КС-2 — '+project.name);
  };

  const buildKS2Content = (project) => {
    const pw = workJournal.filter(j=>j.project===project.name&&j.status==='Подтверждено');
    const bcs = brigadeContracts.filter(bc=>bc.projectName===project.name);
    const brigadeItems = brigadeContractItems.filter(item=>bcs.find(bc=>bc.id===item.contractId)&&item.doneQuantity>0);
    const req = companyRequisites||{};
    let html = '<h2 style="text-align:center">УНИФИЦИРОВАННАЯ ФОРМА № КС-2</h2><h3 style="text-align:center">АКТ О ПРИЁМКЕ ВЫПОЛНЕННЫХ РАБОТ</h3>';
    html += '<table><tr><th>Организация</th><td>'+(req.fullName||req.shortName||companyName||'_____')+'</td><th>Объект</th><td>'+project.name+'</td></tr>';
    if (req.inn) html += '<tr><th>ИНН</th><td>'+req.inn+'</td><th>КПП</th><td>'+(req.kpp||'')+'</td></tr>';
    html += '</table>';
    html += '<table><tr><th>N</th><th>Наименование работ</th><th>Помещение</th><th>Ед.</th><th>Кол-во</th><th>Цена</th><th>Сумма</th></tr>';
    const allItems = brigadeItems.length>0 ? brigadeItems.map(item=>({description:item.name,unit:item.unit,quantity:item.doneQuantity,pricePerUnit:Number(item.priceSmeta||item.price_smeta||0),total:Math.round(item.doneQuantity*Number(item.priceSmeta||item.price_smeta||0)),roomName:''})) : pw;
    allItems.forEach((wk,i) => { html += '<tr><td>'+(i+1)+'</td><td>'+wk.description+'</td><td>'+(wk.roomName||'—')+'</td><td>'+wk.unit+'</td><td>'+wk.quantity+'</td><td>'+(wk.pricePerUnit||0).toLocaleString()+'</td><td>'+(wk.total||0).toLocaleString()+'</td></tr>'; });
    html += '<tr><td colspan="6"><b>ИТОГО:</b></td><td><b>'+allItems.reduce((s,wk)=>s+(wk.total||0),0).toLocaleString()+' руб.</b></td></tr></table>';
    html += '<div class="signatures"><div class="sig"><div class="sig-line">Сдал<br/>'+(req.directorName||'')+'</div></div><div class="sig"><div class="sig-line">Принял</div></div></div>';
    return html;
  };

  const buildKS3Content = (project) => {
    const cat = expByCategory(project.name);
    const total = Object.values(cat).reduce((s,v)=>s+v,0);
    const req = companyRequisites||{};
    let html = '<h2 style="text-align:center">УНИФИЦИРОВАННАЯ ФОРМА № КС-3</h2>';
    html += '<p>Организация: '+(req.fullName||req.shortName||companyName||'_____')+'</p>';
    html += '<table><tr><th>N</th><th>Наименование</th><th>Сумма (руб.)</th></tr>';
    EXPENSE_CATEGORIES.forEach((c,i) => { html += '<tr><td>'+(i+1)+'</td><td>'+c.label+'</td><td>'+cat[c.id].toLocaleString()+'</td></tr>'; });
    html += '<tr><td colspan="2"><b>ИТОГО:</b></td><td><b>'+total.toLocaleString()+'</b></td></tr></table>';
    html += '<div class="signatures"><div class="sig"><div class="sig-line">Подрядчик<br/>'+(req.directorName||'')+'</div></div><div class="sig"><div class="sig-line">Заказчик</div></div></div>';
    return html;
  };

  const buildContractContent = (profile, contract) => {
    const type = contract.contractType || 'ГПХ';
    const fn = CONTRACTS[type] || CONTRACTS['ГПХ'];
    return fn(companyRequisites&&companyRequisites.fullName?companyRequisites:companyName, profile, contract);
  };

  const buildHiddenActContent = (act) => {
    const req = companyRequisites||{};
    const orgName = req.fullName||req.shortName||companyName||'_____';
    const fmtDate = (d) => {
      if(!d) return '«___» __________ 20__ г.';
      const dt = new Date(d);
      if(isNaN(dt)) return d;
      const months=['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'];
      return '«'+String(dt.getDate()).padStart(2,'0')+'» '+months[dt.getMonth()]+' '+dt.getFullYear()+' г.';
    };
    const photoCnt = (act.photos||'').split(',').filter(Boolean).length;
    const certCnt  = (act.certificates||'').split(',').filter(Boolean).length;
    const sig = (label, name, date) => (
      '<div class="hwa-sig">'+
        '<div class="hwa-sig-label">'+label+'</div>'+
        '<div class="hwa-sig-line">'+(name||'')+'</div>'+
        '<div class="hwa-sig-sub">(должность, ФИО, подпись)</div>'+
        '<div class="hwa-sig-date">'+(date?fmtDate(date):'«___» __________ 20__ г.')+'</div>'+
      '</div>'
    );
    const concl = act.conclusion || 'Работы выполнены в соответствии с проектной документацией, требованиями технических регламентов, СНиП и ТУ. Разрешается производство последующих работ.';
    let html = '';
    html += '<style>'+
      '.hwa-meta{margin:6px 0;font-size:12px}'+
      '.hwa-title{text-align:center;font-weight:700;font-size:14px;margin:18px 0 4px}'+
      '.hwa-sub{text-align:center;font-size:13px;margin:0 0 18px}'+
      '.hwa-row{display:flex;justify-content:space-between;font-size:12px;margin:4px 0}'+
      '.hwa-item{margin:8px 0;font-size:12px;line-height:1.5}'+
      '.hwa-item b{display:inline-block;min-width:18px}'+
      '.hwa-val{display:inline-block;border-bottom:1px solid #333;min-width:60%;padding:1px 4px}'+
      '.hwa-block{border-top:1px solid #333;margin-top:6px;padding-top:8px;font-size:12px;line-height:1.5}'+
      '.hwa-sigs{margin-top:30px;display:grid;grid-template-columns:1fr 1fr;gap:20px}'+
      '.hwa-sig{font-size:11px}'+
      '.hwa-sig-label{font-weight:600;margin-bottom:30px}'+
      '.hwa-sig-line{border-bottom:1px solid #333;min-height:18px;font-size:12px;font-weight:600}'+
      '.hwa-sig-sub{font-size:10px;color:#555;margin-top:2px}'+
      '.hwa-sig-date{margin-top:8px;font-size:11px}'+
      '@media print{.hwa-title{font-size:13px}}'+
    '</style>';
    html += '<div class="hwa-meta"><b>'+orgName+'</b></div>';
    html += '<div class="hwa-title">АКТ</div>';
    html += '<div class="hwa-sub">освидетельствования скрытых работ № <b>'+act.actNumber+'</b></div>';
    html += '<div class="hwa-row"><span>'+(act.city?act.city:'г. ____________')+'</span><span>'+fmtDate(act.workDate||new Date().toISOString().slice(0,10))+'</span></div>';
    html += '<div class="hwa-item"><b>Объект капитального строительства:</b> <span class="hwa-val">'+(act.projectName||'')+'</span></div>';
    html += '<div class="hwa-item"><b>Представители:</b><br/>';
    html += '— застройщика (технического заказчика): <span class="hwa-val">'+(act.signedCustomer||'')+'</span><br/>';
    html += '— лица, осуществляющего строительный контроль: <span class="hwa-val">'+(act.signedSupervisor||'')+'</span><br/>';
    html += '— лица, осуществляющего строительство (генподрядчик): <span class="hwa-val">'+(act.signedContractor||'')+'</span><br/>';
    html += '— лица, выполнившего работы, подлежащие освидетельствованию: <span class="hwa-val">'+(act.signedSubcontractor||act.brigade||'')+'</span>';
    html += '</div>';
    html += '<div class="hwa-item">произвели осмотр работ, выполненных <span class="hwa-val">'+(act.brigade||'')+'</span>, и составили настоящий акт о нижеследующем:</div>';
    html += '<div class="hwa-item"><b>1.</b> К освидетельствованию предъявлены следующие работы: <span class="hwa-val">'+(act.workName||'')+'</span> в объёме <b>'+act.quantity+' '+(act.unit||'')+'</b>'+(act.sectionName?' (раздел сметы «'+act.sectionName+'»)':'')+'.</div>';
    html += '<div class="hwa-item"><b>2.</b> Работы выполнены по проектной документации: <span class="hwa-val">'+(act.projectDocs||'_______________________________________')+'</span></div>';
    html += '<div class="hwa-item"><b>3.</b> При выполнении работ применены: <br/><div class="hwa-block">'+(act.materialsUsed||'_______________________________________').replace(/\n/g,'<br/>')+'</div></div>';
    html += '<div class="hwa-item"><b>4.</b> Предъявлены документы, подтверждающие соответствие работ предъявляемым к ним требованиям: фотофиксация скрытых работ — <b>'+photoCnt+'</b> шт.; сертификаты, паспорта, протоколы испытаний — <b>'+certCnt+'</b> шт. (прилагаются к настоящему акту).</div>';
    html += '<div class="hwa-item"><b>5.</b> Освидетельствованы скрытые работы: <span class="hwa-val">'+(act.workName||'')+'</span></div>';
    html += '<div class="hwa-item"><b>6.</b> Дата окончания работ: <b>'+fmtDate(act.workDate)+'</b></div>';
    html += '<div class="hwa-item"><b>7.</b> Заключение:<br/><div class="hwa-block">'+concl.replace(/\n/g,'<br/>')+'</div></div>';
    html += '<div class="hwa-sigs">';
    html += sig('Представитель застройщика (технического заказчика):',act.signedCustomer,act.signedCustomerAt);
    html += sig('Представитель лица, осуществляющего строительный контроль:',act.signedSupervisor,act.signedSupervisorAt);
    html += sig('Представитель лица, осуществляющего строительство (генподрядчик):',act.signedContractor,act.signedContractorAt);
    html += sig('Представитель лица, выполнившего работы (субподрядчик):',act.signedSubcontractor||act.brigade,act.signedSubcontractorAt);
    html += '</div>';
    html += '<p style="margin-top:30px;font-size:10px;color:#555;text-align:center">Форма составлена согласно СНиП 12-01-2004 (Приложение 3). Документ сопровождает приёмку скрытых работ перед их закрытием последующими конструкциями.</p>';
    return html;
  };

  const buildWorkJournalContent = (records, projectName, dateFrom, dateTo) => {
    const req = companyRequisites||{};
    const orgName = req.fullName||req.shortName||companyName||'_____';
    const project = projects.find(p=>p.name===projectName)||{};
    const fmtDate = (d) => { if(!d) return ''; const dt=new Date(d); if(isNaN(dt)) return d; return ('0'+dt.getDate()).slice(-2)+'.'+('0'+(dt.getMonth()+1)).slice(-2)+'.'+dt.getFullYear(); };
    const sum = records.reduce((s,r)=>s+Number(r.total||0),0);
    let html = '<style>'
      + '.wj-meta{margin:6px 0;font-size:11px}'
      + '.wj-title{text-align:center;font-weight:700;font-size:14px;margin:14px 0 4px}'
      + '.wj-sub{text-align:center;font-size:12px;margin:0 0 14px;color:#444}'
      + '.wj-info{display:grid;grid-template-columns:160px 1fr;gap:4px 10px;font-size:11px;margin:10px 0}'
      + '.wj-tbl{border-collapse:collapse;width:100%;font-size:10px;margin-top:10px}'
      + '.wj-tbl th,.wj-tbl td{border:1px solid #333;padding:4px 5px;vertical-align:top}'
      + '.wj-tbl th{background:#f3f4f6;font-weight:600;text-align:center}'
      + '.wj-tbl td.num{text-align:right;white-space:nowrap}'
      + '.wj-foot{margin-top:18px;font-size:11px;color:#444}'
      + '.wj-sigs{margin-top:30px;display:grid;grid-template-columns:1fr 1fr;gap:30px}'
      + '.wj-sig-label{font-weight:600;margin-bottom:30px;font-size:11px}'
      + '.wj-sig-line{border-bottom:1px solid #333;min-height:18px;font-size:12px;font-weight:600}'
      + '.wj-sig-sub{font-size:9px;color:#555;margin-top:2px}'
      + '</style>';
    html += '<div class="wj-meta"><b>'+orgName+'</b></div>';
    html += '<div class="wj-title">ЖУРНАЛ УЧЁТА ВЫПОЛНЕННЫХ РАБОТ</div>';
    html += '<div class="wj-sub">(унифицированная форма № КС-6а, ОКУД 0322005)</div>';
    html += '<div class="wj-info">';
    html += '<span>Заказчик:</span><b>'+(project.client||'____________')+'</b>';
    html += '<span>Подрядчик:</span><b>'+orgName+'</b>';
    html += '<span>Объект:</span><b>'+(projectName||'____________')+'</b>';
    html += '<span>Период:</span><b>'+(dateFrom?fmtDate(dateFrom):'__.__.____')+' — '+(dateTo?fmtDate(dateTo):'__.__.____')+'</b>';
    html += '</div>';
    html += '<table class="wj-tbl"><thead><tr>';
    html += '<th style="width:24px">№</th>';
    html += '<th style="width:60px">Дата</th>';
    html += '<th style="width:90px">Раздел сметы</th>';
    html += '<th>Наименование работ</th>';
    html += '<th style="width:36px">Ед.</th>';
    html += '<th style="width:46px">Объём</th>';
    html += '<th style="width:100px">Исполнитель</th>';
    html += '<th style="width:100px">Ответств. ИТР</th>';
    html += '<th style="width:80px">Погода</th>';
    html += '<th style="width:90px">Качество</th>';
    html += '<th style="width:80px">Стоимость, ₽</th>';
    html += '</tr></thead><tbody>';
    records.forEach((r,i)=>{
      html += '<tr>';
      html += '<td class="num">'+(i+1)+'</td>';
      html += '<td>'+fmtDate(r.date)+'</td>';
      html += '<td>'+(r.sectionName||'—')+'</td>';
      html += '<td>'+(r.description||'')+(r.hiddenWork?' <b>🔒</b>':'')+'</td>';
      html += '<td>'+(r.unit||'')+'</td>';
      html += '<td class="num">'+(r.quantity||0)+'</td>';
      html += '<td>'+(r.masterName||'—')+'</td>';
      html += '<td>'+(r.responsibleItr||'—')+'</td>';
      html += '<td>'+(r.weather||'—')+'</td>';
      html += '<td>'+(r.qualityStatus||r.status||'—')+'</td>';
      html += '<td class="num">'+Number(r.total||0).toLocaleString('ru-RU')+'</td>';
      html += '</tr>';
    });
    html += '<tr><td colspan="10" style="text-align:right;font-weight:700">ИТОГО, ₽:</td><td class="num" style="font-weight:700">'+sum.toLocaleString('ru-RU')+'</td></tr>';
    html += '</tbody></table>';
    html += '<div class="wj-foot">Журнал ведётся в соответствии с РД-11-05-2007 «Порядок ведения общего и (или) специального журналов учёта выполнения работ при строительстве» и СП 48.13330.2019 «Организация строительства».</div>';
    html += '<div class="wj-sigs">';
    html += '<div><div class="wj-sig-label">Должностное лицо, ответственное за совершение операций и правильность их оформления:</div><div class="wj-sig-line"></div><div class="wj-sig-sub">(должность, подпись, ФИО)</div></div>';
    html += '<div><div class="wj-sig-label">Представитель технического надзора заказчика:</div><div class="wj-sig-line"></div><div class="wj-sig-sub">(должность, подпись, ФИО)</div></div>';
    html += '</div>';
    return html;
  };

  const buildMaterialInspectionContent = (records, projectName, dateFrom, dateTo) => {
    const req = companyRequisites||{};
    const orgName = req.fullName||req.shortName||companyName||'_____';
    const project = projects.find(p=>p.name===projectName)||{};
    const fmtDate = (d) => { if(!d) return ''; const dt=new Date(d); if(isNaN(dt)) return d; return ('0'+dt.getDate()).slice(-2)+'.'+('0'+(dt.getMonth()+1)).slice(-2)+'.'+dt.getFullYear(); };
    let html = '<style>'
      + '.mic-meta{margin:6px 0;font-size:11px}'
      + '.mic-title{text-align:center;font-weight:700;font-size:14px;margin:14px 0 4px}'
      + '.mic-sub{text-align:center;font-size:12px;margin:0 0 14px;color:#444}'
      + '.mic-info{display:grid;grid-template-columns:160px 1fr;gap:4px 10px;font-size:11px;margin:10px 0}'
      + '.mic-tbl{border-collapse:collapse;width:100%;font-size:10px;margin-top:10px}'
      + '.mic-tbl th,.mic-tbl td{border:1px solid #333;padding:4px 5px;vertical-align:top}'
      + '.mic-tbl th{background:#f3f4f6;font-weight:600;text-align:center}'
      + '.mic-tbl td.num{text-align:right;white-space:nowrap}'
      + '.mic-foot{margin-top:18px;font-size:11px;color:#444}'
      + '.mic-sigs{margin-top:30px;display:grid;grid-template-columns:1fr 1fr;gap:30px}'
      + '.mic-sig-label{font-weight:600;margin-bottom:30px;font-size:11px}'
      + '.mic-sig-line{border-bottom:1px solid #333;min-height:18px;font-size:12px;font-weight:600}'
      + '.mic-sig-sub{font-size:9px;color:#555;margin-top:2px}'
      + '</style>';
    html += '<div class="mic-meta"><b>'+orgName+'</b></div>';
    html += '<div class="mic-title">ЖУРНАЛ ВХОДНОГО КОНТРОЛЯ МАТЕРИАЛОВ, КОНСТРУКЦИЙ И ИЗДЕЛИЙ</div>';
    html += '<div class="mic-sub">по СП 48.13330.2019 «Организация строительства», §7.1</div>';
    html += '<div class="mic-info">';
    html += '<span>Заказчик:</span><b>'+(project.client||'____________')+'</b>';
    html += '<span>Подрядчик:</span><b>'+orgName+'</b>';
    html += '<span>Объект:</span><b>'+(projectName||'____________')+'</b>';
    html += '<span>Период:</span><b>'+(dateFrom?fmtDate(dateFrom):'__.__.____')+' — '+(dateTo?fmtDate(dateTo):'__.__.____')+'</b>';
    html += '</div>';
    html += '<table class="mic-tbl"><thead><tr>';
    html += '<th style="width:24px">№</th>';
    html += '<th style="width:60px">Дата приёмки</th>';
    html += '<th>Наименование материала</th>';
    html += '<th style="width:36px">Ед.</th>';
    html += '<th style="width:50px">Кол-во</th>';
    html += '<th style="width:110px">Поставщик</th>';
    html += '<th style="width:70px">Партия №</th>';
    html += '<th style="width:80px">Паспорт №</th>';
    html += '<th style="width:80px">Сертификат №</th>';
    html += '<th style="width:80px">Протокол №</th>';
    html += '<th style="width:90px">Результат осмотра</th>';
    html += '<th style="width:90px">Проверил (ФИО)</th>';
    html += '<th style="width:60px">Дата осмотра</th>';
    html += '<th>Замечания</th>';
    html += '</tr></thead><tbody>';
    records.forEach((r,i)=>{
      html += '<tr>';
      html += '<td class="num">'+(i+1)+'</td>';
      html += '<td>'+fmtDate(r.receivedAt)+'</td>';
      html += '<td>'+(r.materialName||'')+'</td>';
      html += '<td>'+(r.unit||'')+'</td>';
      html += '<td class="num">'+(r.quantity||0)+'</td>';
      html += '<td>'+(r.supplier||'—')+'</td>';
      html += '<td>'+(r.batchNumber||'—')+'</td>';
      html += '<td>'+(r.passportNumber||'—')+'</td>';
      html += '<td>'+(r.certificateNumber||'—')+'</td>';
      html += '<td>'+(r.testProtocolNumber||'—')+'</td>';
      html += '<td>'+(r.visualInspectionResult||'—')+'</td>';
      html += '<td>'+(r.inspectorName||'—')+'</td>';
      html += '<td>'+fmtDate(r.inspectedAt)+'</td>';
      html += '<td>'+(r.remarks||'')+'</td>';
      html += '</tr>';
    });
    html += '</tbody></table>';
    html += '<div class="mic-foot">Журнал ведётся в соответствии с СП 48.13330.2019 «Организация строительства» и ГОСТ 24297-2013 «Верификация закупленной продукции. Организация и методы контроля».</div>';
    html += '<div class="mic-sigs">';
    html += '<div><div class="mic-sig-label">Ответственное за входной контроль лицо:</div><div class="mic-sig-line"></div><div class="mic-sig-sub">(должность, подпись, ФИО)</div></div>';
    html += '<div><div class="mic-sig-label">Представитель технического надзора заказчика:</div><div class="mic-sig-line"></div><div class="mic-sig-sub">(должность, подпись, ФИО)</div></div>';
    html += '</div>';
    return html;
  };

  const buildCableJournalContent = (records, projectName, dateFrom, dateTo) => {
    const req = companyRequisites||{};
    const orgName = req.fullName||req.shortName||companyName||'_____';
    const project = projects.find(p=>p.name===projectName)||{};
    const fmtDate = (d) => { if(!d) return ''; const dt=new Date(d); if(isNaN(dt)) return d; return ('0'+dt.getDate()).slice(-2)+'.'+('0'+(dt.getMonth()+1)).slice(-2)+'.'+dt.getFullYear(); };
    let html = '<style>'
      + '.cab-meta{margin:6px 0;font-size:11px}'
      + '.cab-title{text-align:center;font-weight:700;font-size:14px;margin:14px 0 4px}'
      + '.cab-sub{text-align:center;font-size:12px;margin:0 0 14px;color:#444}'
      + '.cab-info{display:grid;grid-template-columns:160px 1fr;gap:4px 10px;font-size:11px;margin:10px 0}'
      + '.cab-tbl{border-collapse:collapse;width:100%;font-size:10px;margin-top:10px}'
      + '.cab-tbl th,.cab-tbl td{border:1px solid #333;padding:4px 5px;vertical-align:top}'
      + '.cab-tbl th{background:#f3f4f6;font-weight:600;text-align:center}'
      + '.cab-tbl td.num{text-align:right;white-space:nowrap}'
      + '.cab-foot{margin-top:18px;font-size:11px;color:#444}'
      + '.cab-sigs{margin-top:30px;display:grid;grid-template-columns:1fr 1fr;gap:30px}'
      + '.cab-sig-label{font-weight:600;margin-bottom:30px;font-size:11px}'
      + '.cab-sig-line{border-bottom:1px solid #333;min-height:18px;font-size:12px;font-weight:600}'
      + '.cab-sig-sub{font-size:9px;color:#555;margin-top:2px}'
      + '</style>';
    html += '<div class="cab-meta"><b>'+orgName+'</b></div>';
    html += '<div class="cab-title">ЖУРНАЛ КАБЕЛЬНОЙ ПРОДУКЦИИ</div>';
    html += '<div class="cab-sub">по СП 76.13330 «Электротехнические устройства» и ПУЭ</div>';
    html += '<div class="cab-info">';
    html += '<span>Заказчик:</span><b>'+(project.client||'____________')+'</b>';
    html += '<span>Подрядчик:</span><b>'+orgName+'</b>';
    html += '<span>Объект:</span><b>'+(projectName||'____________')+'</b>';
    html += '<span>Период:</span><b>'+(dateFrom?fmtDate(dateFrom):'__.__.____')+' — '+(dateTo?fmtDate(dateTo):'__.__.____')+'</b>';
    html += '</div>';
    html += '<table class="cab-tbl"><thead><tr>';
    html += '<th style="width:22px">№</th>';
    html += '<th style="width:54px">Дата приёмки</th>';
    html += '<th>Марка кабеля</th>';
    html += '<th style="width:42px">Сечение, мм²</th>';
    html += '<th style="width:32px">Жил</th>';
    html += '<th style="width:50px">Длина, м (с барабана)</th>';
    html += '<th style="width:50px">№ барабана/бухты</th>';
    html += '<th style="width:80px">Изготовитель</th>';
    html += '<th style="width:80px">Сертификат №</th>';
    html += '<th style="width:42px">R изоляции ДО, МΩ</th>';
    html += '<th style="width:42px">R изоляции ПОСЛЕ, МΩ</th>';
    html += '<th>Место прокладки</th>';
    html += '<th style="width:80px">Способ прокладки</th>';
    html += '<th style="width:54px">Дата монтажа</th>';
    html += '<th style="width:90px">Ответств. ИТР</th>';
    html += '</tr></thead><tbody>';
    records.forEach((r,i)=>{
      html += '<tr>';
      html += '<td class="num">'+(i+1)+'</td>';
      html += '<td>'+fmtDate(r.receivedAt)+'</td>';
      html += '<td>'+(r.cableBrand||'')+'</td>';
      html += '<td class="num">'+(r.crossSection||'—')+'</td>';
      html += '<td class="num">'+(r.coresCount||'—')+'</td>';
      html += '<td class="num">'+(r.lengthReceived||0)+'</td>';
      html += '<td>'+(r.drumNumber||'—')+'</td>';
      html += '<td>'+(r.manufacturer||'—')+'</td>';
      html += '<td>'+(r.certificateNumber||'—')+'</td>';
      html += '<td class="num">'+(r.insulationBefore||'—')+'</td>';
      html += '<td class="num">'+(r.insulationAfter||'—')+'</td>';
      html += '<td>'+(r.installationLocation||'—')+'</td>';
      html += '<td>'+(r.installationMethod||'—')+'</td>';
      html += '<td>'+fmtDate(r.installedAt)+'</td>';
      html += '<td>'+(r.responsibleItr||'—')+'</td>';
      html += '</tr>';
    });
    html += '</tbody></table>';
    html += '<div class="cab-foot">Журнал ведётся в соответствии с СП 76.13330 «Электротехнические устройства», ПУЭ (изд. 7), ГОСТ Р 50571 (электроустановки зданий). Перед сдачей электромонтажных работ — обязательны измерения сопротивления изоляции мегаомметром.</div>';
    html += '<div class="cab-sigs">';
    html += '<div><div class="cab-sig-label">Ответственный за электромонтажные работы (ИТР):</div><div class="cab-sig-line"></div><div class="cab-sig-sub">(должность, подпись, ФИО)</div></div>';
    html += '<div><div class="cab-sig-label">Представитель технического надзора заказчика:</div><div class="cab-sig-line"></div><div class="cab-sig-sub">(должность, подпись, ФИО)</div></div>';
    html += '</div>';
    return html;
  };

  const buildPrescriptionContent = (pr) => {
    const req = companyRequisites||{};
    const orgName = req.fullName||req.shortName||companyName||'_____';
    const project = projects.find(p=>p.name===pr.projectName)||{};
    const fmtDate = (d) => { if(!d) return '«___» __________ 20__ г.'; const dt=new Date(d); if(isNaN(dt)) return d; const months=['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря']; return '«'+String(dt.getDate()).padStart(2,'0')+'» '+months[dt.getMonth()]+' '+dt.getFullYear()+' г.'; };
    let html = '<style>'
      + '.pr-meta{margin:6px 0;font-size:12px}'
      + '.pr-title{text-align:center;font-weight:700;font-size:15px;margin:18px 0 6px}'
      + '.pr-sub{text-align:center;font-size:13px;margin:0 0 18px;color:#444}'
      + '.pr-row{display:flex;justify-content:space-between;font-size:12px;margin:4px 0}'
      + '.pr-item{margin:10px 0;font-size:12px;line-height:1.5}'
      + '.pr-block{border:1px solid #333;padding:10px;margin:8px 0;font-size:12px;line-height:1.5;min-height:50px;border-radius:4px}'
      + '.pr-sigs{margin-top:30px;display:grid;grid-template-columns:1fr 1fr;gap:30px}'
      + '.pr-sig-label{font-weight:600;margin-bottom:30px;font-size:11px}'
      + '.pr-sig-line{border-bottom:1px solid #333;min-height:18px;font-size:12px;font-weight:600}'
      + '.pr-sig-sub{font-size:9px;color:#555;margin-top:2px}'
      + '</style>';
    html += '<div class="pr-meta"><b>'+orgName+'</b></div>';
    html += '<div class="pr-title">ПРЕДПИСАНИЕ № '+(pr.number||pr.id||'____')+'</div>';
    html += '<div class="pr-sub">об устранении выявленных нарушений на объекте строительства</div>';
    html += '<div class="pr-row"><span>'+(project.city||'г. ____________')+'</span><span>'+fmtDate(new Date().toISOString().slice(0,10))+'</span></div>';
    html += '<div class="pr-item"><b>Объект:</b> '+(pr.projectName||'____________')+'</div>';
    html += '<div class="pr-item"><b>Заказчик:</b> '+(project.client||'____________')+'</div>';
    html += '<div class="pr-item"><b>Кем выдано:</b> '+(pr.issuedBy||'____________')+' ('+(pr.issuedByRole||'____________')+')</div>';
    html += '<div class="pr-item"><b>Приоритет:</b> '+(pr.priority||'—')+'</div>';
    html += '<div class="pr-item"><b>Описание нарушения:</b><div class="pr-block">'+((pr.violation||pr.description||'').replace(/\n/g,'<br/>')||'(не указано)')+'</div></div>';
    if (pr.deadline) html += '<div class="pr-item"><b>Срок устранения:</b> '+fmtDate(pr.deadline)+'</div>';
    if (pr.responsible) html += '<div class="pr-item"><b>Ответственный за устранение:</b> '+pr.responsible+'</div>';
    html += '<div class="pr-item"><b>Статус:</b> '+(pr.status||'Открыто')+'</div>';
    if (pr.photoUrl) html += '<div class="pr-item"><b>Фотофиксация нарушения прилагается.</b></div>';
    html += '<div class="pr-sigs">';
    html += '<div><div class="pr-sig-label">Выдал предписание:</div><div class="pr-sig-line">'+(pr.issuedBy||'')+'</div><div class="pr-sig-sub">(должность, ФИО, подпись)</div></div>';
    html += '<div><div class="pr-sig-label">Получил, обязуюсь устранить:</div><div class="pr-sig-line"></div><div class="pr-sig-sub">(должность, ФИО подрядчика, подпись)</div></div>';
    html += '</div>';
    html += '<p style="margin-top:30px;font-size:10px;color:#555;text-align:center">Форма соответствует методическим указаниям МДС 12-46.2008. Подлежит исполнению в указанный срок.</p>';
    return html;
  };

  const buildTBContent = (entry) => {
    const req = companyRequisites||{};
    const instruction = TB_INSTRUCTIONS[entry.type] || '<p>Общие требования безопасности.</p>';
    let html = '<h2 style="text-align:center">'+entry.type.toUpperCase()+'</h2>';
    html += '<p>Организация: '+(req.fullName||req.shortName||companyName||'_____')+'</p>';
    html += '<p>Объект: <b>'+entry.project+'</b> | Дата: <b>'+entry.date+'</b></p>'+instruction;
    html += '<table><tr><th>N</th><th>ФИО</th><th>Должность</th><th>Подпись</th><th>Дата</th></tr>';
    (entry.participants||[]).forEach((p,i) => { html += '<tr><td>'+(i+1)+'</td><td>'+p+'</td><td></td><td style="min-width:120px"></td><td>'+entry.date+'</td></tr>'; });
    html += '</table><div class="signatures"><div class="sig"><div class="sig-line">Инструктаж провёл</div></div></div>';
    return html;
  };

  const buildPricelistContent = (pl, items) => {
    const req = companyRequisites||{};
    const categories = [...new Set(items.map(i=>i.category))];
    let html = '<h2 style="text-align:center">ПРАЙС-ЛИСТ</h2><p><b>'+(req.fullName||req.shortName||companyName||'')+'</b> | '+pl.name+' | '+new Date().toLocaleDateString('ru-RU')+'</p>';
    categories.forEach(cat => {
      html += '<h3 style="color:#f97316;border-bottom:2px solid #f97316;padding-bottom:5px">'+(cat||'Общее')+'</h3><table><tr><th>Наименование</th><th>Ед.</th><th>Цена (руб.)</th></tr>';
      items.filter(i=>i.category===cat).forEach(item => { html += '<tr><td>'+item.name+'</td><td>'+item.unit+'</td><td>'+(item.price*pl.coefficient).toLocaleString()+'</td></tr>'; });
      html += '</table>';
    });
    return html;
  };

  const buildPositionInstructionContent = (role, name) => {
    const req = companyRequisites||{};
    const instruction = POSITION_INSTRUCTIONS[role] || '<h2>ДОЛЖНОСТНАЯ ИНСТРУКЦИЯ</h2>';
    return instruction + '<p><b>Организация:</b> '+(req.fullName||req.shortName||companyName||'_____')+'</p><div class="signatures"><div class="sig"><div class="sig-line">Директор<br/>'+(req.directorName||'')+'</div></div><div class="sig"><div class="sig-line">Ознакомлен<br/><b>'+name+'</b></div></div></div>';
  };

  const buildPassportContent = (project) => {
    const req = companyRequisites||{};
    const projectRooms = rooms.filter(r=>r.project===project.name);
    const cat = expByCategory(project.name);
    const totalExp = Object.values(cat).reduce((s,v)=>s+v,0);
    let html = '<h2 style="text-align:center">ПАСПОРТ ОБЪЕКТА</h2><h3 style="text-align:center">'+project.name+'</h3>';
    html += '<p>Организация: '+(req.fullName||req.shortName||companyName||'_____')+'</p>';
    html += '<table><tr><th>Заказчик</th><td>'+project.client+'</td></tr>'+(isFinanceRole()?'<tr><th>Бюджет</th><td>'+project.budget.toLocaleString()+' руб.</td></tr>':'')+'<tr><th>Статус</th><td>'+project.status+'</td></tr></table>';
    html += '<h3>ПОМЕЩЕНИЯ:</h3><table><tr><th>Помещение</th><th>Пол м2</th><th>Стены м2</th><th>Чистые стены</th><th>Потолок м2</th><th>Тип потолка</th><th>Окна</th><th>Двери</th></tr>';
    projectRooms.forEach(r => {
      const wins = roomWindows.filter(w=>w.room_id===r.id);
      const doors = roomDoors.filter(d=>d.room_id===r.id);
      const netWall = getRoomNetWall(r);
      const winInfo = wins.length>0 ? wins.length+'шт/'+wins.reduce((s,w)=>s+calcWindowArea(w),0).toFixed(1)+'м2' : '—';
      const doorInfo = doors.length>0 ? doors.length+'шт/'+doors.reduce((s,d)=>s+calcDoorArea(d),0).toFixed(1)+'м2' : '—';
      html += '<tr><td>'+r.name+'</td><td>'+r.floorArea+'</td><td>'+r.wallArea+'</td><td>'+netWall+'</td><td>'+r.ceilingArea+'</td><td>'+(r.ceiling_type||r.ceilingType||'—')+'</td><td>'+winInfo+'</td><td>'+doorInfo+'</td></tr>';
    });
    html += '</table>';
    if (projectRooms.length>0) {
      html += '<h3>ОТКОСЫ:</h3><table><tr><th>Помещение</th><th>Откосы окон м2</th><th>Откосы дверей м2</th></tr>';
      projectRooms.forEach(r => {
        const wins = roomWindows.filter(w=>w.room_id===r.id);
        const doors = roomDoors.filter(d=>d.room_id===r.id);
        const winRev = wins.reduce((s,w)=>s+calcWindowReveals(w),0).toFixed(2);
        const doorRev = doors.reduce((s,d)=>s+calcDoorReveals(d),0).toFixed(2);
        html += '<tr><td>'+r.name+'</td><td>'+winRev+'</td><td>'+doorRev+'</td></tr>';
      });
      html += '</table>';
    }
    if(isFinanceRole()) { html += '<h3>ФИНАНСЫ:</h3><table>';
    EXPENSE_CATEGORIES.forEach(c => { html += '<tr><td>'+c.label+'</td><td>'+cat[c.id].toLocaleString()+' руб.</td></tr>'; });
    html += '<tr><td><b>Итого:</b></td><td><b>'+totalExp.toLocaleString()+' руб.</b></td></tr>';
    html += '<tr><td>Бюджет:</td><td>'+project.budget.toLocaleString()+' руб.</td></tr>';
    html += '<tr><td><b>Остаток:</b></td><td><b>'+(project.budget-totalExp).toLocaleString()+' руб.</b></td></tr></table>'; }
    return html;
  };

  const buildInvoiceContent = (inv) => {
    const req = companyRequisites||{};
    const vatCalc = calcVat(inv.totalBase||0, inv.vat||'Без НДС');
    const qrUrl = generateQR(window.location.origin+'/?invoice='+inv.id+'&number='+inv.number);
    let html = '<h2 style="text-align:center">ПРИХОДНАЯ НАКЛАДНАЯ № '+inv.number+'</h2>';
    html += '<p style="text-align:center">'+(req.fullName||req.shortName||companyName||'_____')+'</p>';
    html += '<div style="float:right;margin-bottom:10px"><img src="'+qrUrl+'" width="100" height="100"/><p style="font-size:10px;text-align:center">QR накладной</p></div>';
    html += '<table><tr><th>Дата</th><td>'+inv.date+'</td><th>Поставщик</th><td>'+inv.supplierName+'</td></tr>';
    html += '<tr><th>Принял</th><td>'+inv.acceptedBy+'</td><th>Место</th><td>'+(inv.location==='Основной склад'?'Основной склад':inv.project||'')+'</td></tr>';
    html += '<tr><th>НДС</th><td colspan="3">'+inv.vat+'</td></tr></table>';
    html += '<table><tr><th>N</th><th>Наименование товара</th><th>Категория</th><th>Кол-во</th><th>Ед.</th><th>Цена</th><th>Сумма</th></tr>';
    (inv.items||[]).forEach((item,i) => { html += '<tr><td>'+(i+1)+'</td><td>'+item.name+'</td><td>'+(item.category||'—')+'</td><td>'+item.quantity+'</td><td>'+item.unit+'</td><td>'+Number(item.price||0).toLocaleString()+'</td><td>'+(Number(item.quantity)*Number(item.price||0)).toLocaleString()+'</td></tr>'; });
    html += '<tr><td colspan="6">Итого без НДС:</td><td>'+vatCalc.base.toLocaleString()+' руб.</td></tr>';
    if (inv.vat==='С НДС 22%') html += '<tr><td colspan="6">НДС 22%:</td><td>'+vatCalc.vat.toLocaleString()+' руб.</td></tr><tr><td colspan="6"><b>Итого с НДС:</b></td><td><b>'+vatCalc.total.toLocaleString()+' руб.</b></td></tr>';
    html += '</table><div class="signatures"><div class="sig"><div class="sig-line">Поставщик</div></div><div class="sig"><div class="sig-line">Принял: '+inv.acceptedBy+'</div></div></div>';
    return html;
  };

  const sendCompanyChatMessage = async (text, photoUrl) => {
    if (!text && !photoUrl) return;
    try {
      await fetch(API+'/messages',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chatType:'company',projectId:null,authorId:user.id,authorName:user.name,authorRole:user.role,text,photoUrl})});
      const msgs = await fetch(API+'/messages').then(r=>r.json()).catch(()=>[]);
      setCompanyMessages(Array.isArray(msgs)?msgs:[]);
    } catch(e) {
      const msg = {id:Date.now(),text,photo_url:photoUrl,author_name:user.name,author_role:user.role,created_at:new Date().toISOString()};
      setCompanyMessages(prev=>[...prev,msg]);
    }
    setCompanyChatMessage('');
  };

  const sendProjectChatMessage = async (projectName, text, photoUrl) => {
    if (!text && !photoUrl) return;
    try {
      await fetch(API+'/project-chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({projectName,authorId:user.id,authorName:user.name,authorRole:user.role,text,photoUrl})});
      await loadProjectChat(projectName);
    } catch(e) {}
    setProjectChatMessage('');
  };

  const saveLead = (lead) => {
    const updated = lead.id ? leads.map(l=>l.id===lead.id?lead:l) : [...leads,{...lead,id:Date.now(),createdAt:new Date().toISOString().split('T')[0],createdBy:user.name}];
    setLeads(updated); localStorage.setItem('leads',JSON.stringify(updated));
  };

  const deleteLead = (id) => { const updated=leads.filter(l=>l.id!==id); setLeads(updated); localStorage.setItem('leads',JSON.stringify(updated)); };
  const ratemaster = (masterId, rating) => { const updated={...masterRatings,[masterId]:rating}; setMasterRatings(updated); localStorage.setItem('masterRatings',JSON.stringify(updated)); };
  const confirmMaterialReceipt = async (transferId) => {
    await fetch(API+'/material-transfers/'+transferId+'/sign',{method:'PUT'});
    setMaterialTransfers(prev=>prev.map(t=>t.id===transferId?{...t,signed:true}:t));
  };

  const handleLogin = async () => {
    try {
      const res = await fetch(API+'/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password})});
      if (!res.ok) { setLoginError('Неверный email или пароль'); return; }
      setUser(await res.json());
    } catch { setLoginError('Ошибка подключения к серверу'); }
  };

  const handleRegister = async () => {
    if (!regName||!regEmail||!regPassword||!regCode) { setLoginError('Заполните все поля'); return; }
    try {
      const res = await fetch(API+'/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:regName,email:regEmail,password:regPassword,code:regCode})});
      if (!res.ok) { const err=await res.json(); setLoginError(err.detail); return; }
      setUser(await res.json());
    } catch { setLoginError('Ошибка подключения'); }
  };

  const saveProfile = async () => {
    if (!profileData.fullName||!profileData.inn||!profileData.bankAccount) { alert('Заполните обязательные поля'); return; }
    if (!consentChecked) { alert('Необходимо согласие на обработку ПД'); return; }
    const res = await fetch(API+'/master-profile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...profileData,userId:user.id})});
    setMasterProfile(await res.json()); setShowProfileForm(false);
    await fetch(API+'/pd-consents',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({userId:user.id,signedAt:new Date().toLocaleString('ru-RU'),scanUrl:'',uploadedBy:user.name})});
    await loadAll();
  };

  const canAccess = (p) => user && (ROLES[user.role]||[]).includes(p);
  const isFinanceRole = () => ['директор','зам_директора','бухгалтер'].includes(user?user.role:'');

  // Расчёт прогресса и сумм по факту сметы (используется в дашборде, кабинетах технадзора и заказчика, карточке объекта)
  const _sectionsOfEst = (est) => { try { return est.sections || (typeof est.sectionsJson==='string'?JSON.parse(est.sectionsJson||'[]'):est.sectionsJson) || []; } catch(e) { return []; } };
  const _estimateForProject = (p) => estimatesList.find(e=>(e.projectName===p.name||Number(e.projectId)===Number(p.id))&&(!e.smetaType||e.smetaType==='Заказчик'))||estimatesList.find(e=>e.projectName===p.name||Number(e.projectId)===Number(p.id));
  const projectPlanDone = (p) => { const est=_estimateForProject(p); if(!est) return {plan:0,done:0}; let pl=0,dn=0; _sectionsOfEst(est).forEach(s=>(s.items||[]).forEach(it=>{ const q=Number(it.quantity||0), dq=Number(it.doneQuantity||0), pr=Number(it.priceWork||0)+Number(it.priceMaterial||0); pl+=q*pr; dn+=dq*pr; })); return {plan:pl,done:dn}; };
  const projectRealProgress = (p) => { if(!p) return 0; const {plan,done}=projectPlanDone(p); if(plan>0) return Math.round(done/plan*100); return Number(p.progress||0); };

  // Уведомления для текущего пользователя — собираются из АОСР, непредвиденных, предписаний
  const computeNotifications = () => {
    if (!user) return [];
    const out = [];
    const today = new Date().toISOString().split('T')[0];
    if (user.role==='бухгалтер'||user.role==='директор'||user.role==='зам_директора'){
      hiddenActs.filter(a=>a.status==='Подписан'&&a.paidStatus!=='Оплачен').forEach(a=>{
        out.push({type:'pay',title:'АОСР подписан — можно платить бригаде',text:a.actNumber+' · '+a.workName+' · '+Math.round(Number(a.total||0)).toLocaleString('ru-RU')+' ₽',target:'accounting',icon:'💰',color:'#10b981'});
      });
    }
    if (user.role==='заказчик'){
      (unexpectedWorksList||[]).filter(u=>u.projectName===(user.project_name||user.projectName)&&u.status==='Ожидает согласования').forEach(u=>{
        out.push({type:'unx',title:'Доп.работа на согласование',text:u.description+' · '+(u.total||0).toLocaleString('ru-RU')+' ₽',icon:'🆕',color:'#fbbf24'});
      });
      hiddenActs.filter(a=>a.projectName===(user.project_name||user.projectName)&&!a.signedCustomer).forEach(a=>{
        out.push({type:'aosr',title:'АОСР ждёт моей подписи',text:a.actNumber+' · '+a.workName,icon:'🔒',color:'#f97316'});
      });
    }
    if (user.role==='технадзор'){
      hiddenActs.filter(a=>a.projectName===(user.project_name||user.projectName)&&!a.signedSupervisor).forEach(a=>{
        out.push({type:'aosr',title:'АОСР ждёт моей подписи',text:a.actNumber+' · '+a.workName,icon:'🔒',color:'#f97316'});
      });
    }
    if (['прораб','мастер'].includes(user.role)){
      (prescriptionsList||[]).filter(pr=>pr.responsible===user.name&&pr.status==='Открыто'&&pr.deadline&&pr.deadline<today).forEach(pr=>{
        out.push({type:'presc',title:'Предписание просрочено',text:(pr.violation||pr.description||'').slice(0,80),icon:'⚠️',color:'#ef4444'});
      });
    }
    return out;
  };

  // Хелпер: статус АОСР для записи журнала работ
  const getActStatusForJournal = (w) => {
    if (!w.hiddenWork) return null;
    const act = hiddenActs.find(a=>a.projectName===w.project&&(a.workName||'').trim()===(w.description||'').trim());
    if (!act) return {status:'none', icon:'❓', tip:'АОСР не найден'};
    if (act.status==='Подписан') return {status:'signed', icon:'✅', tip:'АОСР подписан', act};
    return {status:'draft', icon:'⏳', tip:'АОСР черновик — ждёт подписей', act};
  };

  // Формы М-15 (накладная на отпуск материалов) и месячного отчёта технадзора
  const buildM15Content = (transfer) => {
    const req = companyRequisites||{};
    const orgName = req.fullName||req.shortName||companyName||'_____';
    const fmtDate = (d) => { if(!d) return ''; const dt=new Date(d); if(isNaN(dt)) return d; return ('0'+dt.getDate()).slice(-2)+'.'+('0'+(dt.getMonth()+1)).slice(-2)+'.'+dt.getFullYear(); };
    let html = '<style>.m15-tbl{border-collapse:collapse;width:100%;font-size:11px}.m15-tbl th,.m15-tbl td{border:1px solid #333;padding:5px 6px}.m15-tbl th{background:#f3f4f6}</style>';
    html += '<h3 style="text-align:center;margin:8px 0">Унифицированная форма № М-15</h3>';
    html += '<h2 style="text-align:center;margin:0 0 4px">НАКЛАДНАЯ № '+transfer.id+' на отпуск материалов на сторону</h2>';
    html += '<p style="text-align:center;font-size:11px;color:#444">Утверждена Постановлением Госкомстата России от 30.10.1997 № 71а</p>';
    html += '<table class="m15-tbl"><tr><th>Организация</th><td>'+orgName+'</td><th>Дата</th><td>'+fmtDate(transfer.transferDate||transfer.date)+'</td></tr>';
    html += '<tr><th>Отправитель</th><td>'+(transfer.fromLocation||'Основной склад')+'</td><th>Получатель</th><td>'+(transfer.toPerson||'')+' ('+(transfer.toPersonRole||'')+')</td></tr>';
    html += '<tr><th>Объект</th><td colspan="3">'+(transfer.projectName||'')+'</td></tr></table>';
    html += '<table class="m15-tbl" style="margin-top:12px"><tr><th>№</th><th>Наименование материала</th><th>Ед.изм.</th><th>Количество</th><th>Примечание</th></tr>';
    html += '<tr><td>1</td><td>'+(transfer.materialName||'')+'</td><td>'+(transfer.unit||'')+'</td><td>'+(transfer.quantity||0)+'</td><td>'+(transfer.notes||'')+'</td></tr>';
    html += '</table>';
    html += '<div style="margin-top:24px;display:grid;grid-template-columns:1fr 1fr;gap:30px">';
    html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Отпустил:</div><div style="border-bottom:1px solid #333;min-height:18px"></div><div style="font-size:9px;color:#555;margin-top:2px">(должность, ФИО, подпись)</div></div>';
    html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Получил:</div><div style="border-bottom:1px solid #333;min-height:18px">'+(transfer.toPerson||'')+'</div><div style="font-size:9px;color:#555;margin-top:2px">(должность, ФИО, подпись)</div></div>';
    html += '</div>';
    return html;
  };

  const buildAOSKContent = (projectName) => {
    const req = companyRequisites||{};
    const orgName = req.fullName||req.shortName||companyName||'_____';
    const project = projects.find(p=>p.name===projectName)||{};
    const acts = hiddenActs.filter(a=>a.projectName===projectName);
    const responsibleActs = acts.filter(a=>{const wn=(a.workName||'').toLowerCase();return wn.includes('фундамент')||wn.includes('арматур')||wn.includes('бетон')||wn.includes('каркас')||wn.includes('несущ')||wn.includes('перекрыт')||wn.includes('колонн')||wn.includes('балк');});
    const fmtDate=(d)=>{if(!d)return '«___» __________ 20__ г.';const dt=new Date(d);if(isNaN(dt))return d;const m=['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'];return '«'+String(dt.getDate()).padStart(2,'0')+'» '+m[dt.getMonth()]+' '+dt.getFullYear()+' г.';};
    let html='<style>.aosk-title{text-align:center;font-weight:700;font-size:14px;margin:18px 0 4px}.aosk-sub{text-align:center;font-size:13px;margin:0 0 14px}.aosk-item{margin:8px 0;font-size:12px;line-height:1.5}.aosk-tbl{border-collapse:collapse;width:100%;font-size:11px;margin:8px 0}.aosk-tbl th,.aosk-tbl td{border:1px solid #333;padding:4px 6px}.aosk-tbl th{background:#f3f4f6}</style>';
    html+='<div style="margin:6px 0;font-size:12px"><b>'+orgName+'</b></div>';
    html+='<div class="aosk-title">АКТ</div><div class="aosk-sub">освидетельствования ответственных конструкций</div>';
    html+='<div class="aosk-item"><b>Объект:</b> '+(projectName||'')+'</div>';
    html+='<div class="aosk-item"><b>Заказчик:</b> '+(project.client||'____________')+'</div>';
    html+='<div class="aosk-item"><b>Подрядчик:</b> '+orgName+'</div>';
    html+='<div class="aosk-item"><b>Дата:</b> '+fmtDate(new Date().toISOString().slice(0,10))+'</div>';
    html+='<p style="font-size:12px;margin:14px 0 8px">Комиссия в составе представителей застройщика, технадзора, генподрядчика и субподрядчика провела освидетельствование следующих ответственных конструкций:</p>';
    if (responsibleActs.length===0){
      html+='<p style="text-align:center;color:#888;font-size:11px;padding:14px">Записей по ответственным конструкциям нет — ведутся через АОСР (СНиП 12-01-2004)</p>';
    } else {
      html+='<table class="aosk-tbl"><tr><th>№</th><th>Конструкция</th><th>Объём</th><th>Раздел сметы</th><th>Подписан</th><th>Связан с АОСР</th></tr>';
      responsibleActs.forEach((a,i)=>{html+='<tr><td>'+(i+1)+'</td><td>'+(a.workName||'')+'</td><td>'+(a.quantity||0)+' '+(a.unit||'')+'</td><td>'+(a.sectionName||'—')+'</td><td>'+(a.status==='Подписан'?'✅':'⏳ '+(a.status||''))+'</td><td>'+a.actNumber+'</td></tr>';});
      html+='</table>';
    }
    html+='<p style="font-size:12px;margin:14px 0">При выполнении конструкций соблюдены требования: СНиП 3.03.01 (бетонные и железобетонные конструкции), ГОСТ 26633 (бетоны тяжёлые), ГОСТ 5781 (арматура).</p>';
    html+='<p style="font-size:12px"><b>Заключение комиссии:</b> ответственные конструкции выполнены в соответствии с проектной документацией и техническими регламентами. Разрешается производство последующих работ.</p>';
    html+='<div style="margin-top:30px;display:grid;grid-template-columns:1fr 1fr;gap:20px">';
    html+='<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Представитель застройщика (заказчика):</div><div style="border-bottom:1px solid #333;min-height:18px"></div><div style="font-size:9px;color:#555;margin-top:2px">(должность, ФИО, подпись)</div></div>';
    html+='<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Представитель технического надзора:</div><div style="border-bottom:1px solid #333;min-height:18px"></div><div style="font-size:9px;color:#555;margin-top:2px">(должность, ФИО, подпись)</div></div>';
    html+='<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Представитель генподрядчика:</div><div style="border-bottom:1px solid #333;min-height:18px">'+(req.directorName||'')+'</div><div style="font-size:9px;color:#555;margin-top:2px">(должность, ФИО, подпись)</div></div>';
    html+='<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Представитель проектной организации:</div><div style="border-bottom:1px solid #333;min-height:18px"></div><div style="font-size:9px;color:#555;margin-top:2px">(должность, ФИО, подпись)</div></div>';
    html+='</div>';
    html+='<p style="margin-top:20px;font-size:10px;color:#555;text-align:center">Форма соответствует СНиП 12-01-2004 (Приложение 4). Документ обязателен для приёмки несущих/ответственных конструкций.</p>';
    return html;
  };

  const buildKS11Content = (project) => {
    const req = companyRequisites||{};
    const orgName = req.fullName||req.shortName||companyName||'_____';
    const fmtDate=(d)=>{if(!d)return '«___» __________ 20__ г.';const dt=new Date(d);if(isNaN(dt))return d;const m=['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'];return '«'+String(dt.getDate()).padStart(2,'0')+'» '+m[dt.getMonth()]+' '+dt.getFullYear()+' г.';};
    const pd=projectPlanDone(project);
    const aosrTotal=hiddenActs.filter(a=>a.projectName===project.name&&a.status==='Подписан').length;
    const aosrAll=hiddenActs.filter(a=>a.projectName===project.name).length;
    let html='<style>.ks-tbl{border-collapse:collapse;width:100%;font-size:11px}.ks-tbl th,.ks-tbl td{border:1px solid #333;padding:5px 6px}.ks-tbl th{background:#f3f4f6}</style>';
    html+='<h3 style="text-align:center;margin:6px 0">Унифицированная форма № КС-11</h3>';
    html+='<h2 style="text-align:center;margin:0 0 4px">АКТ ПРИЁМКИ ЗАКОНЧЕННОГО СТРОИТЕЛЬСТВОМ ОБЪЕКТА</h2>';
    html+='<p style="text-align:center;font-size:11px;color:#444">Утверждена Постановлением Госкомстата России от 30.10.1997 № 71а</p>';
    html+='<p style="font-size:12px"><b>Объект:</b> '+project.name+'</p>';
    html+='<p style="font-size:12px"><b>Адрес:</b> '+(project.address||project.city||'____________')+'</p>';
    html+='<p style="font-size:12px"><b>Заказчик:</b> '+(project.client||'____________')+'</p>';
    html+='<p style="font-size:12px"><b>Подрядчик:</b> '+orgName+'</p>';
    html+='<p style="font-size:12px"><b>Дата подписания:</b> '+fmtDate(new Date().toISOString().slice(0,10))+'</p>';
    html+='<h3 style="margin-top:14px;font-size:13px">1. Характеристики выполненных работ:</h3>';
    html+='<table class="ks-tbl"><tr><td>Бюджет по договору</td><td>'+Math.round(Number(project.budget||0)).toLocaleString("ru-RU")+' ₽</td></tr>';
    html+='<tr><td>Выполнено по смете</td><td>'+Math.round(pd.done).toLocaleString("ru-RU")+' ₽</td></tr>';
    html+='<tr><td>Срок строительства</td><td>'+(project.startDate||'____')+' — '+(project.deadline||'____')+'</td></tr>';
    html+='<tr><td>АОСР подписанных / всего</td><td>'+aosrTotal+' / '+aosrAll+'</td></tr></table>';
    html+='<h3 style="margin-top:14px;font-size:13px">2. Заключение приёмочной комиссии:</h3>';
    html+='<p style="font-size:12px">Объект <b>'+project.name+'</b> выполнен в соответствии с проектной документацией, техническими регламентами и условиями договора подряда. Все скрытые работы освидетельствованы и приняты согласно АОСР. Объект пригоден к эксплуатации.</p>';
    html+='<div style="margin-top:30px;display:grid;grid-template-columns:1fr 1fr;gap:20px">';
    html+='<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Заказчик:</div><div style="border-bottom:1px solid #333;min-height:18px">'+(project.client||'')+'</div></div>';
    html+='<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Подрядчик:</div><div style="border-bottom:1px solid #333;min-height:18px">'+(req.directorName||orgName)+'</div></div>';
    html+='</div>';
    return html;
  };

  const buildKS14Content = (project) => {
    const req = companyRequisites||{};
    const orgName = req.fullName||req.shortName||companyName||'_____';
    let html='<h3 style="text-align:center;margin:6px 0">Унифицированная форма № КС-14</h3>';
    html+='<h2 style="text-align:center;margin:0 0 4px">АКТ ПРИЁМКИ ОБЪЕКТА ГОСУДАРСТВЕННОЙ ПРИЁМОЧНОЙ КОМИССИЕЙ</h2>';
    html+='<p style="text-align:center;font-size:11px;color:#444">Утверждена Постановлением Госкомстата России от 30.10.1997 № 71а</p>';
    html+='<p style="font-size:12px;margin:14px 0"><b>Объект:</b> '+project.name+' · <b>Адрес:</b> '+(project.address||project.city||'____________')+'</p>';
    html+='<p style="font-size:12px"><b>Заказчик:</b> '+(project.client||'____________')+' · <b>Подрядчик:</b> '+orgName+'</p>';
    html+='<p style="font-size:12px;margin:14px 0">Государственная приёмочная комиссия в составе:</p>';
    html+='<ul style="font-size:12px"><li>Председатель комиссии (представитель заказчика)</li><li>Представитель государственного строительного надзора</li><li>Представитель пожарного надзора</li><li>Представитель санитарно-эпидемиологической службы</li><li>Представитель проектной организации</li><li>Представитель генподрядчика — '+orgName+'</li></ul>';
    html+='<p style="font-size:12px;margin:14px 0">Произвела осмотр законченного строительством объекта и установила, что объект соответствует утверждённому проекту, требованиям технических регламентов и нормативной документации. Объект <b>принят</b> в эксплуатацию.</p>';
    html+='<div style="margin-top:30px;display:grid;grid-template-columns:1fr 1fr;gap:20px">';
    html+='<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Председатель комиссии:</div><div style="border-bottom:1px solid #333;min-height:18px"></div></div>';
    html+='<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Представитель ГСН:</div><div style="border-bottom:1px solid #333;min-height:18px"></div></div>';
    html+='<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Представитель пожнадзора:</div><div style="border-bottom:1px solid #333;min-height:18px"></div></div>';
    html+='<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Представитель СЭС:</div><div style="border-bottom:1px solid #333;min-height:18px"></div></div>';
    html+='<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Проектная организация:</div><div style="border-bottom:1px solid #333;min-height:18px"></div></div>';
    html+='<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Генподрядчик:</div><div style="border-bottom:1px solid #333;min-height:18px">'+(req.directorName||orgName)+'</div></div>';
    html+='</div>';
    return html;
  };

  const buildIGDContent = (projectName) => {
    const project = projects.find(p=>p.name===projectName)||{};
    const req = companyRequisites||{};
    const orgName = req.fullName||req.shortName||companyName||'_____';
    let html='<h2 style="text-align:center;margin:8px 0">ИСПОЛНИТЕЛЬНАЯ ГЕОДЕЗИЧЕСКАЯ ДОКУМЕНТАЦИЯ</h2>';
    html+='<p style="text-align:center;font-size:11px;color:#444">по СП 126.13330 «Геодезические работы в строительстве»</p>';
    html+='<p style="font-size:12px"><b>Объект:</b> '+projectName+'</p>';
    html+='<p style="font-size:12px"><b>Подрядчик:</b> '+orgName+'</p>';
    html+='<h3 style="margin-top:14px;font-size:13px">Перечень исполнительных схем (составляется геодезистом):</h3>';
    html+='<ul style="font-size:12px;line-height:1.7">';
    html+='<li>Схема расположения главных осей здания</li>';
    html+='<li>Схема расположения свай / фундамента (с отклонениями от проекта)</li>';
    html+='<li>Высотная схема цоколя и фундаментной плиты</li>';
    html+='<li>Схема расположения колонн каждого этажа</li>';
    html+='<li>Схема геодезической разбивки внутренних осей</li>';
    html+='<li>Поэтажные планы с фактическими размерами</li>';
    html+='<li>Профиль наружных сетей</li>';
    html+='<li>Сводный план фактического положения объекта на участке</li>';
    html+='</ul>';
    html+='<p style="font-size:11px;color:#666;margin-top:14px">⚠️ Схемы выполняются на бумаге/AutoCAD по СП 126.13330.2017. Должны содержать: фактические координаты, отметки, отклонения от проекта, подписи геодезиста и прораба.</p>';
    html+='<div style="margin-top:30px;display:grid;grid-template-columns:1fr 1fr;gap:20px">';
    html+='<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Геодезист:</div><div style="border-bottom:1px solid #333;min-height:18px"></div></div>';
    html+='<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Производитель работ:</div><div style="border-bottom:1px solid #333;min-height:18px"></div></div>';
    html+='</div>';
    return html;
  };

  const buildVATBookContent = (periodFrom, periodTo) => {
    const req = companyRequisites||{};
    const orgName = req.fullName||req.shortName||companyName||'_____';
    const inRange = (d) => !d ? false : (!periodFrom||d>=periodFrom) && (!periodTo||d<=periodTo);
    const purchases = (supplierInvoices||[]).filter(i=>(i.status==='Оплачен'||i.status==='Утверждён')&&inRange(i.invoiceDate));
    const sales = (interimActs||[]).filter(a=>inRange(a.periodEnd||a.periodStart));
    const totalPurchase = purchases.reduce((s,i)=>s+Number(i.amount||0),0);
    const totalPurchaseVAT = purchases.reduce((s,i)=>s+Number(i.vatAmount||0),0);
    const totalSales = sales.reduce((s,a)=>s+Number(a.totalAmount||0),0);
    const estVATSales = Math.round(totalSales/120*20);
    let html = '<style>.vat-tbl{border-collapse:collapse;width:100%;font-size:11px;margin:8px 0}.vat-tbl th,.vat-tbl td{border:1px solid #333;padding:5px 6px}.vat-tbl th{background:#f3f4f6}</style>';
    html += '<h2 style="text-align:center;margin:6px 0">КНИГА ПОКУПОК И ПРОДАЖ (НДС)</h2>';
    html += '<p style="text-align:center;font-size:11px;color:#444">Налогоплательщик: <b>'+orgName+'</b> · ИНН: '+(req.inn||'____________')+'</p>';
    html += '<p style="text-align:center;font-size:11px;color:#444">Период: '+(periodFrom||'__.__.____')+' — '+(periodTo||'__.__.____')+'</p>';
    html += '<h3 style="margin-top:14px;font-size:13px">Книга покупок (входящие счета от поставщиков)</h3>';
    if(purchases.length===0) html += '<p style="font-size:11px;color:#888">За период покупок нет</p>';
    else {
      html += '<table class="vat-tbl"><tr><th>№</th><th>Дата</th><th>Поставщик</th><th>№ счёта</th><th>Сумма с НДС</th><th>В т.ч. НДС</th><th>Статус</th></tr>';
      purchases.forEach((p,i)=>{html+='<tr><td>'+(i+1)+'</td><td>'+(p.invoiceDate||'')+'</td><td>'+(p.supplierName||'')+'</td><td>'+(p.invoiceNumber||'')+'</td><td style="text-align:right">'+Math.round(Number(p.amount||0)).toLocaleString('ru-RU')+'</td><td style="text-align:right">'+Math.round(Number(p.vatAmount||0)).toLocaleString('ru-RU')+'</td><td>'+p.status+'</td></tr>';});
      html += '<tr style="background:#fef3c7"><td colspan="4"><b>ИТОГО покупки:</b></td><td style="text-align:right"><b>'+Math.round(totalPurchase).toLocaleString('ru-RU')+' ₽</b></td><td style="text-align:right"><b>'+Math.round(totalPurchaseVAT).toLocaleString('ru-RU')+' ₽</b></td><td></td></tr>';
      html += '</table>';
    }
    html += '<h3 style="margin-top:14px;font-size:13px">Книга продаж (выставленные акты выполненных работ)</h3>';
    if(sales.length===0) html += '<p style="font-size:11px;color:#888">За период продаж нет</p>';
    else {
      html += '<table class="vat-tbl"><tr><th>№</th><th>Период</th><th>Объект</th><th>Контрагент</th><th>Сумма</th><th>НДС (20%)</th></tr>';
      sales.forEach((s,i)=>{const v=Math.round(Number(s.totalAmount||0)/120*20);html+='<tr><td>'+(i+1)+'</td><td>'+((s.periodStart||'')+' — '+(s.periodEnd||''))+'</td><td>'+(s.project||'')+'</td><td>'+(s.masterName||'')+'</td><td style="text-align:right">'+Math.round(Number(s.totalAmount||0)).toLocaleString('ru-RU')+'</td><td style="text-align:right">'+v.toLocaleString('ru-RU')+'</td></tr>';});
      html += '<tr style="background:#d1fae5"><td colspan="4"><b>ИТОГО продажи:</b></td><td style="text-align:right"><b>'+Math.round(totalSales).toLocaleString('ru-RU')+' ₽</b></td><td style="text-align:right"><b>'+estVATSales.toLocaleString('ru-RU')+' ₽</b></td></tr>';
      html += '</table>';
    }
    html += '<div style="margin-top:20px;padding:14px;background:#f3f4f6;border-radius:8px;font-size:12px">';
    html += '<b>Итог по НДС за период:</b><br/>';
    html += 'НДС к вычету (покупки): <b>'+Math.round(totalPurchaseVAT).toLocaleString('ru-RU')+' ₽</b><br/>';
    html += 'НДС к начислению (продажи): <b>'+estVATSales.toLocaleString('ru-RU')+' ₽</b><br/>';
    html += '<b style="color:'+(estVATSales-totalPurchaseVAT>0?'#dc2626':'#059669')+'">НДС к уплате в бюджет: '+(estVATSales-totalPurchaseVAT).toLocaleString('ru-RU')+' ₽</b>';
    html += '</div>';
    html += '<p style="margin-top:14px;font-size:10px;color:#666;text-align:center">Расчёт ориентировочный. Финальные суммы определяются по налоговой декларации (ст.169-172 НК РФ). Для ОСН.</p>';
    return html;
  };

  const buildSupplementaryAgreementContent = (unx, project) => {
    const req = companyRequisites||{};
    const orgName = req.fullName||req.shortName||companyName||'_____';
    const fmtDate=(d)=>{if(!d)return '«___» __________ 20__ г.';const dt=new Date(d);if(isNaN(dt))return d;const m=['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'];return '«'+String(dt.getDate()).padStart(2,'0')+'» '+m[dt.getMonth()]+' '+dt.getFullYear()+' г.';};
    const num=unx.id||'____';
    const total=Math.round(Number(unx.total||0)).toLocaleString('ru-RU');
    let html='<h2 style="text-align:center;margin:6px 0">ДОПОЛНИТЕЛЬНОЕ СОГЛАШЕНИЕ № '+num+'</h2>';
    html+='<p style="text-align:center;font-size:11px;color:#444">к договору подряда на объект «'+project.name+'»</p>';
    html+='<div style="display:flex;justify-content:space-between;font-size:11px;margin:14px 0"><span>г. '+(project.city||'____________')+'</span><span>'+fmtDate(unx.approvedAt||new Date().toISOString().slice(0,10))+'</span></div>';
    html+='<p style="font-size:12px;line-height:1.6">'+(project.client||'____________')+', именуемый в дальнейшем <b>«Заказчик»</b>, в лице руководителя, с одной стороны, и '+orgName+', именуемый <b>«Подрядчик»</b>, в лице '+(req.directorName||'руководителя')+', с другой стороны, заключили настоящее дополнительное соглашение о нижеследующем:</p>';
    html+='<h3 style="font-size:13px;margin-top:14px">1. Предмет соглашения</h3>';
    html+='<p style="font-size:12px">Стороны согласовали выполнение Подрядчиком дополнительных работ, не предусмотренных основной сметой:</p>';
    html+='<table style="border-collapse:collapse;width:100%;font-size:11px;margin:8px 0"><tr style="background:#f3f4f6"><th style="border:1px solid #333;padding:5px 6px">Наименование работ</th><th style="border:1px solid #333;padding:5px 6px">Ед.</th><th style="border:1px solid #333;padding:5px 6px">Кол-во</th><th style="border:1px solid #333;padding:5px 6px">Цена</th><th style="border:1px solid #333;padding:5px 6px">Сумма</th></tr>';
    html+='<tr><td style="border:1px solid #333;padding:5px 6px">'+(unx.description||'')+'</td><td style="border:1px solid #333;padding:5px 6px">'+(unx.unit||'')+'</td><td style="border:1px solid #333;padding:5px 6px">'+(unx.quantity||0)+'</td><td style="border:1px solid #333;padding:5px 6px">'+Math.round(Number(unx.price||0)).toLocaleString('ru-RU')+'</td><td style="border:1px solid #333;padding:5px 6px">'+total+'</td></tr></table>';
    html+='<h3 style="font-size:13px;margin-top:14px">2. Стоимость и порядок оплаты</h3>';
    html+='<p style="font-size:12px">Общая стоимость дополнительных работ по настоящему соглашению составляет <b>'+total+' ₽</b>. Оплата производится Заказчиком после фактического выполнения работ и подписания акта приёмки.</p>';
    html+='<h3 style="font-size:13px;margin-top:14px">3. Сроки выполнения</h3>';
    html+='<p style="font-size:12px">Подрядчик обязуется выполнить работы в течение 30 (тридцати) дней с даты подписания настоящего соглашения.</p>';
    html+='<h3 style="font-size:13px;margin-top:14px">4. Прочие условия</h3>';
    html+='<p style="font-size:12px">В остальном применяются условия основного договора подряда. Соглашение составлено в 2 экземплярах — по одному для каждой стороны.</p>';
    html+='<div style="margin-top:30px;display:grid;grid-template-columns:1fr 1fr;gap:30px">';
    html+='<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">ЗАКАЗЧИК:</div><div style="border-bottom:1px solid #333;min-height:18px">'+(project.client||'')+'</div><div style="font-size:9px;color:#555;margin-top:2px">(должность, ФИО, подпись)</div></div>';
    html+='<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">ПОДРЯДЧИК:</div><div style="border-bottom:1px solid #333;min-height:18px">'+(req.directorName||orgName)+'</div><div style="font-size:9px;color:#555;margin-top:2px">(должность, ФИО, подпись)</div></div>';
    html+='</div>';
    return html;
  };

  const buildExecPackageContent = (project) => {
    const acts=hiddenActs.filter(a=>a.projectName===project.name);
    const inspections=(materialInspections||[]).filter(mi=>mi.projectName===project.name);
    const cables=(cableJournal||[]).filter(c=>c.projectName===project.name);
    const tb=(tbJournal||[]).filter(t=>t.project===project.name);
    const presc=(prescriptionsList||[]).filter(pr=>pr.projectName===project.name);
    let html='<h2 style="text-align:center;margin:8px 0">ПАКЕТ ИСПОЛНИТЕЛЬНОЙ ДОКУМЕНТАЦИИ</h2>';
    html+='<p style="text-align:center;font-size:11px;color:#444">для сдачи объекта в Госстройнадзор</p>';
    html+='<p style="font-size:12px;text-align:center;margin:14px 0"><b>'+project.name+'</b></p>';
    html+='<h3 style="margin-top:14px;font-size:13px">Состав пакета:</h3>';
    html+='<table style="border-collapse:collapse;width:100%;font-size:11px"><tr style="background:#f3f4f6"><th style="border:1px solid #333;padding:5px 6px">№</th><th style="border:1px solid #333;padding:5px 6px">Документ</th><th style="border:1px solid #333;padding:5px 6px">Кол-во</th><th style="border:1px solid #333;padding:5px 6px">Норматив</th></tr>';
    const items=[
      ['Общий журнал работ (РД-11-05-2007, форма ЖПР)','1','РД-11-05-2007'],
      ['Акты освидетельствования скрытых работ (АОСР)',acts.length+' ('+acts.filter(a=>a.status==='Подписан').length+' подп.)','СНиП 12-01-2004'],
      ['Акты освидетельствования ответственных конструкций (АОСК)','см. АОСР','СНиП 12-01-2004'],
      ['Журнал входного контроля материалов',inspections.length,'СП 48.13330.2019'],
      ['Журнал кабельной продукции',cables.length,'СП 76.13330'],
      ['Журнал инструктажей ТБ',tb.length,'ГОСТ 12.0.004-2015'],
      ['Исполнительная геодезическая документация (ИГД)','см. ИГД','СП 126.13330'],
      ['Сертификаты и паспорта на материалы','см. журнал входного контроля','—'],
      ['Акт КС-11 (приёмка законченного объекта)','1','Госкомстат № 71а'],
      ['Акт КС-14 (госприёмка)','1 (если ФЗ-44)','Госкомстат № 71а'],
      ['Предписания и ответы на них',presc.length,'МДС 12-46.2008'],
    ];
    items.forEach((it,i)=>{html+='<tr><td style="border:1px solid #333;padding:5px 6px">'+(i+1)+'</td><td style="border:1px solid #333;padding:5px 6px">'+it[0]+'</td><td style="border:1px solid #333;padding:5px 6px">'+it[1]+'</td><td style="border:1px solid #333;padding:5px 6px">'+it[2]+'</td></tr>';});
    html+='</table>';
    html+='<p style="font-size:11px;color:#666;margin-top:18px">⚠️ Перед сдачей в Госстройнадзор все журналы распечатать, прошить, пронумеровать страницы. АОСР должны быть подписаны 4 сторонами. Сертификаты на материалы — оригиналы или заверенные копии.</p>';
    return html;
  };

  const buildM29Content = (projectName, periodFrom, periodTo) => {
    const req = companyRequisites||{};
    const orgName = req.fullName||req.shortName||companyName||'_____';
    const project = projects.find(p=>p.name===projectName)||{};
    const est = _estimateForProject(project);
    // План из сметы по материалам (priceMaterial)
    const planByName = {};
    if (est) _sectionsOfEst(est).forEach(s=>(s.items||[]).forEach(it=>{
      if ((it.itemType||'material')==='material' || Number(it.priceMaterial||0)>0) {
        const key = (it.name||'').trim().toLowerCase();
        if (!key) return;
        if (!planByName[key]) planByName[key] = {name:it.name||'', unit:it.unit||'', plan:0, fact:0};
        planByName[key].plan += Number(it.quantity||0);
      }
    }));
    // Факт из material_transfers и warehouse_history по проекту
    (materialTransfers||[]).filter(t=>t.projectName===projectName).forEach(t=>{
      const key = (t.materialName||'').trim().toLowerCase();
      if (!key) return;
      if (!planByName[key]) planByName[key] = {name:t.materialName||'', unit:t.unit||'', plan:0, fact:0};
      planByName[key].fact += Number(t.quantity||0);
    });
    (history||[]).filter(h=>h.project===projectName&&(h.type||'').includes('расход')).forEach(h=>{
      const key = (h.material||'').trim().toLowerCase();
      if (!key) return;
      if (!planByName[key]) planByName[key] = {name:h.material||'', unit:'', plan:0, fact:0};
      planByName[key].fact += Number(h.quantity||0);
    });
    const rows = Object.values(planByName).sort((a,b)=>(b.fact-b.plan)-(a.fact-a.plan));
    let html = '<style>.m29-tbl{border-collapse:collapse;width:100%;font-size:11px;margin-top:10px}.m29-tbl th,.m29-tbl td{border:1px solid #333;padding:4px 6px}.m29-tbl th{background:#f3f4f6}.m29-over{color:#dc2626;font-weight:700}.m29-ok{color:#059669}</style>';
    html += '<h3 style="text-align:center;margin:6px 0">Унифицированная форма № М-29</h3>';
    html += '<h2 style="text-align:center;margin:0 0 4px">ОТЧЁТ О РАСХОДЕ ОСНОВНЫХ МАТЕРИАЛОВ</h2>';
    html += '<p style="text-align:center;font-size:11px;color:#444">в сопоставлении с производственными нормами (план/факт)</p>';
    html += '<p style="font-size:11px"><b>Объект:</b> '+projectName+' · <b>Подрядчик:</b> '+orgName+' · <b>Период:</b> '+(periodFrom||'__.__.____')+' — '+(periodTo||'__.__.____')+'</p>';
    if (rows.length===0) { html += '<p style="text-align:center;color:#888;padding:20px">Нет данных — не загружена смета или нет движений по материалам</p>'; }
    else {
      html += '<table class="m29-tbl"><tr><th>№</th><th>Наименование материала</th><th>Ед.</th><th>План (смета)</th><th>Факт (списано)</th><th>Отклонение</th><th>Статус</th></tr>';
      rows.forEach((r,i)=>{const delta=r.fact-r.plan;const over=r.plan>0&&delta>r.plan*0.05;html+='<tr><td>'+(i+1)+'</td><td>'+r.name+'</td><td>'+r.unit+'</td><td>'+r.plan.toLocaleString('ru-RU')+'</td><td>'+r.fact.toLocaleString('ru-RU')+'</td><td class="'+(over?'m29-over':'m29-ok')+'">'+(delta>0?'+':'')+delta.toLocaleString('ru-RU')+'</td><td>'+(over?'⚠️ перерасход >5%':delta<0?'✅ экономия':'≈ в норме')+'</td></tr>';});
      html += '</table>';
    }
    html += '<div style="margin-top:24px;display:grid;grid-template-columns:1fr 1fr;gap:30px">';
    html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Производитель работ:</div><div style="border-bottom:1px solid #333;min-height:18px"></div><div style="font-size:9px;color:#555;margin-top:2px">(должность, ФИО, подпись)</div></div>';
    html += '<div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Главный инженер / технадзор:</div><div style="border-bottom:1px solid #333;min-height:18px"></div><div style="font-size:9px;color:#555;margin-top:2px">(должность, ФИО, подпись)</div></div>';
    html += '</div>';
    html += '<p style="margin-top:18px;font-size:10px;color:#666;text-align:center">Форма утверждена приказом ЦСУ СССР № 613, действует. Перерасход выше 5% от нормы требует объяснений и согласования с заказчиком.</p>';
    return html;
  };

  const buildSupervisorMonthlyReport = (projectName, periodFrom, periodTo) => {
    const req = companyRequisites||{};
    const orgName = req.fullName||req.shortName||companyName||'_____';
    const project = projects.find(p=>p.name===projectName)||{};
    const inRange = (d) => !d ? false : (!periodFrom||d>=periodFrom) && (!periodTo||d<=periodTo);
    const acts = hiddenActs.filter(a=>a.projectName===projectName&&inRange(a.workDate));
    const supActs = (supervisorActs||[]).filter(a=>a.projectName===projectName&&inRange(a.date));
    const prescs = (prescriptionsList||[]).filter(pr=>pr.projectName===projectName&&pr.issuedByRole==='Технадзор'&&inRange(pr.deadline));
    let html = '<h2 style="text-align:center;margin:8px 0">МЕСЯЧНЫЙ ОТЧЁТ ТЕХНАДЗОРА</h2>';
    html += '<p style="text-align:center;font-size:12px;color:#444">Объект: <b>'+projectName+'</b> · Период: '+(periodFrom||'__.__.____')+' — '+(periodTo||'__.__.____')+'</p>';
    html += '<p style="font-size:11px"><b>Заказчик:</b> '+(project.client||'____________')+' · <b>Подрядчик:</b> '+orgName+'</p>';
    html += '<h3 style="margin-top:18px">1. Освидетельствование скрытых работ ('+acts.length+')</h3>';
    if(acts.length===0) html += '<p style="font-size:11px;color:#888">За период скрытых работ не предъявлялось</p>';
    else { html += '<table style="border-collapse:collapse;width:100%;font-size:11px"><tr style="background:#f3f4f6"><th style="border:1px solid #333;padding:4px">№ акта</th><th style="border:1px solid #333;padding:4px">Работа</th><th style="border:1px solid #333;padding:4px">Дата</th><th style="border:1px solid #333;padding:4px">Подпись технадзора</th></tr>'; acts.forEach(a=>{html+='<tr><td style="border:1px solid #333;padding:4px">'+a.actNumber+'</td><td style="border:1px solid #333;padding:4px">'+a.workName+'</td><td style="border:1px solid #333;padding:4px">'+(a.workDate||'')+'</td><td style="border:1px solid #333;padding:4px">'+(a.signedSupervisor?'✅ '+a.signedSupervisor:'⏳')+'</td></tr>';}); html += '</table>'; }
    html += '<h3 style="margin-top:18px">2. Акты осмотра ('+supActs.length+')</h3>';
    if(supActs.length===0) html += '<p style="font-size:11px;color:#888">За период не составлялись</p>';
    else supActs.forEach(a=>{html+='<div style="border:1px solid #ddd;padding:10px;margin:6px 0;font-size:11px;border-radius:4px"><b>'+a.actNumber+' · '+a.actType+'</b> ('+a.date+')<br/>'+(a.description||'')+(a.findings?'<br/><b>Обнаружено:</b> '+a.findings:'')+(a.recommendations?'<br/><b>Рекомендации:</b> '+a.recommendations:'')+'</div>';});
    html += '<h3 style="margin-top:18px">3. Предписания технадзора ('+prescs.length+')</h3>';
    if(prescs.length===0) html += '<p style="font-size:11px;color:#888">Предписаний не выдавалось</p>';
    else prescs.forEach(p=>{html+='<div style="border-left:3px solid '+(p.status==='Закрыто'?'#10b981':'#f59e0b')+';padding:8px 10px;margin:6px 0;font-size:11px"><b>'+(p.violation||p.description||'(пусто)')+'</b><br/>Статус: '+(p.status||'')+(p.deadline?' · до '+p.deadline:'')+'</div>';});
    html += '<div style="margin-top:30px;display:grid;grid-template-columns:1fr;gap:30px"><div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Технадзор:</div><div style="border-bottom:1px solid #333;min-height:18px">'+(user?user.name:'')+'</div><div style="font-size:9px;color:#555;margin-top:2px">(должность, ФИО, подпись)</div></div></div>';
    return html;
  };
  const isLeadership = () => ['директор','зам_директора'].includes(user?user.role:'');
  const isProrab = () => ['директор','зам_директора','прораб','главный_инженер'].includes(user?user.role:'');
  const isMasterRole = () => ['мастер','субподрядчик'].includes(user?user.role:'');
  const roleColor = (r) => ({'директор':'#f97316','зам_директора':'#ea580c','главный_инженер':'#8b5cf6','прораб':'#3b82f6','кладовщик':'#10b981','снабженец':'#14b8a6','бухгалтер':'#6b7280','стройконтроль':'#06b6d4','менеджер_crm':'#8b5cf6','мастер':'#ec4899','субподрядчик':'#f59e0b','сметчик':'#3b82f6','заказчик':'#06b6d4','поставщик':'#f59e0b'}[r]||'#6b7280');
  const workedDays = (id) => daysInMonth.filter(d=>timesheet[id+'-'+d]).length;
  const pwTotal = (id) => piecework.filter(p=>Number(p.staffId)===id).reduce((s,p)=>s+p.total,0);
  const calcSalary = (s) => s.payType==='сдельно'?pwTotal(s.id):Math.round((s.salary/31)*workedDays(s.id));
  const matCost = (n) => history.filter(h=>h.project===n&&h.type==='расход').reduce((s,h)=>{const m=materials.find(m=>m.name===h.material);return s+(m?m.price*h.quantity:0);},0);
  const labCost = (n) => staff.filter(s=>s.project===n).reduce((s,st)=>s+calcSalary(st),0)+piecework.filter(p=>p.project===n).reduce((s,p)=>s+p.total,0);
  const expByCategory = (pn) => {
    const r={};
    EXPENSE_CATEGORIES.forEach(c=>{r[c.id]=0;});
    r['materials']=matCost(pn);
    r['works']=labCost(pn);
    // Ручные расходы директора
    manualExpenses.filter(e=>e.project===pn).forEach(e=>{r[e.category]=(r[e.category]||0)+Number(e.amount);});
    // Непредвиденные работы
    unexpectedWorksList.filter(u=>u.projectName===pn&&u.status==='Утверждено').forEach(u=>{r['unexpected']=(r['unexpected']||0)+u.total;});
    // Подотчётные траты (только потраченное)
    accountablePayments.filter(ac=>ac.projectName===pn).forEach(ac=>{r['accountable']=(r['accountable']||0)+Number(ac.spentAmount||0);});
    // Возмещения своих трат
    ownExpenses.filter(e=>e.projectName===pn&&e.status==='Возмещено').forEach(e=>{r['accountable']=(r['accountable']||0)+Number(e.amount||0);});
    return r;
  };
  const lowStock = materials.filter(m=>m.minQuantity&&m.quantity<m.minQuantity);
  const lowMainStock = warehouseMain.filter(m=>m.minQuantity&&m.quantity<m.minQuantity);
  const unreadNotifications = myNotifications(notifications).filter(n=>!n.read).length;

  const exportToExcel = (data, filename) => {
    const headers = Object.keys(data[0]||{});
    const rows = data.map(row=>headers.map(h=>row[h]||'').join('\t'));
    const blob = new Blob(['\ufeff'+[headers.join('\t'),...rows].join('\n')],{type:'text/tab-separated-values;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href=url; a.download=filename+'.xls'; a.click();
    URL.revokeObjectURL(url);
  };

  const saveProject = async () => {
    if (!newProject.name) { alert('Введите название'); return; }
    const data = {...newProject,budget:Number(newProject.budget)};
    if (editingItem) await fetch(API+'/projects/'+editingItem.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    else { await fetch(API+'/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}); notify('Создан проект: '+newProject.name,'project'); }
    await loadAll(); addActivity((editingItem?'Обновил':'Создал')+' проект: '+newProject.name);
    if (!editingItem && newProject.clientEmail && newProject.clientPassword) {
      await fetch(API+'/users',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:newProject.client||newProject.name,email:newProject.clientEmail,password:newProject.clientPassword,role:'заказчик',projectName:newProject.name})});
      alert('Заказчик создан! Логин: '+newProject.clientEmail+' Пароль: '+newProject.clientPassword);
    }
    setNewProject({name:'',client:'',status:'Планирование',budget:'',deadline:'',progress:0,tasks:[],pricelistId:null}); setEditingItem(null); setShowForm(false);
  };

  const updateProjectProgress = async (projectName) => {
    const contracts = brigadeContracts.filter(bc=>bc.projectName===projectName);
    if(!contracts.length) return;
    let totalQty = 0, doneQty = 0;
    for(const bc of contracts){
      const res = await fetch(API+'/brigade-contract-items/'+bc.id);
      const items = await res.json();
      for(const item of items){
        totalQty += Number(item.quantity||0);
        doneQty += Number(item.doneQuantity||0);
      }
    }
    const pct = totalQty>0 ? Math.round(doneQty/totalQty*100) : 0;
    const proj = projects.find(p=>p.name===projectName);
    if(proj && proj.progress!==pct){
      await fetch(API+'/projects/'+proj.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...proj,progress:pct})});
      await loadAll();
    }
  };

  const deleteProject = async (id) => { if (window.confirm('Удалить?')) { await fetch(API+'/projects/'+id,{method:'DELETE'}); await loadAll(); } };
  const editProject = (p) => { setEditingItem(p); setNewProject({...p}); setShowForm(true); };
  const addTask = async (p) => { if (!newTask) return; await fetch(API+'/projects/'+p.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...p,tasks:[...(p.tasks||[]),newTask]})}); await loadAll(); setNewTask(''); };
  const removeTask = async (p,i) => { await fetch(API+'/projects/'+p.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...p,tasks:p.tasks.filter((_,idx)=>idx!==i)})}); await loadAll(); };

  const saveClient = async () => {
    if (!newClient.name) return;
    if (editingItem) await fetch(API+'/clients/'+editingItem.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(newClient)});
    else await fetch(API+'/clients',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(newClient)});
    await loadAll(); setNewClient({name:'',phone:'',email:'',status:'Активный',notes:''}); setEditingItem(null); setShowForm(false);
  };

  const deleteClient = async (id) => { if (window.confirm('Удалить?')) { await fetch(API+'/clients/'+id,{method:'DELETE'}); await loadAll(); } };

  const deleteMaterial = async (id) => { if (window.confirm('Удалить?')) { await fetch(API+'/materials/'+id,{method:'DELETE'}); await loadAll(); } };

  const deleteMainMaterial = async (id) => { if (window.confirm('Удалить?')) { await fetch(API+'/warehouse-main/'+id,{method:'DELETE'}); await loadAll(); } };

  const saveTool = async () => {
    if (!newTool.name) return;
    const data = {...newTool,cost:Number(newTool.cost),masterId:newTool.masterId?Number(newTool.masterId):null};
    if (editingItem) await fetch(API+'/tools/'+editingItem.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    else await fetch(API+'/tools',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    await loadAll(); setNewTool({name:'',inventoryNumber:'',cost:'',status:'На складе',location:'Основной склад',project:'',masterId:'',masterName:'',issueType:'',notes:''}); setEditingItem(null); setShowForm(false);
  };

  const deleteTool = async (id) => { if (window.confirm('Удалить?')) { await fetch(API+'/tools/'+id,{method:'DELETE'}); await loadAll(); } };

  const issueTool = async (tool) => {
    const {masterName, project, issueType} = issueToolData;
    if (!masterName) { alert('Выберите мастера'); return; }
    const updated = {...tool,status:issueType==='В счёт зарплаты'?'У мастера (куплен)':'У мастера',location:'У мастера',masterName,project,issueType};
    await fetch(API+'/tools/'+tool.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(updated)});
    await fetch(API+'/tool-history',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({toolId:tool.id,toolName:tool.name,action:'Выдача',fromLocation:tool.location,toLocation:'У мастера — '+masterName,masterName,project,issueType,condition:'Исправен',date:new Date().toISOString().split('T')[0],createdBy:user.name})});
    await loadAll(); setShowIssueToolModal(null); setIssueToolData({masterName:'',project:'',issueType:'Временно'});
  };

  const returnTool = async (tool) => {
    const updated = {...tool,status:returnToolCondition==='Исправен'?'На складе':'На ремонте',location:'Основной склад',masterName:'',project:'',issueType:''};
    await fetch(API+'/tools/'+tool.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(updated)});
    await fetch(API+'/tool-history',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({toolId:tool.id,toolName:tool.name,action:'Возврат',fromLocation:'У мастера — '+tool.masterName,toLocation:'Основной склад',masterName:tool.masterName,project:tool.project,condition:returnToolCondition,date:new Date().toISOString().split('T')[0],createdBy:user.name})});
    await loadAll(); setShowReturnToolModal(null); setReturnToolCondition('Исправен');
  };

  const autoWriteOffMaterials = async (workName, quantity, projectName) => {
    const norms = WORK_NORMS[workName];
    if (!norms) return;
    const now = new Date();
    for (const norm of norms) {
      const mat = materials.find(m=>m.name===norm.mat&&m.project===projectName);
      if (!mat) continue;
      const writeOff = norm.qty * quantity;
      const nq = Math.max(0, mat.quantity - writeOff);
      await fetch(API+'/materials/'+mat.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...mat,quantity:nq})});
      await fetch(API+'/warehouse-history',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({material:mat.name,type:'расход',quantity:writeOff,date:now.toISOString().split('T')[0],project:projectName,issuedTo:'Автосписание',issuedBy:'Система',dateTime:now.toLocaleDateString('ru-RU')})});
      if (mat.minQuantity&&nq<mat.minQuantity) notify('Заканчивается: '+mat.name,'stock');
    }
  };

  const saveStaff = async () => {
    if (!newStaff.name && !newStaff.lastName && !newStaff.firstName) { alert('Заполните хотя бы фамилию и имя'); return; }
    const fullName = newStaff.name || [newStaff.lastName, newStaff.firstName, newStaff.middleName].filter(Boolean).join(' ');
    const hasEmail = !!newStaff.email;
    const hasPassword = !!newStaff.password;
    const hasRole = !!newStaff.systemRole;
    if ((hasEmail || hasPassword || hasRole) && !(hasEmail && hasPassword && hasRole)) {
      alert('Для выдачи доступа нужны ВСЕ три поля: системная роль + email + пароль. Сейчас заполнено не всё — заполните или очистите все три.');
      return;
    }
    const data = {...newStaff,name:fullName,salary:Number(newStaff.salary)||0,role:newStaff.role||newStaff.systemRole||''};
    if (editingItem) await fetch(API+'/staff/'+editingItem.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    else await fetch(API+'/staff',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    if (hasEmail && hasPassword && hasRole) {
      const existing = users.find(u=>u.email===newStaff.email);
      if (existing) {
        alert('Пользователь с email '+newStaff.email+' уже существует — доступ не создан, сотрудник сохранён.');
      } else {
        try {
          const r = await fetch(API+'/users',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:fullName,email:newStaff.email,password:newStaff.password,role:newStaff.systemRole,projectName:newStaff.project||''})});
          if (!r.ok) {
            const err = await r.json().catch(()=>({detail:'неизвестная ошибка'}));
            alert('Сотрудник сохранён, но доступ создать не удалось: '+(err.detail||r.status));
          }
        } catch(e) {
          alert('Сотрудник сохранён, но доступ создать не удалось: '+e.message);
        }
      }
    }
    await loadAll(); setNewStaff({name:'',role:'',phone:'',salary:'',project:'',payType:'оклад',email:'',password:'',systemRole:'',lastName:'',firstName:'',middleName:'',birthDate:'',citizenship:'РФ',address:'',photoUrl:'',emailWork:'',emailPersonal:'',phoneExtra:'',passportSeries:'',passportNumber:'',passportIssuedBy:'',passportIssuedDate:'',inn:'',snils:'',specialization:'',category:'',employmentType:'',hiredDate:'',firedDate:'',status:'Активен',brigade:'',bankAccount:'',bankName:'',bankBik:'',bankCorr:'',ogrnip:'',cardNumber:'',signatureUrl:'',notes:''}); setEditingItem(null); setShowForm(false);
  };

  const deleteStaff = async (id) => { if (window.confirm('Удалить?')) { await fetch(API+'/staff/'+id,{method:'DELETE'}); await loadAll(); } };

  const addPiecework = async () => {
    if (!newPiecework.staffId||!newPiecework.description||!newPiecework.quantity||!newPiecework.pricePerUnit) return;
    await fetch(API+'/piecework',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newPiecework,total:Number(newPiecework.quantity)*Number(newPiecework.pricePerUnit),date:new Date().toISOString().split('T')[0]})});
    await loadAll(); setNewPiecework({staffId:'',description:'',unit:'м2',quantity:'',pricePerUnit:'',project:''});
  };

  const deletePiecework = async (id) => { if (window.confirm('Удалить?')) { await fetch(API+'/piecework/'+id,{method:'DELETE'}); await loadAll(); } };

  const addMasterWorks = async () => {
    const project = projects.find(p=>p.id===Number(masterProjectId));
    if (!project) return;
    const pl = pricelists.find(p=>p.id===project.pricelistId);
    const coeff = pl?pl.coefficient:1.0;
    const now = new Date();
    let hasWork = false;
    for (const [itemId,workData] of Object.entries(selectedWorks)) {
      if (!workData.quantity||Number(workData.quantity)<=0) continue;
      const item = pricelistItems.find(i=>i.id===Number(itemId));
      if (!item) continue;
      hasWork = true;
      const ppu = item.price*coeff;
      const total = Number(workData.quantity)*ppu;
      await fetch(API+'/piecework',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({staffId:String(user.id),description:item.name,unit:item.unit,quantity:Number(workData.quantity),pricePerUnit:ppu,total,project:project.name,date:now.toISOString().split('T')[0],comment:workData.comment||'',photoUrl:workData.photoUrl||''})});
      const usedMats=(workData.materials||[]).filter(m=>m.name&&Number(m.quantity)>0).map(m=>({name:m.name,quantity:Number(m.quantity),unit:m.unit||'шт'}));
      const wjRes=await fetch(API+'/work-journal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({masterId:user.id,masterName:user.name,project:project.name,description:item.name,unit:item.unit,quantity:Number(workData.quantity),pricePerUnit:ppu,total,date:now.toISOString().split('T')[0],comment:workData.comment||'',photoUrl:workData.photoUrl||'',materialsUsed:usedMats})});
      if(!wjRes.ok){const er=await wjRes.json().catch(()=>({}));alert('Не удалось списать материалы: '+(er.detail||'ошибка'));return;}
      if (workData.roomId) {
        await fetch(API+'/room-works',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({roomId:Number(workData.roomId),project:project.name,roomName:workData.roomName||'',masterId:user.id,masterName:user.name,description:item.name,surface:workData.surface||'Стены',unit:item.unit,quantity:Number(workData.quantity),pricePerUnit:ppu,total,date:now.toISOString().split('T')[0],photoUrl:workData.photoUrl||''})});
      }
    }
    if (!hasWork) { alert('Введите количество хотя бы для одной работы'); return; }
    notify(user.name+' отправил работы','work');
    await loadAll(); setSelectedWorks({}); setMasterProjectId(''); setPricelistItems([]);
    alert('Работы отправлены на проверку!');
  };

  const confirmJ = async (e) => {
    await fetch(API+'/work-journal/'+e.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Подтверждено',confirmedBy:user.name,confirmedAt:new Date().toISOString().split('T')[0]})});
    await autoWriteOffMaterials(e.description,e.quantity,e.project);
    await loadAll(); await updateProjectProgress(e.project||""); notify('Работа подтверждена: '+e.description,'work'); addActivity('Подтвердил: '+e.description);
  };

  const rejectJ = async (e,c) => {
    await fetch(API+'/work-journal/'+e.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Отклонено',confirmedBy:user.name,comment:c||''})});
    await loadAll(); setRejectingEntry(null); setRejectComment('');
  };

  const saveUser = async () => {
    if (!newUser.name||!newUser.email) return;
    if (editingItem) await fetch(API+'/users/'+editingItem.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(newUser)});
    else {
      await fetch(API+'/users',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(newUser)});
      if(newUser.role==='поставщик'){
        const existing = suppliers.find(s=>s.name===newUser.name||s.email===newUser.email);
        if(!existing){
          await fetch(API+'/suppliers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:newUser.name,email:newUser.email,phone:'',specialization:'',category:'Прочее',rating:5.0,status:'Активный'})});
        }
      }
    }
    await loadAll(); setNewUser({name:'',email:'',password:'',role:'прораб',companyName:'',inn:'',projectId:'',projectName:''}); setEditingItem(null); setShowForm(false);
  };

  const deleteUser = async (id) => {
    if (id===user.id) { alert('Нельзя удалить себя!'); return; }
    if (window.confirm('Удалить?')) { await fetch(API+'/users/'+id,{method:'DELETE'}); await loadAll(); }
  };

  const createInvite = async () => { await fetch(API+'/invite-codes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({role:newInviteRole})}); await loadAll(); };
  const deleteInvite = async (id) => { await fetch(API+'/invite-codes/'+id,{method:'DELETE'}); await loadAll(); };

  const savePricelist = async () => {
    if (!newPricelist.name) return;
    if (editingItem) await fetch(API+'/pricelists/'+editingItem.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(newPricelist)});
    else await fetch(API+'/pricelists',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(newPricelist)});
    await loadAll(); setNewPricelist({name:'',description:'',forWho:'',coefficient:1.0}); setEditingItem(null); setShowForm(false);
  };

  const deletePricelist = async (id) => {
    if (window.confirm('Удалить прайс-лист?')) {
      await fetch(API+'/pricelists/'+id,{method:'DELETE'});
      await loadAll();
      if (selectedPricelist&&selectedPricelist.id===id) { setSelectedPricelist(null); setPricelistItems([]); }
    }
  };

  const copyPricelist = async (pl) => { const name=prompt('Название копии:','Копия — '+pl.name); if (!name) return; await fetch(API+'/pricelists/'+pl.id+'/copy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})}); await loadAll(); };

  const savePlItem = async () => {
    if (!newPlItem.name||!newPlItem.price) return;
    const data = {...newPlItem,price:Number(newPlItem.price),pricelistId:selectedPricelist.id};
    if (editingPlItem&&editingPlItem.id) await fetch(API+'/pricelist-items/'+editingPlItem.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    else await fetch(API+'/pricelist-items',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    await loadPricelistItems(selectedPricelist.id);
    setNewPlItem({name:'',unit:'м2',price:'',category:''}); setEditingPlItem(null);
  };

  const saveInlinePlItem = async (item) => {
    await fetch(API+'/pricelist-items/'+item.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...item,price:Number(inlineEditPrice),pricelistId:selectedPricelist.id})});
    await loadPricelistItems(selectedPricelist.id);
    setInlineEditPl(null); setInlineEditPrice('');
  };

  const deletePlItem = async (id) => { await fetch(API+'/pricelist-items/'+id,{method:'DELETE'}); await loadPricelistItems(selectedPricelist.id); };

  const saveSupplier = async () => {
    if (!newSupplier.name) return;
    if (editingItem&&editingItem.id) await fetch(API+'/suppliers/'+editingItem.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(newSupplier)});
    else await fetch(API+'/suppliers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(newSupplier)});
    await loadAll(); setNewSupplier({name:'',phone:'',email:'',specialization:'',category:'Сыпучие и бетон',rating:5.0,status:'Активный'}); setEditingItem(null); setShowForm(false);
  };

  const deleteSupplier = async (id) => { if (window.confirm('Удалить?')) { await fetch(API+'/suppliers/'+id,{method:'DELETE'}); await loadAll(); } };

  const saveRequest = async () => {
    const validItems = newRequest.items.filter(i=>i.materialName&&i.quantity);
    if (!validItems.length||!newRequest.project) return;
    for (const item of validItems) {
      await fetch(API+'/supply-requests',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({materialName:item.materialName,quantity:Number(item.quantity),unit:item.unit,project:newRequest.project,createdBy:user.name,date:new Date().toISOString().split('T')[0],notes:newRequest.notes,selectedSuppliers:newRequest.selectedSuppliers,category:newRequest.category||''})});
    }
    notify('Новая заявка на материалы','supply');
    await loadAll(); setNewRequest({items:[{materialName:'',quantity:'',unit:'шт'}],project:'',notes:'',selectedSuppliers:[],category:''}); setShowForm(false);
  };

  const cancelRequest = async (id) => { await fetch(API+'/supply-requests/'+id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Отменена'})}); await loadAll(); };

  const saveOffer = async (requestId) => {
    if (!newOffer.supplierId||!newOffer.pricePerUnit||!newOffer.deliveryDays) { alert('Заполните все поля включая срок поставки'); return; }
    const req = supplyRequests.find(r=>r.id===requestId);
    await fetch(API+'/supplier-offers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({requestId,supplierId:Number(newOffer.supplierId),pricePerUnit:Number(newOffer.pricePerUnit),totalPrice:Number(newOffer.pricePerUnit)*(req?req.quantity:1),deliveryDays:Number(newOffer.deliveryDays),notes:newOffer.notes})});
    await loadAll(); setNewOffer({supplierId:'',pricePerUnit:'',deliveryDays:'',notes:''});
  };

  const approveOffer = async (offer) => {
    await fetch(API+'/supplier-offers/'+offer.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Утверждено'})});
    await fetch(API+'/supply-requests/'+offer.requestId,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Утверждено'})});
    const req = supplyRequests.find(r=>r.id===offer.requestId);
    await fetch(API+'/supply-history',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({supplierId:offer.supplierId,materialName:req?req.materialName:'',quantity:req?req.quantity:0,unit:req?req.unit:'',pricePerUnit:offer.pricePerUnit,totalPrice:offer.totalPrice,project:req?req.project:'',date:new Date().toISOString().split('T')[0],status:'Ожидает поставки'})});
    notify('КП утверждено','supply'); await loadAll();
  };

  const confirmDelivery = async (d) => {
    await fetch(API+'/supply-history/'+d.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Доставлено',confirmedBy:user.name})});
    const mat = materials.find(m=>m.name===d.materialName);
    if (mat) {
      await fetch(API+'/materials/'+mat.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...mat,quantity:mat.quantity+d.quantity})});
      await fetch(API+'/warehouse-history',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({material:d.materialName,type:'приход',quantity:d.quantity,date:new Date().toISOString().split('T')[0],project:d.project,issuedBy:user.name})});
    }
    notify('Доставлено: '+d.materialName,'delivery'); await loadAll();
  };

  const deleteContract = async (id) => { if (window.confirm('Удалить?')) { await fetch(API+'/contracts/'+id,{method:'DELETE'}); await loadAll(); } };
  const deleteInterimAct = async (id) => { if (window.confirm('Удалить?')) { await fetch(API+'/interim-acts/'+id,{method:'DELETE'}); await loadAll(); } };

  const toggleDay = async (staffId,day) => {
    await fetch(API+'/timesheet',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({staffId,day})});
    setTimesheet(prev=>({...prev,[staffId+'-'+day]:!prev[staffId+'-'+day]}));
  };

  const createContract = async () => {
    if (!newContract.masterId||!newContract.contractNumber||!newContract.project) return;
    await fetch(API+'/contracts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(newContract)});
    await loadAll(); setNewContract({masterId:'',masterName:'',contractType:'ГПХ',contractNumber:'',project:'',startDate:'',endDate:''}); setShowForm(false);
  };

  const createInterimAct = async () => {
    if (!newAct.masterId||!newAct.project||!newAct.periodStart||!newAct.periodEnd) return;
    const mw = workJournal.filter(j=>j.masterId===Number(newAct.masterId)&&j.project===newAct.project&&j.status==='Подтверждено');
    const total = mw.reduce((s,w)=>s+w.total,0);
    const contract = contracts.find(c=>c.masterId===Number(newAct.masterId)&&c.project===newAct.project);
    await fetch(API+'/interim-acts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newAct,masterId:Number(newAct.masterId),contractId:contract?contract.id:null,totalAmount:total,paidAmount:0})});
    notify('Акт создан: '+newAct.masterName,'act');
    await loadAll(); setNewAct({masterId:'',masterName:'',project:'',periodStart:'',periodEnd:''}); setShowForm(false);
  };

  const saveRoom = async () => {
    if (!newRoom.name||!newRoom.project) return;
    const data = {project:newRoom.project,name:newRoom.name,floorArea:Number(newRoom.floorArea)||0,wallArea:Number(newRoom.wallArea)||0,ceilingArea:Number(newRoom.ceilingArea)||0,height:Number(newRoom.height)||0,ceilingType:newRoom.ceilingType,wallMaterial:newRoom.wallMaterial,floorMaterial:newRoom.floorMaterial,windows:0,doors:0,notes:newRoom.notes};
    if (editingItem) await fetch(API+'/rooms/'+editingItem.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    else if(newRoom.roomType&&!['Комната','Кабинет','Коридор','Санузел','Кухня','Балкон','Лестница','Холл','Техническое'].includes(newRoom.roomType)){const updated=[...new Set([...customRoomTypes,newRoom.roomType])];setCustomRoomTypes(updated);localStorage.setItem('customRoomTypes',JSON.stringify(updated));}
    await fetch(API+'/rooms',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    await loadAll(); setNewRoom({project:'',name:'',floorArea:'',wallArea:'',ceilingArea:'',height:'',ceilingType:'Простой',wallMaterial:'Штукатурка',floorMaterial:'Стяжка',notes:''}); setEditingItem(null); setShowRoomForm(false);
  };

  const deleteRoom = async (id) => { if (window.confirm('Удалить?')) { await fetch(API+'/rooms/'+id,{method:'DELETE'}); await loadAll(); } };

  const saveWindow = async (roomId) => {
    if (!newWindow.width||!newWindow.height) return;
    try {
      await fetch(API+'/room-windows',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newWindow,roomId:Number(roomId)})});
      const rwin = await fetch(API+'/room-windows').then(r=>r.json()).catch(()=>[]);
      setRoomWindows(Array.isArray(rwin)?rwin:[]);
    } catch(e) {
      const win = {...newWindow,id:Date.now(),room_id:Number(roomId)};
      setRoomWindows(prev=>[...prev,win]);
    }
    setNewWindow({roomId:'',name:'Окно '+(roomWindows.filter(w=>w.room_id===roomId).length+2),width:'',height:'',windowType:'ПВХ',revealDepth:'',revealMaterial:'Штукатурка'});
  };

  const updateWindow = async (win) => {
    try {
      await fetch(API+'/room-windows/'+win.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(win)});
      const rwin = await fetch(API+'/room-windows').then(r=>r.json()).catch(()=>[]);
      setRoomWindows(Array.isArray(rwin)?rwin:[]);
    } catch(e) {}
    setEditingWindow(null);
  };

  const deleteWindow = async (id) => {
    try {
      await fetch(API+'/room-windows/'+id,{method:'DELETE'});
      setRoomWindows(prev=>prev.filter(w=>w.id!==id));
    } catch(e) { setRoomWindows(prev=>prev.filter(w=>w.id!==id)); }
  };

  const saveDoor = async (roomId) => {
    if (!newDoor.width||!newDoor.height) return;
    try {
      await fetch(API+'/room-doors',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newDoor,roomId:Number(roomId)})});
      const rdoor = await fetch(API+'/room-doors').then(r=>r.json()).catch(()=>[]);
      setRoomDoors(Array.isArray(rdoor)?rdoor:[]);
    } catch(e) {
      const door = {...newDoor,id:Date.now(),room_id:Number(roomId)};
      setRoomDoors(prev=>[...prev,door]);
    }
    setNewDoor({roomId:'',name:'Дверь '+(roomDoors.filter(d=>d.room_id===roomId).length+2),width:'',height:'',doorType:'Деревянная',doorPurpose:'Межкомнатная',revealDepth:'',revealMaterial:'Штукатурка'});
  };

  const updateDoor = async (door) => {
    try {
      await fetch(API+'/room-doors/'+door.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(door)});
      const rdoor = await fetch(API+'/room-doors').then(r=>r.json()).catch(()=>[]);
      setRoomDoors(Array.isArray(rdoor)?rdoor:[]);
    } catch(e) {}
    setEditingDoor(null);
  };

  const deleteDoor = async (id) => {
    try {
      await fetch(API+'/room-doors/'+id,{method:'DELETE'});
      setRoomDoors(prev=>prev.filter(d=>d.id!==id));
    } catch(e) { setRoomDoors(prev=>prev.filter(d=>d.id!==id)); }
  };

  const saveWeather = () => {
    if (!newWeather.projectName||!newWeather.date) return;
    const entry = {...newWeather,id:Date.now(),createdBy:user.name,temperature:Number(newWeather.temperature||0),windSpeed:Number(newWeather.windSpeed||0)};
    const updated = [...weatherLog,entry];
    setWeatherLog(updated); localStorage.setItem('weatherLog',JSON.stringify(updated));
    setNewWeather({projectName:'',date:'',temperature:'',condition:'Ясно',windSpeed:'',notes:''});
  };

  const saveTbEntry = async (data) => {
    // Сохраняем в backend (новая БД) + дублируем в localStorage для совместимости со старыми экранами
    const payload = {
      projectName: data.project || data.projectName || '',
      masterName: data.masterName || '',
      instructor: data.instructor || (user?user.name:''),
      instructionType: data.type || data.instructionType || 'Первичный инструктаж на рабочем месте',
      program: data.program || '',
      instructionText: data.instructionText || '',
      participants: data.participants || [],
      photoUrl: data.photoUrl || '',
      date: data.date || new Date().toISOString().split('T')[0],
    };
    let saved = null;
    try {
      const res = await fetch(API+'/tb-journal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      saved = await res.json();
    } catch(e){ console.error('TB save error', e); }
    const localEntry = {...payload,id:saved?saved.id:Date.now(),createdBy:user.name,project:payload.projectName,type:payload.instructionType};
    const updated = [...tbJournal,localEntry];
    setTbJournal(updated); localStorage.setItem('tbJournal',JSON.stringify(updated));
  };

  const saveWarehouse = async () => {
    if (!newWarehouse.name) return;
    if (editingItem) await fetch(API+'/warehouses/'+editingItem.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(newWarehouse)});
    else await fetch(API+'/warehouses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(newWarehouse)});
    await loadAll(); setNewWarehouse({name:'',city:'',address:'',notes:''}); setEditingItem(null); setShowForm(false);
  };

  const deleteWarehouse = async (id) => { if (window.confirm('Удалить склад?')) { await fetch(API+'/warehouses/'+id,{method:'DELETE'}); await loadAll(); } };

  const saveCompanyRequisites = async () => {
    await fetch(API+'/company-requisites',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(companyReqForm)});
    await loadAll(); alert('Реквизиты сохранены!');
  };

  const saveProjectStage = async (projectId, projectName) => {
    if (!newStage.name) return;
    await fetch(API+'/project-stages',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newStage,projectId,projectName,progress:Number(newStage.progress)||0})});
    await loadAll(); setNewStage({name:'',status:'Не начат',startDate:'',endDate:'',progress:0,responsible:'',notes:''});
  };

  const updateStage = async (stage) => {
    await fetch(API+'/project-stages/'+stage.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(stage)});
    await loadAll();
  };

  const deleteStage = async (id) => { if (window.confirm('Удалить?')) { await fetch(API+'/project-stages/'+id,{method:'DELETE'}); await loadAll(); } };

  const saveChecklist = async (projectId, projectName) => {
    if (!newChecklist.name) return;
    const res = await fetch(API+'/project-checklists',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newChecklist,projectId,projectName,createdBy:user.name,createdAt:new Date().toISOString().split('T')[0]})});
    const cl = await res.json();
    if (newChecklist.template && CHECKLIST_TEMPLATES[newChecklist.template]) {
      const items = CHECKLIST_TEMPLATES[newChecklist.template];
      for (let i=0; i<items.length; i++) {
        await fetch(API+'/checklist-items',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({checklistId:cl.id,name:items[i],checked:false,orderNum:i})});
      }
    }
    await loadAll(); setNewChecklist({name:'',template:''});
  };

  const toggleChecklistItem = async (item) => {
    await fetch(API+'/checklist-items/'+item.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({checked:!item.checked,checkedBy:!item.checked?user.name:'',checkedAt:!item.checked?new Date().toISOString().split('T')[0]:''})});
    await loadChecklistItems(item.checklistId);
  };

  const savePrescription = async (projectName) => {
    if (!newPrescription.violation) return;
    await fetch(API+'/prescriptions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newPrescription,projectName,issuedBy:user.name,issuedByRole:user.role})});
    await loadAll(); setNewPrescription({number:'',violation:'',deadline:'',responsible:'',photoUrl:''});
  };

  const saveUnexpectedWork = async (projectName) => {
    if (!newUnexpected.description) return;
    await fetch(API+'/unexpected-works',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newUnexpected,projectName,quantity:Number(newUnexpected.quantity)||0,price:Number(newUnexpected.price)||0,total:Number(newUnexpected.quantity||0)*Number(newUnexpected.price||0),addedBy:user.name,addedByRole:user.role})});
    notify('Новая непредвиденная работа: '+newUnexpected.description,'unexpected');
    await loadAll(); setNewUnexpected({description:'',unit:'шт',quantity:'',price:'',notes:'',photoUrl:''});
  };

  const approveUnexpectedWork = async (work, price) => {
    const total = work.quantity * Number(price);
    await fetch(API+'/unexpected-works/'+work.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Утверждено',price:Number(price),total,approvedBy:user.name,approvedAt:new Date().toISOString().split('T')[0]})});
    await loadAll();
  };

  const navigateTo = (p) => {
    if (canAccess(p)) {
      setActivePage(p); setShowForm(false); setExpandedProject(null);
      setExpandedClient(null); setEditingItem(null); setEditingPlItem(null);
      setShowPiecework(false); setSelectedPricelist(null); setPricelistItems([]);
      setShowInvites(false); setShowOffers(null);
      setShowSearch(false); setGlobalSearch(''); setShowArchive(false);
      setSelectedInventory(null); setSidebarVisible(false);
      setSelectedWarehouseProject(null); setInlineEditPl(null); setShowRoomForm(false);
    }
  };

  const searchResults = globalSearch.length>=2 ? [
    ...projects.filter(p=>p.name.toLowerCase().includes(globalSearch.toLowerCase())).map(p=>({icon:'📋',title:p.name,subtitle:p.client,page:'projects'})),
    ...clients.filter(c=>c.name.toLowerCase().includes(globalSearch.toLowerCase())).map(c=>({icon:'👥',title:c.name,subtitle:c.phone,page:'clients'})),
    ...materials.filter(m=>m.name.toLowerCase().includes(globalSearch.toLowerCase())).map(m=>({icon:'📦',title:m.name,subtitle:m.quantity+' '+m.unit,page:'warehouse'})),
    ...tools.filter(t=>t.name.toLowerCase().includes(globalSearch.toLowerCase())).map(t=>({icon:'🔧',title:t.name,subtitle:t.status,page:'warehouse'})),
  ].slice(0,8) : [];

  const financeUsers = users.filter(u=>['директор','зам_директора','бухгалтер'].includes(u.role));
  if (isMasterRole()) {
    if (showProfileForm) {
      return (
        <div style={{display:'flex',justifyContent:'center',alignItems:'center',minHeight:'100vh',backgroundColor:C.bg,padding:'20px'}}>
          <div style={{...card,padding:'40px',width:'500px',maxHeight:'90vh',overflowY:'auto'}}>
            <h2 style={{textAlign:'center',color:C.text,marginBottom:'25px',fontSize:'22px',fontWeight:'800'}}>{user.role==='субподрядчик'?'🔩 Заполните профиль субподрядчика':'👷 Заполните профиль'}</h2>
            <input placeholder="ФИО *" value={profileData.fullName} onChange={e=>setProfileData({...profileData,fullName:e.target.value})} style={inp}/>
            <input placeholder="Паспорт серия и номер" value={profileData.passport} onChange={e=>setProfileData({...profileData,passport:e.target.value})} style={inp}/>
            <input placeholder="ИНН *" value={profileData.inn} onChange={e=>setProfileData({...profileData,inn:e.target.value})} style={inp}/>
            <select value={profileData.contractType} onChange={e=>setProfileData({...profileData,contractType:e.target.value})} style={inp}><option>ГПХ</option><option>ИП</option><option>Самозанятый</option></select>
            {profileData.contractType==='ИП'&&<input placeholder="ОГРНИП" value={profileData.ogrnip} onChange={e=>setProfileData({...profileData,ogrnip:e.target.value})} style={inp}/>}
            <input placeholder="Номер счёта *" value={profileData.bankAccount} onChange={e=>setProfileData({...profileData,bankAccount:e.target.value})} style={inp}/>
            <input placeholder="Банк" value={profileData.bankName} onChange={e=>setProfileData({...profileData,bankName:e.target.value})} style={inp}/>
            <input placeholder="Телефон" value={profileData.phone} onChange={e=>setProfileData({...profileData,phone:e.target.value})} style={inp}/>
            <select value={profileData.specialization} onChange={e=>setProfileData({...profileData,specialization:e.target.value})} style={inp}>
              <option value="">Специализация</option>
              {['Каменщик','Электрик','Сантехник','Отделочник','Кровельщик','Бетонщик','Монтажник','Плотник','Сварщик','Разнорабочий','Общестроительные работы','Электромонтаж','Сантехника','Кровельные работы'].map(s=><option key={s}>{s}</option>)}
            </select>
            <div style={{backgroundColor:C.infoLight,border:'1.5px solid '+C.infoBorder,padding:'14px',borderRadius:'10px',marginBottom:'15px'}}>
              <b style={{color:C.info,fontSize:'13px'}}>📄 Согласие на обработку ПД</b>
              <div style={{display:'flex',gap:'8px',margin:'10px 0'}}>
                <button onClick={()=>showPreview(PD_CONSENT_TEXT({fullName:profileData.fullName,passport:profileData.passport,inn:profileData.inn}),'Согласие на ПД')} style={btnB}><Eye size={14}/>Просмотр</button>
                <button onClick={()=>doPrint(PD_CONSENT_TEXT({fullName:profileData.fullName,passport:profileData.passport,inn:profileData.inn}))} style={btnO}><Printer size={14}/>Распечатать</button>
              </div>
              <label style={{display:'flex',alignItems:'flex-start',gap:'12px',cursor:'pointer'}}>
                <input type="checkbox" checked={consentChecked} onChange={e=>setConsentChecked(e.target.checked)} style={{marginTop:'3px',width:'18px',height:'18px',accentColor:C.accent}}/>
                <span style={{fontSize:'13px',color:C.textSec}}>Согласен на обработку персональных данных согласно ФЗ №152-ФЗ <span style={{color:C.danger}}>*</span></span>
              </label>
            </div>
            <button onClick={saveProfile} style={{...btnO,width:'100%',padding:'13px',justifyContent:'center',fontSize:'15px'}}>✅ Сохранить профиль</button>
            <button onClick={()=>setShowProfileForm(false)} style={{width:'100%',padding:'10px',marginTop:'10px',backgroundColor:'transparent',border:'1.5px solid '+C.border,borderRadius:'8px',cursor:'pointer',color:C.textSec}}>Позже</button>
          </div>
        </div>
      );
    }

    const myWorks = piecework.filter(p=>Number(p.staffId)===user.id);
    const myTotal = myWorks.reduce((s,p)=>s+p.total,0);
    const myIssues = materialTransfers.filter(t=>t.toPerson===user.name).map(t=>({id:t.id,materialName:t.materialName,quantity:t.quantity,unit:t.unit,project:t.projectName,confirmed:t.signed}));
    const categories = [...new Set(pricelistItems.map(i=>i.category))];
    const myProjects = [...new Set(myWorks.map(w=>w.project))];
    const myContract = contracts.find(c=>c.masterId===user.id);
    const myActs = interimActs.filter(a=>a.masterId===user.id);
    const projectRooms = masterProjectId ? rooms.filter(r=>r.project===(projects.find(p=>p.id===Number(masterProjectId))?.name||'')) : [];
    const myTools = tools.filter(t=>t.masterName===(masterProfile?.fullName||user.name)&&t.status.includes('У мастера'));

    return (
      <div style={{display:'flex',flexDirection:'column',minHeight:'100vh',backgroundColor:C.bg}}>
        {showPhotoModal&&(<div onClick={()=>setShowPhotoModal(null)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.9)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:2000,cursor:'pointer'}}><img src={showPhotoModal} alt="" style={{maxWidth:'90%',maxHeight:'90%',borderRadius:'12px'}}/></div>)}
        {previewContent&&<PreviewModal content={previewContent} title={previewTitle} onClose={()=>setPreviewContent(null)}/>}
        <div style={{flex:1,padding:'15px',paddingBottom:'90px',overflowY:'auto'}}>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px'}}>
            <div><h2 style={{margin:0,color:C.text,fontSize:'20px',fontWeight:'800'}}>СтройКа</h2><p style={{margin:0,color:C.textSec,fontSize:'12px'}}>{user.name+' — '+(ROLE_LABELS[user.role]||user.role)}</p></div>
            <button onClick={checkinGeo} style={{...btnGr,padding:'8px 16px',fontSize:'12px'}}><MapPin size={14}/>Отметиться</button>
          </div>

          {activePage==='works'&&(<div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px'}}>
              <h3 style={{color:C.text,margin:0,fontSize:'18px',fontWeight:'700'}}>Мои работы</h3>
              <div style={{background:'linear-gradient(135deg,#f97316,#ea580c)',padding:'8px 18px',borderRadius:'10px',fontWeight:'700',fontSize:'14px',color:'white'}}>{myTotal.toLocaleString()+' ₽'}</div>
            </div>
            <div style={{...card,padding:'20px',marginBottom:'15px'}}>
              <h4 style={{marginBottom:'15px',color:C.text,fontSize:'14px',fontWeight:'600'}}>Добавить работы</h4>
              <select value={masterProjectId} onChange={async e=>{const pid=e.target.value;setMasterProjectId(pid);setSelectedWorks({});const proj=projects.find(p=>p.id===Number(pid));if(proj&&proj.pricelistId) await loadPricelistItems(proj.pricelistId);else setPricelistItems([]);}} style={inp}><option value="">Выберите объект</option>{projects.filter(p=>p.status==='В работе').map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
              {masterProjectId&&(()=>{
                const projName=projects.find(p=>p.id===Number(masterProjectId))?.name||'';
                const projEstimates=estimatesList.filter(e=>e.projectName===projName);
                const myItems=[];
                projEstimates.forEach(est=>(est.sections||[]).forEach((s,si)=>(s.items||[]).forEach((it,ii)=>{
                  if(it.brigadeName&&(it.brigadeName===user.name||(user.brigade&&it.brigadeName===user.brigade))){
                    myItems.push({estId:est.id,estName:est.name,sectionIdx:si,itemIdx:ii,section:s.name,...it});
                  }
                })));
                if(myItems.length===0) return null;
                return(<div style={{...card,padding:'14px',marginBottom:'15px',backgroundColor:C.accentLight,border:'1.5px solid '+C.accentBorder}}>
                  <b style={{color:C.accent,fontSize:'13px',display:'block',marginBottom:'10px'}}>🎯 Мои работы по смете ({myItems.length})</b>
                  {myItems.map((mi,n)=>{const qty=Number(mi.quantity)||0;const done=Number(mi.doneQuantity)||0;const remain=Math.max(0,qty-done);return(<div key={n} style={{padding:'10px',marginBottom:'6px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px'}}>
                      <div style={{flex:1}}>
                        <b style={{fontSize:'12px',color:C.text}}>{mi.name}</b>
                        <p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{mi.section+' · план '+qty+' '+mi.unit+' · сделано '+done+' · осталось '+remain+' '+mi.unit}</p>
                      </div>
                      <input type='number' placeholder={'+'+mi.unit} value={mi.doneQuantity||''} onChange={async e=>{
                        const raw=Number(e.target.value);
                        if(qty>0&&raw>qty){alert('План '+qty+' '+mi.unit+'. Нельзя поставить больше.');return;}
                        const est=estimatesList.find(e=>e.id===mi.estId);
                        if(!est) return;
                        const newSections=est.sections.map((s,si)=>si===mi.sectionIdx?{...s,items:s.items.map((it,ii)=>ii===mi.itemIdx?{...it,doneQuantity:raw}:it)}:s);
                        const updated={...est,sections:newSections};
                        setEstimatesList(prev=>prev.map(e=>e.id===updated.id?updated:e));
                        await persistEstimate(updated);
                      }} style={{...inp,marginBottom:0,width:'80px',fontSize:'12px',padding:'4px 6px'}}/>
                      <span style={{fontSize:'11px',color:C.success,fontWeight:'600',whiteSpace:'nowrap'}}>{(done*(Number(mi.priceWork||0)+Number(mi.priceMaterial||0))).toLocaleString('ru-RU')+' ₽'}</span>
                    </div>
                  </div>);})}
                </div>);
              })()}
              {masterProjectId&&brigadeContracts.filter(bc=>bc.projectName===(projects.find(p=>p.id===Number(masterProjectId))?.name)).length>0&&(<div style={{marginBottom:'15px'}}>
                <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'10px'}}>Наряды по объекту (старая система):</b>
                {brigadeContracts.filter(bc=>bc.projectName===(projects.find(p=>p.id===Number(masterProjectId))?.name)).map(bc=>(<div key={bc.id} style={{...card,padding:'12px',marginBottom:'8px',cursor:'pointer',border:'1.5px solid '+C.border}} onClick={async()=>{const res=await fetch(API+'/brigade-contract-items/'+bc.id);const items=await res.json();setSelectedBrigadeContract(bc);setBrigadeContractItems(items);if(bc.pricelistId) await loadPricelistItems(bc.pricelistId);}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                    <div><b style={{fontSize:'13px',color:C.text}}>{bc.brigadeName}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{bc.contractorType+' · '+bc.status}</p></div>
                    <ChevronRight size={16} color={C.textMuted}/>
                  </div>
                  {selectedBrigadeContract?.id===bc.id&&brigadeContractItems.length>0&&(<div style={{marginTop:'10px',borderTop:'1px solid '+C.border,paddingTop:'10px'}}>
                    {brigadeContractItems.map((item,idx)=>(<div key={item.id} style={{display:'flex',alignItems:'center',gap:'8px',padding:'6px 0',borderBottom:'1px solid '+C.border}}>
                      <div style={{flex:1}}>
                        <b style={{fontSize:'12px',color:C.text}}>{item.name}</b>
                        <p style={{color:C.textSec,margin:0,fontSize:'11px'}}>{(Number(item.quantity)>0?'план '+item.quantity+' '+item.unit+' · ':'')+'выполнено: '+(item.doneQuantity||0)+' '+item.unit+(Number(item.quantity)>0?' · осталось '+Math.max(0,Number(item.quantity)-Number(item.doneQuantity||0))+' '+item.unit:'')+' · цена '+Number(item.priceBrigade||0).toLocaleString()+' ₽/'+item.unit}</p>
                      </div>
                      <input type='number' placeholder={item.unit} value={item.doneQuantity||''} onChange={async e=>{const raw=Number(e.target.value);const plan=Number(item.quantity)||0;if(plan>0&&raw>plan){alert('По смете план '+plan+' '+item.unit+'. Нельзя поставить больше — это перебор по смете.');return;}const val=plan>0?Math.min(raw,plan):raw;const updated={...item,doneQuantity:val,status:plan>0&&val>=plan?'Выполнено':val>0?'В работе':'Не начато'};setBrigadeContractItems(prev=>prev.map((it,i)=>i===idx?updated:it));await fetch(API+'/brigade-contract-items/'+item.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(updated)});}} style={{...inp,marginBottom:0,width:'80px',fontSize:'12px',padding:'4px 6px'}}/>
                      <span style={{fontSize:'11px',color:C.accent,fontWeight:'600'}}>{Math.round((item.doneQuantity||0)*item.priceBrigade).toLocaleString()+' ₽'}</span>
                    </div>))}
                  <div style={{marginTop:'8px',marginBottom:'8px'}}>
                    <p style={{color:'#6b7280',fontSize:'12px',margin:'0 0 6px'}}>Фото отчёт:</p>
                    <input type='file' accept='image/*' multiple onChange={async e=>{
                      const files=Array.from(e.target.files);
                      const urls=[];
                      for(const file of files){const url=await uploadPhoto(file);urls.push(url);}
                      setMasterReportPhotos(urls);
                    }} style={{fontSize:'12px'}}/>
                    {masterReportPhotos&&masterReportPhotos.length>0&&(<div style={{display:'flex',gap:'6px',marginTop:'6px',flexWrap:'wrap'}}>{masterReportPhotos.map((url,i)=>(<img key={i} src={url} alt='' style={{width:'60px',height:'60px',objectFit:'cover',borderRadius:'6px'}}/>))}</div>)}
                  </div>
                  <button onClick={async()=>{
                      const doneItems=brigadeContractItems.filter(i=>i.doneQuantity>0);
                      if(!doneItems.length){alert('Введите выполненные объёмы');return;}
                      for(const item of doneItems){
                        const existing=workJournal.find(j=>j.description===item.name&&j.masterId===user.id&&j.project===(selectedBrigadeContract?.projectName||'')&&j.status==='На проверке');
                        if(existing){
                          await fetch(API+'/work-journal/'+existing.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...existing,quantity:item.doneQuantity,total:Math.round(item.doneQuantity*item.priceBrigade),date:new Date().toISOString().split('T')[0]})});
                        } else {
                          await fetch(API+'/work-journal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:selectedBrigadeContract?.projectName||'',description:item.name,quantity:item.doneQuantity,unit:item.unit,date:new Date().toISOString().split('T')[0],masterName:user.name,masterId:user.id,total:Math.round(item.doneQuantity*item.priceBrigade),status:'На проверке',photoUrl:(masterReportPhotos||[]).join(',')})});
                        }
                      }
                      alert('Отправлено на проверку прорабу!');
                      await loadAll();
                      await updateProjectProgress(selectedBrigadeContract?.projectName||'');
                    }} style={{...btnO,marginTop:'10px',width:'100%',justifyContent:'center'}}><Check size={14}/>Отправить на проверку</button>
                  </div>)}
                </div>))}
              </div>)}
              {pricelistItems.length>0&&!selectedBrigadeContract&&(<>
                {categories.map(cat=>(<div key={cat} style={{marginBottom:'15px'}}>
                  <div style={{color:C.accent,fontSize:'11px',fontWeight:'700',marginBottom:'8px',borderBottom:'1.5px solid '+C.border,paddingBottom:'5px',textTransform:'uppercase'}}>{cat}</div>
                  {pricelistItems.filter(i=>i.category===cat).map(item=>{
                    const proj=projects.find(p=>p.id===Number(masterProjectId));
                    const pl=proj&&pricelists.find(p=>p.id===proj.pricelistId);
                    const price=item.price*(pl?pl.coefficient:1.0);
                    const isSel=selectedWorks[item.id]!==undefined;
                    return(<div key={item.id} style={{padding:'12px',marginBottom:'8px',borderRadius:'10px',border:'1.5px solid '+(isSel?C.accent:C.border),backgroundColor:isSel?C.accentLight:C.bgWhite}}>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                        <label style={{display:'flex',alignItems:'center',gap:'12px',cursor:'pointer',flex:1}}>
                          <input type="checkbox" checked={isSel} onChange={e=>{if(e.target.checked) setSelectedWorks(prev=>({...prev,[item.id]:{quantity:'',comment:'',photoUrl:'',roomId:'',roomName:'',surface:'Стены',materials:[]}}));else{const u={...selectedWorks};delete u[item.id];setSelectedWorks(u);}}} style={{width:'18px',height:'18px',accentColor:C.accent}}/>
                          <span style={{fontWeight:isSel?'600':'400',fontSize:'13px',color:C.text}}>{item.name}</span>
                        </label>
                        <span style={{color:C.accent,fontWeight:'700',fontSize:'12px',whiteSpace:'nowrap'}}>{price.toLocaleString()+' ₽/'+item.unit}</span>
                      </div>
                      {isSel&&(<div style={{paddingLeft:'30px',marginTop:'10px'}}>
                        <input placeholder={'Количество ('+item.unit+')'} type="number" value={selectedWorks[item.id]?.quantity||''} onChange={e=>setSelectedWorks(prev=>({...prev,[item.id]:{...prev[item.id],quantity:e.target.value}}))} style={inp}/>
                        {projectRooms.length>0&&(<><select value={selectedWorks[item.id]?.roomId||''} onChange={e=>{const room=projectRooms.find(r=>r.id===Number(e.target.value));setSelectedWorks(prev=>({...prev,[item.id]:{...prev[item.id],roomId:e.target.value,roomName:room?.name||''}}));}} style={inp}><option value="">Выберите помещение</option>{projectRooms.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select><select value={selectedWorks[item.id]?.surface||'Стены'} onChange={e=>setSelectedWorks(prev=>({...prev,[item.id]:{...prev[item.id],surface:e.target.value}}))} style={inp}>{SURFACES.map(s=><option key={s}>{s}</option>)}</select></>)}
                        <input placeholder="Комментарий" value={selectedWorks[item.id]?.comment||''} onChange={e=>setSelectedWorks(prev=>({...prev,[item.id]:{...prev[item.id],comment:e.target.value}}))} style={inp}/>
                        <input type="file" accept="image/*" onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0]);setSelectedWorks(prev=>({...prev,[item.id]:{...prev[item.id],photoUrl:url}}));}}} style={{...inp,padding:'8px'}}/>
                        {(()=>{
                          const proj=projects.find(pp=>pp.id===Number(masterProjectId));
                          const projMats=proj?materials.filter(m=>m.project===proj.name&&Number(m.quantity||0)>0):[];
                          const used=selectedWorks[item.id]?.materials||[];
                          const usedMap={};used.forEach(u=>{usedMap[u.name]=u;});
                          if(!projMats.length) return null;
                          return(<div style={{marginTop:'8px',padding:'8px',backgroundColor:C.bg,borderRadius:'8px',border:'1px solid '+C.border}}>
                            <p style={{fontSize:'11px',color:C.textSec,margin:'0 0 6px'}}>📦 Использованные материалы (опционально, спишутся со склада объекта):</p>
                            <div style={{maxHeight:'150px',overflowY:'auto'}}>
                              {projMats.map(m=>{const checked=!!usedMap[m.name];return(<div key={m.id} style={{display:'flex',alignItems:'center',gap:'6px',padding:'4px 0',fontSize:'11px'}}>
                                <input type='checkbox' checked={checked} onChange={e=>{
                                  const next=e.target.checked?[...used,{name:m.name,quantity:'',unit:m.unit}]:used.filter(u=>u.name!==m.name);
                                  setSelectedWorks(prev=>({...prev,[item.id]:{...prev[item.id],materials:next}}));
                                }} style={{width:'14px',height:'14px',cursor:'pointer'}}/>
                                <span style={{flex:1,color:C.text}}>{m.name}</span>
                                <span style={{color:C.textSec}}>остаток {m.quantity} {m.unit}</span>
                                {checked&&<input type='number' placeholder='кол-во' value={usedMap[m.name].quantity} max={m.quantity} onChange={e=>{
                                  const next=used.map(u=>u.name===m.name?{...u,quantity:e.target.value}:u);
                                  setSelectedWorks(prev=>({...prev,[item.id]:{...prev[item.id],materials:next}}));
                                }} style={{width:'70px',padding:'3px 6px',border:'1px solid '+C.border,borderRadius:'4px',fontSize:'11px'}}/>}
                              </div>);})}
                            </div>
                          </div>);
                        })()}
                      <button onClick={async()=>{
                      const doneItems=brigadeContractItems.filter(i=>i.doneQuantity>0);
                      if(!doneItems.length){alert('Введите выполненные объёмы');return;}
                      for(const item of doneItems){
                        const existing=workJournal.find(j=>j.description===item.name&&j.masterId===user.id&&j.status==='На проверке');
                        if(existing){await fetch(API+'/work-journal/'+existing.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...existing,quantity:item.doneQuantity,total:Math.round(item.doneQuantity*item.priceBrigade),date:new Date().toISOString().split('T')[0]})});}
                        else{await fetch(API+'/work-journal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:selectedBrigadeContract?.projectName||'',description:item.name,quantity:item.doneQuantity,unit:item.unit,date:new Date().toISOString().split('T')[0],masterName:user.name,masterId:user.id,total:Math.round(item.doneQuantity*item.priceBrigade),status:'На проверке',photoUrl:(masterReportPhotos||[]).join(',')})});}
                      }
                      alert('Отправлено на проверку прорабу!');
                      await loadAll();
                      await updateProjectProgress(selectedBrigadeContract?.projectName||'');
                    }} style={{...btnO,marginTop:'10px',width:'100%',justifyContent:'center'}}><Check size={14}/>Отправить на проверку</button>
                  </div>)}
                    </div>);
                  })}
                </div>))}
                <button onClick={addMasterWorks} style={{...btnO,width:'100%',padding:'12px',justifyContent:'center'}}>Отправить работы</button>
              </>)}
              {pricelistItems.length===0&&masterProjectId&&<p style={{color:C.textMuted,textAlign:'center',padding:'20px'}}>Прайс-лист не привязан к проекту</p>}
            </div>
            <div style={{...card,padding:'20px'}}>
              <h4 style={{marginBottom:'15px',color:C.text,fontSize:'14px',fontWeight:'600'}}>Последние работы</h4>
              {myWorks.slice(0,5).map(w=>{const je=workJournal.find(j=>j.masterId===user.id&&j.description===w.description&&j.date===w.date);return(<div key={w.id} style={{padding:'12px 0',borderBottom:'1.5px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center'}}><div><b style={{fontSize:'13px',color:C.text}}>{w.description}</b><p style={{color:C.textSec,margin:'3px 0',fontSize:'12px'}}>{w.quantity+' '+w.unit+' · '+w.project+' · '+w.date}</p>{je&&<span style={badge(je.status==='Подтверждено'?C.success:je.status==='Отклонено'?C.danger:C.warning,je.status==='Подтверждено'?C.successLight:je.status==='Отклонено'?C.dangerLight:C.warningLight,je.status==='Подтверждено'?C.successBorder:je.status==='Отклонено'?C.dangerBorder:C.warningBorder)}>{je.status}</span>}</div><b style={{color:C.success,fontSize:'13px',whiteSpace:'nowrap'}}>{(w.total||0).toLocaleString()+' ₽'}</b></div>);})}
              {myWorks.length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'20px'}}>Работ пока нет</p>}
            </div>
          </div>)}

          {activePage==='history'&&(<div>
            <h3 style={{color:C.text,marginBottom:'20px',fontSize:'18px',fontWeight:'700'}}>История заработка</h3>
            <div style={{background:'linear-gradient(135deg,#f97316,#ea580c)',padding:'16px 20px',borderRadius:'12px',marginBottom:'20px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
              <b style={{color:'white',fontSize:'14px'}}>Всего заработано:</b>
              <b style={{color:'white',fontSize:'20px',fontWeight:'800'}}>{myTotal.toLocaleString()+' ₽'}</b>
            </div>
            {myProjects.map(projectName=>{const projectWorks=myWorks.filter(w=>w.project===projectName);const projectTotal=projectWorks.reduce((s,w)=>s+w.total,0);const isOpen=expandedProject===projectName;return(<div key={projectName} style={{...card,marginBottom:'10px'}}><div style={{padding:'16px',display:'flex',justifyContent:'space-between',alignItems:'center',cursor:'pointer'}} onClick={()=>setExpandedProject(isOpen?null:projectName)}><div><b style={{color:C.text,fontSize:'14px'}}>{projectName}</b><p style={{color:C.textSec,margin:'3px 0',fontSize:'12px'}}>{projectWorks.length+' работ'}</p></div><div style={{display:'flex',alignItems:'center',gap:'12px'}}><b style={{color:C.success,fontSize:'15px'}}>{projectTotal.toLocaleString()+' ₽'}</b>{isOpen?<ChevronUp size={16} color={C.textMuted}/>:<ChevronDown size={16} color={C.textMuted}/>}</div></div>{isOpen&&(<div style={{borderTop:'1.5px solid '+C.border,padding:'12px 16px'}}>{projectWorks.map(w=>(<div key={w.id} style={{padding:'8px 0',borderBottom:'1px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center'}}><div><b style={{fontSize:'13px',color:C.text}}>{w.description}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{w.quantity+' '+w.unit+' · '+w.date}</p></div><b style={{color:C.success,fontSize:'13px'}}>{(w.total||0).toLocaleString()+' ₽'}</b></div>))}</div>)}</div>);})}
            {myProjects.length===0&&<div style={{...card,padding:'40px',textAlign:'center',color:C.textMuted}}>Нет данных</div>}
          </div>)}

          {activePage==='materials'&&(<div>
            <h3 style={{color:C.text,marginBottom:'20px',fontSize:'18px',fontWeight:'700'}}>Мои инструменты</h3>
            {myTools.length>0&&(<div style={{...card,padding:'20px',marginBottom:'16px',borderLeft:'3px solid '+C.purple}}><h4 style={{color:C.purple,marginBottom:'12px',fontSize:'14px',fontWeight:'600'}}>🔧 Инструменты за мной:</h4>{myTools.map(t=>(<div key={t.id} style={{padding:'8px 0',borderBottom:'1px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center'}}><div><b style={{color:C.text,fontSize:'13px'}}>{t.name}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{(t.inventoryNumber?' № '+t.inventoryNumber:'')+(t.project?' · '+t.project:'')}</p>{t.issueType==='В счёт зарплаты'&&<span style={badge(C.danger,C.dangerLight,C.dangerBorder)}>{'Удержание: '+(t.cost||0).toLocaleString()+' ₽'}</span>}</div><span style={badge(C.accent,C.accentLight,C.accentBorder)}>{t.status}</span></div>))}</div>)}
            {myIssues.map(issue=>(<div key={issue.id} style={{...card,padding:'16px',marginBottom:'10px',borderLeft:'3px solid '+(issue.confirmed?C.success:C.warning)}}><div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}><div><b style={{color:C.text}}>{issue.materialName}</b><p style={{color:C.textSec,margin:'3px 0',fontSize:'12px'}}>{issue.quantity+' '+issue.unit+' · '+issue.project}</p></div>{issue.confirmed?<span style={badge(C.success,C.successLight,C.successBorder)}>✅ Принято</span>:<button onClick={()=>confirmMaterialReceipt(issue.id)} style={btnGr}><Check size={14}/>Подтвердить</button>}</div></div>))}
            {myIssues.length===0&&myTools.length===0&&<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Ничего нет</div>}
          </div>)}

          {activePage==='documents'&&(<div>
            <h3 style={{color:C.text,marginBottom:'20px',fontSize:'18px',fontWeight:'700'}}>Мои документы</h3>
            <div style={{...card,padding:'20px',marginBottom:'15px'}}>
              <h4 style={{color:C.text,marginBottom:'10px',fontSize:'14px',fontWeight:'600'}}>📋 Согласие на обработку ПД</h4>
              <div style={{display:'flex',gap:'8px',marginBottom:'10px',flexWrap:'wrap'}}>
                <button onClick={()=>showPreview(PD_CONSENT_TEXT({fullName:masterProfile?.fullName||user.name,passport:masterProfile?.passport||'',inn:masterProfile?.inn||''}),'Согласие на ПД')} style={btnB}><Eye size={14}/>Просмотр</button>
                <button onClick={()=>doPrint(PD_CONSENT_TEXT({fullName:masterProfile?.fullName||user.name,passport:masterProfile?.passport||'',inn:masterProfile?.inn||''}))} style={btnO}><Printer size={14}/>Распечатать</button>
              </div>
              {(()=>{const consent=pdConsents.find(c=>c.userId===user.id);if(consent?.scanUrl) return(<div style={{backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder,padding:'10px',borderRadius:'8px',display:'flex',alignItems:'center',gap:'10px'}}><CheckCircle size={16} color={C.success}/><span style={{color:C.success,fontSize:'13px'}}>Скан загружен</span></div>);return(<label style={{cursor:'pointer',backgroundColor:C.infoLight,padding:'10px',borderRadius:'8px',fontSize:'13px',color:C.info,border:'1.5px solid '+C.infoBorder,display:'inline-flex',alignItems:'center',gap:'8px'}}><Upload size={14}/>Загрузить скан<input type="file" accept="image/*,application/pdf" style={{display:'none'}} onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0]);await fetch(API+'/pd-consents',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({userId:user.id,signedAt:new Date().toLocaleString('ru-RU'),scanUrl:url,uploadedBy:user.name})});await loadAll();}}}/></label>);})()}
            </div>
            <div style={{...card,padding:'20px',marginBottom:'15px'}}>
              <h4 style={{color:C.text,marginBottom:'10px',fontSize:'14px',fontWeight:'600'}}>📄 Мой договор</h4>
              {myContract?(<div><p style={{color:C.textSec,fontSize:'13px'}}>{'Договор № '+myContract.contractNumber+' · '+myContract.contractType+' · '+myContract.project}</p><button onClick={()=>{const mp=masterProfiles.find(p=>p.userId===user.id);if(mp) showPreview(buildContractContent(mp,myContract),'Договор');}} style={{...btnB,marginTop:'8px'}}><Eye size={14}/>Просмотр</button></div>):<p style={{color:C.textMuted,fontSize:'13px'}}>Договор не найден</p>}
            </div>
            <div style={{...card,padding:'20px'}}>
              <h4 style={{color:C.text,marginBottom:'10px',fontSize:'14px',fontWeight:'600'}}>📋 Мои акты</h4>
              {myActs.map(act=>{const totalAmt=act.totalAmount||0;const paidAmt=act.paidAmount||0;const toolDed=myTools.filter(t=>t.issueType==='В счёт зарплаты').reduce((s,t)=>s+t.cost,0);return(<div key={act.id} style={{padding:'12px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'8px',border:'1.5px solid '+C.border}}><div style={{display:'flex',justifyContent:'space-between'}}><div><b style={{fontSize:'13px',color:C.text}}>{'Акт №'+act.id}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{act.project+' · '+act.periodStart+' — '+act.periodEnd}</p><p style={{color:C.text,margin:'1px 0',fontSize:'12px'}}>{'Начислено: '+totalAmt.toLocaleString()+' ₽'}</p>{toolDed>0&&<p style={{color:C.danger,margin:'1px 0',fontSize:'12px'}}>{'Удержания: -'+toolDed.toLocaleString()+' ₽'}</p>}<p style={{color:C.success,margin:'1px 0',fontSize:'12px'}}>{'Оплачено: '+paidAmt.toLocaleString()+' ₽'}</p>{(totalAmt-toolDed-paidAmt)>0&&<p style={{color:C.danger,margin:'1px 0',fontSize:'12px',fontWeight:'600'}}>{'Остаток: '+(totalAmt-toolDed-paidAmt).toLocaleString()+' ₽'}</p>}</div><button onClick={()=>showPreview(buildActContent(act),'Акт')} style={btnB}><Eye size={14}/></button></div></div>);})}
              {myActs.length===0&&<p style={{color:C.textMuted,fontSize:'13px'}}>Актов нет</p>}
            </div>
          </div>)}

          {activePage==='companychat'&&(<div>
            <h3 style={{color:C.text,marginBottom:'20px',fontSize:'18px',fontWeight:'700'}}>Общий чат</h3>
            <div style={{...card,padding:'20px'}}>
              <div style={{backgroundColor:C.bg,borderRadius:'12px',padding:'15px',minHeight:'300px',maxHeight:'400px',overflowY:'auto',marginBottom:'15px',display:'flex',flexDirection:'column',gap:'10px',border:'1.5px solid '+C.border}}>
                {companyMessages.length===0&&<p style={{color:C.textMuted,textAlign:'center',margin:'auto'}}>Сообщений нет</p>}
                {companyMessages.map(msg=>{const isMe=(msg.author_name||msg.author)===user.name;return(<div key={msg.id} style={{display:'flex',justifyContent:isMe?'flex-end':'flex-start'}}><div style={{maxWidth:'80%',backgroundColor:isMe?C.accent:'white',color:isMe?'white':C.text,padding:'10px 14px',borderRadius:isMe?'16px 16px 4px 16px':'16px 16px 16px 4px',border:'1.5px solid '+(isMe?C.accent:C.border)}}>{!isMe&&<div style={{fontSize:'11px',fontWeight:'700',color:roleColor(msg.author_role||msg.role),marginBottom:'4px'}}>{msg.author_name||msg.author}</div>}{msg.text&&<p style={{margin:0,fontSize:'13px'}}>{msg.text}</p>}<div style={{fontSize:'10px',color:isMe?'rgba(255,255,255,0.7)':C.textMuted,marginTop:'4px',textAlign:'right'}}>{msg.created_at?new Date(msg.created_at).toLocaleTimeString('ru-RU'):''}</div></div></div>);})}
              </div>
              <div style={{display:'flex',gap:'8px',alignItems:'center'}}>
              <label style={{cursor:'pointer',padding:'8px',borderRadius:'8px',border:'1.5px solid '+C.border,display:'flex',alignItems:'center'}} title='Фото'>
                🖼️<input type='file' accept='image/*' style={{display:'none'}} onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0]);sendCompanyChatMessage('[Фото] '+e.target.files[0].name,url);}}}/>
              </label>
              <label style={{cursor:'pointer',padding:'8px',borderRadius:'8px',border:'1.5px solid '+C.border,display:'flex',alignItems:'center'}} title='Видео'>
                🎥<input type='file' accept='video/*' style={{display:'none'}} onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0]);sendCompanyChatMessage('[Видео] '+e.target.files[0].name,url);}}}/>
              </label>
              <label style={{cursor:'pointer',padding:'8px',borderRadius:'8px',border:'1.5px solid '+C.border,display:'flex',alignItems:'center'}} title='Документ'>
                📄<input type='file' accept='.pdf,.doc,.docx,.xls,.xlsx' style={{display:'none'}} onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0]);sendCompanyChatMessage('[Документ] '+e.target.files[0].name,url);}}}/>
              </label>
              <input placeholder="Написать..." value={companyChatMessage} onChange={e=>setCompanyChatMessage(e.target.value)} onKeyDown={e=>e.key==='Enter'&&sendCompanyChatMessage(companyChatMessage,'')} style={{...inp,marginBottom:0,flex:1}}/>
              <button onClick={()=>sendCompanyChatMessage(companyChatMessage,'')} style={btnO}>➤</button>
            </div>
            </div>
          </div>)}
        </div>

        <div style={{position:'fixed',bottom:0,left:0,right:0,backgroundColor:'white',borderTop:'1.5px solid '+C.border,display:'flex',justifyContent:'space-around',padding:'10px 0 14px',zIndex:100,boxShadow:'0 -4px 20px rgba(0,0,0,0.06)'}}>
          {[{id:'works',icon:<Briefcase size={22}/>,label:'Работы'},{id:'history',icon:<BarChart3 size={22}/>,label:'История'},{id:'materials',icon:<Package size={22}/>,label:'Инструменты',badge:myIssues.filter(i=>!i.confirmed).length},{id:'documents',icon:<FileText size={22}/>,label:'Документы'},{id:'companychat',icon:<MessageSquare size={22}/>,label:'Чат'}].map(item=>(<div key={item.id} onClick={()=>setActivePage(item.id)} style={{display:'flex',flexDirection:'column',alignItems:'center',cursor:'pointer',padding:'5px 10px',borderRadius:'10px',backgroundColor:activePage===item.id?C.accentLight:'transparent',position:'relative'}}><span style={{color:activePage===item.id?C.accent:C.textMuted}}>{item.icon}</span><span style={{fontSize:'10px',color:activePage===item.id?C.accent:C.textMuted,fontWeight:activePage===item.id?'600':'400',marginTop:'2px'}}>{item.label}</span>{item.badge>0&&<span style={{position:'absolute',top:0,right:3,backgroundColor:C.danger,color:'white',borderRadius:'50%',width:'16px',height:'16px',display:'flex',alignItems:'center',justifyContent:'center',fontSize:'10px'}}>{item.badge}</span>}</div>))}
          <div onClick={()=>setUser(null)} style={{display:'flex',flexDirection:'column',alignItems:'center',cursor:'pointer',padding:'5px 10px'}}><LogOut size={22} color={C.textMuted}/><span style={{fontSize:'10px',color:C.textMuted,marginTop:'2px'}}>Выйти</span></div>
        </div>
      </div>
    );
  }

  if (!user) {
    if (page==='register') {
      return (
        <div style={{display:'flex',justifyContent:'center',alignItems:'center',height:'100vh',backgroundColor:C.bg}}>
          <div style={{...card,padding:'40px',width:'420px',boxShadow:'0 20px 60px rgba(0,0,0,0.08)'}}>
            <div style={{textAlign:'center',marginBottom:'30px'}}><div style={{fontSize:'48px',marginBottom:'10px'}}>🏗️</div><h2 style={{margin:0,color:C.text,fontSize:'24px',fontWeight:'800'}}>СтройКа</h2><p style={{color:C.textSec,fontSize:'13px',margin:'8px 0 0'}}>Регистрация по коду приглашения</p></div>
            <input placeholder="Ваше имя" value={regName} onChange={e=>setRegName(e.target.value)} style={inp}/>
            <input type="email" placeholder="Email" value={regEmail} onChange={e=>setRegEmail(e.target.value)} style={inp}/>
            <input type="password" placeholder="Пароль" value={regPassword} onChange={e=>setRegPassword(e.target.value)} style={inp}/>
            <input placeholder="КОД ПРИГЛАШЕНИЯ" value={regCode} onChange={e=>setRegCode(e.target.value.toUpperCase())} style={{...inp,letterSpacing:'4px',textAlign:'center',fontSize:'18px',fontWeight:'700'}}/>
            {loginError&&<p style={{color:C.danger,fontSize:'13px',marginBottom:'10px'}}>{loginError}</p>}
            <button onClick={handleRegister} style={{...btnO,width:'100%',padding:'13px',justifyContent:'center',fontSize:'15px',marginBottom:'10px'}}>Зарегистрироваться</button>
            <p style={{textAlign:'center',color:C.textSec,fontSize:'13px'}}>Уже есть аккаунт? <span onClick={()=>{setPage('login');setLoginError('');}} style={{color:C.accent,cursor:'pointer',fontWeight:'600'}}>Войти</span></p>
          </div>
        </div>
      );
    }
    return <LoginPage email={email} setEmail={setEmail} password={password} setPassword={setPassword} handleLogin={handleLogin} loginError={loginError} setLoginError={setLoginError} setPage={setPage}/>;
  }

  const allMenuItems = [
    {id:'dashboard',icon:<LayoutDashboard size={18}/>,label:'Главная'},
    {id:'analytics',icon:<BarChart3 size={18}/>,label:'Аналитика'},
    {id:'crm',icon:<Handshake size={18}/>,label:'CRM'},
    {id:'projects',icon:<FolderKanban size={18}/>,label:'Проекты'},
    
    {id:'warehouse',icon:<Package size={18}/>,label:'Склад'},
    {id:'suppliers',icon:<Truck size={18}/>,label:'Поставщики'},
    {id:'accounting',icon:<DollarSign size={18}/>,label:'Бухгалтерия'},
    {id:'personnel',icon:<UserCheck size={18}/>,label:'Персонал'},
    
    {id:'estimates',icon:<Calculator size={18}/>,label:'Сметы'},
    {id:'weather',icon:<CloudSun size={18}/>,label:'Погода / ЖПР'},
    
    {id:'activitylog',icon:<ScrollText size={18}/>,label:'Журнал'},
    {id:'settings',icon:<Settings size={18}/>,label:'Настройки'},
  ];



  // Кабинет поставщика
  if (user && user.role === 'поставщик') {
    const mySupplier = suppliers.find(s => s.name === user.name || s.email === user.email);
    const myCatalog = supplierCatalog.filter(c => c.supplierId === mySupplier?.id);
    const myOffers = supplierOffers.filter(o => o.supplierId === mySupplier?.id);
    const myInvoices = invoices.filter(inv => inv.supplierName === user.name);
    const SUPPLIER_TABS = [{id:'requests',label:'📋 Заявки'},{id:'catalog',label:'📦 Мой каталог'},{id:'offers',label:'💰 Предложения'},{id:'documents',label:'📄 Документы'},{id:'profile',label:'⚙️ Профиль'}];
    return (
      <div style={{minHeight:'100vh',backgroundColor:C.bg,padding:'20px'}}>
        <div style={{maxWidth:'900px',margin:'0 auto'}}>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'24px'}}>
            <div style={{display:'flex',alignItems:'center',gap:'12px'}}>
              <span style={{fontSize:'28px'}}>🏭</span>
              <div><b style={{color:C.text,fontSize:'18px',display:'block'}}>Кабинет поставщика</b><p style={{color:C.textSec,margin:0,fontSize:'13px'}}>{user.name}</p></div>
            </div>
            <button onClick={()=>{setUser(null);localStorage.removeItem('user');}} style={{...btnG,fontSize:'12px'}}>Выйти</button>
          </div>
          <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'12px',marginBottom:'16px'}}>
            <div style={{...card,padding:'16px',textAlign:'center'}}>
              <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 4px'}}>Новых заявок</p>
              <b style={{color:C.danger,fontSize:'24px'}}>{supplyRequests.filter(r=>r.status==='Новая').length}</b>
            </div>
            <div style={{...card,padding:'16px',textAlign:'center'}}>
              <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 4px'}}>Моих предложений</p>
              <b style={{color:C.accent,fontSize:'24px'}}>{myOffers.length}</b>
            </div>
            <div style={{...card,padding:'16px',textAlign:'center'}}>
              <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 4px'}}>Утверждено</p>
              <b style={{color:C.success,fontSize:'24px'}}>{myOffers.filter(o=>o.status==='Утверждено').length}</b>
            </div>
          </div>

          <div style={{display:'flex',gap:0,overflowX:'auto',borderBottom:'1.5px solid '+C.border,marginBottom:'16px'}}>
            {SUPPLIER_TABS.map(t=>(<button key={t.id} onClick={()=>setSupplierTab(t.id)} style={{padding:'10px 16px',border:'none',backgroundColor:'transparent',cursor:'pointer',fontSize:'12px',fontWeight:supplierTab===t.id?'700':'400',color:supplierTab===t.id?C.accent:C.textSec,borderBottom:supplierTab===t.id?'2px solid '+C.accent:'2px solid transparent',whiteSpace:'nowrap'}}>{t.label}</button>))}
          </div>

          {supplierTab==='requests'&&(<div>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>📋 Активные заявки</b>
            {supplyRequests.filter(r=>r.status==='Новая'||r.status==='Ожидает предложений').map(req=>(
              <div key={req.id} style={{padding:'12px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'8px',border:'1.5px solid '+C.border}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
                  <div>
                    <b style={{fontSize:'13px',color:C.text}}>{req.materialName}</b>
                    <p style={{color:C.textSec,margin:'3px 0',fontSize:'12px'}}>{req.quantity+' '+req.unit+' · '+req.projectName}</p>
                    <p style={{color:C.textMuted,margin:0,fontSize:'11px'}}>Нужно к: {req.deadline||'Не указано'}</p>
                  </div>
                  <div>
                    {myOffers.find(o=>o.requestId===req.id)?
                      <span style={{padding:'4px 8px',borderRadius:'6px',fontSize:'11px',backgroundColor:C.successLight,color:C.success}}>✅ Отправлено</span>:
                      <button onClick={()=>{
                        const price=prompt('Ваша цена за единицу (руб):');
                        const days=prompt('Срок поставки (дней):');
                        if(price&&days){
                          fetch(API+'/supplier-offers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({requestId:req.id,supplierId:mySupplier?.id||0,supplierName:user.name,pricePerUnit:Number(price),totalPrice:Number(price)*Number(req.quantity),deliveryDays:Number(days),status:'Ожидает'})}).then(()=>loadAll());
                        }
                      }} style={{...btnO,padding:'5px 12px',fontSize:'11px'}}>💰 Предложить цену</button>
                    }
                  </div>
                </div>
              </div>
            ))}
            {supplyRequests.filter(r=>r.status==='Новая'||r.status==='Ожидает предложений').length===0&&
              <p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'20px'}}>Новых заявок нет</p>
            }
          </div>)}

          {supplierTab==='catalog'&&(<div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'12px'}}>
              <b style={{color:C.text,fontSize:'14px'}}>📦 Мой каталог</b>
              <div style={{display:'flex',gap:'8px'}}>
                <label style={{...btnG,padding:'6px 12px',fontSize:'12px',cursor:'pointer',display:'flex',alignItems:'center',gap:'4px'}}>
                  📥 Excel
                  <input type='file' accept='.xlsx,.xls,.csv' style={{display:'none'}} onChange={e=>{const file=e.target.files[0];if(!file)return;const reader=new FileReader();reader.onload=async ev=>{try{const XLSX=await import('xlsx');const wb=XLSX.read(ev.target.result,{type:'array'});const ws=wb.Sheets[wb.SheetNames[0]];const rows=XLSX.utils.sheet_to_json(ws,{header:1,defval:''});let count=0;for(let i=1;i<rows.length;i++){const r=rows[i];if(!r[0])continue;const item={materialName:String(r[0]),unit:String(r[1]||'шт'),price:Number(r[2]||0),minQuantity:Number(r[3]||1),deliveryDays:Number(r[4]||3),notes:String(r[5]||''),supplierId:mySupplier?.id||0,supplierName:user.name};const res=await fetch(API+'/supplier-catalog',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(item)});const saved=await res.json();setSupplierCatalog(prev=>[...prev,{...item,id:saved.id}]);count++;}alert('Импортировано '+count+' позиций!');}catch(err){alert('Ошибка: '+err.message);}};reader.readAsArrayBuffer(file);e.target.value='';}} />
                </label>
                {supplierRequisites.priceUrl&&(<button onClick={async()=>{
                  try{
                    alert('Загрузка прайса... Это может занять несколько секунд.');
                    const res=await fetch('https://corsproxy.io/?'+encodeURIComponent(supplierRequisites.priceUrl));
                    const blob=await res.arrayBuffer();
                    const XLSX=await import('xlsx');
                    const wb=XLSX.read(blob,{type:'array'});
                    const ws=wb.Sheets[wb.SheetNames[0]];
                    const rows=XLSX.utils.sheet_to_json(ws,{header:1,defval:''});
                    let count=0;
                    for(let i=1;i<rows.length;i++){
                      const r=rows[i];
                      if(!r[0]) continue;
                      const item={materialName:String(r[0]),unit:String(r[1]||'шт'),price:Number(r[2]||0),minQuantity:Number(r[3]||1),deliveryDays:Number(r[4]||3),notes:String(r[5]||''),supplierId:mySupplier?.id||0,supplierName:user.name};
                      const res2=await fetch(API+'/supplier-catalog',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(item)});
                      const saved=await res2.json();
                      setSupplierCatalog(prev=>[...prev,{...item,id:saved.id}]);
                      count++;
                    }
                    alert('Загружено '+count+' позиций!');
                  }catch(err){alert('Ошибка загрузки: '+err.message);}
                }} style={btnG}><Download size={14}/>По ссылке</button>)}
                <button onClick={()=>setShowCatalogForm(!showCatalogForm)} style={btnO}><Plus size={14}/>Добавить</button>
              </div>
            </div>
            {showCatalogForm&&(<div style={{...card,padding:'16px',marginBottom:'12px'}}>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
                <input placeholder='Наименование *' value={newCatalogItem.materialName} onChange={e=>setNewCatalogItem({...newCatalogItem,materialName:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <select value={newCatalogItem.unit} onChange={e=>setNewCatalogItem({...newCatalogItem,unit:e.target.value})} style={{...inp,marginBottom:0}}>{UNITS.map(u=><option key={u}>{u}</option>)}</select>
                <input placeholder='Цена за ед.' type='number' value={newCatalogItem.price} onChange={e=>setNewCatalogItem({...newCatalogItem,price:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Мин. партия' type='number' value={newCatalogItem.minQuantity} onChange={e=>setNewCatalogItem({...newCatalogItem,minQuantity:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Срок поставки (дней)' type='number' value={newCatalogItem.deliveryDays} onChange={e=>setNewCatalogItem({...newCatalogItem,deliveryDays:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Примечание' value={newCatalogItem.notes} onChange={e=>setNewCatalogItem({...newCatalogItem,notes:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
              </div>
              <div style={{display:'flex',gap:'8px',marginTop:'10px'}}>
                <button onClick={async()=>{
                  if(!newCatalogItem.materialName) return;
                  const res=await fetch(API+'/supplier-catalog',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newCatalogItem,supplierId:mySupplier?.id||0,supplierName:user.name})});
                  const saved=await res.json();
                  setSupplierCatalog(prev=>[...prev,{...newCatalogItem,id:saved.id,supplierId:mySupplier?.id||0}]);
                  setNewCatalogItem({materialName:'',unit:'шт',price:'',minQuantity:'1',deliveryDays:'3',notes:''});
                  setShowCatalogForm(false);
                }} style={btnO}><Check size={14}/>Сохранить</button>
                <button onClick={()=>setShowCatalogForm(false)} style={btnG}><X size={14}/>Отмена</button>
              </div>
            </div>)}
            <table style={tbl}><thead><tr>
              <th style={tblH}>Наименование</th>
              <th style={tblH}>Ед.</th>
              <th style={tblH}>Цена</th>
              <th style={tblH}>Мин. партия</th>
              <th style={tblH}>Поставка</th>
              <th style={tblH}>Наличие</th>
              <th style={tblH}></th>
            </tr></thead><tbody>
              {myCatalog.map(item=>(<tr key={item.id}>
                <td style={tblC}>{item.materialName}</td>
                <td style={tblC}>{item.unit}</td>
                <td style={tblC}>{Number(item.price).toLocaleString()+' ₽'}</td>
                <td style={tblC}>{item.minQuantity}</td>
                <td style={tblC}>{item.deliveryDays+' дн.'}</td>
                <td style={tblC}><span style={{color:item.inStock?C.success:C.danger,fontSize:'12px'}}>{item.inStock?'✅ Есть':'❌ Нет'}</span></td>
                <td style={tblC}><button onClick={async()=>{await fetch(API+'/supplier-catalog/'+item.id,{method:'DELETE'});setSupplierCatalog(prev=>prev.filter(c=>c.id!==item.id));}} style={{...btnR,padding:'3px 7px'}}><Trash2 size={11}/></button></td>
              </tr>))}
            </tbody></table>
            {myCatalog.length===0&&<p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'20px'}}>Каталог пуст — добавьте материалы</p>}
          </div>)}

          {supplierTab==='offers'&&(<div>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>Мои предложения</b>
            {myOffers.map(o=>(<div key={o.id} style={{...card,padding:'12px',marginBottom:'8px'}}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',marginBottom:'8px'}}>
                <div><b style={{fontSize:'13px',color:C.text}}>{supplyRequests.find(r=>r.id===o.requestId)?.materialName||'Материал'}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{Number(o.pricePerUnit).toLocaleString()+' руб/ед . '+Number(o.totalPrice).toLocaleString()+' руб . '+o.deliveryDays+' дней'}</p></div>
                <span style={{padding:'3px 8px',borderRadius:'6px',fontSize:'11px',backgroundColor:o.status==='Утверждено'?C.successLight:C.warningLight,color:o.status==='Утверждено'?C.success:C.warning}}>{o.status==='Утверждено'?'Утверждено':'Ожидает'}</span>
              </div>
              {o.status==='Утверждено'&&(<div><p style={{fontSize:'11px',color:C.textSec,marginBottom:'6px'}}>Статус доставки:</p><div style={{display:'flex',gap:'6px',flexWrap:'wrap'}}>{['Готовится к отгрузке','В пути','Доставлено'].map(s=>(<button key={s} onClick={async()=>{await fetch(API+'/supplier-offers/'+o.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({deliveryStatus:s})});await loadAll();}} style={{padding:'4px 10px',border:'1.5px solid '+(o.deliveryStatus===s?C.accent:C.border),borderRadius:'6px',fontSize:'11px',backgroundColor:o.deliveryStatus===s?C.accentLight:'transparent',color:o.deliveryStatus===s?C.accent:C.textSec,cursor:'pointer'}}>{s}</button>))}</div></div>)}
            </div>))}
            {myOffers.length===0&&<p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'20px'}}>Предложений нет</p>}
          </div>)}

          {supplierTab==='documents'&&(<div>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>📄 Документы</b>
            <b style={{color:C.textSec,fontSize:'12px',display:'block',marginBottom:'8px'}}>Накладные</b>
            {myInvoices.map(inv=>(
              <div key={inv.id} style={{padding:'10px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                <div>
                  <b style={{fontSize:'12px',color:C.text}}>Накладная № {inv.number}</b>
                  <p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{inv.date+' · '+Number(inv.totalWithVat||0).toLocaleString()+' ₽ · '+inv.location}</p>
                </div>
                <span style={{padding:'3px 8px',borderRadius:'6px',fontSize:'11px',backgroundColor:C.successLight,color:C.success}}>✅ Принята</span>
              </div>
            ))}
            {myInvoices.length===0&&<p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'20px'}}>Накладных нет</p>}
          </div>)}

          {supplierTab==='profile'&&(<div>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>⚙️ Реквизиты компании</b>
            <div style={{...card,padding:'16px'}}>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                <input placeholder='Название компании' value={supplierRequisites.companyName} onChange={e=>setSupplierRequisites({...supplierRequisites,companyName:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <input placeholder='ИНН' value={supplierRequisites.inn} onChange={e=>setSupplierRequisites({...supplierRequisites,inn:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='КПП' value={supplierRequisites.kpp} onChange={e=>setSupplierRequisites({...supplierRequisites,kpp:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Юридический адрес' value={supplierRequisites.address} onChange={e=>setSupplierRequisites({...supplierRequisites,address:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <input placeholder='Банк' value={supplierRequisites.bank} onChange={e=>setSupplierRequisites({...supplierRequisites,bank:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='БИК' value={supplierRequisites.bik} onChange={e=>setSupplierRequisites({...supplierRequisites,bik:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Расчётный счёт' value={supplierRequisites.account} onChange={e=>setSupplierRequisites({...supplierRequisites,account:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <input placeholder='Телефон' value={supplierRequisites.phone} onChange={e=>setSupplierRequisites({...supplierRequisites,phone:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Email' value={supplierRequisites.email} onChange={e=>setSupplierRequisites({...supplierRequisites,email:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Ссылка на прайс-лист (Google Sheet / Excel URL)' value={supplierRequisites.priceUrl||''} onChange={e=>setSupplierRequisites({...supplierRequisites,priceUrl:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
              </div>
              <button onClick={()=>{fetch(API+'/suppliers/'+(mySupplier?.id||0)+'/requisites',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(supplierRequisites)}).then(()=>{localStorage.setItem('supplierReq_'+user.id,JSON.stringify(supplierRequisites));alert('Реквизиты сохранены!');loadAll();})}} style={{...btnO,marginTop:'12px'}}><Check size={14}/>Сохранить</button>
            </div>
          </div>)}
        </div>
      </div>
    );
  }



  // Кабинет технадзора
  if (user && user.role === 'технадзор') {
    const myProject = projects.find(p => p.id === Number(user.project_id||user.projectId) || p.name === (user.project_name||user.projectName));
    return (
      <div style={{minHeight:'100vh',backgroundColor:C.bg,padding:'20px'}}>
        <div style={{maxWidth:'800px',margin:'0 auto'}}>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'24px'}}>
            <div style={{display:'flex',alignItems:'center',gap:'12px'}}>
              <span style={{fontSize:'28px'}}>🔎</span>
              <div><b style={{color:C.text,fontSize:'18px',display:'block'}}>Технический надзор</b><p style={{color:C.textSec,margin:0,fontSize:'13px'}}>{user.name}</p></div>
            </div>
            <button onClick={()=>{setUser(null);localStorage.removeItem('user');}} style={{...btnG,fontSize:'12px'}}>Выйти</button>
          </div>
          {!myProject?(<div style={{...card,padding:'40px',textAlign:'center'}}><p style={{color:C.textMuted}}>Объект не найден. Обратитесь к подрядчику.</p></div>):(
            <div>
              <div style={{...card,padding:'16px',marginBottom:'16px',backgroundColor:C.accentLight,border:'1.5px solid '+C.accentBorder}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px',flexWrap:'wrap'}}>
                  <div>
                    <b style={{color:C.text,fontSize:'16px'}}>{myProject.name}</b>
                    <p style={{color:C.textSec,margin:'4px 0 0',fontSize:'13px'}}>Статус: {myProject.status} · Прогресс: {projectRealProgress(myProject)}% · Выполнено: {Math.round(projectPlanDone(myProject).done).toLocaleString('ru-RU')} ₽</p>
                  </div>
                  <button onClick={()=>{const today=new Date();const monthAgo=new Date(today.getTime()-30*24*3600*1000);showPreview(buildSupervisorMonthlyReport(myProject.name,monthAgo.toISOString().split('T')[0],today.toISOString().split('T')[0]),'Месячный отчёт технадзора');}} style={btnB}><Eye size={14}/>📊 Месячный отчёт</button>
                </div>
              </div>
              {(()=>{const notifs=computeNotifications();if(notifs.length===0) return null;return(<div style={{marginBottom:'16px'}}>{notifs.slice(0,5).map((n,i)=>(<div key={i} style={{padding:'10px 12px',backgroundColor:'rgba(251,191,36,0.12)',border:'1.5px solid '+n.color,borderRadius:'10px',marginBottom:'6px',display:'flex',alignItems:'center',gap:'10px'}}><span style={{fontSize:'18px'}}>{n.icon}</span><div><b style={{fontSize:'12px',color:C.text,display:'block'}}>{n.title}</b><span style={{fontSize:'11px',color:C.textSec}}>{n.text}</span></div></div>))}</div>);})()}
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'12px',marginBottom:'16px'}}>
                <div style={{...card,padding:'16px'}}>
                  <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'10px'}}>📋 Чек-листы</b>
                  {checklists.filter(c=>c.projectName===myProject.name).map(cl=>(
                    <div key={cl.id} style={{padding:'8px 0',borderBottom:'1px solid '+C.border}}>
                      <b style={{fontSize:'12px',color:C.text}}>{cl.name}</b>
                      <p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{cl.status}</p>
                    </div>
                  ))}
                  {checklists.filter(c=>c.projectName===myProject.name).length===0&&<p style={{color:C.textMuted,fontSize:'12px'}}>Нет чек-листов</p>}
                </div>
                <div style={{...card,padding:'16px'}}>
                  <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'10px'}}>⚠️ Предписания</b>
                  {prescriptionsList.filter(pr=>pr.projectName===myProject.name).map(pr=>(
                    <div key={pr.id} style={{padding:'8px 0',borderBottom:'1px solid '+C.border}}>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'6px'}}>
                        <div style={{flex:1}}>
                          <b style={{fontSize:'12px',color:C.danger}}>{pr.violation||pr.description||'(описание не указано)'}</b>
                          <p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{(pr.priority?pr.priority+' · ':'')+(pr.status||'Открыто')+(pr.deadline?' · до '+pr.deadline:'')}</p>
                        </div>
                        <button onClick={()=>showPreview(buildPrescriptionContent(pr),'Предписание')} style={{...btnB,padding:'4px 8px',fontSize:'11px'}} title="Распечатать предписание">🖨️</button>
                      </div>
                      {pr.photoUrl&&<img src={pr.photoUrl.startsWith('http')?pr.photoUrl:API+pr.photoUrl} alt='' onClick={()=>setShowPhotoModal(pr.photoUrl.startsWith('http')?pr.photoUrl:API+pr.photoUrl)} style={{width:'48px',height:'48px',borderRadius:'6px',objectFit:'cover',cursor:'pointer',marginTop:'4px'}}/>}
                    </div>
                  ))}
                  {prescriptionsList.filter(pr=>pr.projectName===myProject.name).length===0&&<p style={{color:C.textMuted,fontSize:'12px'}}>Предписаний нет</p>}
                </div>
              </div>
              <div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>⚠️ Выдать предписание</b>
                <textarea id='pres_desc_tn' placeholder='Описание нарушения *' style={{...inp,height:'80px'}}/>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                  <select id='pres_priority_tn' style={{...inp,marginBottom:0}}>
                    <option value='Критичное'>🔴 Критичное</option>
                    <option value='Важное'>🟡 Важное</option>
                    <option value='Замечание'>🟢 Замечание</option>
                  </select>
                  <input type='date' id='pres_date_tn' style={{...inp,marginBottom:0}} defaultValue={new Date().toISOString().split('T')[0]}/>
                </div>
                <div style={{display:'flex',gap:'8px',alignItems:'center',marginTop:'10px'}}>
                  <label style={{...btnB,padding:'8px 12px',fontSize:'12px',cursor:'pointer'}}><Upload size={12}/>{prescriptionPhoto?'📷 Фото добавлено':'📷 Прикрепить фото'}<input type='file' accept='image/*' style={{display:'none'}} onChange={async e=>{const f=e.target.files[0];if(f){const url=await uploadPhoto(f);if(url) setPrescriptionPhoto(url);}}}/></label>
                  {prescriptionPhoto&&<button onClick={()=>setPrescriptionPhoto('')} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}><X size={11}/></button>}
                </div>
                <button onClick={async()=>{
                  const desc=document.getElementById('pres_desc_tn').value;
                  if(!desc){alert('Введите описание');return;}
                  const priority=document.getElementById('pres_priority_tn').value;
                  const deadline=document.getElementById('pres_date_tn').value;
                  await fetch(API+'/prescriptions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({projectName:myProject.name,violation:desc,priority,deadline,issuedBy:user.name,issuedByRole:'Технадзор',status:'Открыто',photoUrl:prescriptionPhoto})});
                  await loadAll();
                  document.getElementById('pres_desc_tn').value='';
                  setPrescriptionPhoto('');
                  alert('Предписание выдано!');
                }} style={{...btnO,marginTop:'12px'}}><Plus size={14}/>Выдать предписание</button>
              </div>
              <div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>🔒 Акты освидетельствования скрытых работ (АОСР)</b>
                {(()=>{
                  const here=hiddenActs.filter(a=>a.projectName===myProject.name);
                  if(here.length===0) return <p style={{color:C.textMuted,fontSize:'12px'}}>АОСР пока нет — появятся когда мастер закроет позиции 🔒 в смете объекта.</p>;
                  return(<div>
                    {here.slice(0,10).map(a=>(<div key={a.id} onClick={()=>setEditingAct(a)} style={{padding:'10px 12px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border,cursor:'pointer',display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px'}}>
                      <div style={{flex:1,overflow:'hidden'}}>
                        <b style={{fontSize:'12px',color:C.text}}>{a.actNumber+' · '+a.workName}</b>
                        <p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{(a.quantity||0)+' '+(a.unit||'')+' · '+(a.workDate||'')}</p>
                      </div>
                      <div style={{display:'flex',alignItems:'center',gap:'6px',flexShrink:0}}>
                        {a.signedSupervisor?<span style={{padding:'2px 8px',borderRadius:'10px',fontSize:'10px',fontWeight:'600',backgroundColor:C.successLight,color:C.success}}>✅ Я подписал</span>:<span style={{padding:'2px 8px',borderRadius:'10px',fontSize:'10px',fontWeight:'600',backgroundColor:C.warningLight,color:C.warning}}>⏳ Ждёт моей подписи</span>}
                        <ChevronRight size={14} color={C.textMuted}/>
                      </div>
                    </div>))}
                    <p style={{fontSize:'11px',color:C.textMuted,marginTop:'8px'}}>Клик по строке → откроется карточка акта. В поле «Технадзор» впиши свои ФИО и дату, сохрани — подпись зафиксируется.</p>
                  </div>);
                })()}
              </div>
              <div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'12px'}}>
                  <b style={{color:C.text,fontSize:'14px'}}>📝 Мои акты осмотра / обследования</b>
                  <button onClick={()=>setShowForm(showForm==='svact'?false:'svact')} style={{...btnO,padding:'5px 10px',fontSize:'11px'}}><Plus size={11}/>Новый акт</button>
                </div>
                {showForm==='svact'&&(<div style={{padding:'12px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'10px',border:'1.5px solid '+C.border}}>
                  <select value={newSupervisorAct.actType} onChange={e=>setNewSupervisorAct({...newSupervisorAct,actType:e.target.value})} style={{...inp,marginBottom:'8px'}}>
                    <option>Осмотр</option><option>Обследование</option><option>Акт промежуточной приёмки</option><option>Акт по результатам контроля</option>
                  </select>
                  <textarea placeholder='Предмет осмотра (что проверяли)' value={newSupervisorAct.description} onChange={e=>setNewSupervisorAct({...newSupervisorAct,description:e.target.value})} style={{...inp,minHeight:'60px',marginBottom:'8px'}}/>
                  <textarea placeholder='Результат / что обнаружили' value={newSupervisorAct.findings} onChange={e=>setNewSupervisorAct({...newSupervisorAct,findings:e.target.value})} style={{...inp,minHeight:'60px',marginBottom:'8px'}}/>
                  <textarea placeholder='Рекомендации / требования' value={newSupervisorAct.recommendations} onChange={e=>setNewSupervisorAct({...newSupervisorAct,recommendations:e.target.value})} style={{...inp,minHeight:'50px',marginBottom:'8px'}}/>
                  <div style={{display:'flex',gap:'8px',marginBottom:'8px',alignItems:'center'}}>
                    <input type='date' value={newSupervisorAct.date} onChange={e=>setNewSupervisorAct({...newSupervisorAct,date:e.target.value})} style={{...inp,marginBottom:0,flex:1}}/>
                    <label style={{...btnB,padding:'8px 12px',fontSize:'12px',cursor:'pointer'}}><Upload size={12}/>{supervisorActPhoto?'📷 Фото':'📷 Прикрепить'}<input type='file' accept='image/*' style={{display:'none'}} onChange={async e=>{const f=e.target.files[0];if(f){const url=await uploadPhoto(f);if(url) setSupervisorActPhoto(url);}}}/></label>
                    {supervisorActPhoto&&<button onClick={()=>setSupervisorActPhoto('')} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}><X size={11}/></button>}
                  </div>
                  <div style={{display:'flex',gap:'8px'}}>
                    <button onClick={async()=>{
                      if(!newSupervisorAct.description){alert('Опишите предмет осмотра');return;}
                      await fetch(API+'/supervisor-acts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({projectName:myProject.name,actType:newSupervisorAct.actType,description:newSupervisorAct.description,findings:newSupervisorAct.findings,recommendations:newSupervisorAct.recommendations,issuedBy:user.name,issuedByRole:'Технадзор',photoUrl:supervisorActPhoto,date:newSupervisorAct.date||new Date().toISOString().split('T')[0]})});
                      await loadAll();
                      setNewSupervisorAct({actType:'Осмотр',description:'',findings:'',recommendations:'',date:''});
                      setSupervisorActPhoto('');
                      setShowForm(false);
                      alert('Акт сохранён');
                    }} style={btnO}><Check size={14}/>Сохранить</button>
                    <button onClick={()=>{setShowForm(false);setNewSupervisorAct({actType:'Осмотр',description:'',findings:'',recommendations:'',date:''});setSupervisorActPhoto('');}} style={btnG}>Отмена</button>
                  </div>
                </div>)}
                {(()=>{
                  const here=supervisorActs.filter(a=>a.projectName===myProject.name);
                  if(here.length===0) return <p style={{color:C.textMuted,fontSize:'12px'}}>Актов осмотра пока нет. Нажми «Новый акт» чтобы зафиксировать обследование.</p>;
                  return here.slice(0,10).map(a=>(<div key={a.id} style={{padding:'10px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border}}>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'8px'}}>
                      <div style={{flex:1}}>
                        <b style={{fontSize:'12px',color:C.text}}>{a.actNumber+' · '+a.actType}</b>
                        <p style={{color:C.textSec,margin:'4px 0 0',fontSize:'11px'}}>{a.description}</p>
                        {a.findings&&<p style={{color:C.text,margin:'4px 0 0',fontSize:'11px'}}><b>Обнаружено:</b> {a.findings}</p>}
                        {a.recommendations&&<p style={{color:C.text,margin:'4px 0 0',fontSize:'11px'}}><b>Рекомендации:</b> {a.recommendations}</p>}
                        <p style={{color:C.textMuted,margin:'4px 0 0',fontSize:'10px'}}>{a.date}</p>
                      </div>
                      {a.photoUrl&&<img src={a.photoUrl.startsWith('http')?a.photoUrl:API+a.photoUrl} alt='' onClick={()=>setShowPhotoModal(a.photoUrl.startsWith('http')?a.photoUrl:API+a.photoUrl)} style={{width:'56px',height:'56px',borderRadius:'6px',objectFit:'cover',cursor:'pointer',flexShrink:0}}/>}
                    </div>
                  </div>));
                })()}
              </div>
              <div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>📦 Входной контроль материалов</b>
                {(()=>{
                  const here=materialInspections.filter(mi=>mi.projectName===myProject.name);
                  if(here.length===0) return <p style={{color:C.textMuted,fontSize:'12px'}}>Записей нет. Появятся когда подрядчик примет накладную на материал.</p>;
                  const pending=here.filter(r=>!r.inspected).length;
                  return(<div>
                    {pending>0&&<p style={{color:C.warning,fontSize:'12px',marginBottom:'8px'}}>⏳ {pending} материала ждут отметки о входном контроле</p>}
                    {here.slice(0,8).map(mi=>(<div key={mi.id} style={{padding:'8px 10px',backgroundColor:C.bg,borderRadius:'6px',marginBottom:'4px',border:'1px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                      <div style={{flex:1,overflow:'hidden'}}>
                        <b style={{fontSize:'11px',color:C.text}}>{mi.materialName}</b>
                        <p style={{color:C.textSec,margin:'2px 0',fontSize:'10px'}}>{(mi.quantity||0)+' '+(mi.unit||'')+' · '+(mi.supplier||'—')+' · '+(mi.receivedAt||'')}</p>
                      </div>
                      <span style={{padding:'2px 8px',borderRadius:'10px',fontSize:'10px',fontWeight:'600',backgroundColor:mi.inspected?C.successLight:C.warningLight,color:mi.inspected?C.success:C.warning}}>{mi.inspected?'✅':'⏳'}</span>
                    </div>))}
                  </div>);
                })()}
              </div>
              <div style={{...card,padding:'20px'}}>
                <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>📖 Журнал работ</b>
                {workJournal.filter(j=>j.project===myProject.name).slice(0,10).map(j=>(
                  <div key={j.id} style={{padding:'8px 0',borderBottom:'1px solid '+C.border}}>
                    <b style={{fontSize:'12px',color:C.text}}>{j.description}</b>
                    <p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{j.masterName+' · '+j.date+' · '+j.status}</p>
                  </div>
                ))}
                {workJournal.filter(j=>j.project===myProject.name).length===0&&<p style={{color:C.textMuted,fontSize:'12px'}}>Записей нет</p>}
              </div>
            </div>
          )}
        </div>
        {editingAct&&(()=>{
          const a=editingAct;
          const upd=(k,v)=>setEditingAct({...editingAct,[k]:v});
          const allSigned=!!(a.signedCustomer&&a.signedSupervisor&&a.signedContractor&&a.signedSubcontractor);
          const saveSign=async()=>{
            const body={
              status:allSigned?'Подписан':(a.status||'Черновик'),
              signedCustomer:a.signedCustomer||'',signedSupervisor:a.signedSupervisor||'',
              signedContractor:a.signedContractor||'',signedSubcontractor:a.signedSubcontractor||'',
              signedCustomerAt:a.signedCustomerAt||'',signedSupervisorAt:a.signedSupervisorAt||'',
              signedContractorAt:a.signedContractorAt||'',signedSubcontractorAt:a.signedSubcontractorAt||'',
              conclusion:a.conclusion||'',comments:a.comments||'',
              materialsUsed:a.materialsUsed||'',projectDocs:a.projectDocs||'',
              photos:a.photos||'',certificates:a.certificates||'',city:a.city||'',
            };
            const res=await fetch(API+'/hidden-works-acts/'+a.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
            const data=await res.json().catch(()=>({}));
            setHiddenActs(prev=>prev.map(x=>x.id===a.id?{...x,...body,status:data.status||body.status}:x));
            setEditingAct(null);
          };
          return(<div onClick={()=>setEditingAct(null)} style={{position:'fixed',inset:0,backgroundColor:'rgba(0,0,0,0.55)',zIndex:1600,display:'flex',alignItems:'center',justifyContent:'center',padding:'20px'}}>
            <div onClick={e=>e.stopPropagation()} style={{...card,padding:0,width:'min(640px,100%)',maxHeight:'92vh',display:'flex',flexDirection:'column',overflow:'hidden'}}>
              <div style={{padding:'16px 20px',borderBottom:'1.5px solid '+C.border,backgroundColor:C.bg,display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                <div>
                  <b style={{color:C.text,fontSize:'15px',display:'block'}}>🔒 {a.actNumber}</b>
                  <span style={{fontSize:'11px',color:C.textSec}}>Акт освидетельствования скрытых работ</span>
                </div>
                <button onClick={()=>setEditingAct(null)} style={{...btnG,padding:'5px 10px'}}>✕</button>
              </div>
              <div style={{flex:1,overflowY:'auto',padding:'18px 20px'}}>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px',marginBottom:'14px',padding:'12px',backgroundColor:C.bg,borderRadius:'10px',border:'1.5px solid '+C.border}}>
                  <div><p style={{fontSize:'11px',color:C.textSec,margin:'0 0 4px',fontWeight:'600'}}>Работа</p><b style={{fontSize:'13px',color:C.text}}>{a.workName}</b></div>
                  <div><p style={{fontSize:'11px',color:C.textSec,margin:'0 0 4px',fontWeight:'600'}}>Объём</p><b style={{fontSize:'13px',color:C.text}}>{Number(a.quantity||0).toLocaleString('ru-RU')+' '+(a.unit||'')}</b></div>
                  <div><p style={{fontSize:'11px',color:C.textSec,margin:'0 0 4px',fontWeight:'600'}}>Бригада</p><b style={{fontSize:'13px',color:C.text}}>{a.brigade||'—'}</b></div>
                  <div><p style={{fontSize:'11px',color:C.textSec,margin:'0 0 4px',fontWeight:'600'}}>Дата</p><b style={{fontSize:'13px',color:C.text}}>{a.workDate||'—'}</b></div>
                </div>
                <p style={{fontSize:'11px',color:C.textSec,fontWeight:'600',marginBottom:'4px'}}>Материалы и применённые конструкции</p>
                <div style={{padding:'10px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border,fontSize:'12px',color:C.textSec,whiteSpace:'pre-wrap',marginBottom:'14px',minHeight:'40px'}}>{a.materialsUsed||'(не указаны подрядчиком)'}</div>
                <p style={{fontSize:'11px',color:C.textSec,fontWeight:'600',marginBottom:'4px'}}>Проектная документация</p>
                <div style={{padding:'10px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border,fontSize:'12px',color:C.textSec,whiteSpace:'pre-wrap',marginBottom:'14px',minHeight:'40px'}}>{a.projectDocs||'(не указаны)'}</div>
                <p style={{fontSize:'11px',color:C.textSec,fontWeight:'600',marginBottom:'4px'}}>Заключение комиссии</p>
                <div style={{padding:'10px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border,fontSize:'12px',color:C.textSec,whiteSpace:'pre-wrap',marginBottom:'14px',minHeight:'40px'}}>{a.conclusion||'(подрядчик ещё не заполнил)'}</div>
                <div style={{padding:'14px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder,borderRadius:'10px'}}>
                  <b style={{display:'block',marginBottom:'10px',color:C.warning,fontSize:'13px'}}>✍️ Моя подпись (Технадзор)</b>
                  <input value={a.signedSupervisor||''} onChange={e=>upd('signedSupervisor',e.target.value)} placeholder='ФИО, должность, организация' style={{...inp,marginBottom:'8px'}}/>
                  <input type='date' value={a.signedSupervisorAt||''} onChange={e=>upd('signedSupervisorAt',e.target.value)} style={inp}/>
                  <p style={{fontSize:'11px',color:C.textSec,margin:'8px 0 0',lineHeight:1.4}}>Впиши свои ФИО и дату → нажми «Подписать». Подпись подрядчика, заказчика и субподрядчика поставит каждый со своей стороны.</p>
                </div>
                <div style={{marginTop:'14px',padding:'10px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border,fontSize:'11px'}}>
                  <b style={{color:C.text,fontSize:'12px'}}>Подписи 4 сторон:</b>
                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginTop:'8px'}}>
                    <div><span style={{color:a.signedCustomer?C.success:C.textMuted}}>{a.signedCustomer?'✅':'⏳'} Заказчик:</span> {a.signedCustomer||'—'}</div>
                    <div><span style={{color:a.signedSupervisor?C.success:C.textMuted}}>{a.signedSupervisor?'✅':'⏳'} Технадзор:</span> {a.signedSupervisor||'—'}</div>
                    <div><span style={{color:a.signedContractor?C.success:C.textMuted}}>{a.signedContractor?'✅':'⏳'} Генподрядчик:</span> {a.signedContractor||'—'}</div>
                    <div><span style={{color:a.signedSubcontractor?C.success:C.textMuted}}>{a.signedSubcontractor?'✅':'⏳'} Субподрядчик:</span> {a.signedSubcontractor||'—'}</div>
                  </div>
                </div>
              </div>
              <div style={{padding:'14px 20px',borderTop:'1.5px solid '+C.border,backgroundColor:C.bg,display:'flex',gap:'8px',justifyContent:'flex-end'}}>
                <button onClick={()=>setEditingAct(null)} style={btnG}>Отмена</button>
                <button onClick={saveSign} style={btnO}>✍️ Подписать</button>
              </div>
            </div>
          </div>);
        })()}
        {showPhotoModal&&(<div onClick={()=>setShowPhotoModal(null)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.9)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:2000,cursor:'pointer'}}><img src={showPhotoModal} alt="" style={{maxWidth:'90%',maxHeight:'90%',borderRadius:'12px'}}/></div>)}
      </div>
    );
  }

  // Кабинет заказчика
  if (user && user.role === 'заказчик') {
    const myProject = projects.find(p => p.id === Number(user.project_id||user.projectId) || p.name === (user.project_name||user.projectName));
    return (
      <div style={{minHeight:'100vh',backgroundColor:C.bg,padding:'20px'}}>
        <div style={{maxWidth:'800px',margin:'0 auto'}}>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'24px'}}>
            <div style={{display:'flex',alignItems:'center',gap:'12px'}}>
              <span style={{fontSize:'28px'}}>🏠</span>
              <div><b style={{color:C.text,fontSize:'18px',display:'block'}}>Кабинет заказчика</b><p style={{color:C.textSec,margin:0,fontSize:'13px'}}>{user.name}</p></div>
            </div>
            <button onClick={()=>{setUser(null);localStorage.removeItem('user');}} style={{...btnG,fontSize:'12px'}}>Выйти</button>
          </div>
          {!myProject?(<div style={{...card,padding:'40px',textAlign:'center'}}><p style={{color:C.textMuted}}>Объект не найден. Обратитесь к подрядчику.</p></div>):(
            <div>
              <div style={{...card,padding:'20px',marginBottom:'16px',background:'linear-gradient(135deg,'+C.accent+',#5b6cf0)'}}>
                <b style={{color:'white',fontSize:'20px',display:'block'}}>{myProject.name}</b>
                <p style={{color:'rgba(255,255,255,0.8)',margin:'4px 0 0',fontSize:'14px'}}>Статус: {myProject.status}</p>
              </div>
              {(()=>{const notifs=computeNotifications();if(notifs.length===0) return null;return(<div style={{marginBottom:'16px'}}>{notifs.slice(0,5).map((n,i)=>(<div key={i} style={{padding:'10px 12px',backgroundColor:'rgba(251,191,36,0.12)',border:'1.5px solid '+n.color,borderRadius:'10px',marginBottom:'6px',display:'flex',alignItems:'center',gap:'10px'}}><span style={{fontSize:'18px'}}>{n.icon}</span><div><b style={{fontSize:'12px',color:C.text,display:'block'}}>{n.title}</b><span style={{fontSize:'11px',color:C.textSec}}>{n.text}</span></div></div>))}</div>);})()}
              <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'12px',marginBottom:'16px'}}>
                <div style={{...card,padding:'16px',textAlign:'center'}}>
                  <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 4px'}}>Прогресс</p>
                  <b style={{color:C.accent,fontSize:'24px'}}>{projectRealProgress(myProject)}%</b>
                  <div style={{backgroundColor:C.bgGray,borderRadius:'6px',height:'6px',marginTop:'8px'}}>
                    <div style={{backgroundColor:C.accent,width:projectRealProgress(myProject)+'%',height:'100%',borderRadius:'6px'}}/>
                  </div>
                </div>
                <div style={{...card,padding:'16px',textAlign:'center'}}>
                  <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 4px'}}>Бюджет</p>
                  <b style={{color:C.text,fontSize:'16px'}}>{Number(myProject.budget||0).toLocaleString()+' ₽'}</b>
                </div>
                <div style={{...card,padding:'16px',textAlign:'center'}}>
                  <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 4px'}}>Срок сдачи</p>
                  <b style={{color:C.text,fontSize:'14px'}}>{myProject.deadline||'Не указан'}</b>
                </div>
              </div>
              <div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>📋 Этапы</b>
                {projectStages.filter(s=>s.projectName===myProject.name).map(stage=>(
                  <div key={stage.id} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'8px 0',borderBottom:'1px solid '+C.border}}>
                    <div><b style={{fontSize:'13px',color:C.text}}>{stage.name}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{stage.startDate+' — '+stage.endDate}</p></div>
                    <span style={{padding:'3px 8px',borderRadius:'6px',fontSize:'11px',backgroundColor:stage.status==='Завершён'?C.successLight:stage.status==='В работе'?C.warningLight:C.bg,color:stage.status==='Завершён'?C.success:stage.status==='В работе'?C.warning:C.textSec}}>{stage.status}</span>
                  </div>
                ))}
                {projectStages.filter(s=>s.projectName===myProject.name).length===0&&<p style={{color:C.textMuted,fontSize:'12px'}}>Этапы не добавлены</p>}
              </div>
              {/* АОСР на подпись заказчика */}
              <div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>🔒 Акты освидетельствования скрытых работ (АОСР)</b>
                {(()=>{
                  const here=hiddenActs.filter(a=>a.projectName===myProject.name);
                  if(here.length===0) return <p style={{color:C.textMuted,fontSize:'12px'}}>Актов пока нет. Появятся по ходу работ.</p>;
                  const need=here.filter(a=>!a.signedCustomer);
                  return(<div>
                    {need.length>0&&<p style={{color:C.warning,fontSize:'12px',marginBottom:'8px',fontWeight:'600'}}>⏳ {need.length} акт(ов) ждут моей подписи</p>}
                    {here.slice(0,10).map(a=>(<div key={a.id} onClick={()=>setEditingAct(a)} style={{padding:'10px 12px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border,cursor:'pointer',display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px'}}>
                      <div style={{flex:1,overflow:'hidden'}}>
                        <b style={{fontSize:'12px',color:C.text}}>{a.actNumber+' · '+a.workName}</b>
                        <p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{Number(a.quantity||0).toLocaleString('ru-RU')+' '+(a.unit||'')+' · '+(a.workDate||'')}</p>
                      </div>
                      <span style={{padding:'2px 8px',borderRadius:'10px',fontSize:'10px',fontWeight:'600',backgroundColor:a.signedCustomer?C.successLight:C.warningLight,color:a.signedCustomer?C.success:C.warning}}>{a.signedCustomer?'✅ Я подписал':'⏳ Ждёт моей подписи'}</span>
                    </div>))}
                  </div>);
                })()}
              </div>
              {/* Непредвиденные на согласование */}
              <div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>🆕 Дополнительные работы (вне сметы)</b>
                {(()=>{
                  const pending=(unexpectedWorksList||[]).filter(u=>u.projectName===myProject.name&&u.status==='Ожидает согласования');
                  const approved=(unexpectedWorksList||[]).filter(u=>u.projectName===myProject.name&&u.status==='Утверждено');
                  if(pending.length===0&&approved.length===0) return <p style={{color:C.textMuted,fontSize:'12px'}}>Дополнительных работ нет — всё по смете.</p>;
                  return(<div>
                    {pending.length>0&&<div style={{marginBottom:'10px'}}>
                      <b style={{color:C.warning,fontSize:'12px'}}>⏳ Ждут моего согласования ({pending.length}):</b>
                      {pending.map(u=>(<div key={u.id} style={{padding:'12px',backgroundColor:'#fef3c7',borderRadius:'8px',marginTop:'6px',border:'1.5px solid #fbbf24'}}>
                        <b style={{fontSize:'13px',color:'#78350f'}}>{u.description}</b>
                        <p style={{color:'#78350f',margin:'4px 0',fontSize:'12px'}}>{(u.quantity||0)+' '+u.unit+(u.price>0?' · '+u.price.toLocaleString('ru-RU')+' ₽/'+u.unit:'')+(u.total>0?' · итого '+u.total.toLocaleString('ru-RU')+' ₽':'')}</p>
                        <p style={{color:'#92400e',margin:'0 0 8px',fontSize:'11px'}}>{'Запросил: '+u.addedBy}</p>
                        <div style={{display:'flex',gap:'6px'}}>
                          <button onClick={async()=>{if(!window.confirm('Согласовать дополнительную работу «'+u.description+'» на '+(u.total||0).toLocaleString('ru-RU')+' ₽?')) return;await fetch(API+'/unexpected-works/'+u.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Утверждено',price:u.price,total:u.total,approvedBy:user.name,approvedAt:new Date().toISOString().split('T')[0]})});await loadAll();alert('Согласовано. Подрядчик может приступать.');}} style={{...btnGr,padding:'5px 10px',fontSize:'11px'}}><Check size={11}/>Согласовать</button>
                          <button onClick={async()=>{if(!window.confirm('Отказать в выполнении «'+u.description+'»?')) return;await fetch(API+'/unexpected-works/'+u.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Отклонено',approvedBy:user.name,approvedAt:new Date().toISOString().split('T')[0]})});await loadAll();}} style={{...btnR,padding:'5px 10px',fontSize:'11px'}}><X size={11}/>Отказать</button>
                        </div>
                      </div>))}
                    </div>}
                    {approved.length>0&&<div>
                      <b style={{color:C.success,fontSize:'12px'}}>✅ Согласовано ранее ({approved.length}):</b>
                      {approved.slice(0,5).map(u=>(<div key={u.id} style={{padding:'8px 12px',backgroundColor:C.bg,borderRadius:'6px',marginTop:'4px',display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px',fontSize:'11px'}}>
                        <span style={{color:C.textSec}}>{u.description+' · '+(u.total||0).toLocaleString('ru-RU')+' ₽ · '+u.approvedAt}</span>
                        <button onClick={()=>showPreview(buildSupplementaryAgreementContent(u,myProject),'Доп.соглашение № '+u.id)} style={{...btnB,padding:'3px 8px',fontSize:'10px'}} title="Распечатать доп.соглашение"><Eye size={10}/>📜</button>
                      </div>))}
                    </div>}
                  </div>);
                })()}
              </div>
              {/* Смета */}
              <div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>📐 Смета объекта</b>
                {(()=>{
                  const est=_estimateForProject(myProject);
                  if(!est) return <p style={{color:C.textMuted,fontSize:'12px'}}>Смета подрядчиком ещё не загружена.</p>;
                  const pd=projectPlanDone(myProject);
                  return(<div>
                    <p style={{color:C.text,fontSize:'13px',margin:'0 0 8px'}}><b>{est.name}</b> · v{est.version||'1.0'}</p>
                    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'10px'}}>
                      <div style={{padding:'10px',backgroundColor:C.bg,borderRadius:'8px'}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>По смете</p><b style={{color:C.text,fontSize:'14px'}}>{Math.round(pd.plan).toLocaleString('ru-RU')+' ₽'}</b></div>
                      <div style={{padding:'10px',backgroundColor:C.successLight,borderRadius:'8px'}}><p style={{color:C.success,fontSize:'11px',margin:'0 0 4px'}}>Выполнено</p><b style={{color:C.success,fontSize:'14px'}}>{Math.round(pd.done).toLocaleString('ru-RU')+' ₽'}</b></div>
                    </div>
                    <button onClick={()=>{const sections=_sectionsOfEst(est);let html='<h2>Смета: '+est.name+'</h2><p>Объект: '+myProject.name+'</p><table><tr><th>Раздел</th><th>Работа</th><th>Ед.</th><th>Кол-во</th><th>Цена</th><th>Сумма</th></tr>';sections.forEach(s=>(s.items||[]).forEach(it=>{const price=Number(it.priceWork||0)+Number(it.priceMaterial||0);html+='<tr><td>'+(s.name||'')+'</td><td>'+(it.name||'')+'</td><td>'+(it.unit||'')+'</td><td>'+(it.quantity||0)+'</td><td>'+price.toLocaleString('ru-RU')+'</td><td>'+Math.round(Number(it.quantity||0)*price).toLocaleString('ru-RU')+'</td></tr>';}));html+='<tr><td colspan=5><b>ИТОГО:</b></td><td><b>'+Math.round(pd.plan).toLocaleString('ru-RU')+' ₽</b></td></tr></table>';showPreview(html,'Смета — '+est.name);}} style={btnB}><Eye size={14}/>📄 Посмотреть смету</button>
                  </div>);
                })()}
              </div>
              {/* КС-2 / КС-3 */}
              <div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>📄 Акты КС-2 и КС-3 на согласование</b>
                <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
                  <button onClick={()=>showKS2(myProject)} style={btnO}><Eye size={14}/>📄 КС-2 (приёмка работ)</button>
                  <button onClick={()=>showPreview(buildKS3Content(myProject),'КС-3 — '+myProject.name)} style={btnB}><Eye size={14}/>📋 КС-3 (стоимость)</button>
                </div>
                <p style={{color:C.textMuted,fontSize:'11px',marginTop:'10px',lineHeight:1.4}}>Формируются автоматически из выполненных позиций сметы. Включают раздел «Дополнительные работы» (если есть согласованные доп.соглашения).</p>
              </div>
              {/* Фото-отчёт */}
              <div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>📷 Фото-отчёт</b>
                {(()=>{
                  const photos=workJournal.filter(j=>j.project===myProject.name&&j.photoUrl).slice(0,12);
                  if(photos.length===0) return <p style={{color:C.textMuted,fontSize:'12px'}}>Подрядчик пока не загружал фото работ.</p>;
                  return(<div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(80px,1fr))',gap:'6px'}}>
                    {photos.map((j,i)=>{const url=j.photoUrl.startsWith('http')?j.photoUrl:API+j.photoUrl;return(<img key={i} src={url} alt='' onClick={()=>setShowPhotoModal(url)} title={j.description+' · '+j.date} style={{width:'100%',height:'80px',borderRadius:'6px',objectFit:'cover',cursor:'pointer',border:'1.5px solid '+C.border}}/>);})}
                  </div>);
                })()}
              </div>
              {/* Журнал работ */}
              <div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>📖 Журнал производства работ (последние 10)</b>
                {workJournal.filter(j=>j.project===myProject.name).slice(0,10).map(j=>(
                  <div key={j.id} style={{padding:'8px 0',borderBottom:'1px solid '+C.border}}>
                    <b style={{fontSize:'12px',color:C.text}}>{j.description}{j.unexpectedWorkId?<span title="Допработа" style={{marginLeft:'4px'}}>🆕</span>:null}{j.hiddenWork?<span title="Скрытая работа" style={{marginLeft:'4px'}}>🔒</span>:null}</b>
                    <p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{(j.masterName||'')+' · '+(j.date||'')+' · '+(j.status||'')}</p>
                  </div>
                ))}
                {workJournal.filter(j=>j.project===myProject.name).length===0&&<p style={{color:C.textMuted,fontSize:'12px'}}>Записей нет</p>}
              </div>
              {/* Замечания заказчика */}
              <div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>⚠️ Мои замечания подрядчику</b>
                <textarea id='client_remark' placeholder='Опишите замечание...' style={{...inp,height:'70px'}}/>
                <button onClick={async()=>{
                  const t=document.getElementById('client_remark').value;
                  if(!t.trim()) return;
                  await fetch(API+'/prescriptions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({projectName:myProject.name,violation:t,priority:'Замечание заказчика',issuedBy:user.name,issuedByRole:'Заказчик',status:'Открыто'})});
                  await loadAll();
                  document.getElementById('client_remark').value='';
                  alert('Замечание передано подрядчику');
                }} style={btnO}><Plus size={14}/>Отправить</button>
                <div style={{marginTop:'12px'}}>
                  {(prescriptionsList||[]).filter(pr=>pr.projectName===myProject.name&&(pr.issuedBy===user.name||pr.issuedByRole==='Заказчик')).slice(0,10).map(pr=>(
                    <div key={pr.id} style={{padding:'8px 10px',backgroundColor:C.bg,borderRadius:'6px',marginTop:'4px',border:'1px solid '+C.border}}>
                      <b style={{fontSize:'12px',color:C.text}}>{pr.violation||pr.description||'(пусто)'}</b>
                      <p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{(pr.status||'')+(pr.deadline?' · до '+pr.deadline:'')}</p>
                    </div>
                  ))}
                </div>
              </div>
              {/* История платежей */}
              <div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>💰 Платежи по объекту</b>
                {(()=>{
                  const pp=(projectPayments||[]).filter(x=>x.projectName===myProject.name);
                  const paid=pp.reduce((s,x)=>s+Number(x.amount||0),0);
                  const budget=Number(myProject.budget||0);
                  const remain=budget-paid;
                  return(<div>
                    <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'8px',marginBottom:'10px'}}>
                      <div style={{padding:'10px',backgroundColor:C.bg,borderRadius:'8px'}}><p style={{color:C.textSec,fontSize:'10px',margin:'0 0 4px'}}>Бюджет</p><b style={{color:C.text,fontSize:'13px'}}>{Math.round(budget).toLocaleString('ru-RU')+' ₽'}</b></div>
                      <div style={{padding:'10px',backgroundColor:C.successLight,borderRadius:'8px'}}><p style={{color:C.success,fontSize:'10px',margin:'0 0 4px'}}>Оплачено</p><b style={{color:C.success,fontSize:'13px'}}>{Math.round(paid).toLocaleString('ru-RU')+' ₽'}</b></div>
                      <div style={{padding:'10px',backgroundColor:C.warningLight,borderRadius:'8px'}}><p style={{color:C.warning,fontSize:'10px',margin:'0 0 4px'}}>Остаток</p><b style={{color:C.warning,fontSize:'13px'}}>{Math.round(remain).toLocaleString('ru-RU')+' ₽'}</b></div>
                    </div>
                    {pp.slice(0,8).map((p,i)=>(<div key={i} style={{padding:'6px 10px',backgroundColor:C.bg,borderRadius:'6px',marginTop:'4px',display:'flex',justifyContent:'space-between',fontSize:'11px'}}><span>{(p.date||'')+(p.note?' · '+p.note:'')}</span><b style={{color:C.success}}>{Math.round(Number(p.amount||0)).toLocaleString('ru-RU')+' ₽'}</b></div>))}
                    {pp.length===0&&<p style={{color:C.textMuted,fontSize:'11px',textAlign:'center',padding:'8px'}}>Платежей пока нет</p>}
                  </div>);
                })()}
              </div>
              {/* Договоры */}
              <div style={{...card,padding:'20px'}}>
                <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>📄 Договоры</b>
                {contracts.filter(c=>c.projectName===myProject.name||c.client===user.name).map(c=>(
                  <div key={c.id} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'8px 0',borderBottom:'1px solid '+C.border}}>
                    <div><b style={{fontSize:'13px',color:C.text}}>Договор № {c.number}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{Number(c.totalAmount||0).toLocaleString()+' ₽ · '+c.status}</p></div>
                    <button onClick={()=>showPreview('<h2>Договор №'+c.number+'</h2><p>Заказчик: '+c.client+'</p><p>Сумма: '+Number(c.totalAmount||0).toLocaleString()+' ₽</p>','Договор')} style={{...btnB,padding:'4px 10px',fontSize:'11px'}}><Eye size={11}/>Открыть</button>
                  </div>
                ))}
                {contracts.filter(c=>c.projectName===myProject.name||c.client===user.name).length===0&&<p style={{color:C.textMuted,fontSize:'12px'}}>Договоров нет</p>}
              </div>
            </div>
          )}
        </div>
        {/* Модалка АОСР для подписи заказчика */}
        {editingAct&&(()=>{
          const a=editingAct;
          const upd=(k,v)=>setEditingAct({...editingAct,[k]:v});
          const allSigned=!!(a.signedCustomer&&a.signedSupervisor&&a.signedContractor&&a.signedSubcontractor);
          const saveSign=async()=>{
            const body={
              status:allSigned?'Подписан':(a.status||'Черновик'),
              signedCustomer:a.signedCustomer||'',signedSupervisor:a.signedSupervisor||'',
              signedContractor:a.signedContractor||'',signedSubcontractor:a.signedSubcontractor||'',
              signedCustomerAt:a.signedCustomerAt||'',signedSupervisorAt:a.signedSupervisorAt||'',
              signedContractorAt:a.signedContractorAt||'',signedSubcontractorAt:a.signedSubcontractorAt||'',
              conclusion:a.conclusion||'',comments:a.comments||'',
              materialsUsed:a.materialsUsed||'',projectDocs:a.projectDocs||'',
              photos:a.photos||'',certificates:a.certificates||'',city:a.city||'',
            };
            const res=await fetch(API+'/hidden-works-acts/'+a.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
            const data=await res.json().catch(()=>({}));
            setHiddenActs(prev=>prev.map(x=>x.id===a.id?{...x,...body,status:data.status||body.status}:x));
            setEditingAct(null);
          };
          return(<div onClick={()=>setEditingAct(null)} style={{position:'fixed',inset:0,backgroundColor:'rgba(0,0,0,0.55)',zIndex:1600,display:'flex',alignItems:'center',justifyContent:'center',padding:'20px'}}>
            <div onClick={e=>e.stopPropagation()} style={{...card,padding:0,width:'min(640px,100%)',maxHeight:'92vh',display:'flex',flexDirection:'column',overflow:'hidden'}}>
              <div style={{padding:'16px 20px',borderBottom:'1.5px solid '+C.border,backgroundColor:C.bg,display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                <div>
                  <b style={{color:C.text,fontSize:'15px',display:'block'}}>🔒 {a.actNumber}</b>
                  <span style={{fontSize:'11px',color:C.textSec}}>Акт освидетельствования скрытых работ</span>
                </div>
                <button onClick={()=>setEditingAct(null)} style={{...btnG,padding:'5px 10px'}}>✕</button>
              </div>
              <div style={{flex:1,overflowY:'auto',padding:'18px 20px'}}>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px',marginBottom:'14px',padding:'12px',backgroundColor:C.bg,borderRadius:'10px',border:'1.5px solid '+C.border}}>
                  <div><p style={{fontSize:'11px',color:C.textSec,margin:'0 0 4px',fontWeight:'600'}}>Работа</p><b style={{fontSize:'13px',color:C.text}}>{a.workName}</b></div>
                  <div><p style={{fontSize:'11px',color:C.textSec,margin:'0 0 4px',fontWeight:'600'}}>Объём</p><b style={{fontSize:'13px',color:C.text}}>{Number(a.quantity||0).toLocaleString('ru-RU')+' '+(a.unit||'')}</b></div>
                  <div><p style={{fontSize:'11px',color:C.textSec,margin:'0 0 4px',fontWeight:'600'}}>Бригада</p><b style={{fontSize:'13px',color:C.text}}>{a.brigade||'—'}</b></div>
                  <div><p style={{fontSize:'11px',color:C.textSec,margin:'0 0 4px',fontWeight:'600'}}>Дата</p><b style={{fontSize:'13px',color:C.text}}>{a.workDate||'—'}</b></div>
                </div>
                <p style={{fontSize:'11px',color:C.textSec,fontWeight:'600',marginBottom:'4px'}}>Материалы</p>
                <div style={{padding:'10px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border,fontSize:'12px',color:C.textSec,whiteSpace:'pre-wrap',marginBottom:'14px',minHeight:'40px'}}>{a.materialsUsed||'(не указаны подрядчиком)'}</div>
                <p style={{fontSize:'11px',color:C.textSec,fontWeight:'600',marginBottom:'4px'}}>Заключение комиссии</p>
                <div style={{padding:'10px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border,fontSize:'12px',color:C.textSec,whiteSpace:'pre-wrap',marginBottom:'14px',minHeight:'40px'}}>{a.conclusion||'(подрядчик ещё не заполнил)'}</div>
                <div style={{padding:'14px',backgroundColor:C.accentLight,border:'1.5px solid '+C.accentBorder,borderRadius:'10px'}}>
                  <b style={{display:'block',marginBottom:'10px',color:C.accent,fontSize:'13px'}}>✍️ Моя подпись (Заказчик)</b>
                  <input value={a.signedCustomer||''} onChange={e=>upd('signedCustomer',e.target.value)} placeholder='ФИО, должность, организация' style={{...inp,marginBottom:'8px'}}/>
                  <input type='date' value={a.signedCustomerAt||''} onChange={e=>upd('signedCustomerAt',e.target.value)} style={inp}/>
                </div>
                <div style={{marginTop:'14px',padding:'10px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border,fontSize:'11px'}}>
                  <b style={{color:C.text,fontSize:'12px'}}>Подписи 4 сторон:</b>
                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginTop:'8px'}}>
                    <div><span style={{color:a.signedCustomer?C.success:C.textMuted}}>{a.signedCustomer?'✅':'⏳'} Заказчик:</span> {a.signedCustomer||'—'}</div>
                    <div><span style={{color:a.signedSupervisor?C.success:C.textMuted}}>{a.signedSupervisor?'✅':'⏳'} Технадзор:</span> {a.signedSupervisor||'—'}</div>
                    <div><span style={{color:a.signedContractor?C.success:C.textMuted}}>{a.signedContractor?'✅':'⏳'} Генподрядчик:</span> {a.signedContractor||'—'}</div>
                    <div><span style={{color:a.signedSubcontractor?C.success:C.textMuted}}>{a.signedSubcontractor?'✅':'⏳'} Субподрядчик:</span> {a.signedSubcontractor||'—'}</div>
                  </div>
                </div>
              </div>
              <div style={{padding:'14px 20px',borderTop:'1.5px solid '+C.border,backgroundColor:C.bg,display:'flex',gap:'8px',justifyContent:'flex-end'}}>
                <button onClick={()=>setEditingAct(null)} style={btnG}>Отмена</button>
                <button onClick={saveSign} style={btnO}>✍️ Подписать</button>
              </div>
            </div>
          </div>);
        })()}
        {showPhotoModal&&(<div onClick={()=>setShowPhotoModal(null)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.9)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:2000,cursor:'pointer'}}><img src={showPhotoModal} alt="" style={{maxWidth:'90%',maxHeight:'90%',borderRadius:'12px'}}/></div>)}
        {previewContent&&<PreviewModal content={previewContent} title={previewTitle} onClose={()=>setPreviewContent(null)}/>}
      </div>
    );
  }

  const menuItems = allMenuItems.filter(item=>canAccess(item.id));

  return (
    <div style={{display:'flex',height:'100vh',backgroundColor:C.bg,position:'relative',overflow:'hidden'}}>
      {previewContent&&<PreviewModal content={previewContent} title={previewTitle} onClose={()=>setPreviewContent(null)}/>}
      {showPhotoModal&&(<div onClick={()=>setShowPhotoModal(null)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.9)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:2000,cursor:'pointer'}}><img src={showPhotoModal} alt="" style={{maxWidth:'90%',maxHeight:'90%',borderRadius:'12px'}}/></div>)}
      {editingAct&&(()=>{
        const act=editingAct;
        const upd=(k,v)=>setEditingAct({...editingAct,[k]:v});
        const photosArr=(act.photos||'').split(',').filter(Boolean);
        const certsArr=(act.certificates||'').split(',').filter(Boolean);
        const fillByAI=async()=>{
          setEditingAct(prev=>({...prev,__aiLoading:true}));
          try{
            const res=await fetch(API+'/hidden-works-acts/'+act.id+'/ai-prefill',{method:'POST'});
            if(!res.ok){const e=await res.json().catch(()=>({}));throw new Error(e.detail||('HTTP '+res.status));}
            const d=await res.json();
            setEditingAct(prev=>({...prev,conclusion:d.conclusion||prev.conclusion,projectDocs:d.projectDocs||prev.projectDocs,aiFilled:true,__aiLoading:false}));
            setHiddenActs(prevList=>prevList.map(a=>a.id===act.id?{...a,conclusion:d.conclusion||a.conclusion,projectDocs:d.projectDocs||a.projectDocs,aiFilled:true}:a));
          }catch(e){
            alert('Не получилось получить ответ от AI: '+e.message);
            setEditingAct(prev=>({...prev,__aiLoading:false}));
          }
        };
        const saveAct=async()=>{
          const body={status:act.status||'Черновик',signedCustomer:act.signedCustomer||'',signedSupervisor:act.signedSupervisor||'',signedContractor:act.signedContractor||'',signedSubcontractor:act.signedSubcontractor||'',signedCustomerAt:act.signedCustomerAt||'',signedSupervisorAt:act.signedSupervisorAt||'',signedContractorAt:act.signedContractorAt||'',signedSubcontractorAt:act.signedSubcontractorAt||'',conclusion:act.conclusion||'',comments:act.comments||'',materialsUsed:act.materialsUsed||'',projectDocs:act.projectDocs||'',photos:act.photos||'',certificates:act.certificates||'',city:act.city||''};
          const res=await fetch(API+'/hidden-works-acts/'+act.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
          const data=await res.json().catch(()=>({}));
          const newStatus=data.status||act.status;
          const updated={...act,status:newStatus,aiFilled:false};
          setHiddenActs(prev=>prev.map(a=>a.id===act.id?updated:a));
          setEditingAct(null);
        };
        const onUploadPhoto=async file=>{const url=await uploadPhoto(file);if(url){const next=[...photosArr,url].join(',');upd('photos',next);}};
        const onUploadCert=async file=>{const url=await uploadPhoto(file);if(url){const next=[...certsArr,url].join(',');upd('certificates',next);}};
        const removePhoto=i=>{const next=photosArr.filter((_,idx)=>idx!==i).join(',');upd('photos',next);};
        const removeCert=i=>{const next=certsArr.filter((_,idx)=>idx!==i).join(',');upd('certificates',next);};
        const absUrl=u=>u.startsWith('http')?u:API+u;
        const labelStyle={fontSize:'11px',color:C.textSec,fontWeight:'600',marginBottom:'4px',display:'block'};
        const sectionStyle={marginBottom:'14px'};
        const allSigned=!!(act.signedCustomer&&act.signedSupervisor&&act.signedContractor&&act.signedSubcontractor);
        return(<div onClick={()=>setEditingAct(null)} style={{position:'fixed',inset:0,backgroundColor:'rgba(0,0,0,0.55)',zIndex:1600,display:'flex',alignItems:'center',justifyContent:'center',padding:'20px'}}>
          <div onClick={e=>e.stopPropagation()} style={{...card,padding:0,width:'min(900px,100%)',maxHeight:'92vh',display:'flex',flexDirection:'column',overflow:'hidden'}}>
            <div style={{padding:'16px 20px',borderBottom:'1.5px solid '+C.border,backgroundColor:C.bg,display:'flex',justifyContent:'space-between',alignItems:'center',flexWrap:'wrap',gap:'8px'}}>
              <div>
                <b style={{color:C.text,fontSize:'16px',display:'block'}}>🔒 {act.actNumber}</b>
                <span style={{fontSize:'12px',color:C.textSec}}>Акт освидетельствования скрытых работ · {act.projectName}</span>
              </div>
              <div style={{display:'flex',alignItems:'center',gap:'10px'}}>
                <span style={{padding:'4px 10px',borderRadius:'12px',fontSize:'12px',fontWeight:'600',backgroundColor:allSigned?C.successLight:C.warningLight,color:allSigned?C.success:C.warning}}>{allSigned?'Подписан':(act.status||'Черновик')}</span>
                <button onClick={()=>setEditingAct(null)} style={{...btnG,padding:'5px 10px'}}><X size={14}/></button>
              </div>
            </div>
            <div style={{flex:1,overflowY:'auto',padding:'18px 20px'}}>
              {act.aiFilled&&(<div style={{marginBottom:'14px',padding:'10px 12px',backgroundColor:'#d1fae5',border:'1.5px solid #10b981',borderRadius:'10px',display:'flex',alignItems:'center',gap:'10px'}}><span style={{fontSize:'20px'}}>🤖</span><span style={{fontSize:'12px',color:C.text,lineHeight:1.4}}><b>Черновик заполнен AI.</b> Проверьте формулировки перед подписью — при сохранении после правки метка снимется.</span></div>)}
              <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:'10px',marginBottom:'18px',padding:'12px',backgroundColor:C.bg,borderRadius:'10px',border:'1.5px solid '+C.border}}>
                <div><p style={labelStyle}>Раздел сметы</p><b style={{fontSize:'13px',color:C.text}}>{act.sectionName||'—'}</b></div>
                <div><p style={labelStyle}>Работа</p><b style={{fontSize:'13px',color:C.text}}>{act.workName}</b></div>
                <div><p style={labelStyle}>Бригада</p><b style={{fontSize:'13px',color:C.text}}>{act.brigade||'—'}</b></div>
                <div><p style={labelStyle}>Объём</p><b style={{fontSize:'13px',color:C.text}}>{Number(act.quantity||0).toLocaleString('ru-RU')+' '+(act.unit||'')}</b></div>
                <div><p style={labelStyle}>Цена за ед.</p><b style={{fontSize:'13px',color:C.text}}>{Number(act.pricePerUnit||0).toLocaleString('ru-RU')+' ₽'}</b></div>
                <div><p style={labelStyle}>Сумма</p><b style={{fontSize:'14px',color:C.accent}}>{Number(act.total||0).toLocaleString('ru-RU')+' ₽'}</b></div>
                <div><p style={labelStyle}>Дата работ</p><b style={{fontSize:'13px',color:C.text}}>{act.workDate||'—'}</b></div>
              </div>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px',marginBottom:'14px'}}>
                <div><label style={labelStyle}>Город (для печати)</label><input value={act.city||''} onChange={e=>upd('city',e.target.value)} placeholder='напр. г. Барнаул' style={inp}/></div>
                <div><label style={labelStyle}>Статус (вручную)</label><select value={act.status||'Черновик'} onChange={e=>upd('status',e.target.value)} style={inp}><option>Черновик</option><option>На подписи</option><option>Подписан</option><option>Аннулирован</option></select></div>
              </div>
              <div style={sectionStyle}><label style={labelStyle}>Использованные материалы (марки, сертификаты)</label><textarea value={act.materialsUsed||''} onChange={e=>upd('materialsUsed',e.target.value)} placeholder='Напр.: арматура А500С по ГОСТ 5781-82, сертификат №...; бетон В25 W6, паспорт №...' style={{...inp,minHeight:'70px',resize:'vertical'}}/></div>
              <div style={sectionStyle}><label style={labelStyle}>Проектная документация (чертежи, разделы){act.aiFilled?' 🤖':''}</label><textarea value={act.projectDocs||''} onChange={e=>upd('projectDocs',e.target.value)} placeholder='Напр.: раздел КЖ, лист 12; раздел АР, узел 4' style={{...inp,minHeight:'60px',resize:'vertical'}}/></div>
              <div style={sectionStyle}><label style={labelStyle}>Заключение комиссии{act.aiFilled?' 🤖':''}</label><textarea value={act.conclusion||''} onChange={e=>upd('conclusion',e.target.value)} placeholder='Работы выполнены в соответствии с проектной документацией. Разрешается производство последующих работ.' style={{...inp,minHeight:'70px',resize:'vertical'}}/></div>
              <div style={{...sectionStyle,padding:'14px',backgroundColor:C.bg,borderRadius:'10px',border:'1.5px solid '+C.border}}>
                <b style={{display:'block',marginBottom:'10px',color:C.text,fontSize:'13px'}}>✍️ Подписи комиссии (ФИО + дата)</b>
                {[{role:'Заказчик',f:'signedCustomer',d:'signedCustomerAt'},{role:'Технадзор',f:'signedSupervisor',d:'signedSupervisorAt'},{role:'Генподрядчик',f:'signedContractor',d:'signedContractorAt'},{role:'Субподрядчик',f:'signedSubcontractor',d:'signedSubcontractorAt'}].map(s=>(<div key={s.f} style={{display:'grid',gridTemplateColumns:'140px 1fr 140px',gap:'8px',marginBottom:'8px',alignItems:'center'}}>
                  <span style={{fontSize:'12px',color:C.textSec,fontWeight:'600'}}>{s.role}:</span>
                  <input value={act[s.f]||''} onChange={e=>upd(s.f,e.target.value)} placeholder='ФИО, должность, организация' style={{...inp,marginBottom:0}}/>
                  <input type='date' value={act[s.d]||''} onChange={e=>upd(s.d,e.target.value)} style={{...inp,marginBottom:0}}/>
                </div>))}
                <p style={{fontSize:'11px',color:C.textMuted,margin:'8px 0 0',lineHeight:1.4}}>Когда все 4 ФИО заполнены — статус акта автоматически станет «Подписан» при сохранении.</p>
              </div>
              <div style={sectionStyle}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'8px'}}>
                  <b style={{color:C.text,fontSize:'13px'}}>📷 Фото скрытых работ ({photosArr.length})</b>
                  <label style={{...btnB,padding:'5px 10px',fontSize:'12px',cursor:'pointer'}}><Upload size={12}/>Добавить фото<input type='file' accept='image/*' multiple style={{display:'none'}} onChange={async e=>{for(const f of Array.from(e.target.files)){await onUploadPhoto(f);}}}/></label>
                </div>
                {photosArr.length===0?<p style={{color:C.textMuted,fontSize:'12px',margin:0}}>Фотографий не загружено</p>:(<div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(90px,1fr))',gap:'8px'}}>{photosArr.map((u,i)=>(<div key={i} style={{position:'relative'}}><img src={absUrl(u)} alt='' onClick={()=>setShowPhotoModal(absUrl(u))} style={{width:'100%',height:'90px',borderRadius:'8px',objectFit:'cover',cursor:'pointer',border:'1.5px solid '+C.border}}/><button onClick={()=>removePhoto(i)} style={{position:'absolute',top:'2px',right:'2px',backgroundColor:'rgba(0,0,0,0.6)',color:'white',border:'none',borderRadius:'50%',width:'20px',height:'20px',cursor:'pointer',fontSize:'11px'}}>×</button></div>))}</div>)}
              </div>
              <div style={sectionStyle}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'8px'}}>
                  <b style={{color:C.text,fontSize:'13px'}}>📄 Сертификаты и документы ({certsArr.length})</b>
                  <label style={{...btnB,padding:'5px 10px',fontSize:'12px',cursor:'pointer'}}><Upload size={12}/>Загрузить файл<input type='file' accept='.pdf,.xlsx,.xls,.doc,.docx,image/*' multiple style={{display:'none'}} onChange={async e=>{for(const f of Array.from(e.target.files)){await onUploadCert(f);}}}/></label>
                </div>
                {certsArr.length===0?<p style={{color:C.textMuted,fontSize:'12px',margin:0}}>Файлов не прикреплено</p>:(<div style={{display:'flex',flexDirection:'column',gap:'4px'}}>{certsArr.map((u,i)=>{const name=u.split('/').pop()||u;return(<div key={i} style={{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'8px 10px',backgroundColor:C.bg,border:'1.5px solid '+C.border,borderRadius:'8px'}}><a href={absUrl(u)} target='_blank' rel='noreferrer' style={{color:C.accent,fontSize:'12px',textDecoration:'none',display:'flex',alignItems:'center',gap:'6px',flex:1,overflow:'hidden'}}><span>📄</span><span style={{overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{name}</span></a><button onClick={()=>removeCert(i)} style={{...btnR,padding:'3px 7px',fontSize:'11px'}}><X size={10}/></button></div>);})}</div>)}
              </div>
              <div style={sectionStyle}><label style={labelStyle}>Комментарии (внутренние)</label><textarea value={act.comments||''} onChange={e=>upd('comments',e.target.value)} placeholder='Внутренние пометки, не печатаются' style={{...inp,minHeight:'50px',resize:'vertical'}}/></div>
            </div>
            <div style={{padding:'14px 20px',borderTop:'1.5px solid '+C.border,backgroundColor:C.bg,display:'flex',gap:'8px',justifyContent:'space-between',flexWrap:'wrap'}}>
              <button onClick={()=>{showPreview(buildHiddenActContent(act),'АОСР № '+act.actNumber);}} style={btnB}><Eye size={14}/>🖨️ Печать по СНиП</button>
              <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
                <button disabled={!!act.__aiLoading} onClick={fillByAI} style={{...btnB,backgroundColor:'#10b981',opacity:act.__aiLoading?0.6:1,cursor:act.__aiLoading?'not-allowed':'pointer'}}><Bot size={14}/>{act.__aiLoading?'AI работает…':(act.aiFilled?'🤖 Перезаполнить AI':'🤖 Заполнить через AI')}</button>
                <button onClick={()=>setEditingAct(null)} style={btnG}>Отмена</button>
                <button onClick={saveAct} style={btnO}><Check size={14}/>Сохранить</button>
              </div>
            </div>
          </div>
        </div>);
      })()}
      {editingJournal&&(()=>{
        const j=editingJournal;
        const upd=(k,v)=>setEditingJournal({...editingJournal,[k]:v});
        const todayWeather=weatherLog.find(w=>w.projectName===j.project&&w.date===j.date);
        const proraby=users.filter(u=>['прораб','главный_инженер','зам_директора'].includes(u.role)).map(u=>u.name).filter(Boolean);
        const labelStyle={fontSize:'11px',color:C.textSec,fontWeight:'600',marginBottom:'4px',display:'block'};
        const sectionStyle={marginBottom:'14px'};
        const fillByAI=async()=>{
          setEditingJournal(prev=>({...prev,__aiLoading:true}));
          try{
            const res=await fetch(API+'/work-journal/'+j.id+'/ai-prefill',{method:'POST'});
            if(!res.ok){const e=await res.json().catch(()=>({}));throw new Error(e.detail||('HTTP '+res.status));}
            const d=await res.json();
            setEditingJournal(prev=>({...prev,normatives:d.normatives||prev.normatives,projectDocs:d.projectDocs||prev.projectDocs,comment:(prev.comment&&prev.comment.trim())?prev.comment:(d.qualityNote||''),aiFilled:true,__aiLoading:false}));
            setWorkJournal(prev=>prev.map(x=>x.id===j.id?{...x,normatives:d.normatives||x.normatives,projectDocs:d.projectDocs||x.projectDocs,aiFilled:true}:x));
          }catch(e){
            alert('Не получилось получить ответ от AI: '+e.message);
            setEditingJournal(prev=>({...prev,__aiLoading:false}));
          }
        };
        const saveJournal=async()=>{
          const body={
            status:j.status||'На проверке',
            comment:j.comment||'',
            responsibleItr:j.responsibleItr||'',
            weather:j.weather||'',
            timeStart:j.timeStart||'',
            timeEnd:j.timeEnd||'',
            qualityStatus:j.qualityStatus||'',
            normatives:j.normatives||'',
            projectDocs:j.projectDocs||'',
            sectionName:j.sectionName||'',
            hiddenWork:!!j.hiddenWork,
          };
          await fetch(API+'/work-journal/'+j.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
          setWorkJournal(prev=>prev.map(x=>x.id===j.id?{...x,...body,aiFilled:false}:x));
          setEditingJournal(null);
        };
        return(<div onClick={()=>setEditingJournal(null)} style={{position:'fixed',inset:0,backgroundColor:'rgba(0,0,0,0.55)',zIndex:1600,display:'flex',alignItems:'center',justifyContent:'center',padding:'20px'}}>
          <div onClick={e=>e.stopPropagation()} style={{...card,padding:0,width:'min(900px,100%)',maxHeight:'92vh',display:'flex',flexDirection:'column',overflow:'hidden'}}>
            <div style={{padding:'16px 20px',borderBottom:'1.5px solid '+C.border,backgroundColor:C.bg,display:'flex',justifyContent:'space-between',alignItems:'center',flexWrap:'wrap',gap:'8px'}}>
              <div>
                <b style={{color:C.text,fontSize:'16px',display:'block'}}>📖 Запись журнала производства работ</b>
                <span style={{fontSize:'12px',color:C.textSec}}>{(j.project||'—')+' · '+(j.date||'—')+' · '+(j.masterName||'—')}</span>
              </div>
              <div style={{display:'flex',alignItems:'center',gap:'10px'}}>
                <span style={{padding:'4px 10px',borderRadius:'12px',fontSize:'12px',fontWeight:'600',backgroundColor:j.status==='Подтверждено'?C.successLight:j.status==='Отклонено'?C.dangerLight:C.warningLight,color:j.status==='Подтверждено'?C.success:j.status==='Отклонено'?C.danger:C.warning}}>{j.status||'—'}</span>
                <button onClick={()=>setEditingJournal(null)} style={{...btnG,padding:'5px 10px'}}><X size={14}/></button>
              </div>
            </div>
            <div style={{flex:1,overflowY:'auto',padding:'18px 20px'}}>
              {j.aiFilled&&(<div style={{marginBottom:'14px',padding:'10px 12px',backgroundColor:'#d1fae5',border:'1.5px solid #10b981',borderRadius:'10px',display:'flex',alignItems:'center',gap:'10px'}}><span style={{fontSize:'20px'}}>🤖</span><span style={{fontSize:'12px',color:C.text,lineHeight:1.4}}><b>Поля заполнены AI.</b> Проверь нормативы и проектные документы — при сохранении после правки метка снимется.</span></div>)}
              <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:'10px',marginBottom:'18px',padding:'12px',backgroundColor:C.bg,borderRadius:'10px',border:'1.5px solid '+C.border}}>
                <div><p style={labelStyle}>Раздел сметы</p><b style={{fontSize:'13px',color:C.text}}>{j.sectionName||'—'}</b></div>
                <div><p style={labelStyle}>Работа</p><b style={{fontSize:'13px',color:C.text}}>{j.description}</b></div>
                <div><p style={labelStyle}>Исполнитель</p><b style={{fontSize:'13px',color:C.text}}>{j.masterName||'—'}</b></div>
                <div><p style={labelStyle}>Объём</p><b style={{fontSize:'13px',color:C.text}}>{(j.quantity||0)+' '+(j.unit||'')}</b></div>
                <div><p style={labelStyle}>Сумма</p><b style={{fontSize:'14px',color:C.accent}}>{Number(j.total||0).toLocaleString('ru-RU')+' ₽'}</b></div>
                <div><p style={labelStyle}>Дата</p><b style={{fontSize:'13px',color:C.text}}>{j.date||'—'}</b></div>
              </div>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px',marginBottom:'14px'}}>
                <div><label style={labelStyle}>Ответственный ИТР (прораб)</label><input list="jrnl-itr-list" value={j.responsibleItr||''} onChange={e=>upd('responsibleItr',e.target.value)} placeholder="ФИО прораба или инженера" style={inp}/><datalist id="jrnl-itr-list">{proraby.map(n=><option key={n} value={n}/>)}</datalist></div>
                <div><label style={labelStyle}>Статус</label><select value={j.status||'На проверке'} onChange={e=>upd('status',e.target.value)} style={inp}><option>На проверке</option><option>Подтверждено</option><option>Отклонено</option></select></div>
              </div>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 2fr',gap:'10px',marginBottom:'14px'}}>
                <div><label style={labelStyle}>Начало работы</label><input type="time" value={j.timeStart||''} onChange={e=>upd('timeStart',e.target.value)} style={inp}/></div>
                <div><label style={labelStyle}>Окончание</label><input type="time" value={j.timeEnd||''} onChange={e=>upd('timeEnd',e.target.value)} style={inp}/></div>
                <div><label style={labelStyle}>Метеоусловия (температура, осадки, ветер)</label><div style={{display:'flex',gap:'4px'}}><input value={j.weather||''} onChange={e=>upd('weather',e.target.value)} placeholder="напр. +12°C, без осадков, ветер 3 м/с" style={{...inp,marginBottom:0,flex:1}}/>{todayWeather&&<button onClick={()=>upd('weather',(todayWeather.condition||'')+', '+(todayWeather.temperature||'')+'°C, ветер '+(todayWeather.windSpeed||'')+' м/с')} title="Подтянуть из журнала погоды" style={{...btnG,padding:'5px 10px',fontSize:'11px'}}>📡</button>}</div></div>
              </div>
              <div style={sectionStyle}><label style={labelStyle}>Качество / соответствие проекту</label><select value={j.qualityStatus||''} onChange={e=>upd('qualityStatus',e.target.value)} style={inp}><option value="">— не указано —</option><option>Соответствует проекту</option><option>Соответствует с замечаниями</option><option>Не соответствует</option></select></div>
              <div style={sectionStyle}><label style={labelStyle}>Применимые нормативы (СНиП/СП/ГОСТ){j.aiFilled?' 🤖':''}</label><textarea value={j.normatives||''} onChange={e=>upd('normatives',e.target.value)} placeholder="Напр.: СП 71.13330.2017, ГОСТ 30693-2000" style={{...inp,minHeight:'60px',resize:'vertical'}}/></div>
              <div style={sectionStyle}><label style={labelStyle}>Проектная документация (разделы, листы){j.aiFilled?' 🤖':''}</label><textarea value={j.projectDocs||''} onChange={e=>upd('projectDocs',e.target.value)} placeholder="Напр.: раздел КЖ, лист 12; раздел АР, узел 4" style={{...inp,minHeight:'60px',resize:'vertical'}}/></div>
              <div style={sectionStyle}><label style={labelStyle}>Использованные материалы</label><div style={{padding:'10px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border,fontSize:'12px',color:C.textSec,whiteSpace:'pre-wrap'}}>{j.materialsUsed?(typeof j.materialsUsed==='string'?j.materialsUsed:JSON.stringify(j.materialsUsed)):'(не указаны)'}</div></div>
              <div style={sectionStyle}><label style={labelStyle}>Комментарий / заключение</label><textarea value={j.comment||''} onChange={e=>upd('comment',e.target.value)} placeholder="Замечания, особенности производства работ, ссылки на акты" style={{...inp,minHeight:'70px',resize:'vertical'}}/></div>
              {j.hiddenWork&&<div style={{padding:'10px 12px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder,borderRadius:'8px',fontSize:'12px',color:C.warning,marginBottom:'10px'}}>🔒 Это скрытые работы — для них должен быть оформлен Акт освидетельствования скрытых работ (АОСР). Проверь вкладку «АОСР».</div>}
            </div>
            <div style={{padding:'14px 20px',borderTop:'1.5px solid '+C.border,backgroundColor:C.bg,display:'flex',gap:'8px',justifyContent:'space-between',flexWrap:'wrap'}}>
              <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
                <button onClick={()=>showPreview(buildWorkJournalContent([j],j.project,j.date,j.date),'Запись журнала')} style={btnB}><Eye size={14}/>🖨️ Печать</button>
                {j.hiddenWork&&(<button onClick={()=>{const matchingAct=hiddenActs.find(a=>a.projectName===j.project&&(a.workName||'').trim()===(j.description||'').trim());if(matchingAct){setEditingJournal(null);setEditingAct(matchingAct);}else{alert('Акт скрытых работ для этой записи не найден. Он создаётся автоматически из сметы — отметь позицию переключателем 🔒 и заполни «Сделано».');}}} style={{...btnB,backgroundColor:'#10b981'}}>🔒 Открыть АОСР</button>)}
              </div>
              <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
                <button disabled={!!j.__aiLoading} onClick={fillByAI} style={{...btnB,backgroundColor:'#10b981',opacity:j.__aiLoading?0.6:1,cursor:j.__aiLoading?'not-allowed':'pointer'}}><Bot size={14}/>{j.__aiLoading?'AI работает…':(j.aiFilled?'🤖 Перезаполнить AI':'🤖 Заполнить через AI')}</button>
                <button onClick={()=>setEditingJournal(null)} style={btnG}>Отмена</button>
                <button onClick={saveJournal} style={btnO}><Check size={14}/>Сохранить</button>
              </div>
            </div>
          </div>
        </div>);
      })()}
      {showJournalTableModal&&(()=>{
        const pn=showJournalTableModal;
        const journalHere=workJournal.filter(jw=>jw.project===pn);
        let filtered=journalHere;
        if(journalFilter.from) filtered=filtered.filter(r=>(r.date||'')>=journalFilter.from);
        if(journalFilter.to) filtered=filtered.filter(r=>(r.date||'')<=journalFilter.to);
        if(journalFilter.masterName) filtered=filtered.filter(r=>(r.masterName||'')===journalFilter.masterName);
        if(journalFilter.sectionName) filtered=filtered.filter(r=>(r.sectionName||'')===journalFilter.sectionName);
        if(journalFilter.status) filtered=filtered.filter(r=>r.status===journalFilter.status);
        const sections=[...new Set(journalHere.map(r=>r.sectionName).filter(Boolean))];
        const masters=[...new Set(journalHere.map(r=>r.masterName).filter(Boolean))];
        const sumF=filtered.reduce((s,r)=>s+Number(r.total||0),0);
        const cntDraft=filtered.filter(r=>r.status==='На проверке').length;
        const cntOk=filtered.filter(r=>r.status==='Подтверждено').length;
        return(<div onClick={()=>setShowJournalTableModal(null)} style={{position:'fixed',inset:0,backgroundColor:'rgba(0,0,0,0.55)',zIndex:1600,display:'flex',alignItems:'center',justifyContent:'center',padding:'20px'}}>
          <div onClick={e=>e.stopPropagation()} style={{...card,padding:0,width:'min(1100px,100%)',maxHeight:'92vh',display:'flex',flexDirection:'column',overflow:'hidden'}}>
            <div style={{padding:'16px 20px',borderBottom:'1.5px solid '+C.border,backgroundColor:C.bg,display:'flex',justifyContent:'space-between',alignItems:'center',flexWrap:'wrap',gap:'8px'}}>
              <div>
                <b style={{color:C.text,fontSize:'16px',display:'block'}}>📋 Журнал работ — Таблица КС-6а</b>
                <span style={{fontSize:'12px',color:C.textSec}}>{pn+' · РД-11-05-2007 · СП 48.13330.2019'}</span>
              </div>
              <button onClick={()=>setShowJournalTableModal(null)} style={{...btnG,padding:'5px 10px'}}><X size={14}/></button>
            </div>
            <div style={{flex:1,overflowY:'auto',padding:'18px 20px'}}>
              {journalHere.length===0?<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Записей в журнале пока нет</div>:(<div>
                <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(110px,1fr))',gap:'8px',marginBottom:'12px'}}>
                  <input type="date" value={journalFilter.from} onChange={e=>setJournalFilter({...journalFilter,from:e.target.value})} title="Период с" style={{...inp,marginBottom:0,fontSize:'11px'}}/>
                  <input type="date" value={journalFilter.to} onChange={e=>setJournalFilter({...journalFilter,to:e.target.value})} title="Период по" style={{...inp,marginBottom:0,fontSize:'11px'}}/>
                  <select value={journalFilter.sectionName} onChange={e=>setJournalFilter({...journalFilter,sectionName:e.target.value})} style={{...inp,marginBottom:0,fontSize:'11px'}}><option value="">Все разделы</option>{sections.map(s=><option key={s} value={s}>{s}</option>)}</select>
                  <select value={journalFilter.masterName} onChange={e=>setJournalFilter({...journalFilter,masterName:e.target.value})} style={{...inp,marginBottom:0,fontSize:'11px'}}><option value="">Все исполнители</option>{masters.map(m=><option key={m} value={m}>{m}</option>)}</select>
                  <select value={journalFilter.status} onChange={e=>setJournalFilter({...journalFilter,status:e.target.value})} style={{...inp,marginBottom:0,fontSize:'11px'}}><option value="">Все статусы</option><option>На проверке</option><option>Подтверждено</option><option>Отклонено</option></select>
                  <button onClick={()=>showPreview(buildWorkJournalContent(filtered,pn,journalFilter.from,journalFilter.to),'КС-6а — '+pn)} style={{...btnB,fontSize:'11px',padding:'7px 10px'}}><Eye size={12}/>🖨 Печать КС-6а</button>
                </div>
                <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'10px',marginBottom:'14px'}}>
                  <div style={{...card,padding:'12px',backgroundColor:C.bg}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Записей</p><b style={{color:C.text,fontSize:'16px'}}>{filtered.length}</b></div>
                  <div style={{...card,padding:'12px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}><p style={{color:C.warning,fontSize:'11px',margin:'0 0 4px'}}>На проверке</p><b style={{color:C.warning,fontSize:'16px'}}>{cntDraft}</b></div>
                  <div style={{...card,padding:'12px',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder}}><p style={{color:C.success,fontSize:'11px',margin:'0 0 4px'}}>Подтверждено</p><b style={{color:C.success,fontSize:'16px'}}>{cntOk}</b></div>
                </div>
                <div style={{...card,padding:0,overflow:'auto'}}>
                  <table style={tbl}><thead><tr>
                    <th style={tblH}>Дата</th>
                    <th style={tblH}>Тип</th>
                    <th style={tblH}>Раздел</th>
                    <th style={tblH}>Работа</th>
                    <th style={tblH}>Объём</th>
                    <th style={tblH}>Исполнитель</th>
                    <th style={tblH}>ИТР</th>
                    <th style={tblH}>Погода</th>
                    <th style={tblH}>Качество</th>
                    <th style={tblH}>Статус</th>
                    <th style={tblH}>Сумма</th>
                  </tr></thead><tbody>
                    {filtered.map(jw=>(<tr key={jw.id} style={{cursor:'pointer',backgroundColor:jw.unexpectedWorkId?'#fef3c7':undefined}} onClick={()=>{setEditingJournal(jw);setShowJournalTableModal(null);}}>
                      <td style={tblC}>{jw.date||'—'}</td>
                      <td style={tblC}>{jw.unexpectedWorkId?<span style={{padding:'2px 6px',borderRadius:'8px',fontSize:'10px',fontWeight:'700',backgroundColor:'#fbbf24',color:'#78350f'}}>🆕 вне сметы</span>:<span style={{padding:'2px 6px',borderRadius:'8px',fontSize:'10px',fontWeight:'600',backgroundColor:C.bg,color:C.textSec}}>по смете</span>}</td>
                      <td style={tblC}>{jw.sectionName||'—'}</td>
                      <td style={{...tblC,maxWidth:'260px',whiteSpace:'normal'}}>{jw.description}{jw.hiddenWork?(()=>{const st=getActStatusForJournal({...jw,project:jw.project||pn});return(<span title={st?st.tip:'Скрытые работы — нужен АОСР'} style={{marginLeft:'4px',cursor:st&&st.act?'pointer':'default'}} onClick={e=>{if(st&&st.act){e.stopPropagation();setEditingAct(st.act);setShowJournalTableModal(null);}}}>🔒{st?st.icon:''}</span>);})():null}{jw.aiFilled?<span title="Заполнено AI" style={{marginLeft:'4px'}}>🤖</span>:null}</td>
                      <td style={tblC}>{(jw.quantity||0)+' '+(jw.unit||'')}</td>
                      <td style={tblC}>{jw.masterName||'—'}</td>
                      <td style={tblC}>{jw.responsibleItr||'—'}</td>
                      <td style={tblC}>{jw.weather||'—'}</td>
                      <td style={tblC}>{jw.qualityStatus||'—'}</td>
                      <td style={tblC}><span style={{padding:'2px 8px',borderRadius:'10px',fontSize:'11px',fontWeight:'600',backgroundColor:jw.status==='Подтверждено'?C.successLight:jw.status==='Отклонено'?C.dangerLight:C.warningLight,color:jw.status==='Подтверждено'?C.success:jw.status==='Отклонено'?C.danger:C.warning}}>{jw.status||'—'}</span></td>
                      <td style={tblC}>{Number(jw.total||0).toLocaleString('ru-RU')+' ₽'}</td>
                    </tr>))}
                    {filtered.length===0&&<tr><td colSpan={11} style={{...tblC,textAlign:'center',color:C.textMuted}}>По выбранным фильтрам записей нет</td></tr>}
                  </tbody></table>
                </div>
                <div style={{marginTop:'12px',padding:'12px',backgroundColor:C.accentLight,border:'1.5px solid '+C.accentBorder,borderRadius:'10px',textAlign:'right'}}>
                  <span style={{color:C.textSec,fontSize:'12px',marginRight:'10px'}}>Сумма по фильтру:</span>
                  <b style={{color:C.accent,fontSize:'15px'}}>{sumF.toLocaleString('ru-RU')+' ₽'}</b>
                </div>
              </div>)}
            </div>
          </div>
        </div>);
      })()}
      {editingInspection&&(()=>{
        const mi=editingInspection;
        const upd=(k,v)=>setEditingInspection({...editingInspection,[k]:v});
        const labelStyle={fontSize:'11px',color:C.textSec,fontWeight:'600',marginBottom:'4px',display:'block'};
        const sectionStyle={marginBottom:'14px'};
        const aiSuggest=async()=>{
          setEditingInspection(prev=>({...prev,__aiLoading:true}));
          try{
            const res=await fetch(API+'/material-inspection/'+mi.id+'/ai-suggest',{method:'POST'});
            if(!res.ok){const e=await res.json().catch(()=>({}));throw new Error(e.detail||('HTTP '+res.status));}
            const d=await res.json();
            setEditingInspection(prev=>({...prev,normatives:d.normatives||prev.normatives,remarks:(prev.remarks&&prev.remarks.trim())?prev.remarks:('Требуемые документы: '+(d.requiredDocs||'')),aiFilled:true,__aiLoading:false}));
            setMaterialInspections(prev=>prev.map(x=>x.id===mi.id?{...x,normatives:d.normatives||x.normatives,aiFilled:true}:x));
          }catch(e){
            alert('Не получилось получить ответ от AI: '+e.message);
            setEditingInspection(prev=>({...prev,__aiLoading:false}));
          }
        };
        const saveInspection=async()=>{
          const body={
            batchNumber:mi.batchNumber||'',
            passportNumber:mi.passportNumber||'',
            certificateNumber:mi.certificateNumber||'',
            testProtocolNumber:mi.testProtocolNumber||'',
            visualInspectionResult:mi.visualInspectionResult||'',
            remarks:mi.remarks||'',
            inspectorName:mi.inspectorName||'',
            inspectedAt:mi.inspectedAt||'',
            inspected:!!mi.inspected,
            normatives:mi.normatives||'',
          };
          await fetch(API+'/material-inspection/'+mi.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
          setMaterialInspections(prev=>prev.map(x=>x.id===mi.id?{...x,...body,aiFilled:false}:x));
          setEditingInspection(null);
        };
        return(<div onClick={()=>setEditingInspection(null)} style={{position:'fixed',inset:0,backgroundColor:'rgba(0,0,0,0.55)',zIndex:1600,display:'flex',alignItems:'center',justifyContent:'center',padding:'20px'}}>
          <div onClick={e=>e.stopPropagation()} style={{...card,padding:0,width:'min(820px,100%)',maxHeight:'92vh',display:'flex',flexDirection:'column',overflow:'hidden'}}>
            <div style={{padding:'16px 20px',borderBottom:'1.5px solid '+C.border,backgroundColor:C.bg,display:'flex',justifyContent:'space-between',alignItems:'center',flexWrap:'wrap',gap:'8px'}}>
              <div>
                <b style={{color:C.text,fontSize:'16px',display:'block'}}>📦 Входной контроль материала</b>
                <span style={{fontSize:'12px',color:C.textSec}}>{(mi.materialName||'—')+' · '+(mi.quantity||0)+' '+(mi.unit||'')+' · '+(mi.supplier||'—')}</span>
              </div>
              <div style={{display:'flex',alignItems:'center',gap:'10px'}}>
                <span style={{padding:'4px 10px',borderRadius:'12px',fontSize:'12px',fontWeight:'600',backgroundColor:mi.inspected?C.successLight:C.warningLight,color:mi.inspected?C.success:C.warning}}>{mi.inspected?'Проверено':'Ждёт проверки'}</span>
                <button onClick={()=>setEditingInspection(null)} style={{...btnG,padding:'5px 10px'}}><X size={14}/></button>
              </div>
            </div>
            <div style={{flex:1,overflowY:'auto',padding:'18px 20px'}}>
              {mi.aiFilled&&(<div style={{marginBottom:'14px',padding:'10px 12px',backgroundColor:'#d1fae5',border:'1.5px solid #10b981',borderRadius:'10px',display:'flex',alignItems:'center',gap:'10px'}}><span style={{fontSize:'20px'}}>🤖</span><span style={{fontSize:'12px',color:C.text,lineHeight:1.4}}><b>Поле «Нормативы» подсказано AI.</b> Проверь и сохрани — при правке метка снимется.</span></div>)}
              <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:'10px',marginBottom:'18px',padding:'12px',backgroundColor:C.bg,borderRadius:'10px',border:'1.5px solid '+C.border}}>
                <div><p style={labelStyle}>Материал</p><b style={{fontSize:'13px',color:C.text}}>{mi.materialName||'—'}</b></div>
                <div><p style={labelStyle}>Количество</p><b style={{fontSize:'13px',color:C.text}}>{(mi.quantity||0)+' '+(mi.unit||'')}</b></div>
                <div><p style={labelStyle}>Поставщик</p><b style={{fontSize:'13px',color:C.text}}>{mi.supplier||'—'}</b></div>
                <div><p style={labelStyle}>Дата приёмки</p><b style={{fontSize:'13px',color:C.text}}>{mi.receivedAt||'—'}</b></div>
              </div>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px',marginBottom:'14px'}}>
                <div><label style={labelStyle}>№ партии (на упаковке/паспорте)</label><input value={mi.batchNumber||''} onChange={e=>upd('batchNumber',e.target.value)} placeholder="напр. №147" style={inp}/></div>
                <div><label style={labelStyle}>Паспорт качества №</label><input value={mi.passportNumber||''} onChange={e=>upd('passportNumber',e.target.value)} placeholder="напр. ПК-2026/05/12" style={inp}/></div>
              </div>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px',marginBottom:'14px'}}>
                <div><label style={labelStyle}>Сертификат соответствия №</label><input value={mi.certificateNumber||''} onChange={e=>upd('certificateNumber',e.target.value)} placeholder="напр. РОСС RU.AB12.H00000" style={inp}/></div>
                <div><label style={labelStyle}>Протокол испытаний №</label><input value={mi.testProtocolNumber||''} onChange={e=>upd('testProtocolNumber',e.target.value)} placeholder="напр. ПИ-15 от 14.05.2026" style={inp}/></div>
              </div>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px',marginBottom:'14px'}}>
                <div><label style={labelStyle}>Результат визуального осмотра</label><select value={mi.visualInspectionResult||''} onChange={e=>upd('visualInspectionResult',e.target.value)} style={inp}><option value="">— не указано —</option><option>Соответствует</option><option>С замечаниями</option><option>Не соответствует</option></select></div>
                <div><label style={labelStyle}>Дата осмотра</label><input type='date' value={mi.inspectedAt||''} onChange={e=>upd('inspectedAt',e.target.value)} style={inp}/></div>
              </div>
              <div style={sectionStyle}><label style={labelStyle}>ФИО лица, проводившего входной контроль</label><input value={mi.inspectorName||''} onChange={e=>upd('inspectorName',e.target.value)} placeholder="ФИО прораба или кладовщика" style={inp}/></div>
              <div style={sectionStyle}><label style={labelStyle}>Применимые нормативы (ГОСТ/СП/СНиП){mi.aiFilled?' 🤖':''}</label><textarea value={mi.normatives||''} onChange={e=>upd('normatives',e.target.value)} placeholder="Напр.: ГОСТ 7473-2010 (бетон), ГОСТ 5781-82 (арматура)" style={{...inp,minHeight:'60px',resize:'vertical'}}/></div>
              <div style={sectionStyle}><label style={labelStyle}>Замечания / комментарий</label><textarea value={mi.remarks||''} onChange={e=>upd('remarks',e.target.value)} placeholder="Замечания по качеству, упаковке, документам" style={{...inp,minHeight:'70px',resize:'vertical'}}/></div>
              <div style={{padding:'10px 12px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border,display:'flex',alignItems:'center',gap:'10px'}}>
                <input type='checkbox' id='mi-checked' checked={!!mi.inspected} onChange={e=>upd('inspected',e.target.checked)} style={{width:'18px',height:'18px',cursor:'pointer'}}/>
                <label htmlFor='mi-checked' style={{fontSize:'13px',color:C.text,cursor:'pointer',fontWeight:'600'}}>Входной контроль завершён — материал можно выдавать на работы</label>
              </div>
            </div>
            <div style={{padding:'14px 20px',borderTop:'1.5px solid '+C.border,backgroundColor:C.bg,display:'flex',gap:'8px',justifyContent:'space-between',flexWrap:'wrap'}}>
              <button onClick={()=>showPreview(buildMaterialInspectionContent([mi],mi.projectName,mi.receivedAt,mi.receivedAt),'Запись входного контроля')} style={btnB}><Eye size={14}/>🖨️ Печать</button>
              <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
                <button disabled={!!mi.__aiLoading} onClick={aiSuggest} style={{...btnB,backgroundColor:'#10b981',opacity:mi.__aiLoading?0.6:1,cursor:mi.__aiLoading?'not-allowed':'pointer'}}><Bot size={14}/>{mi.__aiLoading?'AI работает…':'🤖 AI-подсказка нормативов'}</button>
                <button onClick={()=>setEditingInspection(null)} style={btnG}>Отмена</button>
                <button onClick={saveInspection} style={btnO}><Check size={14}/>Сохранить</button>
              </div>
            </div>
          </div>
        </div>);
      })()}
      {editingCable&&(()=>{
        const cb=editingCable;
        const upd=(k,v)=>setEditingCable({...editingCable,[k]:v});
        const proraby=users.filter(u=>['прораб','главный_инженер','зам_директора'].includes(u.role)).map(u=>u.name).filter(Boolean);
        const labelStyle={fontSize:'11px',color:C.textSec,fontWeight:'600',marginBottom:'4px',display:'block'};
        const sectionStyle={marginBottom:'14px'};
        const aiSuggest=async()=>{
          setEditingCable(prev=>({...prev,__aiLoading:true}));
          try{
            const res=await fetch(API+'/cable-journal/'+cb.id+'/ai-suggest',{method:'POST'});
            if(!res.ok){const e=await res.json().catch(()=>({}));throw new Error(e.detail||('HTTP '+res.status));}
            const d=await res.json();
            setEditingCable(prev=>({...prev,normatives:d.normatives||prev.normatives,aiFilled:true,__aiLoading:false}));
            setCableJournal(prev=>prev.map(x=>x.id===cb.id?{...x,normatives:d.normatives||x.normatives,aiFilled:true}:x));
          }catch(e){
            alert('Не получилось получить ответ от AI: '+e.message);
            setEditingCable(prev=>({...prev,__aiLoading:false}));
          }
        };
        const saveCable=async()=>{
          const body={
            drumNumber:cb.drumNumber||'',
            manufacturer:cb.manufacturer||'',
            certificateNumber:cb.certificateNumber||'',
            passportNumber:cb.passportNumber||'',
            insulationBefore:Number(cb.insulationBefore)||0,
            insulationAfter:Number(cb.insulationAfter)||0,
            lengthInstalled:Number(cb.lengthInstalled)||0,
            installationLocation:cb.installationLocation||'',
            installationMethod:cb.installationMethod||'',
            installedAt:cb.installedAt||'',
            responsibleItr:cb.responsibleItr||'',
            normatives:cb.normatives||'',
          };
          await fetch(API+'/cable-journal/'+cb.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
          setCableJournal(prev=>prev.map(x=>x.id===cb.id?{...x,...body,aiFilled:false}:x));
          setEditingCable(null);
        };
        return(<div onClick={()=>setEditingCable(null)} style={{position:'fixed',inset:0,backgroundColor:'rgba(0,0,0,0.55)',zIndex:1600,display:'flex',alignItems:'center',justifyContent:'center',padding:'20px'}}>
          <div onClick={e=>e.stopPropagation()} style={{...card,padding:0,width:'min(900px,100%)',maxHeight:'92vh',display:'flex',flexDirection:'column',overflow:'hidden'}}>
            <div style={{padding:'16px 20px',borderBottom:'1.5px solid '+C.border,backgroundColor:C.bg,display:'flex',justifyContent:'space-between',alignItems:'center',flexWrap:'wrap',gap:'8px'}}>
              <div>
                <b style={{color:C.text,fontSize:'16px',display:'block'}}>⚡ Запись журнала кабельной продукции</b>
                <span style={{fontSize:'12px',color:C.textSec}}>{(cb.cableBrand||'—')+' · '+(cb.crossSection?cb.crossSection+' мм² × '+(cb.coresCount||'?')+' жил':'—')+' · '+(cb.lengthReceived||0)+' м'}</span>
              </div>
              <div style={{display:'flex',alignItems:'center',gap:'10px'}}>
                <span style={{padding:'4px 10px',borderRadius:'12px',fontSize:'12px',fontWeight:'600',backgroundColor:cb.installedAt?C.successLight:C.warningLight,color:cb.installedAt?C.success:C.warning}}>{cb.installedAt?'Проложен':'На складе'}</span>
                <button onClick={()=>setEditingCable(null)} style={{...btnG,padding:'5px 10px'}}><X size={14}/></button>
              </div>
            </div>
            <div style={{flex:1,overflowY:'auto',padding:'18px 20px'}}>
              {cb.aiFilled&&(<div style={{marginBottom:'14px',padding:'10px 12px',backgroundColor:'#d1fae5',border:'1.5px solid #10b981',borderRadius:'10px',display:'flex',alignItems:'center',gap:'10px'}}><span style={{fontSize:'20px'}}>🤖</span><span style={{fontSize:'12px',color:C.text,lineHeight:1.4}}><b>Нормативы и мин. R подсказаны AI.</b> Проверь и сохрани — при правке поля метка снимется.</span></div>)}
              <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:'10px',marginBottom:'18px',padding:'12px',backgroundColor:C.bg,borderRadius:'10px',border:'1.5px solid '+C.border}}>
                <div><p style={labelStyle}>Марка кабеля</p><b style={{fontSize:'13px',color:C.text}}>{cb.cableBrand||'—'}</b></div>
                <div><p style={labelStyle}>Сечение жилы</p><b style={{fontSize:'13px',color:C.text}}>{cb.crossSection?cb.crossSection+' мм²':'—'}</b></div>
                <div><p style={labelStyle}>Кол-во жил</p><b style={{fontSize:'13px',color:C.text}}>{cb.coresCount||'—'}</b></div>
                <div><p style={labelStyle}>Длина с барабана</p><b style={{fontSize:'13px',color:C.text}}>{(cb.lengthReceived||0)+' м'}</b></div>
                <div><p style={labelStyle}>Поставщик</p><b style={{fontSize:'13px',color:C.text}}>{cb.supplier||'—'}</b></div>
                <div><p style={labelStyle}>Дата приёмки</p><b style={{fontSize:'13px',color:C.text}}>{cb.receivedAt||'—'}</b></div>
              </div>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px',marginBottom:'14px'}}>
                <div><label style={labelStyle}>№ барабана / бухты</label><input value={cb.drumNumber||''} onChange={e=>upd('drumNumber',e.target.value)} placeholder="напр. барабан №47" style={inp}/></div>
                <div><label style={labelStyle}>Изготовитель</label><input value={cb.manufacturer||''} onChange={e=>upd('manufacturer',e.target.value)} placeholder="напр. Камкабель, Севкабель" style={inp}/></div>
              </div>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px',marginBottom:'14px'}}>
                <div><label style={labelStyle}>Сертификат соответствия №</label><input value={cb.certificateNumber||''} onChange={e=>upd('certificateNumber',e.target.value)} style={inp}/></div>
                <div><label style={labelStyle}>Паспорт качества №</label><input value={cb.passportNumber||''} onChange={e=>upd('passportNumber',e.target.value)} style={inp}/></div>
              </div>
              <div style={{padding:'12px',backgroundColor:C.bg,borderRadius:'10px',border:'1.5px solid '+C.border,marginBottom:'14px'}}>
                <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'10px'}}>🔌 Замеры сопротивления изоляции (мегаомметр)</b>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                  <div><label style={labelStyle}>R изоляции ДО прокладки, МΩ</label><input type="number" step="0.1" value={cb.insulationBefore||''} onChange={e=>upd('insulationBefore',e.target.value)} placeholder="напр. 500" style={inp}/></div>
                  <div><label style={labelStyle}>R изоляции ПОСЛЕ прокладки, МΩ</label><input type="number" step="0.1" value={cb.insulationAfter||''} onChange={e=>upd('insulationAfter',e.target.value)} placeholder="напр. 480" style={inp}/></div>
                </div>
                <p style={{color:C.textMuted,fontSize:'11px',margin:'8px 0 0'}}>По ПУЭ для большинства силовых кабелей мин. R изоляции = 0.5 МΩ. AI-подсказка ниже даст точное значение для этой марки.</p>
              </div>
              <div style={{padding:'12px',backgroundColor:C.bg,borderRadius:'10px',border:'1.5px solid '+C.border,marginBottom:'14px'}}>
                <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'10px'}}>🔧 Монтаж</b>
                <div style={sectionStyle}><label style={labelStyle}>Место прокладки (объект, этаж, помещение)</label><textarea value={cb.installationLocation||''} onChange={e=>upd('installationLocation',e.target.value)} placeholder="напр. этаж 2, эл.щитовая → коридор → квартиры 21-25" style={{...inp,minHeight:'50px',resize:'vertical'}}/></div>
                <div style={{display:'grid',gridTemplateColumns:'2fr 1fr 1fr',gap:'10px'}}>
                  <div><label style={labelStyle}>Способ прокладки</label><select value={cb.installationMethod||''} onChange={e=>upd('installationMethod',e.target.value)} style={inp}><option value="">— не указано —</option><option>Открыто</option><option>В кабель-канале</option><option>В трубе</option><option>По лотку</option><option>На скобах</option><option>В земле</option><option>Под штукатуркой</option></select></div>
                  <div><label style={labelStyle}>Длина проложенная, м</label><input type="number" step="0.1" value={cb.lengthInstalled||''} onChange={e=>upd('lengthInstalled',e.target.value)} style={inp}/></div>
                  <div><label style={labelStyle}>Дата монтажа</label><input type="date" value={cb.installedAt||''} onChange={e=>upd('installedAt',e.target.value)} style={inp}/></div>
                </div>
              </div>
              <div style={sectionStyle}><label style={labelStyle}>Ответственный ИТР (электрик-инженер)</label><input list="cable-itr-list" value={cb.responsibleItr||''} onChange={e=>upd('responsibleItr',e.target.value)} placeholder="ФИО" style={inp}/><datalist id="cable-itr-list">{proraby.map(n=><option key={n} value={n}/>)}</datalist></div>
              <div style={sectionStyle}><label style={labelStyle}>Применимые нормативы (ГОСТ/СП/ПУЭ){cb.aiFilled?' 🤖':''}</label><textarea value={cb.normatives||''} onChange={e=>upd('normatives',e.target.value)} placeholder="Напр.: ПУЭ 7-е изд., ГОСТ Р 53769 (кабели силовые), СП 76.13330" style={{...inp,minHeight:'80px',resize:'vertical'}}/></div>
            </div>
            <div style={{padding:'14px 20px',borderTop:'1.5px solid '+C.border,backgroundColor:C.bg,display:'flex',gap:'8px',justifyContent:'space-between',flexWrap:'wrap'}}>
              <button onClick={()=>showPreview(buildCableJournalContent([cb],cb.projectName,cb.receivedAt,cb.installedAt||cb.receivedAt),'Запись кабеля')} style={btnB}><Eye size={14}/>🖨️ Печать</button>
              <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
                <button disabled={!!cb.__aiLoading} onClick={aiSuggest} style={{...btnB,backgroundColor:'#10b981',opacity:cb.__aiLoading?0.6:1,cursor:cb.__aiLoading?'not-allowed':'pointer'}}><Bot size={14}/>{cb.__aiLoading?'AI работает…':'🤖 AI-подсказка нормативов и R изоляции'}</button>
                <button onClick={()=>setEditingCable(null)} style={btnG}>Отмена</button>
                <button onClick={saveCable} style={btnO}><Check size={14}/>Сохранить</button>
              </div>
            </div>
          </div>
        </div>);
      })()}
      {showQRModal&&(<div onClick={()=>setShowQRModal(null)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.7)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:2000,cursor:'pointer'}}><div style={{backgroundColor:'white',padding:'30px',borderRadius:'16px',textAlign:'center'}} onClick={e=>e.stopPropagation()}><h3 style={{color:C.text,marginBottom:'16px'}}>{showQRModal.title}</h3><img src={generateQR(showQRModal.data)} alt="QR" style={{width:'200px',height:'200px'}}/><p style={{color:C.textSec,fontSize:'12px',marginTop:'12px'}}>Сканируйте для быстрого доступа</p><button onClick={()=>setShowQRModal(null)} style={{...btnG,marginTop:'12px'}}>Закрыть</button></div></div>)}
      {rejectingEntry&&(<div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:1500}}><div style={{...card,padding:'30px',width:'400px'}}><h3 style={{color:C.text,marginBottom:'15px',fontWeight:'700'}}>Причина отклонения</h3><textarea placeholder="Укажите причину..." value={rejectComment} onChange={e=>setRejectComment(e.target.value)} style={{...inp,height:'100px',resize:'vertical'}}/><div style={{display:'flex',gap:'10px'}}><button onClick={()=>rejectJ(rejectingEntry,rejectComment)} style={btnR}><X size={14}/>Отклонить</button><button onClick={()=>{setRejectingEntry(null);setRejectComment('');}} style={btnG}>Отмена</button></div></div></div>)}
      {showIssueToolModal&&(<div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:1500}}><div style={{...card,padding:'30px',width:'400px'}}><h3 style={{color:C.text,marginBottom:'15px',fontWeight:'700'}}>{'Выдать: '+showIssueToolModal.name}</h3><select value={issueToolData.masterName} onChange={e=>setIssueToolData({...issueToolData,masterName:e.target.value})} style={inp}><option value="">Выберите мастера</option>{masterProfiles.map(mp=><option key={mp.id} value={mp.fullName}>{mp.fullName}</option>)}</select><select value={issueToolData.project} onChange={e=>setIssueToolData({...issueToolData,project:e.target.value})} style={inp}><option value="">Выберите объект</option>{projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}</select><select value={issueToolData.issueType} onChange={e=>setIssueToolData({...issueToolData,issueType:e.target.value})} style={inp}><option value="Временно">Временно</option><option value="В счёт зарплаты">В счёт зарплаты</option></select><div style={{display:'flex',gap:'10px'}}><button onClick={()=>issueTool(showIssueToolModal)} style={btnO}><Check size={14}/>Выдать</button><button onClick={()=>setShowIssueToolModal(null)} style={btnG}>Отмена</button></div></div></div>)}
      {showReturnToolModal&&(<div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:1500}}><div style={{...card,padding:'30px',width:'400px'}}><h3 style={{color:C.text,marginBottom:'15px',fontWeight:'700'}}>{'Вернуть: '+showReturnToolModal.name}</h3><p style={{color:C.textSec,fontSize:'13px',marginBottom:'15px'}}>{'От: '+showReturnToolModal.masterName}</p><select value={returnToolCondition} onChange={e=>setReturnToolCondition(e.target.value)} style={inp}><option value="Исправен">Исправен</option><option value="Требует ремонта">Требует ремонта</option><option value="Сломан">Сломан</option><option value="Утерян">Утерян</option></select><div style={{display:'flex',gap:'10px'}}><button onClick={()=>returnTool(showReturnToolModal)} style={btnGr}><Check size={14}/>Вернуть</button><button onClick={()=>setShowReturnToolModal(null)} style={btnG}>Отмена</button></div></div></div>)}
      {showPayActModal&&(<div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:1500}}><div style={{...card,padding:'30px',width:'420px'}}><h3 style={{color:C.text,marginBottom:'5px',fontWeight:'700'}}>Добавить оплату</h3><p style={{color:C.textSec,fontSize:'13px',marginBottom:'15px'}}>{'Акт №'+showPayActModal.id+' · '+showPayActModal.masterName}</p><div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}><input placeholder="Сумма *" type="number" value={newPayment.amount} onChange={e=>setNewPayment({...newPayment,amount:e.target.value})} style={{...inp,marginBottom:0}}/><select value={newPayment.paymentType} onChange={e=>setNewPayment({...newPayment,paymentType:e.target.value})} style={{...inp,marginBottom:0}}>{PAYMENT_TYPES.map(t=><option key={t} value={t}>{t}</option>)}</select><select value={newPayment.paidBy} onChange={e=>setNewPayment({...newPayment,paidBy:e.target.value})} style={{...inp,marginBottom:0}}><option value="">Кто выплатил</option>{financeUsers.map(u=><option key={u.id} value={u.name}>{u.name+' ('+ROLE_LABELS[u.role]+')'}</option>)}<option value="__manual__">Ввести вручную</option></select><input type="date" value={newPayment.date} onChange={e=>setNewPayment({...newPayment,date:e.target.value})} style={{...inp,marginBottom:0}}/></div>{newPayment.paidBy==='__manual__'&&<input placeholder="ФИО выплатившего" value={newPayment.paidByManual||''} onChange={e=>setNewPayment({...newPayment,paidByManual:e.target.value})} style={{...inp,marginTop:'10px'}}/>}<input placeholder="Примечание" value={newPayment.notes} onChange={e=>setNewPayment({...newPayment,notes:e.target.value})} style={{...inp,marginTop:'8px'}}/><div style={{display:'flex',gap:'10px'}}><button onClick={()=>saveActPayment(showPayActModal.id)} style={btnO}><Check size={14}/>Записать</button><button onClick={()=>setShowPayActModal(null)} style={btnG}>Отмена</button></div><div style={{marginTop:'15px',borderTop:'1.5px solid '+C.border,paddingTop:'12px'}}><b style={{color:C.text,fontSize:'13px'}}>История оплат:</b>{actPayments.filter(p=>p.actId===showPayActModal.id).map(p=>(<div key={p.id} style={{display:'flex',justifyContent:'space-between',padding:'5px 0',borderBottom:'1px solid '+C.border,fontSize:'12px'}}><span style={{color:C.textSec}}>{p.date+' · '+p.paymentType+' · '+p.paidBy}</span><b style={{color:C.success}}>{p.amount.toLocaleString()+' ₽'}</b></div>))}{actPayments.filter(p=>p.actId===showPayActModal.id).length===0&&<p style={{color:C.textMuted,fontSize:'12px',margin:'6px 0'}}>Оплат нет</p>}</div></div></div>)}
      {showAiAssistant&&(<div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',display:'flex',justifyContent:'flex-end',zIndex:1500}}><div style={{width:'420px',backgroundColor:C.bgWhite,display:'flex',flexDirection:'column',boxShadow:'-4px 0 30px rgba(0,0,0,0.15)'}}><div style={{padding:'16px 20px',borderBottom:'1.5px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center',backgroundColor:C.sidebar}}><div><b style={{color:'white',fontSize:'15px'}}>🤖 ИИ Помощник</b><p style={{color:'rgba(255,255,255,0.5)',margin:'2px 0',fontSize:'12px'}}>Знает нормы СНиП, расценки, материалы</p></div><button onClick={()=>setShowAiAssistant(false)} style={{backgroundColor:'transparent',border:'none',cursor:'pointer',color:'white'}}><X size={20}/></button></div><div style={{flex:1,overflowY:'auto',padding:'16px',display:'flex',flexDirection:'column',gap:'12px'}}>{aiChat.length===0&&(<div style={{textAlign:'center',padding:'30px',color:C.textMuted}}><div style={{fontSize:'40px',marginBottom:'10px'}}>🏗️</div><b style={{color:C.text}}>Спросите меня!</b><div style={{display:'flex',flexDirection:'column',gap:'8px',marginTop:'16px'}}>{['Сколько цемента нужно для стяжки 50м2?','Нормы расхода штукатурки на 1м2?','Как рассчитать количество кирпича?','Какие СНиП для жилых домов?'].map(q=>(<button key={q} onClick={()=>setAiMessage(q)} style={{...btnG,fontSize:'12px',textAlign:'left',justifyContent:'flex-start'}}>{q}</button>))}</div></div>)}{aiChat.map((msg,i)=>(<div key={i} style={{display:'flex',justifyContent:msg.role==='user'?'flex-end':'flex-start'}}><div style={{maxWidth:'85%',backgroundColor:msg.role==='user'?C.accent:C.bg,color:msg.role==='user'?'white':C.text,padding:'10px 14px',borderRadius:msg.role==='user'?'16px 16px 4px 16px':'16px 16px 16px 4px',border:'1.5px solid '+(msg.role==='user'?C.accent:C.border),fontSize:'13px',lineHeight:'1.5'}}>{msg.content}<div style={{fontSize:'10px',color:msg.role==='user'?'rgba(255,255,255,0.6)':C.textMuted,marginTop:'4px',textAlign:'right'}}>{msg.time}</div></div></div>))}{aiLoading&&<div style={{display:'flex',justifyContent:'flex-start'}}><div style={{backgroundColor:C.bg,padding:'10px 14px',borderRadius:'16px',border:'1.5px solid '+C.border,color:C.textSec,fontSize:'13px'}}>Думаю...</div></div>}<div ref={chatEndRef}/></div><div style={{padding:'12px',borderTop:'1.5px solid '+C.border}}><div style={{display:'flex',gap:'8px'}}><input placeholder="Задайте вопрос..." value={aiMessage} onChange={e=>setAiMessage(e.target.value)} onKeyDown={e=>e.key==='Enter'&&!aiLoading&&sendAiMessage()} style={{...inp,marginBottom:0,flex:1,fontSize:'13px'}} disabled={aiLoading}/><button onClick={sendAiMessage} disabled={aiLoading} style={btnO}>➤</button></div></div></div></div>)}

      <div style={{position:'fixed',top:0,left:0,width:'16px',height:'100vh',zIndex:200}} onMouseEnter={()=>setSidebarVisible(true)}/>
      <div ref={sidebarRef} onMouseLeave={()=>setSidebarVisible(false)} style={{position:'fixed',top:0,left:0,height:'100vh',width:'240px',backgroundColor:C.sidebar,color:'white',zIndex:300,transform:sidebarVisible?'translateX(0)':'translateX(-100%)',transition:'transform 0.25s cubic-bezier(0.4,0,0.2,1)',display:'flex',flexDirection:'column',boxShadow:sidebarVisible?'4px 0 30px rgba(0,0,0,0.15)':'none'}}>
        <div style={{padding:'22px 20px',borderBottom:'1px solid rgba(255,255,255,0.08)'}}><div style={{display:'flex',alignItems:'center',gap:'12px'}}><div style={{width:'40px',height:'40px',borderRadius:'12px',background:'linear-gradient(135deg,#f97316,#ea580c)',display:'flex',alignItems:'center',justifyContent:'center',fontSize:'20px',flexShrink:0}}>🏗️</div><div><h3 style={{margin:0,color:'white',fontSize:'18px',fontWeight:'800'}}>СтройКа</h3><p style={{margin:0,color:'rgba(255,255,255,0.4)',fontSize:'11px'}}>ERP система</p></div></div></div>
        <div style={{padding:'14px',borderBottom:'1px solid rgba(255,255,255,0.08)'}}><div style={{backgroundColor:'rgba(255,255,255,0.06)',borderRadius:'10px',padding:'12px',display:'flex',alignItems:'center',gap:'10px'}}><div style={{width:'36px',height:'36px',borderRadius:'10px',backgroundColor:roleColor(user.role),display:'flex',alignItems:'center',justifyContent:'center',fontSize:'14px',color:'white',fontWeight:'800',flexShrink:0}}>{user.name.charAt(0)}</div><div style={{overflow:'hidden'}}><div style={{fontSize:'13px',fontWeight:'600',color:'white',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{user.name}</div><div style={{fontSize:'11px',color:'rgba(255,255,255,0.4)',marginTop:'1px'}}>{ROLE_LABELS[user.role]||user.role}</div></div></div></div>
        <div style={{padding:'10px',flex:1,overflowY:'auto'}}>
          {menuItems.map(item=>(<div key={item.id} onClick={()=>navigateTo(item.id)} style={{display:'flex',alignItems:'center',gap:'10px',padding:'10px 12px',borderRadius:'8px',cursor:'pointer',marginBottom:'2px',backgroundColor:activePage===item.id?'rgba(249,115,22,0.15)':'transparent',border:activePage===item.id?'1px solid rgba(249,115,22,0.3)':'1px solid transparent',transition:'all 0.15s'}}><span style={{color:activePage===item.id?C.accent:'rgba(255,255,255,0.5)',flexShrink:0}}>{item.icon}</span><span style={{fontSize:'13px',fontWeight:activePage===item.id?'600':'400',color:activePage===item.id?'white':'rgba(255,255,255,0.6)',flex:1}}>{item.label}</span>{activePage===item.id&&<ChevronRight size={14} color={C.accent}/>}</div>))}
        </div>
        <div style={{padding:'10px',borderTop:'1px solid rgba(255,255,255,0.08)'}}>
          <div onClick={()=>setUser(null)} style={{display:'flex',alignItems:'center',gap:'10px',padding:'10px 12px',borderRadius:'8px',cursor:'pointer',backgroundColor:'rgba(239,68,68,0.1)',border:'1px solid rgba(239,68,68,0.2)'}}><LogOut size={18} color='#ef4444'/><span style={{fontSize:'13px',color:'#ef4444',fontWeight:'500'}}>Выйти</span></div>
        </div>
      </div>

      <div style={{flex:1,display:'flex',flexDirection:'column',overflow:'hidden',width:'100%'}}>
        <div style={{backgroundColor:C.bgWhite,padding:'12px 24px',borderBottom:'1.5px solid '+C.border,display:activePage==='dashboard'?'none':'flex',alignItems:'center',gap:'15px',flexShrink:0,boxShadow:'0 1px 3px rgba(0,0,0,0.04)'}}>
          <div style={{width:'8px',height:'32px',borderRadius:'4px',background:'linear-gradient(135deg,#f97316,#ea580c)',flexShrink:0}}/>
          <h2 style={{margin:0,color:C.text,fontSize:'18px',fontWeight:'700',flex:1}}>{allMenuItems.find(m=>m.id===activePage)?.label||'СтройКа'}</h2>
          <div style={{flex:1,maxWidth:'320px',position:'relative'}}>
            <Search size={15} style={{position:'absolute',left:'10px',top:'50%',transform:'translateY(-50%)',color:C.textMuted}}/>
            <input placeholder="Поиск..." value={globalSearch} onChange={e=>{setGlobalSearch(e.target.value);setShowSearch(e.target.value.length>=2);}} onBlur={()=>setTimeout(()=>setShowSearch(false),200)} style={{...inp,marginBottom:0,paddingLeft:'32px',fontSize:'13px'}}/>
            {showSearch&&searchResults.length>0&&(<div style={{position:'absolute',top:'100%',left:0,right:0,backgroundColor:C.bgWhite,border:'1.5px solid '+C.border,borderRadius:'10px',boxShadow:'0 8px 25px rgba(0,0,0,0.1)',zIndex:1000,maxHeight:'280px',overflowY:'auto',marginTop:'4px'}}>{searchResults.map((r,i)=>(<div key={i} onClick={()=>{navigateTo(r.page);setGlobalSearch('');setShowSearch(false);}} style={{padding:'10px 15px',cursor:'pointer',borderBottom:'1px solid '+C.border,display:'flex',gap:'10px',alignItems:'center'}}><span style={{fontSize:'16px'}}>{r.icon}</span><div><b style={{fontSize:'13px',color:C.text}}>{r.title}</b><p style={{color:C.textSec,margin:0,fontSize:'11px'}}>{r.subtitle}</p></div></div>))}</div>)}
          </div>
          <div ref={notifRef} style={{position:'relative'}}>
            <button onClick={()=>setShowNotifications(!showNotifications)} style={{position:'relative',padding:'8px',backgroundColor:C.bgGray,border:'1.5px solid '+C.border,borderRadius:'10px',cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center'}}>
              <Bell size={18} color={C.textSec}/>
              {unreadNotifications>0&&<span style={{position:'absolute',top:'-4px',right:'-4px',backgroundColor:C.danger,color:'white',borderRadius:'50%',padding:'1px 5px',fontSize:'10px',fontWeight:'700'}}>{unreadNotifications}</span>}
            </button>
            {showNotifications&&(<div style={{position:'absolute',top:'calc(100% + 8px)',right:0,width:'360px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border,borderRadius:'14px',boxShadow:'0 8px 40px rgba(0,0,0,0.12)',zIndex:1000,maxHeight:'420px',overflowY:'auto'}}><div style={{padding:'14px 18px',borderBottom:'1.5px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center'}}><b style={{color:C.text,fontSize:'14px'}}>Уведомления</b><button onClick={()=>{const u=myNotifications(notifications).map(n=>({...n,read:true}));setNotifications(u);localStorage.setItem('notifications',JSON.stringify(u));}} style={{...btnG,fontSize:'11px',padding:'3px 10px'}}>Прочитать все</button></div>{myNotifications(notifications).length===0&&<p style={{padding:'20px',textAlign:'center',color:C.textMuted}}>Нет уведомлений</p>}
                  <div style={{padding:'12px 18px',borderTop:'1.5px solid '+C.border,backgroundColor:C.bg}}>
                    <p style={{fontSize:'11px',color:C.textSec,margin:'0 0 8px'}}>📱 Уведомления в ВКонтакте:</p>
                    {user.vkId ? <span style={{fontSize:'12px',color:C.success}}>✅ ВК подключён (ID: {user.vkId})</span> :
                    <button onClick={()=>{const vkId=prompt('Введите ваш ID ВКонтакте (число из vk.com/id12345):');if(vkId&&Number(vkId)){fetch(API+'/vk-connect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({vkId:Number(vkId),email:user.email})}).then(()=>{const updated={...user,vkId:Number(vkId)};setUser(updated);localStorage.setItem('user',JSON.stringify(updated));alert('ВК подключён!');});}}} style={{...btnO,fontSize:'11px',padding:'5px 12px',width:'100%',justifyContent:'center'}}>Подключить ВК</button>}
                  </div>{myNotifications(notifications).map(n=>(<div key={n.id} onClick={()=>{navigateTo(getNotifPage(n.type));setShowNotifications(false);const u=notifications.map(x=>x.id===n.id?{...x,read:true}:x);setNotifications(u);localStorage.setItem('notifications',JSON.stringify(u));}} style={{padding:'12px 18px',borderBottom:'1px solid '+C.border,backgroundColor:n.read?'transparent':C.accentLight,cursor:'pointer'}}><p style={{margin:0,fontSize:'13px',color:C.text}}>{n.text}</p><p style={{margin:'3px 0 0',fontSize:'11px',color:C.textMuted}}>{n.time}</p></div>))}</div>)}
          </div>
        </div>
        <div style={{flex:1,overflowY:'auto',backgroundColor:activePage==='dashboard'?'#0b1120':C.bg,padding:activePage==='dashboard'?'0':'24px'}}>
          {activePage==='dashboard'&&(()=>{
            const risks=[...lowStock.map(m=>'⚠️ Мало: '+m.name),...lowMainStock.map(m=>'⚠️ Склад: '+m.name)].slice(0,4);
            const _planDoneOf=projectPlanDone; const _projProgress=projectRealProgress;
            const avgProg=projects.length?Math.round(projects.reduce((s,p)=>s+_projProgress(p),0)/projects.length):0;
            const totalDone=projects.reduce((s,p)=>s+_planDoneOf(p).done,0);
            return(
            <div style={{minHeight:'100%',padding:'28px',background:'radial-gradient(circle at 15% 0%,rgba(249,115,22,.15),transparent 32%),linear-gradient(135deg,#0b1120 0%,#111827 100%)',color:'#f8fafc'}}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'28px',flexWrap:'wrap',gap:'12px'}}>
                <div>
                  <h1 style={{fontSize:'28px',fontWeight:'800',letterSpacing:'-.04em',margin:0,color:'#f8fafc'}}>Центр управления стройкой</h1>
                  <p style={{color:'#94a3b8',margin:'6px 0 0',fontSize:'14px'}}>Контроль объектов, финансов, склада и рисков</p>
                </div>
                <div style={{display:'flex',gap:'10px',alignItems:'center'}}>
                  <button onClick={()=>setShowChatPanel(s=>!s)} style={{padding:'8px 10px',background:'rgba(30,41,59,.78)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'12px',cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center'}}><MessageSquare size={18} color='#94a3b8'/></button>
                  <button onClick={()=>setShowAiAssistant(!showAiAssistant)} style={{padding:'8px 10px',background:'rgba(30,41,59,.78)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'12px',cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center'}}><Bot size={18} color='#94a3b8'/></button>
                  <div ref={notifRef} style={{position:'relative'}}>
                    <button onClick={()=>setShowNotifications(!showNotifications)} style={{position:'relative',padding:'8px 10px',background:'rgba(30,41,59,.78)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'12px',cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center'}}>
                      <Bell size={18} color='#94a3b8'/>
                      {unreadNotifications>0&&<span style={{position:'absolute',top:'-4px',right:'-4px',backgroundColor:'#ef4444',color:'white',borderRadius:'50%',padding:'1px 5px',fontSize:'10px',fontWeight:'700'}}>{unreadNotifications}</span>}
                    </button>
                  </div>
                  <button onClick={()=>setShowQuickActions(true)} style={{background:'linear-gradient(135deg,#f97316,#ea580c)',border:'none',borderRadius:'14px',padding:'10px 18px',color:'white',fontWeight:'700',cursor:'pointer',fontSize:'13px',boxShadow:'0 8px 24px rgba(234,88,12,.35)'}}>⚡ Быстро</button>
                </div>
              </div>
              <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:'16px',marginBottom:'20px'}}>
                {[{label:'Объекты',value:projects.filter(p=>p.status!=='Завершён').length,sub:'активных проектов',color:'#fdba74',bg:'rgba(234,88,12,.14)',border:'rgba(234,88,12,.32)'},
                  {label:'Прогресс',value:avgProg+'%',sub:'среднее по сметам',color:'#86efac',bg:'rgba(34,197,94,.12)',border:'rgba(34,197,94,.28)'},
                  {label:'Выполнено',value:totalDone>=1000000?(totalDone/1000000).toFixed(1)+' млн':Math.round(totalDone/1000)+' тыс',sub:'по сметам ₽',color:'#bef264',bg:'rgba(132,204,22,.12)',border:'rgba(132,204,22,.28)'},
                  {label:'Бюджет',value:(()=>{const t=projects.reduce((s,p)=>s+Number(p.budget||0),0);return t>=1000000?Math.round(t/1000000)+' млн':Math.round(t/1000)+' тыс';})(),sub:'общий бюджет ₽',color:'#fca5a5',bg:'rgba(239,68,68,.12)',border:'rgba(239,68,68,.28)'}
                ].map((k,i)=>(
                  <div key={i} style={{background:'rgba(17,24,39,.88)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'22px',padding:'20px',backdropFilter:'blur(24px)',boxShadow:'0 24px 80px rgba(0,0,0,.35)'}}>
                    <span style={{display:'inline-flex',borderRadius:'999px',padding:'5px 10px',fontSize:'11px',fontWeight:'700',background:k.bg,color:k.color,border:'1px solid '+k.border}}>{k.label}</span>
                    <div style={{fontSize:'34px',fontWeight:'800',letterSpacing:'-.04em',margin:'10px 0 4px',color:'#f8fafc'}}>{k.value}</div>
                    <div style={{color:'#94a3b8',fontSize:'13px'}}>{k.sub}</div>
                  </div>
                ))}
              </div>
              <div style={{display:'grid',gridTemplateColumns:'1.3fr 0.7fr',gap:'16px'}}>
                <div style={{background:'rgba(17,24,39,.88)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'22px',padding:'20px',backdropFilter:'blur(24px)'}}>
                  <h2 style={{margin:'0 0 16px',fontSize:'18px',color:'#f8fafc'}}>Ключевые объекты</h2>
                  {projects.slice(0,5).map(p=>{const pd=_planDoneOf(p);const realProg=_projProgress(p);return(
                    <div key={p.id} onClick={()=>{setExpandedProject(p.id);setActivePage('projects');}} style={{padding:'16px',borderRadius:'18px',background:'rgba(30,41,59,.62)',border:'1px solid rgba(148,163,184,.18)',marginBottom:'10px',cursor:'pointer'}}>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'12px'}}>
                        <div><div style={{fontWeight:'800',fontSize:'15px',color:'#f8fafc'}}>{p.name}</div><div style={{color:'#94a3b8',fontSize:'12px',marginTop:'3px'}}>{p.client||'Без заказчика'} · {p.status}</div></div>
                        <span style={{display:'inline-flex',borderRadius:'999px',padding:'4px 10px',fontSize:'11px',fontWeight:'700',background:'rgba(234,88,12,.14)',color:'#fdba74',border:'1px solid rgba(234,88,12,.32)',whiteSpace:'nowrap'}}>{realProg}%</span>
                      </div>
                      <div style={{height:'6px',background:'rgba(148,163,184,.16)',borderRadius:'999px',overflow:'hidden',margin:'10px 0'}}>
                        <div style={{height:'100%',borderRadius:'999px',background:'linear-gradient(90deg,#f97316,#22c55e)',width:`${realProg}%`}}/>
                      </div>
                      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:'8px'}}>
                        <div style={{background:'rgba(30,41,59,.6)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'12px',padding:'10px'}}><div style={{color:'#94a3b8',fontSize:'11px'}}>Бюджет</div><div style={{fontWeight:'700',color:'#f8fafc',fontSize:'13px',marginTop:'3px'}}>{(Number(p.budget||0)/1000).toFixed(0)+' тыс'}</div></div>
                        <div style={{background:'rgba(30,41,59,.6)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'12px',padding:'10px'}}><div style={{color:'#94a3b8',fontSize:'11px'}}>Выполнено</div><div style={{fontWeight:'700',color:'#86efac',fontSize:'13px',marginTop:'3px'}}>{pd.done>0?(pd.done/1000).toFixed(0)+' тыс':'0'}</div></div>
                        <div style={{background:'rgba(30,41,59,.6)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'12px',padding:'10px'}}><div style={{color:'#94a3b8',fontSize:'11px'}}>Срок</div><div style={{fontWeight:'700',color:'#f8fafc',fontSize:'13px',marginTop:'3px'}}>{p.deadline||'—'}</div></div>
                      </div>
                      <div style={{marginTop:'10px',padding:'8px 12px',borderRadius:'12px',background:'rgba(234,88,12,.12)',border:'1px solid rgba(234,88,12,.24)',color:'#fed7aa',fontSize:'12px',fontWeight:'700'}}>{realProg<40?'⚠️ AI: низкий темп':realProg>80?'✅ AI: близко к сдаче':'🔵 AI: темп в норме'}</div>
                    </div>
                  );})}
                </div>
                <div style={{display:'flex',flexDirection:'column',gap:'16px'}}>
                  <div style={{background:'rgba(17,24,39,.88)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'22px',padding:'20px',backdropFilter:'blur(24px)'}}>
                    <h2 style={{margin:'0 0 12px',fontSize:'17px',color:'#f8fafc'}}>AI-инсайты</h2>
                    <div style={{borderRadius:'16px',padding:'14px',background:'linear-gradient(135deg,rgba(234,88,12,.16),rgba(30,41,59,.7))',border:'1px solid rgba(249,115,22,.28)',marginBottom:'12px'}}>
                      <div style={{fontWeight:'800',marginBottom:'6px',color:'#f8fafc',fontSize:'14px'}}>Construction Intelligence</div>
                      <div style={{color:'#cbd5e1',fontSize:'13px',lineHeight:'1.5'}}>Система анализирует склад, финансы и задачи.</div>
                    </div>
                    {risks.length>0?risks.map((r,i)=><div key={i} style={{padding:'10px 12px',borderRadius:'12px',background:'rgba(239,68,68,.10)',border:'1px solid rgba(239,68,68,.22)',color:'#fca5a5',fontSize:'12px',marginBottom:'8px'}}>{r}</div>):<div style={{color:'#94a3b8',fontSize:'13px',padding:'8px 0'}}>Критических рисков нет ✅</div>}
                  </div>
                  <div style={{background:'rgba(17,24,39,.88)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'22px',padding:'20px',backdropFilter:'blur(24px)'}}>
                    <h2 style={{margin:'0 0 12px',fontSize:'17px',color:'#f8fafc'}}>Сегодня</h2>
                    {activityLog.slice(0,5).map((a,i)=>(
                      <div key={i} style={{display:'flex',gap:'12px',padding:'10px 0',borderBottom:'1px solid rgba(148,163,184,.18)'}}>
                        <div style={{width:'10px',height:'10px',borderRadius:'50%',background:'#f97316',boxShadow:'0 0 14px rgba(249,115,22,.8)',marginTop:'4px',flexShrink:0}}/>
                        <div><div style={{fontSize:'13px',fontWeight:'700',color:'#f8fafc'}}>{a.action}</div><div style={{color:'#94a3b8',fontSize:'11px',marginTop:'2px'}}>{a.user+' · '+a.time}</div></div>
                      </div>
                    ))}
                    {activityLog.length===0&&<div style={{color:'#94a3b8',fontSize:'13px'}}>Пока нет активности</div>}
                  </div>
                </div>
              </div>
              <div style={{height:'100px'}}/>
            </div>
            );
          })()}
          {activePage==='projects'&&(<div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px',flexWrap:'wrap',gap:'10px'}}>
              <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
                <button onClick={()=>{setShowForm(showForm===true?false:true);setEditingItem(null);setNewProject({name:'',client:'',status:'Планирование',budget:'',deadline:'',progress:0,tasks:[],pricelistId:null});}} style={btnO}><Plus size={14}/>Новый проект</button>
                <button onClick={()=>setShowArchive(!showArchive)} style={btnG}><Archive size={14}/>{showArchive?'Активные':'Архив'}</button>
              </div>
            </div>
            {showForm===true&&(<div style={{...card,padding:'20px',marginBottom:'20px'}}>
              <h3 style={{color:C.text,marginBottom:'15px',fontWeight:'700'}}>{editingItem?'Редактировать проект':'Новый проект'}</h3>
              <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(200px,1fr))',gap:'10px'}}>
                <input placeholder="Название *" value={newProject.name} onChange={e=>setNewProject({...newProject,name:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder="Заказчик (название)" value={newProject.client} onChange={e=>setNewProject({...newProject,client:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder="Email заказчика (для доступа в кабинет)" value={newProject.clientEmail||''} onChange={e=>setNewProject({...newProject,clientEmail:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder="Пароль заказчика" value={newProject.clientPassword||''} onChange={e=>setNewProject({...newProject,clientPassword:e.target.value})} style={{...inp,marginBottom:0}}/>
                <select value={newProject.status} onChange={e=>setNewProject({...newProject,status:e.target.value})} style={{...inp,marginBottom:0}}>{['Планирование','В работе','Завершён','Заморожен'].map(s=><option key={s}>{s}</option>)}</select>
                <input placeholder="Бюджет" type="number" value={newProject.budget} onChange={e=>setNewProject({...newProject,budget:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder="Дедлайн" type="date" value={newProject.deadline} onChange={e=>setNewProject({...newProject,deadline:e.target.value})} style={{...inp,marginBottom:0}}/>
                <select value={newProject.pricelistId||''} onChange={e=>setNewProject({...newProject,pricelistId:e.target.value?Number(e.target.value):null})} style={{...inp,marginBottom:0}}><option value="">Прайс-лист</option>{pricelists.map(pl=><option key={pl.id} value={pl.id}>{pl.name}</option>)}</select>
                <input placeholder="Этажей (например: 3)" type="number" value={newProject.floors||''} onChange={e=>setNewProject({...newProject,floors:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder="Литеры (например: А,Б,В)" value={newProject.liters||''} onChange={e=>setNewProject({...newProject,liters:e.target.value})} style={{...inp,marginBottom:0}}/>
              </div>
              <div style={{display:'flex',gap:'10px',marginTop:'15px'}}><button onClick={saveProject} style={btnO}><Check size={14}/>{editingItem?'Сохранить':'Создать'}</button><button onClick={()=>{setShowForm(false);setEditingItem(null);}} style={btnG}><X size={14}/>Отмена</button></div>
            </div>)}
            {(showArchive?archivedProjects:projects).map(p=>{
              const cat=expByCategory(p.name);const total=Object.values(cat).reduce((s,v)=>s+v,0);
              const isOpen=expandedProject===p.id;
              const statusColors={'Планирование':[C.info,C.infoLight,C.infoBorder],'В работе':[C.success,C.successLight,C.successBorder],'Завершён':[C.textSec,C.bgGray,C.border],'Заморожен':[C.warning,C.warningLight,C.warningBorder]};
              const sc=statusColors[p.status]||statusColors['Планирование'];
              return(<div key={p.id} style={{...card,marginBottom:'12px',overflow:'visible'}}>
                <div style={{padding:'14px 16px',cursor:'pointer'}} onClick={async()=>{if(isOpen){setExpandedProject(null);}else{setExpandedProject(p.id);setActiveProjectTab('Общее');if(user&&['директор','зам_директора','бухгалтер','прораб'].includes(user.role)&&!projectAiSummaries[p.name]){try{const r=await fetch(API+'/project-ai-summary/'+encodeURIComponent(p.name));const d=await r.json();if(d&&d.exists)setProjectAiSummaries(prev=>({...prev,[p.name]:d}));}catch(e){}}}}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
                    <div style={{flex:1}}>
                      <div style={{display:'flex',alignItems:'center',gap:'10px',marginBottom:'6px'}}>
                        <b style={{fontSize:'15px',color:C.text}}>{p.name}</b>
                        <span style={badge(sc[0],sc[1],sc[2])}>{p.status}</span>
                      </div>
                      <div style={{display:'flex',gap:'15px',flexWrap:'wrap'}}>
                        <span style={{fontSize:'12px',color:C.textSec}}>{'👤 '+p.client}</span>{p.floors>1&&<span style={{fontSize:'12px',color:C.textSec}}>{'🏢 '+p.floors+' эт.'}</span>}{p.liters&&<span style={{fontSize:'12px',color:C.textSec}}>{'🔤 Лит. '+p.liters}</span>}
                        {p.deadline&&<span style={{fontSize:'12px',color:C.textSec}}>{'📅 '+p.deadline}</span>}
                        {isFinanceRole()&&<span style={{fontSize:'12px',color:C.textSec}}>{'💰 '+total.toLocaleString()+' / '+p.budget.toLocaleString()+' ₽'}</span>}
                      </div>
                    </div>
                    <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
                      {isLeadership()&&<button onClick={e=>{e.stopPropagation();editProject(p);}} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}><Edit2 size={11}/></button>}
                      {isLeadership()&&<button onClick={e=>{e.stopPropagation();deleteProject(p.id);}} style={{...btnR,padding:'5px 10px',fontSize:'11px'}}><Trash2 size={11}/></button>}
                      {isOpen?<ChevronUp size={18} color={C.textMuted}/>:<ChevronDown size={18} color={C.textMuted}/>}
                    </div>
                  </div>
                </div>
                {isOpen&&(<div style={{borderTop:'1.5px solid '+C.border}}>
                  <div style={{display:'flex',gap:0,overflowX:'auto',borderBottom:'1.5px solid '+C.border,backgroundColor:C.bg,padding:'0 16px'}}>
                    {(()=>{
                      const tabGroups=[
                        {id:'work',icon:'🔨',label:'Работы',tabs:['Наряды','Непредвиденные','Чек-листы']},
                        {id:'finance',icon:'💰',label:'Финансы',tabs:['Финансы','Смета','Материалы']},
                        {id:'object',icon:'🏗️',label:'Объект',tabs:['Общее','Помещения','График','Этапы']},
                        {id:'journals',icon:'📚',label:'Журналы',tabs:['Главный','Производство работ','АОСР','Входной контроль','Кабельная продукция','Журнал ТБ','Погода','Предписания','Чат']},
                        {id:'docs',icon:'📋',label:'Документы',tabs:['КС-2','КС-3','Паспорт','Акты технадзора','Замечания ГСН']},
                      ];
                      const activeGroup=tabGroups.find(g=>g.tabs.includes(activeProjectTab));
                      return(<div>
                        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(80px,1fr))',gap:'6px',marginBottom:'10px'}}>
                          {tabGroups.map(g=>(<div key={g.id} onClick={()=>{setActiveTabGroup(activeTabGroup===g.id?null:g.id);if(g.tabs.length>0)setActiveProjectTab(g.tabs[0]);}} style={{padding:'12px 6px',borderRadius:'12px',cursor:'pointer',display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',gap:'4px',backgroundColor:activeGroup&&activeGroup.id===g.id?C.accentLight:C.bg,border:'1.5px solid '+(activeGroup&&activeGroup.id===g.id?C.accentBorder:C.border),transition:'all 0.15s',minHeight:'70px'}}>
                            <div style={{fontSize:'22px',lineHeight:1,display:'flex',alignItems:'center',justifyContent:'center'}}>{g.icon}</div>
                            <div style={{fontSize:'11px',fontWeight:activeGroup&&activeGroup.id===g.id?'700':'500',color:activeGroup&&activeGroup.id===g.id?C.accent:C.textSec,textAlign:'center',lineHeight:1.2}}>{g.label}</div>
                          </div>))}
                        </div>
                        {activeGroup&&(<div style={{display:'flex',gap:'4px',flexWrap:'wrap',marginBottom:'8px'}}>
                          {activeGroup.tabs.map(tab=>(<button key={tab} onClick={()=>setActiveProjectTab(tab)} style={{padding:'6px 12px',backgroundColor:activeProjectTab===tab?C.accent:'white',cursor:'pointer',fontSize:'12px',fontWeight:activeProjectTab===tab?'700':'400',color:activeProjectTab===tab?'white':C.textSec,borderRadius:'20px',border:'1.5px solid '+(activeProjectTab===tab?C.accent:C.border)}}>{tab}</button>))}
                        </div>)}
                      </div>);
                    })()}
                  </div>
                  <div style={{padding:'20px'}}>
                    {activeProjectTab==='Общее'&&(<div>
                      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:'12px',marginBottom:'16px'}}>
                        {EXPENSE_CATEGORIES.map(c=>(<div key={c.id} style={{padding:'12px',backgroundColor:C.bg,borderRadius:'10px',border:'1.5px solid '+C.border}}><p style={{margin:'0 0 4px',fontSize:'11px',color:C.textSec}}>{c.label}</p><b style={{fontSize:'14px',color:c.color}}>{(cat[c.id]||0).toLocaleString()+' ₽'}</b></div>))}
                      </div>
                      <div style={{...card,padding:'16px',marginBottom:'12px',backgroundColor:C.accentLight,border:'1.5px solid '+C.accentBorder}}>
                        <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'12px'}}>📊 Наряды и выполнение</b>
                        <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'10px',marginBottom:'12px'}}>
                          <div style={{textAlign:'center'}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Нарядов</p><b style={{color:C.text,fontSize:'18px'}}>{brigadeContracts.filter(bc=>bc.projectName===p.name).length}</b></div>
                          <div style={{textAlign:'center'}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>По договорам</p><b style={{color:C.accent,fontSize:'16px'}}>{brigadeContracts.filter(bc=>bc.projectName===p.name).reduce((s,bc)=>s+Number(bc.totalAmount||0),0).toLocaleString()+' ₽'}</b></div>
                          <div style={{textAlign:'center'}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Смет</p><b style={{color:C.text,fontSize:'18px'}}>{estimatesList.filter(e=>e.projectName===p.name||Number(e.projectId)===Number(p.id)).length}</b></div>
                        </div>
                        <div style={{marginBottom:'12px'}}>
                          <div style={{display:'flex',justifyContent:'space-between',marginBottom:'4px'}}>
                            <b style={{fontSize:'12px',color:C.text}}>Выполнение нарядов</b>
                            <span style={{fontSize:'12px',color:C.textSec}}>{(()=>{
                              const pBrigades=brigadeContracts.filter(bc=>bc.projectName===p.name);
                              if(!pBrigades.length) return '0%';
                              const totalSmeta=pBrigades.reduce((s,bc)=>s+Number(bc.totalAmount||0),0);
                              return totalSmeta>0?'расчёт...':'0%';
                            })()}</span>
                          </div>
                          <div style={{backgroundColor:C.bgGray,borderRadius:'6px',height:'10px'}}>
                            <div style={{backgroundColor:C.success,width:'0%',height:'100%',borderRadius:'6px'}}/>
                          </div>
                        </div>
                        <div style={{display:'grid',gridTemplateColumns:'repeat(2,1fr)',gap:'10px'}}>
                          <div style={{backgroundColor:C.successLight,padding:'10px',borderRadius:'8px',border:'1px solid '+C.successBorder}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Смета заказчика</p><b style={{color:C.success,fontSize:'14px'}}>{estimatesList.filter(e=>(e.projectName===p.name||Number(e.projectId)===Number(p.id))&&(e.smetaType==='Заказчик'||!e.smetaType)).reduce((s,e)=>(e.sections||[]).flatMap(sec=>sec.items||[]).reduce((ss,i)=>ss+(i.isImported?Number(i.priceWork||0):Number(i.quantity||0)*Number(i.priceWork||0)),s),0).toLocaleString()+' ₽'}</b></div>
                          <div style={{backgroundColor:C.warningLight,padding:'10px',borderRadius:'8px',border:'1px solid '+C.warningBorder}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Подрядчикам</p><b style={{color:C.warning,fontSize:'14px'}}>{brigadeContracts.filter(bc=>bc.projectName===p.name).reduce((s,bc)=>s+Number(bc.totalAmount||0),0).toLocaleString()+' ₽'}</b></div>
                        </div>
                      </div>
                      <div style={{backgroundColor:C.bg,borderRadius:'10px',padding:'14px',border:'1.5px solid '+C.border,marginBottom:'12px'}}>
                        {isFinanceRole()&&(<><div style={{display:'flex',justifyContent:'space-between',marginBottom:'8px'}}><b style={{color:C.text,fontSize:'13px'}}>Прогресс бюджета</b><span style={{fontSize:'13px',color:total>p.budget?C.danger:C.success}}>{total.toLocaleString()+' из '+p.budget.toLocaleString()+' ₽'}</span></div>
                        <div style={{backgroundColor:C.bgGray,borderRadius:'6px',height:'10px'}}><div style={{backgroundColor:total>p.budget?C.danger:total>p.budget*0.8?C.warning:C.success,width:Math.min(100,p.budget>0?total/p.budget*100:0)+'%',height:'100%',borderRadius:'6px',transition:'width 0.3s'}}/></div></>)}
                      </div>
                      <div style={{display:'flex',gap:'8px',flexWrap:'wrap',marginBottom:'16px'}}>
                        <button onClick={()=>showPreview(buildPassportContent(p),'Паспорт объекта — '+p.name)} style={btnB}><FileText size={14}/>Паспорт</button>
                        <button onClick={()=>showKS2(p)} style={btnG}><FileText size={14}/>КС-2</button>
                        <button onClick={()=>showPreview(buildKS3Content(p),'КС-3 — '+p.name)} style={btnG}><FileText size={14}/>КС-3</button>
                        <button onClick={()=>showPreview(buildJPRContent(p.name),'ЖПР — '+p.name)} style={btnG}><ScrollText size={14}/>ЖПР</button>
                        <button onClick={()=>setShowQRModal({title:'QR — '+p.name,data:window.location.origin+'/?project='+encodeURIComponent(p.name)})} style={btnG}><QrCode size={14}/>QR</button>
                      </div>
                      <div>
                        <b style={{color:C.text,fontSize:'13px'}}>Задачи:</b>
                        <div style={{display:'flex',gap:'8px',marginTop:'8px',marginBottom:'10px'}}>
                          <input placeholder="Новая задача..." value={newTask} onChange={e=>setNewTask(e.target.value)} onKeyDown={e=>e.key==='Enter'&&addTask(p)} style={{...inp,marginBottom:0,flex:1,fontSize:'13px'}}/>
                          <button onClick={()=>addTask(p)} style={btnO}><Plus size={14}/></button>
                        </div>
                        {(p.tasks||[]).map((t,i)=>(<div key={i} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'8px 10px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border}}><span style={{fontSize:'13px',color:C.text}}>{'• '+t}</span><button onClick={()=>removeTask(p,i)} style={{...btnR,padding:'3px 7px',fontSize:'10px'}}><X size={10}/></button></div>))}
                      </div>

                      {user&&['директор','зам_директора','бухгалтер','прораб'].includes(user.role)&&(()=>{
                        const projSmeta=estimatesList.find(e=>(e.projectName===p.name||Number(e.projectId)===Number(p.id))&&(!e.smetaType||e.smetaType==='Заказчик'))||estimatesList.find(e=>e.projectName===p.name||Number(e.projectId)===Number(p.id));
                        const smetaItems=projSmeta?(projSmeta.sections||[]).flatMap(s=>(s.items||[]).map(i=>({...i,section:s.name}))):[];
                        const norm=(s)=>(s||'').toLowerCase().replace(/[.,;:()«»"'-]/g,' ').replace(/\s+/g,' ').trim();
                        const matchScore=(a,b)=>{const aw=norm(a).split(' ').filter(w=>w.length>=3);const bw=new Set(norm(b).split(' ').filter(w=>w.length>=3));if(!aw.length||!bw.size) return 0;const common=aw.filter(w=>bw.has(w)).length;return common/Math.max(aw.length,1);};
                        const projJournal=workJournal.filter(j=>j.project===p.name);
                        const projMaterials=materials.filter(m=>m.project===p.name);
                        const projTransfers=materialTransfers.filter(t=>t.projectName===p.name);
                        const workProgress=smetaItems.map(it=>{
                          const plan=Number(it.quantity||0);
                          const done=projJournal.filter(j=>matchScore(j.description,it.name)>=0.4).reduce((s,j)=>s+Number(j.quantity||0),0);
                          const left=Math.max(0,plan-done);
                          const pct=plan>0?Math.min(100,Math.round(done/plan*100)):0;
                          return {name:it.name,section:it.section,unit:it.unit,plan,done,left,pct};
                        });
                        const matPlan=smetaItems.filter(i=>Number(i.priceMaterial||0)>0).map(it=>{
                          const plan=Number(it.quantity||0);
                          const bought=projMaterials.filter(m=>matchScore(m.name,it.name)>=0.4).reduce((s,m)=>s+Number(m.quantity||0),0);
                          return {name:it.name,unit:it.unit,plan,bought,need:Math.max(0,plan-bought)};
                        });
                        const fmt=(n)=>Number(n||0).toLocaleString('ru-RU');
                        const payload={
                          project:p.name,
                          total:smetaItems.reduce((s,i)=>s+Number(i.quantity||0)*(Number(i.priceWork||0)+Number(i.priceMaterial||0)),0),
                          workProgress:workProgress.filter(w=>w.plan>0),
                          materials:matPlan,
                          stock:projMaterials.map(m=>({name:m.name,qty:Number(m.quantity||0),unit:m.unit})),
                          transfers:projTransfers.slice(0,20).map(t=>({name:t.materialName,qty:Number(t.quantity||0),unit:t.unit,to:t.toPerson,date:t.transferDate}))
                        };
                        const payloadStr=JSON.stringify(payload);
                        let _h=0;for(let i=0;i<payloadStr.length;i++){_h=((_h*31)+payloadStr.charCodeAt(i))|0;}
                        const currentHash=(_h>>>0).toString(16);
                        const cached=projectAiSummaries[p.name];
                        const isFresh=cached&&cached.payloadHash===currentHash;
                        const fmtAgo=(iso)=>{if(!iso) return '';const d=new Date(iso);const m=Math.floor((Date.now()-d.getTime())/60000);if(m<1) return 'только что';if(m<60) return m+' мин назад';const h=Math.floor(m/60);if(h<24) return h+' ч назад';return Math.floor(h/24)+' дн назад';};
                        const runAiSummary=async()=>{
                          const prompt='Объект "'+p.name+'". Проанализируй прогресс и материальный учёт. Данные ниже.\n\n'+JSON.stringify(payload,null,1)+'\n\nОТВЕТЬ СТРОГО JSON (без markdown):\n{\n  "summary":"одна-две фразы общего впечатления",\n  "progress":[{"what":"что","status":"в норме|отставание|опережение","note":"что заметил"}],\n  "materials":[{"what":"материал","problem":"нехватка|избыток|пропажа|норма","action":"что сделать","amount":число_или_0}],\n  "alerts":[{"type":"критично|внимание|совет","text":"что"}]\n}\nИспользуй только данные из payload. Если данных мало — пиши "недостаточно данных".';
                          setShowAiChat(true);
                          setAiMessages([{role:'user',content:'Контроль объекта: '+p.name}]);
                          setAiLoading(true);
                          try{
                            const res=await fetch(API+'/ai-chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:[{role:'user',content:prompt}],jsonOnly:true})});
                            const data=await res.json();
                            const raw=(data.response||data.error||'').trim();
                            let parsed=null;
                            try{const clean=raw.replace(/^```(?:json)?/i,'').replace(/```$/,'').trim();const s=clean.indexOf('{'),e=clean.lastIndexOf('}');if(s>=0&&e>s) parsed=JSON.parse(clean.slice(s,e+1));}catch(e){}
                            let out;
                            if(parsed){
                              const ln=[];
                              if(parsed.summary) ln.push('📋 '+parsed.summary,'');
                              if(Array.isArray(parsed.alerts)&&parsed.alerts.length){ln.push('🚨 ВНИМАНИЕ');parsed.alerts.forEach((a,n)=>ln.push((n+1)+'. ['+(a.type||'')+'] '+(a.text||'')));ln.push('');}
                              if(Array.isArray(parsed.progress)&&parsed.progress.length){ln.push('🔨 РАБОТЫ');parsed.progress.forEach((q,n)=>ln.push((n+1)+'. '+(q.what||'?')+' — '+(q.status||'?')+(q.note?': '+q.note:'')));ln.push('');}
                              if(Array.isArray(parsed.materials)&&parsed.materials.length){ln.push('📦 МАТЕРИАЛЫ');parsed.materials.forEach((m,n)=>ln.push((n+1)+'. '+(m.what||'?')+' — '+(m.problem||'?')+(m.action?' → '+m.action:'')+(m.amount?' ('+fmt(m.amount)+')':'')));}
                              out=ln.join('\n');
                            }else out=raw||'Ошибка ответа ИИ';
                            setAiMessages([{role:'user',content:'Контроль объекта: '+p.name},{role:'assistant',content:out}]);
                            try{await fetch(API+'/project-ai-summary',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({projectName:p.name,payloadHash:currentHash,summary:out})});setProjectAiSummaries(prev=>({...prev,[p.name]:{exists:true,payloadHash:currentHash,summary:out,updatedAt:new Date().toISOString()}}));}catch(e){}
                          }catch(e){setAiMessages(prev=>[...prev,{role:'assistant',content:'Ошибка соединения'}]);}
                          setAiLoading(false);
                        };
                        return(<div style={{...card,padding:'16px',marginBottom:'12px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.accentBorder}}>
                          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'14px'}}>
                            <b style={{color:C.text,fontSize:'14px'}}>📊 Контроль объекта</b>
                            <button onClick={runAiSummary} style={{...btnB,backgroundColor:'#10b981',fontSize:'12px'}}><Bot size={13}/>{cached?'Обновить ИИ':'AI-сводка'}</button>
                          </div>
                          {cached&&(<div style={{...card,padding:'12px',marginBottom:'14px',backgroundColor:isFresh?C.successLight:C.warningLight,border:'1.5px solid '+(isFresh?C.successBorder:C.warningBorder)}}>
                            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'8px'}}>
                              <b style={{fontSize:'12px',color:isFresh?C.success:C.warning}}>🤖 {isFresh?'AI-сводка актуальна':'⚠️ Данные изменились — нужно обновить'}</b>
                              <span style={{fontSize:'11px',color:C.textSec}}>{fmtAgo(cached.updatedAt)}</span>
                            </div>
                            <div style={{fontSize:'12px',color:C.text,whiteSpace:'pre-wrap',lineHeight:'1.5'}}>{cached.summary}</div>
                          </div>)}
                          {!cached&&<p style={{fontSize:'12px',color:C.textMuted,marginBottom:'12px',padding:'8px',backgroundColor:C.bg,borderRadius:'8px'}}>💡 AI-сводка ещё не делалась. Нажмите «AI-сводка» — анализ сохранится в системе.</p>}
                          {!projSmeta&&<p style={{color:C.textMuted,fontSize:'12px',padding:'10px',textAlign:'center'}}>У объекта нет сметы — нечего сравнивать. Добавьте смету в разделе «Сметы».</p>}
                          {projSmeta&&(<>
                          <div style={{marginBottom:'14px'}}>
                            <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'6px'}}>📋 Прогресс по смете (работы)</b>
                            <table style={{...tbl,fontSize:'11px'}}><thead><tr><th style={tblH}>Позиция</th><th style={tblH}>План</th><th style={tblH}>Выполнено</th><th style={tblH}>Осталось</th><th style={tblH}>%</th></tr></thead><tbody>
                              {workProgress.filter(w=>w.plan>0).slice(0,15).map((w,i)=>(<tr key={i}><td style={{...tblC,fontSize:'11px'}}>{w.name}</td><td style={{...tblC,fontSize:'11px'}}>{w.plan} {w.unit}</td><td style={{...tblC,fontSize:'11px',color:w.done>0?C.success:C.textMuted}}>{w.done} {w.unit}</td><td style={{...tblC,fontSize:'11px',color:w.left>0?C.warning:C.success}}>{w.left} {w.unit}</td><td style={{...tblC,fontSize:'11px',fontWeight:'600',color:w.pct>=100?C.success:w.pct>=50?C.info:C.warning}}>{w.pct}%</td></tr>))}
                            </tbody></table>
                            {!workProgress.filter(w=>w.plan>0).length&&<p style={{color:C.textMuted,fontSize:'11px',padding:'8px'}}>В смете нет позиций работ</p>}
                          </div>
                          <div style={{marginBottom:'14px'}}>
                            <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'6px'}}>📥 Материалы — план vs закуплено</b>
                            <table style={{...tbl,fontSize:'11px'}}><thead><tr><th style={tblH}>Материал</th><th style={tblH}>По смете</th><th style={tblH}>Закуплено</th><th style={tblH}>Не хватает</th></tr></thead><tbody>
                              {matPlan.slice(0,15).map((m,i)=>(<tr key={i}><td style={{...tblC,fontSize:'11px'}}>{m.name}</td><td style={{...tblC,fontSize:'11px'}}>{m.plan} {m.unit}</td><td style={{...tblC,fontSize:'11px',color:m.bought>=m.plan?C.success:C.info}}>{m.bought} {m.unit}</td><td style={{...tblC,fontSize:'11px',color:m.need>0?C.danger:C.success}}>{m.need>0?m.need+' '+m.unit:'✅'}</td></tr>))}
                            </tbody></table>
                            {!matPlan.length&&<p style={{color:C.textMuted,fontSize:'11px',padding:'8px'}}>В смете нет материалов</p>}
                          </div>
                          </>)}
                          <div style={{marginBottom:'14px'}}>
                            <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'6px'}}>📤 Выдачи мастерам ({projTransfers.length})</b>
                            <table style={{...tbl,fontSize:'11px'}}><thead><tr><th style={tblH}>Материал</th><th style={tblH}>Кол-во</th><th style={tblH}>Кому</th><th style={tblH}>Дата</th></tr></thead><tbody>
                              {projTransfers.slice(0,10).map((t,i)=>(<tr key={i}><td style={{...tblC,fontSize:'11px'}}>{t.materialName}</td><td style={{...tblC,fontSize:'11px'}}>{t.quantity} {t.unit}</td><td style={{...tblC,fontSize:'11px'}}>{t.toPerson}</td><td style={{...tblC,fontSize:'11px'}}>{t.transferDate}</td></tr>))}
                            </tbody></table>
                            {!projTransfers.length&&<p style={{color:C.textMuted,fontSize:'11px',padding:'8px'}}>Передач ещё не было</p>}
                          </div>
                          <div>
                            <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'6px'}}>🏬 Остатки на складе объекта ({projMaterials.filter(m=>Number(m.quantity||0)>0).length})</b>
                            <table style={{...tbl,fontSize:'11px'}}><thead><tr><th style={tblH}>Материал</th><th style={tblH}>Остаток</th><th style={tblH}>Категория</th></tr></thead><tbody>
                              {projMaterials.filter(m=>Number(m.quantity||0)>0).slice(0,15).map((m,i)=>(<tr key={i}><td style={{...tblC,fontSize:'11px'}}>{m.name}</td><td style={{...tblC,fontSize:'11px',fontWeight:'600',color:C.success}}>{m.quantity} {m.unit}</td><td style={{...tblC,fontSize:'11px',color:C.textSec}}>{m.category||''}</td></tr>))}
                            </tbody></table>
                            {!projMaterials.filter(m=>Number(m.quantity||0)>0).length&&<p style={{color:C.textMuted,fontSize:'11px',padding:'8px'}}>Склад объекта пуст</p>}
                          </div>
                        </div>);
                      })()}

                    <button onClick={async()=>{
                      const doneItems=brigadeContractItems.filter(i=>i.doneQuantity>0);
                      if(!doneItems.length){alert('Введите выполненные объёмы');return;}
                      for(const item of doneItems){
                        await fetch(API+'/work-journal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:selectedBrigadeContract?.projectName||'',description:item.name,quantity:item.doneQuantity,unit:item.unit,date:new Date().toISOString().split('T')[0],masterName:user.name,masterId:user.id,total:Math.round(item.doneQuantity*item.priceBrigade),status:'На проверке',photoUrl:(masterReportPhotos||[]).join(',')})});
                      }
                      alert('Отправлено на проверку прорабу!');
                      await loadAll();
                      await updateProjectProgress(selectedBrigadeContract?.projectName||'');
                    }} style={{...btnO,display:user&&['мастер','субподрядчик'].includes(user.role)?'flex':'none',marginTop:'10px',width:'100%',justifyContent:'center'}}><Check size={14}/>Отправить на проверку</button>
                  </div>)}

                    {activeProjectTab==='Наряды'&&(<div></div>)}
                    {activeProjectTab==='Этапы'&&(<div>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                        <b style={{color:C.text}}>Этапы проекта</b>
                        {isProrab()&&<button onClick={()=>setShowForm(showForm==='stages'?false:'stages')} style={btnO}><Plus size={14}/>Добавить этап</button>}
                      </div>
                      {showForm==='stages'&&(<div style={{...card,padding:'16px',marginBottom:'16px',backgroundColor:C.bg}}>
                        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
                          <input placeholder="Название этапа *" value={newStage.name} onChange={e=>setNewStage({...newStage,name:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <select value={newStage.status} onChange={e=>setNewStage({...newStage,status:e.target.value})} style={{...inp,marginBottom:0}}>{STAGE_STATUSES.map(s=><option key={s}>{s}</option>)}</select>
                          <input type="date" placeholder="Начало" value={newStage.startDate} onChange={e=>setNewStage({...newStage,startDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input type="date" placeholder="Конец" value={newStage.endDate} onChange={e=>setNewStage({...newStage,endDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Ответственный" value={newStage.responsible} onChange={e=>setNewStage({...newStage,responsible:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <div style={{display:'flex',alignItems:'center',gap:'8px'}}><label style={{fontSize:'12px',color:C.textSec,whiteSpace:'nowrap'}}>Прогресс: {newStage.progress}%</label><input type="range" min="0" max="100" value={newStage.progress} onChange={e=>setNewStage({...newStage,progress:Number(e.target.value)})} style={{flex:1,accentColor:C.accent}}/></div>
                        </div>
                        <div style={{display:'flex',gap:'8px',marginTop:'10px'}}>
                          <button onClick={()=>saveProjectStage(p.id,p.name)} style={btnO}><Check size={14}/>Сохранить</button>
                          <button onClick={()=>setShowForm(false)} style={btnG}><X size={14}/>Отмена</button>
                        </div>
                      <button onClick={async()=>{
                      const doneItems=brigadeContractItems.filter(i=>i.doneQuantity>0);
                      if(!doneItems.length){alert('Введите выполненные объёмы');return;}
                      for(const item of doneItems){
                        await fetch(API+'/work-journal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:selectedBrigadeContract?.projectName||'',description:item.name,quantity:item.doneQuantity,unit:item.unit,date:new Date().toISOString().split('T')[0],masterName:user.name,masterId:user.id,total:Math.round(item.doneQuantity*item.priceBrigade),status:'На проверке',photoUrl:(masterReportPhotos||[]).join(',')})});
                      }
                      alert('Отправлено на проверку прорабу!');
                      await loadAll();
                      await updateProjectProgress(selectedBrigadeContract?.projectName||'');
                    }} style={{...btnO,display:user&&['мастер','субподрядчик'].includes(user.role)?'flex':'none',marginTop:'10px',width:'100%',justifyContent:'center'}}><Check size={14}/>Отправить на проверку</button>
                  </div>)}
                      {projectStages.filter(s=>s.projectName===p.name).map(stage=>{
                        const stColors={'Не начат':[C.textSec,C.bgGray,C.border],'В работе':[C.info,C.infoLight,C.infoBorder],'Завершён':[C.success,C.successLight,C.successBorder],'Заморожен':[C.warning,C.warningLight,C.warningBorder],'Просрочен':[C.danger,C.dangerLight,C.dangerBorder]};
                        const sc=stColors[stage.status]||stColors['Не начат'];
                        return(<div key={stage.id} style={{...card,padding:'14px',marginBottom:'10px',borderLeft:'3px solid '+sc[0]}}>
                          <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
                            <div style={{flex:1}}>
                              <div style={{display:'flex',alignItems:'center',gap:'10px',marginBottom:'6px'}}>
                                <b style={{color:C.text,fontSize:'13px'}}>{stage.name}</b>
                                <span style={badge(sc[0],sc[1],sc[2])}>{stage.status}</span>
                              </div>
                              {(stage.startDate||stage.endDate)&&<p style={{color:C.textSec,margin:'0 0 4px',fontSize:'12px'}}>{(stage.startDate||'')+(stage.endDate?' — '+stage.endDate:'')}</p>}
                              {stage.responsible&&<p style={{color:C.textSec,margin:'0 0 6px',fontSize:'12px'}}>{'👤 '+stage.responsible}</p>}
                              <div style={{backgroundColor:C.bgGray,borderRadius:'4px',height:'6px',marginTop:'6px'}}>
                                <div style={{backgroundColor:sc[0],width:(stage.progress||0)+'%',height:'100%',borderRadius:'4px'}}/>
                              </div>
                              <p style={{color:C.textMuted,margin:'4px 0 0',fontSize:'11px'}}>{(stage.progress||0)+'% выполнено'}</p>
                            </div>
                            {isProrab()&&(<div style={{display:'flex',gap:'4px',marginLeft:'10px'}}>
                              <select value={stage.status} onChange={async e=>{await updateStage({...stage,status:e.target.value});}} style={{fontSize:'11px',padding:'3px 6px',border:'1.5px solid '+C.border,borderRadius:'6px',cursor:'pointer'}}>
                                {STAGE_STATUSES.map(s=><option key={s}>{s}</option>)}
                              </select>
                              <button onClick={()=>deleteStage(stage.id)} style={{...btnR,padding:'4px 8px'}}><Trash2 size={11}/></button>
                            <button onClick={async()=>{
                      const doneItems=brigadeContractItems.filter(i=>i.doneQuantity>0);
                      if(!doneItems.length){alert('Введите выполненные объёмы');return;}
                      for(const item of doneItems){
                        await fetch(API+'/work-journal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:selectedBrigadeContract?.projectName||'',description:item.name,quantity:item.doneQuantity,unit:item.unit,date:new Date().toISOString().split('T')[0],masterName:user.name,masterId:user.id,total:Math.round(item.doneQuantity*item.priceBrigade),status:'На проверке',photoUrl:(masterReportPhotos||[]).join(',')})});
                      }
                      alert('Отправлено на проверку прорабу!');
                      await loadAll();
                      await updateProjectProgress(selectedBrigadeContract?.projectName||'');
                    }} style={{...btnO,display:user&&['мастер','субподрядчик'].includes(user.role)?'flex':'none',marginTop:'10px',width:'100%',justifyContent:'center'}}><Check size={14}/>Отправить на проверку</button>
                  </div>)}
                          </div>
                        </div>);
                      })}
                      {projectStages.filter(s=>s.projectName===p.name).length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'20px'}}>Этапов нет — добавьте первый!</p>}
                  </div>)}

                    {activeProjectTab==='График'&&(<div>
                      <b style={{color:C.text,display:'block',marginBottom:'15px'}}>График Ганта</b>
                      {(()=>{
                        const stages=projectStages.filter(s=>s.projectName===p.name&&s.startDate&&s.endDate);
                        if(stages.length===0) return <p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Добавьте этапы с датами во вкладке Этапы</p>;
                        const allDates=stages.flatMap(s=>[s.startDate,s.endDate]).filter(Boolean).sort();
                        const minDate=new Date(allDates[0]);
                        const maxDate=new Date(allDates[allDates.length-1]);
                        const totalDays=Math.max(1,Math.round((maxDate-minDate)/86400000))+1;
                        const stColors={'Не начат':C.textSec,'В работе':C.info,'Завершён':C.success,'Заморожен':C.warning,'Просрочен':C.danger};
                        return(<div style={{overflowX:'auto'}}>
                          <div style={{minWidth:'600px'}}>
                            <div style={{display:'flex',borderBottom:'1.5px solid '+C.border,paddingBottom:'6px',marginBottom:'8px'}}>
                              <div style={{width:'200px',flexShrink:0,fontSize:'11px',color:C.textSec,fontWeight:'600'}}>Этап</div>
                              <div style={{flex:1,fontSize:'11px',color:C.textSec,fontWeight:'600'}}>Временная шкала</div>
                            </div>
                            {stages.map(stage=>{
                              const sd=new Date(stage.startDate);
                              const ed=new Date(stage.endDate);
                              const left=Math.round((sd-minDate)/86400000)/totalDays*100;
                              const width=Math.max(1,Math.round((ed-sd)/86400000)+1)/totalDays*100;
                              const color=stColors[stage.status]||C.textSec;
                              return(<div key={stage.id} style={{display:'flex',alignItems:'center',marginBottom:'10px'}}>
                                <div style={{width:'200px',flexShrink:0,fontSize:'12px',color:C.text,paddingRight:'10px',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{stage.name}</div>
                                <div style={{flex:1,position:'relative',height:'26px',backgroundColor:C.bg,borderRadius:'4px',border:'1px solid '+C.border}}>
                                  <div style={{position:'absolute',left:left+'%',width:width+'%',minWidth:'2%',height:'100%',backgroundColor:color,borderRadius:'4px',display:'flex',alignItems:'center',paddingLeft:'6px',overflow:'hidden'}}>
                                    <span style={{fontSize:'10px',color:'white',fontWeight:'600',whiteSpace:'nowrap'}}>{stage.progress+'%'}</span>
                                  </div>
                                </div>
                              </div>);
                            })}
                          </div>
                          {projectPayments.filter(pay=>pay.projectName===p.name).length>0&&(<div style={{marginTop:'12px'}}>
                            <b style={{color:C.textSec,fontSize:'12px',display:'block',marginBottom:'8px'}}>История оплат:</b>
                            {projectPayments.filter(pay=>pay.projectName===p.name).map(pay=>(<div key={pay.id} style={{display:'flex',justifyContent:'space-between',padding:'6px 0',borderBottom:'1px solid '+C.border}}>
                              <div><span style={{fontSize:'12px',color:C.text}}>{pay.note||'Оплата'}</span><span style={{fontSize:'11px',color:C.textMuted,marginLeft:'8px'}}>{pay.date}</span></div>
                              <b style={{fontSize:'12px',color:C.success}}>+{Number(pay.amount).toLocaleString()+' ₽'}</b>
                            </div>))}
                          </div>)}
                        </div>);
                      })()}
                  </div>)}

                    {activeProjectTab==='Смета'&&(<div>
                      <b style={{color:C.text,display:'block',marginBottom:'15px'}}>Смета проекта</b>
                      {(()=>{
                        const projEstimates=estimatesList.filter(e=>e.projectName===p.name);
                        if(projEstimates.length===0) return(<div style={{textAlign:'center',padding:'30px',color:C.textMuted}}><p>Смета не привязана</p><button onClick={()=>navigateTo('estimates')} style={btnO}>Перейти в Сметы</button></div>);
                        return projEstimates.map(est=>(<div key={est.id} style={{...card,padding:'14px',marginBottom:'10px'}}>
                          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                            <div><b style={{color:C.text,fontSize:'13px'}}>{est.name}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{'v'+est.version}</p></div>
                            <div style={{display:'flex',gap:'6px'}}>
                              <button onClick={()=>{setSelectedEstimate(est);navigateTo('estimates');}} style={btnB}><Eye size={13}/>Открыть</button>
                            </div>
                          </div>
                        </div>));
                      })()}
                  </div>)}

                    {activeProjectTab==='Производство работ'&&(<div>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',flexWrap:'wrap',gap:'8px'}}>
                        <b style={{color:C.text}}>Журнал производства работ</b>
                        <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
                          <button onClick={()=>setShowJournalTableModal(p.name)} style={btnB}><FileText size={14}/>📋 Таблица КС-6а</button>
                          <button onClick={()=>showPreview(buildJPRContent(p.name),'ЖПР — '+p.name)} style={btnG}><ScrollText size={14}/>ЖПР</button>
                          <button onClick={()=>showKS2(p)} style={btnG}><FileText size={14}/>КС-2</button>
                        </div>
                      </div>
                      {(()=>{const unx=workJournal.filter(j=>j.project===p.name&&j.unexpectedWorkId);if(unx.length===0) return null;const unxSum=unx.reduce((s,j)=>s+Number(j.total||0),0);return(<div style={{marginBottom:'12px',padding:'10px 12px',backgroundColor:'#fef3c7',border:'1.5px solid #fbbf24',borderRadius:'10px',fontSize:'13px',color:'#78350f'}}>🆕 <b>Работы вне сметы:</b> {unx.length} позиц. на <b>{Math.round(unxSum).toLocaleString('ru-RU')+' ₽'}</b> (оформлены доп.соглашениями) — подсвечены жёлтым в списке ниже</div>);})()}
                      {(()=>{
                        const works=workJournal.filter(j=>j.project===p.name);
                        const byDate={};
                        works.forEach(w=>{if(!byDate[w.date]) byDate[w.date]={};if(!byDate[w.date][w.masterName]) byDate[w.date][w.masterName]=[];byDate[w.date][w.masterName].push(w);});
                        return Object.keys(byDate).sort().reverse().map(date=>{
                          const weather=weatherLog.find(w=>w.projectName===p.name&&w.date===date);
                          return(<div key={date} style={{marginBottom:'16px'}}>
                            <div style={{display:'flex',alignItems:'center',gap:'10px',marginBottom:'8px'}}>
                              <b style={{color:C.text,fontSize:'13px'}}>{date}</b>
                              {weather&&<span style={{fontSize:'12px',color:C.info}}>{'🌤️ '+weather.condition+' '+weather.temperature+'°C'}</span>}
                            </div>
                            {Object.keys(byDate[date]).map(masterName=>(<div key={masterName} style={{marginBottom:'8px'}}>
                              <p style={{color:C.accent,fontSize:'12px',fontWeight:'600',margin:'0 0 6px'}}>{'👷 '+masterName}</p>
                              {byDate[date][masterName].map(w=>(<div key={w.id} onClick={()=>setEditingJournal(w)} style={{padding:'8px 10px',backgroundColor:w.unexpectedWorkId?'#fef3c7':C.bg,borderRadius:'8px',marginBottom:'4px',border:'1.5px solid '+(w.unexpectedWorkId?'#fbbf24':C.border),display:'flex',justifyContent:'space-between',alignItems:'center',cursor:'pointer'}}>
                                <div><b style={{fontSize:'12px',color:C.text}}>{w.description}{w.unexpectedWorkId?<span title="Непредвиденная работа (доп.соглашение)" style={{marginLeft:'4px',color:C.warning}}>🆕</span>:null}{w.hiddenWork?(()=>{const st=getActStatusForJournal(w);return(<span title={st?st.tip:'Скрытые работы — нужен АОСР'} style={{marginLeft:'4px',cursor:st&&st.act?'pointer':'default'}} onClick={e=>{if(st&&st.act){e.stopPropagation();setEditingAct(st.act);}}}>🔒{st?st.icon:''}</span>);})():null}</b><p style={{color:C.textSec,margin:'1px 0',fontSize:'11px'}}>{w.quantity+' '+w.unit+(w.roomName?' · '+w.roomName:'')}</p></div>
                                <div style={{display:'flex',alignItems:'center',gap:'6px'}}>
                                  <b style={{color:C.success,fontSize:'12px'}}>{(w.total||0).toLocaleString()+' ₽'}</b>
                                  {isProrab()&&w.status==='На проверке'&&(<><button onClick={()=>confirmJ(w)} style={{...btnGr,padding:'3px 8px',fontSize:'11px'}}><Check size={11}/></button><button onClick={()=>setRejectingEntry(w)} style={{...btnR,padding:'3px 8px',fontSize:'11px'}}><X size={11}/></button></>)}
                                  {w.status==='Подтверждено'&&<span style={badge(C.success,C.successLight,C.successBorder)}>✅</span>}
                                  {w.status==='Отклонено'&&<span style={badge(C.danger,C.dangerLight,C.dangerBorder)}>❌</span>}
                                  {w.photoUrl&&<img src={w.photoUrl} alt="" onClick={()=>setShowPhotoModal(w.photoUrl)} style={{width:'32px',height:'32px',borderRadius:'6px',objectFit:'cover',cursor:'pointer'}}/>}
                                </div>
                              </div>))}
                            </div>))}
                          </div>);
                        });
                      })()}
                      {workJournal.filter(j=>j.project===p.name).length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'20px'}}>Работ нет</p>}
                  </div>)}

                    {activeProjectTab==='Помещения'&&(<div>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                        <b style={{color:C.text}}>Помещения</b>
                        {isProrab()&&<button onClick={()=>{setShowRoomForm(!showRoomForm);setEditingItem(null);setNewRoom({project:p.name,name:'',floorArea:'',wallArea:'',ceilingArea:'',height:'',ceilingType:'Простой',wallMaterial:'Штукатурка',floorMaterial:'Стяжка',notes:''});}} style={btnO}><Plus size={14}/>Добавить</button>}
                      </div>
                      {showRoomForm&&(<div style={{...card,padding:'16px',marginBottom:'16px',backgroundColor:C.bg}}>
                        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
                          <input placeholder="Название *" value={newRoom.name} onChange={e=>setNewRoom({...newRoom,name:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Этаж (1,2,3...)" type="number" value={newRoom.floor||''} onChange={e=>setNewRoom({...newRoom,floor:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Литер (А,Б,В...)" value={newRoom.liter||''} onChange={e=>setNewRoom({...newRoom,liter:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <select value={newRoom.roomType||'Комната'} onChange={e=>setNewRoom({...newRoom,roomType:e.target.value})} style={{...inp,marginBottom:0}}>
                            {[...'Комната,Кабинет,Коридор,Санузел,Кухня,Балкон,Лестница,Холл,Техническое'.split(','),...customRoomTypes,'Другое'].map(t=><option key={t}>{t}</option>)}
                          {(newRoom.roomType==='Другое'||(!['Комната','Кабинет','Коридор','Санузел','Кухня','Балкон','Лестница','Холл','Техническое','Другое',''].includes(newRoom.roomType||'Комната')))&&<input placeholder='Введите своё название' value={newRoom.roomType==='Другое'?'':newRoom.roomType||''} onChange={e=>setNewRoom({...newRoom,roomType:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>}
                          </select>
                          <input placeholder="Высота (м)" type="number" value={newRoom.height} onChange={e=>setNewRoom({...newRoom,height:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Площадь пола (м2)" type="number" value={newRoom.floorArea} onChange={e=>setNewRoom({...newRoom,floorArea:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Площадь стен (м2)" type="number" value={newRoom.wallArea} onChange={e=>setNewRoom({...newRoom,wallArea:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Площадь потолка (м2)" type="number" value={newRoom.ceilingArea} onChange={e=>setNewRoom({...newRoom,ceilingArea:e.target.value})} style={{...inp,marginBottom:0}}/>
                          
                          
                          
                        </div>
                        <div style={{display:'flex',gap:'8px',marginTop:'10px'}}><button onClick={saveRoom} style={btnO}><Check size={14}/>{editingItem?'Сохранить':'Добавить'}</button><button onClick={()=>{setShowRoomForm(false);setEditingItem(null);}} style={btnG}><X size={14}/>Отмена</button></div>
                  </div>)}
                      {rooms.filter(r=>r.project===p.name).map(room=>{
                        const wins=roomWindows.filter(w=>w.room_id===room.id);
                        const doors=roomDoors.filter(d=>d.room_id===room.id);
                        const netWall=getRoomNetWall(room);
                        const winRevTotal=wins.reduce((s,w)=>s+calcWindowReveals(w),0);
                        const doorRevTotal=doors.reduce((s,d)=>s+calcDoorReveals(d),0);
                        const isRoomOpen=expandedRoom===room.id;
                        return(<div key={room.id} style={{...card,marginBottom:'10px'}}>
                          <div style={{padding:'14px',cursor:'pointer',display:'flex',justifyContent:'space-between',alignItems:'center'}} onClick={()=>setExpandedRoom(isRoomOpen?null:room.id)}>
                            <div><b style={{color:C.text,fontSize:'13px'}}>{room.name}</b>{room.floor&&<span style={{fontSize:'11px',color:C.accent,marginLeft:'6px',padding:'1px 6px',backgroundColor:C.accentLight,borderRadius:'4px'}}>{'Эт.'+room.floor+(room.liter?' Лит.'+room.liter:'')}</span>}{room.roomType&&<span style={{fontSize:'11px',color:C.textSec,marginLeft:'4px'}}>{'· '+room.roomType}</span>}<p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{'Пол: '+room.floorArea+'м² · Стены: '+room.wallArea+'м² (чистые: '+netWall+'м²) · Потолок: '+room.ceilingArea+'м²'}</p><p style={{color:C.textSec,margin:'0',fontSize:'11px'}}>{'Окна: '+wins.length+'шт · Двери: '+doors.length+'шт'+(winRevTotal>0?' · Откосы окон: '+winRevTotal+'м²':'')+(doorRevTotal>0?' · Откосы дверей: '+doorRevTotal+'м²':'')}</p></div>
                            <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
                              {isProrab()&&(<><button onClick={e=>{e.stopPropagation();setEditingItem(room);setNewRoom({project:room.project,name:room.name,floorArea:room.floorArea,wallArea:room.wallArea,ceilingArea:room.ceilingArea,height:room.height||'',ceilingType:room.ceiling_type||room.ceilingType||'Простой',wallMaterial:room.wall_material||room.wallMaterial||'Штукатурка',floorMaterial:room.floor_material||room.floorMaterial||'Стяжка',notes:room.notes||''});setShowRoomForm(true);}} style={{...btnG,padding:'4px 8px'}}><Edit2 size={11}/></button><button onClick={e=>{e.stopPropagation();deleteRoom(room.id);}} style={{...btnR,padding:'4px 8px'}}><Trash2 size={11}/></button></>)}
                              {isRoomOpen?<ChevronUp size={16} color={C.textMuted}/>:<ChevronDown size={16} color={C.textMuted}/>}
                            </div>
                          </div>
                          {isRoomOpen&&(<div style={{borderTop:'1.5px solid '+C.border,padding:'14px'}}>
                            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'16px'}}>
                              <div>
                                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'10px'}}>
                                  <b style={{color:C.text,fontSize:'13px'}}>🪟 Окна</b>
                                  <button onClick={()=>setNewWindow({roomId:room.id,name:'Окно '+(wins.length+1),width:'',height:'',windowType:'ПВХ',revealDepth:'',revealMaterial:'Штукатурка'})} style={{...btnO,padding:'4px 10px',fontSize:'11px'}}><Plus size={11}/>Добавить</button>
                                </div>
                                {wins.map(w=>(<div key={w.id} style={{padding:'8px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border}}>
                                  {editingWindow===w.id?(<div>
                                    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'6px',marginBottom:'8px'}}>
                                      <input placeholder="Название" value={w.name} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,name:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <select value={w.window_type||w.windowType||'ПВХ'} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,window_type:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}>{WINDOW_TYPES.map(t=><option key={t}>{t}</option>)}</select>
                                      <input placeholder="Ширина (м)" type="number" value={w.width} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,width:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <input placeholder="Высота (м)" type="number" value={w.height} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,height:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <input placeholder="Откос (см)" type="number" value={w.reveal_depth||w.revealDepth||''} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,reveal_depth:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <select value={w.reveal_material||w.revealMaterial||'Штукатурка'} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,reveal_material:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}>{REVEAL_MATERIALS.map(t=><option key={t}>{t}</option>)}</select>
                                    </div>
                                    <div style={{display:'flex',gap:'6px'}}><button onClick={()=>updateWindow(w)} style={{...btnGr,padding:'4px 10px',fontSize:'11px'}}><Check size={11}/>Сохранить</button><button onClick={()=>setEditingWindow(null)} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}><X size={11}/>Отмена</button></div>
                                  </div>):(<div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                                    <div><b style={{fontSize:'12px',color:C.text}}>{w.name}</b><p style={{color:C.textSec,margin:'1px 0',fontSize:'11px'}}>{(w.window_type||w.windowType||'ПВХ')+' '+w.width+'×'+w.height+'м = '+calcWindowArea(w).toFixed(2)+'м²'}</p>{calcWindowReveals(w)>0&&<p style={{color:C.info,margin:'0',fontSize:'10px'}}>{'Откосы: '+calcWindowReveals(w).toFixed(2)+'м² ('+((w.reveal_depth||w.revealDepth)||0)+'см)'}</p>}</div>
                                    <div style={{display:'flex',gap:'4px'}}><button onClick={()=>setEditingWindow(w.id)} style={{...btnG,padding:'3px 7px'}}><Edit2 size={10}/></button><button onClick={()=>deleteWindow(w.id)} style={{...btnR,padding:'3px 7px'}}><Trash2 size={10}/></button></div>
                  </div>)}
                                </div>))}
                                {newWindow.roomId===room.id&&(<div style={{padding:'10px',backgroundColor:C.accentLight,borderRadius:'8px',border:'1.5px solid '+C.accentBorder}}>
                                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'6px',marginBottom:'8px'}}>
                                    <input placeholder="Название" value={newWindow.name} onChange={e=>setNewWindow({...newWindow,name:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <select value={newWindow.windowType} onChange={e=>setNewWindow({...newWindow,windowType:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>{WINDOW_TYPES.map(t=><option key={t}>{t}</option>)}</select>
                                    <input placeholder="Ширина (м)" type="number" value={newWindow.width} onChange={e=>setNewWindow({...newWindow,width:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <input placeholder="Высота (м)" type="number" value={newWindow.height} onChange={e=>setNewWindow({...newWindow,height:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <input placeholder="Откос (см)" type="number" value={newWindow.revealDepth} onChange={e=>setNewWindow({...newWindow,revealDepth:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <select value={newWindow.revealMaterial} onChange={e=>setNewWindow({...newWindow,revealMaterial:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>{REVEAL_MATERIALS.map(t=><option key={t}>{t}</option>)}</select>
                                  </div>
                                  <div style={{display:'flex',gap:'6px'}}><button onClick={()=>saveWindow(room.id)} style={{...btnO,padding:'5px 12px',fontSize:'11px'}}><Check size={11}/>Добавить</button><button onClick={()=>setNewWindow({roomId:'',name:'Окно 1',width:'',height:'',windowType:'ПВХ',revealDepth:'',revealMaterial:'Штукатурка'})} style={{...btnG,padding:'5px 12px',fontSize:'11px'}}><X size={11}/>Отмена</button></div>
                  </div>)}
                              </div>
                              <div>
                                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'10px'}}>
                                  <b style={{color:C.text,fontSize:'13px'}}>🚪 Двери</b>
                                  <button onClick={()=>setNewDoor({roomId:room.id,name:'Дверь '+(doors.length+1),width:'',height:'',doorType:'Деревянная',doorPurpose:'Межкомнатная',revealDepth:'',revealMaterial:'Штукатурка'})} style={{...btnO,padding:'4px 10px',fontSize:'11px'}}><Plus size={11}/>Добавить</button>
                                </div>
                                {doors.map(d=>(<div key={d.id} style={{padding:'8px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border}}>
                                  {editingDoor===d.id?(<div>
                                    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'6px',marginBottom:'8px'}}>
                                      <input placeholder="Название" value={d.name} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,name:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <select value={d.door_type||d.doorType||'Деревянная'} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,door_type:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}>{DOOR_TYPES.map(t=><option key={t}>{t}</option>)}</select>
                                      <select value={d.door_purpose||d.doorPurpose||'Межкомнатная'} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,door_purpose:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}>{DOOR_PURPOSES.map(t=><option key={t}>{t}</option>)}</select>
                                      <input placeholder="Ширина (м)" type="number" value={d.width} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,width:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <input placeholder="Высота (м)" type="number" value={d.height} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,height:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <input placeholder="Откос (см)" type="number" value={d.reveal_depth||d.revealDepth||''} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,reveal_depth:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <select value={d.reveal_material||d.revealMaterial||'Штукатурка'} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,reveal_material:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}>{REVEAL_MATERIALS.map(t=><option key={t}>{t}</option>)}</select>
                                    </div>
                                    <div style={{display:'flex',gap:'6px'}}><button onClick={()=>updateDoor(d)} style={{...btnGr,padding:'4px 10px',fontSize:'11px'}}><Check size={11}/>Сохранить</button><button onClick={()=>setEditingDoor(null)} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}><X size={11}/>Отмена</button></div>
                                  </div>):(<div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                                    <div><b style={{fontSize:'12px',color:C.text}}>{d.name}</b><p style={{color:C.textSec,margin:'1px 0',fontSize:'11px'}}>{(d.door_type||d.doorType||'')+(d.door_purpose||d.doorPurpose?'/'+(d.door_purpose||d.doorPurpose):'')+ ' '+d.width+'×'+d.height+'м = '+calcDoorArea(d).toFixed(2)+'м²'}</p>{calcDoorReveals(d)>0&&<p style={{color:C.info,margin:'0',fontSize:'10px'}}>{'Откосы: '+calcDoorReveals(d).toFixed(2)+'м² ('+((d.reveal_depth||d.revealDepth)||0)+'см)'}</p>}</div>
                                    <div style={{display:'flex',gap:'4px'}}><button onClick={()=>setEditingDoor(d.id)} style={{...btnG,padding:'3px 7px'}}><Edit2 size={10}/></button><button onClick={()=>deleteDoor(d.id)} style={{...btnR,padding:'3px 7px'}}><Trash2 size={10}/></button></div>
                  </div>)}
                                </div>))}
                                {newDoor.roomId===room.id&&(<div style={{padding:'10px',backgroundColor:C.accentLight,borderRadius:'8px',border:'1.5px solid '+C.accentBorder}}>
                                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'6px',marginBottom:'8px'}}>
                                    <input placeholder="Название" value={newDoor.name} onChange={e=>setNewDoor({...newDoor,name:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <select value={newDoor.doorType} onChange={e=>setNewDoor({...newDoor,doorType:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>{DOOR_TYPES.map(t=><option key={t}>{t}</option>)}</select>
                                    <select value={newDoor.doorPurpose} onChange={e=>setNewDoor({...newDoor,doorPurpose:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>{DOOR_PURPOSES.map(t=><option key={t}>{t}</option>)}</select>
                                    <input placeholder="Ширина (м)" type="number" value={newDoor.width} onChange={e=>setNewDoor({...newDoor,width:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <input placeholder="Высота (м)" type="number" value={newDoor.height} onChange={e=>setNewDoor({...newDoor,height:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <input placeholder="Откос (см)" type="number" value={newDoor.revealDepth} onChange={e=>setNewDoor({...newDoor,revealDepth:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <select value={newDoor.revealMaterial} onChange={e=>setNewDoor({...newDoor,revealMaterial:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>{REVEAL_MATERIALS.map(t=><option key={t}>{t}</option>)}</select>
                                  </div>
                                  <div style={{display:'flex',gap:'6px'}}><button onClick={()=>saveDoor(room.id)} style={{...btnO,padding:'5px 12px',fontSize:'11px'}}><Check size={11}/>Добавить</button><button onClick={()=>setNewDoor({roomId:'',name:'Дверь 1',width:'',height:'',doorType:'Деревянная',doorPurpose:'Межкомнатная',revealDepth:'',revealMaterial:'Штукатурка'})} style={{...btnG,padding:'5px 12px',fontSize:'11px'}}><X size={11}/>Отмена</button></div>
                  </div>)}
                              </div>
                            </div>
                  </div>)}
                        </div>);
                      })}
                      {rooms.filter(r=>r.project===p.name).length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'20px'}}>Помещений нет</p>}
                  </div>)}

                    {activeProjectTab==='Чек-листы'&&(<div>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                        <b style={{color:C.text}}>Чек-листы</b>
                        {isProrab()&&<button onClick={()=>setShowForm(showForm==='checklist'?false:'checklist')} style={btnO}><Plus size={14}/>Создать</button>}
                      </div>
                      {showForm==='checklist'&&(<div style={{...card,padding:'16px',marginBottom:'16px',backgroundColor:C.bg}}>
                        <input placeholder="Название чек-листа *" value={newChecklist.name} onChange={e=>setNewChecklist({...newChecklist,name:e.target.value})} style={inp}/>
                        <select value={newChecklist.template} onChange={e=>setNewChecklist({...newChecklist,template:e.target.value,name:e.target.value||newChecklist.name})} style={inp}><option value="">Свой чек-лист</option>{Object.keys(CHECKLIST_TEMPLATES).map(t=><option key={t} value={t}>{t}</option>)}</select>
                        <div style={{display:'flex',gap:'8px'}}><button onClick={()=>saveChecklist(p.id,p.name)} style={btnO}><Check size={14}/>Создать</button><button onClick={()=>setShowForm(false)} style={btnG}><X size={14}/>Отмена</button></div>
                  </div>)}
                      {checklists.filter(cl=>cl.projectName===p.name).map(cl=>{
                        const items=checklistItems[cl.id]||[];
                        const checked=items.filter(i=>i.checked).length;
                        const isOpen=selectedChecklist===cl.id;
                        return(<div key={cl.id} style={{...card,marginBottom:'10px'}}>
                          <div style={{padding:'14px',cursor:'pointer',display:'flex',justifyContent:'space-between',alignItems:'center'}} onClick={async()=>{if(isOpen){setSelectedChecklist(null);}else{setSelectedChecklist(cl.id);await loadChecklistItems(cl.id);}}}>
                            <div><b style={{color:C.text,fontSize:'13px'}}>{cl.name}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{checked+'/'+items.length+' выполнено'}</p></div>
                            <div style={{display:'flex',alignItems:'center',gap:'10px'}}>
                              <div style={{backgroundColor:C.bgGray,borderRadius:'10px',height:'8px',width:'80px'}}><div style={{backgroundColor:items.length>0&&checked===items.length?C.success:C.accent,width:(items.length>0?checked/items.length*100:0)+'%',height:'100%',borderRadius:'10px'}}/></div>
                              {isOpen?<ChevronUp size={16} color={C.textMuted}/>:<ChevronDown size={16} color={C.textMuted}/>}
                            </div>
                          </div>
                          {isOpen&&(<div style={{borderTop:'1.5px solid '+C.border,padding:'12px 14px'}}>
                            {items.map(item=>(<div key={item.id} style={{display:'flex',alignItems:'center',gap:'10px',padding:'8px 0',borderBottom:'1px solid '+C.border}}>
                              <input type="checkbox" checked={item.checked} onChange={()=>toggleChecklistItem(item)} style={{width:'18px',height:'18px',accentColor:C.accent,cursor:'pointer'}}/>
                              <span style={{fontSize:'13px',color:item.checked?C.textMuted:C.text,textDecoration:item.checked?'line-through':'none',flex:1}}>{item.name}</span>
                              {item.checked&&item.checkedBy&&<span style={{fontSize:'11px',color:C.textMuted}}>{item.checkedBy}</span>}
                            </div>))}
                            <div style={{display:'flex',gap:'8px',marginTop:'10px'}}>
                              <input placeholder="Добавить пункт..." value={newChecklistItem} onChange={e=>setNewChecklistItem(e.target.value)} style={{...inp,marginBottom:0,flex:1,fontSize:'12px'}}/>
                              <button onClick={async()=>{if(!newChecklistItem) return;await fetch(API+'/checklist-items',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({checklistId:cl.id,name:newChecklistItem,checked:false,orderNum:items.length})});await loadChecklistItems(cl.id);setNewChecklistItem('');}} style={{...btnO,padding:'6px 12px'}}><Plus size={13}/></button>
                            </div>
                  </div>)}
                        </div>);
                      })}
                      {checklists.filter(cl=>cl.projectName===p.name).length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'20px'}}>Чек-листов нет</p>}
                  </div>)}

                    {activeProjectTab==='Непредвиденные'&&(<div>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                        <b style={{color:C.text}}>Непредвиденные работы</b>
                        <button onClick={()=>setShowForm(showForm==='unexpected'?false:'unexpected')} style={btnO}><Plus size={14}/>Добавить</button>
                      </div>
                      {showForm==='unexpected'&&(<div style={{...card,padding:'16px',marginBottom:'16px',backgroundColor:C.bg}}>
                        <textarea placeholder="Описание работы *" value={newUnexpected.description} onChange={e=>setNewUnexpected({...newUnexpected,description:e.target.value})} style={{...inp,height:'80px',resize:'vertical'}}/>
                        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:'8px'}}>
                          <input placeholder="Кол-во" type="number" value={newUnexpected.quantity} onChange={e=>setNewUnexpected({...newUnexpected,quantity:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <select value={newUnexpected.unit} onChange={e=>setNewUnexpected({...newUnexpected,unit:e.target.value})} style={{...inp,marginBottom:0}}>{UNITS.map(u=><option key={u}>{u}</option>)}</select>
                          <input placeholder="Цена (₽)" type="number" value={newUnexpected.price} onChange={e=>setNewUnexpected({...newUnexpected,price:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                        <div style={{display:'flex',gap:'8px',alignItems:'center',marginTop:'8px'}}>
                          <label style={{...btnB,padding:'8px 12px',fontSize:'12px',cursor:'pointer'}}><Upload size={12}/>{newUnexpected.photoUrl?'📷 Фото добавлено':'📷 Прикрепить фото'}<input type='file' accept='image/*' style={{display:'none'}} onChange={async e=>{const f=e.target.files[0];if(f){const url=await uploadPhoto(f);if(url) setNewUnexpected({...newUnexpected,photoUrl:url});}}}/></label>
                          {newUnexpected.photoUrl&&<button onClick={()=>setNewUnexpected({...newUnexpected,photoUrl:''})} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}><X size={11}/></button>}
                        </div>
                        <div style={{display:'flex',gap:'8px',marginTop:'10px'}}><button onClick={()=>saveUnexpectedWork(p.name)} style={btnO}><Check size={14}/>Отправить</button><button onClick={()=>setShowForm(false)} style={btnG}><X size={14}/>Отмена</button></div>
                  </div>)}
                      {['Ожидает согласования','Утверждено','Отклонено'].map(status=>{ const items=unexpectedWorksList.filter(u=>u.projectName===p.name&&u.status===status); if(items.length===0) return null; return(<div key={status} style={{marginBottom:'16px'}}><b style={{color:status==='Утверждено'?C.success:status==='Отклонено'?C.danger:C.warning,fontSize:'12px',display:'block',marginBottom:'8px'}}>{status==='Ожидает согласования'?'⏳':status==='Утверждено'?'✅':'❌'} {status} ({items.length})</b>{items.map(u=>(<div key={u.id} style={{padding:'12px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border}}><div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}><div><b style={{fontSize:'13px',color:C.text}}>{u.description}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{u.quantity+' '+u.unit+(u.price>0?' · '+u.price.toLocaleString()+' ₽/'+u.unit:'')+(u.total>0?' · Итого: '+u.total.toLocaleString()+' ₽':'')}</p><p style={{color:C.textMuted,margin:'0',fontSize:'11px'}}>{'Добавил: '+u.addedBy}</p></div>{isLeadership()&&u.status==='Ожидает согласования'&&(<div style={{display:'flex',gap:'6px',alignItems:'center'}}><input placeholder="Цена ₽" type="number" style={{width:'90px',padding:'4px 8px',border:'1.5px solid '+C.border,borderRadius:'6px',fontSize:'12px'}} onChange={e=>e.target.dataset.price=e.target.value}/><button onClick={e=>{approveUnexpectedWork(u,e.target.previousSibling.dataset.price||0);}} style={{...btnGr,padding:'4px 8px',fontSize:'11px'}}><Check size={11}/>Утвердить</button><button onClick={async()=>{await fetch(API+'/unexpected-works/'+u.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Отклонено',approvedBy:user.name,approvedAt:new Date().toISOString().split('T')[0]})});await loadAll();}} style={{...btnR,padding:'4px 8px',fontSize:'11px'}}><X size={11}/>Откл.</button></div>)}</div></div>))}</div>);})}
                      {unexpectedWorksList.filter(u=>u.projectName===p.name).length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'20px'}}>Непредвиденных работ нет</p>}
                  </div>)}

                    {activeProjectTab==='Наряды'&&(<div><div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}><b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Наряды и бригады</b><button onClick={()=>setShowBrigadeForm(!showBrigadeForm)} style={btnO}><Plus size={14}/>Новый наряд</button></div>{showBrigadeForm&&(<div style={{...card,padding:'20px',marginBottom:'16px'}}><div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}><select value={newBrigadeContract.contractorType} onChange={e=>setNewBrigadeContract({...newBrigadeContract,contractorType:e.target.value})} style={{...inp,marginBottom:0}}>{['Своя бригада','Субподрядчик','Мастер'].map(t=><option key={t}>{t}</option>)}</select><input placeholder='Название / ФИО *' value={newBrigadeContract.brigadeName} onChange={e=>setNewBrigadeContract({...newBrigadeContract,brigadeName:e.target.value})} style={{...inp,marginBottom:0}}/>{newBrigadeContract.contractorType!=='Субподрядчик'&&<select value={newBrigadeContract.contractorId} onChange={e=>setNewBrigadeContract({...newBrigadeContract,contractorId:e.target.value})} style={{...inp,marginBottom:0}}><option value=''>Привязать к сотруднику</option>{staff.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select>}<select value={newBrigadeContract.pricelistId||''} onChange={e=>setNewBrigadeContract({...newBrigadeContract,pricelistId:e.target.value})} style={{...inp,marginBottom:0}}><option value=''>🏷️ Прайс бригады (по умолчанию — прайс объекта)</option>{pricelists.map(pl=><option key={pl.id} value={pl.id}>{pl.name}{pl.forWho?' ('+pl.forWho+')':''}</option>)}</select><textarea placeholder='Примечание' value={newBrigadeContract.notes} onChange={e=>setNewBrigadeContract({...newBrigadeContract,notes:e.target.value})} style={{...inp,marginBottom:0,height:'60px'}}/></div><div style={{display:'flex',gap:'8px',marginTop:'12px'}}><button onClick={async()=>{if(!newBrigadeContract.brigadeName) return;const data={...newBrigadeContract,projectId:p.id,projectName:p.name};const res=await fetch(API+'/brigade-contracts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const saved=await res.json();const newBC={...data,id:saved.id,totalAmount:0,status:'Черновик',items:[]};setBrigadeContracts(prev=>[...prev,newBC]);setSelectedBrigadeContract(newBC);setBrigadeContractItems([]);setShowBrigadeForm(false);setNewBrigadeContract({projectId:'',projectName:'',brigadeName:'',contractorType:'Своя бригада',contractorId:'',notes:'',pricelistId:''});}} style={btnO}><Check size={14}/>Создать</button><button onClick={()=>setShowBrigadeForm(false)} style={btnG}><X size={14}/>Отмена</button></div></div>)}{selectedBrigadeContract?(<div><div style={{display:'flex',gap:'8px',marginBottom:'15px',alignItems:'center',flexWrap:'wrap'}}><button onClick={()=>{setSelectedBrigadeContract(null);setBrigadeContractItems([]);}} style={btnG}><ArrowLeft size={14}/>Назад</button><b style={{color:C.text,fontSize:'14px'}}>{selectedBrigadeContract.brigadeName}</b><span style={{padding:'3px 8px',borderRadius:'6px',fontSize:'11px',backgroundColor:C.accentLight,color:C.accent}}>{selectedBrigadeContract.contractorType}</span>{selectedBrigadeContract.status!=='Подписан'&&<button onClick={async()=>{await fetch(API+'/brigade-contracts/'+selectedBrigadeContract.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...selectedBrigadeContract,status:'Подписан',signedAt:new Date().toISOString().split('T')[0]})});setSelectedBrigadeContract({...selectedBrigadeContract,status:'Подписан'});setBrigadeContracts(prev=>prev.map(bc=>bc.id===selectedBrigadeContract.id?{...bc,status:'Подписан'}:bc));}} style={btnO}><Check size={14}/>Подписать</button>}<button onClick={()=>{const html='<h2>ДОГОВОР ПОДРЯДА</h2><p>Объект: '+p.name+'</p><p>Исполнитель: '+selectedBrigadeContract.brigadeName+'</p><table><tr><th>N</th><th>Наименование</th><th>Ед.</th><th>Объём</th><th>Цена</th><th>Сумма</th></tr>'+brigadeContractItems.map((it,i)=>'<tr><td>'+(i+1)+'</td><td>'+it.name+'</td><td>'+it.unit+'</td><td>'+it.quantity+'</td><td>'+Number(it.priceBrigade).toLocaleString()+'</td><td>'+Math.round(it.quantity*it.priceBrigade).toLocaleString()+'</td></tr>').join('')+'<tr><td colspan=5><b>ИТОГО:</b></td><td><b>'+brigadeContractItems.reduce((s,i)=>s+i.quantity*i.priceBrigade,0).toLocaleString()+' руб.</b></td></tr></table>';showPreview(html,'Договор');}} style={btnB}><Eye size={14}/>Договор</button>{selectedBrigadeContract.pricelistId&&(<button onClick={async()=>{const res=await fetch(API+'/brigade-contracts/'+selectedBrigadeContract.id+'/load-from-pricelist',{method:'POST'});const data=await res.json();if(!res.ok||!data.ok){alert('Ошибка: '+(data.detail||'не удалось'));return;}const items=await fetch(API+'/brigade-contract-items/'+selectedBrigadeContract.id).then(r=>r.json());setBrigadeContractItems(items);alert('Загружено позиций: '+data.itemsLoaded+(data.matchedFromEstimate?'\nОбъёмы взяты из сметы: '+data.matchedFromEstimate:''));}} style={{border:'none',borderRadius:'10px',padding:'8px 16px',cursor:'pointer',background:'linear-gradient(135deg, #10b981, #059669)',color:'white',fontWeight:'600',fontSize:'13px',display:'flex',alignItems:'center',gap:'6px',boxShadow:'0 2px 8px rgba(16,185,129,0.3)'}}><Download size={14}/>Подгрузить из прайса</button>)}</div>{(()=>{const sBri=brigadeContractItems.reduce((s,i)=>s+Number(i.quantity||0)*Number(i.priceBrigade||0),0);const sSm=brigadeContractItems.reduce((s,i)=>s+Number(i.quantity||0)*Number(i.priceSmeta||0),0);const eco=sSm-sBri;if(sBri===0&&sSm===0){return(<div style={{...card,padding:'14px',marginBottom:'16px',backgroundColor:C.bg,border:'1.5px dashed '+C.border,textAlign:'center'}}><p style={{margin:0,color:C.textMuted,fontSize:'13px'}}>📋 Наряд пустой. Нажмите <b>«Подгрузить из прайса»</b> или добавьте позиции вручную ниже.</p></div>);}return(<div style={{...card,padding:'16px',marginBottom:'16px',backgroundColor:C.accentLight,border:'1.5px solid '+C.accentBorder}}><div style={{display:'grid',gridTemplateColumns:isFinanceRole()?'repeat(3,1fr)':'1fr',gap:'12px'}}><div><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 4px'}}>Бригаде по договору</p><b style={{color:C.accent,fontSize:'16px'}}>{sBri.toLocaleString('ru-RU')+' ₽'}</b></div><div style={{display:isFinanceRole()?'block':'none'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 4px'}}>По смете заказчика</p><b style={{color:C.text,fontSize:'16px'}}>{sSm.toLocaleString('ru-RU')+' ₽'}</b></div><div style={{display:isFinanceRole()?'block':'none'}}><p style={{color:C.textSec,fontSize:'12px',margin:'0 0 4px'}}>Экономия</p><b style={{color:eco>0?C.success:C.textMuted,fontSize:'16px'}}>{eco.toLocaleString('ru-RU')+' ₽'}</b></div></div></div>);})()}<div style={{...card,padding:'16px',marginBottom:'16px'}}><div style={{marginBottom:'12px'}}>
{estimatesList.filter(e=>e.projectName===p.name||e.projectId===p.id).length>0&&(<div><p style={{color:C.textSec,fontSize:'12px',marginBottom:'6px'}}>Загрузить из сметы:</p><div style={{display:'flex',gap:'6px',flexWrap:'wrap'}}>{estimatesList.filter(e=>e.projectName===p.name||e.projectId===p.id).map(est=>(<button key={est.id} onClick={async()=>{if(!window.confirm('Загрузить '+((est.sections||[]).flatMap(s=>s.items||[]).length)+' позиций из сметы '+est.name+'?')) return;const allItems=(est.sections||[]).flatMap(s=>(s.items||[]).map(i=>({...i,estimateSection:s.name}))).filter(i=>{
  const n=(i.name||'').toLowerCase();
  const u=(i.unit||'');
  if(u==='%') return false;
  const matWords=['кабель','провод','труба','трубы','лоток','короб','розетка','выключатель','светильник','щит','шина','соединитель','кронштейн','уголок','переходник','консоль','держатель','болт','гайка','дюбель','профиль','плита','панель','муфта','тройник','отвод','клапан','вентиль','кран','датчик','грунтовка','клей','раствор','смесь','краска','лак','герметик','пена','мастика','шпатлевка','плитка','кирпич','утеплитель','пленка','анкер','саморез','скоба','хомут','проволока','изолятор','автомат','рубильник','реле','счетчик'];
  if(matWords.some(w=>n.startsWith(w))) return false;
  const workWords=['устройство','монтаж','прокладка','установка','разборка','пробивка','сверление','окраска','штукатурка','кладка','демонтаж','погрузка','перевозка','очистка','покрытие','изоляция','сборка','укладка','ремонт','снятие','затаривание','огрунтовка','добавлять','исключать','смена','третья шпатлевка','вторая шпатлевка'];
  return workWords.some(w=>n.includes(w));
});for(const item of allItems){const newItem={contractId:selectedBrigadeContract.id,estimateSection:item.estimateSection||'',name:item.name,unit:item.unit,quantity:item.quantity||0,priceSmeta:item.priceWork||0,priceBrigade:0,doneQuantity:0,status:'Не начато'};const res=await fetch(API+'/brigade-contract-items',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(newItem)});const saved=await res.json();setBrigadeContractItems(prev=>[...prev,{...newItem,id:saved.id}]);}alert('Загружено!');}} style={{...btnG,fontSize:'11px',padding:'5px 10px'}}>{{Заказчик:'📋',Работы:'👷',Материалы:'📦'}[est.smetaType]||'📄'} {est.name}</button>))}</div></div>)}
</div>
<b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'10px'}}>Добавить работу вручную</b><div style={{display:'grid',gridTemplateColumns:'3fr 1fr 1fr 1fr 1fr auto',gap:'6px',alignItems:'center'}}><input placeholder='Наименование *' value={newBrigadeItem.name} onChange={e=>setNewBrigadeItem({...newBrigadeItem,name:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/><select value={newBrigadeItem.unit} onChange={e=>setNewBrigadeItem({...newBrigadeItem,unit:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>{UNITS.map(u=><option key={u}>{u}</option>)}</select><input placeholder='Объём' type='number' value={newBrigadeItem.quantity} onChange={e=>setNewBrigadeItem({...newBrigadeItem,quantity:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/><input placeholder='Цена смета' type='number' value={newBrigadeItem.priceSmeta} onChange={e=>setNewBrigadeItem({...newBrigadeItem,priceSmeta:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/><input placeholder='Цена бригаде' type='number' value={newBrigadeItem.priceBrigade} onChange={e=>setNewBrigadeItem({...newBrigadeItem,priceBrigade:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/><button onClick={async()=>{if(!newBrigadeItem.name||!selectedBrigadeContract) return;const item={...newBrigadeItem,contractId:selectedBrigadeContract.id,doneQuantity:0,status:'Не начато'};const res=await fetch(API+'/brigade-contract-items',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(item)});const saved=await res.json();setBrigadeContractItems(prev=>[...prev,{...item,id:saved.id}]);setNewBrigadeItem({name:'',unit:'м',quantity:'',priceSmeta:'',priceBrigade:'',estimateSection:''});}} style={{...btnO,padding:'7px 12px'}}><Plus size={13}/></button></div></div><div style={{...card,padding:'12px 16px',marginBottom:'8px',backgroundColor:C.bg,display:isLeadership()?'flex':'none',gap:'10px',alignItems:'center',flexWrap:'wrap'}}>
              <b style={{color:C.text,fontSize:'13px'}}>Массовое выставление цены:</b>
              <span style={{fontSize:'12px',color:C.textSec}}>Коэффициент от сметной цены:</span>
              <input type='number' value={brigadeCoef} onChange={e=>setBrigadeCoef(e.target.value)} style={{...inp,marginBottom:0,width:'80px',fontSize:'12px',padding:'4px 8px'}} step='0.05' min='0.1' max='1'/>
              <span style={{fontSize:'12px',color:C.textSec}}>({Math.round(brigadeCoef*100)}% от сметы)</span>
              <button onClick={async()=>{
                if(!window.confirm('Применить коэффициент '+brigadeCoef+' ко всем позициям?')) return;
                const updated = brigadeContractItems.map(item=>({...item,priceBrigade:Math.round(Number(item.priceSmeta||0)*Number(brigadeCoef||0.6))}));
                setBrigadeContractItems(updated);
                for(const item of updated){
                  await fetch(API+'/brigade-contract-items/'+item.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(item)});
                }
                alert('Цены обновлены!');
              }} style={{...btnO,padding:'6px 14px',fontSize:'12px'}}>Применить ко всем</button>
              <button onClick={async()=>{
                if(!window.confirm('Сбросить все цены бригаде в 0?')) return;
                const updated = brigadeContractItems.map(item=>({...item,priceBrigade:0}));
                setBrigadeContractItems(updated);
                for(const item of updated){
                  await fetch(API+'/brigade-contract-items/'+item.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(item)});
                }
              }} style={{...btnG,padding:'6px 14px',fontSize:'12px'}}>Сбросить цены</button>
            </div>
            <table style={tbl}><thead><tr><th style={tblH}>Наименование</th><th style={tblH}>Ед.</th><th style={tblH}>План</th><th style={tblH}>Выполнено</th><th style={tblH}>Осталось</th><th style={tblH}>%</th><th style={{...tblH,display:isFinanceRole()?'':'none'}}>Цена смета</th><th style={tblH}>Цена бригаде</th><th style={tblH}>К оплате</th><th style={{...tblH,display:isFinanceRole()?'':'none'}}>Экономия</th><th style={tblH}></th></tr></thead><tbody>{brigadeContractItems.map((item,idx)=>{const pct=item.quantity>0?Math.round(item.doneQuantity/item.quantity*100):0;const toPay=Math.round(item.doneQuantity*item.priceBrigade);const economy=Math.round(item.doneQuantity*(item.priceSmeta-item.priceBrigade));const remain=Math.max(0,Number(item.quantity||0)-Number(item.doneQuantity||0));return(<tr key={item.id||idx}><td style={tblC}>{item.name}</td><td style={tblC}>{item.unit}</td><td style={tblC}><input type='number' value={item.quantity||''} onChange={async e=>{const val=Number(e.target.value)||0;const updated={...item,quantity:val};setBrigadeContractItems(prev=>prev.map((it,i)=>i===idx?updated:it));await fetch(API+'/brigade-contract-items/'+item.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...updated,quantity:val})});}} style={{...inp,marginBottom:0,width:'70px',fontSize:'12px',padding:'4px 6px'}}/></td><td style={tblC}><input type='number' value={item.doneQuantity||''} onChange={async e=>{const raw=Number(e.target.value);const plan=Number(item.quantity)||0;if(plan>0&&raw>plan){alert('По смете план '+plan+' '+(item.unit||'')+'. Нельзя поставить больше — это перебор по смете.');return;}const val=plan>0?Math.min(raw,plan):raw;const updated={...item,doneQuantity:val,status:plan>0&&val>=plan?'Выполнено':val>0?'В работе':'Не начато'};setBrigadeContractItems(prev=>prev.map((it,i)=>i===idx?updated:it));await fetch(API+'/brigade-contract-items/'+item.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(updated)});}} style={{...inp,marginBottom:0,width:'80px',fontSize:'12px',padding:'4px 6px'}}/></td><td style={{...tblC,color:remain>0?C.warning:C.success,fontWeight:'600'}}>{Number(item.quantity)>0?remain+' '+(item.unit||''):'—'}</td><td style={tblC}><span style={{padding:'2px 6px',borderRadius:'4px',fontSize:'11px',backgroundColor:pct>=100?C.successLight:pct>0?C.warningLight:C.bg,color:pct>=100?C.success:pct>0?C.warning:C.textMuted}}>{pct+'%'}</span></td><td style={{...tblC,display:isFinanceRole()?'':'none'}}>{Number(item.priceSmeta||0).toLocaleString('ru-RU')+' ₽'}</td><td style={tblC}>{Number(item.priceBrigade||0).toLocaleString('ru-RU')+' ₽'}</td><td style={{...tblC,fontWeight:'600',color:C.accent}}>{toPay.toLocaleString('ru-RU')+' ₽'}</td><td style={{...tblC,fontWeight:'600',color:C.success,display:isFinanceRole()?'':'none'}}>{economy.toLocaleString('ru-RU')+' ₽'}</td><td style={tblC}><button onClick={async()=>{await fetch(API+'/brigade-contract-items/'+item.id,{method:'DELETE'});setBrigadeContractItems(prev=>prev.filter((_,i)=>i!==idx));}} style={{...btnR,padding:'3px 7px'}}><Trash2 size={11}/></button></td></tr>);})}</tbody></table>{brigadeContractItems.length>0&&(<div style={{...card,padding:'16px',marginTop:'16px',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder}}><div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'12px'}}><div><b style={{color:C.text,fontSize:'14px'}}>К оплате бригаде:</b></div><div style={{textAlign:'right'}}><b style={{color:C.accent,fontSize:'18px',display:'block'}}>{brigadeContractItems.reduce((s,i)=>s+Math.round(i.doneQuantity*i.priceBrigade),0).toLocaleString()+' руб.'}</b><b style={{color:C.success,fontSize:'13px'}}>{'+'+brigadeContractItems.reduce((s,i)=>s+Math.round(i.doneQuantity*(i.priceSmeta-i.priceBrigade)),0).toLocaleString()+' руб. экономия'}</b></div></div><button onClick={()=>{const items=brigadeContractItems.filter(i=>i.doneQuantity>0);if(!items.length){alert('Нет выполненных работ');return;}const total=items.reduce((s,i)=>s+Math.round(i.doneQuantity*i.priceBrigade),0);const html='<h2>АКТ ВЫПОЛНЕННЫХ РАБОТ</h2><p>Объект: '+p.name+'</p><p>Исполнитель: '+selectedBrigadeContract.brigadeName+'</p><table><tr><th>N</th><th>Наименование</th><th>Ед.</th><th>Выполнено</th><th>Цена</th><th>Сумма</th></tr>'+items.map((it,i)=>'<tr><td>'+(i+1)+'</td><td>'+it.name+'</td><td>'+it.unit+'</td><td>'+it.doneQuantity+'</td><td>'+Number(it.priceBrigade).toLocaleString()+'</td><td>'+Math.round(it.doneQuantity*it.priceBrigade).toLocaleString()+'</td></tr>').join('')+'<tr><td colspan=5><b>ИТОГО:</b></td><td><b>'+total.toLocaleString()+' руб.</b></td></tr></table>';showPreview(html,'Акт');}} style={{...btnO,width:'100%',justifyContent:'center'}}><ScrollText size={14}/>Сформировать акт</button></div>)}</div>):(<div>{brigadeContracts.filter(bc=>bc.projectName===p.name).map(bc=>(<div key={bc.id} style={{...card,padding:'14px',marginBottom:'8px',display:'flex',justifyContent:'space-between',alignItems:'center',cursor:'pointer'}} onClick={async()=>{setSelectedBrigadeContract(bc);const res=await fetch(API+'/brigade-contract-items/'+bc.id);const items=await res.json();setBrigadeContractItems(items);}}><div><b style={{color:C.text,fontSize:'13px'}}>{bc.brigadeName}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{bc.contractorType+' - '+bc.status}</p></div><div style={{display:'flex',gap:'8px',alignItems:'center'}}><ChevronRight size={16} color={C.textMuted}/><button onClick={async e=>{e.stopPropagation();if(!window.confirm('Удалить наряд?')) return;await fetch(API+'/brigade-contracts/'+bc.id,{method:'DELETE'});setBrigadeContracts(prev=>prev.filter(b=>b.id!==bc.id));}} style={{...btnR,padding:'4px 8px'}}><Trash2 size={11}/></button></div></div>))}{!brigadeContracts.filter(bc=>bc.projectName===p.name).length&&(<div style={{...card,padding:'40px',textAlign:'center',color:C.textMuted}}><Users size={48} style={{marginBottom:'15px',opacity:0.3}}/><p>Нарядов нет</p></div>)}</div>)}</div>)}
                    {activeProjectTab==='Материалы'&&(<div>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                        <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Материалы объекта</b>
                        <div style={{display:'flex',gap:'8px'}}>
                          <button onClick={()=>openReceiveInvoice(p.name)} style={btnB}><Plus size={14}/>Принять материал</button>
                          <button onClick={async()=>{
                            const res=await fetch(API+'/material-transfers?project_name='+encodeURIComponent(p.name));
                            const data=await res.json();
                            setMaterialTransfers(Array.isArray(data)?data:[]);
                            setShowTransferForm(!showTransferForm);
                          }} style={btnO}><Plus size={14}/>Передать материал</button>
                        </div>
                      </div>

                      {showTransferForm&&(<div style={{...card,padding:'20px',marginBottom:'16px'}}>
                        <h3 style={{color:C.text,marginBottom:'15px',fontWeight:'700'}}>Передача материала бригаде/мастеру</h3>
                        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                          <select value={newTransfer.fromLocation} onChange={e=>setNewTransfer({...newTransfer,fromLocation:e.target.value,materialName:'',quantity:''})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}>
                            <option value='Основной склад'>Основной склад</option>
                            {projects.map(pr=><option key={pr.id} value={pr.name}>{pr.name}</option>)}
                          </select>
                          <div style={{gridColumn:'span 2'}}>
                            <p style={{fontSize:'12px',color:C.textSec,marginBottom:'6px'}}>Материалы на складе:</p>
                            <div style={{maxHeight:'200px',overflowY:'auto',border:'1.5px solid '+C.border,borderRadius:'8px',padding:'8px'}}>
                              {[...warehouseMain.filter(m=>m.location===newTransfer.fromLocation||(!m.location&&newTransfer.fromLocation==='Основной склад')),...materials.filter(m=>m.project===newTransfer.fromLocation)].map((m,i)=>(<div key={i} style={{display:'flex',alignItems:'center',gap:'8px',padding:'6px 0',borderBottom:'1px solid '+C.border}}>
                                <input type='checkbox' checked={newTransfer.materialName===m.name} onChange={e=>setNewTransfer({...newTransfer,materialName:e.target.checked?m.name:'',unit:e.target.checked?m.unit:newTransfer.unit,quantity:''})} style={{width:'16px',height:'16px',cursor:'pointer'}}/>
                                <span style={{flex:1,fontSize:'12px',color:C.text}}>{m.name}</span>
                                <span style={{fontSize:'11px',color:C.textSec}}>Остаток: {m.quantity} {m.unit}</span>
                              </div>))}
                              {[...warehouseMain.filter(m=>m.location===newTransfer.fromLocation||(!m.location&&newTransfer.fromLocation==='Основной склад')),...materials.filter(m=>m.project===newTransfer.fromLocation)].length===0&&<p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'10px'}}>Нет материалов на этом складе</p>}
                            </div>
                          </div>
                          {newTransfer.materialName&&(<div style={{display:'flex',gap:'6px',gridColumn:'span 2',alignItems:'center'}}>
                            <b style={{fontSize:'12px',color:C.text,flex:1}}>Передаём: {newTransfer.materialName}</b>
                            <input placeholder='Кол-во *' type='number' value={newTransfer.quantity} onChange={e=>setNewTransfer({...newTransfer,quantity:e.target.value})} style={{...inp,marginBottom:0,width:'120px'}}/>
                            <span style={{fontSize:'12px',color:C.textSec}}>{newTransfer.unit}</span>
                            <span style={{fontSize:'11px',color:C.warning}}>
                              Остаток: {(newTransfer.fromLocation==='Основной склад'?warehouseMain.find(m=>m.name===newTransfer.materialName):materials.find(m=>m.name===newTransfer.materialName&&m.project===newTransfer.fromLocation))?.quantity||0} {newTransfer.unit}
                            </span>
                  </div>)}
                          <select value={newTransfer.toPerson} onChange={e=>{const s=staff.find(st=>st.name===e.target.value);setNewTransfer({...newTransfer,toPerson:e.target.value,toPersonRole:s?s.role:''});}} style={{...inp,marginBottom:0}}>
                            <option value=''>Кому передать *</option>
                            {staff.filter(s=>['мастер','прораб','бригадир'].includes(s.role.toLowerCase())).map(s=><option key={s.id} value={s.name}>{s.name} ({s.role})</option>)}
                            {brigadeContracts.filter(bc=>bc.projectName===p.name).map(bc=><option key={bc.id} value={bc.brigadeName}>🔨 {bc.brigadeName} ({bc.contractorType})</option>)}
                          </select>

                          <input type='date' value={newTransfer.transferDate} onChange={e=>setNewTransfer({...newTransfer,transferDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder='Примечание' value={newTransfer.notes} onChange={e=>setNewTransfer({...newTransfer,notes:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                        <div style={{display:'flex',gap:'8px',marginTop:'12px'}}>
                          <button onClick={async()=>{
                            if(!newTransfer.materialName||!newTransfer.quantity||!newTransfer.toPerson) return;
                            const data={...newTransfer,projectName:p.name,createdBy:user.name};
                            const res=await fetch(API+'/material-transfers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
                            const saved=await res.json();
                            if(!res.ok||!saved.ok){alert('Ошибка: '+(saved.detail||saved.error||'не удалось списать со склада'));return;}
                            setMaterialTransfers(prev=>[{...data,id:saved.id,signed:false},...prev]);
                            const qty=Number(newTransfer.quantity);
                            if(newTransfer.fromLocation==='Основной склад'){
                              setWarehouseMain(prev=>prev.map(m=>m.name===newTransfer.materialName?{...m,quantity:Number(m.quantity||0)-qty}:m));
                            }else{
                              setMaterials(prev=>prev.map(m=>(m.name===newTransfer.materialName&&m.project===newTransfer.fromLocation)?{...m,quantity:Number(m.quantity||0)-qty}:m));
                            }
                            setNewTransfer({materialName:'',quantity:'',unit:'шт',toPerson:'',toPersonRole:'',fromLocation:'Основной склад',notes:'',transferDate:new Date().toISOString().split('T')[0]});
                            setShowTransferForm(false);
                          }} style={btnO}><Check size={14}/>Передать</button>
                          <button onClick={()=>setShowTransferForm(false)} style={btnG}><X size={14}/>Отмена</button>
                        </div>
                  </div>)}

                      <table style={tbl}><thead><tr>
                        <th style={tblH}>Материал</th>
                        <th style={tblH}>Кол-во</th>
                        <th style={tblH}>Кому</th>
                        <th style={tblH}>Дата</th>
                        <th style={tblH}>Статус</th>
                        <th style={tblH}></th>
                      </tr></thead><tbody>
                        {materialTransfers.filter(t=>t.projectName===p.name).map(t=>(<tr key={t.id}>
                          <td style={tblC}>{t.materialName}</td>
                          <td style={tblC}>{t.quantity} {t.unit}</td>
                          <td style={tblC}>{t.toPerson}<br/><span style={{fontSize:'11px',color:C.textSec}}>{t.toPersonRole}</span></td>
                          <td style={tblC}>{t.transferDate}</td>
                          <td style={tblC}>{t.signed?<span style={{color:C.success,fontSize:'12px'}}>✅ Подписано</span>:<span style={{color:C.warning,fontSize:'12px'}}>⏳ Ожидает подписи</span>}</td>
                          <td style={tblC}>
                            {!t.signed&&<button onClick={async()=>{
                              await fetch(API+'/material-transfers/'+t.id+'/sign',{method:'PUT'});
                              setMaterialTransfers(prev=>prev.map(mt=>mt.id===t.id?{...mt,signed:true}:mt));
                            }} style={{...btnO,padding:'4px 10px',fontSize:'11px'}}><Check size={11}/>Подписать</button>}
                            <button onClick={()=>showPreview(buildM15Content(t),'М-15 № '+t.id)} style={{...btnB,padding:'4px 8px',marginLeft:'4px'}} title="Печать М-15 (накладная на отпуск)">🖨️</button>
                            <button onClick={async()=>{
                              await fetch(API+'/material-transfers/'+t.id,{method:'DELETE'});
                              setMaterialTransfers(prev=>prev.filter(mt=>mt.id!==t.id));
                            }} style={{...btnR,padding:'4px 8px',marginLeft:'4px'}}><Trash2 size={11}/></button>
                          </td>
                        </tr>))}
                      </tbody></table>
                      {materialTransfers.filter(t=>t.projectName===p.name).length===0&&(
                        <div style={{...card,padding:'40px',textAlign:'center',color:C.textMuted}}>
                          <Package size={48} style={{marginBottom:'15px',opacity:0.3}}/>
                          <p>Передач материалов нет</p>
                        </div>
                      )}
                  </div>)}
                    {activeProjectTab==='Чат'&&(<div>
                      <b style={{color:C.text,display:'block',marginBottom:'15px'}}>Чат проекта</b>
                      <div style={{backgroundColor:C.bg,borderRadius:'12px',padding:'15px',minHeight:'250px',maxHeight:'350px',overflowY:'auto',marginBottom:'15px',display:'flex',flexDirection:'column',gap:'10px',border:'1.5px solid '+C.border}}>
                        {(()=>{const msgs=projectChatMessages[p.name]||[];if(msgs.length===0) return <p style={{color:C.textMuted,textAlign:'center',margin:'auto',fontSize:'13px'}}>Нет сообщений</p>;return msgs.map(msg=>{const isMe=msg.authorName===user.name;return(<div key={msg.id} style={{display:'flex',justifyContent:isMe?'flex-end':'flex-start'}}><div style={{maxWidth:'80%',backgroundColor:isMe?C.accent:'white',color:isMe?'white':C.text,padding:'10px 14px',borderRadius:isMe?'16px 16px 4px 16px':'16px 16px 16px 4px',border:'1.5px solid '+(isMe?C.accent:C.border)}}>{!isMe&&<div style={{fontSize:'11px',fontWeight:'700',color:roleColor(msg.authorRole),marginBottom:'4px'}}>{msg.authorName}</div>}{msg.text&&<p style={{margin:0,fontSize:'13px'}}>{msg.text}</p>}{(msg.photoUrl||msg.photo_url)&&<img src={msg.photoUrl||msg.photo_url} alt='' style={{width:'180px',borderRadius:'8px',display:'block',marginTop:'6px',cursor:'pointer'}} onClick={()=>setShowPhotoModal(msg.photoUrl||msg.photo_url)}/>}<div style={{fontSize:'10px',color:isMe?'rgba(255,255,255,0.7)':C.textMuted,marginTop:'4px',textAlign:'right'}}>{msg.createdAt?new Date(msg.createdAt).toLocaleTimeString('ru-RU'):''}</div></div></div>);});})()}
                      </div>
                      <div style={{display:'flex',gap:'8px'}}>
                        <input placeholder="Написать..." value={projectChatMessage} onChange={e=>setProjectChatMessage(e.target.value)} onKeyDown={e=>e.key==='Enter'&&sendProjectChatMessage(p.name,projectChatMessage,'')} style={{...inp,marginBottom:0,flex:1}}/>
                        <button onClick={()=>{if(!projectChatMessages[p.name]) loadProjectChat(p.name);sendProjectChatMessage(p.name,projectChatMessage,'');}} style={btnO}>➤</button>
                      </div>
                      {!projectChatMessages[p.name]&&<button onClick={()=>loadProjectChat(p.name)} style={{...btnG,marginTop:'8px',fontSize:'12px'}}>Загрузить чат</button>}
                  </div>)}

                    {activeProjectTab==='Финансы'&&(<div>
                      {isFinanceRole()&&(()=>{
                        const cat=expByCategory(p.name);
                        const total=Object.values(cat).reduce((s,v)=>s+v,0);
                        const received=projectPayments.filter(pay=>pay.projectName===p.name).reduce((s,pay)=>s+Number(pay.amount||0),0);
                        const inAccountable=accountablePayments.filter(ac=>ac.projectName===p.name).reduce((s,ac)=>s+Math.max(0,Number(ac.amount||0)-Number(ac.spentAmount||0)),0);
                        const profit=received-total-inAccountable;
                        const toReimburse=ownExpenses.filter(e=>e.projectName===p.name&&e.status==='Ожидает');
                        return(<div>
                          <div style={{display:'flex',gap:'8px',marginBottom:'12px',flexWrap:'wrap'}}>
                            <button onClick={()=>{const amount=prompt('Сумма оплаты от заказчика (₽):');const note=prompt('Примечание:');if(amount&&Number(amount)>0){fetch(API+'/project-payments',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({projectName:p.name,amount:Number(amount),note:note||'',date:new Date().toISOString().split('T')[0],addedBy:user.name})}).then(()=>loadAll());}}} style={{...btnO,fontSize:'12px',padding:'7px 14px'}}><Plus size={13}/>Оплата от заказчика</button>
                            <button onClick={()=>{setAddExpenseProject(p.name);setNewManualExpense({category:'materials',amount:'',note:'',date:''});}} style={{...btnB,fontSize:'12px',padding:'7px 14px'}}><Plus size={13}/>Расход по объекту</button>
                            <button onClick={()=>{setShowAccountableForm(true);setNewAccountable({...newAccountable,projectName:p.name});}} style={{...btnG,fontSize:'12px',padding:'7px 14px'}}><Plus size={13}/>Подотчёт по объекту</button>
                            {toReimburse.length>0&&<div style={{display:'flex',alignItems:'center',gap:'6px',padding:'7px 14px',backgroundColor:C.warningLight,borderRadius:'8px',border:'1.5px solid '+C.warningBorder}}><span style={{fontSize:'12px',color:C.warning,fontWeight:'600'}}>{'⏳ К возмещению: '+toReimburse.reduce((s,e)=>s+Number(e.amount),0).toLocaleString()+' ₽'}</span></div>}
                          </div>
                          <div style={{...card,padding:'16px',marginBottom:'12px',backgroundColor:C.accentLight,border:'1.5px solid '+C.accentBorder}}>
                            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'10px',cursor:'pointer'}} onClick={()=>setShowBalanceDetails(!showBalanceDetails)}><b style={{color:C.text,fontSize:'14px'}}>💰 Баланс объекта</b><span style={{fontSize:'12px',color:C.accent}}>{showBalanceDetails?'▲ Свернуть':'▼ Подробнее'}</span></div>
                            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
                              <div style={{padding:'10px',backgroundColor:'white',borderRadius:'8px'}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 2px'}}>Получено от заказчика</p><b style={{color:C.success,fontSize:'15px'}}>{received.toLocaleString()+' ₽'}</b></div>
                              <div style={{padding:'10px',backgroundColor:'white',borderRadius:'8px'}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 2px'}}>Все расходы</p><b style={{color:C.danger,fontSize:'15px'}}>{total.toLocaleString()+' ₽'}</b></div>
                              <div style={{padding:'10px',backgroundColor:'white',borderRadius:'8px'}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 2px'}}>В подотчёте</p><b style={{color:C.warning,fontSize:'15px'}}>{inAccountable.toLocaleString()+' ₽'}</b></div>
                              <div style={{padding:'10px',backgroundColor:profit>=0?C.successLight:C.dangerLight,borderRadius:'8px',border:'1.5px solid '+(profit>=0?C.successBorder:C.dangerBorder)}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 2px'}}>Прибыль</p><b style={{color:profit>=0?C.success:C.danger,fontSize:'15px'}}>{profit.toLocaleString()+' ₽'}</b></div>
                            </div>
                          </div>
                          {showBalanceDetails&&(<div style={{...card,padding:'16px',marginBottom:'12px'}}>
                            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'10px'}}>📊 Расходы по категориям</b>
                            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
                              {EXPENSE_CATEGORIES.filter(c=>cat[c.id]>0).map(c=>(<div key={c.id} style={{padding:'10px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border}}><p style={{margin:'0 0 2px',fontSize:'11px',color:C.textSec}}>{c.label}</p><b style={{fontSize:'14px',color:c.color}}>{cat[c.id].toLocaleString()+' ₽'}</b></div>))}
                              {EXPENSE_CATEGORIES.filter(c=>cat[c.id]>0).length===0&&<p style={{color:C.textMuted,fontSize:'12px',gridColumn:'span 2',textAlign:'center',padding:'10px'}}>Расходов пока нет</p>}
                            </div>
                          </div>)}
                          {toReimburse.length>0&&(<div style={{...card,padding:'16px',marginBottom:'12px'}}>
                            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'10px'}}>⏳ К возмещению</b>
                            {toReimburse.map(e=>(<div key={e.id} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'8px 0',borderBottom:'1px solid '+C.border}}>
                              <div><b style={{fontSize:'13px',color:C.text}}>{e.employeeName}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{e.description}</p></div>
                              <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
                                <b style={{color:C.accent,fontSize:'13px'}}>{Number(e.amount).toLocaleString()+' ₽'}</b>
                                {e.photoUrl&&<button onClick={()=>setShowPhotoModal(e.photoUrl.startsWith('http')?e.photoUrl:API+e.photoUrl)} style={{...btnG,padding:'3px 8px',fontSize:'11px'}}>📷</button>}
                                <button onClick={async()=>{await fetch(API+'/own-expenses/'+e.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Возмещено',approvedBy:user.name})});await loadAll();}} style={{...btnO,padding:'3px 8px',fontSize:'11px'}}>✅</button>
                                <button onClick={async()=>{await fetch(API+'/own-expenses/'+e.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Отклонено',approvedBy:user.name})});await loadAll();}} style={{...btnR,padding:'3px 8px',fontSize:'11px'}}>❌</button>
                              </div>
                            </div>))}
                          </div>)}
                          {projectPayments.filter(pay=>pay.projectName===p.name).length>0&&(<div style={{...card,padding:'16px',marginBottom:'12px'}}>
                            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'10px'}}>📋 История оплат от заказчика</b>
                            {projectPayments.filter(pay=>pay.projectName===p.name).map(pay=>(<div key={pay.id} style={{display:'flex',justifyContent:'space-between',padding:'6px 0',borderBottom:'1px solid '+C.border}}>
                              <div><span style={{fontSize:'12px',color:C.text}}>{pay.note||'Оплата'}</span><span style={{fontSize:'11px',color:C.textMuted,marginLeft:'8px'}}>{pay.date}</span></div>
                              <b style={{fontSize:'12px',color:C.success}}>+{Number(pay.amount).toLocaleString()+' ₽'}</b>
                            </div>))}
                          </div>)}
                        </div>);
                      })()}
                  </div>)}
                    {activeProjectTab==='Предписания'&&(<div>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                        <b style={{color:C.text}}>Предписания</b>
                        <button onClick={()=>setShowForm(showForm==='prescription'?false:'prescription')} style={btnO}><Plus size={14}/>Выдать</button>
                      </div>
                      {showForm==='prescription'&&(<div style={{...card,padding:'16px',marginBottom:'16px',backgroundColor:C.bg}}>
                        <input placeholder="Номер предписания" value={newPrescription.number} onChange={e=>setNewPrescription({...newPrescription,number:e.target.value})} style={inp}/>
                        <textarea placeholder="Описание нарушения *" value={newPrescription.violation} onChange={e=>setNewPrescription({...newPrescription,violation:e.target.value})} style={{...inp,height:'80px',resize:'vertical'}}/>
                        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
                          <input type="date" placeholder="Устранить до" value={newPrescription.deadline} onChange={e=>setNewPrescription({...newPrescription,deadline:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Ответственный" value={newPrescription.responsible} onChange={e=>setNewPrescription({...newPrescription,responsible:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                        <div style={{display:'flex',gap:'8px',marginTop:'10px'}}><button onClick={()=>savePrescription(p.name)} style={btnO}><Check size={14}/>Выдать</button><button onClick={()=>setShowForm(false)} style={btnG}><X size={14}/>Отмена</button></div>
                  </div>)}
                      {prescriptionsList.filter(pr=>pr.projectName===p.name).map(pr=>(<div key={pr.id} style={{...card,padding:'14px',marginBottom:'8px',borderLeft:'3px solid '+(pr.status==='Закрыто'?C.success:pr.status==='На проверке'?C.warning:C.danger)}}>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
                          <div><b style={{fontSize:'13px',color:C.text}}>{'Предписание '+(pr.number?'№'+pr.number:'')}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{pr.violation}</p><p style={{color:C.textMuted,margin:'0',fontSize:'11px'}}>{'Выдал: '+pr.issuedBy+(pr.deadline?' · До: '+pr.deadline:'')+(pr.responsible?' · Ответственный: '+pr.responsible:'')}</p></div>
                          <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
                            <span style={badge(pr.status==='Закрыто'?C.success:pr.status==='На проверке'?C.warning:C.danger,pr.status==='Закрыто'?C.successLight:pr.status==='На проверке'?C.warningLight:C.dangerLight,pr.status==='Закрыто'?C.successBorder:pr.status==='На проверке'?C.warningBorder:C.dangerBorder)}>{pr.status}</span>
                            {pr.status==='Открыто'&&<button onClick={async()=>{await fetch(API+'/prescriptions/'+pr.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'На проверке',fixNotes:'Устранено'})});await loadAll();}} style={{...btnGr,padding:'4px 8px',fontSize:'11px'}}>Устранено</button>}
                            {pr.status==='На проверке'&&isProrab()&&<button onClick={async()=>{await fetch(API+'/prescriptions/'+pr.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Закрыто'})});await loadAll();}} style={{...btnGr,padding:'4px 8px',fontSize:'11px'}}>Закрыть</button>}
                          </div>
                        </div>
                      </div>))}
                      {prescriptionsList.filter(pr=>pr.projectName===p.name).length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'20px'}}>Предписаний нет</p>}
                  </div>)}

                    {activeProjectTab==='Журнал ТБ'&&(<div>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                        <b style={{color:C.text}}>Журнал ТБ</b>
                        <button onClick={()=>setShowForm(showForm==='tb'?false:'tb')} style={btnO}><Plus size={14}/>Добавить</button>
                      </div>
                      {showForm==='tb'&&(<div style={{...card,padding:'16px',marginBottom:'16px',backgroundColor:C.bg}}>
                        <select value={newTbEntry.type} onChange={e=>setNewTbEntry({...newTbEntry,type:e.target.value})} style={inp}>{TB_TYPES_GOST.map(t=><option key={t.value} value={t.value}>{t.value}</option>)}{Object.keys(TB_INSTRUCTIONS).filter(k=>!TB_TYPES_GOST.find(t=>t.value===k)).map(t=><option key={t}>{t}</option>)}</select>
                        {(()=>{const meta=TB_TYPES_GOST.find(t=>t.value===newTbEntry.type);return meta?(<p style={{fontSize:'10px',color:C.textMuted,margin:'0 0 8px',padding:'4px 8px',backgroundColor:C.bg,borderRadius:'4px'}}>📋 Периодичность: <b>{meta.freq}</b> · {meta.legal}</p>):null;})()}
                        <input type="date" value={newTbEntry.date} onChange={e=>setNewTbEntry({...newTbEntry,date:e.target.value})} style={inp}/>
                        <textarea placeholder="Программа инструктажа (3-5 пунктов)" value={newTbEntry.program||''} onChange={e=>setNewTbEntry({...newTbEntry,program:e.target.value})} style={{...inp,minHeight:'50px',resize:'vertical'}}/>
                        <div style={{display:'flex',gap:'8px',alignItems:'center',marginBottom:'6px'}}>
                          <textarea placeholder="Текст инструктажа (можно сгенерировать ИИ →)" value={newTbEntry.instructionText||''} onChange={e=>setNewTbEntry({...newTbEntry,instructionText:e.target.value})} style={{...inp,minHeight:'80px',flex:1,marginBottom:0,resize:'vertical'}}/>
                          <button disabled={newTbEntry.aiLoading} onClick={async()=>{setNewTbEntry(prev=>({...prev,aiLoading:true}));try{const res=await fetch(API+'/tb-journal/ai-generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({instructionType:newTbEntry.type,projectName:p.name,workContext:''})});if(!res.ok){const e=await res.json().catch(()=>({}));throw new Error(e.detail||'Ошибка');}const d=await res.json();setNewTbEntry(prev=>({...prev,instructionText:d.instructionText||'',aiLoading:false}));}catch(e){alert('AI: '+e.message);setNewTbEntry(prev=>({...prev,aiLoading:false}));}}} style={{...btnB,backgroundColor:'#10b981',padding:'10px 12px',fontSize:'11px',opacity:newTbEntry.aiLoading?0.6:1}} title="Сгенерировать текст по ГОСТ через ИИ"><Bot size={14}/>{newTbEntry.aiLoading?'…':'🤖 ИИ'}</button>
                        </div>
                        <div style={{display:'flex',gap:'8px',marginBottom:'10px'}}>
                          <input placeholder="ФИО участника" value={newParticipant} onChange={e=>setNewParticipant(e.target.value)} onKeyDown={e=>e.key==='Enter'&&(setNewTbEntry({...newTbEntry,participants:[...(newTbEntry.participants||[]),newParticipant]}),setNewParticipant(''))} style={{...inp,marginBottom:0,flex:1}}/>
                          <button onClick={()=>{if(newParticipant){setNewTbEntry({...newTbEntry,participants:[...(newTbEntry.participants||[]),newParticipant]});setNewParticipant('');}}} style={btnO}><Plus size={14}/></button>
                        </div>
                        {(newTbEntry.participants||[]).map((part,i)=>(<div key={i} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'6px 10px',backgroundColor:C.bg,borderRadius:'6px',marginBottom:'4px',border:'1px solid '+C.border}}><span style={{fontSize:'12px'}}>{part}</span><button onClick={()=>setNewTbEntry({...newTbEntry,participants:(newTbEntry.participants||[]).filter((_,idx)=>idx!==i)})} style={{...btnR,padding:'2px 6px'}}><X size={10}/></button></div>))}
                        <div style={{display:'flex',gap:'8px',marginTop:'10px'}}>
                          <button onClick={async()=>{await saveTbEntry({...newTbEntry,project:p.name});setShowForm(false);setNewTbEntry({project:'',type:'Вводный инструктаж',participants:[],date:'',program:'',instructionText:'',aiLoading:false});}} style={btnO}><Check size={14}/>Сохранить</button>
                          <button onClick={()=>setShowForm(false)} style={btnG}><X size={14}/>Отмена</button>
                        </div>
                  </div>)}
                      {tbJournal.filter(e=>e.project===p.name).map(entry=>(<div key={entry.id} style={{...card,padding:'14px',marginBottom:'8px'}}>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                          <div><b style={{color:C.text,fontSize:'13px'}}>{entry.type}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{entry.date+' · '+(entry.participants||[]).length+' участников'}</p></div>
                          <button onClick={()=>showPreview(buildTBContent(entry),'Журнал ТБ')} style={btnB}><Eye size={14}/>ЖТБ</button>
                        </div>
                      </div>))}
                      {tbJournal.filter(e=>e.project===p.name).length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'20px'}}>Записей нет</p>}
                  </div>)}
                    {activeProjectTab==='АОСР'&&(<div>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',flexWrap:'wrap',gap:'10px'}}>
                        <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>🔒 Акты освидетельствования скрытых работ</b>
                        <span style={{fontSize:'11px',color:C.textMuted}}>Создаются автоматически из сметы по позициям с 🔒</span>
                      </div>
                      {(()=>{const actsHere=hiddenActs.filter(a=>a.projectName===p.name);if(actsHere.length===0)return(<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}><div style={{fontSize:'40px',marginBottom:'10px'}}>📋</div><p style={{margin:'0 0 8px',fontWeight:'600'}}>Актов скрытых работ пока нет</p><p style={{fontSize:'12px',margin:0,lineHeight:1.6}}>Как появятся: в смете объекта отметьте позиции переключателем 🔒.<br/>Когда по такой позиции заполнят «Сделано» — черновик акта создастся сам.</p></div>);
                        const cntDraft=actsHere.filter(a=>a.status!=='Подписан').length;
                        const cntSigned=actsHere.filter(a=>a.status==='Подписан').length;
                        const sumTotal=actsHere.reduce((s,a)=>s+Number(a.total||0),0);
                        return(<div>
                          <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'10px',marginBottom:'14px'}}>
                            <div style={{...card,padding:'12px',backgroundColor:C.bg}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Всего актов</p><b style={{color:C.text,fontSize:'16px'}}>{actsHere.length}</b></div>
                            <div style={{...card,padding:'12px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}><p style={{color:C.warning,fontSize:'11px',margin:'0 0 4px'}}>Черновики</p><b style={{color:C.warning,fontSize:'16px'}}>{cntDraft}</b></div>
                            <div style={{...card,padding:'12px',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder}}><p style={{color:C.success,fontSize:'11px',margin:'0 0 4px'}}>Подписано</p><b style={{color:C.success,fontSize:'16px'}}>{cntSigned}</b></div>
                          </div>
                          <div style={{...card,padding:0,overflow:'auto'}}>
                            <table style={tbl}><thead><tr>
                              <th style={tblH}>№ акта</th>
                              <th style={tblH}>Раздел</th>
                              <th style={tblH}>Работа</th>
                              <th style={tblH}>Бригада</th>
                              <th style={tblH}>Объём</th>
                              <th style={tblH}>Дата</th>
                              <th style={tblH}>Сумма</th>
                              <th style={tblH}>Подписи</th>
                              <th style={tblH}>Статус</th>
                              <th style={tblH}></th>
                            </tr></thead><tbody>
                              {actsHere.map(act=>{const signs=[!!act.signedCustomer,!!act.signedSupervisor,!!act.signedContractor,!!act.signedSubcontractor];const labels=['Заказчик','Технадзор','Генподрядчик','Субподрядчик'];return(<tr key={act.id} style={{cursor:'pointer'}} onClick={()=>setEditingAct(act)}>
                                <td style={tblC}><b style={{color:C.accent}}>{act.actNumber}</b></td>
                                <td style={tblC}>{act.sectionName||'—'}</td>
                                <td style={{...tblC,maxWidth:'280px',whiteSpace:'normal'}}>{act.workName}</td>
                                <td style={tblC}>{act.brigade||'—'}</td>
                                <td style={tblC}>{act.quantity+' '+(act.unit||'')}</td>
                                <td style={tblC}>{act.workDate||'—'}</td>
                                <td style={tblC}>{Number(act.total||0).toLocaleString('ru-RU')+' ₽'}</td>
                                <td style={tblC}><div style={{display:'flex',gap:'3px'}}>{signs.map((ok,i)=>(<div key={i} title={labels[i]+(ok?': подписано':': нет подписи')} style={{width:'12px',height:'12px',borderRadius:'50%',backgroundColor:ok?C.success:C.border,border:'1.5px solid '+(ok?C.success:C.border)}}/>))}</div></td>
                                <td style={tblC}><span style={{padding:'2px 8px',borderRadius:'10px',fontSize:'11px',fontWeight:'600',backgroundColor:act.status==='Подписан'?C.successLight:C.warningLight,color:act.status==='Подписан'?C.success:C.warning}}>{act.status||'Черновик'}</span></td>
                                <td style={tblC} onClick={e=>e.stopPropagation()}><div style={{display:'flex',gap:'4px'}}>
                                  <button onClick={()=>setEditingAct(act)} title="Открыть карточку" style={{...btnB,padding:'3px 7px'}}>✏️</button>
                                  <button onClick={()=>showPreview(buildHiddenActContent(act),'АОСР № '+act.actNumber)} title="Печать по СНиП" style={{...btnG,padding:'3px 7px'}}>🖨️</button>
                                  {isLeadership()&&<button onClick={async()=>{if(!window.confirm('Удалить акт '+act.actNumber+'?')) return;await fetch(API+'/hidden-works-acts/'+act.id,{method:'DELETE'});setHiddenActs(prev=>prev.filter(a=>a.id!==act.id));}} title="Удалить" style={{...btnR,padding:'3px 7px'}}>🗑️</button>}
                                </div></td>
                              </tr>);})}
                            </tbody></table>
                          </div>
                          <div style={{marginTop:'12px',padding:'12px',backgroundColor:C.accentLight,border:'1.5px solid '+C.accentBorder,borderRadius:'10px',textAlign:'right'}}>
                            <span style={{color:C.textSec,fontSize:'12px',marginRight:'10px'}}>Сумма по всем актам объекта:</span>
                            <b style={{color:C.accent,fontSize:'15px'}}>{sumTotal.toLocaleString('ru-RU')+' ₽'}</b>
                          </div>
                        </div>);
                      })()}
                  </div>)}
                  {activeProjectTab==='Главный'&&(<div>
                    <div style={{marginBottom:'15px'}}>
                      <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>📚 Журналы объекта</b>
                      <p style={{color:C.textMuted,fontSize:'12px',margin:'4px 0 0'}}>Клик по карточке откроет соответствующий журнал.</p>
                    </div>
                    {(()=>{
                      const cards=[
                        {tab:'Производство работ',icon:'📖',label:'Производство работ',hint:'Журнал по форме КС-6а',count:workJournal.filter(jw=>jw.project===p.name).length},
                        {tab:'АОСР',icon:'🔒',label:'Скрытые работы (АОСР)',hint:'СНиП 12-01-2004',count:hiddenActs.filter(a=>a.projectName===p.name).length},
                        {tab:'Входной контроль',icon:'📦',label:'Входной контроль материалов',hint:'СП 48.13330.2019',count:materialInspections.filter(mi=>mi.projectName===p.name).length},
                        {tab:'Кабельная продукция',icon:'⚡',label:'Кабельная продукция',hint:'СП 76.13330 · ПУЭ',count:cableJournal.filter(c=>c.projectName===p.name).length},
                        {tab:'Журнал ТБ',icon:'🛡️',label:'Техника безопасности',hint:'ГОСТ 12.0.004-2015',count:(tbJournal||[]).filter(e=>e.project===p.name).length},
                        {tab:'Погода',icon:'🌤',label:'Погода',hint:'Метеоусловия по дням',count:(weatherLog||[]).filter(w=>w.projectName===p.name).length},
                        {tab:'Предписания',icon:'⚠️',label:'Предписания',hint:'От технадзора и стройконтроля',count:(prescriptionsList||[]).filter(pr=>pr.projectName===p.name).length},
                        {tab:'Чат',icon:'💬',label:'Чат проекта',hint:'Переписка по объекту',count:0},
                      ];
                      return(<div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(220px,1fr))',gap:'12px'}}>
                        {cards.map(c=>(<div key={c.tab} onClick={()=>setActiveProjectTab(c.tab)} style={{...card,padding:'16px',cursor:'pointer',border:'1.5px solid '+C.border}}><div style={{display:'flex',alignItems:'center',gap:'10px',marginBottom:'6px'}}><span style={{fontSize:'24px'}}>{c.icon}</span><b style={{color:C.text,fontSize:'13px'}}>{c.label}</b></div><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 6px'}}>{c.hint}</p><b style={{color:C.accent,fontSize:'13px'}}>{c.count+' '+(c.count===1?'запись':c.count>=2&&c.count<=4?'записи':'записей')}</b></div>))}
                      </div>);
                    })()}
                  </div>)}
                  {activeProjectTab==='Погода'&&(<div>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                      <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>🌤 Журнал погоды</b>
                      <span style={{fontSize:'11px',color:C.textMuted}}>Метеоусловия по дням строительства</span>
                    </div>
                    {(()=>{
                      const here=(weatherLog||[]).filter(w=>w.projectName===p.name).slice().sort((a,b)=>(b.date||'').localeCompare(a.date||''));
                      if(here.length===0) return(<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Записей о погоде нет. Логируйте погоду из глобального раздела «Погода» — она автоматически появится здесь по этому объекту.</div>);
                      return(<div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(220px,1fr))',gap:'10px'}}>
                        {here.map((w,i)=>(<div key={i} style={{...card,padding:'12px'}}><b style={{color:C.text,fontSize:'13px'}}>{w.date}</b><p style={{color:C.textSec,margin:'4px 0 0',fontSize:'12px'}}>{(w.condition||'—')+' · '+(w.temperature!=null?w.temperature+'°C':'—')+(w.windSpeed?' · ветер '+w.windSpeed+' м/с':'')}</p>{w.notes&&<p style={{color:C.textMuted,fontSize:'11px',margin:'4px 0 0',fontStyle:'italic'}}>{w.notes}</p>}</div>))}
                      </div>);
                    })()}
                  </div>)}
                  {activeProjectTab==='КС-2'&&(<div>
                    <div style={{...card,padding:'24px',textAlign:'center'}}>
                      <div style={{fontSize:'40px',marginBottom:'10px'}}>📄</div>
                      <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'6px'}}>Акт о приёмке выполненных работ (КС-2)</b>
                      <p style={{color:C.textMuted,fontSize:'12px',margin:'0 0 16px'}}>Унифицированная форма по ОКУД 0322005. Формируется из выполненных позиций сметы и подтверждённых работ. Включает разделы «Основные работы» и «Дополнительные работы» (непредвиденные).</p>
                      <button onClick={()=>showKS2(p)} style={btnO}><Eye size={14}/>🖨 Открыть КС-2</button>
                    </div>
                  </div>)}
                  {activeProjectTab==='КС-3'&&(<div>
                    <div style={{...card,padding:'24px',textAlign:'center'}}>
                      <div style={{fontSize:'40px',marginBottom:'10px'}}>📋</div>
                      <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'6px'}}>Справка о стоимости выполненных работ (КС-3)</b>
                      <p style={{color:C.textMuted,fontSize:'12px',margin:'0 0 16px'}}>Унифицированная форма по ОКУД 0322001. Подаётся вместе с КС-2 за отчётный период.</p>
                      <button onClick={()=>showPreview(buildKS3Content(p),'КС-3 — '+p.name)} style={btnO}><Eye size={14}/>🖨 Открыть КС-3</button>
                    </div>
                  </div>)}
                  {activeProjectTab==='Паспорт'&&(<div>
                    <div style={{...card,padding:'24px',textAlign:'center'}}>
                      <div style={{fontSize:'40px',marginBottom:'10px'}}>📘</div>
                      <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'6px'}}>Паспорт объекта</b>
                      <p style={{color:C.textMuted,fontSize:'12px',margin:'0 0 16px'}}>Сводная карточка объекта с основными характеристиками и реквизитами.</p>
                      <button onClick={()=>showPreview(buildPassportContent(p),'Паспорт — '+p.name)} style={btnO}><Eye size={14}/>🖨 Открыть Паспорт</button>
                    </div>
                  </div>)}
                  {activeProjectTab==='Акты технадзора'&&(<div>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                      <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>📝 Акты осмотра / обследования от технадзора</b>
                      <span style={{fontSize:'11px',color:C.textMuted}}>Создаются технадзором в его кабинете</span>
                    </div>
                    {(()=>{const here=(supervisorActs||[]).filter(a=>a.projectName===p.name);if(here.length===0) return(<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Технадзор пока не загружал актов осмотра по этому объекту.</div>);return(<div>{here.map(a=>(<div key={a.id} style={{...card,padding:'14px',marginBottom:'8px',borderLeft:'3px solid '+C.accent}}>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px'}}>
                        <div style={{flex:1}}>
                          <b style={{color:C.text,fontSize:'13px'}}>{a.actNumber+' · '+a.actType}</b>
                          <p style={{color:C.textSec,margin:'4px 0',fontSize:'12px'}}>{a.description||'—'}</p>
                          {a.findings&&<p style={{color:C.text,margin:'4px 0',fontSize:'11px'}}><b>Обнаружено:</b> {a.findings}</p>}
                          {a.recommendations&&<p style={{color:C.text,margin:'4px 0',fontSize:'11px'}}><b>Рекомендации:</b> {a.recommendations}</p>}
                          <p style={{color:C.textMuted,margin:'4px 0 0',fontSize:'11px'}}>{a.date+' · '+(a.issuedBy||'—')}</p>
                        </div>
                        {a.photoUrl&&<img src={a.photoUrl.startsWith('http')?a.photoUrl:API+a.photoUrl} alt='' onClick={()=>setShowPhotoModal(a.photoUrl.startsWith('http')?a.photoUrl:API+a.photoUrl)} style={{width:'56px',height:'56px',borderRadius:'6px',objectFit:'cover',cursor:'pointer',flexShrink:0}}/>}
                      </div>
                    </div>))}</div>);})()}
                  </div>)}
                  {activeProjectTab==='Замечания ГСН'&&(<div>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',flexWrap:'wrap',gap:'8px'}}>
                      <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>🏛 Замечания контролирующих органов</b>
                      <button onClick={()=>setShowForm(showForm==='gsn'?false:'gsn')} style={btnO}><Plus size={14}/>Добавить</button>
                    </div>
                    {showForm==='gsn'&&(<div style={{...card,padding:'16px',marginBottom:'14px',backgroundColor:C.bg}}>
                      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'8px'}}>
                        <select value={newInspOrder?.body||'ГСН'} onChange={e=>setNewInspOrder({...(newInspOrder||{}),body:e.target.value})} style={{...inp,marginBottom:0}}>{['ГСН','ГПН','Роспотребнадзор','Ростехнадзор','Прокуратура','Иное'].map(b=><option key={b}>{b}</option>)}</select>
                        <input placeholder='ФИО инспектора' value={newInspOrder?.inspector||''} onChange={e=>setNewInspOrder({...(newInspOrder||{}),inspector:e.target.value})} style={{...inp,marginBottom:0}}/>
                      </div>
                      <textarea placeholder='Описание замечания/нарушения *' value={newInspOrder?.description||''} onChange={e=>setNewInspOrder({...(newInspOrder||{}),description:e.target.value})} style={{...inp,minHeight:'60px',marginBottom:'8px'}}/>
                      <textarea placeholder='Требования / рекомендации' value={newInspOrder?.recommendations||''} onChange={e=>setNewInspOrder({...(newInspOrder||{}),recommendations:e.target.value})} style={{...inp,minHeight:'50px',marginBottom:'8px'}}/>
                      <div style={{display:'flex',gap:'8px',marginBottom:'8px'}}>
                        <input type='date' value={newInspOrder?.date||''} onChange={e=>setNewInspOrder({...(newInspOrder||{}),date:e.target.value})} title='Дата проверки' style={{...inp,marginBottom:0,flex:1}}/>
                        <input type='date' value={newInspOrder?.deadline||''} onChange={e=>setNewInspOrder({...(newInspOrder||{}),deadline:e.target.value})} title='Срок устранения' style={{...inp,marginBottom:0,flex:1}}/>
                      </div>
                      <div style={{display:'flex',gap:'8px'}}>
                        <button onClick={async()=>{
                          if(!(newInspOrder&&newInspOrder.description)){alert('Опишите замечание');return;}
                          await fetch(API+'/inspection-orders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({projectName:p.name,body:newInspOrder.body||'ГСН',inspector:newInspOrder.inspector||'',description:newInspOrder.description,recommendations:newInspOrder.recommendations||'',deadline:newInspOrder.deadline||null,date:newInspOrder.date||new Date().toISOString().split('T')[0],status:'Открыто'})});
                          await loadAll();
                          setNewInspOrder(null); setShowForm(false);
                        }} style={btnO}><Check size={14}/>Сохранить</button>
                        <button onClick={()=>{setShowForm(false);setNewInspOrder(null);}} style={btnG}>Отмена</button>
                      </div>
                    </div>)}
                    {(()=>{const here=(inspectionOrders||[]).filter(o=>o.projectName===p.name);if(here.length===0) return(<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Замечаний контролирующих органов нет. Если приходила проверка с замечаниями — зафиксируй её здесь, чтобы пакет ИД был полным.</div>);const open=here.filter(o=>o.status!=='Закрыто').length;const closed=here.filter(o=>o.status==='Закрыто').length;return(<div>
                      <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'10px',marginBottom:'12px'}}>
                        <div style={{...card,padding:'10px',backgroundColor:C.dangerLight}}><p style={{color:C.danger,fontSize:'11px',margin:'0 0 4px'}}>Открытых</p><b style={{color:C.danger,fontSize:'16px'}}>{open}</b></div>
                        <div style={{...card,padding:'10px',backgroundColor:C.successLight}}><p style={{color:C.success,fontSize:'11px',margin:'0 0 4px'}}>Закрытых</p><b style={{color:C.success,fontSize:'16px'}}>{closed}</b></div>
                        <div style={{...card,padding:'10px',backgroundColor:C.bg}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Всего</p><b style={{color:C.text,fontSize:'16px'}}>{here.length}</b></div>
                      </div>
                      {here.map(o=>(<div key={o.id} style={{...card,padding:'14px',marginBottom:'8px',borderLeft:'3px solid '+(o.status==='Закрыто'?C.success:C.danger)}}>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                          <div style={{flex:1,minWidth:'200px'}}>
                            <b style={{color:C.text,fontSize:'13px'}}>{o.orderNumber+' · '+(o.body||'ГСН')+(o.inspector?' · '+o.inspector:'')}</b>
                            <p style={{color:C.danger,margin:'4px 0',fontSize:'12px'}}>{o.description||'—'}</p>
                            {o.recommendations&&<p style={{color:C.text,margin:'4px 0',fontSize:'11px'}}><b>Требования:</b> {o.recommendations}</p>}
                            <p style={{color:C.textMuted,margin:'4px 0 0',fontSize:'11px'}}>{(o.date||'')+(o.deadline?' · срок: '+o.deadline:'')}</p>
                            {o.response&&<div style={{marginTop:'8px',padding:'8px 10px',backgroundColor:C.successLight,borderRadius:'6px',fontSize:'11px',color:C.success}}><b>Ответ ({o.responseDate||'—'}):</b> {o.response}</div>}
                          </div>
                          <div style={{display:'flex',gap:'4px',alignItems:'flex-start'}}>
                            <span style={badge(o.status==='Закрыто'?C.success:C.danger,o.status==='Закрыто'?C.successLight:C.dangerLight,o.status==='Закрыто'?C.successBorder:C.dangerBorder)}>{o.status||'Открыто'}</span>
                            {o.status!=='Закрыто'&&<button onClick={async()=>{const resp=prompt('Опишите как устранили / ответ органу:');if(!resp) return;await fetch(API+'/inspection-orders/'+o.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Закрыто',response:resp,responseDate:new Date().toISOString().split('T')[0]})});await loadAll();}} style={{...btnGr,padding:'4px 8px',fontSize:'11px'}}>Закрыть</button>}
                            <button onClick={async()=>{if(!window.confirm('Удалить замечание?')) return;await fetch(API+'/inspection-orders/'+o.id,{method:'DELETE'});await loadAll();}} style={{...btnR,padding:'4px 8px'}}><Trash2 size={11}/></button>
                          </div>
                        </div>
                      </div>))}
                    </div>);})()}
                  </div>)}
                  {activeProjectTab==='Входной контроль'&&(<div>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',flexWrap:'wrap',gap:'10px'}}>
                      <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>📦 Журнал входного контроля материалов</b>
                      <span style={{fontSize:'11px',color:C.textMuted}}>СП 48.13330.2019 · автозаполняется из накладных</span>
                    </div>
                    {(()=>{
                      const here=materialInspections.filter(mi=>mi.projectName===p.name);
                      if(here.length===0) return(<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}><div style={{fontSize:'40px',marginBottom:'10px'}}>📦</div><p style={{margin:'0 0 8px',fontWeight:'600'}}>Записей пока нет</p><p style={{fontSize:'12px',margin:0,lineHeight:1.6}}>Записи создаются автоматически при оформлении приходной накладной (📦 Материалы → 📷 Принять материал).<br/>Затем здесь прораб/кладовщик дополняет паспорт, сертификат и отметку об осмотре.</p></div>);
                      const cntInsp=here.filter(r=>r.inspected).length;
                      const cntPending=here.length-cntInsp;
                      const cntOk=here.filter(r=>r.visualInspectionResult==='Соответствует').length;
                      return(<div>
                        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(120px,1fr))',gap:'10px',marginBottom:'14px'}}>
                          <div style={{...card,padding:'12px',backgroundColor:C.bg}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Записей</p><b style={{color:C.text,fontSize:'16px'}}>{here.length}</b></div>
                          <div style={{...card,padding:'12px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}><p style={{color:C.warning,fontSize:'11px',margin:'0 0 4px'}}>Ждут проверки</p><b style={{color:C.warning,fontSize:'16px'}}>{cntPending}</b></div>
                          <div style={{...card,padding:'12px',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder}}><p style={{color:C.success,fontSize:'11px',margin:'0 0 4px'}}>Проверено</p><b style={{color:C.success,fontSize:'16px'}}>{cntInsp}</b></div>
                          <div style={{...card,padding:'12px',backgroundColor:C.accentLight,border:'1.5px solid '+C.accentBorder}}><p style={{color:C.accent,fontSize:'11px',margin:'0 0 4px'}}>Соответствует</p><b style={{color:C.accent,fontSize:'16px'}}>{cntOk}</b></div>
                        </div>
                        <div style={{display:'flex',justifyContent:'flex-end',marginBottom:'10px'}}>
                          <button onClick={()=>showPreview(buildMaterialInspectionContent(here,p.name,'',''),'Журнал входного контроля — '+p.name)} style={{...btnB,fontSize:'12px',padding:'7px 12px'}}><Eye size={13}/>🖨 Печать журнала</button>
                        </div>
                        <div style={{...card,padding:0,overflow:'auto'}}>
                          <table style={tbl}><thead><tr>
                            <th style={tblH}>Дата приёмки</th>
                            <th style={tblH}>Материал</th>
                            <th style={tblH}>Кол-во</th>
                            <th style={tblH}>Поставщик</th>
                            <th style={tblH}>Партия</th>
                            <th style={tblH}>Сертификат</th>
                            <th style={tblH}>Результат осмотра</th>
                            <th style={tblH}>Статус</th>
                          </tr></thead><tbody>
                            {here.map(mi=>(<tr key={mi.id} style={{cursor:'pointer'}} onClick={()=>setEditingInspection(mi)}>
                              <td style={tblC}>{mi.receivedAt||'—'}</td>
                              <td style={{...tblC,maxWidth:'260px',whiteSpace:'normal'}}>{mi.materialName}{mi.aiFilled?<span title="Заполнено AI" style={{marginLeft:'4px'}}>🤖</span>:null}</td>
                              <td style={tblC}>{(mi.quantity||0)+' '+(mi.unit||'')}</td>
                              <td style={tblC}>{mi.supplier||'—'}</td>
                              <td style={tblC}>{mi.batchNumber||'—'}</td>
                              <td style={tblC}>{mi.certificateNumber||(mi.passportNumber?'паспорт '+mi.passportNumber:'—')}</td>
                              <td style={tblC}>{mi.visualInspectionResult||'—'}</td>
                              <td style={tblC}><span style={{padding:'2px 8px',borderRadius:'10px',fontSize:'11px',fontWeight:'600',backgroundColor:mi.inspected?(mi.visualInspectionResult==='Не соответствует'?C.dangerLight:C.successLight):C.warningLight,color:mi.inspected?(mi.visualInspectionResult==='Не соответствует'?C.danger:C.success):C.warning}}>{mi.inspected?'Проверено':'Ждёт проверки'}</span></td>
                            </tr>))}
                          </tbody></table>
                        </div>
                      </div>);
                    })()}
                  </div>)}
                  {activeProjectTab==='Кабельная продукция'&&(<div>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',flexWrap:'wrap',gap:'10px'}}>
                      <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>⚡ Журнал кабельной продукции</b>
                      <span style={{fontSize:'11px',color:C.textMuted}}>СП 76.13330 · ПУЭ · автоопределение по марке</span>
                    </div>
                    {(()=>{
                      const here=cableJournal.filter(cb=>cb.projectName===p.name);
                      if(here.length===0) return(<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}><div style={{fontSize:'40px',marginBottom:'10px'}}>⚡</div><p style={{margin:'0 0 8px',fontWeight:'600'}}>Записей пока нет</p><p style={{fontSize:'12px',margin:0,lineHeight:1.6}}>Записи создаются автоматически при приходе кабеля (по накладной).<br/>Система распознаёт марки: ВВГ / АВВГ / КВВГ / СИП / UTP / FTP / NYM и др.</p></div>);
                      const cntInstalled=here.filter(cb=>cb.installedAt).length;
                      const cntPending=here.length-cntInstalled;
                      const totalLength=here.reduce((s,cb)=>s+Number(cb.lengthReceived||0),0);
                      return(<div>
                        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(120px,1fr))',gap:'10px',marginBottom:'14px'}}>
                          <div style={{...card,padding:'12px',backgroundColor:C.bg}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Записей</p><b style={{color:C.text,fontSize:'16px'}}>{here.length}</b></div>
                          <div style={{...card,padding:'12px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}><p style={{color:C.warning,fontSize:'11px',margin:'0 0 4px'}}>Ждут монтажа</p><b style={{color:C.warning,fontSize:'16px'}}>{cntPending}</b></div>
                          <div style={{...card,padding:'12px',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder}}><p style={{color:C.success,fontSize:'11px',margin:'0 0 4px'}}>Проложено</p><b style={{color:C.success,fontSize:'16px'}}>{cntInstalled}</b></div>
                          <div style={{...card,padding:'12px',backgroundColor:C.accentLight,border:'1.5px solid '+C.accentBorder}}><p style={{color:C.accent,fontSize:'11px',margin:'0 0 4px'}}>Общая длина</p><b style={{color:C.accent,fontSize:'16px'}}>{totalLength.toLocaleString('ru-RU')+' м'}</b></div>
                        </div>
                        <div style={{display:'flex',justifyContent:'flex-end',marginBottom:'10px'}}>
                          <button onClick={()=>showPreview(buildCableJournalContent(here,p.name,'',''),'Журнал кабельной продукции — '+p.name)} style={{...btnB,fontSize:'12px',padding:'7px 12px'}}><Eye size={13}/>🖨 Печать журнала</button>
                        </div>
                        <div style={{...card,padding:0,overflow:'auto'}}>
                          <table style={tbl}><thead><tr>
                            <th style={tblH}>Дата</th>
                            <th style={tblH}>Марка</th>
                            <th style={tblH}>Сечение</th>
                            <th style={tblH}>Жил</th>
                            <th style={tblH}>Длина</th>
                            <th style={tblH}>Барабан №</th>
                            <th style={tblH}>R изол. ДО</th>
                            <th style={tblH}>R изол. ПОСЛЕ</th>
                            <th style={tblH}>Место прокладки</th>
                            <th style={tblH}>Статус</th>
                          </tr></thead><tbody>
                            {here.map(cb=>(<tr key={cb.id} style={{cursor:'pointer'}} onClick={()=>setEditingCable(cb)}>
                              <td style={tblC}>{cb.receivedAt||'—'}</td>
                              <td style={{...tblC,maxWidth:'220px',whiteSpace:'normal'}}>{cb.cableBrand}{cb.aiFilled?<span title="Заполнено AI" style={{marginLeft:'4px'}}>🤖</span>:null}</td>
                              <td style={tblC}>{cb.crossSection?cb.crossSection+' мм²':'—'}</td>
                              <td style={tblC}>{cb.coresCount||'—'}</td>
                              <td style={tblC}>{(cb.lengthReceived||0)+' м'}</td>
                              <td style={tblC}>{cb.drumNumber||'—'}</td>
                              <td style={tblC}>{cb.insulationBefore?cb.insulationBefore+' МΩ':'—'}</td>
                              <td style={tblC}>{cb.insulationAfter?cb.insulationAfter+' МΩ':'—'}</td>
                              <td style={{...tblC,maxWidth:'220px',whiteSpace:'normal'}}>{cb.installationLocation||'—'}</td>
                              <td style={tblC}><span style={{padding:'2px 8px',borderRadius:'10px',fontSize:'11px',fontWeight:'600',backgroundColor:cb.installedAt?C.successLight:C.warningLight,color:cb.installedAt?C.success:C.warning}}>{cb.installedAt?'Проложен':'На складе'}</span></td>
                            </tr>))}
                          </tbody></table>
                        </div>
                      </div>);
                    })()}
                  </div>)}
                  </div>
                </div>)}
              </div>);
            })}
            {projects.length===0&&<div style={{...card,padding:'40px',textAlign:'center',color:C.textMuted}}><FolderKanban size={48} style={{marginBottom:'15px',opacity:0.3}}/><p>Проектов нет — создайте первый!</p></div>}
          </div>)}
          {activePage==='clients'&&(<div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px'}}>
              <button onClick={()=>{setShowForm(!showForm);setEditingItem(null);setNewClient({name:'',phone:'',email:'',status:'Активный',notes:''});}} style={btnO}><Plus size={14}/>Новый клиент</button>
            </div>
            {showForm&&(<div style={{...card,padding:'20px',marginBottom:'20px'}}>
              <h3 style={{color:C.text,marginBottom:'15px',fontWeight:'700'}}>{editingItem?'Редактировать':'Новый клиент'}</h3>
              <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(200px,1fr))',gap:'10px'}}>
                <input placeholder="Название *" value={newClient.name} onChange={e=>setNewClient({...newClient,name:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder="Телефон" value={newClient.phone} onChange={e=>setNewClient({...newClient,phone:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder="Email" value={newClient.email} onChange={e=>setNewClient({...newClient,email:e.target.value})} style={{...inp,marginBottom:0}}/>
                <select value={newClient.status} onChange={e=>setNewClient({...newClient,status:e.target.value})} style={{...inp,marginBottom:0}}>{['Активный','Потенциальный','Завершён'].map(s=><option key={s}>{s}</option>)}</select>
                <textarea placeholder="Заметки" value={newClient.notes} onChange={e=>setNewClient({...newClient,notes:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2',height:'60px',resize:'vertical'}}/>
              </div>
              <div style={{display:'flex',gap:'10px',marginTop:'15px'}}><button onClick={saveClient} style={btnO}><Check size={14}/>{editingItem?'Сохранить':'Создать'}</button><button onClick={()=>{setShowForm(false);setEditingItem(null);}} style={btnG}><X size={14}/>Отмена</button></div>
            </div>)}
            {clients.map(c=>(<div key={c.id} style={{...card,marginBottom:'10px'}}>
              <div style={{padding:'16px',display:'flex',justifyContent:'space-between',alignItems:'center',cursor:'pointer'}} onClick={()=>setExpandedClient(expandedClient===c.id?null:c.id)}>
                <div><b style={{color:C.text,fontSize:'14px'}}>{c.name}</b><p style={{color:C.textSec,margin:'3px 0',fontSize:'12px'}}>{c.phone+(c.email?' · '+c.email:'')}</p></div>
                <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
                  <button onClick={e=>{e.stopPropagation();setEditingItem(c);setNewClient({...c});setShowForm(true);}} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}><Edit2 size={11}/></button>
                  <button onClick={e=>{e.stopPropagation();deleteClient(c.id);}} style={{...btnR,padding:'5px 10px',fontSize:'11px'}}><Trash2 size={11}/></button>
                </div>
              </div>
              {expandedClient===c.id&&(<div style={{borderTop:'1.5px solid '+C.border,padding:'16px'}}>
                <p style={{color:C.textSec,fontSize:'13px'}}>{c.notes||'Заметок нет'}</p>
                <b style={{color:C.text,fontSize:'13px',display:'block',marginTop:'10px',marginBottom:'8px'}}>Проекты клиента:</b>
                {projects.filter(p=>p.client===c.name).map(p=>(<div key={p.id} style={{padding:'8px 10px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center'}}><span style={{fontSize:'13px',color:C.text}}>{p.name}</span><span style={{fontSize:'12px',color:C.textSec}}>{p.status}</span></div>))}
                {projects.filter(p=>p.client===c.name).length===0&&<p style={{color:C.textMuted,fontSize:'12px'}}>Проектов нет</p>}
              </div>)}
            </div>))}
            {clients.length===0&&<div style={{...card,padding:'40px',textAlign:'center',color:C.textMuted}}>Клиентов нет</div>}
          </div>)}

          {activePage==='warehouse'&&(<div>
            <div style={{display:'flex',gap:'8px',marginBottom:'20px',flexWrap:'wrap'}}>
              {['objects','main','move','invoices','history','tools','inventory','warehouses'].map(tab=>(<button key={tab} onClick={()=>{setWarehouseTab(tab);setShowForm(false);}} style={{...warehouseTab===tab?btnO:btnG,fontSize:'12px',padding:'7px 14px'}}>{{objects:'Объекты',main:'Основной склад',move:'Перемещение',invoices:'Накладные',history:'История',tools:'Инструменты',inventory:'Инвентаризация',warehouses:'Склады'}[tab]}</button>))}
            </div>

            {warehouseTab==='warehouses'&&(<div>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                <b style={{color:C.text}}>Склады компании</b>
                <button onClick={()=>{setShowForm(!showForm);setEditingItem(null);setNewWarehouse({name:'',city:'',address:'',notes:''});}} style={btnO}><Plus size={14}/>Добавить склад</button>
              </div>
              {showForm&&(<div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                  <input placeholder="Название склада *" value={newWarehouse.name} onChange={e=>setNewWarehouse({...newWarehouse,name:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input placeholder="Город" value={newWarehouse.city} onChange={e=>setNewWarehouse({...newWarehouse,city:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input placeholder="Адрес" value={newWarehouse.address} onChange={e=>setNewWarehouse({...newWarehouse,address:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                  <textarea placeholder="Заметки" value={newWarehouse.notes} onChange={e=>setNewWarehouse({...newWarehouse,notes:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2',height:'60px',resize:'vertical'}}/>
                </div>
                <div style={{display:'flex',gap:'8px',marginTop:'12px'}}><button onClick={saveWarehouse} style={btnO}><Check size={14}/>{editingItem?'Сохранить':'Добавить'}</button><button onClick={()=>{setShowForm(false);setEditingItem(null);}} style={btnG}><X size={14}/>Отмена</button></div>
              </div>)}
              {warehouses.map(wh=>(<div key={wh.id} style={{...card,padding:'16px',marginBottom:'10px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                <div><b style={{color:C.text,fontSize:'14px'}}>{'🏭 '+wh.name}</b><p style={{color:C.textSec,margin:'3px 0',fontSize:'12px'}}>{(wh.city?wh.city+', ':'')+wh.address}</p>{wh.notes&&<p style={{color:C.textMuted,margin:'0',fontSize:'11px'}}>{wh.notes}</p>}</div>
                <div style={{display:'flex',gap:'6px'}}>
                  <button onClick={()=>{setEditingItem(wh);setNewWarehouse({name:wh.name,city:wh.city,address:wh.address,notes:wh.notes});setShowForm(true);}} style={{...btnG,padding:'5px 10px'}}><Edit2 size={11}/></button>
                  <button onClick={()=>deleteWarehouse(wh.id)} style={{...btnR,padding:'5px 10px'}}><Trash2 size={11}/></button>
                </div>
              </div>))}
              {warehouses.length===0&&<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Складов нет — добавьте первый!</div>}
            </div>)}

            {warehouseTab==='objects'&&(<div>
              {!selectedWarehouseProject?(<div>
                <h3 style={{color:C.text,marginBottom:'15px',fontSize:'15px',fontWeight:'700'}}>Материалы по объектам</h3>
                {projects.map(p=>{const mats=materials.filter(m=>m.project===p.name);const total=mats.reduce((s,m)=>s+m.price*m.quantity,0);return(<div key={p.id} style={{...card,padding:'16px',marginBottom:'10px',cursor:'pointer',display:'flex',justifyContent:'space-between',alignItems:'center'}} onClick={()=>setSelectedWarehouseProject(p.name)}><div><b style={{color:C.text,fontSize:'14px'}}>{p.name}</b><p style={{color:C.textSec,margin:'3px 0',fontSize:'12px'}}>{mats.length+' позиций · '+total.toLocaleString()+' ₽'}</p></div><ChevronRight size={18} color={C.textMuted}/></div>);})}
              </div>):(<div>
                <div style={{display:'flex',gap:'10px',alignItems:'center',marginBottom:'15px'}}>
                  <button onClick={()=>setSelectedWarehouseProject(null)} style={btnG}><ArrowLeft size={14}/>Назад</button>
                  <h3 style={{color:C.text,margin:0,fontSize:'15px',fontWeight:'700'}}>{selectedWarehouseProject}</h3>
                </div>
                <div style={{display:'flex',gap:'8px',marginBottom:'15px'}}>
                  <button onClick={()=>openReceiveInvoice(selectedWarehouseProject)} style={btnO}><Plus size={14}/>Принять материал</button>
                  <button onClick={()=>exportToExcel(materials.filter(m=>m.project===selectedWarehouseProject).map(m=>({Наименование:m.name,Единица:m.unit,Количество:m.quantity,Цена:m.price,Сумма:m.quantity*m.price,Проект:m.project})),'Склад_'+selectedWarehouseProject)} style={btnG}><Download size={14}/>Excel</button>
                </div>
                <table style={tbl}><thead><tr><th style={tblH}>Наименование</th><th style={tblH}>Кат.</th><th style={tblH}>Кол-во</th><th style={tblH}>Цена</th><th style={tblH}>Сумма</th><th style={tblH}></th></tr></thead><tbody>
                  {materials.filter(m=>m.project===selectedWarehouseProject).map(m=>(<tr key={m.id} style={{backgroundColor:m.minQuantity&&m.quantity<m.minQuantity?C.dangerLight:'transparent'}}>
                    <td style={tblC}><b style={{fontSize:'13px'}}>{m.name}</b>{m.minQuantity&&m.quantity<m.minQuantity&&<span style={{...badge(C.danger,C.dangerLight,C.dangerBorder),marginLeft:'6px',fontSize:'10px'}}>Мало!</span>}</td>
                    <td style={{...tblC,fontSize:'11px',color:C.textSec}}>{m.category||'—'}</td>
                    <td style={tblC}>{m.quantity+' '+m.unit}</td>
                    <td style={tblC}>{m.price.toLocaleString()+' ₽'}</td>
                    <td style={{...tblC,fontWeight:'600'}}>{(m.price*m.quantity).toLocaleString()+' ₽'}</td>
                    <td style={tblC}><button onClick={()=>deleteMaterial(m.id)} style={{...btnR,padding:'3px 7px'}}><Trash2 size={11}/></button></td>
                  </tr>))}
                </tbody></table>
              </div>)}
            </div>)}

            {warehouseTab==='main'&&(<div>
              <div style={{display:'flex',gap:'8px',marginBottom:'15px',flexWrap:'wrap'}}>
                <button onClick={()=>openReceiveInvoice('Основной склад')} style={btnO}><Plus size={14}/>Принять материал</button>
                <button onClick={()=>exportToExcel(warehouseMain.map(m=>({Наименование:m.name,Единица:m.unit,Количество:m.quantity,Цена:m.price,Сумма:m.quantity*m.price})),'Основной_склад')} style={btnG}><Download size={14}/>Excel</button>
              </div>
              <table style={tbl}><thead><tr><th style={tblH}>Наименование</th><th style={tblH}>Категория</th><th style={tblH}>Кол-во</th><th style={tblH}>Цена</th><th style={tblH}>Сумма</th><th style={tblH}></th></tr></thead><tbody>
                {warehouseMain.map(m=>(<tr key={m.id} style={{backgroundColor:m.minQuantity&&m.quantity<m.minQuantity?C.dangerLight:'transparent'}}>
                  <td style={tblC}><b style={{fontSize:'13px'}}>{m.name}</b>{m.minQuantity&&m.quantity<m.minQuantity&&<span style={{...badge(C.danger,C.dangerLight,C.dangerBorder),marginLeft:'6px',fontSize:'10px'}}>Мало!</span>}</td>
                  <td style={{...tblC,fontSize:'11px',color:C.textSec}}>{m.category||'—'}</td>
                  <td style={tblC}>{m.quantity+' '+m.unit}</td>
                  <td style={tblC}>{m.price.toLocaleString()+' ₽'}</td>
                  <td style={{...tblC,fontWeight:'600'}}>{(m.price*m.quantity).toLocaleString()+' ₽'}</td>
                  <td style={tblC}><button onClick={()=>deleteMainMaterial(m.id)} style={{...btnR,padding:'3px 7px'}}><Trash2 size={11}/></button></td>
                </tr>))}
              </tbody></table>
              {warehouseMain.length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Склад пуст</p>}
            </div>)}

            {warehouseTab==='move'&&(<div>
              <h3 style={{color:C.text,marginBottom:'15px',fontSize:'15px',fontWeight:'700'}}>Перемещение материалов</h3>
              <div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px',marginBottom:'15px'}}>
                  <div>
                    <label style={{fontSize:'12px',color:C.textSec,display:'block',marginBottom:'5px'}}>Откуда:</label>
                    <select value={newMovement.fromLocation} onChange={e=>setNewMovement({...newMovement,fromLocation:e.target.value,selectedMaterials:[]})} style={inp}>
                      <option value="Основной склад">Основной склад</option>
                      {projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label style={{fontSize:'12px',color:C.textSec,display:'block',marginBottom:'5px'}}>Куда:</label>
                    <select value={newMovement.toLocation} onChange={e=>setNewMovement({...newMovement,toLocation:e.target.value})} style={inp}>
                      <option value="">Выберите...</option>
                      <option value="Основной склад">Основной склад</option>
                      {projects.filter(p=>p.name!==newMovement.fromLocation).map(p=><option key={p.id} value={p.name}>{p.name}</option>)}
                    </select>
                  </div>
                </div>
                <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'10px'}}>Выберите материалы:</b>
                {(newMovement.fromLocation==='Основной склад'?warehouseMain:materials.filter(m=>m.project===newMovement.fromLocation)).map(m=>{
                  const sel=newMovement.selectedMaterials?.find(s=>s.name===m.name);
                  return(<div key={m.id} style={{padding:'10px',borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+(sel?C.accent:C.border),backgroundColor:sel?C.accentLight:C.bgWhite,display:'flex',alignItems:'center',gap:'10px'}}>
                    <input type="checkbox" checked={!!sel} onChange={e=>{if(e.target.checked) setNewMovement(prev=>({...prev,selectedMaterials:[...(prev.selectedMaterials||[]),{...m,quantity:''}]}));else setNewMovement(prev=>({...prev,selectedMaterials:(prev.selectedMaterials||[]).filter(s=>s.name!==m.name)}));}} style={{width:'16px',height:'16px',accentColor:C.accent}}/>
                    <span style={{flex:1,fontSize:'13px',color:C.text}}>{m.name+' (есть: '+m.quantity+' '+m.unit+')'}</span>
                    {sel&&<input placeholder="Кол-во" type="number" value={sel.quantity} onChange={e=>setNewMovement(prev=>({...prev,selectedMaterials:prev.selectedMaterials.map(s=>s.name===m.name?{...s,quantity:e.target.value}:s)}))} style={{width:'100px',padding:'5px 8px',border:'1.5px solid '+C.accent,borderRadius:'6px',fontSize:'12px'}}/>}
                  </div>);
                })}
                <input placeholder="Примечание" value={newMovement.notes} onChange={e=>setNewMovement({...newMovement,notes:e.target.value})} style={{...inp,marginTop:'10px'}}/>
                <div style={{display:'flex',gap:'8px',marginTop:'10px'}}>
                  <button onClick={async()=>{await applyWarehouseMovement();showPreview(buildMovementDoc(newMovement,(newMovement.selectedMaterials||[]).filter(s=>s.quantity)),'Накладная М-11');}} style={btnO}><Check size={14}/>Переместить и распечатать</button>
                  <button onClick={applyWarehouseMovement} style={btnG}>Переместить</button>
                </div>
              </div>
              <h3 style={{color:C.text,marginBottom:'10px',fontSize:'14px',fontWeight:'700'}}>История перемещений</h3>
              <table style={tbl}><thead><tr><th style={tblH}>Материал</th><th style={tblH}>Откуда</th><th style={tblH}>Куда</th><th style={tblH}>Кол-во</th><th style={tblH}>Дата</th></tr></thead><tbody>
                {warehouseMovements.slice(0,20).map((m,i)=>(<tr key={i}><td style={tblC}>{m.materialName}</td><td style={tblC}>{m.fromLocation}</td><td style={tblC}>{m.toLocation}</td><td style={tblC}>{m.quantity+' '+m.unit}</td><td style={tblC}>{m.date}</td></tr>))}
              </tbody></table>
            </div>)}

            {warehouseTab==='invoices'&&(<div>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Накладные</b>
                <button onClick={()=>setShowForm(!showForm)} style={btnO}><Plus size={14}/>Новая накладная</button>
              </div>
              {showForm&&(<div style={{...card,padding:'20px',marginBottom:'20px'}}>
                <h3 style={{color:C.text,marginBottom:'15px',fontWeight:'700'}}>Новая приходная накладная</h3>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                  <input placeholder="Номер накладной *" value={newInvoice.number} onChange={e=>setNewInvoice({...newInvoice,number:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input type="date" value={newInvoice.date} onChange={e=>setNewInvoice({...newInvoice,date:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <div style={{gridColumn:'span 2'}}>
                    <label style={{fontSize:'12px',color:C.textSec,display:'flex',alignItems:'center',gap:'8px',marginBottom:'8px',cursor:'pointer'}}><input type="checkbox" checked={newInvoice.isNewSupplier} onChange={e=>setNewInvoice({...newInvoice,isNewSupplier:e.target.checked})} style={{accentColor:C.accent}}/>Новый поставщик</label>
                    {newInvoice.isNewSupplier?<input placeholder="Название поставщика *" value={newInvoice.newSupplierName} onChange={e=>setNewInvoice({...newInvoice,newSupplierName:e.target.value})} style={inp}/>:<select value={newInvoice.supplierId} onChange={e=>setNewInvoice({...newInvoice,supplierId:e.target.value})} style={inp}><option value="">Выберите поставщика</option>{suppliers.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select>}
                  </div>
                  <input placeholder="Принял" value={newInvoice.acceptedBy} onChange={e=>setNewInvoice({...newInvoice,acceptedBy:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <select value={newInvoice.vat} onChange={e=>setNewInvoice({...newInvoice,vat:e.target.value})} style={{...inp,marginBottom:0}}>{VAT_OPTIONS.map(v=><option key={v}>{v}</option>)}</select>
                  <div style={{gridColumn:'span 2'}}>
                    <label style={{fontSize:'12px',color:C.textSec,display:'block',marginBottom:'5px'}}>Куда оприходовать:</label>
                    <select value={newInvoice.location} onChange={e=>setNewInvoice({...newInvoice,location:e.target.value,project:e.target.value==='Основной склад'?'':newInvoice.project})} style={inp}>
                      <option value="Основной склад">Основной склад</option>
                      {projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}
                    </select>
                  </div>
                </div>
                <div style={{marginTop:'10px',marginBottom:'10px'}}>
                  {newInvoice.location!=='Основной склад'&&estimatesList.filter(e=>(e.projectName===newInvoice.location)&&e.smetaType==='Материалы').length>0&&(
                    <div style={{padding:'10px',backgroundColor:C.infoLight,borderRadius:'8px',border:'1.5px solid '+C.infoBorder}}>
                      <p style={{color:C.info,fontSize:'12px',margin:'0 0 6px',fontWeight:'600'}}>📊 Сметы материалов по объекту:</p>
                      <div style={{display:'flex',gap:'6px',flexWrap:'wrap'}}>
                        {estimatesList.filter(e=>e.projectName===newInvoice.location&&e.smetaType==='Материалы').map(est=>(
                          <button key={est.id} onClick={()=>{
                            const smetaItems=(est.sections||[]).flatMap(s=>s.items||[]);
                            const invoiceItems=newInvoice.items.filter(i=>i.name&&i.quantity);
                            let report='📊 СВЕРКА НАКЛАДНОЙ СО СМЕТОЙ\n';
                            report+='Смета: '+est.name+'\n\n';
                            invoiceItems.forEach(invItem=>{
                              const norm=(s)=>s.toLowerCase().replace(/[хx×]/g,'x').replace(/[,.]/g,'.').replace(/\s+/g,' ').trim();const smetaItem=smetaItems.find(si=>norm(si.name).includes(norm(invItem.name))||norm(invItem.name).includes(norm(si.name))||norm(si.name).split(' ').filter(w=>w.length>3).every(w=>norm(invItem.name).includes(w)));
                              if(smetaItem){
                                const need=Number(smetaItem.quantity||0);
                                const got=Number(invItem.quantity||0);
                                const diff=need-got;
                                report+=`✅ ${invItem.name}\n`;
                                report+=`   По смете: ${need} ${smetaItem.unit}\n`;
                                report+=`   Получено: ${got} ${invItem.unit}\n`;
                                report+=diff>0?`   ⚠️ Дефицит: ${diff}\n\n`:`   ✅ Достаточно\n\n`;
                              } else {
                                report+=`❓ ${invItem.name} — не найдено в смете\n\n`;
                              }
                            });
                            setSverkaModal({title:'Сверка накладной со сметой '+est.name,text:report});
                          }} style={{...btnB,fontSize:'11px',padding:'5px 10px'}}>🔍 Сверить с {est.name}</button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
                <b style={{color:C.text,fontSize:'13px',display:'block',marginTop:'15px',marginBottom:'10px'}}>Позиции накладной:</b>
                {newInvoice.items.map((item,idx)=>(<div key={idx} style={{display:'grid',gridTemplateColumns:'3fr 1fr 1fr 1fr 2fr auto',gap:'6px',marginBottom:'8px',alignItems:'center'}}>
                  <input placeholder="Наименование товара *" value={item.name} onChange={e=>{const items=[...newInvoice.items];items[idx]={...items[idx],name:e.target.value};setNewInvoice({...newInvoice,items});}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                  <input placeholder="Кол-во *" type="number" value={item.quantity} onChange={e=>{const items=[...newInvoice.items];items[idx]={...items[idx],quantity:e.target.value};setNewInvoice({...newInvoice,items});}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                  <select value={item.unit} onChange={e=>{const items=[...newInvoice.items];items[idx]={...items[idx],unit:e.target.value};setNewInvoice({...newInvoice,items});}} style={{...inp,marginBottom:0,fontSize:'12px'}}>{UNITS.map(u=><option key={u}>{u}</option>)}</select>
                  <input placeholder="Цена ₽" type="number" value={item.price} onChange={e=>{const items=[...newInvoice.items];items[idx]={...items[idx],price:e.target.value};setNewInvoice({...newInvoice,items});}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                  <select value={item.category} onChange={e=>{const items=[...newInvoice.items];items[idx]={...items[idx],category:e.target.value};setNewInvoice({...newInvoice,items});}} style={{...inp,marginBottom:0,fontSize:'12px'}}><option value="">Категория</option>{MATERIAL_CATEGORIES.map(c=><option key={c}>{c}</option>)}</select>
                  <button onClick={()=>{const items=newInvoice.items.filter((_,i)=>i!==idx);setNewInvoice({...newInvoice,items:items.length?items:[{name:'',quantity:'',unit:'шт',price:'',category:''}]});}} style={{...btnR,padding:'5px 8px'}}><X size={12}/></button>
                </div>))}
                <button onClick={()=>setNewInvoice({...newInvoice,items:[...newInvoice.items,{name:'',quantity:'',unit:'шт',price:'',category:''}]})} style={{...btnG,fontSize:'12px',marginBottom:'15px'}}><Plus size={13}/>Добавить строку</button>
                <div style={{display:'flex',gap:'8px',alignItems:'center',marginBottom:'15px',flexWrap:'wrap'}}>
                  <label style={{cursor:'pointer',backgroundColor:C.infoLight,padding:'8px 14px',borderRadius:'8px',fontSize:'13px',color:C.info,border:'1.5px solid '+C.infoBorder,display:'inline-flex',alignItems:'center',gap:'6px'}}><Upload size={13}/>Добавить фото<input type="file" accept="image/*" multiple style={{display:'none'}} onChange={async e=>{const files=Array.from(e.target.files);const urls=await Promise.all(files.map(f=>uploadPhoto(f)));setNewInvoice(prev=>({...prev,photos:[...(prev.photos||[]),...urls.filter(Boolean)]}));}}/></label>
                  {(newInvoice.photos||[]).map((url,i)=>(<img key={i} src={url} alt="" onClick={()=>setShowPhotoModal(url)} style={{width:'48px',height:'48px',borderRadius:'8px',objectFit:'cover',cursor:'pointer',border:'1.5px solid '+C.border}}/>))}
                </div>
                <div style={{backgroundColor:C.bg,borderRadius:'10px',padding:'12px',marginBottom:'15px',border:'1.5px solid '+C.border}}>
                  <div style={{display:'flex',justifyContent:'space-between',marginBottom:'4px'}}><span style={{color:C.textSec,fontSize:'13px'}}>Итого без НДС:</span><b style={{color:C.text,fontSize:'13px'}}>{newInvoice.items.reduce((s,i)=>s+Number(i.quantity||0)*Number(i.price||0),0).toLocaleString()+' ₽'}</b></div>
                  {newInvoice.vat==='С НДС 22%'&&(<><div style={{display:'flex',justifyContent:'space-between',marginBottom:'4px'}}><span style={{color:C.textSec,fontSize:'13px'}}>НДС 22%:</span><b style={{color:C.text,fontSize:'13px'}}>{Math.round(newInvoice.items.reduce((s,i)=>s+Number(i.quantity||0)*Number(i.price||0),0)/1.22*0.22).toLocaleString()+' ₽'}</b></div><div style={{display:'flex',justifyContent:'space-between'}}><b style={{color:C.text,fontSize:'13px'}}>Итого с НДС:</b><b style={{color:C.accent,fontSize:'15px'}}>{newInvoice.items.reduce((s,i)=>s+Number(i.quantity||0)*Number(i.price||0),0).toLocaleString()+' ₽'}</b></div></>)}
                </div>
                <div style={{display:'flex',gap:'8px'}}><button onClick={saveInvoiceNew} style={btnO}><Check size={14}/>Сохранить и оприходовать</button><button onClick={()=>setShowForm(false)} style={btnG}><X size={14}/>Отмена</button></div>
              </div>)}
              {invoices.map(inv=>{const items=Array.isArray(inv.items)?inv.items:[];return(<div key={inv.id} style={{...card,padding:'16px',marginBottom:'10px'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
                  <div>
                    <b style={{color:C.text,fontSize:'14px'}}>{'Накладная № '+inv.number}</b>
                    <p style={{color:C.textSec,margin:'3px 0',fontSize:'12px'}}>{inv.date+' · '+inv.supplierName+' · '+(inv.location==='Основной склад'?'Основной склад':inv.project||'')}</p>
                    <p style={{color:C.textSec,margin:'0',fontSize:'12px'}}>{'Принял: '+inv.acceptedBy+' · '+inv.vat+' · позиций: '+items.length}</p>
                  </div>
                  <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
                    <b style={{color:C.success,fontSize:'14px'}}>{(inv.totalWithVat||inv.totalBase||0).toLocaleString()+' ₽'}</b>
                    <button onClick={()=>showPreview(buildInvoiceContent(inv),'Накладная № '+inv.number)} style={btnB} title="Печать"><Eye size={13}/></button>
                    <button onClick={()=>setShowQRModal({title:'QR накладной №'+inv.number,data:window.location.origin+'/?invoice='+inv.id})} style={btnG} title="QR-код накладной — отсканировав, можно быстро открыть на телефоне на стройке"><QrCode size={13}/></button>
                  </div>
                </div>
                {items.length>0&&(<details style={{marginTop:'10px'}}>
                  <summary style={{cursor:'pointer',color:C.accent,fontSize:'12px',fontWeight:'600',padding:'4px 0'}}>📋 Показать материалы ({items.length})</summary>
                  <div style={{marginTop:'8px',overflowX:'auto'}}>
                    <table style={{...tbl,fontSize:'11px'}}><thead><tr><th style={tblH}>Наименование</th><th style={tblH}>Ед.</th><th style={tblH}>Кол-во</th><th style={tblH}>Цена</th><th style={tblH}>Сумма</th></tr></thead><tbody>
                      {items.map((it,i)=>(<tr key={i}><td style={tblC}>{it.name||''}</td><td style={tblC}>{it.unit||''}</td><td style={tblC}>{it.quantity||0}</td><td style={tblC}>{Number(it.price||0).toLocaleString('ru-RU')+' ₽'}</td><td style={tblC}>{Number((it.quantity||0)*(it.price||0)).toLocaleString('ru-RU')+' ₽'}</td></tr>))}
                    </tbody></table>
                  </div>
                </details>)}
                {(inv.photos||[]).length>0&&(<div style={{display:'flex',gap:'6px',marginTop:'10px',flexWrap:'wrap'}}>{(inv.photos||[]).map((url,i)=>(<img key={i} src={url} alt="" onClick={()=>setShowPhotoModal(url)} style={{width:'50px',height:'50px',borderRadius:'8px',objectFit:'cover',cursor:'pointer',border:'1.5px solid '+C.border}}/>))}</div>)}
              </div>);})}
              {invoices.length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Накладных нет</p>}
            </div>)}

            {warehouseTab==='history'&&(<div>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>История движения</b>
                <button onClick={()=>exportToExcel(history.map(h=>({Материал:h.material,Тип:h.type,Количество:h.quantity,Дата:h.date,Проект:h.project,Кому:h.issuedTo||''})),'История_склада')} style={btnG}><Download size={14}/>Excel</button>
              </div>
              <table style={tbl}><thead><tr><th style={tblH}>Материал</th><th style={tblH}>Тип</th><th style={tblH}>Кол-во</th><th style={tblH}>Проект</th><th style={tblH}>Дата</th></tr></thead><tbody>
                {history.slice(0,50).map((h,i)=>(<tr key={i}><td style={tblC}>{h.material}</td><td style={tblC}><span style={badge(h.type==='приход'?C.success:C.danger,h.type==='приход'?C.successLight:C.dangerLight,h.type==='приход'?C.successBorder:C.dangerBorder)}>{h.type}</span></td><td style={tblC}>{h.quantity}</td><td style={tblC}>{h.project}</td><td style={tblC}>{h.date}</td></tr>))}
              </tbody></table>
            </div>)}

            {warehouseTab==='tools'&&(<div>
              <div style={{display:'flex',gap:'8px',marginBottom:'15px',flexWrap:'wrap'}}>
                {['list','history'].map(t=>(<button key={t} onClick={()=>setToolsTab(t)} style={{...toolsTab===t?btnO:btnG,fontSize:'12px',padding:'6px 14px'}}>{{list:'Список',history:'История'}[t]}</button>))}
                <button onClick={()=>{setShowForm(!showForm);setEditingItem(null);setNewTool({name:'',inventoryNumber:'',cost:'',status:'На складе',location:'Основной склад',project:'',masterId:'',masterName:'',issueType:'',notes:''});}} style={btnO}><Plus size={14}/>Добавить</button>
              </div>
              {showForm&&(<div style={{...card,padding:'20px',marginBottom:'15px'}}>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                  <input placeholder="Название *" value={newTool.name} onChange={e=>setNewTool({...newTool,name:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input placeholder="Инв. №" value={newTool.inventoryNumber} onChange={e=>setNewTool({...newTool,inventoryNumber:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input placeholder="Стоимость (₽)" type="number" value={newTool.cost} onChange={e=>setNewTool({...newTool,cost:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <select value={newTool.status} onChange={e=>setNewTool({...newTool,status:e.target.value})} style={{...inp,marginBottom:0}}>{TOOL_STATUSES.map(s=><option key={s}>{s}</option>)}</select>
                  <textarea placeholder="Примечание" value={newTool.notes} onChange={e=>setNewTool({...newTool,notes:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2',height:'60px',resize:'vertical'}}/>
                </div>
                <div style={{display:'flex',gap:'8px',marginTop:'12px'}}><button onClick={saveTool} style={btnO}><Check size={14}/>{editingItem?'Сохранить':'Добавить'}</button><button onClick={()=>{setShowForm(false);setEditingItem(null);}} style={btnG}><X size={14}/>Отмена</button></div>
              </div>)}
              {toolsTab==='list'&&(<table style={tbl}><thead><tr><th style={tblH}>Инструмент</th><th style={tblH}>Инв. №</th><th style={tblH}>Статус</th><th style={tblH}>У кого</th><th style={tblH}>Стоимость</th><th style={tblH}></th></tr></thead><tbody>
                {tools.map(t=>(<tr key={t.id}><td style={tblC}><b style={{fontSize:'13px'}}>{t.name}</b>{t.notes&&<p style={{color:C.textMuted,margin:'1px 0',fontSize:'11px'}}>{t.notes}</p>}</td><td style={tblC}>{t.inventoryNumber||'—'}</td><td style={tblC}><span style={badge(t.status==='На складе'?C.success:t.status.includes('У мастера')?C.accent:t.status==='На ремонте'?C.warning:C.danger,t.status==='На складе'?C.successLight:t.status.includes('У мастера')?C.accentLight:t.status==='На ремонте'?C.warningLight:C.dangerLight,t.status==='На складе'?C.successBorder:t.status.includes('У мастера')?C.accentBorder:t.status==='На ремонте'?C.warningBorder:C.dangerBorder)}>{t.status}</span></td><td style={tblC}>{t.masterName?t.masterName+(t.project?' ('+t.project+')':''):'—'}</td><td style={tblC}>{t.cost?(t.cost.toLocaleString()+' ₽'):'—'}{t.issueType==='В счёт зарплаты'&&<span style={{...badge(C.danger,C.dangerLight,C.dangerBorder),marginLeft:'4px',fontSize:'10px'}}>Удержание</span>}</td><td style={tblC}><div style={{display:'flex',gap:'4px'}}>{t.status==='На складе'&&isProrab()&&<button onClick={()=>setShowIssueToolModal(t)} style={{...btnO,padding:'4px 8px',fontSize:'11px'}}>Выдать</button>}{t.status.includes('У мастера')&&isProrab()&&<button onClick={()=>setShowReturnToolModal(t)} style={{...btnGr,padding:'4px 8px',fontSize:'11px'}}>Вернуть</button>}<button onClick={()=>{setEditingItem(t);setNewTool({...t,cost:String(t.cost)});setShowForm(true);}} style={{...btnG,padding:'4px 8px'}}><Edit2 size={11}/></button><button onClick={()=>deleteTool(t.id)} style={{...btnR,padding:'4px 8px'}}><Trash2 size={11}/></button></div></td></tr>))}
              </tbody></table>)}
              {toolsTab==='history'&&(<table style={tbl}><thead><tr><th style={tblH}>Инструмент</th><th style={tblH}>Действие</th><th style={tblH}>Мастер</th><th style={tblH}>Объект</th><th style={tblH}>Состояние</th><th style={tblH}>Дата</th></tr></thead><tbody>
                {toolHistory.map((h,i)=>(<tr key={i}><td style={tblC}>{h.toolName}</td><td style={tblC}><span style={badge(h.action==='Выдача'?C.accent:C.success,h.action==='Выдача'?C.accentLight:C.successLight,h.action==='Выдача'?C.accentBorder:C.successBorder)}>{h.action}</span></td><td style={tblC}>{h.masterName}</td><td style={tblC}>{h.project}</td><td style={tblC}>{h.condition}</td><td style={tblC}>{h.date}</td></tr>))}
              </tbody></table>)}
            </div>)}

            {warehouseTab==='inventory'&&(<div>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Инвентаризация</b>
                <button onClick={()=>setShowForm(!showForm)} style={btnO}><Plus size={14}/>Новая</button>
              </div>
              {showForm&&(<div style={{...card,padding:'20px',marginBottom:'15px'}}>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                  <select value={newInventory.project} onChange={e=>setNewInventory({...newInventory,project:e.target.value})} style={{...inp,marginBottom:0}}><option value="">Выберите объект</option>{projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}</select>
                  <input type="date" value={newInventory.date} onChange={e=>setNewInventory({...newInventory,date:e.target.value})} style={{...inp,marginBottom:0}}/>
                </div>
                <div style={{display:'flex',gap:'8px',marginTop:'12px'}}>
                  <button onClick={async()=>{if(!newInventory.project||!newInventory.date) return;const res=await fetch(API+'/inventory',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newInventory,createdBy:user.name})});const inv=await res.json();await loadAll();setSelectedInventory(inv);setShowForm(false);}} style={btnO}><Check size={14}/>Создать</button>
                  <button onClick={()=>setShowForm(false)} style={btnG}><X size={14}/>Отмена</button>
                </div>
              </div>)}
              {selectedInventory&&(<div style={{...card,padding:'20px',marginBottom:'15px'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                  <b style={{color:C.text}}>{'Инвентаризация: '+selectedInventory.project}</b>
                  <div style={{display:'flex',gap:'6px'}}>
                    <button onClick={async()=>{const items=await fetch(API+'/inventory/'+selectedInventory.id+'/items').then(r=>r.json());showPreview(buildInventoryDoc(selectedInventory,items),'Акт инвентаризации');}} style={btnB}><Eye size={14}/>Акт</button>
                    <button onClick={()=>setSelectedInventory(null)} style={btnG}><X size={14}/>Закрыть</button>
                  </div>
                </div>
                <p style={{color:C.textSec,fontSize:'13px',marginBottom:'15px'}}>Введите фактические остатки:</p>
                {materials.filter(m=>m.project===selectedInventory.project).map(m=>(<div key={m.id} style={{display:'grid',gridTemplateColumns:'3fr 1fr 1fr',gap:'8px',alignItems:'center',marginBottom:'8px',padding:'10px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border}}>
                  <span style={{fontSize:'13px',color:C.text}}>{m.name}</span>
                  <span style={{fontSize:'12px',color:C.textSec}}>{'По учёту: '+m.quantity+' '+m.unit}</span>
                  <input placeholder="Факт" type="number" defaultValue={m.quantity} onBlur={async e=>{const actual=Number(e.target.value);await fetch(API+'/inventory/'+selectedInventory.id+'/items',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({materialName:m.name,unit:m.unit,expected:m.quantity,actual,difference:actual-m.quantity,price:m.price})});}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                </div>))}
              </div>)}
              {inventory.map(inv=>(<div key={inv.id} style={{...card,padding:'14px',marginBottom:'8px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                <div><b style={{color:C.text,fontSize:'13px'}}>{'Инвентаризация: '+inv.project}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{inv.date}</p></div>
                <div style={{display:'flex',gap:'6px'}}>
                  <button onClick={()=>setSelectedInventory(inv)} style={btnG}><Edit2 size={13}/>Открыть</button>
                  <button onClick={async()=>{const items=await fetch(API+'/inventory/'+inv.id+'/items').then(r=>r.json());showPreview(buildInventoryDoc(inv,items),'Акт инвентаризации');}} style={btnB}><Eye size={13}/>Акт</button>
                </div>
              </div>))}
            </div>)}
          </div>)}
          {activePage==='suppliers'&&(<div>
            <div style={{display:'flex',gap:'8px',marginBottom:'20px',flexWrap:'wrap'}}>
              {['active','requests','offers','history'].map(tab=>(<button key={tab} onClick={()=>{setSuppliersTab(tab);setShowForm(false);}} style={{...suppliersTab===tab?btnO:btnG,fontSize:'12px',padding:'7px 14px'}}>{{active:'Поставщики',requests:'Заявки',offers:'КП',history:'История'}[tab]}</button>))}
            </div>

            {suppliersTab==='active'&&(<div>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Поставщики</b>
                <button onClick={()=>{setShowForm(!showForm);setEditingItem(null);setNewSupplier({name:'',phone:'',email:'',specialization:'',category:'Сыпучие и бетон',rating:5.0,status:'Активный'});}} style={btnO}><Plus size={14}/>Добавить</button>
              </div>
              {showForm&&(<div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                  <input placeholder="Название *" value={newSupplier.name} onChange={e=>setNewSupplier({...newSupplier,name:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input placeholder="Телефон" value={newSupplier.phone} onChange={e=>setNewSupplier({...newSupplier,phone:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input placeholder="Email" value={newSupplier.email} onChange={e=>setNewSupplier({...newSupplier,email:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <select value={newSupplier.category} onChange={e=>setNewSupplier({...newSupplier,category:e.target.value})} style={{...inp,marginBottom:0}}>{SUPPLIER_CATEGORIES.map(c=><option key={c}>{c}</option>)}</select>
                  <input placeholder="Специализация" value={newSupplier.specialization} onChange={e=>setNewSupplier({...newSupplier,specialization:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <select value={newSupplier.status} onChange={e=>setNewSupplier({...newSupplier,status:e.target.value})} style={{...inp,marginBottom:0}}>{['Активный','Неактивный','Заблокирован'].map(s=><option key={s}>{s}</option>)}</select>
                </div>
                <div style={{display:'flex',gap:'8px',marginTop:'12px'}}><button onClick={saveSupplier} style={btnO}><Check size={14}/>{editingItem?'Сохранить':'Добавить'}</button><button onClick={()=>{setShowForm(false);setEditingItem(null);}} style={btnG}><X size={14}/>Отмена</button></div>
              </div>)}
              {SUPPLIER_CATEGORIES.map(cat=>{
                const catSuppliers=suppliers.filter(s=>s.category===cat);
                if(catSuppliers.length===0) return null;
                return(<div key={cat} style={{marginBottom:'20px'}}>
                  <div style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'10px',padding:'8px 12px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border}}>
                    <b style={{color:C.accent,fontSize:'13px'}}>{'🏭 '+cat}</b>
                    <span style={{color:C.textSec,fontSize:'12px'}}>{'('+catSuppliers.length+')'}</span>
                  </div>
                  {catSuppliers.map(s=>(<div key={s.id} style={{...card,padding:'14px',marginBottom:'8px',marginLeft:'12px'}}>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                      <div><b style={{color:C.text,fontSize:'13px'}}>{s.name}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{s.phone+(s.email?' · '+s.email:'')+(s.specialization?' · '+s.specialization:'')}</p><div style={{display:'flex',gap:'4px',marginTop:'4px'}}>{[1,2,3,4,5].map(star=>(<span key={star} style={{color:star<=s.rating?'#f59e0b':'#d1d5db',fontSize:'14px',cursor:'pointer'}} onClick={async()=>{await fetch(API+'/suppliers/'+s.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...s,rating:star})});await loadAll();}}>★</span>))}</div></div>
                      <div style={{display:'flex',gap:'6px'}}>
                        <button onClick={()=>{setEditingItem(s);setNewSupplier({...s});setShowForm(true);}} style={{...btnG,padding:'5px 10px'}}><Edit2 size={11}/></button>
                        <button onClick={()=>deleteSupplier(s.id)} style={{...btnR,padding:'5px 10px'}}><Trash2 size={11}/></button>
                      </div>
                    </div>
                  </div>))}
                </div>);
              })}
              {suppliers.length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Поставщиков нет</p>}
            </div>)}

            {suppliersTab==='requests'&&(<div>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Заявки на материалы</b>
                <button onClick={()=>setShowForm(!showForm)} style={btnO}><Plus size={14}/>Новая заявка</button>
              </div>
              {showForm&&(<div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <select value={newRequest.project} onChange={e=>setNewRequest({...newRequest,project:e.target.value})} style={inp}><option value="">Выберите объект *</option>{projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}</select>
                <select value={newRequest.category} onChange={e=>setNewRequest({...newRequest,category:e.target.value})} style={inp}><option value="">Категория материала</option>{SUPPLIER_CATEGORIES.map(c=><option key={c}>{c}</option>)}</select>
                {newRequest.items.map((item,idx)=>(<div key={idx} style={{display:'grid',gridTemplateColumns:'3fr 1fr 1fr auto',gap:'8px',marginBottom:'8px',alignItems:'center'}}>
                  <input placeholder="Материал *" value={item.materialName} onChange={e=>{const items=[...newRequest.items];items[idx]={...items[idx],materialName:e.target.value};setNewRequest({...newRequest,items});}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                  <input placeholder="Кол-во *" type="number" value={item.quantity} onChange={e=>{const items=[...newRequest.items];items[idx]={...items[idx],quantity:e.target.value};setNewRequest({...newRequest,items});}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                  <select value={item.unit} onChange={e=>{const items=[...newRequest.items];items[idx]={...items[idx],unit:e.target.value};setNewRequest({...newRequest,items});}} style={{...inp,marginBottom:0,fontSize:'12px'}}>{UNITS.map(u=><option key={u}>{u}</option>)}</select>
                  <button onClick={()=>setNewRequest({...newRequest,items:newRequest.items.filter((_,i)=>i!==idx)})} style={{...btnR,padding:'5px 8px'}}><X size={12}/></button>
                </div>))}
                <button onClick={()=>setNewRequest({...newRequest,items:[...newRequest.items,{materialName:'',quantity:'',unit:'шт'}]})} style={{...btnG,fontSize:'12px',marginBottom:'12px'}}><Plus size={13}/>Строка</button>
                <textarea placeholder="Примечания" value={newRequest.notes} onChange={e=>setNewRequest({...newRequest,notes:e.target.value})} style={{...inp,height:'60px',resize:'vertical'}}/>
                <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'8px'}}>Отправить поставщикам:</b>
                {suppliers.filter(s=>!newRequest.category||s.category===newRequest.category).map(s=>(<label key={s.id} style={{display:'flex',alignItems:'center',gap:'8px',padding:'8px',cursor:'pointer',borderRadius:'6px',marginBottom:'4px',backgroundColor:newRequest.selectedSuppliers.includes(s.id)?C.accentLight:'transparent'}}><input type="checkbox" checked={newRequest.selectedSuppliers.includes(s.id)} onChange={e=>setNewRequest({...newRequest,selectedSuppliers:e.target.checked?[...newRequest.selectedSuppliers,s.id]:newRequest.selectedSuppliers.filter(id=>id!==s.id)})} style={{accentColor:C.accent}}/><span style={{fontSize:'13px',color:C.text}}>{s.name}</span><span style={{fontSize:'11px',color:C.textSec}}>{s.category}</span></label>))}
                <div style={{display:'flex',gap:'8px',marginTop:'12px'}}><button onClick={saveRequest} style={btnO}><Check size={14}/>Отправить заявку</button><button onClick={()=>setShowForm(false)} style={btnG}><X size={14}/>Отмена</button></div>
              </div>)}
              {supplyRequests.map(req=>(<div key={req.id} style={{...card,padding:'14px',marginBottom:'8px'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
                  <div><b style={{color:C.text,fontSize:'13px'}}>{req.materialName}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{req.quantity+' '+req.unit+' · '+req.project+(req.category?' · '+req.category:'')}</p><p style={{color:C.textMuted,margin:'0',fontSize:'11px'}}>{req.date+' · '+req.createdBy}</p></div>
                  <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
                    <span style={badge(req.status==='Утверждено'?C.success:req.status==='Отменена'?C.danger:C.warning,req.status==='Утверждено'?C.successLight:req.status==='Отменена'?C.dangerLight:C.warningLight,req.status==='Утверждено'?C.successBorder:req.status==='Отменена'?C.dangerBorder:C.warningBorder)}>{req.status}</span>
                    {req.status==='Новая'&&(<><button onClick={()=>setShowOffers(showOffers===req.id?null:req.id)} style={{...btnB,padding:'4px 10px',fontSize:'11px'}}>КП</button><button onClick={()=>cancelRequest(req.id)} style={{...btnR,padding:'4px 10px',fontSize:'11px'}}>Отменить</button></>)}
                  </div>
                </div>
                {showOffers===req.id&&(<div style={{borderTop:'1.5px solid '+C.border,paddingTop:'12px',marginTop:'10px'}}>
                  <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'10px'}}>Добавить КП:</b>
                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:'8px',marginBottom:'10px'}}>
                    <select value={newOffer.supplierId} onChange={e=>setNewOffer({...newOffer,supplierId:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}><option value="">Поставщик</option>{suppliers.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select>
                    <input placeholder="Цена за ед. *" type="number" value={newOffer.pricePerUnit} onChange={e=>setNewOffer({...newOffer,pricePerUnit:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                    <input placeholder="Срок поставки (дней) *" type="number" value={newOffer.deliveryDays} onChange={e=>setNewOffer({...newOffer,deliveryDays:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                  </div>
                  <button onClick={()=>saveOffer(req.id)} style={{...btnO,fontSize:'12px',padding:'6px 14px',marginBottom:'12px'}}><Plus size={12}/>Добавить КП</button>
                  {supplierOffers.filter(o=>o.requestId===req.id).map(o=>{const sup=suppliers.find(s=>s.id===o.supplierId);return(<div key={o.id} style={{padding:'10px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center'}}><div><b style={{fontSize:'12px',color:C.text}}>{sup?sup.name:'Поставщик'}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{'Цена: '+o.pricePerUnit.toLocaleString()+' ₽/ед · Итого: '+o.totalPrice.toLocaleString()+' ₽ · '+o.deliveryDays+' дней'+(o.notes?' · '+o.notes:'')}</p></div>{o.status==='Ожидает'&&isLeadership()&&<button onClick={()=>approveOffer(o)} style={{...btnGr,padding:'4px 10px',fontSize:'11px'}}><Check size={11}/>Утвердить</button>}{o.status==='Утверждено'&&<span style={badge(C.success,C.successLight,C.successBorder)}>✅ Утверждено</span>}</div>);})}
                </div>)}
              </div>))}
              {supplyRequests.length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Заявок нет</p>}
            </div>)}

            {suppliersTab==='offers'&&(<div>
              <h3 style={{color:C.text,marginBottom:'15px',fontSize:'15px',fontWeight:'700'}}>Все коммерческие предложения</h3>
              {supplierOffers.map(o=>{const sup=suppliers.find(s=>s.id===o.supplierId);const req=supplyRequests.find(r=>r.id===o.requestId);return(<div key={o.id} style={{...card,padding:'14px',marginBottom:'8px'}}><div style={{display:'flex',justifyContent:'space-between'}}><div><b style={{fontSize:'13px',color:C.text}}>{req?req.materialName:'—'}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{(sup?sup.name:'')+'  · '+o.pricePerUnit.toLocaleString()+' ₽/ед · Итого: '+o.totalPrice.toLocaleString()+' ₽ · '+o.deliveryDays+' дней'}</p></div><span style={badge(o.status==='Утверждено'?C.success:C.warning,o.status==='Утверждено'?C.successLight:C.warningLight,o.status==='Утверждено'?C.successBorder:C.warningBorder)}>{o.status}</span></div></div>);})}
            </div>)}

            {suppliersTab==='history'&&(<div>
              <h3 style={{color:C.text,marginBottom:'15px',fontSize:'15px',fontWeight:'700'}}>История поставок</h3>
              {supplyHistory.map(d=>(<div key={d.id} style={{...card,padding:'14px',marginBottom:'8px'}}><div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}><div><b style={{fontSize:'13px',color:C.text}}>{d.materialName}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{d.quantity+' '+d.unit+' · '+d.project+' · '+d.date}</p><p style={{color:C.textSec,margin:'0',fontSize:'11px'}}>{'Поставщик: '+(suppliers.find(s=>s.id===d.supplierId)?.name||'—')}</p></div><div style={{display:'flex',gap:'6px',alignItems:'center'}}><b style={{color:C.success,fontSize:'13px'}}>{d.totalPrice.toLocaleString()+' ₽'}</b>{d.status==='Ожидает поставки'&&<button onClick={()=>confirmDelivery(d)} style={{...btnGr,padding:'4px 10px',fontSize:'11px'}}><Check size={11}/>Доставлено</button>}{d.status==='Доставлено'&&<span style={badge(C.success,C.successLight,C.successBorder)}>✅</span>}</div></div></div>))}
              {supplyHistory.length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Истории нет</p>}
            </div>)}
          </div>)}

          {activePage==='accounting'&&(<div>
            <div style={{display:'flex',gap:'8px',marginBottom:'20px',flexWrap:'wrap'}}>
              {['summary','contracts','acts','aosr','payments','documents','salary','expenses','supplierInv','audit'].map(tab=>(<button key={tab} onClick={()=>{setAccountingTab(tab);setShowForm(false);if(tab==='audit'){fetch(API+'/audit-log').then(r=>r.json()).then(d=>setAuditLog(Array.isArray(d)?d:[])).catch(()=>{});}}} style={{...accountingTab===tab?btnO:btnG,fontSize:'12px',padding:'7px 12px'}}>{{summary:'📊 Сводка',contracts:'🧾 Договоры',acts:'📄 Акты',aosr:'🔒 АОСР к оплате',payments:'💸 Платежи',documents:'🏗 По объектам',salary:'👥 Зарплата',expenses:'💼 Авансовые',supplierInv:'📥 Счета постав.',audit:'📜 Аудит'}[tab]}</button>))}
            </div>

            {accountingTab==='summary'&&(<div>
              <b style={{color:C.text,fontSize:'15px',fontWeight:'700',display:'block',marginBottom:'15px'}}>📊 Финансовая сводка по компании</b>
              {(()=>{
                const activeProj=projects.filter(pr=>pr.status==='В работе').length;
                const totalBudget=projects.reduce((s,pr)=>s+Number(pr.budget||0),0);
                const totalPayIn=(projectPayments||[]).reduce((s,p)=>s+Number(p.amount||0),0);
                const totalExpOut=(ownExpenses||[]).reduce((s,e)=>s+Number(e.amount||0),0);
                const totalAccount=(accountablePayments||[]).reduce((s,a)=>s+Number(a.amount||0),0);
                const aosrSigned=hiddenActs.filter(a=>a.status==='Подписан');
                const aosrPaid=hiddenActs.filter(a=>a.paidStatus==='Оплачен');
                const aosrToPay=aosrSigned.filter(a=>a.paidStatus!=='Оплачен');
                const toPaySum=aosrToPay.reduce((s,a)=>s+Number(a.total||0),0);
                const aosrPaidSum=aosrPaid.reduce((s,a)=>s+Number(a.paidAmount||a.total||0),0);
                const netProfit=totalPayIn-totalExpOut-totalAccount;
                const cards=[
                  {label:'Активных проектов',val:activeProj+' из '+projects.length,color:C.accent},
                  {label:'Общий бюджет',val:Math.round(totalBudget).toLocaleString('ru-RU')+' ₽',color:C.text},
                  {label:'Поступило от заказчиков',val:Math.round(totalPayIn).toLocaleString('ru-RU')+' ₽',color:C.success},
                  {label:'Свои расходы',val:Math.round(totalExpOut).toLocaleString('ru-RU')+' ₽',color:C.warning},
                  {label:'Подотчётные',val:Math.round(totalAccount).toLocaleString('ru-RU')+' ₽',color:C.warning},
                  {label:'Чистая прибыль',val:Math.round(netProfit).toLocaleString('ru-RU')+' ₽',color:netProfit>=0?C.success:C.danger},
                ];
                return(<div>
                  <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:'12px',marginBottom:'20px'}}>
                    {cards.map(c=>(<div key={c.label} style={{...card,padding:'16px'}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 6px'}}>{c.label}</p><b style={{color:c.color,fontSize:'18px'}}>{c.val}</b></div>))}
                  </div>
                  <div style={{...card,padding:'20px',backgroundColor:C.bg,border:'1.5px solid '+C.accentBorder}}>
                    <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>🔒 Связка АОСР → платежи (защита)</b>
                    <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(160px,1fr))',gap:'10px'}}>
                      <div><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Всего АОСР</p><b style={{color:C.text,fontSize:'15px'}}>{hiddenActs.length}</b></div>
                      <div><p style={{color:C.warning,fontSize:'11px',margin:'0 0 4px'}}>К оплате (подписан)</p><b style={{color:C.warning,fontSize:'15px'}}>{aosrToPay.length+' · '+Math.round(toPaySum).toLocaleString('ru-RU')+' ₽'}</b></div>
                      <div><p style={{color:C.success,fontSize:'11px',margin:'0 0 4px'}}>Оплачено</p><b style={{color:C.success,fontSize:'15px'}}>{aosrPaid.length+' · '+Math.round(aosrPaidSum).toLocaleString('ru-RU')+' ₽'}</b></div>
                    </div>
                    {aosrToPay.length>0&&<p style={{color:C.warning,fontSize:'12px',margin:'10px 0 0'}}>⚠️ {aosrToPay.length} подписанных АОСР ждут оплаты — перейди на вкладку «🔒 АОСР к оплате»</p>}
                  </div>
                </div>);
              })()}
            </div>)}

            {accountingTab==='aosr'&&(<div>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',flexWrap:'wrap',gap:'10px'}}>
                <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>🔒 АОСР к оплате</b>
                <span style={{fontSize:'11px',color:C.textMuted}}>Подписанные акты можно оплатить · оплаченные внизу</span>
              </div>
              {(()=>{
                const toPay=hiddenActs.filter(a=>a.status==='Подписан'&&a.paidStatus!=='Оплачен');
                const paid=hiddenActs.filter(a=>a.paidStatus==='Оплачен');
                const drafts=hiddenActs.filter(a=>a.status!=='Подписан');
                return(<div>
                  <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'10px',marginBottom:'14px'}}>
                    <div style={{...card,padding:'12px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}><p style={{color:C.warning,fontSize:'11px',margin:'0 0 4px'}}>К оплате</p><b style={{color:C.warning,fontSize:'16px'}}>{toPay.length}</b></div>
                    <div style={{...card,padding:'12px',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder}}><p style={{color:C.success,fontSize:'11px',margin:'0 0 4px'}}>Оплачено</p><b style={{color:C.success,fontSize:'16px'}}>{paid.length}</b></div>
                    <div style={{...card,padding:'12px',backgroundColor:C.bg}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Черновики (ждут подписей)</p><b style={{color:C.text,fontSize:'16px'}}>{drafts.length}</b></div>
                  </div>
                  {toPay.length===0&&paid.length===0&&<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>АОСР к оплате нет. Платить можно только подписанные акты — это защита от двойной оплаты и юридический повод требовать оплату с заказчика.</div>}
                  {toPay.length>0&&<div style={{marginBottom:'18px'}}>
                    <b style={{color:C.warning,fontSize:'13px',display:'block',marginBottom:'8px'}}>⏳ Ждут оплаты ({toPay.length}):</b>
                    {toPay.map(a=>(<div key={a.id} style={{...card,padding:'14px',marginBottom:'8px',borderLeft:'3px solid '+C.warning}}>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                        <div style={{flex:1,minWidth:'200px'}}>
                          <b style={{color:C.text,fontSize:'13px'}}>{a.actNumber+' · '+a.workName}</b>
                          <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{a.projectName+' · '+(a.brigade||'—')+' · '+(a.quantity||0)+' '+(a.unit||'')}</p>
                          <p style={{color:C.accent,margin:'4px 0 0',fontSize:'14px',fontWeight:'700'}}>{Math.round(Number(a.total||0)).toLocaleString('ru-RU')+' ₽'}</p>
                        </div>
                        <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
                          <button onClick={()=>setEditingAct(a)} style={{...btnB,padding:'5px 10px',fontSize:'11px'}}><Eye size={12}/>Открыть</button>
                          <button onClick={async()=>{
                            if(!window.confirm('Оплатить бригаде по АОСР '+a.actNumber+' сумму '+Math.round(Number(a.total||0)).toLocaleString('ru-RU')+' ₽?')) return;
                            const res=await fetch(API+'/hidden-works-acts/'+a.id+'/pay',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({amount:Number(a.total||0),paidBy:user.name,paidNote:'Оплата по АОСР '+a.actNumber,paidAt:new Date().toISOString().split('T')[0]})});
                            if(!res.ok){const e=await res.json().catch(()=>({}));alert('Ошибка: '+(e.detail||'не удалось'));return;}
                            await loadAll();
                            alert('Оплачено! Запись добавлена в платежи проекта.');
                          }} style={btnO}><DollarSign size={12}/>💰 Оплатить</button>
                        </div>
                      </div>
                    </div>))}
                  </div>}
                  {paid.length>0&&<div>
                    <b style={{color:C.success,fontSize:'13px',display:'block',marginBottom:'8px'}}>✅ Оплачено ({paid.length}):</b>
                    {paid.slice(0,20).map(a=>(<div key={a.id} style={{...card,padding:'10px 14px',marginBottom:'6px',borderLeft:'3px solid '+C.success,opacity:0.8}}>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}>
                        <div style={{flex:1,minWidth:'200px'}}>
                          <b style={{color:C.text,fontSize:'12px'}}>{a.actNumber+' · '+a.workName}</b>
                          <p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{a.projectName+' · '+a.paidAt+' · '+(a.paidBy||'—')}</p>
                        </div>
                        <b style={{color:C.success,fontSize:'13px'}}>{Math.round(Number(a.paidAmount||a.total||0)).toLocaleString('ru-RU')+' ₽'}</b>
                      </div>
                    </div>))}
                  </div>}
                </div>);
              })()}
            </div>)}

            {accountingTab==='payments'&&(<div>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>💸 Платежи</b>
                <span style={{fontSize:'11px',color:C.textMuted}}>Сводка по всем источникам</span>
              </div>
              {(()=>{
                const inPays=(projectPayments||[]).slice().sort((a,b)=>(b.date||'').localeCompare(a.date||''));
                const ownExps=(ownExpenses||[]).slice().sort((a,b)=>(b.date||'').localeCompare(a.date||''));
                const accPays=(accountablePayments||[]).slice().sort((a,b)=>(b.date||'').localeCompare(a.date||''));
                const inSum=inPays.reduce((s,p)=>s+Number(p.amount||0),0);
                const ownSum=ownExps.reduce((s,e)=>s+Number(e.amount||0),0);
                const accSum=accPays.reduce((s,a)=>s+Number(a.amount||0),0);
                return(<div>
                  <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'10px',marginBottom:'18px'}}>
                    <div style={{...card,padding:'14px',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder}}><p style={{color:C.success,fontSize:'11px',margin:'0 0 4px'}}>Поступило (от заказчиков)</p><b style={{color:C.success,fontSize:'16px'}}>{Math.round(inSum).toLocaleString('ru-RU')+' ₽'}</b><p style={{color:C.textMuted,fontSize:'10px',margin:'2px 0 0'}}>{inPays.length+' платежей'}</p></div>
                    <div style={{...card,padding:'14px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}><p style={{color:C.warning,fontSize:'11px',margin:'0 0 4px'}}>Свои расходы</p><b style={{color:C.warning,fontSize:'16px'}}>{Math.round(ownSum).toLocaleString('ru-RU')+' ₽'}</b><p style={{color:C.textMuted,fontSize:'10px',margin:'2px 0 0'}}>{ownExps.length+' операций'}</p></div>
                    <div style={{...card,padding:'14px',backgroundColor:C.dangerLight,border:'1.5px solid '+C.dangerBorder}}><p style={{color:C.danger,fontSize:'11px',margin:'0 0 4px'}}>Подотчётные</p><b style={{color:C.danger,fontSize:'16px'}}>{Math.round(accSum).toLocaleString('ru-RU')+' ₽'}</b><p style={{color:C.textMuted,fontSize:'10px',margin:'2px 0 0'}}>{accPays.length+' выдач'}</p></div>
                  </div>
                  {(()=>{const unx=(unexpectedWorksList||[]).filter(u=>u.status==='Утверждено'&&!u.paidStatus);const sum=unx.reduce((s,u)=>s+Number(u.total||0),0);if(unx.length===0) return null;return(<div style={{...card,padding:'14px',marginBottom:'14px',backgroundColor:'#fef3c7',border:'1.5px solid #fbbf24'}}>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'8px',flexWrap:'wrap',gap:'8px'}}>
                      <b style={{color:'#78350f',fontSize:'13px'}}>🆕 Непредвиденные к оплате</b>
                      <b style={{color:'#78350f',fontSize:'14px'}}>{Math.round(sum).toLocaleString('ru-RU')+' ₽'}</b>
                    </div>
                    {unx.slice(0,10).map(u=>(<div key={u.id} style={{padding:'8px 10px',backgroundColor:'rgba(255,255,255,0.6)',borderRadius:'6px',marginTop:'4px',display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px',flexWrap:'wrap'}}>
                      <div style={{flex:1,minWidth:'200px'}}>
                        <b style={{fontSize:'12px',color:'#78350f'}}>{u.description}</b>
                        <p style={{color:'#92400e',margin:'2px 0',fontSize:'11px'}}>{u.projectName+' · '+(u.quantity||0)+' '+u.unit+(u.approvedBy?' · согл. '+u.approvedBy:'')}</p>
                      </div>
                      <b style={{color:'#78350f',fontSize:'13px'}}>{Math.round(Number(u.total||0)).toLocaleString('ru-RU')+' ₽'}</b>
                      <button onClick={async()=>{if(!window.confirm('Отметить как оплачено?')) return;await fetch(API+'/unexpected-works/'+u.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Утверждено',price:u.price,total:u.total,approvedBy:u.approvedBy,approvedAt:u.approvedAt,paidStatus:'Оплачен'})});await fetch(API+'/project-payments',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({projectName:u.projectName,amount:u.total,note:'Оплата непредвиденной: '+u.description,date:new Date().toISOString().split('T')[0],paidBy:user.name})});await loadAll();}} style={{...btnO,padding:'4px 10px',fontSize:'11px'}}><DollarSign size={11}/>Оплатить</button>
                    </div>))}
                  </div>);})()}
                  <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'8px'}}>📅 Последние 15 платежей по проектам:</b>
                  {inPays.slice(0,15).map((p,i)=>(<div key={i} style={{...card,padding:'10px 14px',marginBottom:'6px'}}><div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}><div style={{flex:1,minWidth:'200px'}}><b style={{color:C.text,fontSize:'12px'}}>{p.projectName||'—'}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{(p.date||'')+(p.note?' · '+p.note:'')+(p.paidBy?' · '+p.paidBy:'')}</p></div><b style={{color:C.success,fontSize:'13px'}}>{Math.round(Number(p.amount||0)).toLocaleString('ru-RU')+' ₽'}</b></div></div>))}
                  {inPays.length===0&&<p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'20px'}}>Платежей нет</p>}
                </div>);
              })()}
            </div>)}

            {accountingTab==='contracts'&&(<div>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Договоры</b>
                {isFinanceRole()&&<button onClick={()=>setShowForm(!showForm)} style={btnO}><Plus size={14}/>Новый договор</button>}
              </div>
              {showForm&&(<div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                  <select value={newContract.masterId} onChange={e=>{const mp=masterProfiles.find(p=>p.userId===Number(e.target.value));setNewContract({...newContract,masterId:e.target.value,masterName:mp?mp.fullName:''});}} style={{...inp,marginBottom:0}}><option value="">Выберите мастера *</option>{masterProfiles.map(mp=><option key={mp.userId} value={mp.userId}>{mp.fullName}</option>)}</select>
                  <select value={newContract.contractType} onChange={e=>setNewContract({...newContract,contractType:e.target.value})} style={{...inp,marginBottom:0}}>{['ГПХ','ИП','Самозанятый'].map(t=><option key={t}>{t}</option>)}</select>
                  <input placeholder="Номер договора *" value={newContract.contractNumber} onChange={e=>setNewContract({...newContract,contractNumber:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <select value={newContract.project} onChange={e=>setNewContract({...newContract,project:e.target.value})} style={{...inp,marginBottom:0}}><option value="">Выберите объект *</option>{projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}</select>
                  <input type="date" placeholder="Начало" value={newContract.startDate} onChange={e=>setNewContract({...newContract,startDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input type="date" placeholder="Конец" value={newContract.endDate} onChange={e=>setNewContract({...newContract,endDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                </div>
                <div style={{display:'flex',gap:'8px',marginTop:'12px'}}><button onClick={createContract} style={btnO}><Check size={14}/>Создать</button><button onClick={()=>setShowForm(false)} style={btnG}><X size={14}/>Отмена</button></div>
              </div>)}
              {contracts.map(c=>{const profile=masterProfiles.find(p=>p.userId===c.masterId);return(<div key={c.id} style={{...card,padding:'14px',marginBottom:'8px'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                  <div><b style={{color:C.text,fontSize:'13px'}}>{'Договор № '+c.contractNumber+' · '+c.contractType}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{c.masterName+' · '+c.project}</p><p style={{color:C.textMuted,margin:'0',fontSize:'11px'}}>{c.startDate+' — '+c.endDate}</p></div>
                  <div style={{display:'flex',gap:'6px'}}>
                    {profile&&<button onClick={()=>showPreview(buildContractContent(profile,c),'Договор')} style={btnB}><Eye size={13}/>Просмотр</button>}
                    {pdConsents.find(pd=>pd.userId===c.masterId)&&<span style={badge(C.success,C.successLight,C.successBorder)}>ПД ✅</span>}
                    <button onClick={()=>deleteContract(c.id)} style={{...btnR,padding:'4px 8px'}}><Trash2 size={11}/></button>
                  </div>
                </div>
              </div>);})}
              {contracts.length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Договоров нет</p>}
            </div>)}

            {accountingTab==='acts'&&(<div>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Акты выполненных работ</b>
                {isFinanceRole()&&<button onClick={()=>setShowForm(!showForm)} style={btnO}><Plus size={14}/>Создать акт</button>}
              </div>
              {showForm&&(<div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                  <select value={newAct.masterId} onChange={e=>{const mp=masterProfiles.find(p=>p.userId===Number(e.target.value));setNewAct({...newAct,masterId:e.target.value,masterName:mp?mp.fullName:''});}} style={{...inp,marginBottom:0}}><option value="">Выберите мастера *</option>{masterProfiles.map(mp=><option key={mp.userId} value={mp.userId}>{mp.fullName}</option>)}</select>
                  <select value={newAct.project} onChange={e=>setNewAct({...newAct,project:e.target.value})} style={{...inp,marginBottom:0}}><option value="">Объект *</option>{projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}</select>
                  <input type="date" placeholder="Период с *" value={newAct.periodStart} onChange={e=>setNewAct({...newAct,periodStart:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input type="date" placeholder="Период по *" value={newAct.periodEnd} onChange={e=>setNewAct({...newAct,periodEnd:e.target.value})} style={{...inp,marginBottom:0}}/>
                </div>
                <div style={{display:'flex',gap:'8px',marginTop:'12px'}}><button onClick={createInterimAct} style={btnO}><Check size={14}/>Создать</button><button onClick={()=>setShowForm(false)} style={btnG}><X size={14}/>Отмена</button></div>
              </div>)}
              {interimActs.map(act=>{const paidAmt=act.paidAmount||0;const totalAmt=act.totalAmount||0;const remaining=totalAmt-paidAmt;return(<div key={act.id} style={{...card,padding:'14px',marginBottom:'8px',borderLeft:'3px solid '+(act.status==='Оплачен'?C.success:act.status==='Частично оплачен'?C.warning:C.textSec)}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
                  <div><b style={{color:C.text,fontSize:'13px'}}>{'Акт №'+act.id+' · '+act.masterName}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{act.project+' · '+act.periodStart+' — '+act.periodEnd}</p><div style={{display:'flex',gap:'12px',marginTop:'4px'}}><span style={{fontSize:'12px',color:C.text}}>{'Начислено: '+totalAmt.toLocaleString()+' ₽'}</span><span style={{fontSize:'12px',color:C.success}}>{'Оплачено: '+paidAmt.toLocaleString()+' ₽'}</span>{remaining>0&&<span style={{fontSize:'12px',color:C.danger,fontWeight:'600'}}>{'Остаток: '+remaining.toLocaleString()+' ₽'}</span>}</div></div>
                  <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
                    <span style={badge(act.status==='Оплачен'?C.success:act.status==='Частично оплачен'?C.warning:C.textSec,act.status==='Оплачен'?C.successLight:act.status==='Частично оплачен'?C.warningLight:C.bgGray,act.status==='Оплачен'?C.successBorder:act.status==='Частично оплачен'?C.warningBorder:C.border)}>{act.status||'Не оплачен'}</span>
                    <button onClick={()=>showPreview(buildActContent(act),'Акт')} style={btnB}><Eye size={13}/></button>
                    {isFinanceRole()&&<button onClick={()=>setShowPayActModal(act)} style={btnO}><DollarSign size={13}/>Оплата</button>}
                    <button onClick={()=>deleteInterimAct(act.id)} style={{...btnR,padding:'4px 8px'}}><Trash2 size={11}/></button>
                  </div>
                </div>
              </div>);})}
              {interimActs.length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Актов нет</p>}
            </div>)}

            {accountingTab==='documents'&&(<div>
              <div style={{display:'flex',gap:'8px',marginBottom:'15px',flexWrap:'wrap'}}>
                {projects.map(p=>(<button key={p.id} onClick={()=>setAccountingDocProject(p.name)} style={{...accountingDocProject===p.name?btnO:btnG,fontSize:'12px',padding:'6px 12px'}}>{p.name}</button>))}
              </div>
              {accountingDocProject&&(()=>{const proj=projects.find(pr=>pr.name===accountingDocProject);if(!proj) return null;const pd=projectPlanDone(proj);const budget=Number(proj.budget||0);const ownExp=(ownExpenses||[]).filter(e=>e.projectName===accountingDocProject).reduce((s,e)=>s+Number(e.amount||0),0);const accExp=(accountablePayments||[]).filter(a=>a.projectName===accountingDocProject).reduce((s,a)=>s+Number(a.amount||0),0);const aosrPaid=hiddenActs.filter(a=>a.projectName===accountingDocProject&&a.paidStatus==='Оплачен').reduce((s,a)=>s+Number(a.paidAmount||a.total||0),0);const factCost=ownExp+accExp+aosrPaid;const margin=pd.done-factCost;return(<div>
                <div style={{display:'flex',gap:'8px',marginBottom:'15px',flexWrap:'wrap'}}>
                  {['Паспорт','КС-2','КС-3','ЖПР','М-29','АОСК','КС-11','КС-14','ИГД','📦 Пакет','📋 НДС'].map(doc=>(<button key={doc} onClick={()=>{const p=proj;if(doc==='Паспорт') showPreview(buildPassportContent(p),'Паспорт объекта');if(doc==='КС-2') showKS2(p);if(doc==='КС-3') showPreview(buildKS3Content(p),'КС-3');if(doc==='ЖПР') showPreview(buildJPRContent(p.name),'ЖПР');if(doc==='М-29'){const today=new Date();const monthAgo=new Date(today.getTime()-30*24*3600*1000);showPreview(buildM29Content(p.name,monthAgo.toISOString().split('T')[0],today.toISOString().split('T')[0]),'М-29 — '+p.name);}if(doc==='АОСК') showPreview(buildAOSKContent(p.name),'АОСК — '+p.name);if(doc==='КС-11') showPreview(buildKS11Content(p),'КС-11 — '+p.name);if(doc==='КС-14') showPreview(buildKS14Content(p),'КС-14 — '+p.name);if(doc==='ИГД') showPreview(buildIGDContent(p.name),'ИГД — '+p.name);if(doc==='📦 Пакет') showPreview(buildExecPackageContent(p),'Пакет исполнительной — '+p.name);if(doc==='📋 НДС'){const today=new Date();const qStart=new Date(today.getFullYear(),Math.floor(today.getMonth()/3)*3,1);showPreview(buildVATBookContent(qStart.toISOString().split('T')[0],today.toISOString().split('T')[0]),'Книга НДС — текущий квартал');}}} style={{...btnB,fontSize:'12px',padding:'7px 14px'}}><FileText size={13}/>{doc}</button>))}
                </div>
                <div style={{...card,padding:'14px',marginBottom:'14px',backgroundColor:C.bg,border:'1.5px solid '+C.border}}>
                  <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'10px'}}>💰 Себестоимость объекта (план vs факт)</b>
                  <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(140px,1fr))',gap:'10px'}}>
                    <div><p style={{color:C.textSec,fontSize:'10px',margin:'0 0 4px'}}>Бюджет (договор)</p><b style={{color:C.text,fontSize:'14px'}}>{Math.round(budget).toLocaleString('ru-RU')+' ₽'}</b></div>
                    <div><p style={{color:C.textSec,fontSize:'10px',margin:'0 0 4px'}}>Выполнено по смете</p><b style={{color:C.accent,fontSize:'14px'}}>{Math.round(pd.done).toLocaleString('ru-RU')+' ₽'}</b></div>
                    <div><p style={{color:C.textSec,fontSize:'10px',margin:'0 0 4px'}}>Факт расходов</p><b style={{color:C.warning,fontSize:'14px'}}>{Math.round(factCost).toLocaleString('ru-RU')+' ₽'}</b></div>
                    <div><p style={{color:C.textSec,fontSize:'10px',margin:'0 0 4px'}}>Маржа</p><b style={{color:margin>=0?C.success:C.danger,fontSize:'14px'}}>{Math.round(margin).toLocaleString('ru-RU')+' ₽'}</b></div>
                  </div>
                  <p style={{color:C.textMuted,fontSize:'10px',margin:'8px 0 0',lineHeight:1.4}}>Факт = свои расходы ({Math.round(ownExp).toLocaleString('ru-RU')+' ₽'}) + подотчётные ({Math.round(accExp).toLocaleString('ru-RU')+' ₽'}) + оплачено по АОСР ({Math.round(aosrPaid).toLocaleString('ru-RU')+' ₽'})</p>
                </div>
                <div>
                  <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'10px'}}>Акты по проекту:</b>
                  {interimActs.filter(a=>a.project===accountingDocProject).map(act=>(<div key={act.id} style={{...card,padding:'12px',marginBottom:'8px',display:'flex',justifyContent:'space-between',alignItems:'center'}}><div><b style={{fontSize:'13px',color:C.text}}>{'Акт №'+act.id+' · '+act.masterName}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{(act.totalAmount||0).toLocaleString()+' ₽ · '+act.periodStart+' — '+act.periodEnd}</p></div><button onClick={()=>showPreview(buildActContent(act),'Акт')} style={btnB}><Eye size={13}/></button></div>))}
                </div>
              </div>);})()}
              {!accountingDocProject&&<p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Выберите проект</p>}
            </div>)}

            {accountingTab==='salary'&&(<div>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',flexWrap:'wrap',gap:'8px'}}>
                <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>👥 Расчёт зарплаты — текущий месяц</b>
                <span style={{fontSize:'11px',color:C.textMuted}}>Оклад из staff.salary + сдельные из piecework за месяц</span>
              </div>
              {(()=>{const monthStart=new Date(); monthStart.setDate(1); const monthStartStr=monthStart.toISOString().split('T')[0];
                const today=new Date().toISOString().split('T')[0];
                const rows=staff.filter(st=>st.status!=='Уволен'&&st.status!=='Архив').map(st=>{
                  const pw=(piecework||[]).filter(p=>Number(p.staffId)===st.id&&p.date&&p.date>=monthStartStr&&p.date<=today);
                  const pwSum=pw.reduce((s,p)=>s+Number(p.total||0),0);
                  const salary=Number(st.salary||0);
                  const total=(st.payType==='Сдельная'?pwSum:(st.payType==='Оклад'?salary:salary+pwSum));
                  return {id:st.id,name:st.name||(st.lastName||'')+' '+(st.firstName||''),role:st.role||'—',payType:st.payType||'—',salary,pwSum,total};
                });
                const grandTotal=rows.reduce((s,r)=>s+r.total,0);
                return(<div>
                  <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(150px,1fr))',gap:'10px',marginBottom:'14px'}}>
                    <div style={{...card,padding:'12px',backgroundColor:C.bg}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Сотрудников</p><b style={{color:C.text,fontSize:'16px'}}>{rows.length}</b></div>
                    <div style={{...card,padding:'12px',backgroundColor:C.accentLight}}><p style={{color:C.accent,fontSize:'11px',margin:'0 0 4px'}}>К выплате за месяц</p><b style={{color:C.accent,fontSize:'16px'}}>{Math.round(grandTotal).toLocaleString('ru-RU')+' ₽'}</b></div>
                  </div>
                  <div style={{...card,padding:0,overflow:'auto'}}>
                    <table style={tbl}><thead><tr><th style={tblH}>ФИО</th><th style={tblH}>Должность</th><th style={tblH}>Тип оплаты</th><th style={tblH}>Оклад</th><th style={tblH}>Сдельные за месяц</th><th style={tblH}>К выплате</th></tr></thead><tbody>
                      {rows.map(r=>(<tr key={r.id}><td style={tblC}>{r.name}</td><td style={tblC}>{r.role}</td><td style={tblC}>{r.payType}</td><td style={tblC}>{r.salary?r.salary.toLocaleString('ru-RU')+' ₽':'—'}</td><td style={tblC}>{r.pwSum>0?Math.round(r.pwSum).toLocaleString('ru-RU')+' ₽':'—'}</td><td style={{...tblC,fontWeight:'700',color:C.accent}}>{Math.round(r.total).toLocaleString('ru-RU')+' ₽'}</td></tr>))}
                      {rows.length===0&&<tr><td colSpan={6} style={{...tblC,textAlign:'center',color:C.textMuted}}>Активных сотрудников нет</td></tr>}
                    </tbody></table>
                  </div>
                  <p style={{color:C.textMuted,fontSize:'11px',marginTop:'8px',lineHeight:1.4}}>📋 Тип оплаты «Оклад» → берётся только staff.salary. «Сдельная» → только сумма piecework за месяц. «Смешанная» → оба. Период считается от 1-го числа текущего месяца.</p>
                </div>);
              })()}
            </div>)}

            {accountingTab==='expenses'&&(<div>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',flexWrap:'wrap',gap:'8px'}}>
                <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>💼 Авансовые отчёты и командировочные</b>
                <button onClick={()=>setNewExpenseReport({reportType:'Авансовый отчёт',employeeName:'',projectName:'',purpose:'',issuedAmount:'',spentAmount:'',balance:'',dateFrom:'',dateTo:''})} style={btnO}><Plus size={14}/>Новый отчёт</button>
              </div>
              {newExpenseReport&&(<div style={{...card,padding:'16px',marginBottom:'14px',backgroundColor:C.bg}}>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'8px'}}>
                  <select value={newExpenseReport.reportType} onChange={e=>setNewExpenseReport({...newExpenseReport,reportType:e.target.value})} style={{...inp,marginBottom:0}}>{['Авансовый отчёт','Командировочные','Мелкий нал','Бензин/такси','Закупка материалов'].map(t=><option key={t}>{t}</option>)}</select>
                  <select value={newExpenseReport.employeeName} onChange={e=>setNewExpenseReport({...newExpenseReport,employeeName:e.target.value})} style={{...inp,marginBottom:0}}><option value=''>Кому выдано *</option>{staff.map(st=><option key={st.id} value={st.name}>{st.name}</option>)}</select>
                  <select value={newExpenseReport.projectName} onChange={e=>setNewExpenseReport({...newExpenseReport,projectName:e.target.value})} style={{...inp,marginBottom:0}}><option value=''>Объект (если по проекту)</option>{projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}</select>
                  <input placeholder='Назначение *' value={newExpenseReport.purpose} onChange={e=>setNewExpenseReport({...newExpenseReport,purpose:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input placeholder='Выдано (₽) *' type='number' value={newExpenseReport.issuedAmount} onChange={e=>setNewExpenseReport({...newExpenseReport,issuedAmount:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input placeholder='Потрачено (₽)' type='number' value={newExpenseReport.spentAmount} onChange={e=>setNewExpenseReport({...newExpenseReport,spentAmount:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input type='date' value={newExpenseReport.dateFrom} onChange={e=>setNewExpenseReport({...newExpenseReport,dateFrom:e.target.value})} title='С' style={{...inp,marginBottom:0}}/>
                  <input type='date' value={newExpenseReport.dateTo} onChange={e=>setNewExpenseReport({...newExpenseReport,dateTo:e.target.value})} title='По' style={{...inp,marginBottom:0}}/>
                </div>
                <div style={{display:'flex',gap:'8px'}}>
                  <button onClick={async()=>{
                    if(!newExpenseReport.employeeName||!newExpenseReport.purpose||!newExpenseReport.issuedAmount){alert('Заполните: кому, назначение, выдано');return;}
                    const issued=Number(newExpenseReport.issuedAmount)||0;const spent=Number(newExpenseReport.spentAmount||0);
                    await fetch(API+'/expense-reports',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newExpenseReport,issuedAmount:issued,spentAmount:spent,totalAmount:spent||issued,balance:issued-spent,status:'На утверждении'})});
                    await loadAll(); setNewExpenseReport(null);
                  }} style={btnO}><Check size={14}/>Сохранить</button>
                  <button onClick={()=>setNewExpenseReport(null)} style={btnG}>Отмена</button>
                </div>
              </div>)}
              {expenseReports.length===0?<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}><p>Отчётов нет</p><p style={{fontSize:'11px'}}>Сотрудник съездил в командировку или потратил мелкий нал → добавьте отчёт для бухгалтерии.</p></div>:(<div>
                {expenseReports.map(r=>(<div key={r.id} style={{...card,padding:'14px',marginBottom:'8px',borderLeft:'3px solid '+(r.status==='Утверждён'?C.success:r.status==='Отклонён'?C.danger:C.warning)}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                    <div style={{flex:1,minWidth:'200px'}}>
                      <b style={{color:C.text,fontSize:'13px'}}>{r.reportType+' · '+r.employeeName}</b>
                      <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{(r.projectName?r.projectName+' · ':'')+r.purpose}</p>
                      <p style={{color:C.textMuted,margin:0,fontSize:'11px'}}>Выдано: {Math.round(r.issuedAmount).toLocaleString('ru-RU')+' ₽'} · Потрачено: {Math.round(r.spentAmount||0).toLocaleString('ru-RU')+' ₽'} · Остаток: <b style={{color:Math.round(r.balance)>0?C.success:C.danger}}>{Math.round(r.balance).toLocaleString('ru-RU')+' ₽'}</b></p>
                    </div>
                    <div style={{display:'flex',gap:'4px'}}>
                      <span style={badge(r.status==='Утверждён'?C.success:r.status==='Отклонён'?C.danger:C.warning,r.status==='Утверждён'?C.successLight:r.status==='Отклонён'?C.dangerLight:C.warningLight,r.status==='Утверждён'?C.successBorder:r.status==='Отклонён'?C.dangerBorder:C.warningBorder)}>{r.status}</span>
                      {r.status==='На утверждении'&&<><button onClick={async()=>{await fetch(API+'/expense-reports/'+r.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Утверждён',approvedBy:user.name,approvedAt:new Date().toISOString().split('T')[0]})});await loadAll();}} style={{...btnGr,padding:'4px 8px',fontSize:'11px'}}>✅</button><button onClick={async()=>{await fetch(API+'/expense-reports/'+r.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Отклонён',approvedBy:user.name,approvedAt:new Date().toISOString().split('T')[0]})});await loadAll();}} style={{...btnR,padding:'4px 8px',fontSize:'11px'}}>✕</button></>}
                      <button onClick={async()=>{if(!window.confirm('Удалить?')) return;await fetch(API+'/expense-reports/'+r.id,{method:'DELETE'});await loadAll();}} style={{...btnR,padding:'4px 8px'}}><Trash2 size={11}/></button>
                    </div>
                  </div>
                </div>))}
              </div>)}
            </div>)}

            {accountingTab==='supplierInv'&&(<div>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',flexWrap:'wrap',gap:'8px'}}>
                <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>📥 Входящие счета от поставщиков</b>
                <button onClick={()=>setNewSupplierInvoice({supplierName:'',projectName:'',invoiceNumber:'',invoiceDate:'',amount:'',vatAmount:'',description:''})} style={btnO}><Plus size={14}/>Новый счёт</button>
              </div>
              {newSupplierInvoice&&(<div style={{...card,padding:'16px',marginBottom:'14px',backgroundColor:C.bg}}>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'8px'}}>
                  <select value={newSupplierInvoice.supplierName} onChange={e=>{const sup=suppliers.find(s=>s.name===e.target.value);setNewSupplierInvoice({...newSupplierInvoice,supplierName:e.target.value,supplierId:sup?sup.id:null});}} style={{...inp,marginBottom:0}}><option value=''>Поставщик *</option>{(suppliers||[]).map(s=><option key={s.id} value={s.name}>{s.name}</option>)}</select>
                  <select value={newSupplierInvoice.projectName} onChange={e=>setNewSupplierInvoice({...newSupplierInvoice,projectName:e.target.value})} style={{...inp,marginBottom:0}}><option value=''>Объект (если по проекту)</option>{projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}</select>
                  <input placeholder='№ счёта *' value={newSupplierInvoice.invoiceNumber} onChange={e=>setNewSupplierInvoice({...newSupplierInvoice,invoiceNumber:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input type='date' value={newSupplierInvoice.invoiceDate} onChange={e=>setNewSupplierInvoice({...newSupplierInvoice,invoiceDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input placeholder='Сумма с НДС (₽) *' type='number' value={newSupplierInvoice.amount} onChange={e=>setNewSupplierInvoice({...newSupplierInvoice,amount:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input placeholder='В т.ч. НДС (₽)' type='number' value={newSupplierInvoice.vatAmount} onChange={e=>setNewSupplierInvoice({...newSupplierInvoice,vatAmount:e.target.value})} style={{...inp,marginBottom:0}}/>
                </div>
                <textarea placeholder='Описание (за что счёт)' value={newSupplierInvoice.description} onChange={e=>setNewSupplierInvoice({...newSupplierInvoice,description:e.target.value})} style={{...inp,minHeight:'50px',marginBottom:'8px'}}/>
                <div style={{display:'flex',gap:'8px'}}>
                  <button onClick={async()=>{
                    if(!newSupplierInvoice.supplierName||!newSupplierInvoice.invoiceNumber||!newSupplierInvoice.amount){alert('Заполните: поставщик, № счёта, сумма');return;}
                    await fetch(API+'/supplier-invoices',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newSupplierInvoice,amount:Number(newSupplierInvoice.amount)||0,vatAmount:Number(newSupplierInvoice.vatAmount||0),status:'На утверждении'})});
                    await loadAll(); setNewSupplierInvoice(null);
                  }} style={btnO}><Check size={14}/>Сохранить</button>
                  <button onClick={()=>setNewSupplierInvoice(null)} style={btnG}>Отмена</button>
                </div>
              </div>)}
              {(()=>{const pending=supplierInvoices.filter(i=>i.status==='На утверждении');const approved=supplierInvoices.filter(i=>i.status==='Утверждён');const paid=supplierInvoices.filter(i=>i.status==='Оплачен');const totalP=pending.reduce((s,i)=>s+Number(i.amount||0),0);return(<div>
                <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(150px,1fr))',gap:'10px',marginBottom:'14px'}}>
                  <div style={{...card,padding:'12px',backgroundColor:C.warningLight}}><p style={{color:C.warning,fontSize:'11px',margin:'0 0 4px'}}>На утверждении</p><b style={{color:C.warning,fontSize:'15px'}}>{pending.length+' · '+Math.round(totalP).toLocaleString('ru-RU')+' ₽'}</b></div>
                  <div style={{...card,padding:'12px',backgroundColor:C.accentLight}}><p style={{color:C.accent,fontSize:'11px',margin:'0 0 4px'}}>Утверждены (к оплате)</p><b style={{color:C.accent,fontSize:'15px'}}>{approved.length}</b></div>
                  <div style={{...card,padding:'12px',backgroundColor:C.successLight}}><p style={{color:C.success,fontSize:'11px',margin:'0 0 4px'}}>Оплачены</p><b style={{color:C.success,fontSize:'15px'}}>{paid.length}</b></div>
                </div>
                {supplierInvoices.length===0?<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Счетов нет. Поставщик прислал счёт → загрузи сюда → отметишь «Утверждён» → снабженец увидит «можно закупать»</div>:supplierInvoices.map(inv=>(<div key={inv.id} style={{...card,padding:'14px',marginBottom:'8px',borderLeft:'3px solid '+(inv.status==='Оплачен'?C.success:inv.status==='Утверждён'?C.accent:C.warning)}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                    <div style={{flex:1,minWidth:'200px'}}>
                      <b style={{color:C.text,fontSize:'13px'}}>{inv.supplierName+' · № '+inv.invoiceNumber}</b>
                      <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{(inv.projectName?inv.projectName+' · ':'')+(inv.invoiceDate||'')+(inv.description?' · '+inv.description:'')}</p>
                      <p style={{color:C.accent,margin:0,fontSize:'13px',fontWeight:'700'}}>{Math.round(Number(inv.amount||0)).toLocaleString('ru-RU')+' ₽'+(inv.vatAmount?' (НДС '+Math.round(Number(inv.vatAmount)).toLocaleString('ru-RU')+' ₽)':'')}</p>
                    </div>
                    <div style={{display:'flex',gap:'4px',alignItems:'center'}}>
                      <span style={badge(inv.status==='Оплачен'?C.success:inv.status==='Утверждён'?C.accent:C.warning,inv.status==='Оплачен'?C.successLight:inv.status==='Утверждён'?C.accentLight:C.warningLight,inv.status==='Оплачен'?C.successBorder:inv.status==='Утверждён'?C.accentBorder:C.warningBorder)}>{inv.status}</span>
                      {inv.status==='На утверждении'&&<button onClick={async()=>{await fetch(API+'/supplier-invoices/'+inv.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Утверждён',approvedBy:user.name,approvedAt:new Date().toISOString().split('T')[0]})});await loadAll();alert('Утверждено. Уведомление снабженцу: можно закупать.');}} style={{...btnGr,padding:'4px 8px',fontSize:'11px'}}>✅ Утвердить</button>}
                      {inv.status==='Утверждён'&&<button onClick={async()=>{if(!window.confirm('Отметить как оплачено '+Math.round(Number(inv.amount||0)).toLocaleString('ru-RU')+' ₽?')) return;await fetch(API+'/supplier-invoices/'+inv.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Оплачен',paidBy:user.name,paidAt:new Date().toISOString().split('T')[0],paidNote:'Оплата счёта №'+inv.invoiceNumber})});if(inv.projectName){await fetch(API+'/project-payments',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({projectName:inv.projectName,amount:inv.amount,note:'Оплата счёта '+inv.supplierName+' №'+inv.invoiceNumber,date:new Date().toISOString().split('T')[0],paidBy:user.name})});}await loadAll();}} style={{...btnO,padding:'4px 8px',fontSize:'11px'}}>💰 Оплатить</button>}
                      <button onClick={async()=>{if(!window.confirm('Удалить?')) return;await fetch(API+'/supplier-invoices/'+inv.id,{method:'DELETE'});await loadAll();}} style={{...btnR,padding:'4px 8px'}}><Trash2 size={11}/></button>
                    </div>
                  </div>
                </div>))}
              </div>);})()}
            </div>)}

            {accountingTab==='audit'&&(<div>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',flexWrap:'wrap',gap:'10px'}}>
                <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>📜 Журнал действий пользователей (Audit log)</b>
                <button onClick={()=>fetch(API+'/audit-log').then(r=>r.json()).then(d=>setAuditLog(Array.isArray(d)?d:[]))} style={{...btnB,fontSize:'12px',padding:'7px 12px'}}>🔄 Обновить</button>
              </div>
              {auditLog.length===0?<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}><p>Записей нет</p><p style={{fontSize:'11px'}}>Записи появляются по мере действий пользователей. Интеграция с endpoints — в Ф6.1.</p></div>:(<div style={{...card,padding:0,overflow:'auto'}}>
                <table style={tbl}><thead><tr>
                  <th style={tblH}>Время</th>
                  <th style={tblH}>Пользователь</th>
                  <th style={tblH}>Действие</th>
                  <th style={tblH}>Объект изменения</th>
                  <th style={tblH}>Проект</th>
                  <th style={tblH}>Описание</th>
                </tr></thead><tbody>
                  {auditLog.slice(0,100).map(a=>(<tr key={a.id}>
                    <td style={tblC}>{a.createdAt||'—'}</td>
                    <td style={tblC}>{(a.userName||'—')+(a.userRole?' ('+a.userRole+')':'')}</td>
                    <td style={tblC}><span style={{padding:'2px 8px',borderRadius:'10px',fontSize:'11px',fontWeight:'600',backgroundColor:C.bg,color:C.textSec}}>{a.action||'—'}</span></td>
                    <td style={tblC}>{(a.entityType||'')+(a.entityId?' №'+a.entityId:'')}</td>
                    <td style={tblC}>{a.projectName||'—'}</td>
                    <td style={{...tblC,maxWidth:'300px',whiteSpace:'normal'}}>{a.description||''}</td>
                  </tr>))}
                </tbody></table>
              </div>)}
            </div>)}
          </div>)}
          {activePage==='personnel'&&(<div>
            <div style={{display:'flex',gap:'8px',marginBottom:'20px',flexWrap:'wrap'}}>
              {['staff','timesheet','piecework'].map(tab=>(<button key={tab} onClick={()=>{setPersonnelTab(tab);setShowForm(false);}} style={{...personnelTab===tab?btnO:btnG,fontSize:'12px',padding:'7px 14px'}}>{{staff:'👥 Сотрудники',timesheet:'📅 Табель',piecework:'💵 Сдельные'}[tab]}</button>))}
            </div>

            {personnelTab==='masters'&&(<div>
              <h3 style={{color:C.text,marginBottom:'15px',fontSize:'15px',fontWeight:'700'}}>Мастера и субподрядчики</h3>
              {ROLE_GROUPS.filter(g=>['рабочие','субподрядчики'].includes(g.key)).map(group=>{
                const groupUsers=users.filter(u=>group.roles.includes(u.role));
                if(groupUsers.length===0) return null;
                return(<div key={group.key} style={{marginBottom:'20px'}}>
                  <div style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'10px',padding:'8px 12px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border}}><div style={{width:'10px',height:'10px',borderRadius:'50%',backgroundColor:group.color}}/><b style={{color:C.text,fontSize:'13px'}}>{group.label}</b><span style={{color:C.textSec,fontSize:'12px'}}>{'('+groupUsers.length+')'}</span></div>
                  {groupUsers.map(u=>{
                    const profile=masterProfiles.find(p=>p.userId===u.id);
                    const consent=pdConsents.find(c=>c.userId===u.id);
                    const contract=contracts.find(c=>c.masterId===u.id);
                    const myActs=interimActs.filter(a=>a.masterId===u.id);
                    const totalEarned=myActs.reduce((s,a)=>s+(a.totalAmount||0),0);
                    const totalPaid=myActs.reduce((s,a)=>s+(a.paidAmount||0),0);
                    const rating=masterRatings[u.id]||0;
                    const isOpen=expandedMaster===u.id;
                    return(<div key={u.id} style={{...card,marginBottom:'10px',marginLeft:'12px'}}>
                      <div style={{padding:'14px',cursor:'pointer',display:'flex',justifyContent:'space-between',alignItems:'center'}} onClick={()=>setExpandedMaster(isOpen?null:u.id)}>
                        <div style={{display:'flex',alignItems:'center',gap:'12px'}}>
                          <div style={{width:'42px',height:'42px',borderRadius:'12px',backgroundColor:roleColor(u.role),display:'flex',alignItems:'center',justifyContent:'center',fontSize:'16px',color:'white',fontWeight:'800',flexShrink:0}}>{u.name.charAt(0)}</div>
                          <div>
                            <b style={{color:C.text,fontSize:'14px'}}>{u.name}</b>
                            <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{ROLE_LABELS[u.role]+(profile?' · '+profile.contractType+(profile.specialization?' · '+profile.specialization:''):'')}</p>
                            <div style={{display:'flex',gap:'4px',marginTop:'3px'}}>{[1,2,3,4,5].map(s=>(<span key={s} style={{color:s<=rating?'#f59e0b':'#d1d5db',fontSize:'16px',cursor:'pointer'}} onClick={e=>{e.stopPropagation();ratemaster(u.id,s);}}>{s<=rating?'★':'☆'}</span>))}</div>
                          </div>
                        </div>
                        <div style={{display:'flex',alignItems:'center',gap:'10px'}}>
                          <div style={{textAlign:'right'}}>
                            <p style={{color:C.success,margin:0,fontSize:'13px',fontWeight:'600'}}>{totalEarned.toLocaleString()+' ₽'}</p>
                            {totalEarned-totalPaid>0&&<p style={{color:C.danger,margin:'2px 0 0',fontSize:'11px'}}>{'Долг: '+(totalEarned-totalPaid).toLocaleString()+' ₽'}</p>}
                          </div>
                          {isOpen?<ChevronUp size={16} color={C.textMuted}/>:<ChevronDown size={16} color={C.textMuted}/>}
                        </div>
                      </div>
                      {isOpen&&(<div style={{borderTop:'1.5px solid '+C.border,padding:'14px'}}>
                        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px',marginBottom:'15px'}}>
                          <div style={{padding:'10px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border}}>
                            <p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Профиль</p>
                            {profile?(<div><p style={{margin:'2px 0',fontSize:'12px',color:C.text}}>{'ФИО: '+profile.fullName}</p><p style={{margin:'2px 0',fontSize:'12px',color:C.text}}>{'ИНН: '+profile.inn}</p><p style={{margin:'2px 0',fontSize:'12px',color:C.text}}>{'Банк: '+profile.bankName}</p><p style={{margin:'2px 0',fontSize:'12px',color:C.text}}>{'Р/с: '+profile.bankAccount}</p></div>):<p style={{color:C.textMuted,fontSize:'12px'}}>Не заполнен</p>}
                          </div>
                          <div style={{padding:'10px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border}}>
                            <p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Документы</p>
                            <div style={{display:'flex',flexDirection:'column',gap:'6px'}}>
                              {consent?(<div style={{display:'flex',gap:'6px',alignItems:'center'}}><CheckCircle size={14} color={C.success}/><span style={{fontSize:'12px',color:C.success}}>ПД подписано</span>{consent.scanUrl&&<img src={consent.scanUrl} alt="" onClick={()=>setShowPhotoModal(consent.scanUrl)} style={{width:'28px',height:'28px',borderRadius:'4px',objectFit:'cover',cursor:'pointer'}}/>}</div>):(<span style={{fontSize:'12px',color:C.warning}}>⚠️ ПД не подписано</span>)}
                              {contract?(<div style={{display:'flex',gap:'6px',alignItems:'center'}}><CheckCircle size={14} color={C.success}/><span style={{fontSize:'12px',color:C.success}}>{'Договор № '+contract.contractNumber}</span></div>):(<span style={{fontSize:'12px',color:C.warning}}>⚠️ Договора нет</span>)}
                            </div>
                          </div>
                        </div>
                        <div style={{display:'flex',gap:'8px',flexWrap:'wrap',marginBottom:'15px'}}>
                          {profile&&contract&&(<button onClick={()=>showPreview(buildContractContent(profile,contract),'Договор')} style={btnB}><Eye size={13}/>Договор</button>)}
                          {profile&&(<button onClick={()=>showPreview(PD_CONSENT_TEXT(profile),'Согласие на ПД')} style={btnG}><FileText size={13}/>Согласие ПД</button>)}
                          {profile&&(<button onClick={()=>showPreview(buildPositionInstructionContent(u.role,profile.fullName),'Должностная инструкция')} style={btnG}><FileText size={13}/>Должн. инструкция</button>)}
                        </div>
                        <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'8px'}}>Работы по проектам:</b>
                        {[...new Set(workJournal.filter(j=>j.masterId===u.id).map(j=>j.project))].map(projectName=>{
                          const pWorks=workJournal.filter(j=>j.masterId===u.id&&j.project===projectName);
                          const pTotal=pWorks.reduce((s,w)=>s+(w.total||0),0);
                          const isProjectOpen=expandedMasterProject===u.id+'-'+projectName;
                          return(<div key={projectName} style={{marginBottom:'8px',borderRadius:'8px',border:'1.5px solid '+C.border,overflow:'hidden'}}>
                            <div style={{padding:'10px 12px',cursor:'pointer',display:'flex',justifyContent:'space-between',alignItems:'center',backgroundColor:C.bg}} onClick={()=>setExpandedMasterProject(isProjectOpen?null:u.id+'-'+projectName)}>
                              <b style={{fontSize:'12px',color:C.text}}>{projectName}</b>
                              <div style={{display:'flex',gap:'8px',alignItems:'center'}}><span style={{fontSize:'12px',color:C.success,fontWeight:'600'}}>{pTotal.toLocaleString()+' ₽'}</span>{isProjectOpen?<ChevronUp size={14}/>:<ChevronDown size={14}/>}</div>
                            </div>
                            {isProjectOpen&&(<div style={{padding:'8px 12px'}}>
                              {pWorks.map(w=>(<div key={w.id} style={{padding:'6px 0',borderBottom:'1px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center'}}><div><span style={{fontSize:'12px',color:C.text}}>{w.description}</span><p style={{color:C.textSec,margin:'1px 0',fontSize:'11px'}}>{w.quantity+' '+w.unit+' · '+w.date}</p></div><b style={{fontSize:'12px',color:C.success}}>{(w.total||0).toLocaleString()+' ₽'}</b></div>))}
                  </div>)}
                          </div>);
                        })}
                  </div>)}
                    </div>);
                  })}
                </div>);
              })}
            </div>)}

            {personnelTab==='staff'&&(<div>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Сотрудники компании</b>
                <button onClick={()=>{setShowForm(!showForm);setEditingItem(null);setNewStaff({name:'',role:'',phone:'',salary:'',project:'',payType:'оклад'});}} style={btnO}><Plus size={14}/>Добавить</button>
              </div>
              {showForm&&(<div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'8px'}}>👤 Основное</b>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:'10px',marginBottom:'10px'}}>
                  <input placeholder='Фамилия *' value={newStaff.lastName} onChange={e=>setNewStaff({...newStaff,lastName:e.target.value,name:[e.target.value,newStaff.firstName,newStaff.middleName].filter(Boolean).join(' ')})} style={{...inp,marginBottom:0}}/>
                  <input placeholder='Имя *' value={newStaff.firstName} onChange={e=>setNewStaff({...newStaff,firstName:e.target.value,name:[newStaff.lastName,e.target.value,newStaff.middleName].filter(Boolean).join(' ')})} style={{...inp,marginBottom:0}}/>
                  <input placeholder='Отчество' value={newStaff.middleName} onChange={e=>setNewStaff({...newStaff,middleName:e.target.value,name:[newStaff.lastName,newStaff.firstName,e.target.value].filter(Boolean).join(' ')})} style={{...inp,marginBottom:0}}/>
                </div>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px',marginBottom:'10px'}}>
                  <input placeholder='Должность (напр. штукатур)' value={newStaff.role} onChange={e=>setNewStaff({...newStaff,role:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input placeholder='Специализация' value={newStaff.specialization} onChange={e=>setNewStaff({...newStaff,specialization:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input placeholder='Телефон' value={newStaff.phone} onChange={e=>setNewStaff({...newStaff,phone:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <select value={newStaff.project} onChange={e=>setNewStaff({...newStaff,project:e.target.value})} style={{...inp,marginBottom:0}}><option value=''>Объект</option>{projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}</select>
                  <select value={newStaff.payType} onChange={e=>setNewStaff({...newStaff,payType:e.target.value})} style={{...inp,marginBottom:0}}><option value='оклад'>Оклад</option><option value='сдельно'>Сдельно</option><option value='почасово'>Почасово</option></select>
                  {newStaff.payType!=='сдельно'&&<input placeholder={newStaff.payType==='почасово'?'Ставка ₽/ч':'Оклад (₽)'} type='number' value={newStaff.salary} onChange={e=>setNewStaff({...newStaff,salary:e.target.value})} style={{...inp,marginBottom:0}}/>}
                  <select value={newStaff.status} onChange={e=>setNewStaff({...newStaff,status:e.target.value})} style={{...inp,marginBottom:0}}><option>Активен</option><option>Отпуск</option><option>Больничный</option><option>Уволен</option></select>
                  <select value={newStaff.employmentType} onChange={e=>setNewStaff({...newStaff,employmentType:e.target.value})} style={{...inp,marginBottom:0}}><option value=''>Тип занятости</option><option>Трудовой договор</option><option>ГПХ</option><option>Самозанятый</option><option>ИП</option><option>ООО</option></select>
                </div>

                <div onClick={()=>setStaffExpandedSections(s=>({...s,access:!s.access}))} style={{padding:'8px 12px',backgroundColor:C.bg,borderRadius:'8px',cursor:'pointer',marginBottom:'6px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                  <b style={{fontSize:'12px',color:C.text}}>🔐 Доступ в систему</b>
                  <span style={{fontSize:'14px',color:C.textSec}}>{staffExpandedSections.access?'▾':'▸'}</span>
                </div>
                {staffExpandedSections.access&&(<div style={{padding:'10px',marginBottom:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}>
                  <p style={{color:C.textSec,fontSize:'11px',margin:'0 0 8px'}}>Чтобы сотрудник мог входить в приложение — заполните все три поля.</p>
                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                    <select value={newStaff.systemRole} onChange={e=>setNewStaff({...newStaff,systemRole:e.target.value})} style={{...inp,marginBottom:0}}><option value=''>Системная роль</option>{Object.keys(ROLE_LABELS).filter(r=>r!=='заказчик'&&r!=='поставщик').map(r=><option key={r} value={r}>{ROLE_LABELS[r]}</option>)}</select>
                    <input type='email' placeholder='Email для входа' value={newStaff.email} onChange={e=>setNewStaff({...newStaff,email:e.target.value,emailWork:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input type='text' placeholder='Пароль' value={newStaff.password} onChange={e=>setNewStaff({...newStaff,password:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                  </div>
                </div>)}

                <div onClick={()=>setStaffExpandedSections(s=>({...s,docs:!s.docs}))} style={{padding:'8px 12px',backgroundColor:C.bg,borderRadius:'8px',cursor:'pointer',marginBottom:'6px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                  <b style={{fontSize:'12px',color:C.text}}>📄 Документы</b>
                  <span style={{fontSize:'14px',color:C.textSec}}>{staffExpandedSections.docs?'▾':'▸'}</span>
                </div>
                {staffExpandedSections.docs&&(<div style={{padding:'10px',marginBottom:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}>
                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                    <input placeholder='Паспорт серия' value={newStaff.passportSeries} onChange={e=>setNewStaff({...newStaff,passportSeries:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Паспорт номер' value={newStaff.passportNumber} onChange={e=>setNewStaff({...newStaff,passportNumber:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Кем выдан' value={newStaff.passportIssuedBy} onChange={e=>setNewStaff({...newStaff,passportIssuedBy:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                    <input type='date' placeholder='Дата выдачи' value={newStaff.passportIssuedDate} onChange={e=>setNewStaff({...newStaff,passportIssuedDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input type='date' placeholder='Дата рождения' value={newStaff.birthDate} onChange={e=>setNewStaff({...newStaff,birthDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='ИНН' value={newStaff.inn} onChange={e=>setNewStaff({...newStaff,inn:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='СНИЛС' value={newStaff.snils} onChange={e=>setNewStaff({...newStaff,snils:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Гражданство' value={newStaff.citizenship} onChange={e=>setNewStaff({...newStaff,citizenship:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Адрес проживания' value={newStaff.address} onChange={e=>setNewStaff({...newStaff,address:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                  </div>
                </div>)}

                <div onClick={()=>setStaffExpandedSections(s=>({...s,finance:!s.finance}))} style={{padding:'8px 12px',backgroundColor:C.bg,borderRadius:'8px',cursor:'pointer',marginBottom:'6px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                  <b style={{fontSize:'12px',color:C.text}}>💰 Финансы (для выплат)</b>
                  <span style={{fontSize:'14px',color:C.textSec}}>{staffExpandedSections.finance?'▾':'▸'}</span>
                </div>
                {staffExpandedSections.finance&&(<div style={{padding:'10px',marginBottom:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}>
                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                    <input placeholder='Расчётный счёт' value={newStaff.bankAccount} onChange={e=>setNewStaff({...newStaff,bankAccount:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Банк' value={newStaff.bankName} onChange={e=>setNewStaff({...newStaff,bankName:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='БИК' value={newStaff.bankBik} onChange={e=>setNewStaff({...newStaff,bankBik:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Кор/счёт' value={newStaff.bankCorr} onChange={e=>setNewStaff({...newStaff,bankCorr:e.target.value})} style={{...inp,marginBottom:0}}/>
                    {(newStaff.employmentType==='ИП'||newStaff.employmentType==='ООО')&&<input placeholder='ОГРНИП / ОГРН' value={newStaff.ogrnip} onChange={e=>setNewStaff({...newStaff,ogrnip:e.target.value})} style={{...inp,marginBottom:0}}/>}
                    <input placeholder='Номер карты' value={newStaff.cardNumber} onChange={e=>setNewStaff({...newStaff,cardNumber:e.target.value})} style={{...inp,marginBottom:0}}/>
                  </div>
                </div>)}

                <div onClick={()=>setStaffExpandedSections(s=>({...s,extra:!s.extra}))} style={{padding:'8px 12px',backgroundColor:C.bg,borderRadius:'8px',cursor:'pointer',marginBottom:'6px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                  <b style={{fontSize:'12px',color:C.text}}>📝 Дополнительно</b>
                  <span style={{fontSize:'14px',color:C.textSec}}>{staffExpandedSections.extra?'▾':'▸'}</span>
                </div>
                {staffExpandedSections.extra&&(<div style={{padding:'10px',marginBottom:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}>
                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                    <input placeholder='Email личный' value={newStaff.emailPersonal} onChange={e=>setNewStaff({...newStaff,emailPersonal:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Доп. телефон (родственник)' value={newStaff.phoneExtra} onChange={e=>setNewStaff({...newStaff,phoneExtra:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input type='date' placeholder='Дата приёма' value={newStaff.hiredDate} onChange={e=>setNewStaff({...newStaff,hiredDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input type='date' placeholder='Дата увольнения' value={newStaff.firedDate} onChange={e=>setNewStaff({...newStaff,firedDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Бригада/Подразделение' value={newStaff.brigade} onChange={e=>setNewStaff({...newStaff,brigade:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder='Категория/разряд' value={newStaff.category} onChange={e=>setNewStaff({...newStaff,category:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <textarea placeholder='Заметки' value={newStaff.notes} onChange={e=>setNewStaff({...newStaff,notes:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2',minHeight:'60px',fontFamily:'inherit'}}/>
                  </div>
                </div>)}

                <div style={{display:'flex',gap:'8px',marginTop:'14px'}}>
                  <button onClick={saveStaff} style={btnO}><Check size={14}/>{editingItem?'Сохранить':'Добавить'}</button>
                  <button onClick={()=>{setShowForm(false);setEditingItem(null);}} style={btnG}><X size={14}/>Отмена</button>
                </div>
              </div>)}
              <table style={tbl}><thead><tr><th style={tblH}></th><th style={tblH}>ФИО</th><th style={tblH}>Должность</th><th style={tblH}>Объект</th><th style={tblH}>Тип оплаты</th><th style={tblH}>Зарплата</th><th style={tblH}>Доступ</th><th style={tblH}></th></tr></thead><tbody>
                {staff.map(s=>{const hasAccess=users.find(u=>u.name===s.name);const isExp=expandedStaffId===s.id;return(<React.Fragment key={s.id}>
                  <tr style={{cursor:'pointer',backgroundColor:isExp?C.bg:'transparent'}} onClick={()=>openStaffProfile(s)}>
                    <td style={{...tblC,width:'24px',textAlign:'center'}}>{isExp?<ChevronUp size={14}/>:<ChevronDown size={14}/>}</td>
                    <td style={tblC}><b style={{fontSize:'13px'}}>{s.name}</b><p style={{color:C.textSec,margin:'1px 0',fontSize:'11px'}}>{s.phone}</p></td>
                    <td style={tblC}>{s.role}{s.specialization?' · '+s.specialization:''}</td>
                    <td style={tblC}>{s.project||'—'}</td>
                    <td style={tblC}>{s.payType==='сдельно'?'Сдельно':'Оклад: '+(s.salary||0).toLocaleString()+' ₽'}</td>
                    <td style={{...tblC,fontWeight:'600',color:C.success}}>{calcSalary(s).toLocaleString()+' ₽'}</td>
                    <td style={tblC} onClick={e=>e.stopPropagation()}>{hasAccess?<span style={{padding:'2px 8px',borderRadius:'10px',backgroundColor:C.successLight,color:C.success,fontSize:'11px',fontWeight:'600'}}>✅ {hasAccess.email||'есть'}</span>:<button onClick={()=>{const email=prompt('Email для входа:');if(!email) return;const password=prompt('Пароль:');if(!password) return;const role=prompt('Системная роль (директор/зам_директора/бухгалтер/прораб/мастер/субподрядчик/кладовщик/снабженец):','мастер');if(!role) return;fetch(API+'/users',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:s.name,email,password,role,projectName:s.project||''})}).then(()=>loadAll()).then(()=>alert('Доступ выдан: '+email));}} style={{...btnB,padding:'3px 8px',fontSize:'11px'}}>🔐 Выдать</button>}</td>
                    <td style={tblC} onClick={e=>e.stopPropagation()}><div style={{display:'flex',gap:'4px'}}><button onClick={()=>{setEditingItem(s);setNewStaff({...s,salary:String(s.salary||''),email:'',password:'',systemRole:''});setShowForm(true);}} style={{...btnG,padding:'3px 7px'}}><Edit2 size={11}/></button><button onClick={()=>deleteStaff(s.id)} style={{...btnR,padding:'3px 7px'}}><Trash2 size={11}/></button></div></td>
                  </tr>
                  {isExp&&(<tr><td colSpan='8' style={{padding:'14px 18px',backgroundColor:C.bg,borderBottom:'1.5px solid '+C.border}}>
                    {staffProfileLoading?<p style={{color:C.textMuted,fontSize:'12px'}}>⏳ Загрузка профиля...</p>:staffProfile?(<div>
                      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(200px,1fr))',gap:'10px',marginBottom:'14px'}}>
                        <div style={{padding:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}><p style={{margin:0,fontSize:'10px',color:C.textSec}}>Тип занятости</p><b style={{fontSize:'12px',color:C.text}}>{s.employmentType||'не указан'}</b></div>
                        <div style={{padding:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}><p style={{margin:0,fontSize:'10px',color:C.textSec}}>Паспорт</p><b style={{fontSize:'12px',color:C.text}}>{s.passportSeries||s.passportNumber?(s.passportSeries+' '+s.passportNumber):'не заполнен'}</b></div>
                        <div style={{padding:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}><p style={{margin:0,fontSize:'10px',color:C.textSec}}>ИНН</p><b style={{fontSize:'12px',color:C.text}}>{s.inn||'не заполнен'}</b></div>
                        <div style={{padding:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border}}><p style={{margin:0,fontSize:'10px',color:C.textSec}}>Банк</p><b style={{fontSize:'12px',color:C.text}}>{s.bankName||'не указан'}</b></div>
                      </div>

                      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'14px'}}>
                        <div style={{...card,padding:'12px'}}>
                          <b style={{fontSize:'12px',color:C.text,display:'block',marginBottom:'8px'}}>📄 Договоры ({staffProfile.contracts.length})</b>
                          {staffProfile.contracts.length===0?<p style={{color:C.textMuted,fontSize:'11px'}}>Договоров нет</p>:staffProfile.contracts.map(c=>(<div key={c.id} style={{padding:'6px 0',borderBottom:'1px solid '+C.border,fontSize:'11px'}}><b>№{c.contractNumber}</b> · {c.project} · {c.status||'-'}</div>))}
                        </div>
                        <div style={{...card,padding:'12px'}}>
                          <b style={{fontSize:'12px',color:C.text,display:'block',marginBottom:'8px'}}>📋 Акты ({staffProfile.acts.length})</b>
                          {staffProfile.acts.length===0?<p style={{color:C.textMuted,fontSize:'11px'}}>Актов нет</p>:staffProfile.acts.map(a=>(<div key={a.id} style={{padding:'6px 0',borderBottom:'1px solid '+C.border,fontSize:'11px',display:'flex',justifyContent:'space-between'}}><span>№{a.actNumber} · {a.project}</span><b style={{color:C.success}}>{a.totalAmount.toLocaleString()} ₽</b></div>))}
                        </div>
                        <div style={{...card,padding:'12px'}}>
                          <b style={{fontSize:'12px',color:C.text,display:'block',marginBottom:'8px'}}>✅ Согласия на ПД ({staffProfile.pdConsents.length})</b>
                          {staffProfile.pdConsents.length===0?<p style={{color:C.warning,fontSize:'11px'}}>⚠️ Не подписано</p>:staffProfile.pdConsents.map(p=>(<div key={p.id} style={{padding:'6px 0',fontSize:'11px',color:C.success}}>✓ Подписано {p.signedAt}</div>))}
                        </div>
                        <div style={{...card,padding:'12px'}}>
                          <b style={{fontSize:'12px',color:C.text,display:'block',marginBottom:'8px'}}>🔒 Инструктажи ТБ ({staffProfile.tbJournal.length})</b>
                          {staffProfile.tbJournal.length===0?<p style={{color:C.warning,fontSize:'11px'}}>⚠️ Инструктажей нет</p>:staffProfile.tbJournal.slice(0,5).map(t=>(<div key={t.id} style={{padding:'4px 0',fontSize:'11px'}}><b>{t.instructionType}</b> · {t.projectName} · {t.date}</div>))}
                        </div>
                      </div>

                      <div style={{...card,padding:'12px',marginTop:'14px'}}>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'8px'}}>
                          <b style={{fontSize:'12px',color:C.text}}>📎 Прочие документы ({staffProfile.customDocuments.length})</b>
                          <button onClick={()=>setShowStaffDocForm(true)} style={{...btnO,padding:'4px 10px',fontSize:'11px'}}><Plus size={11}/>Добавить</button>
                        </div>
                        {showStaffDocForm&&(<div style={{marginBottom:'10px',padding:'10px',backgroundColor:C.bg,borderRadius:'8px'}}>
                          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'6px',marginBottom:'6px'}}>
                            <select value={newStaffDoc.docType} onChange={e=>setNewStaffDoc({...newStaffDoc,docType:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>
                              {['Трудовой договор','Договор ГПХ','Договор с самозанятым','Договор с ИП','Приказ','Должн. инструкция','Мед. книжка','Справка о статусе самозанятого','Чек НПД','Прочее'].map(t=><option key={t}>{t}</option>)}
                            </select>
                            <input placeholder='Название/Номер' value={newStaffDoc.title} onChange={e=>setNewStaffDoc({...newStaffDoc,title:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                          </div>
                          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:'6px',marginBottom:'6px'}}>
                            <input type='file' accept='image/*,.pdf' onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0]);setNewStaffDoc({...newStaffDoc,fileUrl:url});}}} style={{fontSize:'11px'}}/>
                            <input type='date' value={newStaffDoc.signedAt} onChange={e=>setNewStaffDoc({...newStaffDoc,signedAt:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                            <input type='date' placeholder='Истекает' value={newStaffDoc.expiresAt} onChange={e=>setNewStaffDoc({...newStaffDoc,expiresAt:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                          </div>
                          <div style={{display:'flex',gap:'6px'}}>
                            <button onClick={()=>addStaffDoc(s.id)} style={{...btnO,fontSize:'11px',padding:'4px 10px'}}><Check size={11}/>Сохранить</button>
                            <button onClick={()=>setShowStaffDocForm(false)} style={{...btnG,fontSize:'11px',padding:'4px 10px'}}><X size={11}/>Отмена</button>
                          </div>
                        </div>)}
                        {staffProfile.customDocuments.map(d=>(<div key={d.id} style={{padding:'6px 0',borderBottom:'1px solid '+C.border,fontSize:'11px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                          <div style={{flex:1}}><b>{d.docType}</b> · {d.title}{d.signedAt?' · подписан '+d.signedAt:''}{d.expiresAt?' · истекает '+d.expiresAt:''}</div>
                          <div style={{display:'flex',gap:'4px'}}>
                            {d.fileUrl&&<a href={d.fileUrl.startsWith('http')?d.fileUrl:API+d.fileUrl} target='_blank' rel='noreferrer' style={{...btnB,padding:'2px 8px',fontSize:'10px',textDecoration:'none'}}>👁️</a>}
                            <button onClick={async()=>{if(window.confirm('Удалить документ?')){await fetch(API+'/staff-documents/'+d.id,{method:'DELETE'});const data=await fetch(API+'/staff/'+s.id+'/profile').then(r=>r.json());setStaffProfile(data);}}} style={{...btnR,padding:'2px 7px'}}><Trash2 size={10}/></button>
                          </div>
                        </div>))}
                        {staffProfile.customDocuments.length===0&&<p style={{color:C.textMuted,fontSize:'11px',padding:'4px'}}>Нет загруженных документов</p>}
                      </div>

                      {staffProfile.workJournal.length>0&&(<div style={{...card,padding:'12px',marginTop:'14px'}}>
                        <b style={{fontSize:'12px',color:C.text,display:'block',marginBottom:'8px'}}>💼 Последние работы ({staffProfile.workJournal.length})</b>
                        {staffProfile.workJournal.slice(0,8).map((w,i)=>(<div key={i} style={{padding:'4px 0',borderBottom:'1px solid '+C.border,fontSize:'11px',display:'flex',justifyContent:'space-between'}}><span>{w.project} · {w.description} · {w.quantity} {w.unit}</span><b style={{color:C.success}}>{w.total.toLocaleString()} ₽</b></div>))}
                      </div>)}
                    </div>):<p style={{color:C.textMuted,fontSize:'12px'}}>Не удалось загрузить профиль</p>}
                  </td></tr>)}
                </React.Fragment>);})}
              </tbody></table>
            </div>)}

            {personnelTab==='timesheet'&&(<div>
              <h3 style={{color:C.text,marginBottom:'15px',fontSize:'15px',fontWeight:'700'}}>Табель учёта</h3>
              <div style={{overflowX:'auto'}}><table style={tbl}><thead><tr><th style={{...tblH,minWidth:'150px'}}>Сотрудник</th>{daysInMonth.map(d=><th key={d} style={{...tblH,textAlign:'center',padding:'6px 4px',minWidth:'28px'}}>{d}</th>)}<th style={tblH}>Дни</th><th style={tblH}>Итого</th></tr></thead><tbody>
                {staff.map(s=>(<tr key={s.id}><td style={tblC}><b style={{fontSize:'12px'}}>{s.name}</b><p style={{color:C.textSec,margin:'1px 0',fontSize:'11px'}}>{s.role}</p></td>{daysInMonth.map(d=>(<td key={d} style={{...tblC,textAlign:'center',padding:'4px',cursor:'pointer'}} onClick={()=>toggleDay(s.id,d)}><div style={{width:'22px',height:'22px',borderRadius:'6px',backgroundColor:timesheet[s.id+'-'+d]?C.success:'transparent',border:'1.5px solid '+(timesheet[s.id+'-'+d]?C.success:C.border),display:'flex',alignItems:'center',justifyContent:'center',margin:'auto',fontSize:'10px',color:'white',fontWeight:'700'}}>{timesheet[s.id+'-'+d]?'✓':''}</div></td>))}<td style={{...tblC,fontWeight:'600'}}>{workedDays(s.id)}</td><td style={{...tblC,fontWeight:'700',color:C.success}}>{calcSalary(s).toLocaleString()+' ₽'}</td></tr>))}
              </tbody></table></div>
            </div>)}

            {personnelTab==='piecework'&&(<div>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Сдельные работы</b>
                <button onClick={()=>setShowPiecework(!showPiecework)} style={btnO}><Plus size={14}/>Добавить</button>
              </div>
              {showPiecework&&(<div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                  <select value={newPiecework.staffId} onChange={e=>setNewPiecework({...newPiecework,staffId:e.target.value})} style={{...inp,marginBottom:0}}><option value="">Сотрудник *</option>{staff.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select>
                  <select value={newPiecework.project} onChange={e=>setNewPiecework({...newPiecework,project:e.target.value})} style={{...inp,marginBottom:0}}><option value="">Объект</option>{projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}</select>
                  <input placeholder="Описание *" value={newPiecework.description} onChange={e=>setNewPiecework({...newPiecework,description:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                  <input placeholder="Количество *" type="number" value={newPiecework.quantity} onChange={e=>setNewPiecework({...newPiecework,quantity:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <select value={newPiecework.unit} onChange={e=>setNewPiecework({...newPiecework,unit:e.target.value})} style={{...inp,marginBottom:0}}>{UNITS.map(u=><option key={u}>{u}</option>)}</select>
                  <input placeholder="Цена за единицу *" type="number" value={newPiecework.pricePerUnit} onChange={e=>setNewPiecework({...newPiecework,pricePerUnit:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <div style={{padding:'10px',backgroundColor:C.accentLight,borderRadius:'8px',border:'1.5px solid '+C.accentBorder,display:'flex',alignItems:'center',justifyContent:'center'}}><b style={{color:C.accent}}>{newPiecework.quantity&&newPiecework.pricePerUnit?(Number(newPiecework.quantity)*Number(newPiecework.pricePerUnit)).toLocaleString()+' ₽':'0 ₽'}</b></div>
                </div>
                <div style={{display:'flex',gap:'8px',marginTop:'12px'}}><button onClick={addPiecework} style={btnO}><Check size={14}/>Добавить</button><button onClick={()=>setShowPiecework(false)} style={btnG}><X size={14}/>Отмена</button></div>
              </div>)}
              {staff.map(s=>{
                const sWorks=piecework.filter(p=>Number(p.staffId)===s.id);
                const sTotal=sWorks.reduce((ss,p)=>ss+p.total,0);
                if(sWorks.length===0) return null;
                const isOpen=expandedPieceworkProject===s.id;
                return(<div key={s.id} style={{...card,marginBottom:'10px'}}>
                  <div style={{padding:'14px',cursor:'pointer',display:'flex',justifyContent:'space-between',alignItems:'center'}} onClick={()=>setExpandedPieceworkProject(isOpen?null:s.id)}>
                    <div><b style={{color:C.text,fontSize:'13px'}}>{s.name}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{sWorks.length+' работ'}</p></div>
                    <div style={{display:'flex',alignItems:'center',gap:'10px'}}><b style={{color:C.success,fontSize:'14px'}}>{sTotal.toLocaleString()+' ₽'}</b>{isOpen?<ChevronUp size={16}/>:<ChevronDown size={16}/>}</div>
                  </div>
                  {isOpen&&(<div style={{borderTop:'1.5px solid '+C.border,padding:'12px 14px'}}>
                    {sWorks.map(w=>(<div key={w.id} style={{padding:'8px 0',borderBottom:'1px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center'}}><div><b style={{fontSize:'12px',color:C.text}}>{w.description}</b><p style={{color:C.textSec,margin:'1px 0',fontSize:'11px'}}>{w.quantity+' '+w.unit+' × '+w.pricePerUnit.toLocaleString()+' ₽ · '+w.date+(w.project?' · '+w.project:'')}</p></div><div style={{display:'flex',gap:'6px',alignItems:'center'}}><b style={{fontSize:'12px',color:C.success}}>{w.total.toLocaleString()+' ₽'}</b><button onClick={()=>deletePiecework(w.id)} style={{...btnR,padding:'3px 6px'}}><Trash2 size={10}/></button></div></div>))}
                  </div>)}
                </div>);
              })}
            </div>)}
          </div>)}

          {activePage==='pricelists'&&(<div>
            <div style={{display:'flex',gap:'16px',height:'calc(100vh - 120px)'}}>
              <div style={{width:'280px',flexShrink:0,display:'flex',flexDirection:'column',gap:'10px',overflowY:'auto'}}>
                <button onClick={()=>{setShowForm(!showForm);setEditingItem(null);setNewPricelist({name:'',description:'',forWho:'',coefficient:1.0});setSelectedPricelist(null);setPricelistItems([]);}} style={{...btnO,justifyContent:'center'}}><Plus size={14}/>Новый прайс-лист</button>
                <button onClick={()=>{setGeneratePricelistForm({description:'',name:'',forWho:'',coefficient:1.0});setShowGeneratePricelist(true);}} style={{...btnB,backgroundColor:'#10b981',justifyContent:'center'}}><Bot size={14}/>🤖 Сгенерировать ИИ</button>
                <button onClick={()=>{setFromEstimateForm({estimateId:'',name:'',forWho:'',coefficient:1.0});setShowFromEstimate(true);}} style={{...btnB,justifyContent:'center'}}><FileText size={14}/>📋 Из сметы</button>
                {showForm&&!selectedPricelist&&(<div style={{...card,padding:'20px'}}><div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}><input placeholder="Название *" value={newPricelist.name} onChange={e=>setNewPricelist({...newPricelist,name:e.target.value})} style={{...inp,marginBottom:0}}/><select value={newPricelist.forWho} onChange={e=>setNewPricelist({...newPricelist,forWho:e.target.value})} style={{...inp,marginBottom:0}}><option value="">Для кого</option>{['Электрики','Сантехники','Каменщики','Отделочники','Кровельщики','Монтажники','Общий'].map(r=><option key={r}>{r}</option>)}</select></div><label style={{color:C.textSec,fontSize:'13px',display:'block',marginTop:'10px',marginBottom:'4px'}}>{'Коэффициент: ×'+newPricelist.coefficient}</label><input type="range" min="0.5" max="3" step="0.1" value={newPricelist.coefficient} onChange={e=>setNewPricelist({...newPricelist,coefficient:Number(e.target.value)})} style={{width:'100%',marginBottom:'12px',accentColor:C.accent}}/><div style={{display:'flex',gap:'10px'}}><button onClick={savePricelist} style={btnO}>Сохранить</button><button onClick={()=>{setShowForm(false);setEditingItem(null);}} style={btnG}>Отмена</button></div></div>)}
                {pricelists.map(pl=>(<div key={pl.id} onClick={async()=>{setSelectedPricelist(pl);await loadPricelistItems(pl.id);setShowForm(false);setEditingPlItem(null);}} style={{...card,padding:'14px',cursor:'pointer',border:'1.5px solid '+(selectedPricelist?.id===pl.id?C.accent:C.border),backgroundColor:selectedPricelist?.id===pl.id?C.accentLight:C.bgWhite}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
                    <div style={{flex:1}}><h3 style={{margin:0,color:C.text,fontSize:'14px',fontWeight:'600'}}>{pl.name}</h3>{pl.forWho&&<p style={{color:C.accent,margin:'3px 0',fontSize:'12px'}}>{'Для: '+pl.forWho}</p>}<p style={{color:C.info,margin:'3px 0',fontSize:'12px'}}>{'Коэф.: ×'+pl.coefficient}</p></div>
                    <div style={{display:'flex',gap:'4px'}} onClick={e=>e.stopPropagation()}><button onClick={()=>copyPricelist(pl)} style={{...btnG,padding:'3px 7px',fontSize:'10px'}}><Copy size={10}/></button><button onClick={()=>deletePricelist(pl.id)} style={{...btnR,padding:'3px 7px'}}><Trash2 size={10}/></button></div>
                  </div>
                </div>))}
              </div>
              <div style={{flex:1,overflowY:'auto'}}>
                {selectedPricelist?(<div>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',marginBottom:'20px',flexWrap:'wrap',gap:'10px'}}>
                    <div><h3 style={{margin:0,color:C.text,fontWeight:'700'}}>{selectedPricelist.name}</h3>{selectedPricelist.forWho&&<p style={{color:C.accent,margin:'4px 0',fontSize:'13px'}}>{'Для: '+selectedPricelist.forWho}</p>}<div style={{display:'flex',alignItems:'center',gap:'8px',marginTop:'4px'}}><span style={{color:C.textSec,fontSize:'13px'}}>Коэффициент: ×</span><input type='number' step='0.1' min='0.1' max='10' value={selectedPricelist.coefficient} onChange={e=>setSelectedPricelist(prev=>({...prev,coefficient:Number(e.target.value)}))} onKeyDown={async e=>{if(e.key==='Enter'){await fetch(API+'/pricelists/'+selectedPricelist.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...selectedPricelist,coefficient:Number(e.target.value)})});await loadAll();alert('Сохранено!');}}} style={{width:'70px',padding:'4px 8px',border:'1.5px solid '+C.accent,borderRadius:'6px',fontSize:'13px',fontWeight:'600',color:C.accent}}/><span style={{color:C.textMuted,fontSize:'11px'}}>Enter для сохранения</span></div></div>
                    <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
                      <button onClick={()=>showPreview(buildPricelistContent(selectedPricelist,pricelistItems),'Прайс-лист')} style={btnB}><Eye size={14}/>Просмотр</button>
                      <button onClick={()=>exportToExcel(pricelistItems.map(i=>({Категория:i.category||'',Наименование:i.name,Единица:i.unit,Цена:i.price,'С коэф.':i.price*selectedPricelist.coefficient})),'Прайс_'+selectedPricelist.name)} style={btnG}><Download size={14}/>Excel</button>
                    </div>
                  </div>
                  <div style={{...card,padding:'16px',marginBottom:'16px'}}>
                    <h4 style={{color:C.text,marginBottom:'12px',fontSize:'13px',fontWeight:'600'}}>{editingPlItem?'Редактировать позицию':'Добавить позицию'}</h4>
                    <div style={{display:'grid',gridTemplateColumns:'3fr 1fr 1fr 2fr auto',gap:'8px',alignItems:'center'}}>
                      <input placeholder="Наименование *" value={newPlItem.name} onChange={e=>setNewPlItem({...newPlItem,name:e.target.value})} style={{...inp,marginBottom:0,fontSize:'13px'}}/>
                      <select value={newPlItem.unit} onChange={e=>setNewPlItem({...newPlItem,unit:e.target.value})} style={{...inp,marginBottom:0,fontSize:'13px'}}>{UNITS.map(u=><option key={u}>{u}</option>)}</select>
                      <input placeholder="Цена *" type="number" value={newPlItem.price} onChange={e=>setNewPlItem({...newPlItem,price:e.target.value})} style={{...inp,marginBottom:0,fontSize:'13px'}}/>
                      <select value={newPlItem.category} onChange={e=>setNewPlItem({...newPlItem,category:e.target.value})} style={{...inp,marginBottom:0,fontSize:'13px'}}><option value="">Категория</option>{Object.keys(PRICELISTS_DATA).map(c=><option key={c}>{c}</option>)}</select>
                      <button onClick={savePlItem} style={{...btnO,padding:'8px 14px'}}><Check size={14}/>{editingPlItem?'Сохр.':'Добавить'}</button>
                    </div>
                    {editingPlItem&&<button onClick={()=>{setEditingPlItem(null);setNewPlItem({name:'',unit:'м2',price:'',category:''});}} style={{...btnG,marginTop:'8px',fontSize:'12px'}}><X size={12}/>Отменить</button>}
                  </div>
                  {[...new Set(pricelistItems.map(i=>(i.category||'').trim()))].sort((a,b)=>a==='' ? 1 : b==='' ? -1 : a.localeCompare(b,'ru')).map(cat=>{
                    const catItems=pricelistItems.filter(i=>(i.category||'').trim()===cat);
                    if(catItems.length===0) return null;
                    return(<div key={cat||'nocat'} style={{marginBottom:'20px'}}>
                      {cat&&<div style={{padding:'8px 12px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border,marginBottom:'8px',display:'flex',alignItems:'center',gap:'8px'}}><b style={{color:C.accent,fontSize:'12px',textTransform:'uppercase'}}>{'🔧 '+cat}</b><span style={{color:C.textSec,fontSize:'11px'}}>{'('+catItems.length+' позиций)'}</span></div>}
                      <table style={tbl}><thead><tr><th style={tblH}>Наименование</th><th style={tblH}>Ед.</th><th style={tblH}>Цена</th><th style={tblH}>С коэф.</th><th style={tblH}></th></tr></thead><tbody>
                        {catItems.map(item=>(<tr key={item.id}>
                          <td style={tblC}>{item.name}</td>
                          <td style={tblC}>{item.unit}</td>
                          <td style={tblC}>{inlineEditPl===item.id?(<div style={{display:'flex',gap:'4px',alignItems:'center'}}><input type='number' value={inlineEditPrice} onChange={e=>setInlineEditPrice(e.target.value)} onKeyDown={async e=>{if(e.key==='Enter') saveInlinePlItem(item);if(e.key==='Escape'){setInlineEditPl(null);setInlineEditPrice('');}}} autoFocus style={{width:'80px',padding:'4px 6px',border:'1.5px solid '+C.accent,borderRadius:'6px',fontSize:'12px'}}/><button onClick={()=>saveInlinePlItem(item)} style={{...btnGr,padding:'3px 6px'}}><Check size={11}/></button><button onClick={()=>{setInlineEditPl(null);setInlineEditPrice('');}} style={{...btnR,padding:'3px 6px'}}><X size={11}/></button></div>):(<span style={{cursor:'pointer',fontWeight:'500'}} onClick={()=>{setInlineEditPl(item.id);setInlineEditPrice(String(item.price));}}>{item.price.toLocaleString()+' ₽'}</span>)}</td>
                          <td style={{...tblC,color:C.info,fontWeight:'600'}}>{(item.price*selectedPricelist.coefficient).toLocaleString()+' ₽'}</td>
                          <td style={tblC}><div style={{display:'flex',gap:'4px'}}><button onClick={()=>{setEditingPlItem(item);setNewPlItem({name:item.name,unit:item.unit,price:String(item.price),category:item.category||''});}} style={{...btnG,padding:'3px 8px',fontSize:'11px'}}><Edit2 size={11}/></button><button onClick={()=>deletePlItem(item.id)} style={{...btnR,padding:'3px 6px'}}><Trash2 size={11}/></button></div></td>
                        </tr>))}
                      </tbody></table>
                    </div>);
                  })}
                  {pricelistItems.length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Позиций нет — добавьте первую!</p>}
                </div>):(<div style={{...card,padding:'60px',textAlign:'center',color:C.textMuted}}><Tag size={48} style={{marginBottom:'15px',opacity:0.3}}/><p>Выберите прайс-лист</p></div>)}
              </div>
            </div>
          </div>)}

          {activePage==='users'&&isLeadership()&&(<div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px',flexWrap:'wrap',gap:'10px'}}>
              <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
                <button onClick={()=>{setShowForm(!showForm);setEditingItem(null);setNewUser({name:'',email:'',password:'',role:'прораб'});}} style={btnO}><Plus size={14}/>Новый пользователь</button>
                <button onClick={()=>setShowInvites(!showInvites)} style={btnG}><Plus size={14}/>Коды приглашений</button>
              </div>
              <input placeholder="Поиск..." value={searchUser} onChange={e=>setSearchUser(e.target.value)} style={{...inp,marginBottom:0,width:'220px'}}/>
            </div>
            {showForm&&(<div style={{...card,padding:'20px',marginBottom:'20px'}}>
              <h3 style={{color:C.text,marginBottom:'15px',fontWeight:'700'}}>{editingItem?'Редактировать':'Новый пользователь'}</h3>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                <input placeholder="Имя *" value={newUser.name} onChange={e=>setNewUser({...newUser,name:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input type="email" placeholder="Email *" value={newUser.email} onChange={e=>setNewUser({...newUser,email:e.target.value})} style={{...inp,marginBottom:0}}/>
                {!editingItem&&<input type="password" placeholder="Пароль *" value={newUser.password} onChange={e=>setNewUser({...newUser,password:e.target.value})} style={{...inp,marginBottom:0}}/>}
                <select value={newUser.role} onChange={e=>setNewUser({...newUser,role:e.target.value})} style={{...inp,marginBottom:0}}>{Object.keys(ROLES).map(r=><option key={r} value={r}>{ROLE_LABELS[r]||r}</option>)}</select>
                {['заказчик','технадзор'].includes(newUser.role)&&(<select value={newUser.projectId} onChange={e=>{const p=projects.find(pr=>pr.id===Number(e.target.value));setNewUser({...newUser,projectId:e.target.value,projectName:p?p.name:''});}} style={{...inp,marginBottom:0}}><option value=''>Привязать к проекту *</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>)}
              </div>
              <div style={{display:'flex',gap:'10px',marginTop:'15px'}}><button onClick={saveUser} style={btnO}><Check size={14}/>{editingItem?'Сохранить':'Создать'}</button><button onClick={()=>{setShowForm(false);setEditingItem(null);}} style={btnG}><X size={14}/>Отмена</button></div>
            </div>)}
            {showInvites&&(<div style={{...card,padding:'20px',marginBottom:'20px'}}>
              <h3 style={{color:C.text,marginBottom:'15px',fontWeight:'700'}}>Коды приглашений</h3>
              <div style={{display:'flex',gap:'10px',marginBottom:'15px',alignItems:'center'}}>
                <select value={newInviteRole} onChange={e=>setNewInviteRole(e.target.value)} style={{...inp,marginBottom:0,width:'200px'}}>{Object.keys(ROLES).map(r=><option key={r} value={r}>{ROLE_LABELS[r]||r}</option>)}</select>
                <button onClick={createInvite} style={btnO}><Plus size={14}/>Создать код</button>
              </div>
              {inviteCodes.filter(c=>!c.used).map(c=>(<div key={c.id} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'10px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'8px',border:'1.5px solid '+C.border}}>
                <div><b style={{fontSize:'14px',letterSpacing:'2px',color:C.accent}}>{c.code}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{ROLE_LABELS[c.role]||c.role}</p></div>
                <div style={{display:'flex',gap:'6px'}}>
                  <button onClick={()=>navigator.clipboard.writeText(c.code)} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}><Copy size={11}/>Скопировать</button>
                  <button onClick={()=>deleteInvite(c.id)} style={{...btnR,padding:'5px 8px'}}><Trash2 size={11}/></button>
                </div>
              </div>))}
            </div>)}
            {ROLE_GROUPS.map(group=>{
              const groupUsers=users.filter(u=>group.roles.includes(u.role)&&u.name.toLowerCase().includes(searchUser.toLowerCase()));
              if(groupUsers.length===0) return null;
              const isOpen=expandedGroup===group.key;
              return(<div key={group.key} style={{...card,marginBottom:'10px'}}>
                <div style={{padding:'14px 18px',cursor:'pointer',display:'flex',justifyContent:'space-between',alignItems:'center'}} onClick={()=>setExpandedGroup(isOpen?null:group.key)}>
                  <div style={{display:'flex',alignItems:'center',gap:'10px'}}><div style={{width:'10px',height:'10px',borderRadius:'50%',backgroundColor:group.color}}/><b style={{color:C.text,fontSize:'14px'}}>{group.label}</b><span style={{...badge(group.color,C.bgWhite,C.border)}}>{groupUsers.length}</span></div>
                  {isOpen?<ChevronUp size={16} color={C.textMuted}/>:<ChevronDown size={16} color={C.textMuted}/>}
                </div>
                {isOpen&&(<div style={{borderTop:'1.5px solid '+C.border,padding:'10px 18px'}}>
                  {groupUsers.map(u=>(<div key={u.id} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'10px 0',borderBottom:'1px solid '+C.border}}>
                    <div style={{display:'flex',alignItems:'center',gap:'10px'}}>
                      <div style={{width:'36px',height:'36px',borderRadius:'10px',backgroundColor:roleColor(u.role),display:'flex',alignItems:'center',justifyContent:'center',color:'white',fontWeight:'700',fontSize:'14px'}}>{u.name.charAt(0)}</div>
                      <div><b style={{fontSize:'13px',color:C.text}}>{u.name}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{u.email+' · '+(ROLE_LABELS[u.role]||u.role)}</p></div>
                    </div>
                    <div style={{display:'flex',gap:'6px'}}>
                      <button onClick={()=>{setEditingItem(u);setNewUser({name:u.name,email:u.email,password:'',role:u.role});setShowForm(true);}} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}><Edit2 size={11}/></button>
                      {u.id!==user.id&&<button onClick={()=>deleteUser(u.id)} style={{...btnR,padding:'5px 8px',fontSize:'11px'}}><Trash2 size={11}/></button>}
                    </div>
                  </div>))}
                </div>)}
              </div>);
            })}
          </div>)}
          {activePage==='estimates'&&(<div>
            <div style={{display:'flex',gap:'8px',marginBottom:'20px',flexWrap:'wrap'}}>
              {['list','import'].map(tab=>(<button key={tab} onClick={()=>setEstimatesTab(tab)} style={{...estimatesTab===tab?btnO:btnG,fontSize:'12px',padding:'7px 14px'}}>{{list:'📋 Сметы',import:'📥 Импорт Гранд Смета'}[tab]}</button>))}
              <button onClick={()=>setActivePage('pricelists')} style={{...btnG,fontSize:'12px',padding:'7px 14px'}}>🏷️ Прайс-листы</button>
            </div>

            {estimatesTab==='list'&&(<div>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Сметы</b>
                <div style={{display:'flex',gap:'8px'}}>
                  <button onClick={()=>{setGenerateForm({description:'',projectId:'',pricelistId:'',area:'',name:''});setShowGenerateEstimate(true);}} style={{...btnB,backgroundColor:'#10b981'}}><Bot size={14}/>🤖 Сгенерировать ИИ</button>
                  <button onClick={()=>setShowForm(!showForm)} style={btnO}><Plus size={14}/>Новая смета</button>
                </div>
              </div>
              {showForm&&(<div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                  <select value={newEstimate.projectId} onChange={e=>{const p=projects.find(pr=>pr.id===Number(e.target.value));setNewEstimate({...newEstimate,projectId:e.target.value,projectName:p?p.name:'',name:p?'Смета — '+p.name:''});}} style={{...inp,marginBottom:0}}><option value="">Выберите проект</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
                  <input placeholder="Название сметы *" value={newEstimate.name} onChange={e=>setNewEstimate({...newEstimate,name:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input placeholder="Версия" value={newEstimate.version} onChange={e=>setNewEstimate({...newEstimate,version:e.target.value})} style={{...inp,marginBottom:0}}/>
                  {estimatesList.filter(e=>e.isTemplate).length>0&&(<select value={newEstimate.templateId||''} onChange={e=>setNewEstimate({...newEstimate,templateId:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}>
                    <option value=''>📄 Пустая смета</option>
                    {estimatesList.filter(e=>e.isTemplate).map(t=>(<option key={t.id} value={t.id}>⭐ Из шаблона: {t.name}</option>))}
                  </select>)}
                </div>
                <div style={{display:'flex',gap:'8px',marginTop:'12px'}}><button onClick={async()=>{
                  if(!newEstimate.name) return;
                  let sections=[];
                  if(newEstimate.templateId){
                    const tmpl=estimatesList.find(e=>String(e.id)===String(newEstimate.templateId));
                    if(tmpl) sections=(tmpl.sections||[]).map(s=>({...s,id:Date.now()+Math.random(),items:(s.items||[]).map(i=>({...i,id:Date.now()+Math.random()}))}));
                  }
                  const res=await fetch(API+'/estimates',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newEstimate,sections})});
                  const est=await res.json();
                  const newEst={...newEstimate,id:est.id,sections};
                  setEstimatesList([...estimatesList,newEst]);
                  setSelectedEstimate(newEst);
                  setShowForm(false);
                  setNewEstimate({projectId:'',projectName:'',name:'',version:'1.0',smetaType:'Заказчик',templateId:''});
                }} style={btnO}><Check size={14}/>Создать</button><button onClick={()=>setShowForm(false)} style={btnG}><X size={14}/>Отмена</button></div>
              </div>)}
              {selectedEstimate?(<div>
                {(importValidating||importValidationWarnings.length>0)&&(<div style={{...card,padding:'14px',marginBottom:'14px',backgroundColor:importValidating?C.infoLight:(importValidationWarnings.some(w=>w.severity==='критично')?C.dangerLight:C.warningLight),border:'1.5px solid '+(importValidating?C.infoBorder:(importValidationWarnings.some(w=>w.severity==='критично')?C.dangerBorder:C.warningBorder))}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'8px'}}>
                    <b style={{fontSize:'13px',color:importValidating?C.info:(importValidationWarnings.some(w=>w.severity==='критично')?C.danger:C.warning)}}>{importValidating?'🤖 ИИ проверяет смету...':('⚠️ Найдено замечаний: '+importValidationWarnings.length)}</b>
                    {!importValidating&&<button onClick={()=>setImportValidationWarnings([])} style={{background:'none',border:'none',cursor:'pointer',fontSize:'16px',color:C.textSec}}>×</button>}
                  </div>
                  {importValidationWarnings.length>0&&(<div>{importValidationWarnings.map((w,i)=>(<div key={i} style={{padding:'6px 8px',marginBottom:'4px',backgroundColor:'rgba(255,255,255,0.6)',borderRadius:'6px',borderLeft:'3px solid '+(w.severity==='критично'?C.danger:w.severity==='внимание'?C.warning:C.info)}}><b style={{fontSize:'11px',color:C.text}}>{(w.severity==='критично'?'🔴 ':w.severity==='внимание'?'🟡 ':'💡 ')+(w.where||'?')}</b><p style={{fontSize:'11px',color:C.textSec,margin:'2px 0 0'}}>{w.message||''}</p></div>))}</div>)}
                </div>)}
                <div style={{display:'flex',gap:'8px',marginBottom:'15px',alignItems:'center'}}>
                  <button onClick={()=>setSelectedEstimate(null)} style={btnG}><ArrowLeft size={14}/>Назад</button>
                  <b style={{color:C.text,fontSize:'15px'}}>{selectedEstimate.name}</b>
                  <button onClick={()=>{const total=(selectedEstimate.sections||[]).flatMap(s=>s.items||[]).reduce((sum,i)=>sum+(i.isImported?Number(i.priceWork||0):Number(i.quantity||0)*(Number(i.priceWork||0)+Number(i.priceMaterial||0))),0);const html='<h2>'+selectedEstimate.name+'</h2><table><tr><th>N</th><th>Наименование</th><th>Ед.</th><th>Кол-во</th><th>Цена работ</th><th>Цена мат.</th><th>Сумма</th></tr>'+(selectedEstimate.sections||[]).flatMap(s=>[`<tr><td colspan="7"><b>${s.name}</b></td></tr>`,...(s.items||[]).map((it,i)=>`<tr><td>${i+1}</td><td>${it.name}</td><td>${it.unit}</td><td>${it.quantity}</td><td>${Number(it.priceWork||0).toLocaleString()}</td><td>${Number(it.priceMaterial||0).toLocaleString()}</td><td>${(Number(it.quantity||0)*(Number(it.priceWork||0)+Number(it.priceMaterial||0))).toLocaleString()}</td></tr>`)]).join('')+'<tr><td colspan="6"><b>ИТОГО:</b></td><td><b>'+total.toLocaleString()+' ₽</b></td></tr></table>';showPreview(html,'Смета');}} style={btnB}><Eye size={14}/>Просмотр</button>
                  <button onClick={()=>exportToExcel((selectedEstimate.sections||[]).flatMap(s=>(s.items||[]).map(i=>({Раздел:s.name,Наименование:i.name,Единица:i.unit,Количество:i.quantity,'Цена работ':i.priceWork,'Цена мат.':i.priceMaterial,Сумма:Number(i.quantity||0)*(Number(i.priceWork||0)+Number(i.priceMaterial||0))}))),selectedEstimate.name)} style={btnG}><Download size={14}/>Excel</button>
                  <button onClick={async()=>{
                    const res=await fetch(API+'/estimates/'+selectedEstimate.id+'/toggle-template',{method:'PUT'});
                    const data=await res.json();
                    setEstimatesList(prev=>prev.map(e=>e.id===selectedEstimate.id?{...e,isTemplate:data.isTemplate}:e));
                    setSelectedEstimate(prev=>({...prev,isTemplate:data.isTemplate}));
                    alert(data.isTemplate?'Смета помечена как шаблон — её можно использовать при создании новых смет':'Смета больше не шаблон');
                  }} style={selectedEstimate.isTemplate?{...btnO,backgroundColor:'#facc15',color:'#1f2937'}:btnG}>⭐ {selectedEstimate.isTemplate?'Шаблон':'В шаблон'}</button>
                  <button onClick={async()=>{
                    try{
                      const versions=await fetch(API+'/estimates/'+selectedEstimate.id+'/versions').then(r=>r.json());
                      setEstimateVersions(Array.isArray(versions)?versions:[]);
                      setSelectedVersionsToCompare([]);
                      setShowVersionHistory(true);
                    }catch(e){alert('Не удалось загрузить историю');}
                  }} style={btnG}>📜 История</button>
                  <button onClick={async()=>{
                    try{
                      const h=await fetch(API+'/estimates/'+selectedEstimate.id+'/chat-history').then(r=>r.json());
                      setEstimateChatMessages(Array.isArray(h)?h:[]);
                    }catch(e){setEstimateChatMessages([]);}
                    setShowEstimateChat(true);
                  }} style={{...btnB,backgroundColor:'#0ea5e9'}}><MessageSquare size={14}/>Чат</button>
                  <button onClick={()=>{
                    setDistributeAssignments({});
                    const existing=brigadeContracts.filter(bc=>bc.projectName===selectedEstimate.projectName);
                    setDistributeBrigades(existing.length?existing.map(bc=>({name:bc.brigadeName,contractorType:bc.contractorType,pricelistId:bc.pricelistId||''})):[]);
                    setShowDistribute(true);
                  }} style={{...btnO,backgroundColor:'#16a34a'}}><Users size={14}/>👷 Распределить</button>
                  <button onClick={async()=>{
                    let plMap={};
                    const proj=projects.find(p=>p.id===Number(selectedEstimate.projectId));
                    if(proj&&proj.pricelistId){
                      try{
                        const pli=await fetch(API+'/pricelists/'+proj.pricelistId+'/items').then(r=>r.json());
                        (pli||[]).forEach(p=>{const k=(p.name||'').toLowerCase().trim();if(k) plMap[k]=Number(p.price||0);});
                      }catch(e){}
                    }
                    const allItems=(selectedEstimate.sections||[]).flatMap(s=>(s.items||[]).map(i=>{
                      const work=Number(i.priceWork||0);
                      const mat=Number(i.priceMaterial||0);
                      const qty=Number(i.quantity||0);
                      const sum=i.isImported?work:qty*(work+mat);
                      let plPrice=0,diff=0;
                      if(Object.keys(plMap).length){
                        const k=(i.name||'').toLowerCase().trim();
                        plPrice=plMap[k]||0;
                        if(!plPrice){const f=Object.keys(plMap).find(pk=>pk.length>5&&(k.includes(pk)||pk.includes(k)));if(f) plPrice=plMap[f];}
                        if(plPrice&&(work+mat)>0){diff=Math.round(((work+mat)/plPrice-1)*100);}
                      }
                      return {section:s.name,name:i.name,unit:i.unit,qty,work,mat,sum,plPrice,diff};
                    }));
                    const total=allItems.reduce((s,i)=>s+i.sum,0);
                    const top5=[...allItems].sort((a,b)=>b.sum-a.sum).slice(0,5);
                    const bySection={};
                    allItems.forEach(i=>{bySection[i.section]=(bySection[i.section]||0)+i.sum;});
                    const shares=Object.entries(bySection).map(([n,s])=>({name:n,sum:s,share:total>0?Math.round(s/total*100):0})).sort((a,b)=>b.sum-a.sum);
                    const fmt=(n)=>Number(n||0).toLocaleString('ru-RU');
                    const prompt='Ты эксперт по строительным сметам. Анализируешь смету "'+selectedEstimate.name+'" на '+fmt(total)+' ₽.\n\n'
                      +'РАЗДЕЛЫ ('+shares.length+'):\n'+shares.map(s=>'• '+s.name+': '+fmt(s.sum)+' ₽ ('+s.share+'%)').join('\n')+'\n\n'
                      +'ТОП-5 ДОРОГИХ ПОЗИЦИЙ:\n'+top5.map((i,n)=>(n+1)+'. ['+i.section+'] '+i.name+': '+i.qty+' '+i.unit+', '+fmt(i.sum)+' ₽ ('+(total>0?Math.round(i.sum/total*100):0)+'%)'+(i.plPrice?', прайс '+fmt(i.plPrice)+'₽ → '+(i.diff>0?'+':'')+i.diff+'%':'')).join('\n')+'\n\n'
                      +'ВСЕ ПОЗИЦИИ:\n'+allItems.map(i=>'- ['+i.section+'] '+i.name+' | '+i.qty+' '+i.unit+' | '+fmt(i.sum)+'₽'+(i.plPrice?' (прайс '+fmt(i.plPrice)+'₽, '+(i.diff>0?'+':'')+i.diff+'%)':'')).join('\n')+'\n\n'
                      +'ОТВЕТЬ СТРОГО В ФОРМАТЕ JSON (без markdown, без ```, только сырой JSON):\n'
                      +'{\n'
                      +'  "top": [{"name":"название позиции","section":"раздел","sum":число,"share":процент,"why":"почему дорого"}],\n'
                      +'  "sections": [{"name":"полное название раздела","sum":число,"share":процент,"summary":"что в разделе","note":"на что обратить внимание или норма"}],\n'
                      +'  "risks": [{"where":"конкретная позиция или раздел","problem":"что не так","impact":число_или_0}],\n'
                      +'  "actions": [{"do":"конкретное действие","target":"что/где менять","savings":число_или_0}]\n'
                      +'}\n\n'
                      +'ПРАВИЛА:\n'
                      +'• top — 5 позиций из ТОП-5 выше, цифры из данных точно.\n'
                      +'• sections — ОБЯЗАТЕЛЬНО по КАЖДОМУ из '+shares.length+' разделов (не пропускай ни один). Для каждого: summary одной фразой (например "штукатурка, шпатлёвка, окраска"), note — что важного увидел (отклонения, странные объёмы) или просто "норма".\n'
                      +'• risks — позиции с отклонением от прайса >20%, странные объёмы, возможные дубли, забытые сопутствующие работы. Минимум 0, максимум 7. Если ничего — [].\n'
                      +'• actions — 3-6 КОНКРЕТНЫХ шагов с привязкой к позиции или разделу. НЕ "найти поставщиков", а "заменить X на Y в позиции Z". savings — оценка экономии в рублях или 0.\n'
                      +'• Все числа — без пробелов, без "руб", только цифры. 1260000 а не "1 260 000 руб".\n'
                      +'• Только валидный JSON. Никакого текста до или после.';
                    setShowAiChat(true);
                    setAiMessages([{role:'user',content:'Анализ сметы: '+selectedEstimate.name}]);
                    setAiLoading(true);
                    try{
                      const res=await fetch(API+'/ai-chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:[{role:'user',content:prompt}],jsonOnly:true})});
                      const data=await res.json();
                      const raw=(data.response||data.error||'').trim();
                      let parsed=null;
                      try{
                        const clean=raw.replace(/^```(?:json)?/i,'').replace(/```$/,'').trim();
                        const start=clean.indexOf('{'),end=clean.lastIndexOf('}');
                        if(start>=0&&end>start) parsed=JSON.parse(clean.slice(start,end+1));
                      }catch(e){}
                      let out;
                      if(parsed&&(parsed.top||parsed.sections||parsed.risks||parsed.actions)){
                        const lines=[];
                        lines.push('💰 Общая сумма: '+fmt(total)+' ₽');
                        lines.push('');
                        if(Array.isArray(parsed.top)&&parsed.top.length){
                          lines.push('🔝 ТОП ДОРОГИХ ПОЗИЦИЙ');
                          parsed.top.forEach((t,n)=>{lines.push((n+1)+'. '+(t.name||'?')+(t.section?' ['+t.section+']':''));lines.push('   '+fmt(t.sum)+' ₽'+(t.share?' ('+t.share+'%)':'')+(t.why?' — '+t.why:''));});
                          lines.push('');
                        }
                        if(Array.isArray(parsed.sections)&&parsed.sections.length){
                          lines.push('📊 ПО РАЗДЕЛАМ');
                          parsed.sections.forEach((s,n)=>{
                            lines.push((n+1)+'. '+(s.name||'?')+' — '+fmt(s.sum)+' ₽'+(s.share?' ('+s.share+'%)':''));
                            if(s.summary) lines.push('   '+s.summary);
                            if(s.note&&s.note.toLowerCase()!=='норма') lines.push('   ⚡ '+s.note);
                          });
                          lines.push('');
                        }
                        if(Array.isArray(parsed.risks)&&parsed.risks.length){
                          lines.push('⚠️ РИСКИ');
                          parsed.risks.forEach((r,n)=>{lines.push((n+1)+'. '+(r.where||'?')+': '+(r.problem||'')+(r.impact?' (~'+fmt(r.impact)+' ₽)':''));});
                          lines.push('');
                        }else{
                          lines.push('✅ Явных рисков не выявлено');
                          lines.push('');
                        }
                        if(Array.isArray(parsed.actions)&&parsed.actions.length){
                          lines.push('🎯 ЧТО СДЕЛАТЬ');
                          parsed.actions.forEach((a,n)=>{lines.push((n+1)+'. '+(a.do||'?')+(a.target?' → '+a.target:'')+(a.savings?' (экономия ~'+fmt(a.savings)+' ₽)':''));});
                        }
                        out=lines.join('\n');
                      }else{
                        out=raw||'Ошибка: пустой ответ от ИИ';
                      }
                      setAiMessages([{role:'user',content:'Анализ сметы: '+selectedEstimate.name},{role:'assistant',content:out}]);
                    }catch(e){setAiMessages(prev=>[...prev,{role:'assistant',content:'Ошибка соединения'}]);}
                    setAiLoading(false);
                  }} style={{...btnB,backgroundColor:'#10b981'}}><Bot size={14}/>ИИ Анализ</button>
                </div>
                <div style={{...card,padding:'16px',marginBottom:'16px'}}>
                  <div style={{display:'flex',gap:'8px',marginBottom:'10px',alignItems:'center'}}>
                    <input placeholder="Новый раздел" value={newEstimateSection.name} onChange={e=>setNewEstimateSection({name:e.target.value})} style={{...inp,marginBottom:0,flex:1}}/>
                    <button onClick={()=>{if(!newEstimateSection.name) return;const section={id:Date.now(),name:newEstimateSection.name,items:[]};const updated={...selectedEstimate,sections:[...(selectedEstimate.sections||[]),section]};setSelectedEstimate(updated);setEstimatesList(prev=>prev.map(e=>e.id===updated.id?updated:e));setNewEstimateSection({name:''});}} style={btnO}><Plus size={14}/>Раздел</button>
                  </div>
                </div>
                {(selectedEstimate.sections||[]).map((section,si)=>{
                  const itemKind=(it)=>it.itemType||(Number(it.priceMaterial||0)>0&&Number(it.priceWork||0)===0?'material':'work');
                  const sumOf=(it)=>it.isImported?Number(it.priceWork||0)+Number(it.priceMaterial||0):Number(it.quantity||0)*(Number(it.priceWork||0)+Number(it.priceMaterial||0));
                  const allItems=section.items||[];
                  const works=allItems.map((i,idx)=>({...i,_idx:idx})).filter(i=>itemKind(i)==='work');
                  const mats=allItems.map((i,idx)=>({...i,_idx:idx})).filter(i=>itemKind(i)==='material');
                  const total=allItems.reduce((s,i)=>s+sumOf(i),0);
                  const totalW=works.reduce((s,i)=>s+sumOf(i),0);
                  const totalM=mats.reduce((s,i)=>s+sumOf(i),0);
                  const removeAt=(idx)=>{const sections=(selectedEstimate.sections||[]).map((s,sidx)=>sidx===si?{...s,items:(s.items||[]).filter((_,i)=>i!==idx)}:s);const updated={...selectedEstimate,sections};setSelectedEstimate(updated);setEstimatesList(prev=>prev.map(e=>e.id===updated.id?updated:e));persistEstimate(updated);};
                  const updateItem=(idx,field,val)=>{const sections=(selectedEstimate.sections||[]).map((s,sidx)=>sidx===si?{...s,items:(s.items||[]).map((it,i)=>i===idx?{...it,[field]:val,isImported:field==='quantity'||field==='priceWork'||field==='priceMaterial'?false:it.isImported}:it)}:s);const updated={...selectedEstimate,sections};setSelectedEstimate(updated);setEstimatesList(prev=>prev.map(e=>e.id===updated.id?updated:e));};
                  const persist=()=>persistEstimate(selectedEstimate);
                  const inpCell={padding:'4px 6px',border:'1px solid '+C.border,borderRadius:'4px',fontSize:'11px',width:'100%',backgroundColor:C.bgWhite,outline:'none'};
                  const projBrigades=brigadeContracts.filter(bc=>bc.projectName===selectedEstimate.projectName).map(bc=>bc.brigadeName).filter(Boolean);
                  const renderGroup=(title,emoji,list,groupTotal,accent)=>(<div style={{marginBottom:'10px'}}>
                    <div style={{padding:'6px 10px',backgroundColor:accent+'15',borderRadius:'6px',display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'4px',borderLeft:'3px solid '+accent}}>
                      <b style={{color:accent,fontSize:'12px'}}>{emoji+' '+title+' ('+list.length+')'}</b>
                      <b style={{color:accent,fontSize:'12px'}}>{groupTotal.toLocaleString('ru-RU')+' ₽'}</b>
                    </div>
                    {list.length>0?(<table style={tbl}><thead><tr>
                      <th style={tblH}>Наименование</th>
                      <th style={{...tblH,width:'60px'}}>Ед.</th>
                      <th style={{...tblH,width:'70px'}}>План</th>
                      <th style={{...tblH,width:'90px'}}>👷 Кому</th>
                      <th style={{...tblH,width:'70px'}}>✅ Сделано</th>
                      <th style={{...tblH,width:'70px'}}>📉 Осталось</th>
                      <th style={{...tblH,width:'90px'}}>Цена</th>
                      <th style={tblH}>Сумма</th>
                      <th style={{...tblH,width:'36px'}}></th>
                    </tr></thead><tbody>
                      {list.map(item=>{const qty=Number(item.quantity)||0;const done=Number(item.doneQuantity)||0;const remain=Math.max(0,qty-done);return(<tr key={item.id||item._idx}>
                        <td style={tblC}><div style={{display:'flex',alignItems:'center',gap:'4px'}}><button onClick={()=>{updateItem(item._idx,'hiddenWork',!item.hiddenWork);setTimeout(persist,100);}} title={item.hiddenWork?'Скрытая работа (для акта)':'Обычная работа'} style={{border:'none',background:'none',cursor:'pointer',padding:'0 2px',fontSize:'13px',opacity:item.hiddenWork?1:0.3}}>{item.hiddenWork?'🔒':'🔓'}</button><input value={item.name||''} onChange={e=>updateItem(item._idx,'name',e.target.value)} onBlur={persist} style={inpCell}/></div></td>
                        <td style={tblC}><select value={item.unit||'шт'} onChange={e=>{updateItem(item._idx,'unit',e.target.value);setTimeout(persist,100);}} style={inpCell}>{UNITS.map(u=><option key={u}>{u}</option>)}</select></td>
                        <td style={tblC}><input type='number' value={item.quantity||''} onChange={e=>updateItem(item._idx,'quantity',e.target.value)} onBlur={persist} style={inpCell}/></td>
                        <td style={tblC}><select value={item.brigadeName||''} onChange={e=>{updateItem(item._idx,'brigadeName',e.target.value);setTimeout(persist,100);}} style={inpCell}><option value=''>—</option>{projBrigades.map(b=><option key={b} value={b}>{b}</option>)}</select></td>
                        <td style={tblC}><input type='number' value={item.doneQuantity||''} onChange={e=>{const raw=Number(e.target.value);if(qty>0&&raw>qty){alert('Сделано не может быть больше плана ('+qty+' '+item.unit+')');return;}updateItem(item._idx,'doneQuantity',raw);}} onBlur={persist} style={{...inpCell,color:done>0?C.success:C.text}}/></td>
                        <td style={{...tblC,color:qty>0&&remain===0?C.success:remain>0?C.warning:C.textMuted,fontWeight:'600',fontSize:'11px'}}>{qty>0?remain+' '+item.unit:'—'}</td>
                        <td style={tblC}><input type='number' value={item.priceWork||item.priceMaterial||''} onChange={e=>{const v=e.target.value;if(itemKind(item)==='material')updateItem(item._idx,'priceMaterial',v);else updateItem(item._idx,'priceWork',v);}} onBlur={persist} style={inpCell}/></td>
                        <td style={{...tblC,fontWeight:'600',color:C.success}}>{sumOf(item).toLocaleString('ru-RU')+' ₽'}</td>
                        <td style={tblC}><button onClick={()=>removeAt(item._idx)} style={{...btnR,padding:'3px 7px'}}><Trash2 size={11}/></button></td>
                      </tr>);})}
                    </tbody></table>):(<p style={{fontSize:'11px',color:C.textMuted,padding:'6px 10px'}}>Нет позиций</p>)}
                  </div>);
                  return(<div key={section.id} style={{...card,marginBottom:'12px'}}>
                  <div style={{padding:'12px 16px',backgroundColor:C.bg,display:'flex',justifyContent:'space-between',alignItems:'center',borderBottom:'1.5px solid '+C.border}}>
                    <b style={{color:C.accent,fontSize:'13px'}}>{'📁 '+section.name}</b>
                    <b style={{color:C.text,fontSize:'13px'}}>{total.toLocaleString('ru-RU')+' ₽'}</b>
                  </div>
                  <div style={{padding:'12px 16px'}}>
                    {renderGroup('Работы','🔨',works,totalW,C.accent)}
                    {renderGroup('Материалы','📦',mats,totalM,C.info)}
                    <div style={{display:'grid',gridTemplateColumns:'3fr 1fr 1fr 1fr 1fr auto',gap:'6px',marginTop:'10px',alignItems:'center'}}>
                      <input placeholder="Наименование работы *" value={newEstimateItem.sectionId===section.id?newEstimateItem.name:''} onChange={e=>setNewEstimateItem({...newEstimateItem,sectionId:section.id,name:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                      <select value={newEstimateItem.sectionId===section.id?newEstimateItem.unit:'м2'} onChange={e=>setNewEstimateItem({...newEstimateItem,sectionId:section.id,unit:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>{UNITS.map(u=><option key={u}>{u}</option>)}</select>
                      <input placeholder="Кол-во" type="number" value={newEstimateItem.sectionId===section.id?newEstimateItem.quantity:''} onChange={e=>setNewEstimateItem({...newEstimateItem,sectionId:section.id,quantity:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                      <input placeholder="Цена работ" type="number" value={newEstimateItem.sectionId===section.id?newEstimateItem.priceWork:''} onChange={e=>setNewEstimateItem({...newEstimateItem,sectionId:section.id,priceWork:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                      <input placeholder="Цена мат." type="number" value={newEstimateItem.sectionId===section.id?newEstimateItem.priceMaterial:''} onChange={e=>setNewEstimateItem({...newEstimateItem,sectionId:section.id,priceMaterial:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                      <button onClick={()=>{if(!newEstimateItem.name||newEstimateItem.sectionId!==section.id) return;const item={id:Date.now(),name:newEstimateItem.name,unit:newEstimateItem.unit,quantity:newEstimateItem.quantity,priceWork:newEstimateItem.priceWork,priceMaterial:newEstimateItem.priceMaterial};const sections=(selectedEstimate.sections||[]).map((s,idx)=>idx===si?{...s,items:[...(s.items||[]),item]}:s);const updated={...selectedEstimate,sections};setSelectedEstimate(updated);setEstimatesList(prev=>prev.map(e=>e.id===updated.id?updated:e));setNewEstimateItem({sectionId:'',name:'',unit:'м2',quantity:'',priceWork:'',priceMaterial:''});}} style={{...btnO,padding:'7px 12px'}}><Plus size={13}/></button>
                    </div>
                  </div>
                </div>);})}
                <div style={{...card,padding:'16px',backgroundColor:C.accentLight,border:'1.5px solid '+C.accentBorder}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                    <b style={{color:C.text,fontSize:'14px'}}>ИТОГО по смете:</b>
                    <b style={{color:C.accent,fontSize:'18px'}}>{(selectedEstimate.sections||[]).flatMap(s=>s.items||[]).reduce((sum,i)=>sum+(i.isImported?Number(i.priceWork||0):Number(i.quantity||0)*(Number(i.priceWork||0)+Number(i.priceMaterial||0))),0).toLocaleString()+' ₽'}</b>
                  </div>
                </div>
              </div>):(<div>
                {estimatesList.map(est=>(<div key={est.id} style={{...card,padding:'14px',marginBottom:'8px',display:'flex',justifyContent:'space-between',alignItems:'center'}}><div style={{flex:1,cursor:'pointer'}} onClick={()=>setSelectedEstimate(est)}><b style={{color:C.text,fontSize:'13px'}}>{est.name}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{(est.projectName||'')+(est.version?' · v'+est.version:'')+(est.smetaType?' · '+est.smetaType:'')}</p></div><div style={{display:'flex',gap:'6px',alignItems:'center'}}><b style={{color:C.success,fontSize:'13px'}}>{(est.sections||[]).flatMap(s=>s.items||[]).reduce((sum,i)=>sum+(i.isImported?Number(i.priceWork||0):Number(i.quantity||0)*(Number(i.priceWork||0)+Number(i.priceMaterial||0))),0).toLocaleString()+' ₽'}</b><ChevronRight size={16} color={C.textMuted} style={{cursor:'pointer'}} onClick={()=>setSelectedEstimate(est)}/><button onClick={e=>{e.stopPropagation();if(window.confirm('Удалить смету?')){fetch(API+'/estimates/'+est.id,{method:'DELETE'});setEstimatesList(prev=>prev.filter(e=>e.id!==est.id));}}} style={{...btnR,padding:'4px 8px'}}><Trash2 size={11}/></button></div></div>))}
                {estimatesList.length===0&&<div style={{...card,padding:'40px',textAlign:'center',color:C.textMuted}}><Calculator size={48} style={{marginBottom:'15px',opacity:0.3}}/><p>Смет нет — создайте первую!</p></div>}
              </div>)}
            </div>)}

            {estimatesTab==='import'&&(<div>
              <h3 style={{color:C.text,marginBottom:'15px',fontSize:'15px',fontWeight:'700'}}>Импорт из Гранд Смета (Excel)</h3>
              <div style={{...card,padding:'20px',marginBottom:'20px'}}>
                <p style={{color:C.textSec,fontSize:'13px',marginBottom:'15px'}}>Загрузите Excel файл из Гранд Сметы — система автоматически распознает разделы и позиции.</p>
                <select value={newEstimate.projectId} onChange={e=>{const p=projects.find(pr=>pr.id===Number(e.target.value));setNewEstimate({...newEstimate,projectId:e.target.value,projectName:p?p.name:'',name:p?'Смета — '+p.name:''});}} style={{...inp,maxWidth:'400px'}}>
                  <option value="">Привязать к проекту (необязательно)</option>
                  {projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
                <select value={newEstimate.smetaType} onChange={e=>setNewEstimate({...newEstimate,smetaType:e.target.value})} style={{...inp,maxWidth:'400px'}}>
                  <option value="Заказчик">📋 Смета заказчика (полная ЛСР)</option>
                  <option value="Работы">👷 Смета работ (для бригады)</option>
                  <option value="Материалы">📦 Смета материалов (для закупки)</option>
                </select>
                <label style={{display:'inline-flex',alignItems:'center',gap:'10px',cursor:'pointer',backgroundColor:C.accentLight,padding:'14px 24px',borderRadius:'10px',border:'1.5px dashed '+C.accent,fontSize:'14px',color:C.accent,fontWeight:'600'}}>
                  <Upload size={20}/>Загрузить Excel файл (.xlsx)
                  <input type="file" accept=".xlsx,.xls" style={{display:'none'}} onChange={async e=>{
                    if(!e.target.files[0]) return;
                    if(!newEstimate.projectId){alert('Сначала выберите проект — без привязки смета не сохранится');e.target.value='';return;}
                    const fd=new FormData();
                    fd.append('file',e.target.files[0]);
                    try {
                      const res=await fetch(API+'/parse-smeta',{method:'POST',body:fd});
                      const data=await res.json();
                      if(data.error){alert('Ошибка: '+data.error);return;}
                      const sections={};
                      (data.items||[]).forEach(item=>{
                        if(!sections[item.section]) sections[item.section]={id:Date.now()+Math.random(),name:item.section,items:[]};
                        const tw=Number(item.totalWork||0);
                        const tm=Number(item.totalMaterial||0);
                        sections[item.section].items.push({id:Date.now()+Math.random(),name:item.name,unit:item.unit,quantity:item.quantity,priceWork:tw>0||tm===0?(tw||item.total):0,priceMaterial:tm>0?tm:0,isImported:true,itemType:item.type||'work'});
                      });
                      const projName=newEstimate.projectName||(projects.find(p=>p.id===Number(newEstimate.projectId))?.name||'');const fileName=e.target.files[0].name.replace('.xlsx','').replace('.xls','');const est={id:Date.now(),name:fileName||newEstimate.name||'Смета — '+projName,projectId:newEstimate.projectId,projectName:projName,version:'1.0',sections:Object.values(sections)};
                      const saveRes=await fetch(API+'/estimates',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(est)});const saved=await saveRes.json();const estWithId={...est,id:saved.id,smetaType:newEstimate.smetaType||'Заказчик'};setEstimatesList(prev=>[...prev,estWithId]);setSelectedEstimate(estWithId);setEstimatesTab('list');
                      setImportValidating(true);
                      setImportValidationWarnings([]);
                      try{
                        const items=Object.values(sections).flatMap(s=>(s.items||[]).map(i=>({section:s.name,name:i.name,unit:i.unit,qty:Number(i.quantity||0)})));
                        const valPrompt='Проверь смету "'+est.name+'" на типовые проблемы при импорте из Гранд Сметы. Позиции:\n'+JSON.stringify(items,null,1)+'\n\nИЩИ:\n- Забытые сопутствующие работы (например штукатурка без грунтовки)\n- Возможные дубликаты позиций\n- Подозрительно большие или маленькие объёмы\n- Странные единицы измерения\n\nОТВЕТЬ СТРОГО JSON:\n{"warnings":[{"type":"забыто|дубль|объём|единица|другое","where":"раздел или позиция","message":"что не так","severity":"критично|внимание|совет"}]}\nЕсли всё хорошо — пиши {"warnings":[]}. Только JSON.';
                        const r=await fetch(API+'/ai-chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:[{role:'user',content:valPrompt}],jsonOnly:true})});
                        const d=await r.json();
                        const raw=(d.response||'').trim();
                        const clean=raw.replace(/^```(?:json)?/i,'').replace(/```$/,'').trim();
                        const s=clean.indexOf('{'),en=clean.lastIndexOf('}');
                        if(s>=0&&en>s){const p=JSON.parse(clean.slice(s,en+1));if(Array.isArray(p.warnings))setImportValidationWarnings(p.warnings);}
                      }catch(err){}
                      setImportValidating(false);
                      alert('Импортировано '+data.count+' позиций! ИИ проверяет смету в фоне — результат появится сверху.');
                    } catch(err){alert('Ошибка импорта');}
                  }}/>
                </label>
                <div style={{marginTop:'20px',padding:'15px',backgroundColor:C.bg,borderRadius:'10px',border:'1.5px solid '+C.border}}>
                  <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'8px'}}>📋 Поддерживаемый формат:</b>
                  <p style={{color:C.textSec,fontSize:'12px',margin:'3px 0'}}>✅ Гранд Смета версии 2024-2025</p>
                  <p style={{color:C.textSec,fontSize:'12px',margin:'3px 0'}}>✅ Разделы и подразделы</p>
                  <p style={{color:C.textSec,fontSize:'12px',margin:'3px 0'}}>✅ Наименование, единица, количество, стоимость</p>
                  <p style={{color:C.textSec,fontSize:'12px',margin:'3px 0'}}>✅ До 5000+ позиций</p>
                </div>
              </div>
            </div>)}
          </div>)}

          {activePage==='weather'&&(<div>
            <div style={{display:'flex',gap:'8px',marginBottom:'20px',flexWrap:'wrap'}}>
              {['log','jpr'].map(tab=>(<button key={tab} onClick={()=>setWeatherTab(tab)} style={{...weatherTab===tab?btnO:btnG,fontSize:'12px',padding:'7px 14px'}}>{{log:'Журнал погоды',jpr:'ЖПР'}[tab]}</button>))}
            </div>

            {weatherTab==='log'&&(<div>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Журнал погоды</b>
                <button onClick={()=>setShowForm(!showForm)} style={btnO}><Plus size={14}/>Добавить запись</button>
              </div>
              {showForm&&(<div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                  <select value={newWeather.projectName} onChange={e=>setNewWeather({...newWeather,projectName:e.target.value})} style={{...inp,marginBottom:0}}><option value="">Выберите объект *</option>{projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}</select>
                  <input type="date" value={newWeather.date} onChange={e=>setNewWeather({...newWeather,date:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <select value={newWeather.condition} onChange={e=>setNewWeather({...newWeather,condition:e.target.value})} style={{...inp,marginBottom:0}}>{WEATHER_CONDITIONS.map(w=><option key={w}>{w}</option>)}</select>
                  <input placeholder="Температура (°C)" type="number" value={newWeather.temperature} onChange={e=>setNewWeather({...newWeather,temperature:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input placeholder="Скорость ветра (м/с)" type="number" value={newWeather.windSpeed} onChange={e=>setNewWeather({...newWeather,windSpeed:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input placeholder="Примечание" value={newWeather.notes} onChange={e=>setNewWeather({...newWeather,notes:e.target.value})} style={{...inp,marginBottom:0}}/>
                </div>
                <div style={{display:'flex',gap:'8px',marginTop:'12px'}}><button onClick={()=>{saveWeather();setShowForm(false);}} style={btnO}><Check size={14}/>Сохранить</button><button onClick={()=>setShowForm(false)} style={btnG}><X size={14}/>Отмена</button></div>
              </div>)}
              {projects.map(p=>{
                const pWeather=weatherLog.filter(w=>w.projectName===p.name).sort((a,b)=>b.date.localeCompare(a.date));
                if(pWeather.length===0) return null;
                return(<div key={p.id} style={{...card,marginBottom:'12px'}}>
                  <div style={{padding:'12px 16px',backgroundColor:C.bg,borderBottom:'1.5px solid '+C.border}}><b style={{color:C.text,fontSize:'13px'}}>{'📍 '+p.name}</b></div>
                  <div style={{padding:'12px 16px'}}>
                    {pWeather.map(w=>(<div key={w.id} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'8px 0',borderBottom:'1px solid '+C.border}}>
                      <div><b style={{fontSize:'13px',color:C.text}}>{w.date}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{w.condition+' · '+w.temperature+'°C · Ветер: '+w.windSpeed+' м/с'+(w.notes?' · '+w.notes:'')}</p></div>
                      <span style={{fontSize:'24px'}}>{{Ясно:'☀️',Облачно:'⛅',Пасмурно:'☁️',Дождь:'🌧️',Снег:'❄️',Гроза:'⛈️',Туман:'🌫️',Ветер:'💨'}[w.condition]||'🌤️'}</span>
                    </div>))}
                  </div>
                </div>);
              })}
              {weatherLog.length===0&&<div style={{...card,padding:'40px',textAlign:'center',color:C.textMuted}}><CloudSun size={48} style={{marginBottom:'15px',opacity:0.3}}/><p>Записей нет</p></div>}
            </div>)}

            {weatherTab==='jpr'&&(<div>
              <h3 style={{color:C.text,marginBottom:'15px',fontSize:'15px',fontWeight:'700'}}>Журнал производства работ</h3>
              {projects.map(p=>{const works=workJournal.filter(j=>j.project===p.name&&j.status==='Подтверждено');if(works.length===0) return null;return(<div key={p.id} style={{...card,padding:'14px',marginBottom:'10px',display:'flex',justifyContent:'space-between',alignItems:'center'}}><div><b style={{color:C.text,fontSize:'13px'}}>{p.name}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{works.length+' работ · '+works.reduce((s,w)=>s+(w.total||0),0).toLocaleString()+' ₽'}</p></div><button onClick={()=>showPreview(buildJPRContent(p.name),'ЖПР — '+p.name)} style={btnB}><ScrollText size={14}/>ЖПР</button></div>);})}
              {projects.every(p=>workJournal.filter(j=>j.project===p.name&&j.status==='Подтверждено').length===0)&&<div style={{...card,padding:'40px',textAlign:'center',color:C.textMuted}}>Подтверждённых работ нет</div>}
            </div>)}
          </div>)}

          {activePage==='settings'&&isFinanceRole()&&(<div>
            <div style={{display:'flex',gap:'8px',marginBottom:'20px',flexWrap:'wrap'}}>
              {['requisites','documents'].map(tab=>(<button key={tab} onClick={()=>setSettingsTab(tab)} style={{...settingsTab===tab?btnO:btnG,fontSize:'12px',padding:'7px 14px'}}>{{requisites:'Реквизиты компании',documents:'Юр. документы'}[tab]}</button>))}
            </div>

            {settingsTab==='requisites'&&(<div>
              <div style={{...card,padding:'24px',marginBottom:'20px'}}>
                <h3 style={{color:C.text,marginBottom:'20px',fontWeight:'700',fontSize:'16px'}}>🏢 Реквизиты организации</h3>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'12px'}}>
                  <input placeholder="Полное название организации" value={companyReqForm.fullName} onChange={e=>setCompanyReqForm({...companyReqForm,fullName:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                  <input placeholder="Краткое название" value={companyReqForm.shortName} onChange={e=>setCompanyReqForm({...companyReqForm,shortName:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input placeholder="ИНН" value={companyReqForm.inn} onChange={e=>setCompanyReqForm({...companyReqForm,inn:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input placeholder="КПП" value={companyReqForm.kpp} onChange={e=>setCompanyReqForm({...companyReqForm,kpp:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input placeholder="ОГРН" value={companyReqForm.ogrn} onChange={e=>setCompanyReqForm({...companyReqForm,ogrn:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input placeholder="Юридический адрес" value={companyReqForm.legalAddress} onChange={e=>setCompanyReqForm({...companyReqForm,legalAddress:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                  <input placeholder="Фактический адрес" value={companyReqForm.actualAddress} onChange={e=>setCompanyReqForm({...companyReqForm,actualAddress:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                  <input placeholder="Телефон" value={companyReqForm.phone} onChange={e=>setCompanyReqForm({...companyReqForm,phone:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <input placeholder="Email" value={companyReqForm.email} onChange={e=>setCompanyReqForm({...companyReqForm,email:e.target.value})} style={{...inp,marginBottom:0}}/>
                </div>
                <div style={{borderTop:'1.5px solid '+C.border,marginTop:'20px',paddingTop:'20px'}}>
                  <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>Руководство</b>
                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'12px'}}>
                    <input placeholder="ФИО директора" value={companyReqForm.directorName} onChange={e=>setCompanyReqForm({...companyReqForm,directorName:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder="Должность" value={companyReqForm.directorPosition} onChange={e=>setCompanyReqForm({...companyReqForm,directorPosition:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder="Действует на основании" value={companyReqForm.basis} onChange={e=>setCompanyReqForm({...companyReqForm,basis:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                  </div>
                </div>
                <div style={{borderTop:'1.5px solid '+C.border,marginTop:'20px',paddingTop:'20px'}}>
                  <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>Банковские реквизиты</b>
                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'12px'}}>
                    <input placeholder="Банк" value={companyReqForm.bankName} onChange={e=>setCompanyReqForm({...companyReqForm,bankName:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                    <input placeholder="БИК" value={companyReqForm.bik} onChange={e=>setCompanyReqForm({...companyReqForm,bik:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder="Расчётный счёт" value={companyReqForm.rs} onChange={e=>setCompanyReqForm({...companyReqForm,rs:e.target.value})} style={{...inp,marginBottom:0}}/>
                    <input placeholder="Корр. счёт" value={companyReqForm.ks} onChange={e=>setCompanyReqForm({...companyReqForm,ks:e.target.value})} style={{...inp,marginBottom:0}}/>
                  </div>
                </div>
                <button onClick={async()=>{await saveCompanyRequisites();setCompanyRequisites(companyReqForm);}} style={{...btnO,marginTop:'20px',padding:'12px 30px',fontSize:'15px'}}><Check size={16}/>Сохранить реквизиты</button>
              </div>
              {companyRequisites&&companyRequisites.fullName&&(<div style={{...card,padding:'20px',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder}}>
                <b style={{color:C.success,fontSize:'14px',display:'block',marginBottom:'10px'}}>✅ Реквизиты сохранены — подставляются во все документы</b>
                <p style={{color:C.text,margin:'3px 0',fontSize:'13px'}}>{companyRequisites.fullName}</p>
                <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{'ИНН: '+companyRequisites.inn+' · КПП: '+companyRequisites.kpp+' · ОГРН: '+companyRequisites.ogrn}</p>
                <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{'Директор: '+companyRequisites.directorName}</p>
                <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{'Банк: '+companyRequisites.bankName+' · Р/с: '+companyRequisites.rs}</p>
              </div>)}
            </div>)}

            {settingsTab==='documents'&&(<div>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Юридические документы</b>
                <button onClick={()=>setShowForm(!showForm)} style={btnO}><Plus size={14}/>Добавить документ</button>
              </div>
              {showForm&&(<div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                  <input placeholder="Название документа *" value={newCompanyDoc.name} onChange={e=>setNewCompanyDoc({...newCompanyDoc,name:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <select value={newCompanyDoc.docType} onChange={e=>setNewCompanyDoc({...newCompanyDoc,docType:e.target.value})} style={{...inp,marginBottom:0}}>{['Устав','ОГРН','ИНН','Выписка ЕГРЮЛ','Лицензия СРО','Доверенность','Прочее'].map(t=><option key={t}>{t}</option>)}</select>
                  <input type="date" placeholder="Срок действия" value={newCompanyDoc.expiresAt} onChange={e=>setNewCompanyDoc({...newCompanyDoc,expiresAt:e.target.value})} style={{...inp,marginBottom:0}}/>
                  <label style={{cursor:'pointer',backgroundColor:C.infoLight,padding:'10px',borderRadius:'8px',fontSize:'13px',color:C.info,border:'1.5px solid '+C.infoBorder,display:'flex',alignItems:'center',gap:'8px'}}><Upload size={14}/>Загрузить файл<input type="file" accept="image/*,application/pdf" style={{display:'none'}} onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0]);setNewCompanyDoc(prev=>({...prev,fileUrl:url}));}}} /></label>
                </div>
                {newCompanyDoc.fileUrl&&<p style={{color:C.success,fontSize:'12px',marginTop:'8px'}}>✅ Файл загружен</p>}
                <div style={{display:'flex',gap:'8px',marginTop:'12px'}}><button onClick={async()=>{if(!newCompanyDoc.name) return;await fetch(API+'/company-documents',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newCompanyDoc,uploadedBy:user.name})});await loadAll();setNewCompanyDoc({name:'',docType:'Устав',fileUrl:'',expiresAt:''});setShowForm(false);}} style={btnO}><Check size={14}/>Сохранить</button><button onClick={()=>setShowForm(false)} style={btnG}><X size={14}/>Отмена</button></div>
              </div>)}
              {['Устав','ОГРН','ИНН','Выписка ЕГРЮЛ','Лицензия СРО','Доверенность','Прочее'].map(docType=>{
                const docs=companyDocuments.filter(d=>d.docType===docType);
                if(docs.length===0) return null;
                return(<div key={docType} style={{marginBottom:'16px'}}>
                  <div style={{padding:'8px 12px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border,marginBottom:'8px'}}><b style={{color:C.accent,fontSize:'12px'}}>{'📄 '+docType}</b></div>
                  {docs.map(doc=>(<div key={doc.id} style={{...card,padding:'14px',marginBottom:'6px',marginLeft:'12px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                    <div><b style={{color:C.text,fontSize:'13px'}}>{doc.name}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{doc.uploadedBy+(doc.expiresAt?' · до '+doc.expiresAt:'')}</p></div>
                    <div style={{display:'flex',gap:'6px'}}>
                      {doc.fileUrl&&<button onClick={()=>setShowPhotoModal(doc.fileUrl)} style={btnB}><Eye size={13}/>Открыть</button>}
                      <button onClick={async()=>{await fetch(API+'/company-documents/'+doc.id,{method:'DELETE'});await loadAll();}} style={{...btnR,padding:'5px 8px'}}><Trash2 size={11}/></button>
                    </div>
                  </div>))}
                </div>);
              })}
              {companyDocuments.length===0&&<div style={{...card,padding:'40px',textAlign:'center',color:C.textMuted}}><FileText size={48} style={{marginBottom:'15px',opacity:0.3}}/><p>Документов нет — загрузите первый!</p></div>}
            </div>)}
          </div>)}

          {activePage==='analytics'&&(<div>
            <h3 style={{color:C.text,marginBottom:'20px',fontSize:'16px',fontWeight:'700'}}>Аналитика</h3>
            <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'16px',marginBottom:'24px'}}>
              {[{label:'Всего проектов',value:projects.length,icon:'📋'},{label:'В работе',value:projects.filter(p=>p.status==='В работе').length,icon:'🔨'},{label:'Завершено',value:projects.filter(p=>p.status==='Завершён').length,icon:'✅'},{label:'Сотрудников',value:staff.length,icon:'👷'},{label:'Поставщиков',value:suppliers.length,icon:'🚛'},{label:'Договоров',value:contracts.length,icon:'📄'}].map((s,i)=>(<div key={i} style={{...card,padding:'16px'}}><div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}><div><p style={{margin:'0 0 4px',color:C.textSec,fontSize:'12px'}}>{s.label}</p><b style={{fontSize:'20px',color:C.text}}>{s.value}</b></div><span style={{fontSize:'24px'}}>{s.icon}</span></div></div>))}
            </div>
            <div style={{...card,padding:'20px',marginBottom:'20px'}}>
              <h4 style={{color:C.text,marginBottom:'15px',fontSize:'14px',fontWeight:'700'}}>Расходы по проектам</h4>
              {projects.filter(p=>p.status==='В работе').map(p=>{const cat=expByCategory(p.name);const total=Object.values(cat).reduce((s,v)=>s+v,0);const pct=p.budget>0?Math.min(100,Math.round(total/p.budget*100)):0;return(<div key={p.id} style={{marginBottom:'14px'}}><div style={{display:'flex',justifyContent:'space-between',marginBottom:'5px'}}><b style={{fontSize:'13px',color:C.text}}>{p.name}</b><span style={{fontSize:'12px',color:total>p.budget?C.danger:C.textSec}}>{total.toLocaleString()+' / '+p.budget.toLocaleString()+' ₽ ('+pct+'%)'}</span></div><div style={{backgroundColor:C.bgGray,borderRadius:'6px',height:'10px'}}><div style={{backgroundColor:pct>80?C.danger:pct>60?C.warning:C.success,width:pct+'%',height:'100%',borderRadius:'6px'}}/></div></div>);})}
            </div>
            <div style={{...card,padding:'20px'}}>
              <h4 style={{color:C.text,marginBottom:'15px',fontSize:'14px',fontWeight:'700'}}>Активность журнала работ</h4>
              <table style={tbl}><thead><tr><th style={tblH}>Мастер</th><th style={tblH}>Работ</th><th style={tblH}>Сумма</th><th style={tblH}>Подтверждено</th></tr></thead><tbody>
                {[...new Set(workJournal.map(j=>j.masterName))].map(name=>{const mWorks=workJournal.filter(j=>j.masterName===name);const confirmed=mWorks.filter(j=>j.status==='Подтверждено');return(<tr key={name}><td style={tblC}>{name}</td><td style={tblC}>{mWorks.length}</td><td style={{...tblC,fontWeight:'600',color:C.success}}>{mWorks.reduce((s,w)=>s+(w.total||0),0).toLocaleString()+' ₽'}</td><td style={tblC}><span style={badge(C.success,C.successLight,C.successBorder)}>{confirmed.length+'/'+mWorks.length}</span></td></tr>);})}
              </tbody></table>
            </div>
          </div>)}

          {activePage==='crm'&&(<div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px'}}>
              <h3 style={{color:C.text,margin:0,fontSize:'16px',fontWeight:'700'}}>CRM — Лиды</h3>
              <button onClick={()=>{setShowForm(!showForm);setEditingItem(null);setNewLead({name:'',phone:'',email:'',source:'',budget:'',notes:'',stage:'Новый'});}} style={btnO}><Plus size={14}/>Новый лид</button>
            </div>
            {showForm&&(<div style={{...card,padding:'20px',marginBottom:'20px'}}>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                <input placeholder="Имя клиента *" value={newLead.name} onChange={e=>setNewLead({...newLead,name:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder="Телефон" value={newLead.phone} onChange={e=>setNewLead({...newLead,phone:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder="Email" value={newLead.email} onChange={e=>setNewLead({...newLead,email:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder="Источник" value={newLead.source} onChange={e=>setNewLead({...newLead,source:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder="Бюджет (₽)" type="number" value={newLead.budget} onChange={e=>setNewLead({...newLead,budget:e.target.value})} style={{...inp,marginBottom:0}}/>
                <select value={newLead.stage} onChange={e=>setNewLead({...newLead,stage:e.target.value})} style={{...inp,marginBottom:0}}>{CRM_STAGES.map(s=><option key={s}>{s}</option>)}</select>
                <textarea placeholder="Заметки" value={newLead.notes} onChange={e=>setNewLead({...newLead,notes:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2',height:'60px',resize:'vertical'}}/>
              </div>
              <div style={{display:'flex',gap:'10px',marginTop:'15px'}}><button onClick={()=>{saveLead(editingItem?{...newLead,id:editingItem.id}:newLead);setShowForm(false);setEditingItem(null);}} style={btnO}><Check size={14}/>{editingItem?'Сохранить':'Добавить'}</button><button onClick={()=>{setShowForm(false);setEditingItem(null);}} style={btnG}><X size={14}/>Отмена</button></div>
            </div>)}
            <div style={{display:'grid',gridTemplateColumns:'repeat(5,1fr)',gap:'12px',overflowX:'auto'}}>
              {CRM_STAGES.map(stage=>(<div key={stage} style={{minWidth:'200px'}}>
                <div style={{padding:'8px 12px',backgroundColor:stage==='Отказ'?C.dangerLight:stage==='Договор'?C.successLight:C.bg,borderRadius:'8px',marginBottom:'10px',border:'1.5px solid '+(stage==='Отказ'?C.dangerBorder:stage==='Договор'?C.successBorder:C.border)}}><b style={{color:stage==='Отказ'?C.danger:stage==='Договор'?C.success:C.text,fontSize:'12px'}}>{stage}</b><span style={{color:C.textSec,fontSize:'11px',marginLeft:'6px'}}>{'('+leads.filter(l=>l.stage===stage).length+')'}</span></div>
                {leads.filter(l=>l.stage===stage).map(lead=>(<div key={lead.id} style={{...card,padding:'12px',marginBottom:'8px',borderLeft:'3px solid '+C.accent}}>
                  <b style={{color:C.text,fontSize:'13px'}}>{lead.name}</b>
                  <p style={{color:C.textSec,margin:'3px 0',fontSize:'11px'}}>{lead.phone+(lead.email?' · '+lead.email:'')}</p>
                  {lead.budget&&<p style={{color:C.success,margin:'2px 0',fontSize:'12px',fontWeight:'600'}}>{Number(lead.budget).toLocaleString()+' ₽'}</p>}
                  <p style={{color:C.textMuted,margin:'2px 0',fontSize:'11px'}}>{lead.source}</p>
                  <div style={{display:'flex',gap:'4px',marginTop:'8px',flexWrap:'wrap'}}>
                    {CRM_STAGES.filter(s=>s!==stage).map(s=>(<button key={s} onClick={()=>saveLead({...lead,stage:s})} style={{padding:'2px 8px',backgroundColor:C.bg,border:'1px solid '+C.border,borderRadius:'4px',cursor:'pointer',fontSize:'10px',color:C.textSec}}>→{s}</button>))}
                    <button onClick={()=>{setEditingItem(lead);setNewLead({...lead});setShowForm(true);}} style={{...btnG,padding:'2px 6px',fontSize:'10px'}}><Edit2 size={9}/></button>
                    <button onClick={()=>deleteLead(lead.id)} style={{...btnR,padding:'2px 6px',fontSize:'10px'}}><Trash2 size={9}/></button>
                  </div>
                </div>))}
              </div>))}
            </div>
          </div>)}

          {activePage==='activitylog'&&(<div>
            <h3 style={{color:C.text,marginBottom:'20px',fontSize:'16px',fontWeight:'700'}}>Журнал активности</h3>
            <table style={tbl}><thead><tr><th style={tblH}>Действие</th><th style={tblH}>Пользователь</th><th style={tblH}>Роль</th><th style={tblH}>Время</th></tr></thead><tbody>
              {activityLog.map((e,i)=>(<tr key={i}><td style={tblC}>{e.action}</td><td style={tblC}>{e.user}</td><td style={tblC}>{ROLE_LABELS[e.role]||e.role}</td><td style={tblC}>{e.time}</td></tr>))}
            </tbody></table>
            {activityLog.length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Журнал пуст</p>}
          </div>)}

          {activePage==='companychat'&&(<div>
            <h3 style={{color:C.text,marginBottom:'20px',fontSize:'16px',fontWeight:'700'}}>Общий чат</h3>
            <div style={{...card,padding:'0',overflow:'hidden',height:'calc(100vh - 200px)',display:'flex',flexDirection:'column'}}>
              <div style={{flex:1,overflowY:'auto',padding:'20px',display:'flex',flexDirection:'column',gap:'12px',backgroundColor:C.bg}}>
                {companyMessages.length===0&&<p style={{color:C.textMuted,textAlign:'center',margin:'auto'}}>Сообщений нет</p>}
                {companyMessages.map(msg=>{const isMe=(msg.author_name||msg.author)===user.name;return(<div key={msg.id} style={{display:'flex',justifyContent:isMe?'flex-end':'flex-start',alignItems:'flex-end',gap:'8px'}}>{!isMe&&<div style={{width:'32px',height:'32px',borderRadius:'10px',backgroundColor:roleColor(msg.author_role||msg.role),display:'flex',alignItems:'center',justifyContent:'center',color:'white',fontWeight:'700',fontSize:'13px',flexShrink:0}}>{(msg.author_name||msg.author||'?').charAt(0)}</div>}<div style={{maxWidth:'70%'}}>{!isMe&&<div style={{fontSize:'11px',fontWeight:'700',color:roleColor(msg.author_role||msg.role),marginBottom:'4px'}}>{msg.author_name||msg.author}</div>}<div style={{backgroundColor:isMe?C.accent:'white',color:isMe?'white':C.text,padding:'10px 14px',borderRadius:isMe?'18px 18px 4px 18px':'18px 18px 18px 4px',border:'1.5px solid '+(isMe?C.accent:C.border),boxShadow:'0 1px 3px rgba(0,0,0,0.06)'}}>{msg.text&&<p style={{margin:0,fontSize:'14px',lineHeight:'1.5'}}>{msg.text}</p>}{msg.photo_url&&<img src={msg.photo_url.startsWith('http')?msg.photo_url:API+msg.photo_url} alt='' onClick={()=>setShowPhotoModal(msg.photo_url.startsWith('http')?msg.photo_url:API+msg.photo_url)} style={{width:'200px',borderRadius:'8px',display:'block',marginTop:msg.text?'8px':'0',cursor:'pointer'}}/>}</div><div style={{fontSize:'10px',color:C.textMuted,marginTop:'3px',textAlign:isMe?'right':'left'}}>{msg.created_at?new Date(msg.created_at).toLocaleTimeString('ru-RU'):''}</div></div></div>);})}
              </div>
              <div style={{padding:'14px 16px',borderTop:'1.5px solid '+C.border,backgroundColor:C.bgWhite}}>
                <div style={{display:'flex',gap:'8px',alignItems:'flex-end'}}>
                  <label style={{cursor:'pointer',backgroundColor:C.bgGray,padding:'10px',borderRadius:'10px',border:'1.5px solid '+C.border,display:'flex',alignItems:'center'}}><Upload size={18} color={C.textSec}/><input type="file" accept="image/*" style={{display:'none'}} onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0]);sendCompanyChatMessage('',url);}}}/></label>
                  <textarea placeholder="Написать..." value={companyChatMessage} onChange={e=>setCompanyChatMessage(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendCompanyChatMessage(companyChatMessage,'');}}} style={{...inp,marginBottom:'0',resize:'none',height:'55px',flex:1,fontSize:'14px'}}/>
                  <button onClick={()=>sendCompanyChatMessage(companyChatMessage,'')} style={{...btnO,padding:'14px 22px',alignSelf:'flex-start'}}>➤</button>
                </div>
              </div>
            </div>
          </div>)}
        </div>
      </div>
    {sverkaModal&&(<div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:2000,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div style={{backgroundColor:'white',borderRadius:'16px',padding:'24px',width:'90%',maxWidth:'600px',maxHeight:'80vh',overflowY:'auto'}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'16px'}}>
          <b style={{fontSize:'15px'}}>📊 {sverkaModal.title}</b>
          <button onClick={()=>setSverkaModal(null)} style={{background:'none',border:'none',fontSize:'20px',cursor:'pointer'}}>×</button>
        </div>
        <pre style={{fontSize:'13px',lineHeight:'1.8',whiteSpace:'pre-wrap',fontFamily:'inherit'}}>{sverkaModal.text}</pre>
        <button onClick={()=>setSverkaModal(null)} style={{...btnO,marginTop:'16px',width:'100%',justifyContent:'center'}}>Закрыть</button>
      </div>
    </div>)}
    {showAiChat&&(<div style={isMobile?{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:C.bgWhite,zIndex:1000,display:'flex',flexDirection:'column',overflow:'hidden'}:{position:'fixed',bottom:'80px',right:'20px',width:'480px',height:'620px',backgroundColor:C.bgWhite,borderRadius:'16px',boxShadow:'0 8px 32px rgba(0,0,0,0.15)',border:'1.5px solid '+C.border,zIndex:1000,display:'flex',flexDirection:'column',overflow:'hidden'}}>
        <div style={{padding:'14px 16px',backgroundColor:C.accent,display:'flex',justifyContent:'space-between',alignItems:'center'}}>
          <div style={{display:'flex',alignItems:'center',gap:'8px'}}>
            <span style={{fontSize:'20px'}}>🤖</span>
            <div><b style={{color:'white',fontSize:'14px',display:'block'}}>ИИ Помощник</b><p style={{color:'rgba(255,255,255,0.8)',fontSize:'11px',margin:0}}>СтройКа Assistant</p></div>
          </div>
          <button onClick={()=>setShowAiChat(false)} style={{background:'none',border:'none',color:'white',cursor:'pointer',fontSize:'18px'}}>×</button>
        </div>
        <div style={{flex:1,overflowY:'auto',padding:'12px',display:'flex',flexDirection:'column',gap:'8px',backgroundColor:C.bg}}>
          {aiMessages.map((msg,i)=>(<div key={i} style={{display:'flex',justifyContent:msg.role==='user'?'flex-end':'flex-start'}}>
            <div style={{maxWidth:'85%',padding:'8px 12px',borderRadius:msg.role==='user'?'16px 16px 4px 16px':'16px 16px 16px 4px',backgroundColor:msg.role==='user'?C.accent:'white',color:msg.role==='user'?'white':C.text,fontSize:'13px',lineHeight:'1.5',boxShadow:'0 1px 3px rgba(0,0,0,0.08)',border:msg.role==='user'?'none':'1.5px solid '+C.border,whiteSpace:'pre-wrap'}}>
              {msg.content}
            </div>
          </div>))}
          {aiLoading&&(<div style={{display:'flex',justifyContent:'flex-start'}}><div style={{padding:'8px 12px',borderRadius:'16px 16px 16px 4px',backgroundColor:'white',border:'1.5px solid '+C.border,fontSize:'13px',color:C.textSec}}>⏳ Думаю...</div></div>)}
        </div>
        <div style={{padding:'10px 12px',borderTop:'1.5px solid '+C.border,backgroundColor:C.bgWhite,display:'flex',gap:'8px'}}>
          <input value={aiInput} onChange={e=>setAiInput(e.target.value)} onKeyDown={async e=>{
            if(e.key==='Enter'&&!e.shiftKey&&aiInput.trim()){
              e.preventDefault();
              const msg=aiInput.trim();
              setAiInput('');
              setAiMessages(prev=>[...prev,{role:'user',content:msg}]);
              setAiLoading(true);
              try{
                const context='Данные системы: проектов '+projects.length+', сотрудников '+staff.length+', материалов на складе '+materials.length+' позиций, договоров '+contracts.length+'. Текущий пользователь: '+user.name+' ('+ROLE_LABELS[user.role]+').';
                const res=await fetch(API+'/ai-chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:[...aiMessages,{role:'user',content:context+' Вопрос: '+msg}]})});
                const data=await res.json();
                setAiMessages(prev=>[...prev,{role:'assistant',content:data.response||data.error||'Ошибка ответа'}]);
              }catch(err){
                setAiMessages(prev=>[...prev,{role:'assistant',content:'Ошибка соединения с ИИ. Проверьте подключение.'}]);
              }
              setAiLoading(false);
            }
          }} placeholder='Задайте вопрос...' style={{...inp,marginBottom:0,flex:1,fontSize:'13px'}}/>
          <button onClick={async()=>{
            if(!aiInput.trim()) return;
            const msg=aiInput.trim();
            setAiInput('');
            setAiMessages(prev=>[...prev,{role:'user',content:msg}]);
            setAiLoading(true);
            try{
              const context='Данные системы: проектов '+projects.length+', сотрудников '+staff.length+', материалов на складе '+materials.length+' позиций, договоров '+contracts.length+'. Текущий пользователь: '+user.name+' ('+ROLE_LABELS[user.role]+').';
              const res=await fetch(API+'/ai-chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:[...aiMessages,{role:'user',content:context+' Вопрос: '+msg}]})});
              const data=await res.json();
              setAiMessages(prev=>[...prev,{role:'assistant',content:data.response||data.error||'Ошибка ответа'}]);
            }catch(err){
              setAiMessages(prev=>[...prev,{role:'assistant',content:'Ошибка соединения с ИИ.'}]);
            }
            setAiLoading(false);
          }} style={{...btnO,padding:'8px 14px'}}>➤</button>
        </div>
      </div>)}
      <div style={{position:'fixed',bottom:0,left:0,right:0,backgroundColor:activePage==='dashboard'?'rgba(15,23,42,0.95)':'white',borderTop:activePage==='dashboard'?'1px solid rgba(148,163,184,0.18)':'1.5px solid #e5e7eb',display:'flex',justifyContent:'space-around',padding:'8px 0 12px',zIndex:200,boxShadow:'0 -4px 20px rgba(0,0,0,0.06)'}}>
        {[{id:'dashboard',icon:<LayoutDashboard size={20}/>,label:'Главная'},{id:'projects',icon:<FolderKanban size={20}/>,label:'Объекты'},{id:'warehouse',icon:<Package size={20}/>,label:'Склад'},{id:'companychat',icon:<MessageSquare size={20}/>,label:'Чат',isPanel:true},{id:'more',icon:<ChevronUp size={20}/>,label:'Ещё'}].map(item=>(<div key={item.id} onClick={()=>{if(item.id==='more'){setShowMobileMenu(s=>!s);setShowQuickActions(false);}else if(item.id==='companychat'){setShowChatPanel(s=>!s);setShowMobileMenu(false);setShowQuickActions(false);}else{setActivePage(item.id);setShowMobileMenu(false);setShowQuickActions(false);}}} style={{display:'flex',flexDirection:'column',alignItems:'center',cursor:'pointer',padding:'4px 8px',borderRadius:'8px',backgroundColor:activePage===item.id?(activePage==='dashboard'?'rgba(249,115,22,0.15)':'#fff7ed'):'transparent'}}><span style={{color:activePage===item.id?'#f97316':activePage==='dashboard'?'#94a3b8':'#6b7280'}}>{item.icon}</span><span style={{fontSize:'10px',color:activePage===item.id?'#f97316':activePage==='dashboard'?'#94a3b8':'#9ca3af',fontWeight:activePage===item.id?'700':'400',marginTop:'2px'}}>{item.label}</span></div>))}
      </div>
      {reportingPayment&&(<div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:500,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div className='mobile-modal' style={{...card,padding:'20px',width:'340px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
        <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'12px'}}>💵 Отчёт о трате</b>
        <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 12px'}}>{'Выдано: '+Number(reportingPayment.amount).toLocaleString()+' ₽ · Остаток: '+(Number(reportingPayment.amount)-Number(reportingPayment.spentAmount||0)).toLocaleString()+' ₽'}</p>
        <select value={newExpense.projectName||reportingPayment.projectName} onChange={e=>setNewExpense({...newExpense,projectName:e.target.value})} style={inp}><option value=''>Проект *</option>{projects.map(proj=><option key={proj.id} value={proj.name}>{proj.name}</option>)}</select>
        <select value={newExpense.category||'accountable'} onChange={e=>setNewExpense({...newExpense,category:e.target.value})} style={inp}><option value=''>Категория затрат</option>{EXPENSE_CATEGORIES.map(c=><option key={c.id} value={c.id}>{c.label}</option>)}</select>
        <input placeholder='За что потрачено *' value={newExpense.description} onChange={e=>setNewExpense({...newExpense,description:e.target.value})} style={inp}/>
        <input placeholder='Сумма (₽) *' type='number' value={newExpense.amount} onChange={e=>setNewExpense({...newExpense,amount:e.target.value})} style={inp}/>
        <label style={{display:'block',marginBottom:'12px',cursor:'pointer'}}>
          <span style={{fontSize:'12px',color:C.textSec}}>📷 Фото чека:</span>
          <input type='file' accept='image/*' style={{display:'none'}} onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0]);setNewExpense(prev=>({...prev,photoUrl:url}));}}}/>
          {newExpense.photoUrl?<div style={{maxHeight:'180px',overflowY:'auto',borderRadius:'8px',marginTop:'6px',border:'1px solid #e5e7eb'}}><img src={newExpense.photoUrl.startsWith('http')?newExpense.photoUrl:API+newExpense.photoUrl} alt='' style={{width:'100%'}}/></div>:<div style={{border:'2px dashed '+C.border,borderRadius:'8px',padding:'20px',textAlign:'center',marginTop:'6px',color:C.textMuted}}>Нажмите чтобы загрузить</div>}
        </label>
        <div style={{display:'flex',gap:'8px'}}>
          <button onClick={async()=>{
            if(!newExpense.description||!newExpense.amount||expenseSubmitting) return;
            setExpenseSubmitting(true);
            await fetch(API+'/accountable-expenses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({paymentId:reportingPayment.id,projectName:newExpense.projectName||reportingPayment.projectName,description:newExpense.description,amount:Number(newExpense.amount),photoUrl:newExpense.photoUrl||'',date:new Date().toISOString().split('T')[0],addedBy:user.name})});
            setReportingPayment(null);
            setNewExpense({description:'',amount:'',photoUrl:''});
            setExpenseSubmitting(false);
            await loadAll();
            alert('Отчёт отправлен!');
          }} style={btnO}><Check size={14}/>Отправить</button>
          <button onClick={()=>{setReportingPayment(null);setNewExpense({description:'',amount:'',photoUrl:''});}} style={btnG}><X size={14}/>Отмена</button>
        </div>
      </div>
    </div>)}
    {addExpenseProject&&(<div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:500,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div className='mobile-modal' style={{...card,padding:'20px',width:'340px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
        <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'12px'}}>➕ Добавить расход</b>
        <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 12px'}}>{'Проект: '+addExpenseProject}</p>
        <select value={newManualExpense.category} onChange={e=>setNewManualExpense({...newManualExpense,category:e.target.value})} style={inp}>{EXPENSE_CATEGORIES.map(c=><option key={c.id} value={c.id}>{c.label}</option>)}</select>
        <input placeholder='Сумма (₽) *' type='number' value={newManualExpense.amount} onChange={e=>setNewManualExpense({...newManualExpense,amount:e.target.value})} style={inp}/>
        <input placeholder='Примечание' value={newManualExpense.note} onChange={e=>setNewManualExpense({...newManualExpense,note:e.target.value})} style={inp}/>
        <input type='date' value={newManualExpense.date} onChange={e=>setNewManualExpense({...newManualExpense,date:e.target.value})} style={inp}/>
        <div style={{display:'flex',gap:'8px'}}>
          <button onClick={async()=>{
            if(!newManualExpense.amount) return;
            await fetch(API+'/expenses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:addExpenseProject,category:newManualExpense.category,amount:Number(newManualExpense.amount),note:newManualExpense.note||'',date:newManualExpense.date||new Date().toISOString().split('T')[0],addedBy:user.name})});
            setAddExpenseProject('');
            await loadAll();
            alert('Расход добавлен!');
          }} style={btnO}><Check size={14}/>Добавить</button>
          <button onClick={()=>setAddExpenseProject('')} style={btnG}><X size={14}/>Отмена</button>
        </div>
      </div>
    </div>)}
    {showAccountableForm&&(<div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:500,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div className='mobile-modal' style={{...card,padding:'20px',width:'340px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
        <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'12px'}}>💵 Выдать подотчёт</b>
        {newAccountable.projectName?<p style={{color:C.textSec,fontSize:'12px',margin:'0 0 12px'}}>{'Объект: '+newAccountable.projectName}</p>:<select value={newAccountable.projectName||''} onChange={e=>setNewAccountable({...newAccountable,projectName:e.target.value})} style={inp}><option value=''>Выберите проект *</option>{projects.map(pr=><option key={pr.id} value={pr.name}>{pr.name}</option>)}</select>}
        <select value={newAccountable.givenTo} onChange={e=>setNewAccountable({...newAccountable,givenTo:e.target.value})} style={inp}><option value=''>Кому выдать *</option>{users.filter(u=>['прораб','мастер','снабженец','кладовщик'].includes(u.role)).map(u=><option key={u.id} value={u.name}>{u.name}</option>)}</select>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
          <input placeholder='Сумма *' type='number' value={newAccountable.amount} onChange={e=>setNewAccountable({...newAccountable,amount:e.target.value})} style={{...inp,marginBottom:0}}/>
          <select value={newAccountable.paymentMethod} onChange={e=>setNewAccountable({...newAccountable,paymentMethod:e.target.value})} style={{...inp,marginBottom:0}}>{['Наличные','Перевод на карту','Корпоративная карта','Через кассу'].map(m=><option key={m}>{m}</option>)}</select>
        </div>
        <input placeholder='Назначение' value={newAccountable.purpose} onChange={e=>setNewAccountable({...newAccountable,purpose:e.target.value})} style={inp}/>
        <input type='date' value={newAccountable.date} onChange={e=>setNewAccountable({...newAccountable,date:e.target.value})} style={inp}/>
        <div style={{display:'flex',gap:'8px'}}>
          <button onClick={async()=>{
            if(!newAccountable.givenTo||!newAccountable.amount||!newAccountable.projectName) return;
            await fetch(API+'/accountable-payments',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newAccountable,amount:Number(newAccountable.amount),addedBy:user.name})});
            setNewAccountable({givenTo:'',amount:'',paymentMethod:'Наличные',purpose:'',date:'',projectName:''});
            setShowAccountableForm(false);
            await loadAll();
          }} style={btnO}><Check size={14}/>Выдать</button>
          <button onClick={()=>{setShowAccountableForm(false);setNewAccountable({givenTo:'',amount:'',paymentMethod:'Наличные',purpose:'',date:'',projectName:''});}} style={btnG}><X size={14}/>Отмена</button>
        </div>
      </div>
    </div>)}
    {showDistribute&&selectedEstimate&&(<div onClick={()=>!distributing&&setShowDistribute(false)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:650,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div onClick={e=>e.stopPropagation()} className='mobile-modal' style={{...card,padding:'22px',width:'720px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
        <div style={{display:'flex',alignItems:'center',gap:'10px',marginBottom:'4px'}}>
          <span style={{fontSize:'22px'}}>👷</span>
          <b style={{color:C.text,fontSize:'15px'}}>Распределить смету по бригадам</b>
        </div>
        <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 14px'}}>Каждой позиции выбери бригаду. Из этого автоматически создадутся наряды с пересчётом цен по коэффициенту бригадного прайса (или 0.6 по умолчанию).</p>
        <div style={{...card,padding:'10px',marginBottom:'10px',backgroundColor:C.bg}}>
          <b style={{fontSize:'12px',color:C.text,display:'block',marginBottom:'6px'}}>Бригады, которым раздаём:</b>
          <div style={{display:'flex',flexWrap:'wrap',gap:'6px',marginBottom:'8px'}}>
            {distributeBrigades.map((b,i)=>(<span key={i} style={{padding:'4px 10px',borderRadius:'12px',backgroundColor:C.accentLight,color:C.accent,fontSize:'11px',display:'flex',alignItems:'center',gap:'6px'}}>{b.name}<button onClick={()=>setDistributeBrigades(prev=>prev.filter((_,idx)=>idx!==i))} style={{background:'none',border:'none',cursor:'pointer',color:C.danger}}>×</button></span>))}
            {distributeBrigades.length===0&&<span style={{fontSize:'11px',color:C.textMuted}}>Пока пусто — добавь бригады ниже</span>}
          </div>
          <div style={{display:'flex',gap:'4px'}}>
            <input placeholder='Название бригады' value={newDistributeBrigade.brigadeName} onChange={e=>setNewDistributeBrigade({...newDistributeBrigade,brigadeName:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px',flex:1}}/>
            <select value={newDistributeBrigade.pricelistId} onChange={e=>setNewDistributeBrigade({...newDistributeBrigade,pricelistId:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px',width:'160px'}}><option value=''>Прайс (необязат.)</option>{pricelists.map(pl=><option key={pl.id} value={pl.id}>{pl.name}</option>)}</select>
            <button onClick={()=>{if(!newDistributeBrigade.brigadeName.trim()) return;setDistributeBrigades(prev=>[...prev,{name:newDistributeBrigade.brigadeName.trim(),contractorType:newDistributeBrigade.contractorType,pricelistId:newDistributeBrigade.pricelistId}]);setNewDistributeBrigade({brigadeName:'',contractorType:'Своя бригада',pricelistId:''});}} style={{...btnO,fontSize:'12px',padding:'6px 10px'}}><Plus size={12}/>Добавить</button>
          </div>
        </div>
        <div style={{maxHeight:'380px',overflowY:'auto',marginBottom:'10px'}}>
          {(selectedEstimate.sections||[]).map((s,si)=>(<div key={si} style={{marginBottom:'10px'}}>
            <div style={{padding:'4px 8px',backgroundColor:C.accentLight,borderRadius:'4px',marginBottom:'4px'}}><b style={{fontSize:'11px',color:C.accent}}>{s.name}</b></div>
            {(s.items||[]).map((it,ii)=>{const key=si+'-'+ii;return(<div key={ii} style={{display:'grid',gridTemplateColumns:'1fr 70px 80px 1fr',gap:'6px',padding:'4px 8px',alignItems:'center',fontSize:'11px',borderBottom:'1px solid '+C.border}}>
              <span style={{color:C.text}}>{it.name}</span>
              <span style={{color:C.textSec}}>{it.quantity} {it.unit}</span>
              <span style={{color:C.textMuted}}>{Number(it.priceWork||0).toLocaleString('ru-RU')}₽</span>
              <select value={distributeAssignments[key]||''} onChange={e=>setDistributeAssignments(prev=>({...prev,[key]:e.target.value}))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'3px 6px'}}>
                <option value=''>— не назначено —</option>
                {distributeBrigades.map((b,bi)=><option key={bi} value={b.name}>{b.name}</option>)}
              </select>
            </div>);})}
          </div>))}
        </div>
        <div style={{display:'flex',gap:'8px',justifyContent:'space-between',marginTop:'12px'}}>
          <button onClick={async()=>{
            if(distributeBrigades.length===0){alert('Сначала добавьте бригады');return;}
            setDistributing(true);
            try{
              const res=await fetch(API+'/estimates/'+selectedEstimate.id+'/ai-distribute-suggest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({brigadeNames:distributeBrigades.map(b=>b.name)})});
              const data=await res.json();
              if(data.ok&&Array.isArray(data.assignments)){
                const newAssign={};
                let flatIdx=0;
                (selectedEstimate.sections||[]).forEach((s,si)=>(s.items||[]).forEach((it,ii)=>{
                  const a=data.assignments.find(a=>a.itemIndex===flatIdx);
                  if(a) newAssign[si+'-'+ii]=a.brigadeName;
                  flatIdx++;
                }));
                setDistributeAssignments(newAssign);
                alert('ИИ распределил позиции — проверьте и поправьте если нужно');
              }else alert('ИИ не справился, распределите вручную');
            }catch(e){alert('Ошибка ИИ: '+e.message);}
            setDistributing(false);
          }} disabled={distributing||distributeBrigades.length===0} style={{...btnB,backgroundColor:'#10b981',fontSize:'12px'}}><Bot size={13}/>🤖 ИИ распределит</button>
          <div style={{display:'flex',gap:'8px'}}>
            <button onClick={()=>setShowDistribute(false)} disabled={distributing} style={btnG}><X size={14}/>Отмена</button>
            <button disabled={distributing||Object.keys(distributeAssignments).length===0} onClick={async()=>{
              const assignments=[];
              (selectedEstimate.sections||[]).forEach((s,si)=>(s.items||[]).forEach((it,ii)=>{
                const bname=distributeAssignments[si+'-'+ii];
                if(bname){
                  const bdata=distributeBrigades.find(b=>b.name===bname);
                  assignments.push({section:s.name,name:it.name,unit:it.unit||'шт',quantity:Number(it.quantity||0),priceSmeta:Number(it.priceWork||0),brigadeName:bname,contractorType:bdata?.contractorType||'Своя бригада',pricelistId:bdata?.pricelistId||null});
                }
              }));
              if(!assignments.length){alert('Ничего не назначено');return;}
              setDistributing(true);
              try{
                const res=await fetch(API+'/estimates/'+selectedEstimate.id+'/distribute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({assignments,defaultCoefficient:0.6})});
                const data=await res.json();
                if(!res.ok||!data.ok){alert('Ошибка: '+(data.detail||'не удалось'));setDistributing(false);return;}
                await loadAll();
                setShowDistribute(false);
                setDistributing(false);
                alert('Создано нарядов: '+data.createdContracts.length+'\n\n'+data.createdContracts.map(c=>'• '+c.brigadeName+' ('+c.itemsCount+' поз., '+Math.round(c.totalAmount).toLocaleString('ru-RU')+' ₽)').join('\n'));
              }catch(e){alert('Ошибка: '+e.message);setDistributing(false);}
            }} style={btnO}>{distributing?'⏳...':'✨ Создать наряды'}</button>
          </div>
        </div>
      </div>
    </div>)}
    {showFromEstimate&&(<div onClick={()=>!creatingFromEstimate&&setShowFromEstimate(false)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:650,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div onClick={e=>e.stopPropagation()} className='mobile-modal' style={{...card,padding:'22px',width:'480px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
        <div style={{display:'flex',alignItems:'center',gap:'10px',marginBottom:'4px'}}>
          <span style={{fontSize:'22px'}}>📋</span>
          <b style={{color:C.text,fontSize:'15px'}}>Создать прайс-лист из сметы</b>
        </div>
        <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 14px'}}>Все позиции выбранной сметы попадут в прайс. Категория = название раздела сметы. Цены подтянутся из сметы — потом можно поправить вручную.</p>
        <select value={fromEstimateForm.estimateId} onChange={e=>{const est=estimatesList.find(es=>String(es.id)===e.target.value);setFromEstimateForm({...fromEstimateForm,estimateId:e.target.value,name:est?'Прайс из «'+est.name+'»':fromEstimateForm.name});}} style={inp}>
          <option value=''>Выберите смету *</option>
          {estimatesList.map(e=><option key={e.id} value={e.id}>{e.name}{e.projectName?' — '+e.projectName:''}</option>)}
        </select>
        <input placeholder='Название прайс-листа' value={fromEstimateForm.name} onChange={e=>setFromEstimateForm({...fromEstimateForm,name:e.target.value})} style={inp}/>
        <select value={fromEstimateForm.forWho} onChange={e=>setFromEstimateForm({...fromEstimateForm,forWho:e.target.value})} style={inp}>
          <option value=''>Для кого (необязательно)</option>
          {['Общий','Электрики','Сантехники','Каменщики','Отделочники','Кровельщики','Монтажники'].map(r=><option key={r}>{r}</option>)}
        </select>
        <label style={{color:C.textSec,fontSize:'12px',display:'block',marginBottom:'4px'}}>{'Коэффициент: ×'+fromEstimateForm.coefficient}</label>
        <input type='range' min='0.5' max='3' step='0.1' value={fromEstimateForm.coefficient} onChange={e=>setFromEstimateForm({...fromEstimateForm,coefficient:Number(e.target.value)})} style={{width:'100%',marginBottom:'10px',accentColor:C.accent}}/>
        <div style={{display:'flex',gap:'8px',justifyContent:'flex-end',marginTop:'8px'}}>
          <button onClick={()=>setShowFromEstimate(false)} disabled={creatingFromEstimate} style={btnG}><X size={14}/>Отмена</button>
          <button disabled={creatingFromEstimate||!fromEstimateForm.estimateId} onClick={async()=>{
            setCreatingFromEstimate(true);
            try{
              const res=await fetch(API+'/pricelists/from-estimate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(fromEstimateForm)});
              const data=await res.json();
              if(!res.ok||!data.ok){alert('Не удалось создать: '+(data.detail||'ошибка'));setCreatingFromEstimate(false);return;}
              await loadAll();
              const newPl=await fetch(API+'/pricelists').then(r=>r.json()).then(arr=>(Array.isArray(arr)?arr.find(p=>p.id===data.id):null));
              if(newPl){setSelectedPricelist(newPl);await loadPricelistItems(newPl.id);}
              setShowFromEstimate(false);
              setCreatingFromEstimate(false);
              alert('Прайс-лист «'+data.name+'» создан! Позиций: '+data.itemsCount);
            }catch(e){alert('Ошибка: '+e.message);setCreatingFromEstimate(false);}
          }} style={btnO}>{creatingFromEstimate?'⏳ Создаю...':'✨ Создать'}</button>
        </div>
      </div>
    </div>)}
    {showGeneratePricelist&&(<div onClick={()=>!generatingPricelist&&setShowGeneratePricelist(false)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:650,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div onClick={e=>e.stopPropagation()} className='mobile-modal' style={{...card,padding:'22px',width:'520px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
        <div style={{display:'flex',alignItems:'center',gap:'10px',marginBottom:'4px'}}>
          <span style={{fontSize:'22px'}}>🤖</span>
          <b style={{color:C.text,fontSize:'15px'}}>Сгенерировать прайс-лист через ИИ</b>
        </div>
        <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 14px'}}>Опишите для каких работ нужен прайс. ИИ соберёт список позиций с рыночными ценами по РФ 2026.</p>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'10px'}}>
          <input placeholder='Название прайс-листа' value={generatePricelistForm.name} onChange={e=>setGeneratePricelistForm({...generatePricelistForm,name:e.target.value})} style={{...inp,marginBottom:0}}/>
          <select value={generatePricelistForm.forWho} onChange={e=>setGeneratePricelistForm({...generatePricelistForm,forWho:e.target.value})} style={{...inp,marginBottom:0}}>
            <option value=''>Для кого (необязательно)</option>
            {['Электрики','Сантехники','Каменщики','Отделочники','Кровельщики','Монтажники','Общий'].map(r=><option key={r}>{r}</option>)}
          </select>
        </div>
        <textarea placeholder='Опишите подробнее: какие работы должны быть в прайсе, на какой тип объектов, какие материалы. Например: "Прайс для полного отделочного ремонта квартир и офисов: штукатурка, шпатлёвка, окраска, обои, плитка, ламинат, потолки. Включи демонтажные и подготовительные работы."' rows={6} value={generatePricelistForm.description} onChange={e=>setGeneratePricelistForm({...generatePricelistForm,description:e.target.value})} style={{...inp,marginBottom:'10px',resize:'vertical',fontFamily:'inherit',fontSize:'13px',lineHeight:'1.5'}}/>
        <label style={{color:C.textSec,fontSize:'12px',display:'block',marginBottom:'4px'}}>{'Коэффициент: ×'+generatePricelistForm.coefficient}</label>
        <input type='range' min='0.5' max='3' step='0.1' value={generatePricelistForm.coefficient} onChange={e=>setGeneratePricelistForm({...generatePricelistForm,coefficient:Number(e.target.value)})} style={{width:'100%',marginBottom:'10px',accentColor:C.accent}}/>
        <div style={{display:'flex',gap:'8px',justifyContent:'flex-end',marginTop:'8px'}}>
          <button onClick={()=>setShowGeneratePricelist(false)} disabled={generatingPricelist} style={btnG}><X size={14}/>Отмена</button>
          <button disabled={generatingPricelist||!generatePricelistForm.description.trim()} onClick={async()=>{
            if(!generatePricelistForm.description.trim()) return;
            setGeneratingPricelist(true);
            try{
              const res=await fetch(API+'/ai-generate-pricelist',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(generatePricelistForm)});
              const data=await res.json();
              if(!res.ok||!data.ok){alert('ИИ не справился: '+(data.detail||'попробуйте ещё раз с более детальным описанием'));setGeneratingPricelist(false);return;}
              await loadAll();
              const newPl=await fetch(API+'/pricelists').then(r=>r.json()).then(arr=>(Array.isArray(arr)?arr.find(p=>p.id===data.id):null));
              if(newPl){setSelectedPricelist(newPl);await loadPricelistItems(newPl.id);}
              setShowGeneratePricelist(false);
              setGeneratingPricelist(false);
              alert('Прайс-лист «'+data.name+'» создан! Позиций: '+data.itemsCount+'. Проверьте цены — можно редактировать вручную.');
            }catch(e){alert('Ошибка: '+e.message);setGeneratingPricelist(false);}
          }} style={{...btnO,backgroundColor:'#10b981'}}>{generatingPricelist?'⏳ ИИ думает... (15-40 сек)':'✨ Сгенерировать'}</button>
        </div>
        {generatingPricelist&&<p style={{color:C.textMuted,fontSize:'11px',marginTop:'10px',textAlign:'center'}}>Не закрывайте окно. ИИ собирает позиции прайс-листа.</p>}
      </div>
    </div>)}
    {showGenerateEstimate&&(<div onClick={()=>!generating&&setShowGenerateEstimate(false)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:650,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div onClick={e=>e.stopPropagation()} className='mobile-modal' style={{...card,padding:'22px',width:'520px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
        <div style={{display:'flex',alignItems:'center',gap:'10px',marginBottom:'4px'}}>
          <span style={{fontSize:'22px'}}>🤖</span>
          <b style={{color:C.text,fontSize:'15px'}}>Сгенерировать смету через ИИ</b>
        </div>
        <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 14px'}}>ИИ соберёт черновик из позиций прайс-листа на основе вашего описания. Объёмы и цены потом можно поправить вручную.</p>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'10px'}}>
          <select value={generateForm.projectId} onChange={e=>{const p=projects.find(pr=>pr.id===Number(e.target.value));setGenerateForm({...generateForm,projectId:e.target.value,pricelistId:p&&p.pricelistId?String(p.pricelistId):generateForm.pricelistId,name:p?'Смета — '+p.name:generateForm.name});}} style={{...inp,marginBottom:0}}>
            <option value=''>Без привязки к проекту</option>
            {projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <select value={generateForm.pricelistId} onChange={e=>setGenerateForm({...generateForm,pricelistId:e.target.value})} style={{...inp,marginBottom:0}}>
            <option value=''>Без прайс-листа</option>
            {pricelists.map(pl=><option key={pl.id} value={pl.id}>📋 {pl.name}</option>)}
          </select>
          <input placeholder='Название сметы' value={generateForm.name} onChange={e=>setGenerateForm({...generateForm,name:e.target.value})} style={{...inp,marginBottom:0}}/>
          <input placeholder='Площадь (м²)' type='number' value={generateForm.area} onChange={e=>setGenerateForm({...generateForm,area:e.target.value})} style={{...inp,marginBottom:0}}/>
        </div>
        <textarea placeholder='Опишите объект как можно подробнее: тип помещения, что нужно сделать, материалы, особенности. Например: "Квартира 3-комн 75 м² в новостройке без отделки. Стяжка, штукатурка/шпатлёвка/окраска стен, плитка в санузле и кухне, ламинат в комнатах, натяжные потолки. Установка межкомнатных дверей (4 шт), сантехника под ключ."' rows={6} value={generateForm.description} onChange={e=>setGenerateForm({...generateForm,description:e.target.value})} style={{...inp,marginBottom:'10px',resize:'vertical',fontFamily:'inherit',fontSize:'13px',lineHeight:'1.5'}}/>
        <div style={{display:'flex',gap:'8px',justifyContent:'flex-end',marginTop:'8px'}}>
          <button onClick={()=>setShowGenerateEstimate(false)} disabled={generating} style={btnG}><X size={14}/>Отмена</button>
          <button disabled={generating||!generateForm.description.trim()} onClick={async()=>{
            if(!generateForm.description.trim()) return;
            setGenerating(true);
            try{
              const res=await fetch(API+'/ai-generate-estimate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(generateForm)});
              const data=await res.json();
              if(!res.ok||!data.ok){alert('ИИ не справился: '+(data.detail||'попробуйте ещё раз с более детальным описанием'));setGenerating(false);return;}
              const est={id:data.id,name:data.name,projectId:data.projectId||'',projectName:data.projectName||'',version:'1.0',sections:data.sections};
              setEstimatesList(prev=>[...prev,est]);
              setSelectedEstimate(est);
              setShowGenerateEstimate(false);
              setGenerating(false);
              alert('Смета создана! Проверьте позиции и объёмы — можно редактировать вручную.');
            }catch(e){alert('Ошибка: '+e.message);setGenerating(false);}
          }} style={{...btnO,backgroundColor:'#10b981'}}>{generating?'⏳ ИИ думает... (15-40 сек)':'✨ Сгенерировать'}</button>
        </div>
        {generating&&<p style={{color:C.textMuted,fontSize:'11px',marginTop:'10px',textAlign:'center'}}>Не закрывайте окно. ИИ собирает разделы и позиции.</p>}
      </div>
    </div>)}
    {showEstimateChat&&selectedEstimate&&(<div onClick={()=>setShowEstimateChat(false)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:650,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div onClick={e=>e.stopPropagation()} className='mobile-modal' style={{...card,padding:0,width:'640px',height:'700px',margin:'20px',display:'flex',flexDirection:'column',overflow:'hidden'}}>
        <div style={{padding:'14px 18px',backgroundColor:'#0ea5e9',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
          <div style={{display:'flex',alignItems:'center',gap:'10px'}}>
            <span style={{fontSize:'22px'}}>💬</span>
            <div>
              <b style={{color:'white',fontSize:'14px',display:'block'}}>Чат по смете</b>
              <p style={{color:'rgba(255,255,255,0.85)',fontSize:'11px',margin:0}}>{selectedEstimate.name}</p>
            </div>
          </div>
          <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
            <button onClick={async()=>{if(window.confirm('Очистить историю чата?')){await fetch(API+'/estimates/'+selectedEstimate.id+'/chat-history',{method:'DELETE'});setEstimateChatMessages([]);}}} style={{background:'transparent',border:'1px solid rgba(255,255,255,0.4)',color:'white',cursor:'pointer',padding:'4px 10px',borderRadius:'6px',fontSize:'11px'}}>🗑️ Очистить</button>
            <button onClick={()=>setShowEstimateChat(false)} style={{background:'none',border:'none',cursor:'pointer',color:'white',fontSize:'22px',padding:'0 6px'}}>×</button>
          </div>
        </div>
        <div style={{flex:1,overflowY:'auto',padding:'16px',display:'flex',flexDirection:'column',gap:'10px',backgroundColor:C.bg}}>
          {estimateChatMessages.length===0&&!estimateChatLoading&&(<div style={{textAlign:'center',padding:'30px',color:C.textMuted}}>
            <div style={{fontSize:'40px',marginBottom:'10px'}}>💬</div>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'8px'}}>Задайте вопрос по смете</b>
            <p style={{fontSize:'12px',marginBottom:'14px'}}>ИИ помнит контекст этой сметы и предыдущие вопросы</p>
            <div style={{display:'flex',flexDirection:'column',gap:'6px',maxWidth:'420px',margin:'0 auto'}}>
              {['Какая самая дорогая позиция?','А если убрать раздел 5?','Чем заменить дорогие материалы?','Помоги объяснить клиенту почему смета подорожала'].map(q=>(<button key={q} onClick={()=>setEstimateChatInput(q)} style={{...btnG,fontSize:'12px',textAlign:'left',justifyContent:'flex-start',padding:'8px 12px'}}>💭 {q}</button>))}
            </div>
          </div>)}
          {estimateChatMessages.map((m,i)=>(<div key={m.id||i} style={{display:'flex',justifyContent:m.role==='user'?'flex-end':'flex-start'}}>
            <div style={{maxWidth:'85%',padding:'10px 14px',borderRadius:m.role==='user'?'14px 14px 4px 14px':'14px 14px 14px 4px',backgroundColor:m.role==='user'?C.accent:'white',color:m.role==='user'?'white':C.text,fontSize:'13px',lineHeight:'1.5',boxShadow:'0 1px 3px rgba(0,0,0,0.08)',border:m.role==='user'?'none':'1.5px solid '+C.border,whiteSpace:'pre-wrap'}}>{m.content}</div>
          </div>))}
          {estimateChatLoading&&(<div style={{display:'flex',justifyContent:'flex-start'}}><div style={{padding:'10px 14px',borderRadius:'14px 14px 14px 4px',backgroundColor:'white',border:'1.5px solid '+C.border,fontSize:'13px',color:C.textSec}}>⏳ Думаю над вопросом…</div></div>)}
        </div>
        <div style={{padding:'12px 14px',borderTop:'1.5px solid '+C.border,backgroundColor:C.bgWhite,display:'flex',gap:'8px'}}>
          <input value={estimateChatInput} onChange={e=>setEstimateChatInput(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendEstimateChatMessage();}}} placeholder='Спросите по смете... (Enter — отправить)' disabled={estimateChatLoading} style={{...inp,marginBottom:0,flex:1,fontSize:'13px'}}/>
          <button disabled={estimateChatLoading||!estimateChatInput.trim()} onClick={sendEstimateChatMessage} style={{...btnO,padding:'10px 16px'}}>➤</button>
        </div>
      </div>
    </div>)}
    {showVersionHistory&&selectedEstimate&&(<div onClick={()=>setShowVersionHistory(false)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:600,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div onClick={e=>e.stopPropagation()} className='mobile-modal' style={{...card,padding:'20px',width:'520px',margin:'20px',maxHeight:'85vh',overflowY:'auto'}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'14px'}}>
          <b style={{color:C.text,fontSize:'15px'}}>📜 История версий: {selectedEstimate.name}</b>
          <button onClick={()=>setShowVersionHistory(false)} style={{background:'none',border:'none',cursor:'pointer',fontSize:'18px',color:C.textSec}}>×</button>
        </div>
        {estimateVersions.length===0?(<p style={{color:C.textMuted,fontSize:'13px',padding:'20px',textAlign:'center'}}>История пуста. Снимки сохраняются автоматически при сохранении изменений сметы.</p>):(<>
          <p style={{color:C.textSec,fontSize:'12px',marginBottom:'10px'}}>Отметьте 2 версии чтобы сравнить через ИИ:</p>
          <div style={{maxHeight:'320px',overflowY:'auto',marginBottom:'12px'}}>
            {estimateVersions.map(v=>{const sel=selectedVersionsToCompare.includes(v.id);return(<div key={v.id} style={{padding:'10px',marginBottom:'6px',borderRadius:'8px',border:'1.5px solid '+(sel?C.accent:C.border),backgroundColor:sel?C.accentLight:C.bg,display:'flex',alignItems:'center',gap:'10px'}}>
              <input type='checkbox' checked={sel} onChange={e=>{if(e.target.checked){if(selectedVersionsToCompare.length<2)setSelectedVersionsToCompare([...selectedVersionsToCompare,v.id]);}else{setSelectedVersionsToCompare(selectedVersionsToCompare.filter(id=>id!==v.id));}}} style={{width:'16px',height:'16px',accentColor:C.accent}}/>
              <div style={{flex:1}}>
                <b style={{fontSize:'12px',color:C.text}}>v{v.versionLabel||'?'} — {Number(v.total||0).toLocaleString('ru-RU')} ₽</b>
                <p style={{fontSize:'11px',color:C.textSec,margin:'2px 0'}}>{new Date(v.createdAt).toLocaleString('ru-RU')}{v.createdBy?' · '+v.createdBy:''}</p>
                {v.comment&&<p style={{fontSize:'11px',color:C.textMuted,margin:'2px 0'}}>{v.comment}</p>}
              </div>
              <button onClick={async()=>{
                if(!window.confirm('Восстановить эту версию? Текущие данные будут сохранены как новая запись в истории.')) return;
                const ver=await fetch(API+'/estimate-version/'+v.id).then(r=>r.json());
                if(ver&&ver.sections){
                  const updated={...selectedEstimate,sections:ver.sections};
                  await fetch(API+'/estimates/'+selectedEstimate.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...updated,versionComment:'Восстановление из v'+(v.versionLabel||''),updatedBy:user.name})});
                  setSelectedEstimate(updated);
                  setEstimatesList(prev=>prev.map(e=>e.id===updated.id?updated:e));
                  setShowVersionHistory(false);
                  alert('Версия восстановлена');
                }
              }} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}>↶ Восстановить</button>
            </div>);})}
          </div>
          {selectedVersionsToCompare.length===2&&(<button onClick={async()=>{
            const [aId,bId]=selectedVersionsToCompare;
            const [a,b]=await Promise.all([fetch(API+'/estimate-version/'+aId).then(r=>r.json()),fetch(API+'/estimate-version/'+bId).then(r=>r.json())]);
            const totalOf=(secs)=>secs.flatMap(s=>s.items||[]).reduce((sum,i)=>sum+(i.isImported?Number(i.priceWork||0):Number(i.quantity||0)*(Number(i.priceWork||0)+Number(i.priceMaterial||0))),0);
            const flatten=(secs)=>secs.flatMap(s=>(s.items||[]).map(i=>({section:s.name,name:i.name,unit:i.unit,qty:Number(i.quantity||0),work:Number(i.priceWork||0),mat:Number(i.priceMaterial||0),sum:i.isImported?Number(i.priceWork||0):Number(i.quantity||0)*(Number(i.priceWork||0)+Number(i.priceMaterial||0))})));
            const payload={a:{label:a.versionLabel,total:totalOf(a.sections||[]),items:flatten(a.sections||[])},b:{label:b.versionLabel,total:totalOf(b.sections||[]),items:flatten(b.sections||[])}};
            const prompt='Сравни две версии сметы. Версия A (старая) и B (новая). Данные:\n'+JSON.stringify(payload,null,1)+'\n\nОТВЕТЬ СТРОГО JSON:\n{"summary":"одной фразой что произошло (стало дороже/дешевле и насколько)","changes":[{"what":"конкретная позиция или раздел","kind":"добавлена|удалена|объём|цена","detail":"что изменилось","impact":число_в_рублях}]}\nИспользуй только данные.';
            setShowVersionHistory(false);
            setShowAiChat(true);
            setAiMessages([{role:'user',content:'Сравнение версий v'+a.versionLabel+' ↔ v'+b.versionLabel}]);
            setAiLoading(true);
            try{
              const res=await fetch(API+'/ai-chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:[{role:'user',content:prompt}],jsonOnly:true})});
              const data=await res.json();
              const raw=(data.response||data.error||'').trim();
              let parsed=null;
              try{const clean=raw.replace(/^```(?:json)?/i,'').replace(/```$/,'').trim();const s=clean.indexOf('{'),e=clean.lastIndexOf('}');if(s>=0&&e>s) parsed=JSON.parse(clean.slice(s,e+1));}catch(e){}
              let out;
              if(parsed){
                const ln=[];
                if(parsed.summary) ln.push('📋 '+parsed.summary,'');
                if(Array.isArray(parsed.changes)&&parsed.changes.length){ln.push('🔍 ИЗМЕНЕНИЯ');parsed.changes.forEach((c,n)=>ln.push((n+1)+'. ['+(c.kind||'?')+'] '+(c.what||'?')+': '+(c.detail||'')+(c.impact?' ('+(c.impact>0?'+':'')+Number(c.impact).toLocaleString('ru-RU')+' ₽)':'')));}
                out=ln.join('\n');
              }else out=raw||'Ошибка';
              setAiMessages([{role:'user',content:'Сравнение v'+a.versionLabel+' ↔ v'+b.versionLabel},{role:'assistant',content:out}]);
            }catch(e){setAiMessages(prev=>[...prev,{role:'assistant',content:'Ошибка соединения'}]);}
            setAiLoading(false);
          }} style={{...btnO,backgroundColor:'#10b981',width:'100%',justifyContent:'center'}}><Bot size={14}/>🤖 Сравнить через ИИ</button>)}
        </>)}
      </div>
    </div>)}
    {showReceiveDialog&&(<div onClick={()=>setShowReceiveDialog(false)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:600,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div onClick={e=>e.stopPropagation()} className='mobile-modal' style={{...card,padding:'24px',width:'320px',margin:'20px'}}>
        <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'4px'}}>📥 Принять материал</b>
        <p style={{color:C.textSec,fontSize:'12px',marginBottom:'18px'}}>Выберите как заполнить накладную</p>
        <button onClick={()=>{setShowReceiveDialog(false);setShowScanInvoice(true);}} style={{...btnB,width:'100%',padding:'14px',justifyContent:'center',marginBottom:'10px',fontSize:'14px'}}><Scan size={16}/>📷 Сканировать накладную</button>
        <button onClick={()=>{setShowReceiveDialog(false);setShowScannedInvoiceForm(true);}} style={{...btnG,width:'100%',padding:'14px',justifyContent:'center',fontSize:'14px'}}><Edit2 size={14}/>✍️ Ввести вручную</button>
        <button onClick={()=>setShowReceiveDialog(false)} style={{width:'100%',marginTop:'10px',padding:'8px',backgroundColor:'transparent',border:'none',color:C.textSec,cursor:'pointer',fontSize:'13px'}}>Отмена</button>
      </div>
    </div>)}
    {showScannedInvoiceForm&&(<div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:500,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div className='mobile-modal' style={{...card,padding:'20px',width:'380px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
        <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'4px'}}>📋 Накладная</b>
        <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 12px'}}>Проверьте данные и сохраните</p>
        <input placeholder='Номер накладной *' value={newInvoice.number||''} onChange={e=>setNewInvoice({...newInvoice,number:e.target.value})} style={inp}/>
        <input placeholder='Поставщик' value={newInvoice.supplier||newInvoice.newSupplierName||''} onChange={e=>setNewInvoice({...newInvoice,supplier:e.target.value,newSupplierName:e.target.value,isNewSupplier:true})} style={inp}/>
        <select value={newInvoice.location||''} onChange={e=>setNewInvoice({...newInvoice,location:e.target.value,project:e.target.value!=='Основной склад'?e.target.value:''})} style={inp}>
          <option value=''>Выберите склад *</option>
          <option value='Основной склад'>📦 Основной склад</option>
          {projects.map(p=><option key={p.id} value={p.name}>🏗️ {p.name}</option>)}
        </select>
        <input type='date' value={newInvoice.date||new Date().toISOString().split('T')[0]} onChange={e=>setNewInvoice({...newInvoice,date:e.target.value})} style={inp}/>
        <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'8px'}}>Позиции:</b>
        {(newInvoice.items||[]).map((item,idx)=>(<div key={idx} style={{display:'grid',gridTemplateColumns:'2fr 0.7fr 0.7fr 1fr 24px',gap:'4px',marginBottom:'6px'}}>
          <input placeholder='Название' value={item.name} onChange={e=>{const items=[...newInvoice.items];items[idx]={...items[idx],name:e.target.value};setNewInvoice({...newInvoice,items});}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
          <input placeholder='Кол.' type='number' value={item.quantity} onChange={e=>{const items=[...newInvoice.items];items[idx]={...items[idx],quantity:e.target.value};setNewInvoice({...newInvoice,items});}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
          <select value={item.unit||'шт'} onChange={e=>{const items=[...newInvoice.items];items[idx]={...items[idx],unit:e.target.value};setNewInvoice({...newInvoice,items});}} style={{...inp,marginBottom:0,fontSize:'11px',padding:'6px 4px'}}>{UNITS.map(u=><option key={u}>{u}</option>)}</select>
          <input placeholder='Цена' type='number' value={item.price} onChange={e=>{const items=[...newInvoice.items];items[idx]={...items[idx],price:e.target.value};setNewInvoice({...newInvoice,items});}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
          <button onClick={()=>{const items=newInvoice.items.filter((_,i)=>i!==idx);if(!items.length)items.push({name:'',quantity:'',unit:'шт',price:'',category:''});setNewInvoice({...newInvoice,items});}} style={{...btnR,padding:'4px 6px',fontSize:'11px'}}><X size={12}/></button>
        </div>))}
        <button onClick={()=>setNewInvoice({...newInvoice,items:[...(newInvoice.items||[]),{name:'',quantity:'',unit:'шт',price:'',category:''}]})} style={{...btnG,fontSize:'12px',padding:'6px 12px',marginBottom:'10px'}}><Plus size={12}/>Ещё позиция</button>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',margin:'8px 0'}}>
          <b style={{color:C.text,fontSize:'13px'}}>Итого: {(newInvoice.items||[]).reduce((s,i)=>s+Number(i.quantity||0)*Number(i.price||0),0).toLocaleString()} ₽</b>
        </div>
        <div style={{display:'flex',gap:'8px',marginTop:'12px'}}>
          <button onClick={async()=>{
            if(!newInvoice.number) return alert('Укажите номер накладной');
            if(!newInvoice.location) return alert('Выберите склад');
            const validItems=(newInvoice.items||[]).filter(i=>i.name&&Number(i.quantity)>0);
            if(!validItems.length) return alert('Добавьте хотя бы одну позицию');
            try{
              await saveInvoiceNew();
              setShowScannedInvoiceForm(false);
              alert('Накладная принята, материалы оприходованы!');
            }catch(e){alert('Ошибка: '+(e.message||e));}
          }} style={btnO}><Check size={14}/>Сохранить</button>
          <button onClick={()=>setShowScannedInvoiceForm(false)} style={btnG}><X size={14}/>Отмена</button>
        </div>
      </div>
    </div>)}
    {showScanInvoice&&(<div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:500,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div className='mobile-modal' style={{...card,padding:'20px',width:'340px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
        <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'12px'}}>📷 Сканировать накладную</b>
        <label style={{display:'block',marginBottom:'12px',cursor:'pointer'}}>
          <input type='file' accept='image/*' capture='environment' style={{display:'none'}} onChange={async e=>{
            if(!e.target.files[0]) return;
            setScanningInvoice(true);
            const base64 = await new Promise(res=>{const r=new FileReader();r.onload=()=>res(r.result.split(',')[1]);r.readAsDataURL(e.target.files[0]);});
            try {
              const resp = await fetch(API+'/scan-invoice',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image:base64})});
              const data = await resp.json();
              if(!data.ok) throw new Error(data.error||'Ошибка');
              const parsed = data.data;
              const today = new Date().toISOString().split('T')[0];
              setNewInvoice(prev=>({...prev,
                supplier:parsed.supplier||'',
                newSupplierName:parsed.supplier||'',
                isNewSupplier:true,
                date:today,
                acceptedBy:user.name,
                vat:'Без НДС',
                totalWithVat:parsed.total||0,
                items:(parsed.items||[]).map(item=>({
                  name:item.name||'',
                  quantity:String(item.quantity||''),
                  unit:item.unit||'шт',
                  price:String(item.price||''),
                  category:''
                }))
              }));
              setShowScanInvoice(false);
              setShowScannedInvoiceForm(true);
              alert('Накладная распознана! Проверьте данные.');
            } catch(e){
              alert('Не удалось распознать. Попробуйте ещё раз.');
            }
            setScanningInvoice(false);
          }}/>
          <div style={{border:'2px dashed '+C.border,borderRadius:'12px',padding:'30px',textAlign:'center',cursor:'pointer'}}>
            {scanningInvoice?<div><div style={{fontSize:'32px',marginBottom:'8px'}}>⏳</div><p style={{color:C.textSec,fontSize:'13px'}}>ИИ распознаёт накладную...</p></div>:<div><div style={{fontSize:'48px',marginBottom:'8px'}}>📷</div><p style={{color:C.text,fontSize:'14px',fontWeight:'600'}}>Нажмите чтобы сфотографировать</p><p style={{color:C.textSec,fontSize:'12px',marginTop:'4px'}}>ИИ автоматически заполнит форму</p></div>}
          </div>
        </label>
        <button onClick={()=>setShowScanInvoice(false)} style={{...btnG,width:'100%',justifyContent:'center'}}><X size={14}/>Отмена</button>
      </div>
    </div>)}
    {showOwnExpenseForm&&(<div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:500,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div className='mobile-modal' style={{...card,padding:'20px',width:'340px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
        <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'12px'}}>💸 Потратил свои деньги</b>
        <select value={newOwnExpense.projectName} onChange={e=>setNewOwnExpense({...newOwnExpense,projectName:e.target.value})} style={inp}><option value=''>Выберите проект *</option>{projects.map(proj=><option key={proj.id} value={proj.name}>{proj.name}</option>)}</select>
        <input placeholder='За что потрачено *' value={newOwnExpense.description} onChange={e=>setNewOwnExpense({...newOwnExpense,description:e.target.value})} style={inp}/>
        <input placeholder='Сумма (₽) *' type='number' value={newOwnExpense.amount} onChange={e=>setNewOwnExpense({...newOwnExpense,amount:e.target.value})} style={inp}/>
        <input type='date' value={newOwnExpense.date} onChange={e=>setNewOwnExpense({...newOwnExpense,date:e.target.value})} style={inp}/>
        <label style={{display:'block',marginBottom:'12px',cursor:'pointer'}}>
          <span style={{fontSize:'12px',color:C.textSec}}>📷 Фото чека:</span>
          <input type='file' accept='image/*' capture='environment' style={{display:'none'}} onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0]);setNewOwnExpense(prev=>({...prev,photoUrl:url}));}}}/>
          {newOwnExpense.photoUrl?<div style={{maxHeight:'180px',overflowY:'auto',borderRadius:'8px',marginTop:'6px',border:'1px solid '+C.border}}><img src={newOwnExpense.photoUrl.startsWith('http')?newOwnExpense.photoUrl:API+newOwnExpense.photoUrl} alt='' style={{width:'100%'}}/></div>:<div style={{border:'2px dashed '+C.border,borderRadius:'8px',padding:'16px',textAlign:'center',marginTop:'6px',color:C.textMuted,fontSize:'12px'}}>Нажмите чтобы загрузить фото чека</div>}
        </label>
        <div style={{display:'flex',gap:'8px'}}>
          <button onClick={async()=>{
            if(!newOwnExpense.projectName||!newOwnExpense.description||!newOwnExpense.amount) return;
            await fetch(API+'/own-expenses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newOwnExpense,amount:Number(newOwnExpense.amount),employeeName:user.name,employeeId:user.id})});
            setNewOwnExpense({projectName:'',description:'',amount:'',photoUrl:'',date:''});
            setShowOwnExpenseForm(false);
            await loadAll();
            alert('Отправлено на возмещение!');
          }} style={btnO}><Check size={14}/>Отправить</button>
          <button onClick={()=>{setShowOwnExpenseForm(false);setNewOwnExpense({projectName:'',description:'',amount:'',photoUrl:'',date:''});}} style={btnG}><X size={14}/>Отмена</button>
        </div>
      </div>
    </div>)}
    {showQuickActions&&(<div onMouseDown={e=>{e.preventDefault();setShowQuickActions(false);}} style={{position:'fixed',top:0,left:0,right:0,bottom:'60px',backgroundColor:'rgba(0,0,0,0.5)',zIndex:299}}/>)}
    {showQuickActions&&(<div style={{position:'fixed',bottom:'65px',left:0,right:0,backgroundColor:'#0f172a',borderRadius:'16px 16px 0 0',padding:'16px',zIndex:300,boxShadow:'0 -8px 30px rgba(0,0,0,0.4)',maxHeight:'70vh',overflowY:'auto',border:'1px solid rgba(148,163,184,0.18)'}}>
      <div style={{textAlign:'center',marginBottom:'12px'}}><div style={{width:'36px',height:'4px',backgroundColor:'#e5e7eb',borderRadius:'2px',margin:'0 auto'}}/></div>
      <b style={{color:'#111827',fontSize:'14px',display:'block',marginBottom:'12px'}}>⚡ Быстрые действия</b>
      <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'10px'}}>
        {[
          {icon:<Scan size={24}/>,label:'Скан накладной',color:'#f97316',action:()=>{setShowQuickActions(false);setShowScanInvoice(true);},roles:['директор','зам_директора','бухгалтер','прораб','кладовщик','снабженец']},
          {icon:<CreditCard size={24}/>,label:'Мои траты',color:'#22c55e',action:()=>{setShowQuickActions(false);setShowOwnExpenseForm(true);}},
          {icon:<MessageSquare size={24}/>,label:'Чат',color:'#3b82f6',action:()=>{setShowQuickActions(false);setActivePage('companychat');}},
          {icon:<FolderKanban size={24}/>,label:'Объекты',color:'#f59e0b',action:()=>{setShowQuickActions(false);setActivePage('projects');}},
          {icon:<Package size={24}/>,label:'Склад',color:'#8b5cf6',action:()=>{setShowQuickActions(false);setActivePage('warehouse');}},
          {icon:<Bot size={24}/>,label:'ИИ',color:'#f97316',action:()=>{setShowQuickActions(false);setShowAiAssistant(true);}},
        ].filter(btn=>!btn.roles||(user&&btn.roles.includes(user.role))).map((btn,i)=>(<div key={i} onClick={btn.action} style={{display:'flex',flexDirection:'column',alignItems:'center',padding:'14px 8px',borderRadius:'16px',cursor:'pointer',background:'rgba(30,41,59,0.6)',border:'1px solid rgba(148,163,184,0.12)'}}>
          <div style={{width:'48px',height:'48px',borderRadius:'14px',background:`rgba(${btn.color==='#f97316'?'249,115,22':btn.color==='#22c55e'?'34,197,94':btn.color==='#3b82f6'?'59,130,246':btn.color==='#f59e0b'?'245,158,11':btn.color==='#8b5cf6'?'139,92,246':'249,115,22'},.15)`,display:'flex',alignItems:'center',justifyContent:'center',marginBottom:'8px',color:btn.color}}>{btn.icon}</div>
          <span style={{fontSize:'11px',color:'#94a3b8',fontWeight:'600',textAlign:'center'}}>{btn.label}</span>
        </div>))}
      </div>
    </div>)}
    {showMobileMenu&&(<div onMouseDown={e=>{e.preventDefault();setShowMobileMenu(false);}} style={{position:'fixed',top:0,left:0,right:0,bottom:'60px',backgroundColor:'rgba(0,0,0,0.5)',zIndex:299}}/>)}
      {showMobileMenu&&(<div style={{position:'fixed',bottom:'60px',left:0,right:0,backgroundColor:'white',borderRadius:'16px 16px 0 0',padding:'16px',zIndex:300,maxHeight:'60vh',overflowY:'auto',boxShadow:'0 -8px 30px rgba(0,0,0,0.15)'}}>
        <div style={{textAlign:'center',marginBottom:'12px'}}><div style={{width:'36px',height:'4px',backgroundColor:'#e5e7eb',borderRadius:'2px',margin:'0 auto'}}/></div>
        <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'8px'}}>
          {menuItems.map(m=>(<div key={m.id} onClick={()=>{setActivePage(m.id);setShowMobileMenu(false);}} style={{display:'flex',flexDirection:'column',alignItems:'center',padding:'12px 8px',borderRadius:'12px',cursor:'pointer',backgroundColor:activePage===m.id?'rgba(249,115,22,0.15)':'rgba(30,41,59,0.6)',border:'1px solid rgba(148,163,184,0.12)'}}><span style={{fontSize:'24px',marginBottom:'4px'}}>{m.icon}</span><span style={{fontSize:'11px',color:activePage===m.id?'#f97316':'#94a3b8',fontWeight:activePage===m.id?'700':'400',textAlign:'center',lineHeight:'1.3'}}>{m.label}</span></div>))}
        </div>
      </div>)}
      
      
    {showChatPanel&&(<div onMouseDown={e=>{e.preventDefault();setShowChatPanel(false);}} style={{position:'fixed',top:0,left:0,right:0,bottom:'60px',backgroundColor:'rgba(0,0,0,0.5)',zIndex:399}}/>)}
    {showChatPanel&&(<div style={{position:'fixed',bottom:'70px',right:'12px',width:'340px',height:'460px',backgroundColor:'#0f172a',borderRadius:'16px',zIndex:400,display:'flex',flexDirection:'column',boxShadow:'0 8px 32px rgba(0,0,0,0.5)',border:'1px solid rgba(148,163,184,0.18)'}}>
      <div style={{padding:'16px',borderBottom:'1px solid rgba(148,163,184,0.18)',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
        <b style={{color:'#f8fafc',fontSize:'16px'}}>💬 Чат</b>
        <button onClick={()=>setShowChatPanel(false)} style={{background:'none',border:'none',cursor:'pointer',color:'#94a3b8'}}><X size={20}/></button>
      </div>
      <div style={{flex:1,overflowY:'auto',padding:'12px',display:'flex',flexDirection:'column',gap:'8px'}}>
        {companyMessages.slice(-20).map((msg,i)=>(
          <div key={i} style={{display:'flex',justifyContent:(msg.author_name||msg.author)===user.name?'flex-end':'flex-start'}}>
            <div style={{maxWidth:'80%',padding:'10px 14px',borderRadius:(msg.author_name||msg.author)===user.name?'16px 16px 4px 16px':'16px 16px 16px 4px',backgroundColor:(msg.author_name||msg.author)===user.name?'#ea580c':'rgba(30,41,59,0.8)',color:'#f8fafc',fontSize:'13px',lineHeight:'1.5'}}>
              {(msg.author_name||msg.author)!==user.name&&<div style={{fontSize:'11px',color:'#94a3b8',marginBottom:'4px',fontWeight:'600'}}>{msg.author_name||msg.author}</div>}
              {msg.text}
              <div style={{fontSize:'10px',color:'rgba(255,255,255,0.5)',marginTop:'4px',textAlign:'right'}}>{msg.time}</div>
            </div>
          </div>
        ))}
        {companyMessages.length===0&&<div style={{textAlign:'center',color:'#94a3b8',padding:'30px',fontSize:'14px'}}>Нет сообщений</div>}
      </div>
      <div style={{padding:'12px',borderTop:'1px solid rgba(148,163,184,0.18)',display:'flex',gap:'8px'}}>
        <label style={{padding:'8px',background:'rgba(30,41,59,0.8)',border:'1px solid rgba(148,163,184,0.18)',borderRadius:'10px',cursor:'pointer',display:'flex',alignItems:'center'}}><Camera size={16} color='#94a3b8'/><input type='file' accept='image/*' style={{display:'none'}} onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0]);sendCompanyChatMessage('[Фото]',url);}}}/></label>
        <label style={{padding:'8px',background:'rgba(30,41,59,0.8)',border:'1px solid rgba(148,163,184,0.18)',borderRadius:'10px',cursor:'pointer',display:'flex',alignItems:'center'}}><FileText size={16} color='#94a3b8'/><input type='file' accept='.pdf,.doc,.docx' style={{display:'none'}} onChange={async e=>{if(e.target.files[0]){sendCompanyChatMessage('[Документ] '+e.target.files[0].name,'');}}}/>  </label>
        <input placeholder="Сообщение..." value={companyChatInput||''} onChange={e=>setCompanyChatInput(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&companyChatInput?.trim()){sendCompanyChatMessage(companyChatInput);setCompanyChatInput('');}}} style={{flex:1,padding:'10px 14px',backgroundColor:'rgba(30,41,59,0.8)',border:'1px solid rgba(148,163,184,0.18)',borderRadius:'12px',color:'#f8fafc',fontSize:'13px',outline:'none'}}/>
        <button onClick={()=>{if(companyChatInput?.trim()){sendCompanyChatMessage(companyChatInput);setCompanyChatInput('');}}} style={{padding:'10px 16px',backgroundColor:'#ea580c',border:'none',borderRadius:'12px',color:'white',cursor:'pointer'}}><MessageSquare size={16}/></button>
      </div>
    </div>)}

      
    </div>
  );
}

export default App;
// cache bust понедельник, 18 мая 2026 г. 00:22:26 (MSK)
