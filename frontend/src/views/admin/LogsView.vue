<template>
  <main class="admin-page" v-loading="loading">
    <div class="admin-page-head">
      <div>
        <h1>操作日志</h1>
        <p>审计后台关键操作和变更记录</p>
      </div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <el-table :data="logs" size="small" class="admin-table" empty-text="暂无日志" @row-click="selected = $event">
      <el-table-column prop="created_at" label="时间" width="180" />
      <el-table-column prop="actor_email" label="操作者" min-width="180" />
      <el-table-column prop="actor_role" label="角色" width="110" />
      <el-table-column prop="action" label="动作" min-width="150" />
      <el-table-column label="目标" min-width="150">
        <template #default="{ row }">{{ row.target_type }} #{{ row.target_id }}</template>
      </el-table-column>
      <el-table-column prop="reason" label="原因" min-width="220" />
    </el-table>

    <el-drawer v-model="detailOpen" title="日志详情" size="560px" @closed="selected = null">
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="IP">{{ selected?.ip_address || '-' }}</el-descriptions-item>
        <el-descriptions-item label="User Agent">{{ selected?.user_agent || '-' }}</el-descriptions-item>
      </el-descriptions>
      <h2 class="admin-json-title">变更前</h2>
      <pre>{{ JSON.stringify(selected?.before || {}, null, 2) }}</pre>
      <h2 class="admin-json-title">变更后</h2>
      <pre>{{ JSON.stringify(selected?.after || {}, null, 2) }}</pre>
    </el-drawer>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

import { fetchAdminLogs } from '../../api/adminConsole'

const loading = ref(false)
const logs = ref([])
const selected = ref(null)
const detailOpen = computed({
  get: () => Boolean(selected.value),
  set: (value) => {
    if (!value) selected.value = null
  },
})

const load = async () => {
  loading.value = true
  try {
    const response = await fetchAdminLogs()
    logs.value = response.results || []
  } catch (error) {
    ElMessage.error(error.message || '加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
