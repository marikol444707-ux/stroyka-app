import { useState } from 'react';
import {
  createAccountableExpenseForm,
  createAccountablePaymentForm,
  createManualExpenseForm,
  createOwnExpenseForm,
} from './paymentInitialForms';

export function usePaymentUiState() {
  const [showAccountableForm, setShowAccountableForm] = useState(false);
  const [newAccountable, setNewAccountable] = useState(createAccountablePaymentForm);
  const [reportingPayment, setReportingPayment] = useState(null);
  const [newExpense, setNewExpense] = useState(createAccountableExpenseForm);
  const [expenseSubmitting, setExpenseSubmitting] = useState(false);
  const [showOwnExpenseForm, setShowOwnExpenseForm] = useState(false);
  const [addExpenseProject, setAddExpenseProject] = useState('');
  const [showBalanceDetails, setShowBalanceDetails] = useState(false);
  const [newManualExpense, setNewManualExpense] = useState(createManualExpenseForm);
  const [newOwnExpense, setNewOwnExpense] = useState(createOwnExpenseForm);

  return {
    addExpenseProject,
    expenseSubmitting,
    newAccountable,
    newExpense,
    newManualExpense,
    newOwnExpense,
    reportingPayment,
    setAddExpenseProject,
    setExpenseSubmitting,
    setNewAccountable,
    setNewExpense,
    setNewManualExpense,
    setNewOwnExpense,
    setReportingPayment,
    setShowAccountableForm,
    setShowBalanceDetails,
    setShowOwnExpenseForm,
    showAccountableForm,
    showBalanceDetails,
    showOwnExpenseForm,
  };
}
