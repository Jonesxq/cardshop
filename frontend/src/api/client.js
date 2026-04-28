import axios from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 15000,
})

const redirectToLogin = () => {
  localStorage.removeItem('user')
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  const current = `${window.location.pathname}${window.location.search}`
  if (!window.location.pathname.startsWith('/login')) {
    window.location.href = `/login?redirect=${encodeURIComponent(current)}`
  }
}

const FIELD_LABELS = {
  email: '邮箱',
  password: '密码',
  code: '验证码',
  refresh: '登录状态',
  purpose: '用途',
  detail: '提示',
  non_field_errors: '提示',
}

const flattenError = (data) => {
  if (!data) return ''
  if (typeof data === 'string') return data
  if (Array.isArray(data)) return data.map(flattenError).filter(Boolean).join('；')
  if (typeof data === 'object') {
    if (data.detail) return flattenError(data.detail)
    if (data.message) return flattenError(data.message)
    if (data.non_field_errors) return flattenError(data.non_field_errors)
    return Object.entries(data)
      .map(([field, value]) => {
        const label = FIELD_LABELS[field] || field
        const message = flattenError(value)
        return message ? `${label}：${message}` : ''
      })
      .filter(Boolean)
      .join('；')
  }
  return String(data)
}

export const formatApiError = (error) => {
  return flattenError(error?.response?.data) || error?.message || '请求失败，请稍后再试'
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original?._retry) {
      const refresh = localStorage.getItem('refresh_token')
      if (refresh) {
        original._retry = true
        try {
          const response = await axios.post(`${api.defaults.baseURL}/auth/token/refresh`, { refresh })
          localStorage.setItem('access_token', response.data.access)
          original.headers.Authorization = `Bearer ${response.data.access}`
          return api(original)
        } catch {
          redirectToLogin()
        }
      } else {
        redirectToLogin()
      }
    }
    const message = formatApiError(error)
    const apiError = new Error(message)
    apiError.response = error.response
    apiError.status = error.response?.status
    apiError.originalError = error
    return Promise.reject(apiError)
  },
)
