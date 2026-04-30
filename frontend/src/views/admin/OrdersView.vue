<template>
  <main class="admin-page" v-loading="loading">
    <div class="admin-page-head">
      <div>
        <h1>订单管理</h1>
        <p>处理付款、发货、库存释放等订单动作</p>
      </div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <div class="admin-toolbar">
      <el-input v-model="filters.keyword" clearable placeholder="订单号 / 联系方式" :prefix-icon="Search" @keyup.enter="load" />
      <el-select v-model="filters.status" clearable placeholder="状态">
        <el-option label="待支付" value="pending" />
        <el-option label="已支付" value="paid" />
        <el-option label="已取消" value="cancelled" />
        <el-option label="已过期" value="expired" />
      </el-select>
      <el-button type="primary" :icon="Search" @click="load">查询</el-button>
    </div>

    <el-table :data="orders" size="small" class="admin-table" empty-text="暂无订单">
      <el-table-column type="expand" width="44">
        <template #default="{ row }">
          <div class="admin-expand">
            <strong>发货内容</strong>
            <pre>{{ formatDelivery(row.delivery_items) }}</pre>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="order_no" label="订单号" min-width="170" />
      <el-table-column prop="product_name" label="商品" min-width="150" />
      <el-table-column prop="contact" label="联系" min-width="160" />
      <el-table-column prop="amount" label="金额" width="100" />
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column prop="paid_at" label="支付时间" width="180" />
      <el-table-column label="操作" width="390" fixed="right">
        <template #default="{ row }">
          <div class="admin-row-actions">
            <el-button v-if="row.status === 'pending'" size="small" :icon="CircleCheck" @click="runOrderAction(row, markAdminOrderPaid)">标记支付</el-button>
            <el-button v-if="row.status === 'pending' || row.status === 'expired'" size="small" :icon="Close" @click="runOrderAction(row, cancelAdminOrder)">取消</el-button>
            <el-button v-if="row.status === 'paid'" size="small" :icon="Tickets" @click="runOrderAction(row, redeliverAdminOrder)">重发</el-button>
            <el-button v-if="row.status === 'paid'" size="small" :icon="RefreshRight" @click="runOrderAction(row, replaceAdminOrderCard)">换卡</el-button>
            <el-button v-if="row.status === 'pending'" size="small" :icon="Box" @click="runOrderAction(row, releaseAdminOrderStock)">释放</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
  </main>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Box, CircleCheck, Close, Refresh, RefreshRight, Search, Tickets } from '@element-plus/icons-vue'

import {
  cancelAdminOrder,
  fetchAdminOrders,
  markAdminOrderPaid,
  redeliverAdminOrder,
  releaseAdminOrderStock,
  replaceAdminOrderCard,
} from '../../api/adminConsole'

const loading = ref(false)
const orders = ref([])
const filters = reactive({ keyword: '', status: '' })

const load = async () => {
  loading.value = true
  try {
    const response = await fetchAdminOrders(filters)
    orders.value = response.results || []
  } catch (error) {
    ElMessage.error(error.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const promptReason = async (title) => {
  const { value } = await ElMessageBox.prompt('请输入操作原因', title, {
    confirmButtonText: '提交',
    cancelButtonText: '取消',
    inputType: 'textarea',
    inputValidator: (text) => Boolean(text && text.trim()),
    inputErrorMessage: '原因不能为空',
  })
  return value.trim()
}

const runOrderAction = async (order, action) => {
  try {
    const reason = await promptReason(`订单 ${order.order_no}`)
    await action(order.id, { reason })
    ElMessage.success('操作已记录')
    await load()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(error.message || '操作失败')
  }
}

const formatDelivery = (items) => {
  if (!items || !items.length) return '暂无发货内容'
  return items.map((item) => (typeof item === 'string' ? item : JSON.stringify(item))).join('\n')
}

onMounted(load)
</script>
