<template>
  <main class="page auth-page">
    <section class="auth-panel">
      <h1>注册</h1>
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" type="email" autocomplete="email" />
        </el-form-item>
        <el-form-item label="验证码">
          <div class="code-row">
            <el-input v-model="form.code" />
            <el-button :icon="Message" :loading="sending" @click="sendCode">发送</el-button>
          </div>
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-alert v-if="devCode" type="info" :closable="false" :title="`开发验证码：${devCode}`" />
        <el-button type="primary" :icon="UserFilled" :loading="loading" @click="submit">创建账号</el-button>
      </el-form>
      <div class="auth-links">
        <RouterLink to="/login">已有账号登录</RouterLink>
      </div>
    </section>
  </main>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Message, UserFilled } from '@element-plus/icons-vue'

import { register, sendEmailCode } from '../api/auth'
import { formatApiError } from '../api/client'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const loading = ref(false)
const sending = ref(false)
const devCode = ref('')
const form = reactive({ email: '', password: '', code: '' })

const sendCode = async () => {
  if (!form.email.trim()) {
    ElMessage.warning('请先填写邮箱')
    return
  }
  sending.value = true
  try {
    const data = await sendEmailCode({ email: form.email, purpose: 'register' })
    devCode.value = data.dev_code || ''
    ElMessage.success('验证码已发送')
  } catch (error) {
    ElMessage.error(formatApiError(error))
  } finally {
    sending.value = false
  }
}

const submit = async () => {
  if (!form.email.trim()) {
    ElMessage.warning('请填写邮箱')
    return
  }
  if (!form.code.trim()) {
    ElMessage.warning('请填写验证码')
    return
  }
  if (form.password.length < 8) {
    ElMessage.warning('密码至少需要 8 位')
    return
  }
  loading.value = true
  try {
    const data = await register(form)
    auth.setSession(data)
    ElMessage.success('注册成功')
    router.push(route.query.redirect || '/account/orders')
  } catch (error) {
    ElMessage.error(formatApiError(error))
  } finally {
    loading.value = false
  }
}
</script>
