import React from 'react';

const LoginPage = ({email, setEmail, password, setPassword, handleLogin, loginError, setLoginError, setPage}) => {
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
            <button style={{fontSize:'13px',color:'#FF6A00',fontWeight:'500',background:'none',border:'none',cursor:'pointer'}}>Забыли пароль?</button>
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
              <div style={{fontSize:'14px',fontWeight:'700',color:'#fff',marginBottom:'4px'}}>Ваши данные под защитой</div>
              <div style={{fontSize:'11px',color:'#636366',lineHeight:1.5}}>Современные технологии шифрования</div>
            </div>
            <div style={{width:'60px',height:'60px',borderRadius:'14px',background:'linear-gradient(145deg,#162a52,#0d1e3d)',display:'flex',alignItems:'center',justifyContent:'center',fontSize:'28px',flexShrink:0}}>🛡️</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
