<template>
  <main class="admin-page" v-loading="loading">
    <div class="admin-page-head">
      <div>
        <h1>支付流水</h1>
        <p>排查渠道回调、交易号和异常流水</p>
      </div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <div class="admin-toolbar">
      <el-input v-model="filters.provider" clearable placeholder="渠道" />
      <el-select v-model="filters.status" clearable placeholder="状态">
        <el-option label="成功" value="success" />
        <el-option label="失败" value="failed" />
        <el-option label="已忽略" value="ignored" />
      </el-select>
      <el-button type="primary" :icon="Search" @click="load">查询</el-button>
    </div>

    <el-table :data="payments" size="small" class="admin-table" empty-text="暂无流水">
      <el-table-column prop="provider" label="渠道" width="90" />
      <el-table-column prop="order_no" label="订单号" min-width="160" />
      <el-table-column prop="trade_no" label="渠道单号" min-width="150" />
      <el-table-column prop="out_trade_no" label="商户单号" min-width="150" />
      <el-table-column prop="amount" label="金额" width="100" />
      <el-table-column prop="status" label="状态" width="90" />
      <el-table-column prop="note" label="备注" min-width="160" />
      <el-table-column prop="created_at" label="时间" width="180" />
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button size="small" :icon="View" @click="selected = row">载荷</el-button>
          <el-button v-if="canResolvePayments && row.status === 'failed'" size="small" type="primary" :icon="CircleCheck" @click="resolve(row)">处理</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-drawer v-model="payloadOpen" title="支付载荷" size="520px" @closed="selected = null">
      <pre>{{ JSON.stringify(selected?.raw_payload || {}, null, 2) }}</pre>
    </el-drawer>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CircleCheck, Refresh, Search, View } from '@element-plus/icons-vue'

import { fetchAdminPayments, resolveAdminPayment } from '../../api/adminConsole'
import { useAdminSessionStore } from '../../stores/adminSession'

const admin = useAdminSessionStore()
const loading = ref(false)
const payments = ref([])
const selected = ref(null)
const filters = reactive({ provider: '', status: '' })
const canResolvePayments = computed(() => Boolean(admin.permissions.can_resolve_payments))
const payloadOpen = computed({
  get: () => Boolean(selected.value),
  set: (value) => {
    if (!value) selected.value = null
  },
})

const load = async () => {
  loading.value = true
  try {
    const response = await fetchAdminPayments(filters)
    payments.value = response.results || []
  } catch (error) {
    ElMessage.error(error.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const resolve = async (payment) => {
  try {
    const { value } = await ElMessageBox.prompt('请输入处理原因', `流水 ${payment.id}`, {
      confirmButtonText: '提交',
      cancelButtonText: '取消',
      inputType: 'textarea',
      inputValidator: (text) => Boolean(text && text.trim()),
      inputErrorMessage: '原因不能为空',
    })
    await resolveAdminPayment(payment.id, { reason: value.trim() })
    ElMessage.success('流水已处理')
    await load()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(error.message || '处理失败')
  }
}

onMounted(load)
</script>
