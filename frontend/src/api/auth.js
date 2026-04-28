import { api } from './client'

export const sendEmailCode = (payload) => api.post('/auth/email-code', payload).then((res) => res.data)
export const register = (payload) => api.post('/auth/register', payload).then((res) => res.data)
export const login = (payload) => api.post('/auth/login', payload).then((res) => res.data)
export const resetPassword = (payload) => api.post('/auth/reset-password', payload).then((res) => res.data)
export const fetchMe = () => api.get('/auth/me').then((res) => res.data)
export const fetchMyOrders = () => api.get('/auth/orders').then((res) => res.data)

