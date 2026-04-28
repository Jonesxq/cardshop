import { api } from './client'

export const fetchHome = () => api.get('/shop/home').then((res) => res.data)

export const createOrder = (payload) => api.post('/orders', payload).then((res) => res.data)

export const queryOrders = ({ order_no, contact, keyword } = {}) =>
  api
    .get('/orders/query', {
      params: {
        order_no,
        contact,
        keyword,
      },
    })
    .then((res) => res.data.results)

export const fetchOrderPayment = (orderNo, payload = {}) =>
  api.post(`/orders/${encodeURIComponent(orderNo)}/payment`, payload).then((res) => res.data)

export const completeDevPayment = (orderNo, payload = {}) =>
  api.post('/payments/dev/complete', { order_no: orderNo, ...payload }).then((res) => res.data)
