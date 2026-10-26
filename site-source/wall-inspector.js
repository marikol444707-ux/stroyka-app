import {materials} from './materials-data.js';

// One preference store is shared with the optional comparison and project brief.
// No unreviewed wall assembly is substituted into the house geometry.
export function createWallInspector({store,onOpen,onLayout,onCompare,onBrief,onStudy,onReturn=done=>done(),category="wall",content={}}){
  const $=s=>document.querySelector(s.replaceAll('#wall-','#'+category+'-')),dialog=$('#wall-inspector'),mobile=matchMedia('(max-width:700px)'),walls=materials.filter(m=>m.category===category);
  let preview=store.snapshot()[category]||(content.initial||'aerated'),returnFocus=null,returnScroll=0,study=false,studyMaterial=null,returnToken=0,returning=false;
  const defaults={heading:'Из чего стены?',studyHeading:'Устройство стены',studyCta:'Рассмотреть устройство стены',shortNames:{concrete:'Монолит'},...content};
  const highlights={
    aerated:['Удобно подрезать; блок легче полнотелой кирпичной кладки.','Нужны защита от увлажнения и подходящий крепёж для тяжёлых предметов.'],
    brick:['Подходит для массивных стен и разнообразных деталей кладки.','Полнотелая кладка имеет значительную массу; мелкий формат увеличивает трудоёмкость.'],
    ceramic:['Крупный формат уменьшает число отдельных элементов кладки.','Нужны аккуратная резка, подходящий крепёж и согласованные доборные элементы.'],
    frame:['Лёгкая конструкция; возможна сборка из подготовленных сухих элементов.','Особенно важны защита от влаги, герметичность и контроль полного состава стены.'],
    concrete:['Можно проектировать разные формы и проёмы по расчёту конструктора.','Нужны контроль бетонирования и выдерживания, расчёт массы и теплоизоляции.']
  };
  Object.assign(highlights,content.highlights||{});
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
  function fact(label,text){const row=el('div',undefined,'wall-fact');row.append(el('dt',label),el('dd',text));return row;}
  const choices=$('#wall-options');
  const optionsHome=choices.parentElement,optionsAnchor=choices.nextSibling;
  function setStudy(enabled){
    if(study===enabled)return;
    if(!enabled){returnToken++;returning=false;}
    study=enabled;dialog.dataset.study=String(enabled);$('#wall-lab').hidden=!enabled;
    $('#wall-heading').textContent=enabled?defaults.studyHeading:defaults.heading;
    if(enabled){$('#wall-lab-material-slot').append(choices);studyMaterial=preview;onStudy(true,preview);}
    else{optionsHome.insertBefore(choices,optionsAnchor);onStudy(false);studyMaterial=null;}
    $('#wall-study').textContent=enabled?'Вернуться к дому':defaults.studyCta;
    $('#wall-study').setAttribute('aria-expanded',String(enabled));dialog.scrollTop=0;onLayout();
    if(enabled&&!mobile.matches)dialog.scrollIntoView({block:'start',behavior:'instant'});
  }
  function returnToHouse(){
    if(!study||returning)return;returning=true;const token=++returnToken;
    onReturn(()=>{if(token!==returnToken||!study)return;returning=false;setStudy(false);render();$('#wall-study').focus({preventScroll:true});});
  }
  for(const m of walls){
    const label=el('label',undefined,'wall-option'),radio=el('input');radio.type='radio';radio.name=category+'-material';radio.value=m.id;
    radio.addEventListener('change',()=>{preview=m.id;store.selectPreference(category,m.id);$('#wall-feedback').textContent='В пожеланиях: '+m.title+'.';});
    label.append(radio,el('span',defaults.shortNames[m.id]||m.title));choices.append(label);
  }
  function render(){
    const selected=store.snapshot()[category],m=walls.find(m=>m.id===preview)||walls[0];
    for(const input of choices.querySelectorAll('input'))input.checked=input.value===selected;
    $('#wall-material-title').textContent=m.title;
    $('#wall-swatch').className='material-swatch '+m.texture;
    $('#wall-material-summary').textContent=m.summary;
    $('#wall-key-facts').replaceChildren(fact('Плюсы',highlights[m.id][0]),fact('Ограничения',highlights[m.id][1]));
    $('#wall-more-facts').replaceChildren(fact('Подробнее о преимуществах',m.benefit),fact('Подробнее об ограничениях',m.limitation),fact('Теплозащита',m.heat),fact('Что влияет на смету',m.budget));
    const questions=$('#wall-questions');questions.replaceChildren();for(const q of m.questions)questions.append(el('li',q));
    $('#wall-aerated-note').hidden=m.id!=='aerated';
    $('#wall-selection').textContent=selected?'В пожеланиях: '+walls.find(m=>m.id===selected).title:'Материал пока не выбран. Нажмите на подходящий вариант.';
    $('#wall-remove').hidden=!selected;
    if(study&&studyMaterial!==m.id){studyMaterial=m.id;onStudy(true,m.id);}
    window['__'+category.toUpperCase()+'_INSPECTOR_STATUS__']={open:dialog.open,preview:m.id,choice:selected||null,mobile:mobile.matches,assemblyChanged:false,study};
  }
  store.subscribe(state=>{if(state[category])preview=state[category];$('#wall-feedback').textContent='';render();});
  function present(){
    if(mobile.matches){dialog.showModal();document.body.classList.add('wall-sheet-open');}
    else{dialog.show();document.body.classList.remove('wall-sheet-open');}
  }
  function open(){
    if(dialog.open){$('#wall-heading').focus({preventScroll:true});return;}
    returnFocus=document.activeElement;returnScroll=scrollY;preview=store.snapshot()[category]||preview;$('#wall-feedback').textContent='';$('#wall-details').open=false;
    onOpen();present();render();$('#wall-heading').focus({preventScroll:true});onLayout();
  }
  function close({restoreFocus=true}={}){
    if(!dialog.open)return;setStudy(false);dialog.close();document.body.classList.remove('wall-sheet-open');onLayout();render();
    if(restoreFocus){if(returnFocus?.isConnected)returnFocus.focus({preventScroll:true});if(mobile.matches)scrollTo({top:returnScroll,behavior:'instant'});}
  }
  $('#wall-close').addEventListener('click',()=>close());
  dialog.addEventListener('cancel',e=>{e.preventDefault();close();});
  dialog.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();close();}});
  $('#wall-remove').addEventListener('click',()=>{store.selectPreference(category,null);$('#wall-feedback').textContent='Материал убран из пожеланий.';choices.querySelector('input[value="'+preview+'"]').focus({preventScroll:true});});
  $('#wall-compare').addEventListener('click',()=>{close({restoreFocus:false});onCompare();});
  $('#wall-brief').addEventListener('click',()=>{close({restoreFocus:false});onBrief();});
  $('#wall-study').addEventListener('click',()=>{if(study){returnToHouse();return;}setStudy(true);render();$('#wall-lab-heading').focus({preventScroll:true});});
  $('#wall-lab-back').addEventListener('click',returnToHouse);
  mobile.addEventListener('change',()=>{if(!dialog.open)return;dialog.close();document.body.classList.remove('wall-sheet-open');present();render();$('#wall-heading').focus({preventScroll:true});onLayout();if(study&&!mobile.matches)dialog.scrollIntoView({block:'start',behavior:'instant'});});
  render();
  return {open,close,isOpen:()=>dialog.open};
}
