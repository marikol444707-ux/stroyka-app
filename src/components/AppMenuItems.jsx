import React from 'react';
import {
  BarChart3,
  Calculator,
  CloudSun,
  ClipboardList,
  CreditCard,
  DollarSign,
  FolderKanban,
  Globe2,
  Handshake,
  LayoutDashboard,
  Package,
  ScrollText,
  Settings,
  ShoppingCart,
  UserCheck,
} from 'lucide-react';

export const buildAppMenuItems = () => [
  { id: 'dashboard', icon: <LayoutDashboard size={18} />, label: 'Главная' },
  { id: 'analytics', icon: <BarChart3 size={18} />, label: 'Аналитика' },
  { id: 'crm', icon: <Handshake size={18} />, label: 'CRM' },
  { id: 'projects', icon: <FolderKanban size={18} />, label: 'Проекты' },
  { id: 'assignments', icon: <ClipboardList size={18} />, label: 'Поручения' },
  { id: 'site', icon: <Globe2 size={18} />, label: 'Сайт' },

  { id: 'warehouse', icon: <Package size={18} />, label: 'Склад' },
  { id: 'supply', icon: <ShoppingCart size={18} />, label: 'Снабжение' },
  { id: 'accounting', icon: <DollarSign size={18} />, label: 'Бухгалтерия' },
  { id: 'personnel', icon: <UserCheck size={18} />, label: 'Персонал' },

  { id: 'estimates', icon: <Calculator size={18} />, label: 'Сметы' },
  { id: 'weather', icon: <CloudSun size={18} />, label: 'Погода / ЖПР' },

  { id: 'myexpenses', icon: <CreditCard size={18} />, label: 'Мои траты' },
  { id: 'activitylog', icon: <ScrollText size={18} />, label: 'Журнал' },
  { id: 'settings', icon: <Settings size={18} />, label: 'Настройки' },
];
