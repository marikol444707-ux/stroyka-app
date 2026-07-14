import React from 'react';
import {
  BriefcaseBusiness,
  Building2,
  Calculator,
  ClipboardCheck,
  Hammer,
  Handshake,
  Package,
  ShieldCheck,
} from 'lucide-react';

export const PUBLIC_CONSENT_VERSION = 'public-site-pd-v1-2026-06-21';
export const PUBLIC_SITE_OPERATOR = {
  name: 'СтройКа',
  site: 'stroyka26.pro',
  privacyEmail: 'privacy@stroyka26.pro',
  leadEmail: 'info@stroyka26.pro',
};

export const PROJECT_EXAMPLE_STATUS = 'Проект-идея / пример для расчета';

export const publicFunnelSteps = [
  {
    number: '1',
    title: 'Выбрать направление',
    text: 'Дом, ремонт, реконструкция или коммерческий объект.',
    target: 'directions',
  },
  {
    number: '2',
    title: 'Открыть проект',
    text: 'Посмотреть фасад, ракурс, планировку и ориентир цены.',
    target: 'projects',
  },
  {
    number: '3',
    title: 'Уточнить расчет',
    text: 'Площадь, комплектация, материалы, сроки и файлы.',
    target: 'calculator',
  },
  {
    number: '4',
    title: 'Оставить заявку',
    text: 'Параметры попадут в CRM для точной сметы.',
    target: 'request',
  },
];

export const workTypes = [
  { value: 'house', label: 'Дом', short: 'Строительство', description: 'Коробка, тёплый контур, инженерия, под ключ' },
  { value: 'repair', label: 'Ремонт', short: 'Отделка', description: 'Квартира, дом, офис, состояние и набор работ' },
  { value: 'commerce', label: 'Коммерция', short: 'Бизнес-объект', description: 'Офис, магазин, кафе, салон, запуск к дате' },
  { value: 'reconstruction', label: 'Реконструкция', short: 'Переделка', description: 'Демонтаж, усиление, кровля, инженерия' },
];

export const houseWallTypes = [
  { value: 'gasblock', label: 'Газоблок', multiplier: 1 },
  { value: 'brick', label: 'Кирпич', multiplier: 1.18 },
  { value: 'monolith', label: 'Монолит', multiplier: 1.28 },
  { value: 'frame', label: 'Каркас', multiplier: 0.88 },
];

export const housePackages = [
  { value: 'box', label: 'Коробка', rate: 38000 },
  { value: 'warm', label: 'Тёплый контур', rate: 52000 },
  { value: 'engineering', label: 'Инженерия', rate: 25000 },
  { value: 'turnkey', label: 'Под ключ', rate: 72000 },
];

export const stages = [
  { value: 'idea', label: 'Есть идея' },
  { value: 'project', label: 'Есть проект' },
  { value: 'estimate', label: 'Есть смета' },
  { value: 'start', label: 'Нужно начать быстро' },
];

export const repairObjects = [
  { value: 'apartment', label: 'Квартира', multiplier: 1 },
  { value: 'privateHouse', label: 'Дом', multiplier: 1.08 },
  { value: 'office', label: 'Офис', multiplier: 0.94 },
  { value: 'retail', label: 'Помещение', multiplier: 1.05 },
];

export const repairConditions = [
  { value: 'new', label: 'Новостройка', multiplier: 1 },
  { value: 'secondary', label: 'Вторичка', multiplier: 1.12 },
  { value: 'old', label: 'Старый фонд', multiplier: 1.25 },
  { value: 'afterDemolition', label: 'После демонтажа', multiplier: 0.95 },
];

export const repairLevels = [
  { value: 'cosmetic', label: 'Косметический', rate: 18000 },
  { value: 'capital', label: 'Капитальный', rate: 32000 },
  { value: 'designer', label: 'Дизайнерский', rate: 48000 },
  { value: 'commercial', label: 'Коммерческий ремонт', rate: 36000 },
];

export const materialModes = [
  { value: 'client', label: 'Материалы клиента', multiplier: 0.72 },
  { value: 'partial', label: 'Частично через нас', multiplier: 0.88 },
  { value: 'company', label: 'Материалы через СтройКа', multiplier: 1 },
];

export const commerceTypes = [
  { value: 'office', label: 'Офис', multiplier: 1 },
  { value: 'shop', label: 'Магазин', multiplier: 1.08 },
  { value: 'cafe', label: 'Кафе', multiplier: 1.22 },
  { value: 'warehouse', label: 'Склад', multiplier: 0.78 },
  { value: 'salon', label: 'Салон', multiplier: 1.12 },
  { value: 'medical', label: 'Медкабинет', multiplier: 1.32 },
];

export const commerceLevels = [
  { value: 'base', label: 'Базовая подготовка', rate: 26000 },
  { value: 'standard', label: 'Рабочий формат', rate: 38000 },
  { value: 'opening', label: 'Под открытие', rate: 52000 },
  { value: 'special', label: 'Сложная инженерия', rate: 64000 },
];

export const reconstructionScopes = [
  { value: 'house', label: 'Дом целиком', rate: 42000 },
  { value: 'extension', label: 'Пристройка', rate: 36000 },
  { value: 'roof', label: 'Кровля', rate: 19000 },
  { value: 'facade', label: 'Фасад', rate: 21000 },
  { value: 'inside', label: 'Внутри помещения', rate: 30000 },
];

export const getOptionLabel = (options, value) => (
  options.find((item) => item.value === value)?.label || options[0]?.label || ''
);

export const projectFilters = [
  { value: 'all', label: 'Все' },
  { value: 'house', label: 'Дома' },
  { value: 'repair', label: 'Ремонт' },
  { value: 'commerce', label: 'Коммерция' },
  { value: 'reconstruction', label: 'Реконструкция' },
];

export const workProofItems = [
  {
    title: 'Скрытые работы',
    text: 'Фото до закрытия, исполнитель и привязка к этапу работ.',
    image: 'https://images.unsplash.com/photo-1503387762-592deb58ef4e?auto=format&fit=crop&w=900&q=82',
    metric: 'Этап + фото',
    icon: ClipboardCheck,
  },
  {
    title: 'Материалы на объекте',
    text: 'Поставки, остатки и движение материалов под внутренним контролем.',
    image: 'https://images.unsplash.com/photo-1581092160607-ee22621dd758?auto=format&fit=crop&w=900&q=82',
    metric: 'Склад',
    icon: Package,
  },
  {
    title: 'Ежедневный ход работ',
    text: 'Работы мастеров, объёмы, замечания и подтверждения.',
    image: 'https://images.unsplash.com/photo-1581094271901-8022df4466f9?auto=format&fit=crop&w=900&q=82',
    metric: 'Журнал работ',
    icon: Hammer,
  },
];

export const trustItems = [
  {
    title: 'Расчёт не теряется',
    text: 'Выбранное направление, проект, параметры калькулятора и комментарий уходят в CRM одной заявкой.',
    icon: Calculator,
  },
  {
    title: 'Материалы под контролем',
    text: 'Поставки, накладные, остатки и передача материалов фиксируются внутри рабочей системы.',
    icon: Package,
  },
  {
    title: 'Этапы подтверждаются',
    text: 'Фото, скрытые работы, замечания и ежедневный ход объекта остаются в истории объекта.',
    icon: ClipboardCheck,
  },
  {
    title: 'Документы отдельно от сайта',
    text: 'Публичная витрина не публикует договоры и внутренние документы, они остаются внутри ERP.',
    icon: ShieldCheck,
  },
];

export const faqItems = [
  {
    question: 'Почему стоимость на сайте предварительная?',
    answer: 'Сайт даёт ориентир по выбранному типу объекта, площади и комплектации. Точная сумма появляется после замера, проверки проекта, материалов, грунтов, инженерии и сроков.',
  },
  {
    question: 'Что происходит после отправки заявки?',
    answer: 'Заявка попадает в CRM. В ней сохраняются телефон, комментарий, выбранный проект, примерная стоимость и параметры расчёта. После этого менеджер или директор уточняет данные.',
  },
  {
    question: 'Можно выбрать готовый проект и изменить планировку?',
    answer: 'Да. Карточки на сайте нужны как стартовая точка. Планировку, площадь, фасад, комплектацию и материалы можно уточнить перед точной сметой.',
  },
  {
    question: 'Почему документы не публикуются на сайте?',
    answer: 'Публичный сайт показывает направления, примеры и расчёт. Договоры, накладные, акты и внутренние документы остаются в защищённой рабочей системе.',
  },
  {
    question: 'Можно ли загрузить свои фото, план или проект?',
    answer: 'Да. В калькуляторе есть загрузка файлов. Они повышают точность первичного расчёта и помогают быстрее подготовить смету.',
  },
];

export const referenceDirections = [
  {
    id: 'one-floor-modern',
    title: 'Одноэтажный современный дом',
    text: 'Компактные дома 90-160 м2 с террасой, светлой гостиной и понятной планировкой.',
    image: '/site-assets/projects/h1-01/facade.webp',
    tags: ['1 этаж', 'современный фасад', 'терраса'],
    calcPatch: { type: 'house', floors: 1, wallType: 'gasblock', package: 'turnkey', area: 120, rooms: 4 },
    examples: [
      'Дом 90-110 м2 с плоской кровлей и террасой',
      'Дом 120-140 м2 с панорамным остеклением гостиной',
      'L-образный дом с закрытым внутренним двориком',
      'Дом с навесом для автомобиля вместо гаража',
      'Минималистичный дом с фасадом из штукатурки и дерева',
      'Дом с большой кухней-гостиной и выходом на участок',
      'Компактный дом для молодой семьи на узком участке',
      'Дом с мастер-спальней и двумя детскими',
      'Дом с отдельной котельной и хозяйственным входом',
      'Дом с летней кухней/террасой как главным сценарием',
    ],
  },
  {
    id: 'one-floor-brick',
    title: 'Одноэтажный дом из кирпича',
    text: 'Классические капитальные дома для постоянного проживания.',
    image: '/site-assets/projects/b1-01/facade.webp',
    tags: ['кирпич', 'классика', 'надежность'],
    calcPatch: { type: 'house', floors: 1, wallType: 'brick', package: 'turnkey', area: 135, rooms: 4 },
    examples: [
      'Классический кирпичный дом с вальмовой кровлей',
      'Дом из светлого кирпича с темной кровлей',
      'Дом из темного кирпича с белыми откосами',
      'Кирпичный дом с высоким цоколем',
      'Дом с крыльцом и аккуратной входной группой',
      'Дом с эркером в гостиной',
      'Кирпичный дом с пристроенной террасой',
      'Дом с теплой кровлей и утепленным чердаком',
      'Дом с фасадным декором без перегруза',
      'Кирпичный дом для постоянного проживания',
    ],
  },
  {
    id: 'family-cottage',
    title: 'Семейный коттедж',
    text: 'Загородные дома с общей семейной зоной, террасой и удобной логикой жизни.',
    image: '/site-assets/projects/fam-01/facade.webp',
    tags: ['коттедж', 'семья', 'двор'],
    calcPatch: { type: 'house', floors: 1, wallType: 'gasblock', package: 'turnkey', area: 155, rooms: 5 },
    examples: [
      'Коттедж с большой кухней-гостиной',
      'Коттедж с террасой для семьи и гостей',
      'Коттедж с детскими комнатами на солнечной стороне',
      'Коттедж с отдельной гостевой комнатой',
      'Коттедж с каминной зоной',
      'Коттедж с навесом и хозяйственным блоком',
      'Коттедж со вторым светом в гостиной',
      'Коттедж с выходом из кухни на двор',
      'Коттедж с большой прихожей и гардеробной',
      'Коттедж с готовым сценарием "заехать и жить"',
    ],
  },
  {
    id: 'two-floor-modern',
    title: 'Двухэтажный современный дом',
    text: 'Современная архитектура, больше площади на компактном участке.',
    image: 'https://images.unsplash.com/photo-1600047509358-9dc75507daeb?auto=format&fit=crop&w=900&q=82',
    tags: ['2 этажа', 'современный', 'панорама'],
    calcPatch: { type: 'house', floors: 2, wallType: 'gasblock', package: 'turnkey', area: 180, rooms: 5 },
    examples: [
      'Кубический дом с плоской кровлей',
      'Дом с балконом и террасой на втором этаже',
      'Дом со вторым светом и панорамными окнами',
      'Дом на узком участке с вытянутой планировкой',
      'Дом с комбинированным фасадом: штукатурка, дерево, камень',
      'Дом с приватной спальней на втором этаже',
      'Дом с кабинетом на первом этаже',
      'Дом с выходом гостиной на задний двор',
      'Дом с минималистичной входной группой',
      'Дом с современной вечерней подсветкой фасада',
    ],
  },
  {
    id: 'two-floor-brick',
    title: 'Двухэтажный дом из кирпича',
    text: 'Капитальные дома с классическим фасадом и долгим сроком службы.',
    image: 'https://images.unsplash.com/photo-1600566752355-35792bedcfea?auto=format&fit=crop&w=900&q=82',
    tags: ['кирпич', '2 этажа', 'статус'],
    calcPatch: { type: 'house', floors: 2, wallType: 'brick', package: 'turnkey', area: 205, rooms: 6 },
    examples: [
      'Классический кирпичный дом с симметричным фасадом',
      'Дом из клинкерного кирпича',
      'Дом с кирпичным фасадом и каменным цоколем',
      'Дом с гаражом в общем объеме',
      'Дом с колоннами/крыльцом без лишнего декора',
      'Дом с мансардным вторым этажом',
      'Дом с эркером и большой гостиной',
      'Дом с теплой кровлей и полноценным вторым этажом',
      'Дом с кирпичным забором и единой входной группой',
      'Дом в классическом стиле для постоянного проживания',
    ],
  },
  {
    id: 'garage-house',
    title: 'Двухэтажный дом с гаражом',
    text: 'Дом, гараж и хозяйственные зоны в одной удобной схеме.',
    image: 'https://images.unsplash.com/photo-1600607688969-a5bfcd646154?auto=format&fit=crop&w=900&q=82',
    tags: ['гараж', 'хозблок', 'семья'],
    calcPatch: { type: 'house', floors: 2, wallType: 'gasblock', package: 'turnkey', area: 220, rooms: 5 },
    examples: [
      'Дом с встроенным гаражом на одну машину',
      'Дом с гаражом на две машины',
      'Дом с гаражом и мастерской',
      'Дом с гаражом и кладовой для инструмента',
      'Дом с жилой комнатой над гаражом',
      'Дом с навесом перед гаражом',
      'Дом с боковым въездом в гараж',
      'Дом с отдельным входом из гаража в дом',
      'Дом с хозяйственным блоком рядом с гаражом',
      'Дом с гаражом, котельной и прачечной в одном блоке',
    ],
  },
  {
    id: 'townhouse',
    title: 'Компактный таунхаус',
    text: 'Секции для городской жизни, инвестиций или семейного формата.',
    image: 'https://images.unsplash.com/photo-1600566752229-250ed79470f8?auto=format&fit=crop&w=900&q=82',
    tags: ['таунхаус', 'секции', 'компактно'],
    calcPatch: { type: 'house', floors: 2, wallType: 'brick', package: 'warm', area: 115, rooms: 4 },
    examples: [
      'Таунхаус на 2 секции',
      'Таунхаус на 4 секции',
      'Угловая секция с увеличенным участком',
      'Секция с индивидуальным парковочным местом',
      'Секция с маленьким задним двориком',
      'Таунхаус под сдачу в аренду',
      'Таунхаус для молодой семьи',
      'Таунхаус с общей архитектурной линией фасада',
      'Таунхаус с отдельными входными группами',
      'Таунхаус с отделкой white box',
    ],
  },
  {
    id: 'cottage-reconstruction',
    title: 'Реконструкция коттеджа',
    text: 'Обновление старого дома: фасад, кровля, инженерия, планировка.',
    image: 'https://images.unsplash.com/photo-1581094288338-2314dddb7ece?auto=format&fit=crop&w=900&q=82',
    tags: ['реконструкция', 'до/после', 'инженерия'],
    calcPatch: { type: 'reconstruction', reconstructionScope: 'house', area: 170, rooms: 5, roofTouch: true, engineeringNew: true },
    examples: [
      'Обновление старого кирпичного фасада',
      'Усиление и замена кровли',
      'Пристройка террасы к существующему дому',
      'Переделка холодного чердака в жилую мансарду',
      'Замена окон и утепление откосов',
      'Утепление фасада с новой финишной отделкой',
      'Перепланировка первого этажа под кухню-гостиную',
      'Замена инженерных коммуникаций',
      'Обновление входной группы и крыльца',
      'Комплексная реконструкция до/после',
    ],
  },
  {
    id: 'facade',
    title: 'Ремонт и отделка фасада',
    text: 'Фасад, утепление, декоративная отделка и аккуратный внешний вид дома.',
    image: 'https://images.unsplash.com/photo-1503387762-592deb58ef4e?auto=format&fit=crop&w=900&q=82',
    tags: ['фасад', 'утепление', 'отделка'],
    calcPatch: { type: 'reconstruction', reconstructionScope: 'facade', area: 180, rooms: 1, roofTouch: false, engineeringNew: false },
    examples: [
      'Декоративная штукатурка фасада',
      'Утепление фасада под штукатурку',
      'Вентилируемый фасад',
      'Фасад из клинкерной плитки',
      'Отделка цоколя камнем',
      'Покраска фасада с восстановлением трещин',
      'Обновление откосов, отливов и водостока',
      'Комбинированный фасад: штукатурка + дерево',
      'Фасад с наружной подсветкой',
      'Ремонт фасада после усадки/трещин',
    ],
  },
  {
    id: 'roof',
    title: 'Ремонт кровли',
    text: 'Замена покрытия, утепление, водосток, примыкания и безопасность.',
    image: 'https://images.unsplash.com/photo-1541976590-713941681591?auto=format&fit=crop&w=900&q=82',
    tags: ['кровля', 'утепление', 'водосток'],
    calcPatch: { type: 'reconstruction', reconstructionScope: 'roof', area: 150, rooms: 1, roofTouch: true, engineeringNew: false },
    examples: [
      'Замена старого покрытия на металлочерепицу',
      'Замена покрытия на мягкую кровлю',
      'Ремонт протечек и примыканий',
      'Усиление стропильной системы',
      'Утепление кровли и чердака',
      'Монтаж водосточной системы',
      'Установка снегозадержателей',
      'Монтаж мансардных окон',
      'Ремонт карнизов и подшивы',
      'Полная кровля под ключ с демонтажом старой',
    ],
  },
  {
    id: 'apartment-repair',
    title: 'Ремонт квартиры',
    text: 'Новостройка, вторичка, капитальный или быстрый ремонт под задачу.',
    image: 'https://images.unsplash.com/photo-1600607687920-4e2a09cf159d?auto=format&fit=crop&w=900&q=82',
    tags: ['квартира', 'ремонт', 'чистовая'],
    calcPatch: { type: 'repair', repairObject: 'apartment', repairLevel: 'capital', area: 72, rooms: 3, bathrooms: 1 },
    examples: [
      'Ремонт квартиры в новостройке',
      'Ремонт квартиры под сдачу',
      'Капитальный ремонт старой квартиры',
      'Ремонт студии',
      'Ремонт однокомнатной квартиры',
      'Ремонт двухкомнатной квартиры',
      'Ремонт квартиры с перепланировкой',
      'Ремонт квартиры с заменой электрики',
      'Ремонт квартиры с выравниванием стен и полов',
      'Чистовая отделка после черновых работ',
    ],
  },
  {
    id: 'private-house-finish',
    title: 'Отделка частного дома',
    text: 'Дом после коробки: черновая, чистовая отделка и подготовка к проживанию.',
    image: 'https://images.unsplash.com/photo-1600566753151-384129cf4e3e?auto=format&fit=crop&w=900&q=82',
    tags: ['частный дом', 'отделка', 'заехать жить'],
    calcPatch: { type: 'repair', repairObject: 'privateHouse', repairLevel: 'capital', area: 150, rooms: 5, bathrooms: 2 },
    examples: [
      'Отделка дома после коробки',
      'Черновая отделка дома',
      'Чистовая отделка дома',
      'Монтаж гипсокартона и перегородок',
      'Устройство теплых полов',
      'Укладка плитки и напольных покрытий',
      'Монтаж лестницы и ограждений',
      'Отделка гостиной и кухни',
      'Отделка спален и санузлов',
      'Комплексная отделка заехать и жить',
    ],
  },
  {
    id: 'bathroom',
    title: 'Ремонт ванной комнаты',
    text: 'Плитка, сантехника, гидроизоляция и аккуратные узлы.',
    image: 'https://images.unsplash.com/photo-1600566752355-35792bedcfea?auto=format&fit=crop&w=900&q=82',
    tags: ['санузел', 'плитка', 'сантехника'],
    calcPatch: { type: 'repair', repairObject: 'apartment', repairLevel: 'capital', area: 8, rooms: 1, bathrooms: 1, tiles: true },
    examples: [
      'Маленькая ванная в квартире',
      'Совмещенный санузел',
      'Гостевой санузел',
      'Ванная с душевой зоной',
      'Ванная с полноценной чашей',
      'Гидроизоляция и подготовка основания',
      'Укладка керамогранита крупного формата',
      'Скрытые люки и ревизии',
      'Теплый пол и полотенцесушитель',
      'Полный санузел под ключ',
    ],
  },
  {
    id: 'kitchen-living',
    title: 'Ремонт кухни и гостиной',
    text: 'Главная семейная зона: свет, электрика, полы, стены и финишная отделка.',
    image: 'https://images.unsplash.com/photo-1600210491892-03d54c0aaf87?auto=format&fit=crop&w=900&q=82',
    tags: ['кухня-гостиная', 'свет', 'семья'],
    calcPatch: { type: 'repair', repairObject: 'apartment', repairLevel: 'designer', area: 42, rooms: 1, bathrooms: 0 },
    examples: [
      'Кухня-гостиная в квартире',
      'Кухня-гостиная в частном доме',
      'Кухня с островом',
      'Гостиная с ТВ-зоной',
      'Зонирование кухни и отдыха освещением',
      'Отделка стен под покраску',
      'Укладка пола в едином контуре',
      'Подготовка электрики под кухонный гарнитур',
      'Монтаж фартука и рабочей зоны',
      'Комплексная отделка семейной зоны',
    ],
  },
  {
    id: 'office',
    title: 'Ремонт офисных помещений',
    text: 'Офисы и коммерческие помещения под работу команды и прием клиентов.',
    image: 'https://images.unsplash.com/photo-1497366754035-f200968a6e72?auto=format&fit=crop&w=900&q=82',
    tags: ['офис', 'коммерция', 'сроки'],
    calcPatch: { type: 'commerce', commerceType: 'office', commerceLevel: 'opening', area: 180, rooms: 6 },
    examples: [
      'Open space для команды',
      'Кабинетный офис',
      'Ресепшен и входная зона',
      'Переговорная комната',
      'Ремонт офиса без остановки работы',
      'Замена напольных покрытий',
      'Потолки, свет и рабочие зоны',
      'Электрика и слаботочные сети',
      'Стеклянные перегородки',
      'Офис под ключ для заезда сотрудников',
    ],
  },
];

export const readyProjectCardsByDirection = {
  'one-floor-modern': [
    {
      code: 'H1-01',
      title: 'Одноэтажный кирпичный дом 110 м2',
      area: '110 м2',
      floors: '1 этаж',
      layout: 'Кухня-гостиная 45,8 м2, 3 спальни, ванная, санузел, гардеробная, кладовая, прихожая.',
      visuals: 'Реальный 3D-фасад, второй ракурс и обмерный план 110 м2.',
      media: [
        { id: 'render-front', kind: 'image', role: 'render', label: '3D фасад', src: '/site-assets/projects/h1-01/facade.webp' },
        { id: 'render-side', kind: 'image', role: 'render', label: '3D боковой', src: '/site-assets/projects/h1-01/side.webp' },
        { id: 'plan-1', kind: 'image', role: 'plan', label: 'Планировка', src: '/site-assets/projects/h1-01/plan.png' },
      ],
      calcPatch: { area: 110, floors: 1, rooms: 4, bedrooms: 3, wallType: 'brick', package: 'turnkey' },
    },
    {
      code: 'H1-02',
      title: 'Дом 116 м2 с кухней-гостиной',
      area: '116 м2',
      floors: '1 этаж',
      layout: 'Кухня-гостиная 36,9 м2, 3 спальни, две ванные, кладовая, гардеробные и прихожая.',
      visuals: 'Фасады из рабочего альбома, второй ракурс и план М 1:100.',
      media: [
        { id: 'render-front', kind: 'image', role: 'render', label: '3D фасад', src: '/site-assets/projects/h1-02/facade.webp' },
        { id: 'render-side', kind: 'image', role: 'render', label: '3D боковой', src: '/site-assets/projects/h1-02/side.webp' },
        { id: 'plan-1', kind: 'image', role: 'plan', label: 'Планировка', src: '/site-assets/projects/h1-02/plan.png' },
      ],
      calcPatch: { area: 116, floors: 1, rooms: 4, bedrooms: 3, wallType: 'brick', package: 'turnkey' },
    },
    {
      code: 'H1-03',
      title: 'Современный дом 100 м2 с плоской кровлей',
      area: '100 м2',
      floors: '1 этаж',
      layout: 'Кухня-гостиная 35,1 м2, 3 спальни, ванная, санузел, техническое помещение и входная зона.',
      visuals: 'Современный плоский фасад, перспективный вид и план из рабочего альбома.',
      media: [
        { id: 'render-front', kind: 'image', role: 'render', label: '3D фасад', src: '/site-assets/projects/h1-03/facade.webp' },
        { id: 'render-side', kind: 'image', role: 'render', label: '3D боковой', src: '/site-assets/projects/h1-03/side.webp' },
        { id: 'plan-1', kind: 'image', role: 'plan', label: 'Планировка', src: '/site-assets/projects/h1-03/plan.png' },
      ],
      calcPatch: { area: 100, floors: 1, rooms: 4, bedrooms: 3, wallType: 'gasblock', package: 'turnkey' },
    },
  ],
  'one-floor-brick': [
    {
      code: 'B1-01',
      title: 'Кирпичный дом 110 м2 с кухней-гостиной',
      area: '110 м2',
      floors: '1 этаж',
      layout: 'Кухня-гостиная 45,8 м2, 3 спальни, ванная, санузел, гардеробная и кладовая.',
      visuals: 'Реальный 3D-фасад в светлом кирпиче, второй ракурс и обмерный план 110 м2.',
      media: [
        { id: 'render-front', kind: 'image', role: 'render', label: '3D фасад', src: '/site-assets/projects/b1-01/facade.webp' },
        { id: 'render-side', kind: 'image', role: 'render', label: '3D боковой', src: '/site-assets/projects/b1-01/side.webp' },
        { id: 'plan-1', kind: 'image', role: 'plan', label: 'Планировка', src: '/site-assets/projects/b1-01/plan.png' },
      ],
      calcPatch: { area: 110, floors: 1, rooms: 4, bedrooms: 3, wallType: 'brick', package: 'turnkey' },
    },
    {
      code: 'B1-02',
      title: 'Дом 138 м2 с эркером',
      area: '138 м2',
      floors: '1 этаж',
      layout: 'Гостиная с эркером, 3 спальни, кабинет, 2 санузла.',
      visuals: 'Кирпичный фасад с эркером, второй ракурс и план 138 м2.',
      media: [
        { id: 'render-front', kind: 'image', role: 'render', label: '3D фасад', src: '/site-assets/projects/b1-02/facade.webp' },
        { id: 'render-side', kind: 'image', role: 'render', label: '3D боковой', src: '/site-assets/projects/b1-02/side.webp' },
        { id: 'plan-1', kind: 'image', role: 'plan', label: 'Планировка', src: '/site-assets/projects/b1-02/plan.png' },
      ],
      calcPatch: { area: 138, floors: 1, rooms: 5, bedrooms: 3, wallType: 'brick', package: 'turnkey' },
    },
    {
      code: 'B1-03',
      title: 'Кирпичный дом 155 м2 с террасой',
      area: '155 м2',
      floors: '1 этаж',
      layout: 'Кухня-гостиная с выходом на террасу, 4 спальни, 2 санузла.',
      visuals: 'Кирпич, терраса, второй ракурс и план 155 м2.',
      media: [
        { id: 'render-front', kind: 'image', role: 'render', label: '3D фасад', src: '/site-assets/projects/b1-03/facade.webp' },
        { id: 'render-side', kind: 'image', role: 'render', label: '3D терраса', src: '/site-assets/projects/b1-03/side.webp' },
        { id: 'plan-1', kind: 'image', role: 'plan', label: 'Планировка', src: '/site-assets/projects/b1-03/plan.png' },
      ],
      calcPatch: { area: 155, floors: 1, rooms: 5, bedrooms: 4, wallType: 'brick', package: 'turnkey' },
    },
  ],
  'family-cottage': [
    {
      code: 'FAM-01',
      title: 'Семейный дом 116 м2 с тремя спальнями',
      area: '116 м2',
      floors: '1 этаж',
      layout: 'Кухня-гостиная 36,9 м2, 3 спальни, две ванные, кладовая и гардеробные.',
      visuals: 'Рабочий альбом: фасады, второй ракурс и план М 1:100.',
      media: [
        { id: 'render-front', kind: 'image', role: 'render', label: '3D фасад', src: '/site-assets/projects/fam-01/facade.webp' },
        { id: 'render-side', kind: 'image', role: 'render', label: '3D боковой', src: '/site-assets/projects/fam-01/side.webp' },
        { id: 'plan-1', kind: 'image', role: 'plan', label: 'Планировка', src: '/site-assets/projects/fam-01/plan.png' },
      ],
      calcPatch: { area: 116, floors: 1, rooms: 4, bedrooms: 3, wallType: 'brick', package: 'turnkey' },
    },
    {
      code: 'FAM-02',
      title: 'Коттедж 170 м2 со вторым светом',
      area: '170 м2',
      floors: '1 этаж',
      layout: 'Гостиная со вторым светом, 3 спальни, кабинет, 2 санузла.',
      visuals: 'Высокая гостиная, второй ракурс и план 170 м2.',
      media: [
        { id: 'render-front', kind: 'image', role: 'render', label: '3D фасад', src: '/site-assets/projects/fam-02/facade.webp' },
        { id: 'render-side', kind: 'image', role: 'render', label: '3D боковой', src: '/site-assets/projects/fam-02/side.webp' },
        { id: 'plan-1', kind: 'image', role: 'plan', label: 'Планировка', src: '/site-assets/projects/fam-02/plan.png' },
      ],
      calcPatch: { area: 170, floors: 1, rooms: 5, bedrooms: 3, wallType: 'gasblock', package: 'turnkey' },
    },
    {
      code: 'FAM-03',
      title: 'Коттедж 185 м2 с гостевой комнатой',
      area: '185 м2',
      floors: '1 этаж',
      layout: '4 спальни, гостевая, кухня-гостиная, постирочная.',
      visuals: 'Терраса, второй ракурс и план 185 м2.',
      media: [
        { id: 'render-front', kind: 'image', role: 'render', label: '3D фасад', src: '/site-assets/projects/fam-03/facade.webp' },
        { id: 'render-side', kind: 'image', role: 'render', label: '3D терраса', src: '/site-assets/projects/fam-03/side.webp' },
        { id: 'plan-1', kind: 'image', role: 'plan', label: 'Планировка', src: '/site-assets/projects/fam-03/plan.png' },
      ],
      calcPatch: { area: 185, floors: 1, rooms: 6, bedrooms: 5, wallType: 'gasblock', package: 'turnkey' },
    },
  ],
  'two-floor-modern': [
    { code: 'H2-01', title: 'Двухэтажный дом 222 м2 в Ставрополе', area: '222 м2', floors: '2 этажа', layout: '1 этаж: кухня-столовая, гостиная, кабинет, терраса и хоззоны. 2 этаж: мастер-спальня, 2 спальни, гардеробные и санузлы.', visuals: 'Фасадные листы и планы 1/2 этажа из архитектурного альбома.', calcPatch: { area: 222, floors: 2, rooms: 6, bedrooms: 3, wallType: 'gasblock', package: 'turnkey' } },
    { code: 'H2-02', title: 'Дом 174 м2 с четырьмя спальнями', area: '174 м2', floors: '2 этажа', layout: '1 этаж: кухня-гостиная, кабинет, котельная. 2 этаж: 4 спальни, санузел, два балкона.', visuals: 'Фасад с балконами и планы этажей.', calcPatch: { area: 174, floors: 2, rooms: 6, bedrooms: 4, wallType: 'gasblock', package: 'turnkey' } },
    { code: 'H2-03', title: 'Дом 235 м2 с террасой и балконом', area: '235 м2', floors: '2 этажа', layout: 'Большая кухня-гостиная, кабинет, мастер-спальня, 3 спальни, балкон, терраса.', visuals: 'Большой современный фасад и планы этажей.', calcPatch: { area: 235, floors: 2, rooms: 6, bedrooms: 4, wallType: 'gasblock', package: 'turnkey' } },
  ],
  'two-floor-brick': [
    { code: 'B2-01', title: 'Капитальный дом 222 м2 с террасой', area: '222 м2', floors: '2 этажа', layout: '1 этаж: кухня-столовая, гостиная, кабинет, терраса и хоззоны. 2 этаж: 3 спальни, гардеробные и санузлы.', visuals: 'Архитектурные фасады и планы 1/2 этажа.', calcPatch: { area: 222, floors: 2, rooms: 6, bedrooms: 3, wallType: 'brick', package: 'turnkey' } },
    { code: 'B2-02', title: 'Дом 210 м2 с гаражной зоной', area: '210 м2', floors: '2 этажа', layout: '1 этаж: общая зона. 2 этаж: спальни. Отдельный хозблок.', visuals: 'Фасад + план 1/2 этажа.', calcPatch: { area: 210, floors: 2, rooms: 5, wallType: 'brick', package: 'turnkey' } },
    { code: 'B2-03', title: 'Классический дом 240 м2', area: '240 м2', floors: '2 этажа', layout: '5 спален, кабинет, большая кухня-гостиная, 3 санузла.', visuals: 'Классический фасад + планы.', calcPatch: { area: 240, floors: 2, rooms: 6, wallType: 'brick', package: 'turnkey' } },
  ],
  'garage-house': [
    { code: 'GAR-01', title: 'Дом 136 м2 с гаражом и террасой', area: '136 м2', floors: '2 этажа', layout: 'Гараж, кухня-гостиная, терраса. 2 этаж: 3 спальни, санузел.', visuals: 'Фасад с гаражом, терраса и планы этажей.', calcPatch: { area: 136, floors: 2, rooms: 4, bedrooms: 3, wallType: 'gasblock', package: 'turnkey' } },
    { code: 'GAR-02', title: 'Дом 193 м2 с гаражом и плоской кровлей', area: '193 м2', floors: '2 этажа', layout: 'Гараж, кабинет, кухня-гостиная, мастер-спальня, 2 спальни, кровля-терраса.', visuals: 'Современный фасад, гараж и планы этажей.', calcPatch: { area: 193, floors: 2, rooms: 5, bedrooms: 3, wallType: 'gasblock', package: 'turnkey' } },
    { code: 'GAR-03', title: 'Дом 218 м2 с гаражом и мастер-спальней', area: '218 м2', floors: '2 этажа', layout: 'Гараж, мастерская, каминная гостиная, гостевая, мастер-спальня и 3 спальни.', visuals: 'Фасад с гаражом, мастерская и планы этажей.', calcPatch: { area: 218, floors: 2, rooms: 6, bedrooms: 5, wallType: 'gasblock', package: 'turnkey' } },
  ],
  townhouse: [
    { code: 'TOWN-01', title: 'Таунхаус 95 м2', area: '95 м2', floors: '2 этажа', layout: '1 этаж: кухня-гостиная. 2 этаж: 2 спальни.', visuals: 'Фасад секции + план.', calcPatch: { area: 95, floors: 2, rooms: 3, wallType: 'brick', package: 'warm' } },
    { code: 'TOWN-02', title: 'Таунхаус 120 м2 для семьи', area: '120 м2', floors: '2 этажа', layout: '3 спальни, кухня-гостиная, 2 санузла.', visuals: 'Фасад секции + планы.', calcPatch: { area: 120, floors: 2, rooms: 4, wallType: 'brick', package: 'warm' } },
    { code: 'TOWN-03', title: 'Таунхаус 135 м2 с кабинетом', area: '135 м2', floors: '2 этажа', layout: 'Кабинет, 3 спальни, кухня-гостиная.', visuals: 'Фасад + план.', calcPatch: { area: 135, floors: 2, rooms: 5, wallType: 'brick', package: 'warm' } },
  ],
  'cottage-reconstruction': [
    { code: 'REC-01', title: 'Реконструкция дома 140 м2', area: '140 м2', floors: '1-2 этажа', layout: 'Фасад, кровля, окна, обновление планировки.', visuals: 'До/после фасада + схема изменений.', calcPatch: { type: 'reconstruction', reconstructionScope: 'house', area: 140, rooms: 4, roofTouch: true, engineeringNew: true } },
    { code: 'REC-02', title: 'Мансарда вместо чердака', area: '80 м2 мансарды', floors: '2 этаж', layout: 'Спальни или кабинет на мансарде, лестница, утепление.', visuals: 'Кровля + план мансарды.', calcPatch: { type: 'reconstruction', reconstructionScope: 'roof', area: 80, rooms: 3, roofTouch: true, engineeringNew: true } },
    { code: 'REC-03', title: 'Пристройка террасы и кухни', area: '+35 м2', floors: '1 этаж', layout: 'Расширение кухни-гостиной и новая терраса.', visuals: 'Фасад с пристройкой + план.', calcPatch: { type: 'reconstruction', reconstructionScope: 'house', area: 35, rooms: 1, roofTouch: false, engineeringNew: false } },
  ],
  facade: [
    { code: 'FAC-01', title: 'Утепление фасада 180 м2', area: '180 м2 фасада', floors: 'дом', layout: 'Утепление, армирование, декоративная штукатурка.', visuals: 'Фасад до/после + узел стены.', calcPatch: { type: 'reconstruction', reconstructionScope: 'facade', area: 180, rooms: 1, roofTouch: false, engineeringNew: false } },
    { code: 'FAC-02', title: 'Фасад штукатурка + дерево', area: '220 м2 фасада', floors: 'дом', layout: 'Комбинированная отделка, подсветка, откосы.', visuals: 'Фасад + цветовая схема.', calcPatch: { type: 'reconstruction', reconstructionScope: 'facade', area: 220, rooms: 1, roofTouch: false, engineeringNew: false } },
    { code: 'FAC-03', title: 'Клинкерный фасад', area: '200 м2 фасада', floors: 'дом', layout: 'Клинкерная плитка, цоколь, отливы.', visuals: 'Фасад + узел цоколя.', calcPatch: { type: 'reconstruction', reconstructionScope: 'facade', area: 200, rooms: 1, roofTouch: false, engineeringNew: false } },
  ],
  roof: [
    { code: 'ROOF-01', title: 'Замена кровли 160 м2', area: '160 м2 кровли', floors: 'дом', layout: 'Демонтаж, обрешетка, металлочерепица, водосток.', visuals: 'Кровля + схема скатов.', calcPatch: { type: 'reconstruction', reconstructionScope: 'roof', area: 160, rooms: 1, roofTouch: true, engineeringNew: false } },
    { code: 'ROOF-02', title: 'Утепленная мансардная кровля', area: '190 м2 кровли', floors: 'мансарда', layout: 'Утепление, пароизоляция, окна, подшива.', visuals: 'Кровля + разрез утепления.', calcPatch: { type: 'reconstruction', reconstructionScope: 'roof', area: 190, rooms: 2, roofTouch: true, engineeringNew: false } },
    { code: 'ROOF-03', title: 'Мягкая кровля 145 м2', area: '145 м2 кровли', floors: 'дом', layout: 'Основание, подкладочный ковер, мягкая черепица.', visuals: 'Кровля + узел примыкания.', calcPatch: { type: 'reconstruction', reconstructionScope: 'roof', area: 145, rooms: 1, roofTouch: true, engineeringNew: false } },
  ],
  'apartment-repair': [
    { code: 'APT-01', title: 'Ремонт квартиры 45 м2', area: '45 м2', floors: 'квартира', layout: 'Кухня, спальня, санузел, прихожая.', visuals: 'Интерьер + план квартиры.', calcPatch: { type: 'repair', repairObject: 'apartment', repairLevel: 'capital', area: 45, rooms: 2, bathrooms: 1 } },
    { code: 'APT-02', title: 'Ремонт квартиры 72 м2', area: '72 м2', floors: 'квартира', layout: 'Кухня-гостиная, 2 спальни, санузел.', visuals: 'Интерьер + план 72 м2.', calcPatch: { type: 'repair', repairObject: 'apartment', repairLevel: 'capital', area: 72, rooms: 3, bathrooms: 1 } },
    { code: 'APT-03', title: 'Ремонт квартиры 95 м2', area: '95 м2', floors: 'квартира', layout: '3 спальни, кухня-гостиная, 2 санузла.', visuals: 'Интерьер + план.', calcPatch: { type: 'repair', repairObject: 'apartment', repairLevel: 'designer', area: 95, rooms: 4, bathrooms: 2 } },
  ],
  'private-house-finish': [
    { code: 'FIN-01', title: 'Отделка дома 120 м2', area: '120 м2', floors: 'дом', layout: 'Черновая и чистовая отделка, 3 спальни, кухня-гостиная.', visuals: 'Интерьер + план дома.', calcPatch: { type: 'repair', repairObject: 'privateHouse', repairLevel: 'capital', area: 120, rooms: 4, bathrooms: 1 } },
    { code: 'FIN-02', title: 'Отделка дома 160 м2', area: '160 м2', floors: 'дом', layout: 'Теплые полы, лестница, 4 спальни, 2 санузла.', visuals: 'Интерьер + план.', calcPatch: { type: 'repair', repairObject: 'privateHouse', repairLevel: 'capital', area: 160, rooms: 5, bathrooms: 2 } },
    { code: 'FIN-03', title: 'Отделка дома 210 м2', area: '210 м2', floors: '2 этажа', layout: 'Лестница, 5 комнат, 3 санузла.', visuals: 'Интерьер + планы этажей.', calcPatch: { type: 'repair', repairObject: 'privateHouse', repairLevel: 'designer', area: 210, rooms: 6, bathrooms: 3 } },
  ],
  bathroom: [
    { code: 'BATH-01', title: 'Санузел 4 м2', area: '4 м2', floors: 'квартира', layout: 'Душ, унитаз, раковина, стиральная зона.', visuals: 'Интерьер + план раскладки.', calcPatch: { type: 'repair', repairObject: 'apartment', repairLevel: 'capital', area: 4, rooms: 1, bathrooms: 1, tiles: true } },
    { code: 'BATH-02', title: 'Ванная 6 м2', area: '6 м2', floors: 'квартира', layout: 'Ванна, инсталляция, тумба, теплый пол.', visuals: 'Интерьер + план раскладки плитки.', calcPatch: { type: 'repair', repairObject: 'apartment', repairLevel: 'capital', area: 6, rooms: 1, bathrooms: 1, tiles: true } },
    { code: 'BATH-03', title: 'Санузел 9 м2 в доме', area: '9 м2', floors: 'дом', layout: 'Душ, ванна, две раковины, скрытые люки.', visuals: 'Интерьер + план.', calcPatch: { type: 'repair', repairObject: 'privateHouse', repairLevel: 'capital', area: 9, rooms: 1, bathrooms: 1, tiles: true } },
  ],
  'kitchen-living': [
    { code: 'KIT-01', title: 'Кухня-гостиная 28 м2', area: '28 м2', floors: 'квартира', layout: 'Кухонная линия, столовая, ТВ-зона.', visuals: 'Интерьер + план мебели.', calcPatch: { type: 'repair', repairObject: 'apartment', repairLevel: 'designer', area: 28, rooms: 1, bathrooms: 0 } },
    { code: 'KIT-02', title: 'Кухня-гостиная 42 м2', area: '42 м2', floors: 'квартира', layout: 'Остров, диванная зона, световые сценарии.', visuals: 'Интерьер + план.', calcPatch: { type: 'repair', repairObject: 'apartment', repairLevel: 'designer', area: 42, rooms: 1, bathrooms: 0 } },
    { code: 'KIT-03', title: 'Кухня-гостиная в доме 55 м2', area: '55 м2', floors: 'дом', layout: 'Остров, камин/ТВ-зона, выход на террасу.', visuals: 'Интерьер + план.', calcPatch: { type: 'repair', repairObject: 'privateHouse', repairLevel: 'designer', area: 55, rooms: 1, bathrooms: 0 } },
  ],
  office: [
    { code: 'OFF-01', title: 'Офис open space 120 м2', area: '120 м2', floors: 'коммерция', layout: '18 рабочих мест, переговорная, кухня, санузел.', visuals: 'Интерьер офиса + план рабочих мест.', calcPatch: { type: 'commerce', commerceType: 'office', commerceLevel: 'opening', area: 120, rooms: 4 } },
    { code: 'OFF-02', title: 'Кабинетный офис 180 м2', area: '180 м2', floors: 'коммерция', layout: '8 кабинетов, ресепшен, переговорная, архив.', visuals: 'Интерьер + план.', calcPatch: { type: 'commerce', commerceType: 'office', commerceLevel: 'opening', area: 180, rooms: 10 } },
    { code: 'OFF-03', title: 'Офис 260 м2 с клиентской зоной', area: '260 м2', floors: 'коммерция', layout: 'Ресепшен, open space, кабинеты, переговорные.', visuals: 'Интерьер + план зонирования.', calcPatch: { type: 'commerce', commerceType: 'office', commerceLevel: 'opening', area: 260, rooms: 12 } },
  ],
};

export const makeProjectMedia = (code, labels, files = ['facade.webp', 'side.webp', 'plan.png']) => {
  const slug = String(code).toLowerCase();
  return files.map((file, index) => ({
    id: index === 0 ? 'render-front' : index === 1 ? 'render-side' : `plan-${index - 1}`,
    kind: 'image',
    role: file.startsWith('plan') ? 'plan' : 'render',
    label: labels[index] || `Вид ${index + 1}`,
    src: `/site-assets/projects/${slug}/${file}`,
  }));
};

export const makeProjectMediaMap = (codes, labels, files) => Object.fromEntries(
  codes.map((code) => [code, makeProjectMedia(code, labels, files)]),
);

export const readyProjectMediaByCode = {
  ...makeProjectMediaMap(
    ['H2-01', 'H2-02', 'H2-03', 'B2-01', 'B2-02', 'B2-03', 'GAR-01', 'GAR-02', 'GAR-03', 'TOWN-01', 'TOWN-02', 'TOWN-03'],
    ['3D фасад', '3D боковой', 'План 1 этажа', 'План 2 этажа'],
    ['facade.webp', 'side.webp', 'plan-1.png', 'plan-2.png'],
  ),
  ...makeProjectMediaMap(
    ['REC-01', 'REC-02', 'REC-03'],
    ['Визуал обновления', 'Узел работ', 'Схема работ'],
  ),
  ...makeProjectMediaMap(
    ['FAC-01', 'FAC-02', 'FAC-03'],
    ['Вид фасада', 'Узел фасада', 'Схема фасада'],
  ),
  ...makeProjectMediaMap(
    ['ROOF-01', 'ROOF-02', 'ROOF-03'],
    ['Вид кровли', 'Узел кровли', 'Схема кровли'],
  ),
  ...makeProjectMediaMap(
    ['APT-01', 'APT-02', 'APT-03', 'FIN-01', 'FIN-02', 'FIN-03', 'BATH-01', 'BATH-02', 'BATH-03', 'KIT-01', 'KIT-02', 'KIT-03', 'OFF-01', 'OFF-02', 'OFF-03'],
    ['Визуал', 'Второй ракурс', 'Планировка'],
  ),
};

export const getReferenceProjectCards = (direction) => {
  const cards = readyProjectCardsByDirection[direction.id];
  if (cards?.length) {
    return cards.map((card) => ({
      ...card,
      media: card.media || readyProjectMediaByCode[card.code],
    }));
  }
  return direction.examples.map((example, index) => ({
    code: `${direction.id}-${index + 1}`,
    title: example,
    area: `${direction.calcPatch.area || ''} м2`.trim(),
    floors: direction.calcPatch.floors ? `${direction.calcPatch.floors} этаж` : 'объект',
    layout: direction.text,
    visuals: 'Фасад/интерьер + планировка.',
    calcPatch: direction.calcPatch,
  }));
};

export const findReferenceProjectByCode = (code) => {
  const target = String(code || '').trim().toUpperCase();
  if (!target) return null;
  for (const direction of referenceDirections) {
    const project = getReferenceProjectCards(direction).find(
      (item) => String(item.code || '').toUpperCase() === target,
    );
    if (project) return { direction, project };
  }
  return null;
};

export const parseProjectArea = (project) => {
  const match = String(project?.area || '').replace(',', '.').match(/(\d+(?:\.\d+)?)/);
  return match ? Number(match[1]) : Number(project?.calcPatch?.area || 120);
};

export const getProjectProfile = (direction, project) => {
  const calc = { ...(direction.calcPatch || {}), ...(project?.calcPatch || {}) };
  const rawFloors = String(project?.floors || '');
  const floors = Number(calc.floors || (rawFloors.includes('2') || rawFloors.includes('мансарда') ? 2 : 1));
  const isRepair = calc.type === 'repair';
  const isCommerce = calc.type === 'commerce';
  const isFacade = calc.reconstructionScope === 'facade';
  const isRoof = calc.reconstructionScope === 'roof';
  const isGarage = direction.id === 'garage-house' || project?.code?.startsWith('GAR-') || /гараж/i.test(project?.title || '');
  const isBrick = calc.wallType === 'brick' || direction.id.includes('brick');
  const visualType = isCommerce
    ? 'office'
    : direction.id === 'bathroom'
      ? 'bathroom'
      : direction.id === 'kitchen-living'
        ? 'kitchen'
        : isRepair
          ? 'interior'
          : isRoof
            ? 'roof'
            : isFacade
              ? 'facade'
              : 'house';
  return {
    floors: Math.max(1, floors || 1),
    isGarage,
    isBrick,
    visualType,
    title: project?.title || direction.title,
  };
};

export const getProjectMediaOptions = (direction, project) => {
  if (Array.isArray(project?.media) && project.media.length) {
    return project.media.map((item, index) => ({
      id: item.id || `media-${index + 1}`,
      kind: item.kind || 'image',
      role: item.role || (item.id?.startsWith('plan') ? 'plan' : 'render'),
      angle: item.angle,
      floor: item.floor,
      label: item.label || `Вид ${index + 1}`,
      src: item.src,
    }));
  }
  const profile = getProjectProfile(direction, project);
  const renderLabel = profile.visualType === 'house'
    ? '3D фасад'
    : profile.visualType === 'roof'
      ? 'Ракурс кровли'
      : profile.visualType === 'facade'
        ? 'Фасад'
        : 'Визуал';
  const secondLabel = profile.visualType === 'house'
    ? '3D боковой'
    : profile.visualType === 'roof'
      ? 'Узел кровли'
      : profile.visualType === 'facade'
        ? 'Фасад сбоку'
        : 'Второй ракурс';
  const planLabel = profile.floors > 1 ? 'План 1 этажа' : 'Планировка';
  return [
    { id: 'render-front', kind: 'render', angle: 'front', label: renderLabel },
    { id: 'render-side', kind: 'render', angle: 'side', label: secondLabel },
    { id: 'plan-1', kind: 'plan', floor: 1, label: planLabel },
    ...(profile.floors > 1 ? [{ id: 'plan-2', kind: 'plan', floor: 2, label: 'План 2 этажа' }] : []),
  ];
};

export const getProjectSpecs = (direction, project) => {
  const area = parseProjectArea(project);
  const floors = Number(project?.calcPatch?.floors || direction.calcPatch?.floors || 1);
  const rooms = Number(project?.calcPatch?.rooms || direction.calcPatch?.rooms || 1);
  const type = project?.calcPatch?.type || direction.calcPatch?.type || 'house';
  const isHouse = type === 'house';
  const isRepair = type === 'repair';
  const isFacade = project?.calcPatch?.reconstructionScope === 'facade';
  const isRoof = project?.calcPatch?.reconstructionScope === 'roof';
  const isGarage = direction.id === 'garage-house' || project?.code?.startsWith('GAR-');
  const explicitBedrooms = Number(project?.calcPatch?.bedrooms ?? direction.calcPatch?.bedrooms);
  const bedroomMatches = String(project?.layout || '').toLowerCase().matchAll(/(\d+)\s*(?:спальн|детск)/g);
  const layoutBedrooms = [...bedroomMatches].reduce((sum, match) => sum + Number(match[1] || 0), 0)
    + (/мастер[-\s]?спальн/.test(String(project?.layout || '').toLowerCase()) ? 1 : 0);
  const bedrooms = Number.isFinite(explicitBedrooms)
    ? explicitBedrooms
    : layoutBedrooms || (isHouse ? Math.max(1, rooms - 2) : Math.max(0, rooms - 1));
  const width = Math.max(8.5, Math.sqrt(area * 0.85)).toFixed(1).replace('.', ',');
  const length = Math.max(9.5, area / Number(width.replace(',', '.'))).toFixed(1).replace('.', ',');
  const wallMaterial = project?.calcPatch?.wallType === 'brick'
    ? 'кирпич / клинкер'
    : isRepair
      ? 'существующее основание'
      : 'пеноблок / газобетон';
  const finish = isFacade
    ? 'утепление / штукатурка'
    : isRoof
      ? 'кровельное покрытие'
      : isRepair
        ? 'чистовая / инженерия'
        : 'панели / штукатурка';

  return [
    ['Общая площадь', project?.area || `${area} м2`],
    ['Жилая площадь', isHouse ? `${Math.round(area * 0.42)} м2` : `${Math.round(area * 0.72)} м2`],
    ['Размеры', isHouse ? `${width} x ${length} м` : project?.floors || 'по объекту'],
    ['Высота здания', isHouse ? `${floors === 1 ? '4,1' : '7,9'} м` : 'по месту'],
    ['Количество комнат', String(Math.max(rooms, 1))],
    ['Количество спален', isHouse ? String(bedrooms) : 'по задаче'],
    ['Гараж', isGarage ? 'есть' : 'нет'],
    ['Отделка', finish],
    ['Материал стен', wallMaterial],
    ['Фундамент', isHouse ? 'монолитная плита' : 'существующий'],
    ['Перекрытия', floors > 1 ? 'монолитные' : 'по проекту'],
  ];
};

export const splitLayoutItems = (value) => String(value || '')
  .replace(/\s+/g, ' ')
  .split(/[,;]+/)
  .map((item) => item.trim().replace(/\.$/, ''))
  .filter(Boolean)
  .slice(0, 8);

export const getProjectLayoutGroups = (direction, project) => {
  const calc = { ...(direction?.calcPatch || {}), ...(project?.calcPatch || {}) };
  const layout = String(project?.layout || direction?.text || '').trim();
  const type = calc.type || 'house';
  const floorMatches = [...layout.matchAll(/(\d)\s*этаж:\s*([^.]*)/gi)];

  if (floorMatches.length) {
    return floorMatches.map((match) => ({
      title: `${match[1]} этаж`,
      items: splitLayoutItems(match[2]),
    })).filter((group) => group.items.length);
  }

  const title = type === 'commerce'
    ? 'Зоны объекта'
    : type === 'repair'
      ? 'Помещения'
      : type === 'reconstruction'
        ? 'Состав работ'
        : 'Планировка';
  const items = splitLayoutItems(layout)
    .map((item) => item.replace(/^и\s+/i, ''));

  return [{
    title,
    items: items.length ? items : splitLayoutItems(direction?.text || project?.title),
  }];
};

export const referenceHouseObjectCardPackages = {
  'one-floor-modern': {
    status: 'Карточка современного дома',
    format: 'Одноэтажный современный дом',
    accent: 'терраса / панорама',
    summary: ({ title, wall, floors, rooms }) => `${title}: ${wall}, ${floors} эт., ${rooms} комн., акцент на светлую кухню-гостиную, террасу и понятную посадку на участок.`,
    stages: ['Посадка на участок', 'Планировка семьи', 'Фасады и терраса', 'Смета под ключ'],
    deliverables: ['3D фасады', 'Планировка', 'Терраса и вход', 'Расчет комплектации'],
  },
  'one-floor-brick': {
    status: 'Карточка кирпичного дома',
    format: 'Одноэтажный дом из кирпича',
    accent: 'кирпич / надежность',
    summary: ({ title, floors, rooms }) => `${title}: капитальный кирпичный дом, ${floors} эт., ${rooms} комн., с упором на долговечность, кровлю, цоколь и аккуратную входную группу.`,
    stages: ['Посадка и цоколь', 'Планировка', 'Кирпичный фасад', 'Смета и узлы'],
    deliverables: ['Фасад из кирпича', 'План дома', 'Узлы кровли', 'Расчет материалов'],
  },
  'family-cottage': {
    status: 'Карточка семейного коттеджа',
    format: 'Семейный коттедж',
    accent: 'семья / двор',
    summary: ({ title, rooms }) => `${title}: сценарий постоянного проживания, ${rooms} комн., общая семейная зона, спальни, хранение и выход во двор без лишних проходов.`,
    stages: ['Сценарии семьи', 'Планировка зон', 'Фасады и двор', 'Смета проживания'],
    deliverables: ['Семейная планировка', '3D двор', 'Хоззоны', 'Расчет под ключ'],
  },
  'two-floor-modern': {
    status: 'Карточка современного двухэтажного дома',
    format: 'Двухэтажный современный дом',
    accent: '2 этажа / панорама',
    summary: ({ title, wall, rooms }) => `${title}: ${wall}, ${rooms} комн., компактная посадка на участок, первый этаж под общую зону и второй этаж под приватные комнаты.`,
    stages: ['Габариты участка', 'Планы 1/2 этажа', 'Современный фасад', 'Смета по этапам'],
    deliverables: ['3D фасады', 'Планы этажей', 'Разрез / второй свет', 'Бюджет строительства'],
  },
  'two-floor-brick': {
    status: 'Карточка капитального двухэтажного дома',
    format: 'Двухэтажный дом из кирпича',
    accent: 'кирпич / статус',
    summary: ({ title, rooms }) => `${title}: капитальный двухэтажный дом, ${rooms} комн., с классическим фасадом, надежной кровлей и полноценной семейной планировкой.`,
    stages: ['Фундамент и стены', 'Планировка этажей', 'Кирпичный фасад', 'Смета конструкций'],
    deliverables: ['Кирпичные фасады', 'Планы 1/2 этажа', 'Узлы цоколя', 'Расчет коробки'],
  },
  'garage-house': {
    status: 'Карточка дома с гаражом',
    format: 'Двухэтажный дом с гаражом',
    accent: 'гараж / хозблок',
    summary: ({ title, rooms }) => `${title}: дом, гараж и хозяйственные зоны в одной схеме, ${rooms} комн., с удобным входом из гаража и понятной логикой хранения.`,
    stages: ['Въезд и посадка', 'Гаражный блок', 'Жилая зона', 'Смета дома и гаража'],
    deliverables: ['Фасад с гаражом', 'Планы этажей', 'Схема въезда', 'Расчет хозблока'],
  },
  townhouse: {
    status: 'Карточка таунхауса',
    format: 'Компактный таунхаус',
    accent: 'секции / компактно',
    summary: ({ title, rooms }) => `${title}: компактная секция, ${rooms} комн., с отдельным входом, понятным первым этажом и приватной зоной на втором этаже.`,
    stages: ['Секция и участок', 'Планы этажей', 'Фасадная линия', 'Смета секции'],
    deliverables: ['Фасад секции', 'Планы 1/2 этажа', 'Схема парковки', 'Расчет white box'],
  },
};

export const referenceReconstructionObjectCardPackages = {
  'cottage-reconstruction': {
    status: 'Карточка реконструкции дома',
    format: 'Реконструкция коттеджа',
    accent: 'до/после',
    summary: ({ title }) => `${title}: сначала фиксируем состояние дома, затем считаем демонтаж, усиления, новые узлы, инженерные изменения и очередность работ.`,
    stages: ['Обследование', 'Дефектовка', 'Проект узлов', 'Смета по этапам'],
    deliverables: ['Фото до/после', 'Схема изменений', 'Ведомость демонтажа', 'План контроля'],
  },
  facade: {
    status: 'Карточка фасадных работ',
    format: 'Ремонт и отделка фасада',
    accent: 'фасад / утепление',
    summary: ({ title }) => `${title}: считаем площадь фасада, утепление, армирование, финишную отделку, цоколь, откосы, отливы и места примыканий.`,
    stages: ['Обмер фасада', 'Выбор системы', 'Узлы и материалы', 'Смета фасада'],
    deliverables: ['Схема фасада', 'Узлы цоколя', 'Цветовое решение', 'Расчет материалов'],
  },
  roof: {
    status: 'Карточка кровельных работ',
    format: 'Ремонт кровли',
    accent: 'кровля / водосток',
    summary: ({ title }) => `${title}: фиксируем скаты, примыкания, утепление, водосток, безопасность и считаем работы с демонтажом старого покрытия.`,
    stages: ['Осмотр кровли', 'Схема скатов', 'Материалы и узлы', 'Смета кровли'],
    deliverables: ['Схема кровли', 'Узлы примыканий', 'Ведомость материалов', 'График монтажа'],
  },
};

export const referenceInteriorObjectCardPackages = {
  'apartment-repair': {
    status: 'Карточка ремонта квартиры',
    format: 'Ремонт квартиры',
    accent: 'квартира / чистовая',
    summary: ({ title }) => `${title}: фиксируем планировку, состояние основания, инженерные точки, отделку по комнатам и формируем расчет до понятного результата.`,
    stages: ['Замер квартиры', 'План работ', 'Материалы по комнатам', 'Смета ремонта'],
    deliverables: ['План квартиры', 'Ведомость отделки', 'Список материалов', 'График работ'],
  },
  'private-house-finish': {
    status: 'Карточка отделки дома',
    format: 'Отделка частного дома',
    accent: 'дом / заехать жить',
    summary: ({ title }) => `${title}: отделка после коробки с инженерией, полами, стенами, санузлами, лестницей и подготовкой дома к проживанию.`,
    stages: ['Осмотр коробки', 'Инженерия', 'Черновая отделка', 'Чистовая комплектация'],
    deliverables: ['План отделки', 'Инженерные точки', 'Ведомость материалов', 'Смета заехать жить'],
  },
  bathroom: {
    status: 'Карточка санузла',
    format: 'Ремонт ванной комнаты',
    accent: 'плитка / сантехника',
    summary: ({ title }) => `${title}: считаем гидроизоляцию, плитку, сантехнику, скрытые узлы, ревизии, теплый пол и аккуратную раскладку.`,
    stages: ['Обмер санузла', 'Раскладка плитки', 'Сантехника и узлы', 'Смета под ключ'],
    deliverables: ['План раскладки', 'Список сантехники', 'Узлы ревизий', 'Расчет плитки'],
  },
  'kitchen-living': {
    status: 'Карточка кухни-гостиной',
    format: 'Ремонт кухни и гостиной',
    accent: 'семейная зона',
    summary: ({ title }) => `${title}: собираем электрику под кухню, световые сценарии, полы, стены, фартук, ТВ-зону и мебельную логику.`,
    stages: ['План мебели', 'Электрика и свет', 'Отделка стен/пола', 'Смета зоны'],
    deliverables: ['План кухни', 'Схема света', 'Ведомость отделки', 'Расчет зоны'],
  },
  office: {
    status: 'Карточка коммерческого ремонта',
    format: 'Ремонт офисных помещений',
    accent: 'офис / запуск',
    summary: ({ title }) => `${title}: зонирование рабочих мест, инженерия, свет, слаботочка, отделка и график запуска помещения без лишней остановки бизнеса.`,
    stages: ['Обмер и ТЗ', 'План зонирования', 'Инженерия и отделка', 'График запуска'],
    deliverables: ['План рабочих мест', 'Ведомость отделки', 'Схема инженерии', 'Смета по этапам'],
  },
};

export const getReferenceObjectCard = (direction, project, estimate) => {
  const calc = { ...(direction?.calcPatch || {}), ...(project?.calcPatch || {}) };
  const area = parseProjectArea(project);
  const rooms = Number(calc.rooms || direction?.calcPatch?.rooms || 1);
  const floors = Number(calc.floors || direction?.calcPatch?.floors || 1);
  const type = calc.type || 'house';
  const isRepair = type === 'repair';
  const isCommerce = type === 'commerce';
  const isReconstruction = type === 'reconstruction';
  const scope = calc.reconstructionScope || '';
  const wall = calc.wallType === 'brick' ? 'кирпич' : calc.wallType === 'monolith' ? 'монолит' : 'газоблок';

  if (isCommerce) {
    const commercePackage = referenceInteriorObjectCardPackages[direction?.id];
    const commerceTitle = project?.title || direction?.title || 'Коммерческий объект';
    return {
      code: project?.code || direction?.id || '',
      format: commercePackage?.format || 'Коммерческий объект',
      status: commercePackage?.status || 'Готовая карточка для расчета',
      summary: commercePackage?.summary?.({ title: commerceTitle, area, rooms }) || `${commerceTitle}: зонирование, инженерия и запуск помещения под работу.`,
      facts: [
        ['Площадь', project?.area || `${area} м2`],
        ['Акцент', commercePackage?.accent || `${Math.max(rooms, 1)} зон`],
        ['Срок', area > 220 ? '75-110 дней' : '45-80 дней'],
        ['Бюджет', estimate?.rangeLabel || 'после замера'],
      ],
      stages: commercePackage?.stages || ['Обмер и ТЗ', 'План зонирования', 'Инженерия и смета', 'График запуска'],
      deliverables: commercePackage?.deliverables || ['План рабочих зон', 'Ведомость отделки', 'Инженерные решения', 'Смета по этапам'],
    };
  }

  if (isRepair) {
    const repairPackage = referenceInteriorObjectCardPackages[direction?.id];
    const repairTitle = project?.title || direction?.title || 'Ремонт помещения';
    return {
      code: project?.code || direction?.id || '',
      format: repairPackage?.format || (calc.repairObject === 'privateHouse' ? 'Отделка дома' : 'Ремонт помещения'),
      status: repairPackage?.status || 'Карточка ремонта',
      summary: repairPackage?.summary?.({ title: repairTitle, area, rooms }) || `${repairTitle}: планировка, отделка и материалы под выбранный уровень работ.`,
      facts: [
        ['Площадь', project?.area || `${area} м2`],
        ['Акцент', repairPackage?.accent || `${Math.max(rooms, 1)} помещ.`],
        ['Срок', area > 120 ? '70-120 дней' : '30-75 дней'],
        ['Бюджет', estimate?.rangeLabel || 'после замера'],
      ],
      stages: repairPackage?.stages || ['Замер', 'План работ', 'Материалы', 'Смета и график'],
      deliverables: repairPackage?.deliverables || ['Планировка', 'Список материалов', 'Работы по комнатам', 'Фотофиксация этапов'],
    };
  }

  if (isReconstruction) {
    const format = scope === 'roof'
      ? 'Кровля / мансарда'
      : scope === 'facade'
        ? 'Фасадные работы'
        : 'Реконструкция дома';
    const reconstructionPackage = referenceReconstructionObjectCardPackages[direction?.id];
    const reconstructionTitle = project?.title || direction?.title || format;
    return {
      code: project?.code || direction?.id || '',
      format: reconstructionPackage?.format || format,
      status: reconstructionPackage?.status || 'Карточка реконструкции',
      summary: reconstructionPackage?.summary?.({ title: reconstructionTitle, area, scope }) || `${reconstructionTitle}: обследование, демонтаж, усиление и поэтапный расчет работ.`,
      facts: [
        ['Объем', project?.area || `${area} м2`],
        ['Акцент', reconstructionPackage?.accent || format],
        ['Срок', scope === 'roof' ? '25-55 дней' : '35-90 дней'],
        ['Бюджет', estimate?.rangeLabel || 'после осмотра'],
      ],
      stages: reconstructionPackage?.stages || ['Осмотр', 'Дефектовка', 'Решение по узлам', 'Смета и этапы'],
      deliverables: reconstructionPackage?.deliverables || ['Схема работ', 'Фото до/после', 'Ведомость материалов', 'План контроля'],
    };
  }

  const housePackage = referenceHouseObjectCardPackages[direction?.id];
  const houseTitle = project?.title || direction?.title || 'Проект дома';
  const defaultHouseSummary = `${houseTitle}: ${wall}, ${floors} эт., ${rooms} комн., расчет под выбранную комплектацию.`;

  return {
    code: project?.code || direction?.id || '',
    format: housePackage?.format || `${floors > 1 ? 'Двухэтажный' : 'Одноэтажный'} дом`,
    status: housePackage?.status || 'Проектная карточка дома',
    summary: housePackage?.summary?.({ title: houseTitle, wall, floors, rooms, area }) || defaultHouseSummary,
    facts: [
      ['Площадь', project?.area || `${area} м2`],
      ['Акцент', housePackage?.accent || project?.floors || `${floors} этаж`],
      ['Комнат', String(Math.max(rooms, 1))],
      ['Бюджет', estimate?.rangeLabel || 'после проекта'],
    ],
    stages: housePackage?.stages || ['Участок и ТЗ', 'Планировка', 'Фасады и конструктив', 'Смета и график'],
    deliverables: housePackage?.deliverables || ['3D ракурсы', 'Планы этажей', 'Паспорт объекта', 'Расчет стоимости'],
  };
};

export const getPlanRooms = (project, floor = 1) => {
  const rawParts = String(project?.layout || '')
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean);
  const secondFloor = ['Холл', 'Мастер-спальня', 'Спальня', 'Спальня', 'Санузел', 'Гардероб'];
  const firstFloor = ['Кухня-гостиная', 'Спальня', 'Спальня', 'Санузел', 'Холл'];
  const fallback = floor > 1 ? secondFloor : firstFloor;
  const parts = floor > 1 ? secondFloor : (rawParts.length ? rawParts : fallback);
  const sizes = floor > 1 ? ['12 м2', '18 м2', '15 м2', '14 м2', '6 м2', '5 м2'] : ['34 м2', '16 м2', '13 м2', '12 м2', '7 м2', '5 м2'];
  return parts.slice(0, 6).map((name, index) => ({
    name,
    size: sizes[index] || '',
    wide: index === 0,
  }));
};

export const ProjectPlanGraphic = ({ project, title, floor = 1 }) => {
  const rooms = getPlanRooms(project, floor);
  return (
    <div className="public-project-plan-hero">
      <strong>{title}</strong>
      <div className="public-project-plan-grid" aria-label={title}>
        {rooms.map((room, index) => (
          <span className={room.wide ? 'wide' : ''} key={`${room.name}-${index}`}>
            <b>{room.name}</b>
            <small>{room.size}</small>
          </span>
        ))}
      </div>
    </div>
  );
};

export const ProjectConceptVisual = ({ direction, project, media }) => {
  const profile = getProjectProfile(direction, project);
  if (media?.src) {
    return (
      <img
        className={`public-project-media-image ${media.role === 'plan' ? 'is-plan' : 'is-render'}`}
        src={media.src}
        alt={`${media.label || 'Визуал'}: ${profile.title}`}
      />
    );
  }
  if (media?.kind === 'plan') {
    return <ProjectPlanGraphic project={project} title={media.label} floor={media.floor} />;
  }
  const className = [
    'public-project-render',
    `render-${profile.visualType}`,
    profile.floors > 1 ? 'floors-2' : 'floors-1',
    profile.isGarage ? 'has-garage' : '',
    profile.isBrick ? 'is-brick' : '',
    media?.angle === 'side' ? 'angle-side' : 'angle-front',
  ].filter(Boolean).join(' ');
  return (
    <div className={className} aria-label={`${media?.label || 'Визуал'}: ${profile.title}`}>
      <span className="render-sky" />
      <span className="render-ground" />
      <span className="render-shadow" />
      <span className="render-main" />
      <span className="render-upper" />
      <span className="render-wing" />
      <span className="render-garage" />
      <span className="render-roof" />
      <span className="render-window window-a" />
      <span className="render-window window-b" />
      <span className="render-window window-c" />
      <span className="render-door" />
      <span className="render-interior-wall" />
      <span className="render-interior-floor" />
      <span className="render-interior-feature feature-a" />
      <span className="render-interior-feature feature-b" />
      <span className="render-interior-feature feature-c" />
      <span className="render-label">{media?.label || 'Визуал'}</span>
    </div>
  );
};

export const ProjectConceptThumb = ({ direction, project }) => {
  const profile = getProjectProfile(direction, project);
  const imageMedia = Array.isArray(project?.media) ? project.media.find((item) => item.src) : null;
  if (imageMedia?.src) {
    return (
      <img
        className="public-project-concept-thumb image-thumb"
        src={imageMedia.src}
        alt=""
      />
    );
  }
  const className = [
    'public-project-concept-thumb',
    `thumb-${profile.visualType}`,
    profile.floors > 1 ? 'floors-2' : 'floors-1',
    profile.isGarage ? 'has-garage' : '',
    profile.isBrick ? 'is-brick' : '',
  ].filter(Boolean).join(' ');
  return (
    <span className={className} aria-hidden="true">
      <i className="thumb-main" />
      <i className="thumb-upper" />
      <i className="thumb-wing" />
      <i className="thumb-garage" />
      <i className="thumb-window one" />
      <i className="thumb-window two" />
    </span>
  );
};

export const getCompactMediaLabel = (media) => {
  if (!media) return 'Вид';
  if (media.role === 'plan' || media.kind === 'plan' || String(media.id || '').startsWith('plan')) return 'План';
  return String(media.label || 'Вид').replace(/^3D\s+/i, '');
};

export const getProjectMediaSequence = (direction, project) => (
  getProjectMediaOptions(direction, project).map((media, index) => ({
    ...media,
    number: index + 1,
    compactLabel: getCompactMediaLabel(media),
  }))
);

export const ProjectCardMediaPreview = ({ direction, project }) => {
  const mediaOptions = getProjectMediaSequence(direction, project).slice(0, 3);
  const primary = mediaOptions[0];
  const secondary = mediaOptions.slice(1);
  return (
    <div className="public-project-card-media" aria-hidden="true">
      <div className="public-project-card-primary">
        <ProjectConceptVisual direction={direction} project={project} media={primary} />
        <span><b>{primary?.number || 1}</b>{primary?.label || '3D фасад'}</span>
      </div>
      <div className="public-project-card-secondary">
        {secondary.map((media) => (
          <div key={media.id}>
            <ProjectConceptVisual direction={direction} project={project} media={media} />
            <span><b>{media.number}</b>{media.compactLabel}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export const partnerTypes = [
  { value: 'supplier', label: 'Поставщик', note: 'Материалы, счета, КП, документы', icon: Handshake },
  { value: 'master', label: 'Мастер', note: 'Сдельные работы, объекты, акты', icon: Hammer },
  { value: 'brigade', label: 'Бригада', note: 'Пакеты работ, закрытия, расчёты', icon: BriefcaseBusiness },
  { value: 'subcontractor', label: 'Субподрядчик', note: 'Договор, объёмы, исполнительная документация', icon: Building2 },
];

export const publicProjects = [
  {
    id: 'mihailovsk-house',
    category: 'house',
    title: 'Дом в Михайловске',
    location: 'Михайловск',
    area: '142 м2',
    year: '2026',
    stage: 'Тёплый контур',
    progress: 68,
    price: 'от 7,6 млн ₽',
    term: '5 месяцев',
    passport: 'Фотоотчеты, материалы, этапы работ',
    result: 'Коробка, кровля, окна, инженерная подготовка',
    tags: ['Дом', 'Тёплый контур', 'Паспорт объекта'],
    images: [
      'https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&q=84',
      'https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?auto=format&fit=crop&w=900&q=82',
      'https://images.unsplash.com/photo-1503387762-592deb58ef4e?auto=format&fit=crop&w=900&q=82',
    ],
  },
  {
    id: 'office-repair',
    category: 'commerce',
    title: 'Ремонт офиса',
    location: 'Ставрополь',
    area: '310 м2',
    year: '2026',
    stage: 'Финишная приёмка',
    progress: 92,
    price: 'от 5,2 млн ₽',
    term: '62 дня',
    passport: 'Фото, инженерия, этапы приемки',
    result: 'Офис под работу команды и приём клиентов',
    tags: ['Офис', 'Инженерия', 'Сроки'],
    images: [
      'https://images.unsplash.com/photo-1497366754035-f200968a6e72?auto=format&fit=crop&w=1200&q=84',
      'https://images.unsplash.com/photo-1497366811353-6870744d04b2?auto=format&fit=crop&w=900&q=82',
      'https://images.unsplash.com/photo-1497215842964-222b430dc094?auto=format&fit=crop&w=900&q=82',
    ],
  },
  {
    id: 'cottage-repair',
    category: 'repair',
    title: 'Коттеджный ремонт',
    location: 'Невинномысск',
    area: '188 м2',
    year: '2025',
    stage: 'Инженерия',
    progress: 45,
    price: 'от 4,1 млн ₽',
    term: '4 месяца',
    passport: 'Электрика, сантехника, фото скрытых работ',
    result: 'Капитальный ремонт с заменой инженерии',
    tags: ['Ремонт', 'Дом', 'Скрытые работы'],
    images: [
      'https://images.unsplash.com/photo-1600607687920-4e2a09cf159d?auto=format&fit=crop&w=1200&q=84',
      'https://images.unsplash.com/photo-1600566752355-35792bedcfea?auto=format&fit=crop&w=900&q=82',
      'https://images.unsplash.com/photo-1600607687644-c7171b42498b?auto=format&fit=crop&w=900&q=82',
    ],
  },
  {
    id: 'shop-fitout',
    category: 'commerce',
    title: 'Помещение под магазин',
    location: 'Пятигорск',
    area: '96 м2',
    year: '2025',
    stage: 'Сдано',
    progress: 100,
    price: 'от 2,4 млн ₽',
    term: '38 дней',
    passport: 'Сроки, отделка, готовность к открытию',
    result: 'Торговый зал, подсобные зоны, освещение',
    tags: ['Коммерция', 'Под открытие', 'Гарантия'],
    images: [
      'https://images.unsplash.com/photo-1604014237800-1c9102c219da?auto=format&fit=crop&w=1200&q=84',
      'https://images.unsplash.com/photo-1600210491892-03d54c0aaf87?auto=format&fit=crop&w=900&q=82',
      'https://images.unsplash.com/photo-1600607688969-a5bfcd646154?auto=format&fit=crop&w=900&q=82',
    ],
  },
];

export const formatMoney = (value) => new Intl.NumberFormat('ru-RU', {
  maximumFractionDigits: 0,
}).format(value);

export const formatCompactMoney = (value) => {
  const amount = Math.max(0, Math.round((Number(value) || 0) / 10000) * 10000);
  if (amount >= 1000000) {
    const millions = amount / 1000000;
    return `${new Intl.NumberFormat('ru-RU', {
      maximumFractionDigits: millions < 10 ? 1 : 0,
    }).format(millions)} млн ₽`;
  }
  if (amount >= 1000) {
    return `${formatMoney(Math.round(amount / 1000))} тыс. ₽`;
  }
  return `${formatMoney(amount)} ₽`;
};

export const publicCalcDefaults = {
  type: 'house',
  area: 140,
  floors: 2,
  wallType: 'gasblock',
  package: 'turnkey',
  stage: 'project',
  foundation: true,
  communications: true,
  deadline: 'normal',
  files: 0,
  repairObject: 'apartment',
  rooms: 3,
  bathrooms: 1,
  ceilingHeight: 2.7,
  repairCondition: 'new',
  repairLevel: 'capital',
  demolition: false,
  electric: true,
  plumbing: true,
  walls: true,
  floorsWork: true,
  ceiling: true,
  tiles: true,
  materialMode: 'partial',
  trash: true,
  commerceType: 'office',
  commerceLevel: 'opening',
  commerceCondition: 'shell',
  ventilation: true,
  fireSafety: false,
  powerEquipment: true,
  designProject: false,
  nightWork: false,
  reconstructionScope: 'house',
  keepsStructure: true,
  reinforcement: true,
  foundationTouch: false,
  roofTouch: true,
  engineeringNew: true,
  inspectionNeeded: true,
};

export const normalizeSiteProject = (project) => {
  const images = Array.isArray(project.images) && project.images.length
    ? project.images
    : (Array.isArray(project.publicImages) ? project.publicImages : []);
  return {
    id: String(project.id || project.projectId || project.title || Math.random()),
    category: project.category || project.publicCategory || 'house',
    title: project.title || project.publicTitle || '',
    location: project.location || project.publicLocation || '',
    area: project.area || project.publicArea || '',
    year: project.year || project.publicYear || '',
    stage: project.stage || project.publicStage || '',
    progress: Math.max(0, Math.min(100, Number(project.progress ?? project.publicProgress ?? 0))),
    price: project.price || project.publicPriceLabel || '',
    term: project.term || project.publicTerm || '',
    passport: project.passport || project.publicPassport || 'Фото, этапы и паспорт объекта',
    summary: project.summary || project.publicSummary || '',
    result: project.result || project.publicResult || project.publicSummary || '',
    tags: Array.isArray(project.tags) ? project.tags : (Array.isArray(project.publicTags) ? project.publicTags : []),
    images,
    isLive: Boolean(project.isLive || project.publicIsLive),
  };
};
