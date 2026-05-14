import React from 'react';

const LoginPage = ({email, setEmail, password, setPassword, handleLogin, loginError, setLoginError, setPage, C, inp, btnO, card}) => {
  return (
    <div style={{display:'flex',justifyContent:'center',alignItems:'center',height:'100vh',backgroundColor:C.bg}}>
      <div style={{...card,padding:'40px',width:'420px',boxShadow:'0 20px 60px rgba(0,0,0,0.08)'}}>
        <div style={{textAlign:'center',marginBottom:'35px'}}>
          <div style={{width:'72px',height:'72px',borderRadius:'20px',background:'linear-gradient(135deg,#f97316,#ea580c)',display:'flex',alignItems:'center',justifyContent:'center',fontSize:'36px',margin:'0 auto 15px'}}>🏗️</div>
          <h2 style={{margin:0,color:C.text,fontSize:'28px',fontWeight:'800'}}>СтройКа</h2>
          <p style={{color:C.textSec,margin:'8px 0 0',fontSize:'14px'}}>Система управления строительством</p>
        </div>
        <input type="email" placeholder="Email" value={email} onChange={e=>setEmail(e.target.value)} style={inp}/>
        <input type="password" placeholder="Пароль" value={password} onChange={e=>setPassword(e.target.value)} onKeyDown={e=>e.key==='Enter'&&handleLogin()} style={inp}/>
        {loginError&&<p style={{color:C.danger,fontSize:'13px',marginBottom:'10px'}}>{loginError}</p>}
        <button onClick={handleLogin} style={{...btnO,width:'100%',padding:'14px',justifyContent:'center',fontSize:'15px',marginBottom:'12px'}}>Войти</button>
        <button onClick={()=>{setPage('register');setLoginError('');}} style={{width:'100%',padding:'12px',backgroundColor:'transparent',border:'1.5px solid '+C.border,color:C.textSec,borderRadius:'8px',cursor:'pointer',fontSize:'14px'}}>Регистрация по коду</button>
        <div style={{marginTop:'20px',padding:'15px',backgroundColor:C.accentLight,border:'1.5px solid '+C.accentBorder,borderRadius:'10px',fontSize:'12px',color:C.textSec}}>
          <b style={{color:C.accent}}>Тестовые аккаунты:</b><br/>
          admin@stroyka.ru / admin123<br/>buh@stroyka.ru / buh123
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
