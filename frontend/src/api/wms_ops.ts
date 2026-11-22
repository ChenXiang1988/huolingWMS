import request from './request'

// ── 库内作业 ───────────────────────────────
export const listTransfers = (params: any) =>
  request.get('/wms-internal-ops/transfers', { params })
export const createTransfer = (data: any) =>
  request.post('/wms-internal-ops/transfers', data)
export const executeTransfer = (id: number) =>
  request.post(`/wms-internal-ops/transfers/${id}/execute`)

export const listCounts = (params: any) =>
  request.get('/wms-internal-ops/counts', { params })
export const getCount = (id: number) =>
  request.get(`/wms-internal-ops/counts/${id}`)
export const createCount = (data: any) =>
  request.post('/wms-internal-ops/counts', data)
export const saveCountLines = (id: number, data: any) =>
  request.put(`/wms-internal-ops/counts/${id}/lines`, data)
export const confirmCount = (id: number) =>
  request.post(`/wms-internal-ops/counts/${id}/confirm`)

export const listSamples = (params: any) =>
  request.get('/wms-internal-ops/samples', { params })
export const backfillSamples = () =>
  request.post('/wms-internal-ops/samples/backfill')
export const disposeSample = (id: number, data: any) =>
  request.post(`/wms-internal-ops/samples/${id}/dispose`, data)

// ── 任务 ───────────────────────────────────
export const listTasks = (params: any) => request.get('/wms-tasking/tasks', { params })
export const generateTasks = () => request.post('/wms-tasking/tasks/generate')
export const claimTask = (id: number) => request.post(`/wms-tasking/tasks/${id}/claim`)
export const submitTask = (id: number, data: any) =>
  request.post(`/wms-tasking/tasks/${id}/submit`, data)
export const recycleTasks = () => request.post('/wms-tasking/tasks/recycle')
