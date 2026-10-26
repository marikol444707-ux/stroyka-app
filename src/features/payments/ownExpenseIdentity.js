// employeeId belongs to staff, not users. Prefer the server-resolved user link.
export const isOwnExpense = (expense, user = {}) => {
  if (Number(expense.employeeUserId) > 0) return Number(expense.employeeUserId) === Number(user.id);
  const staffId = Number(user.staffId || user.staff_id);
  if (staffId > 0 && Number(expense.employeeId) > 0) return Number(expense.employeeId) === staffId;
  const name = value => String(value || '').trim().toLocaleLowerCase('ru');
  return Boolean(name(user.name) && name(expense.employeeName) === name(user.name));
};
