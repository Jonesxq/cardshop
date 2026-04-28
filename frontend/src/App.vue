<template>
  <div class="app-shell">
    <header class="topbar">
      <RouterLink class="brand" to="/">
        <span class="brand-mark">AI</span>
        <span>{{ siteName }}</span>
      </RouterLink>
      <nav class="nav-links">
        <RouterLink to="/">
          <el-icon><HomeFilled /></el-icon>
          商品
        </RouterLink>
        <RouterLink to="/orders">
          <el-icon><Search /></el-icon>
          查单
        </RouterLink>
        <RouterLink v-if="auth.isLoggedIn" to="/account/orders">
          <el-icon><Tickets /></el-icon>
          我的订单
        </RouterLink>
        <a href="https://ping0.cc/" target="_blank" rel="noopener noreferrer" aria-label="打开 IP 检测">
          <el-icon><Monitor /></el-icon>
          IP 检测
        </a>
      </nav>
      <div class="user-actions">
        <el-button v-if="!auth.isLoggedIn" :icon="User" @click="$router.push('/login')">登录</el-button>
        <el-button v-else :icon="SwitchButton" @click="auth.logout()">退出</el-button>
      </div>
    </header>
    <RouterView @site-loaded="siteName = $event.site_name || siteName" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { HomeFilled, Monitor, Search, SwitchButton, Tickets, User } from '@element-plus/icons-vue'
import { useAuthStore } from './stores/auth'

const siteName = ref('AI 发卡商城')
const auth = useAuthStore()
</script>
