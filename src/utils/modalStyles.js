export const formLabelStyle = (C) => ({
  fontSize: '11px',
  color: C.textSec,
  fontWeight: '600',
  marginBottom: '4px',
  display: 'block',
});

export const formSectionStyle = () => ({marginBottom: '14px'});

export const modalOverlayStyle = () => ({
  position: 'fixed',
  inset: 0,
  backgroundColor: 'rgba(0,0,0,0.55)',
  zIndex: 1600,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: '20px',
});

export const modalShellStyle = (card, width = 'min(900px,100%)') => ({
  ...card,
  padding: 0,
  width,
  maxHeight: '92vh',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
});

export const modalHeaderStyle = (C) => ({
  padding: '16px 20px',
  borderBottom: '1.5px solid ' + C.border,
  backgroundColor: C.bg,
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  flexWrap: 'wrap',
  gap: '8px',
});

export const modalBodyStyle = () => ({
  flex: 1,
  overflowY: 'auto',
  padding: '18px 20px',
});

export const modalSummaryGridStyle = (C) => ({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))',
  gap: '10px',
  marginBottom: '18px',
  padding: '12px',
  backgroundColor: C.bg,
  borderRadius: '10px',
  border: '1.5px solid ' + C.border,
});

export const twoColumnGridStyle = () => ({
  display: 'grid',
  gridTemplateColumns: '1fr 1fr',
  gap: '10px',
  marginBottom: '14px',
});

export const threeColumnGridStyle = () => ({
  display: 'grid',
  gridTemplateColumns: '1fr 1fr 2fr',
  gap: '10px',
  marginBottom: '14px',
});

export const statusPillStyle = (C, variant = 'warning') => {
  const colors = {
    success: {bg: C.successLight, text: C.success},
    danger: {bg: C.dangerLight, text: C.danger},
    warning: {bg: C.warningLight, text: C.warning},
  };
  const color = colors[variant] || colors.warning;
  return {
    padding: '4px 10px',
    borderRadius: '12px',
    fontSize: '12px',
    fontWeight: '600',
    backgroundColor: color.bg,
    color: color.text,
  };
};
