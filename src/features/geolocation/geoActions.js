export const createGeoActions = ({
  geoCheckins,
  setGeoCheckins,
  user,
}) => {
  const checkinGeo = () => {
    if (!navigator.geolocation) {
      alert('Геолокация не поддерживается');
      return;
    }
    navigator.geolocation.getCurrentPosition((pos) => {
      const checkin = {
        id: Date.now(),
        userId: user.id,
        userName: user.name,
        lat: pos.coords.latitude,
        lng: pos.coords.longitude,
        time: new Date().toLocaleString('ru-RU'),
        date: new Date().toISOString().split('T')[0],
      };
      const updated = [...geoCheckins, checkin];
      setGeoCheckins(updated);
      localStorage.setItem('geoCheckins', JSON.stringify(updated));
      alert('Отметка зафиксирована: ' + new Date().toLocaleTimeString('ru-RU'));
    }, () => alert('Не удалось получить геолокацию'));
  };

  return {
    checkinGeo,
  };
};
