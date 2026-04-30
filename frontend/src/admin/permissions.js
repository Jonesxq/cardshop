import {
  Box,
  CreditCard,
  DataAnalysis,
  Document,
  Goods,
  Setting,
  Tickets,
  User,
} from '@element-plus/icons-vue'

export const ADMIN_MENUS = [
  { key: 'dashboard', label: '工作台', path: '/admin-console', icon: DataAnalysis, permission: 'can_view_dashboard' },
  { key: 'orders', label: '订单管理', path: '/admin-console/orders', icon: Tickets, permission: 'can_manage_orders' },
  { key: 'products', label: '商品管理', path: '/admin-console/products', icon: Goods, permission: 'can_manage_products' },
  { key: 'inventory', label: '库存管理', path: '/admin-console/inventory', icon: Box, permission: 'can_manage_inventory' },
  { key: 'payments', label: '支付流水', path: '/admin-console/payments', icon: CreditCard, permission: 'can_view_payments' },
  { key: 'users', label: '用户管理', path: '/admin-console/users', icon: User, permission: 'can_manage_users' },
  { key: 'content', label: '内容配置', path: '/admin-console/content', icon: Setting, permission: 'can_manage_settings' },
  { key: 'logs', label: '操作日志', path: '/admin-console/logs', icon: Document, permission: 'can_view_logs' },
]

export const canUseAdminAction = (session, permission) => Boolean(session?.permissions?.[permission])

export const adminMenusForSession = (session) =>
  ADMIN_MENUS.filter((item) => canUseAdminAction(session, item.permission))
