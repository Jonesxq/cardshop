<template>
  <div class="admin-console">
    <aside class="admin-sidebar">
      <RouterLink class="admin-brand" to="/admin-console">
        <el-icon><Monitor /></el-icon>
        <span>运营后台</span>
      </RouterLink>
      <nav class="admin-menu" aria-label="admin">
        <RouterLink v-for="item in menus" :key="item.key" :to="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
    </aside>

    <section class="admin-main">
      <header class="admin-header">
        <div class="admin-user">
          <strong>{{ admin.user?.email || '未登录' }}</strong>
          <el-tag size="small" effect="plain">{{ roleLabel }}</el-tag>
        </div>
        <div class="admin-header-actions">
          <el-button :icon="Refresh" :loading="admin.loading" @click="refreshPermissions">刷新权限</el-button>
          <el-button :icon="SwitchButton" @click="logout">退出</el-button>
        </div>
      </header>
      <RouterView />
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Monitor, Refresh, SwitchButton } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

import { adminMenusForSession } from '../../admin/permissions'
import { useAdminSessionStore } from '../../stores/adminSession'
import { useAuthStore } from '../../stores/auth'

const admin = useAdminSessionStore()
const auth = useAuthStore()
const router = useRouter()

const menus = computed(() => adminMenusForSession(admin))
const roleLabel = computed(() => ({
  operator: '运营',
  finance: '财务',
  superadmin: '超级管理员',
}[admin.role] || '无角色'))

const refreshPermissions = async () => {
  try {
    await admin.load({ force: true })
    ElMessage.success('权限已刷新')
  } catch (error) {
    ElMessage.error(error.message || '刷新失败')
  }
}

const logout = () => {
  auth.logout()
  admin.reset()
  router.push({ path: '/login', query: { redirect: '/admin-console' } })
}
</script>
