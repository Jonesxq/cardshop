<template>
  <main class="page narrow">
    <section class="query-panel">
      <h1>我的订单</h1>
      <el-button :icon="Refresh" :loading="loading" @click="loadOrders">刷新</el-button>
    </section>

    <section class="result-list" v-loading="loading">
      <article class="order-result" v-for="order in orders" :key="order.order_no">
        <div class="order-head">
          <div>
            <span class="status-pill" :class="order.status">{{ statusText(order.status) }}</span>
            <h2>{{ order.product_name }}</h2>
          </div>
          <div class="order-actions">
            <strong>¥{{ order.amount }}</strong>
            <el-button
              v-if="order.status === 'pending'"
              type="primary"
              :icon="CreditCard"
              :loading="payingOrderNo === order.order_no"
              @click="continuePayment(order)"
            >
              继续支付
            </el-button>
          </div>
        </div>
        <dl>
          <div><dt>订单号</dt><dd>{{ order.order_no }}</dd></div>
          <div><dt>数量</dt><dd>{{ order.quantity }}</dd></div>
          <div><dt>创建时间</dt><dd>{{ formatTime(order.created_at) }}</dd></div>
          <div><dt>过期时间</dt><dd>{{ formatTime(order.expires_at) }}</dd></div>
        </dl>
        <el-alert
          v-if="order.status === 'pending'"
          class="order-tip"
          type="warning"
          :closable="false"
          title="该订单尚未支付，点击继续支付可重新跳转到支付页面。"
        />
        <el-alert
          v-if="order.status === 'expired'"
          class="order-tip"
          type="error"
          :closable="false"
          title="该订单已过期，库存已释放，请重新下单。"
        />
        <div v-if="order.delivery_items.length" class="delivery-box">
          <h3>发货内容</h3>
          <pre>{{ order.delivery_items.join('\n') }}</pre>
        </div>
      </article>
      <el-empty v-if="!loading && !orders.length" description="暂无订单" />
    </section>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { CreditCard, Refresh } from '@element-plus/icons-vue'

import { fetchMyOrders } from '../api/auth'
import { completeDevPayment, fetchOrderPayment } from '../api/shop'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const loading = ref(false)
const payingOrderNo = ref('')
const orders = ref([])

const loadOrders = async () => {
  if (!auth.isLoggedIn) {
    router.push('/login')
    return
  }
  loading.value = true
  try {
    orders.value = await fetchMyOrders()
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.value = false
  }
}

const continuePayment = async (order) => {
  payingOrderNo.value = order.order_no
  try {
    const paymentOrder = await fetchOrderPayment(order.order_no)
    if (paymentOrder.payment?.mode === 'dev') {
      await completeDevPayment(order.order_no)
      ElMessage.success('支付成功，卡密已发货')
      await loadOrders()
      return
    }
    if (paymentOrder.payment?.redirect_url) {
      window.location.href = paymentOrder.payment.redirect_url
      return
    }
    ElMessage.error('支付链接生成失败，请联系管理员')
  } catch (error) {
    ElMessage.error(error.message)
    await loadOrders()
  } finally {
    payingOrderNo.value = ''
  }
}

const statusText = (status) =>
  ({
    pending: '待支付',
    paid: '已发货',
    expired: '已过期',
    cancelled: '已取消',
  })[status] || status

const formatTime = (value) => (value ? new Date(value).toLocaleString() : '-')

onMounted(loadOrders)
</script>
