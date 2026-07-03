const normalizedCableText = (name = '') => String(name || '').toUpperCase().replace(/Ё/g, 'Е').replace(/[\s"'«»()\\/\-._]/g, '');

const nonCablePattern = /(КОРОБ|РАСПАЕЧ|РАСПРЕДЕЛ|РАЗВЕТВ|ПОДРОЗЕТ|РОЗЕТК|ВЫКЛЮЧАТ|КЛЕММ|НАКОНЕЧ|ГИЛЬЗ|МУФТ|ВВОД|САЛЬНИК|КАБЕЛЬКАНАЛ|КАБЕЛКАНАЛ|КАНАЛКАБЕЛ|ЛОТОК|ГОФР|ТРУБ|КЛИПС|СКОБ|ХОМУТ|ДЕРЖАТЕЛ|ЗАЖИМ|СТЯЖК|ДЮБЕЛ|САМОРЕЗ|ШУРУП|ГВОЗД|БОЛТ|ГАЙК|ШАЙБ|АНКЕР)/;
const cablePattern = /(ВВГ|АВВГ|ВББШВ|ПВВ|ПВС|ПУГВ|ПУНП|ПВ1|ПВ3|СИП|КВВГ|КГ|NYM|NYY|КАБЕЛ|ПРОВОД|ШВВП|UTP|FTP|SFTP|FUTP|UUTP|SFUTP|FFTP|CAT5|CAT5E|CAT6|CAT6A|LAN|ETHERNET|ВИТАЯПАРА|КПС|КПСЭ|КПСВВ|КПСНГ|КСВВ|КСПВ|КСПЭВ|КВПЭФ|ТППЭП|ТПВ|JYSTY|JEH|JHSTH|RG6|RG59|КОАКС|ДОМОФОН|ОХРАН|КИП|RS485|RS232)/;

export const isCableName = (name = '') => {
  const text = normalizedCableText(name);
  if (!text || nonCablePattern.test(text)) return false;
  return cablePattern.test(text);
};

export const detectCableType = (name = '') => {
  const text = normalizedCableText(name);
  if (!isCableName(name)) return '';
  if (/(КПС|КПСЭ|КПСВВ|КПСНГ|ОПС|FRLS|FRHF|ПОЖАР|СИГНАЛИЗАЦ)/.test(text)) return 'Пожарная сигнализация';
  if (/(UTP|FTP|SFTP|FUTP|UUTP|SFUTP|FFTP|CAT5|CAT5E|CAT6|CAT6A|LAN|ETHERNET|ВИТАЯПАРА)/.test(text)) return 'СКС / интернет';
  if (/(КСВВ|КСПВ|КСПЭВ|КВПЭФ|ТППЭП|ТПВ|JYSTY|JEH|JHSTH|RG6|RG59|КОАКС|ТЕЛЕФОН|ДОМОФОН|ОХРАН|КИП|RS485|RS232)/.test(text)) return 'Слаботочка / сигнализация';
  if (/(ВВГ|АВВГ|ВББШВ|ПВВ|ПВС|ПУГВ|ПУНП|ПВ1|ПВ3|СИП|КВВГ|КГ|NYM|NYY|КАБЕЛ|ПРОВОД|ШВВП)/.test(text)) return 'Силовой кабель';
  return 'Кабель';
};

export const cableTypeOf = (cable) => cable?.cableType || detectCableType(cable?.cableBrand || '');
