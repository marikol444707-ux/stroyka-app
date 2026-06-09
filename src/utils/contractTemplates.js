const html = (value) => String(value ?? '')
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#039;');

const money = (value) => Math.round(Number(value || 0)).toLocaleString('ru-RU') + ' руб.';

const dateText = (value) => value || '«___» __________ 20__ г.';

const companyInfo = (company, fallbackName = '_____') => {
  if (typeof company === 'string') {
    return {
      name: company || fallbackName,
      director: '_____',
      basis: 'Устава',
      inn: '_______',
      rs: '_______',
      bankName: '_______',
    };
  }

  const req = company || {};
  return {
    name: req.fullName || req.shortName || fallbackName,
    director: req.directorName || '_____',
    basis: req.basis || 'Устава',
    inn: req.inn || '_______',
    rs: req.rs || '_______',
    bankName: req.bankName || '_______',
  };
};

const normalizeType = (type) => String(type || '').toLowerCase();

const isSelfEmployed = (type) => {
  const t = normalizeType(type);
  return t.includes('самозан') || t.includes('нпд');
};

const isLegalContractor = (type) => {
  const t = normalizeType(type);
  return t.includes('ип') || t.includes('ооо') || t.includes('субподряд') || t.includes('подряд');
};

const performerTitle = (type) => {
  if (isSelfEmployed(type)) return 'Исполнитель';
  if (isLegalContractor(type)) return 'Подрядчик';
  return 'Исполнитель';
};

const performerName = (performer, contract) => (
  performer?.fullName || performer?.name || performer?.brigadeName || contract?.brigadeName || contract?.masterName || '________________'
);

const performerRequisites = (performer, type) => {
  const isIp = normalizeType(type).includes('ип');
  const rows = [
    ['ФИО / наименование', performerName(performer, {})],
    ['ИНН', performer?.inn || '_______'],
  ];
  if (isIp || performer?.ogrnip) rows.push(['ОГРНИП', performer?.ogrnip || '_______']);
  if (performer?.bankAccount) rows.push(['Р/с', performer.bankAccount]);
  if (performer?.bankName) rows.push(['Банк', performer.bankName]);
  return rows;
};

const contractItemsTable = (items = []) => {
  const safeItems = (items || []).filter(Boolean);
  if (!safeItems.length) {
    return '<p>Перечень, объёмы и стоимость работ определяются по смете/прайсу, наряду и актам, сформированным в системе.</p>';
  }

  const rows = safeItems.map((item, index) => {
    const qty = Number(item.quantity || item.doneQuantity || 0);
    const price = Number(item.priceBrigade || item.price || item.priceWork || 0);
    const sum = qty * price;
    return '<tr>' +
      '<td>' + (index + 1) + '</td>' +
      '<td>' + html(item.name || item.description || '') + '</td>' +
      '<td>' + html(item.unit || '') + '</td>' +
      '<td style="text-align:right">' + html(qty.toLocaleString('ru-RU', {maximumFractionDigits: 3})) + '</td>' +
      '<td style="text-align:right">' + html(price.toLocaleString('ru-RU')) + '</td>' +
      '<td style="text-align:right">' + html(Math.round(sum).toLocaleString('ru-RU')) + '</td>' +
    '</tr>';
  }).join('');

  const total = safeItems.reduce((sum, item) => {
    const qty = Number(item.quantity || item.doneQuantity || 0);
    const price = Number(item.priceBrigade || item.price || item.priceWork || 0);
    return sum + qty * price;
  }, 0);

  return '<table><tr><th>N</th><th>Работа</th><th>Ед.</th><th>Объём</th><th>Цена</th><th>Сумма</th></tr>' +
    rows +
    '<tr><td colspan="5"><b>ИТОГО по договору:</b></td><td style="text-align:right"><b>' + money(total) + '</b></td></tr></table>';
};

const commonClauses = (type) => {
  const self = isSelfEmployed(type);
  return '' +
    '<h3>2. СТОИМОСТЬ, АКТЫ И ОПЛАТА</h3>' +
    '<p>2.1. Стоимость работ определяется по фактически принятому объёму, указанному в системе, и по согласованным расценкам. Работы без наряда, сметы или письменного согласования не подлежат оплате.</p>' +
    '<p>2.2. Оплата производится после подписания акта выполненных работ, загрузки скана подписанного акта в систему, передачи исполнительной документации, фотофиксации и устранения замечаний.</p>' +
    (self
      ? '<p>2.3. Исполнитель обязан сформировать и передать Заказчику чек НПД через приложение «Мой налог». Оплата без чека НПД не является окончательно закрытой.</p>'
      : '<p>2.3. Исполнитель передаёт Заказчику закрывающие документы, предусмотренные его статусом: акт, счёт, УПД/чек/иной документ, если он применим.</p>') +
    '<p>2.4. Заказчик удерживает <b>5% от полной стоимости фактически принятого объёма работ</b> как гарантийное удержание. Удержание возвращается через <b>1 год после полного исполнения договора</b> и подписания итогового акта, если отсутствуют неустранённые дефекты, претензии и задолженность Исполнителя.</p>' +
    '<p>2.5. Если в гарантийный период Исполнитель не устраняет дефекты в согласованный срок, Заказчик вправе устранить их своими силами или третьими лицами и зачесть расходы из гарантийного удержания.</p>' +
    '<h3>3. КАЧЕСТВО, ИСПОЛНИТЕЛЬНАЯ ДОКУМЕНТАЦИЯ И СКРЫТЫЕ РАБОТЫ</h3>' +
    '<p>3.1. Работы выполняются по проектной документации, смете, строительным нормам, требованиям охраны труда, пожарной и электробезопасности.</p>' +
    '<p>3.2. Скрытые работы не закрываются без фотофиксации и освидетельствования. При необходимости оформляется АОСР, журналы, паспорта, сертификаты и иная исполнительная документация.</p>' +
    '<p>3.3. Если для работ требуется лицензия, допуск или специальное разрешение, Исполнитель подтверждает наличие такого права до начала работ и несёт ответственность за его отсутствие.</p>' +
    '<h3>4. МАТЕРИАЛЫ И СПИСАНИЕ</h3>' +
    '<p>4.1. Давальческие материалы Заказчика передаются Исполнителю только под конкретный объект и работы. Материалы учитываются в системе, списываются по фактически принятому объёму и нормам расхода.</p>' +
    '<p>4.2. Перерасход материалов без подтверждённой причины, потери, порча и использование не на тот объект возмещаются Исполнителем или удерживаются из оплаты.</p>' +
    '<p>4.3. Неиспользованные материалы и остатки подлежат возврату Заказчику с отражением в системе.</p>' +
    '<h3>5. ДОПОЛНИТЕЛЬНЫЕ РАБОТЫ</h3>' +
    '<p>5.1. Дополнительные работы, изменения объёмов и работы вне сметы выполняются только после письменного согласования Заказчика и оформления изменения/дополнительного соглашения в системе.</p>' +
    '<h3>6. ГАРАНТИЯ И ОТВЕТСТВЕННОСТЬ</h3>' +
    '<p>6.1. Гарантийный срок на выполненные работы составляет не менее <b>12 месяцев</b>, если по виду работ или отдельному соглашению не установлен больший срок.</p>' +
    '<p>6.2. За нарушение сроков выполнения работ Исполнитель уплачивает неустойку <b>0,5% от стоимости просроченного объёма за каждый день просрочки</b>, но не более 20% стоимости договора.</p>' +
    '<p>6.3. Стороны решают споры переговорами, при недостижении соглашения — в судебном порядке по месту нахождения Заказчика.</p>';
};

const selfEmployedClauses = '<h3>7. ОСОБЫЕ УСЛОВИЯ ДЛЯ САМОЗАНЯТОГО</h3>' +
  '<p>7.1. Исполнитель подтверждает статус плательщика налога на профессиональный доход и обязуется немедленно уведомить Заказчика об утрате такого статуса.</p>' +
  '<p>7.2. Исполнитель выполняет работы лично, не привлекает работников по трудовым договорам и самостоятельно определяет способ выполнения результата. Договор не устанавливает трудовой режим, должность, зарплату, отпуск, табель или постоянное рабочее место.</p>' +
  '<p>7.3. Если Исполнитель утратил статус НПД или не выдал чек, он возмещает Заказчику расходы, налоги, штрафы и иные потери, возникшие по этой причине.</p>';

export const buildPerformerContractHtml = ({
  company,
  performer,
  contract,
  items = [],
  titlePrefix = '',
} = {}) => {
  const type = contract?.contractType || contract?.contractorType || performer?.contractType || 'ГПХ';
  const self = isSelfEmployed(type);
  const c = companyInfo(company);
  const name = performerName(performer, contract);
  const role = performerTitle(type);
  const number = contract?.contractNumber || contract?.number || (contract?.id ? 'БР-' + contract.id : '_____');
  const project = contract?.project || contract?.projectName || '_____';
  const totalFromItems = (items || []).reduce((sum, item) => {
    const qty = Number(item.quantity || item.doneQuantity || 0);
    const price = Number(item.priceBrigade || item.price || item.priceWork || 0);
    return sum + qty * price;
  }, 0);
  const total = totalFromItems || Number(contract?.totalAmount || contract?.planAmount || 0);
  const title = self
    ? 'ДОГОВОР ВЫПОЛНЕНИЯ РАБОТ С ПЛАТЕЛЬЩИКОМ НПД № ' + html(number)
    : (isLegalContractor(type)
      ? 'ДОГОВОР СУБПОДРЯДА / ВЫПОЛНЕНИЯ РАБОТ № ' + html(number)
      : 'ДОГОВОР ПОДРЯДА / ВЫПОЛНЕНИЯ РАБОТ № ' + html(number));

  const requisites = performerRequisites(performer || {}, type).map(([label, value]) => (
    '<tr><td>' + html(label) + '</td><td>' + html(value) + '</td></tr>'
  )).join('');

  return '' +
    '<h2 style="text-align:center">' + (titlePrefix ? html(titlePrefix) + '<br/>' : '') + title + '</h2>' +
    '<p style="text-align:center">г. _____________ ' + dateText(contract?.contractDate) + '</p>' +
    '<p><b>' + html(c.name) + '</b>, именуемое в дальнейшем «Заказчик», в лице <b>' + html(c.director) + '</b>, действующего на основании <b>' + html(c.basis) + '</b>, с одной стороны, и <b>' + html(name) + '</b>, именуемый в дальнейшем «' + role + '», с другой стороны, заключили настоящий договор.</p>' +
    '<h3>1. ПРЕДМЕТ ДОГОВОРА</h3>' +
    '<p>1.1. ' + role + ' обязуется выполнить строительно-монтажные работы на объекте: <b>' + html(project) + '</b>, а Заказчик обязуется принять и оплатить фактически выполненный и принятый результат.</p>' +
    '<p>1.2. Срок выполнения работ: с <b>' + html(dateText(contract?.startDate)) + '</b> по <b>' + html(dateText(contract?.endDate)) + '</b>. Конкретные этапы и объёмы фиксируются в системе и актах.</p>' +
    '<p>1.3. Перечень работ:</p>' +
    contractItemsTable(items) +
    (total ? '<p><b>Ориентировочная цена договора:</b> ' + money(total) + '. Итоговая сумма определяется по принятым актам.</p>' : '') +
    commonClauses(type) +
    (self ? selfEmployedClauses : '<h3>7. ПРОЧИЕ УСЛОВИЯ</h3><p>7.1. Исполнитель самостоятельно организует выполнение работ и несёт ответственность за привлечённых им лиц, если такое привлечение письменно согласовано Заказчиком.</p>') +
    '<h3>8. РЕКВИЗИТЫ И ПОДПИСИ</h3>' +
    '<table><tr><th>ЗАКАЗЧИК</th><th>' + html(role.toUpperCase()) + '</th></tr>' +
      '<tr><td><b>' + html(c.name) + '</b><br/>ИНН: ' + html(c.inn) + '<br/>Р/с: ' + html(c.rs) + '<br/>Банк: ' + html(c.bankName) + '</td>' +
      '<td><table>' + requisites + '</table></td></tr>' +
      '<tr><td style="padding-top:40px">_____________/' + html(c.director) + '</td><td style="padding-top:40px">_____________/' + html(name) + '</td></tr>' +
    '</table>';
};
