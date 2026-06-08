import React, {useState} from 'react';

const API = process.env.REACT_APP_API_URL || (window.location.hostname==='localhost'?'http://localhost:8001':'');

const LoginPage = ({email, setEmail, password, setPassword, handleLogin, loginError, setLoginError, setPage}) => {
  const [forgotMode, setForgotMode] = useState(false);
  const [forgotStep, setForgotStep] = useState(1);
  const [resetCode, setResetCode] = useState('');
  const [newPass, setNewPass] = useState('');
  const [forgotMsg, setForgotMsg] = useState('');
  const [forgotErr, setForgotErr] = useState('');
  const [devCode, setDevCode] = useState('');

  const requestReset = async () => {
    setForgotErr(''); setForgotMsg('');
    if(!email){setForgotErr('Введите email');return;}
    try {
      const res = await fetch(API+'/password-reset-request',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email})});
      const d = await res.json();
      if(!res.ok){setForgotErr(d.detail||'Ошибка');return;}
      setForgotStep(2);
      setForgotMsg(d.message||'Код сгенерирован');
      if(d._devCode) setDevCode(d._devCode);
    } catch(e){ setForgotErr('Ошибка соединения'); }
  };

  const doReset = async () => {
    setForgotErr(''); setForgotMsg('');
    if(!resetCode||!newPass){setForgotErr('Заполни код и новый пароль');return;}
    if(newPass.length<5){setForgotErr('Пароль не короче 5 символов');return;}
    try {
      const res = await fetch(API+'/password-reset',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,code:resetCode,newPassword:newPass})});
      const d = await res.json();
      if(!res.ok){setForgotErr(d.detail||'Ошибка');return;}
      setForgotStep(3);
      setForgotMsg('Пароль изменён. Войди с новым паролем.');
      setPassword(newPass);
    } catch(e){ setForgotErr('Ошибка соединения'); }
  };

  if (forgotMode) return (
    <div style={{minHeight:'100vh',display:'flex',alignItems:'center',justifyContent:'center',padding:'20px',background:'radial-gradient(circle at 15% 10%,rgba(234,88,12,.18),transparent 28%),linear-gradient(135deg,#020617 0%,#0f172a 54%,#020617 100%)'}}>
      <div style={{width:'100%',maxWidth:'400px',borderRadius:'34px',background:'linear-gradient(145deg,rgba(15,23,42,.96),rgba(2,6,23,.96))',border:'1px solid rgba(148,163,184,.2)',padding:'32px 28px',color:'#e5e5ea'}}>
        <h2 style={{margin:'0 0 8px',fontSize:'22px',fontWeight:'800',color:'#fff'}}>🔑 Восстановление пароля</h2>
        <p style={{margin:'0 0 20px',fontSize:'13px',color:'#8e8e93'}}>{forgotStep===1?'Введи свой email — мы создадим код восстановления':forgotStep===2?'Введи 6-значный код и новый пароль':'Готово!'}</p>
        {forgotStep===1&&(<div>
          <div style={{background:'#2c2c2e',borderRadius:'11px',padding:'11px 14px',marginBottom:'10px'}}>
            <span style={{fontSize:'11px',color:'#636366',display:'block',marginBottom:'2px'}}>E-mail</span>
            <input type='email' value={email} onChange={e=>setEmail(e.target.value)} placeholder='you@stroyka.ru' style={{background:'none',border:'none',outline:'none',color:'#e5e5ea',fontSize:'14px',width:'100%'}}/>
          </div>
          <button onClick={requestReset} style={{width:'100%',padding:'15px 18px',borderRadius:'12px',border:'none',cursor:'pointer',background:'linear-gradient(135deg,#FF6000 0%,#FF8000 45%,#FF6A00 100%)',color:'white',fontSize:'15px',fontWeight:'700'}}>Получить код</button>
        </div>)}
        {forgotStep===2&&(<div>
          {devCode&&<div style={{padding:'10px 14px',borderRadius:'10px',background:'rgba(34,197,94,.12)',border:'1px solid rgba(34,197,94,.26)',color:'#86efac',fontSize:'12px',marginBottom:'10px'}}>🔧 Dev-режим: код <b style={{fontSize:'16px',letterSpacing:'2px'}}>{devCode}</b><br/><span style={{fontSize:'10px',opacity:0.7}}>В production код выдаётся через настроенный канал восстановления</span></div>}
          <div style={{background:'#2c2c2e',borderRadius:'11px',padding:'11px 14px',marginBottom:'10px'}}>
            <span style={{fontSize:'11px',color:'#636366',display:'block',marginBottom:'2px'}}>Код восстановления (6 цифр)</span>
            <input type='text' value={resetCode} onChange={e=>setResetCode(e.target.value)} placeholder='123456' maxLength={6} style={{background:'none',border:'none',outline:'none',color:'#e5e5ea',fontSize:'18px',letterSpacing:'4px',width:'100%'}}/>
          </div>
          <div style={{background:'#2c2c2e',borderRadius:'11px',padding:'11px 14px',marginBottom:'10px'}}>
            <span style={{fontSize:'11px',color:'#636366',display:'block',marginBottom:'2px'}}>Новый пароль (≥5 символов)</span>
            <input type='password' value={newPass} onChange={e=>setNewPass(e.target.value)} placeholder='••••••' style={{background:'none',border:'none',outline:'none',color:'#e5e5ea',fontSize:'14px',width:'100%'}}/>
          </div>
          <button onClick={doReset} style={{width:'100%',padding:'15px 18px',borderRadius:'12px',border:'none',cursor:'pointer',background:'linear-gradient(135deg,#FF6000 0%,#FF8000 45%,#FF6A00 100%)',color:'white',fontSize:'15px',fontWeight:'700'}}>Сменить пароль</button>
        </div>)}
        {forgotStep===3&&(<div>
          <div style={{padding:'14px 16px',borderRadius:'12px',background:'rgba(34,197,94,.12)',border:'1px solid rgba(34,197,94,.26)',color:'#86efac',fontSize:'14px',marginBottom:'14px'}}>✅ Пароль успешно изменён</div>
          <button onClick={()=>{setForgotMode(false);setForgotStep(1);setResetCode('');setNewPass('');setForgotMsg('');setForgotErr('');setDevCode('');}} style={{width:'100%',padding:'15px 18px',borderRadius:'12px',border:'none',cursor:'pointer',background:'linear-gradient(135deg,#FF6000 0%,#FF8000 45%,#FF6A00 100%)',color:'white',fontSize:'15px',fontWeight:'700'}}>Войти</button>
        </div>)}
        {forgotErr&&<p style={{color:'#fca5a5',fontSize:'13px',marginTop:'10px',padding:'10px',background:'rgba(239,68,68,.12)',borderRadius:'8px'}}>{forgotErr}</p>}
        {forgotMsg&&!forgotErr&&<p style={{color:'#86efac',fontSize:'12px',marginTop:'10px'}}>{forgotMsg}</p>}
        <button onClick={()=>{setForgotMode(false);setForgotStep(1);}} style={{marginTop:'14px',background:'none',border:'none',color:'#636366',fontSize:'13px',cursor:'pointer',width:'100%',textAlign:'center'}}>← Назад ко входу</button>
      </div>
    </div>
  );

  return (
    <div style={{minHeight:'100vh',display:'flex',alignItems:'center',justifyContent:'center',padding:'20px',background:'radial-gradient(circle at 15% 10%,rgba(234,88,12,.18),transparent 28%),linear-gradient(135deg,#020617 0%,#0f172a 54%,#020617 100%)'}}>
      <div style={{position:'absolute',width:'260px',height:'260px',borderRadius:'50%',background:'rgba(234,88,12,.35)',filter:'blur(70px)',top:'-90px',left:'-70px',pointerEvents:'none'}}/>
      <div style={{position:'absolute',width:'260px',height:'260px',borderRadius:'50%',background:'rgba(59,130,246,.18)',filter:'blur(70px)',bottom:'-90px',right:'-70px',pointerEvents:'none'}}/>
      <div style={{width:'100%',maxWidth:'400px',position:'relative',overflow:'hidden',borderRadius:'34px',background:'linear-gradient(145deg,rgba(15,23,42,.96),rgba(2,6,23,.96))',border:'1px solid rgba(148,163,184,.2)',boxShadow:'0 30px 100px rgba(0,0,0,.55)'}}>
        <div style={{position:'relative',height:'180px',padding:'24px 28px 0',overflow:'hidden',background:'transparent'}}>
          <div style={{position:'absolute',top:0,right:0,width:'200px',height:'180px',pointerEvents:'none'}}>
            <svg width="200" height="180" viewBox="0 0 200 180" fill="none">
              <defs>
                <linearGradient id="beam" x1="0%" y1="100%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#FF6A00" stopOpacity="0"/>
                  <stop offset="60%" stopColor="#FF8C30" stopOpacity="0.9"/>
                  <stop offset="100%" stopColor="#FF6A00" stopOpacity="0"/>
                </linearGradient>
                <filter id="glow1"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
              </defs>
              <line x1="60" y1="200" x2="200" y2="10" stroke="url(#beam)" strokeWidth="3" filter="url(#glow1)"/>
              <polyline points="185,6 198,6 198,30" stroke="#FF6A00" strokeOpacity="0.55" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <p style={{fontSize:'10px',letterSpacing:'1.5px',color:'#5a5a5e',textTransform:'uppercase',fontWeight:'500',marginBottom:'8px',position:'relative',zIndex:2}}>СИСТЕМА УПРАВЛЕНИЯ СТРОИТЕЛЬСТВОМ</p>
          <div style={{fontSize:'56px',fontWeight:'900',lineHeight:1,letterSpacing:'-2px',position:'relative',zIndex:2,fontStyle:'italic',display:'flex',alignItems:'baseline'}}>
            <span style={{color:'#ffffff'}}>СТРОЙ</span>
            <span style={{color:'#FF6A00',textShadow:'0 0 30px rgba(255,106,0,0.7)'}}>КА</span>
          </div>
        </div>
        <div style={{padding:'16px 28px 28px'}}>
          <div style={{background:'#2c2c2e',borderRadius:'11px',padding:'11px 14px 11px 14px',marginBottom:'10px'}}>
            <span style={{fontSize:'11px',color:'#636366',display:'block',marginBottom:'2px'}}>E-mail</span>
            <input type="email" placeholder="admin@stroyka.ru" value={email} onChange={e=>setEmail(e.target.value)} onKeyDown={e=>e.key==='Enter'&&handleLogin()} style={{background:'none',border:'none',outline:'none',color:'#e5e5ea',fontSize:'14px',width:'100%'}}/>
          </div>
          <div style={{background:'#2c2c2e',borderRadius:'11px',padding:'11px 14px',marginBottom:'10px'}}>
            <span style={{fontSize:'11px',color:'#636366',display:'block',marginBottom:'2px'}}>Пароль</span>
            <input type="password" placeholder="••••••••" value={password} onChange={e=>setPassword(e.target.value)} onKeyDown={e=>e.key==='Enter'&&handleLogin()} style={{background:'none',border:'none',outline:'none',color:'#e5e5ea',fontSize:'14px',width:'100%'}}/>
          </div>
          {loginError&&<div style={{padding:'10px 14px',borderRadius:'10px',background:'rgba(239,68,68,.12)',border:'1px solid rgba(239,68,68,.26)',color:'#fca5a5',fontSize:'13px',marginBottom:'10px'}}>{loginError}</div>}
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'8px 0 14px'}}>
            <div style={{display:'flex',alignItems:'center',gap:'9px'}}>
              <div style={{width:'20px',height:'20px',borderRadius:'50%',background:'radial-gradient(circle at 38% 35%,#ffb84d,#FF6A00 70%)',boxShadow:'0 0 10px rgba(255,106,0,0.55)'}}/>
              <span style={{fontSize:'13px',color:'#e5e5ea'}}>Запомнить меня</span>
            </div>
            <button onClick={()=>{setForgotMode(true);setLoginError('');}} style={{fontSize:'13px',color:'#FF6A00',fontWeight:'500',background:'none',border:'none',cursor:'pointer'}}>Забыли пароль?</button>
          </div>
          <button onClick={handleLogin} style={{width:'100%',padding:'15px 18px',borderRadius:'12px',border:'none',cursor:'pointer',background:'linear-gradient(135deg,#FF6000 0%,#FF8000 45%,#FF6A00 100%)',display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:'12px',boxShadow:'0 4px 24px rgba(255,100,0,0.45)'}}>
            <span style={{color:'#fff',fontSize:'15px',fontWeight:'700'}}>Войти в систему</span>
            <div style={{width:'30px',height:'30px',borderRadius:'50%',background:'rgba(255,255,255,0.18)',display:'flex',alignItems:'center',justifyContent:'center',color:'white',fontSize:'16px'}}>→</div>
          </button>
          <div style={{display:'flex',alignItems:'center',gap:'10px',marginBottom:'10px'}}>
            <div style={{flex:1,height:'1px',background:'#2c2c2e'}}/>
            <span style={{fontSize:'11px',color:'#3a3a3c',letterSpacing:'1.5px'}}>или</span>
            <div style={{flex:1,height:'1px',background:'#2c2c2e'}}/>
          </div>
          <button onClick={()=>{setPage('register');setLoginError('');}} style={{width:'100%',padding:'14px',borderRadius:'12px',border:'1px solid #3a3a3c',background:'#252527',cursor:'pointer',color:'#aeaeb2',fontSize:'13px',fontWeight:'500',marginBottom:'12px'}}>Вход по коду</button>
          <div style={{background:'#252527',borderRadius:'13px',padding:'14px 16px',display:'flex',alignItems:'center',justifyContent:'space-between',gap:'14px'}}>
            <div>
              <div style={{fontSize:'14px',fontWeight:'700',color:'#fff',marginBottom:'4px'}}>Ваши данные<br/>под защитой</div>
              <div style={{fontSize:'11px',color:'#636366',lineHeight:1.5}}>Современные технологии шифрования</div>
            </div>
            <div style={{width:'60px',height:'60px',borderRadius:'14px',background:'linear-gradient(145deg,#162a52,#0d1e3d)',display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0,boxShadow:'0 4px 20px rgba(20,70,180,0.4)'}}>
      <svg width="32" height="36" viewBox="0 0 36 42" fill="none">
        <defs><linearGradient id="sg" x1="8" y1="2" x2="28" y2="42"><stop offset="0%" stopColor="#2a5cbf"/><stop offset="100%" stopColor="#0d1e40"/></linearGradient></defs>
        <path d="M18 2L3 8v12c0 9 6.5 17.4 15 19.5C27.5 37.4 33 29 33 20V8L18 2z" fill="url(#sg)" stroke="#3a6abf" strokeWidth="1.2"/>
        <path d="M12 20.5l4.5 4.5 8-9" stroke="#5aabff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
