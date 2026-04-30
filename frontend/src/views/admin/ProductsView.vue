<template>
  <main class="admin-page" v-loading="loading">
    <div class="admin-page-head">
      <div>
        <h1>商品管理</h1>
        <p>维护商品、分类、上下架和排序</p>
      </div>
      <div class="admin-head-actions">
        <el-button :icon="FolderAdd" @click="categoryDialog = true">新建分类</el-button>
        <el-button type="primary" :icon="Plus" @click="productDialog = true">新建商品</el-button>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </div>
    </div>

    <div class="admin-toolbar">
      <el-input v-model="filters.keyword" clearable placeholder="商品名 / 描述" :prefix-icon="Search" @keyup.enter="load" />
      <el-button type="primary" :icon="Search" @click="load">查询</el-button>
    </div>

    <section class="admin-grid products-layout">
      <div class="admin-panel">
        <h2>商品</h2>
        <el-table :data="products" size="small" class="admin-table" empty-text="暂无商品">
          <el-table-column prop="name" label="商品" min-width="170" />
          <el-table-column prop="category_name" label="分类" width="130" />
          <el-table-column prop="price" label="价格" width="100" />
          <el-table-column label="库存" width="210">
            <template #default="{ row }">
              可售 {{ row.stock?.available || 0 }} / 预留 {{ row.stock?.reserved || 0 }} / 已售 {{ row.stock?.sold || 0 }}
            </template>
          </el-table-column>
          <el-table-column label="上架" width="92">
            <template #default="{ row }">
              <el-switch v-model="row.is_active" @change="updateProduct(row, { is_active: row.is_active })" />
            </template>
          </el-table-column>
          <el-table-column label="排序" width="128">
            <template #default="{ row }">
              <el-input-number v-model="row.sort_order" size="small" :min="0" :controls="false" @change="updateProduct(row, { sort_order: row.sort_order })" />
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="admin-panel">
        <h2>分类</h2>
        <el-table :data="categories" size="small" empty-text="暂无分类">
          <el-table-column prop="name" label="名称" min-width="130" />
          <el-table-column prop="slug" label="标识" min-width="120" />
          <el-table-column label="启用" width="78">
            <template #default="{ row }">
              <el-switch v-model="row.is_active" @change="updateCategory(row)" />
            </template>
          </el-table-column>
          <el-table-column label="编辑" width="76">
            <template #default="{ row }">
              <el-button size="small" :icon="Edit" circle @click="openCategoryEdit(row)" />
            </template>
          </el-table-column>
        </el-table>
      </div>
    </section>

    <el-dialog v-model="productDialog" title="新建商品" width="560px">
      <el-form label-position="top">
        <el-form-item label="分类">
          <el-select v-model="productForm.category" filterable placeholder="选择分类">
            <el-option v-for="item in categories" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称"><el-input v-model="productForm.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="productForm.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="价格"><el-input v-model="productForm.price" /></el-form-item>
        <el-form-item label="图片 URL"><el-input v-model="productForm.image_url" /></el-form-item>
        <div class="admin-form-row">
          <el-form-item label="上架"><el-switch v-model="productForm.is_active" /></el-form-item>
          <el-form-item label="排序"><el-input-number v-model="productForm.sort_order" :min="0" /></el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="productDialog = false">取消</el-button>
        <el-button type="primary" @click="createProduct">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="categoryDialog" :title="categoryForm.id ? '编辑分类' : '新建分类'" width="420px">
      <el-form label-position="top">
        <el-form-item label="名称"><el-input v-model="categoryForm.name" /></el-form-item>
        <el-form-item label="标识"><el-input v-model="categoryForm.slug" /></el-form-item>
        <div class="admin-form-row">
          <el-form-item label="启用"><el-switch v-model="categoryForm.is_active" /></el-form-item>
          <el-form-item label="排序"><el-input-number v-model="categoryForm.sort_order" :min="0" /></el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="categoryDialog = false">取消</el-button>
        <el-button type="primary" @click="saveCategory">保存</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Edit, FolderAdd, Plus, Refresh, Search } from '@element-plus/icons-vue'

import {
  createAdminCategory,
  createAdminProduct,
  fetchAdminCategories,
  fetchAdminProducts,
  updateAdminCategory,
  updateAdminProduct,
} from '../../api/adminConsole'

const loading = ref(false)
const products = ref([])
const categories = ref([])
const productDialog = ref(false)
const categoryDialog = ref(false)
const filters = reactive({ keyword: '' })
const productForm = reactive({ category: '', name: '', description: '', price: '', image_url: '', is_active: true, sort_order: 0 })
const categoryForm = reactive({ id: null, name: '', slug: '', is_active: true, sort_order: 0 })

const load = async () => {
  loading.value = true
  try {
    const [productResponse, categoryResponse] = await Promise.all([
      fetchAdminProducts(filters),
      fetchAdminCategories({ page_size: 100 }),
    ])
    products.value = productResponse.results || []
    categories.value = categoryResponse.results || categoryResponse || []
  } catch (error) {
    ElMessage.error(error.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const updateProduct = async (row, payload) => {
  try {
    await updateAdminProduct(row.id, payload)
    ElMessage.success('商品已更新')
    await load()
  } catch (error) {
    ElMessage.error(error.message || '更新失败')
    await load()
  }
}

const createProduct = async () => {
  try {
    await createAdminProduct({ ...productForm })
    productDialog.value = false
    Object.assign(productForm, { category: '', name: '', description: '', price: '', image_url: '', is_active: true, sort_order: 0 })
    ElMessage.success('商品已创建')
    await load()
  } catch (error) {
    ElMessage.error(error.message || '创建失败')
  }
}

const openCategoryEdit = (row) => {
  Object.assign(categoryForm, row)
  categoryDialog.value = true
}

const updateCategory = async (row) => {
  try {
    await updateAdminCategory(row.id, { is_active: row.is_active })
    ElMessage.success('分类已更新')
    await load()
  } catch (error) {
    ElMessage.error(error.message || '更新失败')
    await load()
  }
}

const saveCategory = async () => {
  const payload = {
    name: categoryForm.name,
    slug: categoryForm.slug,
    is_active: categoryForm.is_active,
    sort_order: categoryForm.sort_order,
  }
  try {
    if (categoryForm.id) await updateAdminCategory(categoryForm.id, payload)
    else await createAdminCategory(payload)
    categoryDialog.value = false
    Object.assign(categoryForm, { id: null, name: '', slug: '', is_active: true, sort_order: 0 })
    ElMessage.success('分类已保存')
    await load()
  } catch (error) {
    ElMessage.error(error.message || '保存失败')
  }
}

onMounted(load)
</script>
