import request from './request'

/** 当前账号是否绑定货主。后台用它挡住货主账号，门户用它挡住员工账号。 */
export const isOwnerPortal = () => request.get('/wms-master-data/me/portal')

/**
 * 货主门户专用登录。
 *
 * 不复用 `/auth/login`：那个接口对任何合法账号都发 token。门户走这条独立接口，
 * 只接受绑定了货主的账号，员工账号在这里直接失败。
 */
export const ownerLogin = (data: { username: string; password: string }) =>
  request.post('/wms-master-data/owner-login', data)

// ── 仓库配置 ──────────────────────────────
export const getWarehouse = () => request.get('/wms-master-data/warehouse')
export const saveWarehouse = (data: any) => request.put('/wms-master-data/warehouse', data)

// ── 库区 ─────────────────────────────────
export const listZones = () => request.get('/wms-master-data/zones')
export const createZone = (data: any) => request.post('/wms-master-data/zones', data)

// ── 库位 ─────────────────────────────────
export const listLocations = (params: any) =>
  request.get('/wms-master-data/locations', { params })
export const createLocation = (data: any) => request.post('/wms-master-data/locations', data)
export const updateLocation = (id: number, data: any) =>
  request.put(`/wms-master-data/locations/${id}`, data)
export const batchCreateLocations = (data: any) =>
  request.post('/wms-master-data/locations/batch', data)

// ── 货主 ─────────────────────────────────
export const listOwners = (params: any) =>
  request.get('/wms-master-data/owners', { params })
export const createOwner = (data: any) => request.post('/wms-master-data/owners', data)
export const updateOwner = (id: number, data: any) =>
  request.put(`/wms-master-data/owners/${id}`, data)
export const toggleOwner = (id: number, enabled: boolean) =>
  request.post(`/wms-master-data/owners/${id}/toggle`, null, { params: { enabled } })

// ── 商品 ─────────────────────────────────
export const listSkus = (params: any) => request.get('/wms-master-data/skus', { params })
export const createSku = (data: any) => request.post('/wms-master-data/skus', data)
export const updateSku = (id: number, data: any) =>
  request.put(`/wms-master-data/skus/${id}`, data)
export const updateSkuStorage = (id: number, data: any) =>
  request.put(`/wms-master-data/skus/${id}/storage`, data)

// ── 条码 ─────────────────────────────────
export const listBarcodes = (skuId: number) =>
  request.get(`/wms-master-data/skus/${skuId}/barcodes`)
export const addBarcode = (skuId: number, data: any) =>
  request.post(`/wms-master-data/skus/${skuId}/barcodes`, data)
export const deleteBarcode = (barcodeId: number) =>
  request.delete(`/wms-master-data/barcodes/${barcodeId}`)

// ── 合作方 ───────────────────────────────
export const listPartners = (params: any) =>
  request.get('/wms-master-data/partners', { params })
export const createPartner = (data: any) => request.post('/wms-master-data/partners', data)

// ── API 凭证 ─────────────────────────────
export const listApiKeys = (params: any) =>
  request.get('/wms-master-data/apikeys', { params })
export const createApiKey = (data: any) => request.post('/wms-master-data/apikeys', data)
export const rotateApiKey = (id: number) =>
  request.post(`/wms-master-data/apikeys/${id}/rotate`)
