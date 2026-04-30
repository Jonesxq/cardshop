<template>
  <main class="admin-page" v-loading="loading">
    <div class="admin-page-head">
      <div>
        <h1>用户管理</h1>
        <p>查看用户交易概览并维护员工权限</p>
      </div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <div class="admin-toolbar">
      <el-input v-model="filters.keyword" clearable placeholder="邮箱 / 用户名" :prefix-icon="Search" @keyup.enter="load" />
      <el-button type="primary" :icon="Search" @click="load">查询</el-button>
    </div>

    <el-table :data="users" size="small" class="admin-table" empty-text="暂无用户">
      <el-table-column prop="email" label="邮箱" min-width="190" />
      <el-table-column prop="is_active" label="启用" width="86">
        <template #default="{ row }">
          <el-switch v-model="row.is_active" :disabled="!canManageStaff" @change="save(row)" />
        </template>
      </el-table-column>
      <el-table-column prop="is_staff" label="员工" width="86">
        <template #default="{ row }">
          <el-switch v-model="row.is_staff" :disabled="!canManageStaff" @change="save(row)" />
        </template>
      </el-table-column>
      <el-table-column prop="is_superuser" label="超管" width="72">
        <template #default="{ row }">{{ row.is_superuser ? '是' : '否' }}</template>
      </el-table-column>
      <el-table-column label="角色" width="150">
        <template #default="{ row }">
          <el-select v-model="row.role" :disabled="!canManageStaff" @change="save(row)">
            <el-option label="运营" value="operator" />
            <el-option label="财务" value="finance" />
            <el-option label="超级管理员" value="superadmin" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column prop="order_count" label="订单数" width="90" />
      <el-table-column prop="total_paid_amount" label="支付金额" width="120" />
    </el-table>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'

import { fetchAdminUsers, updateAdminUser } from '../../api/adminConsole'
import { useAdminSessionStore } from '../../stores/adminSession'

const admin = useAdminSessionStore()
const loading = ref(false)
const users = ref([])
const filters = reactive({ keyword: '' })
const canManageStaff = computed(() => Boolean(admin.permissions.can_manage_staff))

const load = async () => {
  loading.value = true
  try {
    const response = await fetchAdminUsers(filters)
    users.value = response.results || []
  } catch (error) {
    ElMessage.error(error.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const save = async (user) => {
  try {
    const { value } = await ElMessageBox.prompt('请输入调整原因', user.email, {
      confirmButtonText: '提交',
      cancelButtonText: '取消',
      inputType: 'textarea',
      inputValidator: (text) => Boolean(text && text.trim()),
      inputErrorMessage: '原因不能为空',
    })
    await updateAdminUser(user.id, {
      is_active: user.is_active,
      is_staff: user.is_staff,
      role: user.role,
      reason: value.trim(),
    })
    ElMessage.success('用户已更新')
    await load()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(error.message || '更新失败')
    await load()
  }
}

onMounted(load)
</script>
