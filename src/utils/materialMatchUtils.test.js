import {
  materialAutoMatchSafe,
  materialNameMatchScore,
} from './materialMatchUtils';

const expectSafeMaterialMatch = (invoiceName, estimateName) => {
  const score = materialNameMatchScore(invoiceName, estimateName);
  expect(score).toBeGreaterThanOrEqual(0.82);
  expect(materialAutoMatchSafe(invoiceName, estimateName, score)).toBe(true);
};

describe('materialMatchUtils', () => {
  test.each([
    ['Гипрок влагостойкий 12,5 мм', 'Лист гипсокартонный влагостойкий'],
    ['Профиль ПН 50/40', 'Направляющая UW 50'],
    ['Кабель ВВГнг 3х2,5', 'Провод медный 3х2,5'],
    ['Прожектор LED 50Вт', 'Светильник светодиодный'],
    ['Труба ППР 25', 'Труба полипропиленовая 25'],
    ['Самонарезающий шуруп с прессшайбой', 'Саморезы с прессшайбой'],
  ])('matches %s to %s by family', (invoiceName, estimateName) => {
    expectSafeMaterialMatch(invoiceName, estimateName);
  });
});
