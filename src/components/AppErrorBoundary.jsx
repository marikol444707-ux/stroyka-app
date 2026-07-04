import React from 'react';

const clearStroykaClientCaches = async () => {
  try {
    if (typeof window !== 'undefined' && 'caches' in window) {
      const keys = await window.caches.keys();
      await Promise.all(keys.filter((key) => key.startsWith('stroyka-')).map((key) => window.caches.delete(key)));
    }
  } catch (_e) {}

  try {
    if (typeof navigator !== 'undefined' && 'serviceWorker' in navigator) {
      const registrations = await navigator.serviceWorker.getRegistrations();
      await Promise.all(registrations.map((registration) => registration.update().catch(() => {})));
    }
  } catch (_e) {}
};

export default class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidUpdate(prevProps) {
    if (prevProps.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  componentDidCatch(error, errorInfo) {
    console.error('Stroyka app render error:', error, errorInfo);
  }

  handleRefresh = async () => {
    await clearStroykaClientCaches();
    window.location.reload();
  };

  render() {
    if (!this.state.error) return this.props.children;

    const message = this.state.error?.message || 'Неизвестная ошибка приложения';

    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#070d1d',
        color: '#f8fafc',
        padding: 20,
      }}>
        <div style={{
          width: '100%',
          maxWidth: 520,
          border: '1px solid #334155',
          borderRadius: 24,
          background: '#0f172a',
          padding: 24,
          boxShadow: '0 24px 80px rgba(0,0,0,.35)',
        }}>
          <div style={{fontSize: 28, fontWeight: 900, marginBottom: 12}}>Приложение нужно обновить</div>
          <div style={{fontSize: 17, color: '#cbd5e1', lineHeight: 1.5, marginBottom: 16}}>
            После входа загрузился устаревший или поврежденный файл интерфейса. Нажмите обновление, кэш приложения будет сброшен.
          </div>
          <div style={{
            border: '1px solid #7f1d1d',
            borderRadius: 14,
            background: '#2a1020',
            color: '#fecaca',
            padding: '12px 14px',
            marginBottom: 18,
            wordBreak: 'break-word',
          }}>
            {message}
          </div>
          <button
            type="button"
            onClick={this.handleRefresh}
            style={{
              width: '100%',
              border: 0,
              borderRadius: 16,
              background: '#f97316',
              color: '#fff',
              fontSize: 18,
              fontWeight: 900,
              padding: '16px 18px',
              cursor: 'pointer',
            }}
          >
            Обновить приложение
          </button>
        </div>
      </div>
    );
  }
}
