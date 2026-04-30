<template>
  <main class="page auth-page">
    <section class="auth-panel">
      <h1>登录</h1>
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="账号 / 邮箱">
          <el-input v-model="form.email" type="text" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password autocomplete="current-password" />
        </el-form-item>
        <el-button type="primary" :icon="Lock" :loading="loading" @click="submit">登录</el-button>
      </el-form>
      <div class="auth-links">
        <RouterLink to="/register">创建账号</RouterLink>
        <RouterLink to="/reset-password">找回密码</RouterLink>
      </div>
    </section>
  </main>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Lock } from '@element-plus/icons-vue'

import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const loading = ref(false)
const form = reactive({ email: '', password: '' })

const submit = async () => {
  loading.value = true
  try {
    await auth.login(form)
    ElMessage.success('登录成功')
    router.push(route.query.redirect || '/account/orders')
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.value = false
  }
}
</script>
