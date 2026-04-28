import { defineStore } from 'pinia'
import { fetchMe, login as loginRequest } from '../api/auth'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: JSON.parse(localStorage.getItem('user') || 'null'),
    accessToken: localStorage.getItem('access_token') || '',
    refreshToken: localStorage.getItem('refresh_token') || '',
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.accessToken),
  },
  actions: {
    setSession(payload) {
      this.user = payload.user
      this.accessToken = payload.tokens.access
      this.refreshToken = payload.tokens.refresh
      localStorage.setItem('user', JSON.stringify(payload.user))
      localStorage.setItem('access_token', payload.tokens.access)
      localStorage.setItem('refresh_token', payload.tokens.refresh)
    },
    async login(payload) {
      const data = await loginRequest(payload)
      this.setSession(data)
    },
    async loadMe() {
      if (!this.accessToken) return
      this.user = await fetchMe()
      localStorage.setItem('user', JSON.stringify(this.user))
    },
    logout() {
      this.user = null
      this.accessToken = ''
      this.refreshToken = ''
      localStorage.removeItem('user')
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
    },
  },
})

