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
  gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))',
  gap: '10px',
  marginBottom: '14px',
});

export const threeColumnGridStyle = () => ({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))',
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

export const modalFooterStyle = (C) => ({
  padding: '14px 20px',
  borderTop: '1.5px solid ' + C.border,
  backgroundColor: C.bg,
  display: 'flex',
  gap: '8px',
  justifyContent: 'space-between',
  flexWrap: 'wrap',
});

export const footerActionsStyle = () => ({
  display: 'flex',
  gap: '8px',
  flexWrap: 'wrap',
});

export const infoPanelStyle = (C, extra = {}) => ({
  padding: '10px 12px',
  backgroundColor: C.bg,
  border: '1.5px solid ' + C.border,
  borderRadius: '8px',
  fontSize: '12px',
  color: C.textSec,
  ...extra,
});

export const borderedBlockStyle = (C) => ({
  padding: '12px',
  backgroundColor: C.bg,
  borderRadius: '10px',
  border: '1.5px solid ' + C.border,
  marginBottom: '14px',
});

export const checkboxRowStyle = (C) => ({
  ...infoPanelStyle(C),
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
});

export const checkboxInputStyle = () => ({
  width: '18px',
  height: '18px',
  cursor: 'pointer',
});

export const checkboxLabelStyle = (C) => ({
  fontSize: '13px',
  color: C.text,
  cursor: 'pointer',
  fontWeight: '600',
});

export const twoColumnGridTightStyle = () => ({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))',
  gap: '10px',
});

export const installGridStyle = () => ({
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))',
  gap: '10px',
});

export const aiActionButtonStyle = (baseStyle, loading = false) => ({
  ...baseStyle,
  backgroundColor: '#10b981',
  color: 'white',
  borderColor: '#059669',
  opacity: loading ? 0.6 : 1,
  cursor: loading ? 'not-allowed' : 'pointer',
});

export const closeButtonStyle = (baseStyle) => ({
  ...baseStyle,
  padding: '5px 10px',
});

export const smallIconButtonStyle = (baseStyle) => ({
  ...baseStyle,
  padding: '5px 10px',
  fontSize: '11px',
});

export const summaryValueStyle = (C) => ({
  fontSize: '13px',
  color: C.text,
});

export const textareaStyle = (baseStyle, minHeight = '70px') => ({
  ...baseStyle,
  minHeight,
  resize: 'vertical',
});

export const sectionTitleStyle = (C) => ({
  color: C.text,
  fontSize: '13px',
  display: 'block',
  marginBottom: '10px',
});

export const sectionHintStyle = (C) => ({
  color: C.textMuted,
  fontSize: '11px',
  margin: '8px 0 0',
});
