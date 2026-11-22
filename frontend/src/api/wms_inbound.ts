import request from './request'

// ── 入库预报 ──────────────────────────────
export const listAsns = (params: any) => request.get('/wms-inbound/asns', { params })
export const getAsn = (id: number) => request.get(`/wms-inbound/asns/${id}`)
export const createAsn = (data: any) => request.post('/wms-inbound/asns', data)
export const confirmAsn = (id: number) => request.post(`/wms-inbound/asns/${id}/confirm`)
export const cancelAsn = (id: number) => request.post(`/wms-inbound/asns/${id}/cancel`)
export const closeAsn = (id: number) => request.post(`/wms-inbound/asns/${id}/close`)

// ── 服务订单 ──────────────────────────────
export const listServiceOrders = (params: any) =>
  request.get('/wms-inbound/service-orders', { params })
export const createServiceOrder = (data: any) =>
  request.post('/wms-inbound/service-orders', data)

// ── 收货 ─────────────────────────────────
export const listReceipts = (params: any) =>
  request.get('/wms-inbound/receipts', { params })
export const getReceipt = (id: number) => request.get(`/wms-inbound/receipts/${id}`)
export const openReceipt = (asnId: number) =>
  request.post(`/wms-inbound/asns/${asnId}/receipts`)
export const saveReceiptLines = (id: number, data: any) =>
  request.put(`/wms-inbound/receipts/${id}/lines`, data)
export const confirmReceipt = (id: number) =>
  request.post(`/wms-inbound/receipts/${id}/confirm`)
export const scanReceiptBarcode = (id: number, code: string) =>
  request.get(`/wms-inbound/receipts/${id}/scan`, { params: { code } })

// ── 上架 ─────────────────────────────────
export const listPutaways = (params: any) =>
  request.get('/wms-inbound/putaways', { params })
export const getPutaway = (id: number) => request.get(`/wms-inbound/putaways/${id}`)
export const confirmPutawayLine = (lineId: number, toLocationId?: number) =>
  request.post(`/wms-inbound/putaway-lines/${lineId}/confirm`, {
    to_location_id: toLocationId ?? null,
  })
