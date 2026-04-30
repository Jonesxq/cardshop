import { defineStore } from 'pinia'

import { fetchAdminMe } from '../api/adminConsole'

export const useAdminSessionStore = defineStore('adminSession', {
  state: () => ({
    loaded: false,
    loading: false,
    user: null,
    role: '',
    permissions: {},
    accessToken: '',
  }),
  actions: {
    async load({ force = false } = {}) {
      const currentToken = localStorage.getItem('access_token') || ''
      if (this.loaded && !force && this.accessToken === currentToken) return
      this.loading = true
      try {
        const data = await fetchAdminMe()
        this.user = data
        this.role = data.role
        this.permissions = data.permissions || {}
        this.accessToken = currentToken
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
      this.accessToken = ''
    },
  },
})
