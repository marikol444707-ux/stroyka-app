import React from 'react';
import { Eye, FileText } from 'lucide-react';

const DOC_BUTTONS = ['Паспорт', 'КС-2', 'КС-3', 'ЖПР', 'М-29', 'АОСК', 'КС-11', 'КС-14', 'ИГД', '📦 Пакет', '📋 НДС', 'М-2', 'М-8', '📦 Потребность', '🔥 Свар', '🧱 Бет', '⚙️ Монт', '🛡 АКЗ', '❄️ Изол', '⛓ Свай'];

export default function AccountingDocumentsPanel({
  C,
  card,
  btnO,
  btnG,
  btnB,
  accountingDocProject,
  setAccountingDocProject,
  projects,
  projectPayments,
  projectPlanDone,
  ownExpenses,
  accountablePayments,
  supplierInvoices,
  brigadeContracts,
  materialControlSummaryForProject,
  invoices,
  warehouseInvoiceEstimateControl,
  badge,
  showPreview,
  buildPassportContent,
  showKS2,
  buildKS3Content,
  buildJPRContent,
  buildM29Content,
  buildAOSKContent,
  buildKS11Content,
  buildKS14Content,
  buildIGDContent,
  buildExecPackageContent,
  buildVATBookContent,
  suppliers,
  buildM2Content,
  buildM8Content,
  buildMaterialRequirementContent,
  buildSpecJournalContent,
  interimActs,
  buildActContent,
}) {
  const selectedProject = accountingDocProject ? (projects || []).find(project => project.name === accountingDocProject) : null;
  const projectPaymentSignedAmount = (payment) => {
    const amount = Number(payment?.amount || 0);
    const note = String(payment?.note || '').trim().toLowerCase();
    const outgoing = amount < 0 ||
      note.startsWith('оплата счёта') ||
      note.startsWith('оплата бригаде') ||
      note.startsWith('возмещение') ||
      note.startsWith('выплата исполнителю');
    return outgoing ? -Math.abs(amount) : Math.max(0, amount);
  };

  const handleDocAction = (doc, project) => {
    if (doc === 'Паспорт') showPreview(buildPassportContent(project), 'Паспорт объекта');
    if (doc === 'КС-2') showKS2(project);
    if (doc === 'КС-3') showPreview(buildKS3Content(project), 'КС-3');
    if (doc === 'ЖПР') showPreview(buildJPRContent(project.name), 'ЖПР');
    if (doc === 'М-29') {
      const today = new Date();
      const monthAgo = new Date(today.getTime() - 30 * 24 * 3600 * 1000);
      showPreview(buildM29Content(project.name, monthAgo.toISOString().split('T')[0], today.toISOString().split('T')[0]), 'М-29 — ' + project.name);
    }
    if (doc === 'АОСК') showPreview(buildAOSKContent(project.name), 'АОСК — ' + project.name);
    if (doc === 'КС-11') showPreview(buildKS11Content(project), 'КС-11 — ' + project.name);
    if (doc === 'КС-14') showPreview(buildKS14Content(project), 'КС-14 — ' + project.name);
    if (doc === 'ИГД') showPreview(buildIGDContent(project.name), 'ИГД — ' + project.name);
    if (doc === '📦 Пакет') showPreview(buildExecPackageContent(project), 'Пакет исполнительной — ' + project.name);
    if (doc === '📋 НДС') {
      const today = new Date();
      const qStart = new Date(today.getFullYear(), Math.floor(today.getMonth() / 3) * 3, 1);
      showPreview(buildVATBookContent(qStart.toISOString().split('T')[0], today.toISOString().split('T')[0]), 'Книга НДС — текущий квартал');
    }
    if (doc === 'М-2') {
      const supplierName = window.prompt('Поставщик (название):', '');
      if (!supplierName) return;
      const receiverName = window.prompt('Кому выдаётся доверенность (ФИО):', '');
      const receiverPassport = window.prompt('Паспорт получателя (серия, номер):', '');
      const supplier = (suppliers || []).find(item => item.name === supplierName) || { name: supplierName };
      showPreview(buildM2Content(supplier, [], project.name, receiverName || '', receiverPassport || ''), 'М-2 Доверенность');
    }
    if (doc === 'М-8') {
      const today = new Date();
      const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
      showPreview(buildM8Content(project.name, '', monthStart.toISOString().split('T')[0], today.toISOString().split('T')[0]), 'М-8 Лимитно-заборная — ' + project.name);
    }
    if (doc === '📦 Потребность') showPreview(buildMaterialRequirementContent(project.name), 'Потребность материалов — ' + project.name);
    if (doc === '🔥 Свар') showPreview(buildSpecJournalContent(project.name, 'welding'), 'Журнал сварочных работ — ' + project.name);
    if (doc === '🧱 Бет') showPreview(buildSpecJournalContent(project.name, 'concrete'), 'Журнал бетонных работ — ' + project.name);
    if (doc === '⚙️ Монт') showPreview(buildSpecJournalContent(project.name, 'assembly'), 'Журнал монтажа — ' + project.name);
    if (doc === '🛡 АКЗ') showPreview(buildSpecJournalContent(project.name, 'anticorrosion'), 'Журнал антикоррозийной защиты — ' + project.name);
    if (doc === '❄️ Изол') showPreview(buildSpecJournalContent(project.name, 'insulation'), 'Журнал изоляционных работ — ' + project.name);
    if (doc === '⛓ Свай') showPreview(buildSpecJournalContent(project.name, 'piling'), 'Журнал свайных работ — ' + project.name);
  };

  const renderSelectedProject = () => {
    if (!selectedProject) return null;

    const planDone = projectPlanDone(selectedProject);
    const budget = Number(selectedProject.budget || 0);
    const ownExp = (ownExpenses || [])
      .filter(expense => expense.projectName === accountingDocProject && expense.status === 'Возмещено')
      .reduce((sum, expense) => sum + Number(expense.amount || 0), 0);
    const accExp = (accountablePayments || []).filter(payment => payment.projectName === accountingDocProject).reduce((sum, payment) => sum + Number(payment.amount || 0), 0);
    const supExp = (supplierInvoices || []).filter(invoice => invoice.projectName === accountingDocProject).reduce((sum, invoice) => sum + Number(invoice.paidAmount || 0), 0);
    const brigExp = (brigadeContracts || []).filter(contract => contract.projectName === accountingDocProject).reduce((sum, contract) => sum + Number(contract.paidAmount || 0), 0);
    const paymentJournalOut = (projectPayments || [])
      .filter(payment => payment.projectName === accountingDocProject)
      .reduce((sum, payment) => {
        const signed = projectPaymentSignedAmount(payment);
        return signed < 0 ? sum + Math.abs(signed) : sum;
      }, 0);
    const factCost = accExp + paymentJournalOut;
    const margin = planDone.done - factCost;
    const materialControl = materialControlSummaryForProject(accountingDocProject);
    const materialRiskRows = materialControl.outsideRows.length + materialControl.stockMismatchRows.length;
    const moneyText = (value) => Math.round(Number(value || 0)).toLocaleString('ru-RU') + ' ₽';
    const projectInvoices = (invoices || []).filter(invoice => {
      const place = invoice?.location === 'Основной склад' ? '' : (invoice?.project || invoice?.location || '');
      return place === accountingDocProject;
    });
    const invoiceBasisRows = projectInvoices.map(invoice => {
      const controls = typeof warehouseInvoiceEstimateControl === 'function' ? warehouseInvoiceEstimateControl(invoice).filter(control => control.name) : [];
      const riskControls = controls.filter(control => ['danger', 'warning'].includes(control.severity));
      const confirmedControls = controls.filter(control => control.severity === 'success');
      const lineSum = controls.reduce((sum, control) => sum + Number(control.lineSum || 0), 0);
      const amount = Number(invoice.total || invoice.totalAmount || invoice.amount || invoice.sum || 0) || lineSum;
      const dangerCount = riskControls.filter(control => control.severity === 'danger').length;
      const warningCount = riskControls.filter(control => control.severity === 'warning').length;
      const outsideCount = riskControls.filter(control => control.status === 'Вне сметы').length;
      const overCount = riskControls.filter(control => control.status === 'Сверх сметы').length;
      const unitMismatchCount = riskControls.filter(control => control.status === 'Ед. не совпала').length;
      const priceOverCount = riskControls.filter(control => control.status === 'Цена выше плана').length;
      return {
        invoice,
        controls,
        riskControls,
        confirmedControls,
        amount,
        dangerCount,
        warningCount,
        outsideCount,
        overCount,
        unitMismatchCount,
        priceOverCount,
      };
    }).sort((a, b) => String(b.invoice.date || '').localeCompare(String(a.invoice.date || '')) || Number(b.invoice.id || 0) - Number(a.invoice.id || 0));
    const invoiceIssueRows = (invoices || [])
      .filter(invoice => (invoice.project || invoice.location) === accountingDocProject)
      .flatMap(invoice => warehouseInvoiceEstimateControl(invoice)
        .filter(control => ['danger', 'warning'].includes(control.severity))
        .map(control => ({ invoice, control })))
      .slice(0, 12);

    return (
      <div>
        <div style={{ display: 'flex', gap: '8px', marginBottom: '15px', flexWrap: 'wrap' }}>
          {DOC_BUTTONS.map(doc => (
            <button
              key={doc}
              onClick={() => handleDocAction(doc, selectedProject)}
              style={{ ...btnB, fontSize: '12px', padding: '7px 14px' }}
            >
              <FileText size={13} />
              {doc}
            </button>
          ))}
        </div>

        <div style={{ ...card, padding: '14px', marginBottom: '14px', backgroundColor: C.bg, border: '1.5px solid ' + C.border }}>
          <b style={{ color: C.text, fontSize: '13px', display: 'block', marginBottom: '10px' }}>💰 Себестоимость объекта (план vs факт)</b>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))', gap: '10px' }}>
            <div><p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 4px' }}>Бюджет (договор)</p><b style={{ color: C.text, fontSize: '14px' }}>{Math.round(budget).toLocaleString('ru-RU') + ' ₽'}</b></div>
            <div><p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 4px' }}>Выполнено по смете</p><b style={{ color: C.accent, fontSize: '14px' }}>{Math.round(planDone.done).toLocaleString('ru-RU') + ' ₽'}</b></div>
            <div><p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 4px' }}>Факт расходов</p><b style={{ color: C.warning, fontSize: '14px' }}>{Math.round(factCost).toLocaleString('ru-RU') + ' ₽'}</b></div>
            <div><p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 4px' }}>Маржа</p><b style={{ color: margin >= 0 ? C.success : C.danger, fontSize: '14px' }}>{Math.round(margin).toLocaleString('ru-RU') + ' ₽'}</b></div>
          </div>
          <p style={{ color: C.textMuted, fontSize: '10px', margin: '8px 0 0', lineHeight: 1.4 }}>
            Факт = платежный журнал ({Math.round(paymentJournalOut).toLocaleString('ru-RU') + ' ₽'}) + подотчётные ({Math.round(accExp).toLocaleString('ru-RU') + ' ₽'}). Расшифровка: возмещения ({Math.round(ownExp).toLocaleString('ru-RU') + ' ₽'}), поставщики ({Math.round(supExp).toLocaleString('ru-RU') + ' ₽'}), бригады ({Math.round(brigExp).toLocaleString('ru-RU') + ' ₽'}).
          </p>
        </div>

        <div style={{ ...card, padding: '14px', marginBottom: '14px', backgroundColor: C.bg, border: '1.5px solid ' + (materialControl.toBuyRows.length ? C.warningBorder : C.successBorder) }}>
          <b style={{ color: C.text, fontSize: '13px', display: 'block', marginBottom: '10px' }}>📦 Материалы по смете: контроль для бухгалтерии</b>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))', gap: '10px' }}>
            <div><p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 4px' }}>План материалов</p><b style={{ color: C.text, fontSize: '14px' }}>{Math.round(materialControl.planSum || 0).toLocaleString('ru-RU') + ' ₽'}</b></div>
            <div><p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 4px' }}>Получено/накладные</p><b style={{ color: C.success, fontSize: '14px' }}>{Math.round(materialControl.suppliedSum || 0).toLocaleString('ru-RU') + ' ₽'}</b></div>
            <div><p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 4px' }}>Позиций к закупке</p><b style={{ color: materialControl.toBuyRows.length ? C.warning : C.success, fontSize: '14px' }}>{materialControl.toBuyRows.length}</b></div>
            <div><p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 4px' }}>Вне сметы/расх.</p><b style={{ color: materialRiskRows ? C.danger : C.success, fontSize: '14px' }}>{materialRiskRows}</b></div>
          </div>
          <p style={{ color: C.textMuted, fontSize: '10px', margin: '8px 0 0', lineHeight: 1.4 }}>
            Счета поставщиков нужно сверять с ведомостью потребности: материал должен быть в смете или в утверждённом изменении, а в печатной ведомости видно, к какой работе относится ресурс.
          </p>
          <div style={{ marginTop: '12px', paddingTop: '10px', borderTop: '1px solid ' + C.border }}>
            <b style={{ color: C.text, fontSize: '12px', display: 'block', marginBottom: '6px' }}>Накладные: объект → поставщик → материал → основание по смете</b>
            {invoiceBasisRows.length === 0 ? (
              <p style={{ color: C.textMuted, fontSize: '11px', margin: 0 }}>По выбранному объекту приходных накладных пока нет.</p>
            ) : (
              <div style={{ display: 'grid', gap: '8px' }}>
                {invoiceBasisRows.slice(0, 20).map(row => {
                  const riskColor = row.dangerCount ? C.danger : row.warningCount ? C.warning : C.success;
                  const riskBg = row.dangerCount ? C.dangerLight : row.warningCount ? C.warningLight : C.successLight;
                  const riskBorder = row.dangerCount ? C.dangerBorder : row.warningCount ? C.warningBorder : C.successBorder;
                  const riskText = row.riskControls.length
                    ? [
                      row.outsideCount ? 'вне сметы ' + row.outsideCount : '',
                      row.overCount ? 'сверх ' + row.overCount : '',
                      row.unitMismatchCount ? 'ед. изм. ' + row.unitMismatchCount : '',
                      row.priceOverCount ? 'цена ' + row.priceOverCount : '',
                    ].filter(Boolean).join(' · ')
                    : 'подтверждено сметой';

                  return (
                    <div key={row.invoice.id || row.invoice.number || row.invoice.date} style={{ ...card, padding: '10px', backgroundColor: C.bgAlt, border: '1px solid ' + C.border }}>
                      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(180px,0.9fr) minmax(180px,1fr) minmax(150px,1fr) auto', gap: '10px', alignItems: 'start' }}>
                        <div>
                          <b style={{ color: C.text, fontSize: '12px' }}>№ {row.invoice.number || row.invoice.id || '—'} · {row.invoice.date || 'без даты'}</b>
                          <p style={{ color: C.textMuted, fontSize: '10px', margin: '3px 0 0' }}>{row.invoice.supplierName || row.invoice.supplier || 'Поставщик не указан'}</p>
                          <p style={{ color: C.accent, fontSize: '11px', margin: '3px 0 0', fontWeight: 800 }}>{moneyText(row.amount)}</p>
                        </div>
                        <div>
                          <p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 4px' }}>Строки накладной</p>
                          <b style={{ color: C.text, fontSize: '12px' }}>{row.controls.length}</b>
                          <span style={{ color: C.textMuted, fontSize: '11px' }}> · по смете {row.confirmedControls.length}</span>
                          <p style={{ color: C.textMuted, fontSize: '10px', margin: '4px 0 0' }}>
                            {row.controls.slice(0, 3).map(control => control.canonicalName || control.name).join(' · ') || 'Строки не распознаны'}
                            {row.controls.length > 3 ? ' · +' + (row.controls.length - 3) : ''}
                          </p>
                        </div>
                        <div>
                          <p style={{ color: C.textSec, fontSize: '10px', margin: '0 0 4px' }}>Основание</p>
                          <p style={{ color: C.textMuted, fontSize: '10px', margin: 0, lineHeight: 1.35 }}>
                            {row.controls.slice(0, 3).map(control => {
                              const sections = control.sectionsList?.slice(0, 2).join(' · ') || control.sections || '';
                              return sections || (control.planSourceCount ? 'сметных строк: ' + control.planSourceCount : control.status);
                            }).join(' / ') || 'Нет сметного основания'}
                          </p>
                        </div>
                        <span style={badge(riskColor, riskBg, riskBorder)}>{riskText}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
          {invoiceIssueRows.length > 0 && (
            <div style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px solid ' + C.border }}>
              <b style={{ color: C.warning, fontSize: '12px', display: 'block', marginBottom: '6px' }}>Накладные требуют проверки перед оплатой</b>
              {invoiceIssueRows.map(({ invoice, control }, index) => (
                <div key={(invoice.id || 'inv') + '-' + index} style={{ display: 'grid', gridTemplateColumns: 'minmax(180px,1fr) minmax(160px,1fr) auto', gap: '8px', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid ' + C.border }}>
                  <div>
                    <b style={{ color: C.text, fontSize: '11px' }}>№ {invoice.number || invoice.id} · {invoice.date || ''}</b>
                    <p style={{ color: C.textMuted, fontSize: '10px', margin: '2px 0 0' }}>{invoice.supplierName || '—'}</p>
                  </div>
                  <div>
                    <b style={{ color: C.text, fontSize: '11px' }}>{control.canonicalName || control.name}</b>
                    <p style={{ color: C.textMuted, fontSize: '10px', margin: '2px 0 0' }}>{control.planSourceCount ? 'сметных строк: ' + control.planSourceCount + ' · ' : ''}{control.sectionsList?.slice(0, 2).join(' · ')}</p>
                  </div>
                  <span style={badge(control.severity === 'danger' ? C.danger : C.warning, control.severity === 'danger' ? C.dangerLight : C.warningLight, control.severity === 'danger' ? C.dangerBorder : C.warningBorder)}>{control.status}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          <b style={{ color: C.text, fontSize: '13px', display: 'block', marginBottom: '10px' }}>Акты по проекту:</b>
          {(interimActs || []).filter(act => act.project === accountingDocProject).map(act => (
            <div key={act.id} style={{ ...card, padding: '12px', marginBottom: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <b style={{ fontSize: '13px', color: C.text }}>{'Акт №' + act.id + ' · ' + act.masterName}</b>
                <p style={{ color: C.textSec, margin: '2px 0', fontSize: '12px' }}>{(act.totalAmount || 0).toLocaleString() + ' ₽ · ' + act.periodStart + ' — ' + act.periodEnd}</p>
              </div>
              <button onClick={() => showPreview(buildActContent(act), 'Акт')} style={btnB}>
                <Eye size={13} />
              </button>
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div>
      <div style={{ display: 'flex', gap: '8px', marginBottom: '15px', flexWrap: 'wrap' }}>
        {(projects || []).map(project => (
          <button
            key={project.id}
            onClick={() => setAccountingDocProject(project.name)}
            style={{ ...(accountingDocProject === project.name ? btnO : btnG), fontSize: '12px', padding: '6px 12px' }}
          >
            {project.name}
          </button>
        ))}
      </div>
      {accountingDocProject ? renderSelectedProject() : <p style={{ color: C.textMuted, textAlign: 'center', padding: '30px' }}>Выберите проект</p>}
    </div>
  );
}
