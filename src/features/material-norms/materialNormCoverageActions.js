import { fmtMeasure, toNum } from '../../utils/measureUtils';
import { materialTitleForNormRule } from '../../utils/materialNormUtils';

export const createMaterialNormCoverageActions = ({
  API,
  user,
  estimatesList = [],
  selectedEstimate,
  canEditMaterialNorms,
  sectionsOfEstimate,
  persistEstimate,
  refreshData = async () => {},
  setAiTasks,
  setEstimatesList,
  setMaterialNormNotice,
  setSelectedEstimate,
  fetchFn = fetch,
  alertFn = window.alert,
  confirmFn = window.confirm,
  promptFn = window.prompt,
}) => {
  const saveMaterialNormOverrideFromCoverage = async (row) => {
    if (!canEditMaterialNorms() || !row?.projectName || !row?.rule) return;
    const nextQty = promptFn(
      'Расход для этого объекта/сметы ('+(row.rule.materialUnit||row.materialUnit||'')+' / '+(row.rule.workUnit||row.workUnit||'')+'):',
      String(row.qtyPerUnit || row.rule.qtyPerUnit || ''),
    );
    if (nextQty === null) return;
    const qty = toNum(nextQty);
    if (qty <= 0) { alertFn('Расход должен быть больше 0'); return; }
    const payload = {
      baseNormId: row.rule.baseNormId || row.rule.dbId || null,
      projectName: row.projectName,
      estimateId: row.estimateId || null,
      sectionName: row.sectionName || '',
      workName: row.workName || '',
      materialName: row.materialName || row.rule.name || '',
      work: row.rule.work || [],
      blockWork: row.rule.blockWork || [],
      material: row.rule.material || [],
      workUnit: row.rule.workUnit || row.workUnit || 'м2',
      materialUnit: row.rule.materialUnit || row.materialUnit || 'кг',
      qtyPerUnit: qty,
      thicknessBaseMm: row.rule.thicknessBaseMm || null,
      defaultThicknessMm: row.rule.defaultThicknessMm || null,
      label: 'Поправка '+row.projectName+': '+qty+' '+(row.rule.materialUnit||row.materialUnit||'')+' / '+(row.rule.workUnit||row.workUnit||''),
      reason: 'Уточнение по активной смете: '+(row.estimateName||'')+' / '+(row.sectionName||''),
      active: true,
    };
    const res = await fetchFn(API+'/material-norms/overrides', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload),
    });
    const data = await res.json().catch(()=>({}));
    if (!res.ok) { alertFn(data.detail || 'Не удалось сохранить поправку'); return; }
    setMaterialNormNotice({
      tone:'success',
      title:'Поправка нормы сохранена',
      text:'Поправка применится к объекту '+row.projectName+' и этой смете. Базовый справочник не изменён.',
    });
    await refreshData();
  };

  const updateEstimateFromNormCoverage = async (row, updater, successTitle, successText) => {
    if (!canEditMaterialNorms() || !row?.estimateId) return;
    const est = (estimatesList||[]).find(e=>Number(e.id)===Number(row.estimateId));
    if (!est) { alertFn('Смета не найдена в текущем списке'); return; }
    const sections = sectionsOfEstimate(est).map((s,si)=>si===Number(row.sectionIdx)?updater(s,si):s);
    const updated = {...est, sections, updatedBy:user?.name||''};
    setEstimatesList(prev=>prev.map(e=>Number(e.id)===Number(updated.id)?updated:e));
    if (selectedEstimate && Number(selectedEstimate.id)===Number(updated.id)) setSelectedEstimate(updated);
    await persistEstimate(updated);
    setMaterialNormNotice({tone:'success',title:successTitle,text:successText});
  };

  const addEstimateMaterialFromCoverage = async (row) => {
    if (!row?.rule || row.status!=='Нет материала в смете') return;
    const defaultName = row.materialName || materialTitleForNormRule(row.rule);
    const name = promptFn('Название материала для добавления в раздел сметы:', defaultName);
    if (name === null) return;
    const cleanName = name.trim();
    if (!cleanName) { alertFn('Название материала не может быть пустым'); return; }
    const qtyRaw = promptFn('Количество материала:', String(row.requiredQty || ''));
    if (qtyRaw === null) return;
    const qty = toNum(qtyRaw);
    if (qty <= 0) { alertFn('Количество должно быть больше 0'); return; }
    const unit = row.requiredUnit || row.rule.materialUnit || row.materialUnit || 'шт';
    await updateEstimateFromNormCoverage(row, (section)=>{
      const items = section.items || [];
      const insertAfter = Math.max(0, Number(row.itemIdx));
      const materialItem = {
        id: Date.now()+Math.random(),
        itemType: 'material',
        type: 'Материал',
        name: cleanName,
        unit,
        quantity: qty,
        priceWork: 0,
        priceMaterial: 0,
        isImported: false,
        measurementBasis: 'manual',
        sourceNormRule: row.rule.ruleKey || row.rule.id || '',
        sourceWorkName: row.workName || '',
        sourceEstimateAction: 'added_from_norm_coverage',
      };
      return {...section, items:[...items.slice(0,insertAfter+1), materialItem, ...items.slice(insertAfter+1)]};
    }, 'Материал добавлен в смету', cleanName+' добавлен в раздел '+(row.sectionName||'')+'. Цена 0 — сметчик может заполнить её отдельно.');
  };

  const markEstimateWorkNoMaterialFromCoverage = async (row) => {
    if (!row?.rule || row.status!=='Нет материала в смете') return;
    const ruleKey = String(row.rule.ruleKey || row.rule.id || '');
    if (!ruleKey) return;
    if (!confirmFn('Пометить эту работу как не требующую материала по норме «'+(row.materialName||materialTitleForNormRule(row.rule))+'»?')) return;
    await updateEstimateFromNormCoverage(row, (section)=>{
      const items = (section.items||[]).map((it,idx)=>{
        if (idx!==Number(row.itemIdx)) return it;
        const skip = new Set((Array.isArray(it.materialNormSkipRules)?it.materialNormSkipRules:[]).map(String));
        skip.add(ruleKey);
        return {
          ...it,
          materialNormSkipRules: Array.from(skip),
          materialNormSkipReason: 'Материал по норме не требуется / входит в цену работы',
          materialNormSkipUpdatedAt: new Date().toISOString(),
          materialNormSkipUpdatedBy: user?.name || '',
        };
      });
      return {...section, items};
    }, 'Работа помечена без материала', 'Строка останется в смете, но больше не будет считаться ошибкой покрытия норм.');
  };

  const createMaterialNormCoverageTask = async (row) => {
    if (!row?.projectName || row.status!=='Нет материала в смете') return;
    const payload = {
      projectName: row.projectName,
      title: 'Уточнить материал в смете: '+(row.materialName||materialTitleForNormRule(row.rule)||'материал'),
      description: 'В активной смете есть работа, для которой найдена норма, но нет строки материала. Объект: '+row.projectName+'. Смета: '+(row.estimateName||'')+'. Раздел: '+(row.sectionName||'')+'. Работа: '+(row.workName||'')+'. Норма: '+(row.materialName||materialTitleForNormRule(row.rule)||'')+'. Расчетная потребность: '+(row.requiredQty?fmtMeasure(row.requiredQty,row.requiredUnit):'не рассчитана')+'. Нужно добавить материал в смету или пометить работу как не требующую материала.',
      assignedRole: 'сметчик',
      status: 'Новое',
      actionLabel: 'Проверить смету',
      actionPayload: JSON.stringify({type:'material_norm_coverage',estimateId:row.estimateId,sectionName:row.sectionName,workName:row.workName,ruleKey:row.rule?.ruleKey||row.rule?.id||''}),
    };
    const res = await fetchFn(API+'/ai-tasks', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload),
    });
    const data = await res.json().catch(()=>({}));
    if (!res.ok) { alertFn(data.detail || 'Не удалось создать поручение'); return; }
    setAiTasks(prev=>[data,...(prev||[])]);
    setMaterialNormNotice({tone:'success',title:'Поручение создано',text:'Сметчику поставлена задача уточнить материал или подтвердить, что он не нужен.'});
  };

  return {
    addEstimateMaterialFromCoverage,
    createMaterialNormCoverageTask,
    markEstimateWorkNoMaterialFromCoverage,
    saveMaterialNormOverrideFromCoverage,
    updateEstimateFromNormCoverage,
  };
};
