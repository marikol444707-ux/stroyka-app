export const detectCableType = (name = '') => {
  const text = String(name || '').toUpperCase().replace(/Ё/g, 'Е').replace(/[\s"'«»()\\/\-._]/g, '');
  if (/(КПС|КПСЭ|КПСВВ|ОПС|ПОЖАР)/.test(text)) return 'Пожарная сигнализация';
  if (/(UTP|FTP|SFTP|FUTP|UUTP|SFUTP)/.test(text)) return 'СКС / интернет';
  if (/(КСВВ|КСПВ|КСПЭВ|КВПЭФ|ТППЭП|ТПВ|JYSTY|JEH|JHSTH)/.test(text)) return 'Слаботочка / сигнализация';
  if (/(ВВГ|АВВГ|ВББШВ|ПВВ|ПВС|СИП|КВВГ|КГ|NYM|NYY|КАБЕЛ|ПРОВОД)/.test(text)) return 'Силовой кабель';
  return 'Кабель';
};

export const cableTypeOf = (cable) => cable?.cableType || detectCableType(cable?.cableBrand || '');
