import request from './request'

/** 库存按「货主 + 商品 + 状态」聚合，批次明细走 detail。 */
export const listStocks = (params: any) =>
  request.get('/wms-inventory/stocks', { params })

export const listStockDetail = (params: any) =>
  request.get('/wms-inventory/stocks/detail', { params })

export const listTxns = (params: any) => request.get('/wms-inventory/txns', { params })

export const listLots = (params: any) => request.get('/wms-inventory/lots', { params })

/**
 * 手工调整库存。
 *
 * `request_id` 由调用方生成并在重试时复用——服务端拿它当幂等键，
 * 每次点击都新生成就会失去幂等性。
 */
export const createAdjustment = (data: any) =>
  request.post('/wms-inventory/adjustments', data)
