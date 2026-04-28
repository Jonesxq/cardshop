<template>
  <main class="page narrow">
    <section class="query-panel">
      <h1>订单查询</h1>
      <div class="query-row order-lookup-row">
        <el-input v-model="orderNo" size="large" placeholder="请输入订单号" @keyup.enter="search" />
        <el-input v-model="contact" size="large" placeholder="请输入下单联系方式" @keyup.enter="search" />
        <el-button type="primary" size="large" :icon="Search" :loading="loading" @click="search">查询</el-button>
        <el-button size="large" :icon="Refresh" :loading="loading" @click="search">刷新</el-button>
      </div>
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
        <div v-if="order.delivery_items.length" class="delivery-box">
          <h3>发货内容</h3>
          <pre>{{ order.delivery_items.join('\n') }}</pre>
        </div>
        <el-alert
          v-else-if="order.status === 'pending'"
          class="order-tip"
          type="warning"
          :closable="false"
          title="订单待支付或支付通知尚未到达，请稍后刷新。"
        />
        <el-alert
          v-else-if="order.status === 'expired'"
          class="order-tip"
          type="error"
          :closable="false"
          title="订单已过期，库存已释放，请重新下单。"
        />
      </article>
      <el-empty v-if="searched && !orders.length" description="未找到订单" />
    </section>
  </main>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { CreditCard, Refresh, Search } from '@element-plus/icons-vue'

import { completeDevPayment, fetchOrderPayment, queryOrders } from '../api/shop'

const route = useRoute()
const router = useRouter()
const orderNo = ref(route.query.order_no || route.query.keyword || sessionStorage.getItem('guest_order_no') || '')
const contact = ref(sessionStorage.getItem('guest_order_contact') || '')
const orders = ref([])
const loading = ref(false)
const searched = ref(false)
const payingOrderNo = ref('')
let pollTimer = null
let pollCount = 0

const saveLookup = () => {
  sessionStorage.setItem('guest_order_no', orderNo.value.trim())
  sessionStorage.setItem('guest_order_contact', contact.value.trim())
}

const search = async () => {
  if (!orderNo.value.trim()) {
    ElMessage.warning('请输入订单号')
    return
  }
  if (!contact.value.trim()) {
    ElMessage.warning('请输入下单联系方式')
    return
  }
  loading.value = true
  searched.value = true
  try {
    saveLookup()
    orders.value = await queryOrders({
      order_no: orderNo.value.trim(),
      contact: contact.value.trim(),
    })
    router.replace({ path: '/orders', query: { order_no: orderNo.value.trim() } })
    schedulePollingIfNeeded()
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.value = false
  }
}

const continuePayment = async (order) => {
  payingOrderNo.value = order.order_no
  try {
    const paymentOrder = await fetchOrderPayment(order.order_no, { contact: contact.value.trim() })
    if (paymentOrder.payment?.mode === 'dev') {
      await completeDevPayment(order.order_no, { contact: contact.value.trim() })
      ElMessage.success('支付成功，卡密已发货')
      await search()
      return
    }
    if (paymentOrder.payment?.redirect_url) {
      saveLookup()
      window.location.href = paymentOrder.payment.redirect_url
      return
    }
    ElMessage.error('支付链接生成失败，请联系管理员')
  } catch (error) {
    ElMessage.error(error.message)
    await search()
  } finally {
    payingOrderNo.value = ''
  }
}

const schedulePollingIfNeeded = () => {
  if (pollTimer) {
    window.clearTimeout(pollTimer)
    pollTimer = null
  }
  if (!orders.value.some((order) => order.status === 'pending') || pollCount >= 6) return
  pollCount += 1
  pollTimer = window.setTimeout(search, 5000)
}

const statusText = (status) =>
  ({
    pending: '待支付',
    paid: '已发货',
    expired: '已过期',
    cancelled: '已取消',
  })[status] || status

const formatTime = (value) => (value ? new Date(value).toLocaleString() : '-')

onMounted(() => {
  if (orderNo.value && contact.value) search()
})

onBeforeUnmount(() => {
  if (pollTimer) window.clearTimeout(pollTimer)
})
</script>
