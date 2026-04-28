import { createRouter, createWebHistory } from 'vue-router'

import HomeView from '../views/HomeView.vue'
import LoginView from '../views/LoginView.vue'
import RegisterView from '../views/RegisterView.vue'
import ResetPasswordView from '../views/ResetPasswordView.vue'
import OrderQueryView from '../views/OrderQueryView.vue'
import AccountOrdersView from '../views/AccountOrdersView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/orders', name: 'orders-query', component: OrderQueryView },
    { path: '/login', name: 'login', component: LoginView },
    { path: '/register', name: 'register', component: RegisterView },
    { path: '/reset-password', name: 'reset-password', component: ResetPasswordView },
    { path: '/account/orders', name: 'account-orders', component: AccountOrdersView, meta: { requiresAuth: true } },
  ],
})

router.beforeEach((to) => {
  if (to.meta.requiresAuth && !localStorage.getItem('access_token')) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  return true
})

export default router
