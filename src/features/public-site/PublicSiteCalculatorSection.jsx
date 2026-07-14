import React from 'react';
import { Calculator, Check } from 'lucide-react';
import { PublicProjectFilePicker } from './PublicProjectFilePicker';
import {
  workTypes,
  houseWallTypes,
  housePackages,
  stages,
  repairObjects,
  repairConditions,
  repairLevels,
  materialModes,
  commerceTypes,
  commerceLevels,
  reconstructionScopes,
  formatMoney,
} from './publicSiteContent';

export const PublicSiteCalculatorSection = ({
  calc,
  updateCalc,
  result,
  scrollTo,
  leadFileUploadsEnabled = false,
  leadFiles = [],
  leadFileError = '',
  chooseLeadFiles,
  removeLeadFile,
}) => (
          <section id="calculator" className="public-calculator" aria-label="Калькулятор строительства">
            <div className="public-tool-header">
              <div>
                <p className="public-tool-kicker">Предварительный расчёт</p>
                <h2>Калькулятор стоимости</h2>
              </div>
              <div className="public-live-badge">
                <Calculator size={16} />
                Сумма обновляется
              </div>
            </div>

            <div className="public-type-grid" aria-label="Тип расчёта">
              {workTypes.map((item) => (
                <button
                  className={calc.type === item.value ? 'public-type-card active' : 'public-type-card'}
                  type="button"
                  key={item.value}
                  onClick={() => updateCalc('type', item.value)}
                >
                  <span>{item.short}</span>
                  <b>{item.label}</b>
                  <small>{item.description}</small>
                </button>
              ))}
            </div>

            <div className="public-stepper">
              {[
                '1 Тип объекта',
                calc.type === 'house' ? '2 Конструктив' : '2 Состояние',
                calc.type === 'house' ? '3 Комплектация' : '3 Работы',
                '4 Итог',
              ].map((step, index) => (
                <div className={index === 3 ? 'public-step active' : 'public-step'} key={step}>
                  {step}
                </div>
              ))}
            </div>

            <div className="public-calc-grid">
              <label className="public-field">
                <span>{calc.type === 'repair' ? 'Площадь ремонта, м2' : calc.type === 'commerce' ? 'Площадь помещения, м2' : 'Площадь, м2'}</span>
                <input
                  type="number"
                  min="10"
                  value={calc.area}
                  onChange={(event) => updateCalc('area', event.target.value)}
                />
              </label>

              {calc.type === 'house' && (
                <>
                  <label className="public-field">
                    <span>Этажей</span>
                    <select value={calc.floors} onChange={(event) => updateCalc('floors', event.target.value)}>
                      <option value="1">1 этаж</option>
                      <option value="2">2 этажа</option>
                      <option value="3">3 этажа</option>
                    </select>
                  </label>
                  <label className="public-field">
                    <span>Комнат</span>
                    <input type="number" min="1" value={calc.rooms} onChange={(event) => updateCalc('rooms', event.target.value)} />
                  </label>
                  <label className="public-field">
                    <span>Материал стен</span>
                    <select value={calc.wallType} onChange={(event) => updateCalc('wallType', event.target.value)}>
                      {houseWallTypes.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                    </select>
                  </label>
                  <label className="public-field">
                    <span>Комплектация</span>
                    <select value={calc.package} onChange={(event) => updateCalc('package', event.target.value)}>
                      {housePackages.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                    </select>
                  </label>
                </>
              )}

              {calc.type === 'repair' && (
                <>
                  <label className="public-field">
                    <span>Что ремонтируем</span>
                    <select value={calc.repairObject} onChange={(event) => updateCalc('repairObject', event.target.value)}>
                      {repairObjects.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                    </select>
                  </label>
                  <label className="public-field">
                    <span>Комнат</span>
                    <input type="number" min="1" value={calc.rooms} onChange={(event) => updateCalc('rooms', event.target.value)} />
                  </label>
                  <label className="public-field">
                    <span>Санузлов</span>
                    <input type="number" min="0" value={calc.bathrooms} onChange={(event) => updateCalc('bathrooms', event.target.value)} />
                  </label>
                  <label className="public-field">
                    <span>Состояние</span>
                    <select value={calc.repairCondition} onChange={(event) => updateCalc('repairCondition', event.target.value)}>
                      {repairConditions.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                    </select>
                  </label>
                  <label className="public-field">
                    <span>Уровень ремонта</span>
                    <select value={calc.repairLevel} onChange={(event) => updateCalc('repairLevel', event.target.value)}>
                      {repairLevels.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                    </select>
                  </label>
                  <label className="public-field">
                    <span>Материалы</span>
                    <select value={calc.materialMode} onChange={(event) => updateCalc('materialMode', event.target.value)}>
                      {materialModes.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                    </select>
                  </label>
                </>
              )}

              {calc.type === 'commerce' && (
                <>
                  <label className="public-field">
                    <span>Тип бизнеса</span>
                    <select value={calc.commerceType} onChange={(event) => updateCalc('commerceType', event.target.value)}>
                      {commerceTypes.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                    </select>
                  </label>
                  <label className="public-field">
                    <span>Формат работ</span>
                    <select value={calc.commerceLevel} onChange={(event) => updateCalc('commerceLevel', event.target.value)}>
                      {commerceLevels.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                    </select>
                  </label>
                  <label className="public-field">
                    <span>Помещений / зон</span>
                    <input type="number" min="1" value={calc.rooms} onChange={(event) => updateCalc('rooms', event.target.value)} />
                  </label>
                  <label className="public-field">
                    <span>Состояние помещения</span>
                    <select value={calc.commerceCondition} onChange={(event) => updateCalc('commerceCondition', event.target.value)}>
                      <option value="shell">Черновое</option>
                      <option value="ready">Почти готово</option>
                      <option value="old">Старое помещение</option>
                    </select>
                  </label>
                </>
              )}

              {calc.type === 'reconstruction' && (
                <>
                  <label className="public-field">
                    <span>Что реконструируем</span>
                    <select value={calc.reconstructionScope} onChange={(event) => updateCalc('reconstructionScope', event.target.value)}>
                      {reconstructionScopes.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                    </select>
                  </label>
                  <label className="public-field">
                    <span>Конструкции</span>
                    <select value={calc.keepsStructure ? 'keep' : 'replace'} onChange={(event) => updateCalc('keepsStructure', event.target.value === 'keep')}>
                      <option value="keep">Часть сохраняем</option>
                      <option value="replace">Полная переделка</option>
                    </select>
                  </label>
                  <label className="public-field">
                    <span>Помещений</span>
                    <input type="number" min="1" value={calc.rooms} onChange={(event) => updateCalc('rooms', event.target.value)} />
                  </label>
                  <label className="public-field">
                    <span>Сложность</span>
                    <select value={calc.inspectionNeeded ? 'inspect' : 'simple'} onChange={(event) => updateCalc('inspectionNeeded', event.target.value === 'inspect')}>
                      <option value="inspect">Нужно обследование</option>
                      <option value="simple">Понятный объём</option>
                    </select>
                  </label>
                </>
              )}

              <label className="public-field">
                <span>Срок</span>
                <select value={calc.deadline} onChange={(event) => updateCalc('deadline', event.target.value)}>
                  <option value="normal">Обычный график</option>
                  <option value="fast">Ускоренный старт</option>
                </select>
              </label>
              <label className="public-field">
                <span>Стадия</span>
                <select value={calc.stage} onChange={(event) => updateCalc('stage', event.target.value)}>
                  {stages.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                </select>
              </label>
            </div>

            <div className="public-check-grid">
              {calc.type === 'house' && (
                <>
                  <label><input type="checkbox" checked={calc.foundation} onChange={(event) => updateCalc('foundation', event.target.checked)} /> Фундамент нужен</label>
                  <label><input type="checkbox" checked={calc.communications} onChange={(event) => updateCalc('communications', event.target.checked)} /> Коммуникации нужны</label>
                </>
              )}

              {calc.type === 'repair' && (
                <>
                  <label><input type="checkbox" checked={calc.demolition} onChange={(event) => updateCalc('demolition', event.target.checked)} /> Демонтаж</label>
                  <label><input type="checkbox" checked={calc.electric} onChange={(event) => updateCalc('electric', event.target.checked)} /> Электрика</label>
                  <label><input type="checkbox" checked={calc.plumbing} onChange={(event) => updateCalc('plumbing', event.target.checked)} /> Сантехника</label>
                  <label><input type="checkbox" checked={calc.walls} onChange={(event) => updateCalc('walls', event.target.checked)} /> Стены</label>
                  <label><input type="checkbox" checked={calc.floorsWork} onChange={(event) => updateCalc('floorsWork', event.target.checked)} /> Полы</label>
                  <label><input type="checkbox" checked={calc.ceiling} onChange={(event) => updateCalc('ceiling', event.target.checked)} /> Потолки</label>
                  <label><input type="checkbox" checked={calc.tiles} onChange={(event) => updateCalc('tiles', event.target.checked)} /> Плитка</label>
                  <label><input type="checkbox" checked={calc.trash} onChange={(event) => updateCalc('trash', event.target.checked)} /> Вывоз мусора</label>
                </>
              )}

              {calc.type === 'commerce' && (
                <>
                  <label><input type="checkbox" checked={calc.ventilation} onChange={(event) => updateCalc('ventilation', event.target.checked)} /> Вентиляция</label>
                  <label><input type="checkbox" checked={calc.fireSafety} onChange={(event) => updateCalc('fireSafety', event.target.checked)} /> Пожарка</label>
                  <label><input type="checkbox" checked={calc.powerEquipment} onChange={(event) => updateCalc('powerEquipment', event.target.checked)} /> Электрика под оборудование</label>
                  <label><input type="checkbox" checked={calc.designProject} onChange={(event) => updateCalc('designProject', event.target.checked)} /> Есть дизайн-проект</label>
                  <label><input type="checkbox" checked={calc.nightWork} onChange={(event) => updateCalc('nightWork', event.target.checked)} /> Ночные работы</label>
                </>
              )}

              {calc.type === 'reconstruction' && (
                <>
                  <label><input type="checkbox" checked={calc.demolition} onChange={(event) => updateCalc('demolition', event.target.checked)} /> Большой демонтаж</label>
                  <label><input type="checkbox" checked={calc.reinforcement} onChange={(event) => updateCalc('reinforcement', event.target.checked)} /> Усиление конструкций</label>
                  <label><input type="checkbox" checked={calc.foundationTouch} onChange={(event) => updateCalc('foundationTouch', event.target.checked)} /> Трогаем фундамент</label>
                  <label><input type="checkbox" checked={calc.roofTouch} onChange={(event) => updateCalc('roofTouch', event.target.checked)} /> Трогаем кровлю</label>
                  <label><input type="checkbox" checked={calc.engineeringNew} onChange={(event) => updateCalc('engineeringNew', event.target.checked)} /> Новая инженерия</label>
                </>
              )}

            </div>

            {leadFileUploadsEnabled && (
              <PublicProjectFilePicker
                files={leadFiles}
                error={leadFileError}
                onChoose={chooseLeadFiles}
                onRemove={removeLeadFile}
              />
            )}

            <div className="public-result">
              <div className="public-result-main">
                <div>
                  <span>Предварительно</span>
                  <strong>{formatMoney(result.min)} - {formatMoney(result.max)} ₽</strong>
                  <small>{result.typeLabel}: {result.summary}</small>
                </div>
                <div className="public-confidence">
                  <div className="public-confidence-top">
                    <span>Точность расчёта</span>
                    <b>{result.confidence}%</b>
                  </div>
                  <div className="public-progress"><i style={{ width: `${result.confidence}%` }} /></div>
                </div>
                <button className="public-primary public-result-button" type="button" onClick={() => scrollTo('request')}>
                  Получить точную смету
                </button>
              </div>

              <div className="public-breakdown">
                {result.breakdown.map((item) => (
                  <div className="public-breakdown-row" key={item.label}>
                    <span>{item.label}</span>
                    <b>{formatMoney(item.value)} ₽</b>
                  </div>
                ))}
              </div>

              <div className="public-advice-list">
                {result.advice.map((item) => (
                  <p key={item}><Check size={15} /> {item}</p>
                ))}
              </div>
            </div>
          </section>
);
