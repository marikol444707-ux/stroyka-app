export const workedDaysForStaff = (staffId, timesheet = {}, days = []) => (
  (days || []).filter(day => timesheet[`${staffId}-${day}`]).length
);

export const pieceworkTotalForStaff = (staffId, piecework = []) => (
  (piecework || [])
    .filter(item => Number(item.staffId) === Number(staffId))
    .reduce((sum, item) => sum + Number(item.total || 0), 0)
);

export const calcStaffSalary = (staff, timesheet = {}, piecework = [], days = []) => {
  if (!staff) return 0;
  if (staff.payType === 'сдельно') return pieceworkTotalForStaff(staff.id, piecework);
  return Math.round((Number(staff.salary || 0) / 31) * workedDaysForStaff(staff.id, timesheet, days));
};
