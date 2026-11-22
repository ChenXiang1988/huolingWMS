import request from './request'

// ── 波次规则 ───────────────────────────────
export const listWaveRules = () => request.get('/wms-outbound/wave-rules')
export const createWaveRule = (data: any) => request.post('/wms-outbound/wave-rules', data)
export const updateWaveRule = (id: number, data: any) =>
  request.put(`/wms-outbound/wave-rules/${id}`, data)

// ── 波次 ──────────────────────────────────
export const listWaves = (params: any) => request.get('/wms-outbound/waves', { params })
export const getWave = (id: number) => request.get(`/wms-outbound/waves/${id}`)
export const createWave = (data: any) => request.post('/wms-outbound/waves', data)
export const cancelWave = (id: number, reason?: string) =>
  request.post(`/wms-outbound/waves/${id}/cancel`, { reason })

// ── 播种墙 ────────────────────────────────
export const initCells = (waveId: number) =>
  request.post(`/wms-outbound/waves/${waveId}/cells`)
export const listCells = (waveId: number) =>
  request.get(`/wms-outbound/waves/${waveId}/cells`)
export const scanSeed = (waveId: number, data: any) =>
  request.post(`/wms-outbound/waves/${waveId}/seed`, data)

// ── 补货 ──────────────────────────────────
export const listReplenishments = (params: any) =>
  request.get('/wms-internal-ops/replenishments', { params })
export const suggestReplenish = (ownerId?: number) =>
  request.post('/wms-internal-ops/replenishments/suggest', null,
    { params: ownerId ? { owner_id: ownerId } : {} })
export const executeReplenish = (id: number) =>
  request.post(`/wms-internal-ops/replenishments/${id}/execute`)
