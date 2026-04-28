<template>
  <main class="page auth-page">
    <section class="auth-panel">
      <h1>找回密码</h1>
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" type="email" />
        </el-form-item>
        <el-form-item label="验证码">
          <div class="code-row">
            <el-input v-model="form.code" />
            <el-button :icon="Message" :loading="sending" @click="sendCode">发送</el-button>
          </div>
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-alert v-if="devCode" type="info" :closable="false" :title="`开发验证码：${devCode}`" />
        <el-button type="primary" :icon="RefreshLeft" :loading="loading" @click="submit">重置密码</el-button>
      </el-form>
    </section>
  </main>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Message, RefreshLeft } from '@element-plus/icons-vue'

import { resetPassword, sendEmailCode } from '../api/auth'
import { formatApiError } from '../api/client'

const router = useRouter()
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
    const data = await sendEmailCode({ email: form.email, purpose: 'reset' })
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
    ElMessage.warning('新密码至少需要 8 位')
    return
  }
  loading.value = true
  try {
    await resetPassword(form)
    ElMessage.success('密码已重置')
    router.push('/login')
  } catch (error) {
    ElMessage.error(formatApiError(error))
  } finally {
    loading.value = false
  }
}
</script>
