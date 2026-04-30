import { defineStore } from 'pinia'

import { fetchAdminMe } from '../api/adminConsole'

export const useAdminSessionStore = defineStore('adminSession', {
  state: () => ({
    loaded: false,
    loading: false,
    user: null,
    role: '',
    permissions: {},
  }),
  actions: {
    async load({ force = false } = {}) {
      if (this.loaded && !force) return
      this.loading = true
      try {
        const data = await fetchAdminMe()
        this.user = data
        this.role = data.role
        this.permissions = data.permissions || {}
        this.loaded = true
      } finally {
        this.loading = false
      }
    },
    reset() {
      this.loaded = false
      this.loading = false
      this.user = null
      this.role = ''
      this.permissions = {}
    },
  },
})
