import request from './request'

// ── 订单 ─────────────────────────────────
export const listOrders = (params: any) => request.get('/wms-outbound/orders', { params })
export const getOrder = (id: number) => request.get(`/wms-outbound/orders/${id}`)
export const createOrder = (data: any) => request.post('/wms-outbound/orders', data)
export const allocateOrder = (id: number) => request.post(`/wms-outbound/orders/${id}/allocate`)
export const cancelOrder = (id: number) => request.post(`/wms-outbound/orders/${id}/cancel`)
export const makePick = (id: number) => request.post(`/wms-outbound/orders/${id}/pick`)
export const recordCheck = (id: number, data: any) =>
  request.post(`/wms-outbound/orders/${id}/check`, data)
export const shipOrder = (id: number, data: any) =>
  request.post(`/wms-outbound/orders/${id}/ship`, data)

// ── 拣货 ─────────────────────────────────
export const listPicks = (params: any) => request.get('/wms-outbound/picks', { params })
export const getPick = (id: number) => request.get(`/wms-outbound/picks/${id}`)
export const confirmPickLine = (lineId: number, locationCode?: string) =>
  request.post(`/wms-outbound/pick-lines/${lineId}/confirm`, {
    location_code: locationCode || null,
  })
