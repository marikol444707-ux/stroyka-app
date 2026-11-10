import React, { useRef, useState } from 'react';
import { ChevronRight, ShieldCheck } from 'lucide-react';
import { PUBLIC_SITE_OPERATOR } from './publicSiteContent';

export function PublicSiteHero({ onLogin, scrollTo, onChooseDirection }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef(null);
  const closeMenuOnEscape = (event) => {
    if (event.key === 'Escape' && menuOpen) {
      setMenuOpen(false);
      menuButton.current?.focus();
    }
  };
  return (<section className="public-hero public-design-hero" id="top">
  <header className="public-design-nav" onKeyDown={closeMenuOnEscape}>
    <button type="button" className="public-design-brand" onClick={() => scrollTo('top')} aria-label="СтройКа — наверх"><span className="public-design-brand-icon" aria-hidden="true">▰</span>Строй<span>Ка</span><small>СТРОИТЕЛЬСТВО И РЕМОНТ</small></button>
    <button type="button" ref={menuButton} className="public-design-menu" aria-expanded={menuOpen} aria-controls="public-design-navigation" onClick={()=>setMenuOpen(!menuOpen)}>{menuOpen ? 'Закрыть ×' : 'Меню ☰'}</button>
    <nav id="public-design-navigation" className={menuOpen?'public-design-navigation expanded':'public-design-navigation'} aria-label="Основная навигация">
      {[['directions','Проекты'],['calculator','Калькулятор'],['process','Как работаем'],['suppliers','Партнёрам']].map(([id,label])=><button type="button" key={id} onClick={()=>{setMenuOpen(false);scrollTo(id)}}>{label}</button>)}
      <button type="button" className="public-design-mobile-contact" onClick={() => { setMenuOpen(false); onLogin(); }}>Личный кабинет ↗</button>
      <a className="public-design-mobile-contact" href={'tel:+' + PUBLIC_SITE_OPERATOR.phone.replace(/\D/g, '')}>{PUBLIC_SITE_OPERATOR.phone}</a>
    </nav>
    <div className="public-design-nav-contact"><a href={'tel:+' + PUBLIC_SITE_OPERATOR.phone.replace(/\D/g, '')}>{PUBLIC_SITE_OPERATOR.phone}</a><button type="button" onClick={onLogin}>Личный кабинет <span>↗</span></button></div>
  </header>
  <div className="public-design-cover">
    <img className="public-design-cover-image" src="/site-assets/projects/h2-01/facade.webp" alt="Проект-идея двухэтажного дома с террасой" fetchPriority="high" />
    <div className="public-design-cover-content">
      <p className="public-design-kicker"><span/>СТАВРОПОЛЬСКИЙ КРАЙ</p>
      <h1>Ваш дом.<br/>Ваши планы.<br/><em>Наша работа.</em></h1>
      <p className="public-design-cover-lead">Строим, ремонтируем и ведём объект<br className="public-design-desktop-break"/> от первой сметы до передачи ключей.</p>
      <div className="public-design-cover-actions"><button type="button" className="public-primary" onClick={()=>scrollTo('directions')}>Подобрать проект <ChevronRight size={18}/></button><button type="button" className="public-design-link-light" onClick={()=>scrollTo('calculator')}>Рассчитать свой объект ↗</button></div>
      <div className="public-design-cover-foot"><ShieldCheck size={18}/><span>Смета, этапы и фотоотчёты —<br/>в вашем личном кабинете.</span></div>
    </div>
    <div className="public-design-image-credit">ПРОЕКТ-ИДЕЯ · ИЛЛЮСТРАЦИЯ</div>
    <button type="button" className="public-design-image-card" onClick={()=>onChooseDirection('two-floor-modern')}><span>Идея для вашего дома</span><strong>Современный дом<br/>с просторной террасой <span>↗</span></strong><small>Посмотреть варианты и планировки</small></button>
  </div>
  <div className="public-design-quickstart"><div><span className="public-design-kicker">С ЧЕГО НАЧНЁМ?</span><strong>Выберите свою задачу</strong></div>{[['one-floor-modern','01','Построить дом','Проекты, планировки, комплектации'],['apartment-repair','02','Сделать ремонт','Квартиры, дома и помещения'],['cottage-reconstruction','03','Обновить объект','Реконструкция, фасад и кровля']].map(([id,n,title,note])=><button type="button" key={id} onClick={()=>onChooseDirection(id)}><small>{n}</small><span><strong>{title}</strong><em>{note}</em></span><ChevronRight size={19}/></button>)}</div>
</section>
);
}
