// Editorial teaching models. Geometry uses arbitrary visual units, never metres.
// These are not approved wall systems or product-specific installation details.
const basics={
  aerated:{title:'Газобетон',core:'Кладка из блоков',note:'Схематичные блоки и швы. Марку, плотность, толщину и узлы ещё нужно выбрать.'},
  brick:{title:'Кирпич',core:'Кирпичная кладка',note:'Условная перевязка. Вид кирпича, толщина, раствор и армирование не определены.'},
  ceramic:{title:'Керамический блок',core:'Кладка из пустотных блоков',note:'Пустоты показаны для объяснения принципа. Их форма не соответствует конкретному изделию.'},
  frame:{title:'Каркас',core:'Каркас и заполнение',note:'Стойки и заполнение показаны условно. Обшивки, мембраны, крепления и полный состав требуют проекта.'},
  concrete:{title:'Монолитный железобетон',core:'Бетон и арматура',note:'Часть бетона условно убрана, чтобы показать арматуру. Расположение и сечения не являются расчётной схемой.'}
};
export const wallSchemes=Object.fromEntries(Object.entries(basics).map(([id,m])=>[id,{
  ...m,id,reviewStatus:'draft',scale:null,thickness:null,thermalValue:null,price:null,
  roles:[
    {id:'inside',title:'Со стороны комнаты',description:'Условная поверхность внутренней отделки. Материал, основание и пригодность для конкретного помещения предстоит согласовать.'},
    {id:'core',title:m.core,description:m.note},
    {id:'outside',title:'Наружное решение',description:'Пунктир обозначает ещё не выбранную наружную систему. Утепление, отделка и защитные слои определяются расчётом и проектом; эта рамка не обозначает конкретный материал.'}
  ]
}]));
