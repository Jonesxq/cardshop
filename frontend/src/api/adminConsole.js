import { api } from './client'

const data = (request) => request.then((res) => res.data)

export const fetchAdminMe = () => data(api.get('/admin-console/me'))
export const fetchAdminDashboard = () => data(api.get('/admin-console/dashboard'))

export const fetchAdminProducts = (params = {}) => data(api.get('/admin-console/products', { params }))
export const fetchAdminProduct = (id) => data(api.get(`/admin-console/products/${id}`))
export const createAdminProduct = (payload) => data(api.post('/admin-console/products', payload))
export const updateAdminProduct = (id, payload) => data(api.patch(`/admin-console/products/${id}`, payload))

export const fetchAdminCategories = (params = {}) => data(api.get('/admin-console/categories', { params }))
export const fetchAdminCategory = (id) => data(api.get(`/admin-console/categories/${id}`))
export const createAdminCategory = (payload) => data(api.post('/admin-console/categories', payload))
export const updateAdminCategory = (id, payload) => data(api.patch(`/admin-console/categories/${id}`, payload))

export const fetchAdminCards = (params = {}) => data(api.get('/admin-console/cards', { params }))
export const previewCardImport = (payload) => data(api.post('/admin-console/cards/import/preview', payload))
export const commitCardImport = (payload) => data(api.post('/admin-console/cards/import/commit', payload))

export const fetchAdminOrders = (params = {}) => data(api.get('/admin-console/orders', { params }))
export const fetchAdminOrder = (id) => data(api.get(`/admin-console/orders/${id}`))
export const markAdminOrderPaid = (id, payload) => data(api.post(`/admin-console/orders/${id}/mark-paid`, payload))
export const cancelAdminOrder = (id, payload) => data(api.post(`/admin-console/orders/${id}/cancel`, payload))
export const redeliverAdminOrder = (id, payload) => data(api.post(`/admin-console/orders/${id}/redeliver`, payload))
export const replaceAdminOrderCard = (id, payload) => data(api.post(`/admin-console/orders/${id}/replace-card`, payload))
export const releaseAdminOrderStock = (id, payload) => data(api.post(`/admin-console/orders/${id}/release-stock`, payload))

export const fetchAdminPayments = (params = {}) => data(api.get('/admin-console/payments', { params }))
export const fetchAdminPayment = (id) => data(api.get(`/admin-console/payments/${id}`))
export const resolveAdminPayment = (id, payload) => data(api.post(`/admin-console/payments/${id}/resolve`, payload))

export const fetchAdminUsers = (params = {}) => data(api.get('/admin-console/users', { params }))
export const fetchAdminUser = (id) => data(api.get(`/admin-console/users/${id}`))
export const updateAdminUser = (id, payload) => data(api.patch(`/admin-console/users/${id}`, payload))

export const fetchAdminAnnouncements = (params = {}) => data(api.get('/admin-console/announcements', { params }))
export const fetchAdminAnnouncement = (id) => data(api.get(`/admin-console/announcements/${id}`))
export const createAdminAnnouncement = (payload) => data(api.post('/admin-console/announcements', payload))
export const updateAdminAnnouncement = (id, payload) => data(api.patch(`/admin-console/announcements/${id}`, payload))

export const fetchAdminSiteConfig = (params = {}) => data(api.get('/admin-console/site-config', { params }))
export const updateAdminSiteConfig = (key, payload) => data(api.patch(`/admin-console/site-config/${key}`, payload))

export const fetchAdminLogs = (params = {}) => data(api.get('/admin-console/logs', { params }))
