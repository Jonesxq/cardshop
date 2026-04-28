<template>
  <main class="page">
    <section class="shop-band">
      <div class="shop-head">
        <div>
          <p class="eyebrow">自动发货 · 库存实时锁定</p>
          <h1>{{ home.site.site_name }}</h1>
          <p class="subcopy">{{ home.site.footer_text }}</p>
        </div>
        <el-button :icon="Search" size="large" @click="$router.push('/orders')">订单查询</el-button>
      </div>

      <div class="notice-row" v-if="home.announcements.length">
        <div class="notice" v-for="item in home.announcements" :key="item.id">
          <el-icon><Bell /></el-icon>
          <div>
            <strong>{{ item.title }}</strong>
            <p>{{ item.content }}</p>
          </div>
        </div>
      </div>
    </section>

    <section class="content-grid">
      <aside class="category-panel">
        <button
          class="category-item"
          :class="{ active: activeCategory === 'all' }"
          @click="activeCategory = 'all'"
        >
          全部商品
        </button>
        <button
          v-for="category in home.categories"
          :key="category.id"
          class="category-item"
          :class="{ active: activeCategory === category.id }"
          @click="activeCategory = category.id"
        >
          {{ category.name }}
        </button>
      </aside>

      <div class="products-grid" v-loading="loading">
        <article class="product-card" v-for="product in filteredProducts" :key="product.id">
          <img :src="product.image_url" :alt="product.name" />
          <div class="product-body">
            <span class="category-chip">{{ product.category_name }}</span>
            <h2>{{ product.name }}</h2>
            <p>{{ product.description }}</p>
            <div class="product-meta">
              <strong>¥{{ product.price }}</strong>
              <span :class="{ danger: product.is_sold_out }">库存 {{ product.stock }}</span>
            </div>
            <el-button
              type="primary"
              :icon="ShoppingCart"
              :disabled="product.is_sold_out"
              @click="openOrder(product)"
            >
              立即购买
            </el-button>
          </div>
        </article>
      </div>
    </section>

    <el-dialog v-model="orderDialog" width="520px" :title="selectedProduct?.name || '创建订单'">
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="购买数量">
          <el-input-number v-model="orderForm.quantity" :min="1" :max="20" />
        </el-form-item>
        <el-form-item label="联系方式">
          <el-input v-model="orderForm.contact" placeholder="邮箱、手机号或其他可用于查单的联系方式" />
        </el-form-item>
        <el-form-item label="支付方式">
          <el-segmented v-model="orderForm.pay_type" :options="payOptions" />
        </el-form-item>
      </el-form>
      <div class="dialog-summary" v-if="selectedProduct">
        <span>应付金额</span>
        <strong>¥{{ totalAmount }}</strong>
      </div>
      <template #footer>
        <el-button @click="orderDialog = false">取消</el-button>
        <el-button type="primary" :icon="ShoppingCart" :loading="submitting" @click="submitOrder">提交订单</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="paymentDialog" width="560px" title="订单已创建">
      <div class="payment-box" v-if="createdOrder">
        <p>订单号：<strong>{{ createdOrder.order_no }}</strong></p>
        <p>金额：<strong>¥{{ createdOrder.amount }}</strong></p>
        <p>请在 {{ formatTime(createdOrder.expires_at) }} 前完成支付。</p>
        <el-alert
          v-if="createdOrder.payment.mode === 'dev'"
          type="info"
          :closable="false"
          title="当前为开发模式，可直接模拟支付成功。"
        />
        <el-alert
          v-if="createdOrder.payment.mode === 'alipay'"
          type="success"
          :closable="false"
          title="当前将跳转到支付宝沙箱网页支付。支付后请返回订单查询页刷新状态。"
        />
      </div>
      <template #footer>
        <el-button @click="goQueryOrder">去查单</el-button>
        <el-button
          v-if="createdOrder?.payment.mode === 'dev'"
          type="success"
          :icon="CircleCheck"
          :loading="paying"
          @click="simulatePayment"
        >
          模拟支付成功
        </el-button>
        <el-button v-else type="primary" :icon="CreditCard" @click="goPay">前往支付宝支付</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Bell, CircleCheck, CreditCard, Search, ShoppingCart } from '@element-plus/icons-vue'

import { completeDevPayment, createOrder, fetchHome } from '../api/shop'
import { useAuthStore } from '../stores/auth'

const emit = defineEmits(['site-loaded'])
const router = useRouter()
const auth = useAuthStore()

const loading = ref(true)
const submitting = ref(false)
const paying = ref(false)
const activeCategory = ref('all')
const orderDialog = ref(false)
const paymentDialog = ref(false)
const selectedProduct = ref(null)
const createdOrder = ref(null)
const createdOrderContact = ref('')
const home = reactive({
  site: {},
  announcements: [],
  categories: [],
  products: [],
})
const orderForm = reactive({
  quantity: 1,
  contact: '',
  pay_type: 'alipay',
})
const payOptions = [{ label: '支付宝', value: 'alipay' }]

const filteredProducts = computed(() => {
  if (activeCategory.value === 'all') return home.products
  return home.products.filter((item) => item.category_id === activeCategory.value)
})

const totalAmount = computed(() => {
  if (!selectedProduct.value) return '0.00'
  return (Number(selectedProduct.value.price) * orderForm.quantity).toFixed(2)
})

const saveGuestOrderLookup = (orderNo, contact) => {
  sessionStorage.setItem('guest_order_no', orderNo)
  sessionStorage.setItem('guest_order_contact', contact)
}

const loadHome = async () => {
  loading.value = true
  try {
    const data = await fetchHome()
    Object.assign(home, data)
    emit('site-loaded', data.site)
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.value = false
  }
}

const openOrder = (product) => {
  selectedProduct.value = product
  orderForm.quantity = 1
  orderForm.contact = auth.user?.email || sessionStorage.getItem('guest_order_contact') || ''
  orderForm.pay_type = 'alipay'
  orderDialog.value = true
}

const submitOrder = async () => {
  const contact = orderForm.contact.trim()
  if (!contact) {
    ElMessage.warning('请填写联系方式')
    return
  }
  submitting.value = true
  try {
    createdOrder.value = await createOrder({
      product_id: selectedProduct.value.id,
      quantity: orderForm.quantity,
      contact,
      pay_type: orderForm.pay_type,
    })
    createdOrderContact.value = contact
    saveGuestOrderLookup(createdOrder.value.order_no, contact)
    orderDialog.value = false
    paymentDialog.value = true
    await loadHome()
  } catch (error) {
    const existingOrderNo = error.response?.data?.existing_order_no
    if (existingOrderNo) {
      saveGuestOrderLookup(existingOrderNo, contact)
      try {
        await ElMessageBox.confirm(
          '你已有该商品未支付订单，请先继续支付或等待订单过期。',
          '已有未支付订单',
          {
            confirmButtonText: auth.isLoggedIn ? '去我的订单' : '去查单',
            cancelButtonText: '留在当前页',
            type: 'warning',
          },
        )
        if (auth.isLoggedIn) {
          router.push('/account/orders')
        } else {
          router.push({ path: '/orders', query: { order_no: existingOrderNo } })
        }
      } catch {
        // User chose to stay on the current page.
      }
      return
    }
    ElMessage.error(error.message)
  } finally {
    submitting.value = false
  }
}

const simulatePayment = async () => {
  paying.value = true
  try {
    const result = await completeDevPayment(createdOrder.value.order_no, {
      contact: createdOrderContact.value,
    })
    ElMessage.success('支付成功，卡密已发货')
    paymentDialog.value = false
    await loadHome()
    router.push({ path: '/orders', query: { order_no: result.order_no } })
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    paying.value = false
  }
}

const goQueryOrder = () => {
  if (createdOrder.value) {
    saveGuestOrderLookup(createdOrder.value.order_no, createdOrderContact.value)
    router.push({ path: '/orders', query: { order_no: createdOrder.value.order_no } })
  }
}

const goPay = () => {
  if (!createdOrder.value?.payment?.redirect_url) {
    ElMessage.error('支付参数缺失，请联系管理员')
    return
  }
  window.location.href = createdOrder.value.payment.redirect_url
}

const formatTime = (value) => new Date(value).toLocaleString()

onMounted(loadHome)
</script>
