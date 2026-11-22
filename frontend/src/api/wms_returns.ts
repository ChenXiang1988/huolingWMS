import request from './request'

export const listDisposals = (params: any) =>
  request.get('/wms-returns/disposals', { params })

/** restock 转回可发 / scrap 报废 / return_owner 退回货主（P3 起开放）。 */
export const handleDisposal = (id: number, data: { method: string; reason?: string }) =>
  request.post(`/wms-returns/disposals/${id}/handle`, data)

// ── 退货单 ─────────────────────────────────
export const listReturns = (params: any) =>
  request.get('/wms-returns/returns', { params })
export const getReturn = (id: number) =>
  request.get(`/wms-returns/returns/${id}`)
export const createReturn = (data: any) =>
  request.post('/wms-returns/returns', data)
export const receiveReturn = (id: number) =>
  request.post(`/wms-returns/returns/${id}/receive`)
