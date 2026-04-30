<template>
  <main class="admin-page" v-loading="loading">
    <div class="admin-page-head">
      <div>
        <h1>工作台</h1>
        <p>订单、支付、库存的实时概览</p>
      </div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <section class="admin-metrics">
      <div v-for="item in metricItems" :key="item.key" class="admin-metric">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </div>
    </section>

    <section class="admin-grid two">
      <div class="admin-panel">
        <h2>低库存商品</h2>
        <el-table :data="dashboard.low_stock_products || []" size="small" empty-text="暂无低库存">
          <el-table-column prop="name" label="商品" min-width="150" />
          <el-table-column prop="available" label="可售" width="90" />
        </el-table>
      </div>
      <div class="admin-panel">
        <h2>热销商品</h2>
        <el-table :data="dashboard.top_products || []" size="small" empty-text="暂无数据">
          <el-table-column prop="name" label="商品" min-width="150" />
          <el-table-column prop="paid_order_count" label="订单" width="80" />
          <el-table-column prop="paid_amount" label="金额" width="110" />
        </el-table>
      </div>
      <div class="admin-panel">
        <h2>异常支付</h2>
        <el-table :data="dashboard.abnormal_payments || []" size="small" empty-text="暂无异常">
          <el-table-column prop="order_no" label="订单号" min-width="150" />
          <el-table-column prop="provider" label="渠道" width="90" />
          <el-table-column prop="status" label="状态" width="90" />
          <el-table-column prop="amount" label="金额" width="100" />
        </el-table>
      </div>
      <div class="admin-panel">
        <h2>近 7 日成交</h2>
        <el-table :data="dashboard.trend || []" size="small" empty-text="暂无数据">
          <el-table-column prop="date" label="日期" min-width="120" />
          <el-table-column prop="order_count" label="订单" width="80" />
          <el-table-column prop="paid_amount" label="金额" width="110" />
        </el-table>
      </div>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

import { fetchAdminDashboard } from '../../api/adminConsole'

const loading = ref(false)
const dashboard = ref({ summary: {} })

const metricItems = computed(() => {
  const summary = dashboard.value.summary || {}
  return [
    { key: 'orders', label: '今日订单', value: summary.today_order_count ?? 0 },
    { key: 'paid', label: '今日实收', value: summary.today_paid_amount ?? '0.00' },
    { key: 'pending', label: '待支付订单', value: summary.pending_order_count ?? 0 },
    { key: 'stock', label: '低库存商品', value: summary.low_stock_product_count ?? 0 },
    { key: 'payments', label: '异常支付', value: summary.abnormal_payment_count ?? 0 },
  ]
})

const load = async () => {
  loading.value = true
  try {
    dashboard.value = await fetchAdminDashboard()
  } catch (error) {
    ElMessage.error(error.message || '加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
