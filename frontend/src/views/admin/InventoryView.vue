<template>
  <main class="admin-page" v-loading="loading">
    <div class="admin-page-head">
      <div>
        <h1>库存管理</h1>
        <p>批量导入卡密并查看当前卡库存</p>
      </div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <section class="admin-grid two">
      <div class="admin-panel">
        <h2>导入卡密</h2>
        <el-form label-position="top">
          <el-form-item label="商品">
            <el-select v-model="form.product_id" filterable placeholder="选择商品" @change="handleImportProductChange">
              <el-option v-for="product in products" :key="product.id" :label="product.name" :value="product.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="卡密">
            <el-input v-model="form.cards" type="textarea" :rows="10" placeholder="每行一条卡密" @input="clearPreview" />
          </el-form-item>
          <el-form-item label="原因">
            <el-input v-model="form.reason" placeholder="例如：供应商补货批次 20260430" />
          </el-form-item>
          <div class="admin-actions">
            <el-button :icon="View" @click="preview">预览</el-button>
            <el-button type="primary" :disabled="!canCommit" @click="commit">确认导入</el-button>
          </div>
        </el-form>
      </div>

      <div class="admin-panel">
        <h2>预览结果</h2>
        <el-descriptions v-if="previewResult" :column="2" border size="small">
          <el-descriptions-item label="总行数">{{ previewResult.total_rows }}</el-descriptions-item>
          <el-descriptions-item label="可导入">{{ previewResult.valid_count }}</el-descriptions-item>
          <el-descriptions-item label="空行">{{ previewResult.empty_count }}</el-descriptions-item>
          <el-descriptions-item label="批内重复">{{ previewResult.same_batch_duplicate_count }}</el-descriptions-item>
          <el-descriptions-item label="已存在">{{ previewResult.existing_duplicate_count }}</el-descriptions-item>
        </el-descriptions>
        <el-table v-if="previewResult?.rejected_samples?.length" :data="previewResult.rejected_samples" size="small" class="admin-nested-table">
          <el-table-column prop="row_number" label="行" width="70" />
          <el-table-column prop="status" label="原因" width="140" />
          <el-table-column prop="value" label="样例" min-width="160" />
        </el-table>
        <el-empty v-if="!previewResult" description="暂无预览" />
      </div>
    </section>

    <div class="admin-panel admin-section-panel">
      <div class="admin-panel-head">
        <h2>当前卡列表</h2>
        <div class="admin-toolbar compact">
          <el-select v-model="cardFilters.product_id" clearable filterable placeholder="商品" @change="loadCards">
            <el-option v-for="product in products" :key="product.id" :label="product.name" :value="product.id" />
          </el-select>
          <el-select v-model="cardFilters.status" clearable placeholder="状态" @change="loadCards">
            <el-option label="可售" value="available" />
            <el-option label="预留" value="reserved" />
            <el-option label="已售" value="sold" />
            <el-option label="作废" value="void" />
          </el-select>
        </div>
      </div>
      <el-table :data="cards" size="small" class="admin-table" empty-text="暂无卡密">
        <el-table-column prop="product_name" label="商品" min-width="160" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="reserved_order_no" label="预留订单" min-width="150" />
        <el-table-column prop="reserved_until" label="预留到期" width="180" />
        <el-table-column prop="sold_at" label="售出时间" width="180" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
      </el-table>
    </div>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, View } from '@element-plus/icons-vue'

import { commitCardImport, fetchAdminCards, fetchAdminProducts, previewCardImport } from '../../api/adminConsole'

const loading = ref(false)
const products = ref([])
const cards = ref([])
const previewResult = ref(null)
const previewSnapshot = ref(null)
const form = reactive({ product_id: '', cards: '', reason: '' })
const cardFilters = reactive({ product_id: '', status: '' })
const canCommit = computed(() => Boolean(
  previewResult.value
  && previewSnapshot.value
  && previewSnapshot.value.product_id === form.product_id
  && previewSnapshot.value.cards === form.cards,
))

const loadProducts = async () => {
  const response = await fetchAdminProducts({ page_size: 100 })
  products.value = response.results || []
}

const loadCards = async () => {
  const response = await fetchAdminCards(cardFilters)
  cards.value = response.results || []
}

const clearPreview = () => {
  previewResult.value = null
  previewSnapshot.value = null
}

const handleImportProductChange = async () => {
  clearPreview()
  await loadCards()
}

const load = async () => {
  loading.value = true
  try {
    await loadProducts()
    await loadCards()
  } catch (error) {
    ElMessage.error(error.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const preview = async () => {
  if (!form.product_id) return ElMessage.warning('请选择商品')
  try {
    previewResult.value = await previewCardImport({ product_id: form.product_id, cards: form.cards })
    previewSnapshot.value = { product_id: form.product_id, cards: form.cards }
  } catch (error) {
    ElMessage.error(error.message || '预览失败')
  }
}

const commit = async () => {
  if (!canCommit.value) return ElMessage.warning('请先预览当前商品和卡密')
  if (!form.reason.trim()) return ElMessage.warning('原因不能为空')
  try {
    const result = await commitCardImport({ product_id: form.product_id, cards: form.cards, reason: form.reason.trim() })
    ElMessage.success(`已导入 ${result.created_count || 0} 条`)
    clearPreview()
    form.cards = ''
    await loadCards()
  } catch (error) {
    ElMessage.error(error.message || '导入失败')
  }
}

onMounted(load)
</script>
