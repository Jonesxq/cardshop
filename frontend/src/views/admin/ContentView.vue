<template>
  <main class="admin-page" v-loading="loading">
    <div class="admin-page-head">
      <div>
        <h1>内容配置</h1>
        <p>维护公告和站点配置项</p>
      </div>
      <div class="admin-head-actions">
        <el-button v-if="canManageAnnouncements" type="primary" :icon="Plus" @click="openAnnouncement()">新建公告</el-button>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </div>
    </div>

    <section class="admin-grid two">
      <div v-if="canManageAnnouncements" class="admin-panel">
        <h2>公告</h2>
        <el-table :data="announcements" size="small" empty-text="暂无公告">
          <el-table-column prop="title" label="标题" min-width="150" />
          <el-table-column label="启用" width="78">
            <template #default="{ row }">
              <el-switch v-model="row.is_active" @change="saveAnnouncement(row)" />
            </template>
          </el-table-column>
          <el-table-column prop="sort_order" label="排序" width="78" />
          <el-table-column label="编辑" width="76">
            <template #default="{ row }">
              <el-button size="small" :icon="Edit" circle @click="openAnnouncement(row)" />
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="canManageSettings" class="admin-panel">
        <h2>站点配置</h2>
        <el-table :data="configs" size="small" empty-text="暂无配置">
          <el-table-column prop="key" label="键" width="140" />
          <el-table-column prop="label" label="标签" width="130" />
          <el-table-column prop="value" label="值" min-width="170" />
          <el-table-column label="编辑" width="76">
            <template #default="{ row }">
              <el-button size="small" :icon="Edit" circle @click="openConfig(row)" />
            </template>
          </el-table-column>
        </el-table>
      </div>
    </section>

    <el-dialog v-model="announcementDialog" :title="announcementForm.id ? '编辑公告' : '新建公告'" width="560px">
      <el-form label-position="top">
        <el-form-item label="标题"><el-input v-model="announcementForm.title" /></el-form-item>
        <el-form-item label="内容"><el-input v-model="announcementForm.content" type="textarea" :rows="5" /></el-form-item>
        <div class="admin-form-row">
          <el-form-item label="启用"><el-switch v-model="announcementForm.is_active" /></el-form-item>
          <el-form-item label="排序"><el-input-number v-model="announcementForm.sort_order" :min="0" /></el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="announcementDialog = false">取消</el-button>
        <el-button type="primary" @click="saveAnnouncement(announcementForm)">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="configDialog" title="编辑配置" width="480px">
      <el-form label-position="top">
        <el-form-item label="键"><el-input v-model="configForm.key" disabled /></el-form-item>
        <el-form-item label="标签"><el-input v-model="configForm.label" /></el-form-item>
        <el-form-item label="值"><el-input v-model="configForm.value" type="textarea" :rows="4" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="configDialog = false">取消</el-button>
        <el-button type="primary" @click="saveConfig">保存</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Edit, Plus, Refresh } from '@element-plus/icons-vue'

import {
  createAdminAnnouncement,
  fetchAdminAnnouncements,
  fetchAdminSiteConfig,
  updateAdminAnnouncement,
  updateAdminSiteConfig,
} from '../../api/adminConsole'
import { useAdminSessionStore } from '../../stores/adminSession'

const admin = useAdminSessionStore()
const loading = ref(false)
const announcements = ref([])
const configs = ref([])
const announcementDialog = ref(false)
const configDialog = ref(false)
const announcementForm = reactive({ id: null, title: '', content: '', is_active: true, sort_order: 0 })
const configForm = reactive({ key: '', label: '', value: '' })
const canManageAnnouncements = computed(() => Boolean(admin.permissions.can_manage_products))
const canManageSettings = computed(() => Boolean(admin.permissions.can_manage_settings))

const load = async () => {
  loading.value = true
  try {
    const [announcementResponse, configResponse] = await Promise.all([
      canManageAnnouncements.value ? fetchAdminAnnouncements({ page_size: 100 }) : Promise.resolve({ results: [] }),
      canManageSettings.value ? fetchAdminSiteConfig({ page_size: 100 }) : Promise.resolve({ results: [] }),
    ])
    announcements.value = announcementResponse.results || []
    configs.value = configResponse.results || []
  } catch (error) {
    ElMessage.error(error.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const openAnnouncement = (row) => {
  Object.assign(announcementForm, row || { id: null, title: '', content: '', is_active: true, sort_order: 0 })
  announcementDialog.value = true
}

const saveAnnouncement = async (row) => {
  const payload = {
    title: row.title,
    content: row.content,
    is_active: row.is_active,
    sort_order: row.sort_order,
  }
  try {
    if (row.id) await updateAdminAnnouncement(row.id, payload)
    else await createAdminAnnouncement(payload)
    announcementDialog.value = false
    ElMessage.success('公告已保存')
    await load()
  } catch (error) {
    ElMessage.error(error.message || '保存失败')
    await load()
  }
}

const openConfig = (row) => {
  Object.assign(configForm, row)
  configDialog.value = true
}

const saveConfig = async () => {
  try {
    await updateAdminSiteConfig(configForm.key, { value: configForm.value, label: configForm.label })
    configDialog.value = false
    ElMessage.success('配置已保存')
    await load()
  } catch (error) {
    ElMessage.error(error.message || '保存失败')
  }
}

onMounted(load)
</script>
