import { createRouter, createWebHistory } from 'vue-router'

import HomeView from '../views/HomeView.vue'
import LoginView from '../views/LoginView.vue'
import RegisterView from '../views/RegisterView.vue'
import ResetPasswordView from '../views/ResetPasswordView.vue'
import OrderQueryView from '../views/OrderQueryView.vue'
import AccountOrdersView from '../views/AccountOrdersView.vue'
import AdminConsoleLayout from '../views/admin/AdminConsoleLayout.vue'
import AdminForbiddenView from '../views/admin/AdminForbiddenView.vue'
import AdminDashboardView from '../views/admin/DashboardView.vue'
import AdminOrdersView from '../views/admin/OrdersView.vue'
import AdminProductsView from '../views/admin/ProductsView.vue'
import AdminInventoryView from '../views/admin/InventoryView.vue'
import AdminPaymentsView from '../views/admin/PaymentsView.vue'
import AdminUsersView from '../views/admin/UsersView.vue'
import AdminContentView from '../views/admin/ContentView.vue'
import AdminLogsView from '../views/admin/LogsView.vue'
import { useAdminSessionStore } from '../stores/adminSession'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/orders', name: 'orders-query', component: OrderQueryView },
    { path: '/login', name: 'login', component: LoginView },
    { path: '/register', name: 'register', component: RegisterView },
    { path: '/reset-password', name: 'reset-password', component: ResetPasswordView },
    { path: '/account/orders', name: 'account-orders', component: AccountOrdersView, meta: { requiresAuth: true } },
    {
      path: '/admin-console',
      component: AdminConsoleLayout,
      meta: { requiresAuth: true, requiresAdmin: true },
      children: [
        { path: '', name: 'admin-dashboard', component: AdminDashboardView },
        { path: 'orders', name: 'admin-orders', component: AdminOrdersView },
        { path: 'products', name: 'admin-products', component: AdminProductsView },
        { path: 'inventory', name: 'admin-inventory', component: AdminInventoryView },
        { path: 'payments', name: 'admin-payments', component: AdminPaymentsView },
        { path: 'users', name: 'admin-users', component: AdminUsersView },
        { path: 'content', name: 'admin-content', component: AdminContentView },
        { path: 'logs', name: 'admin-logs', component: AdminLogsView },
      ],
    },
    { path: '/admin-console/forbidden', name: 'admin-forbidden', component: AdminForbiddenView },
  ],
})

router.beforeEach(async (to) => {
  if (to.meta.requiresAuth && !localStorage.getItem('access_token')) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.meta.requiresAdmin) {
    const adminSession = useAdminSessionStore()
    try {
      await adminSession.load()
    } catch {
      return { path: '/admin-console/forbidden' }
    }
  }
  return true
})

export default router
