import request from './request'

/** 当前账号绑定的货主与建单开关。owner_id 由服务端注入，前端只用来展示。 */
export const portalContext = () => request.get('/wms-master-data/portal/context')

/** 本货主可建单的商品（最小字段，不含别的货主档案）。 */
export const portalSkus = () => request.get('/wms-master-data/portal/skus')

/** 货主自助建入库预报。请求体里没有 owner_id。 */
export const portalCreateAsn = (data: any) =>
  request.post('/wms-inbound/portal/asns', data)

/** 货主自助建出库订单。请求体里没有 owner_id。 */
export const portalCreateOrder = (data: any) =>
  request.post('/wms-outbound/portal/orders', data)

/** 本货主的出库订单，分页。owner_id 由服务端按会话注入，前端传不了。 */
export const portalOrders = (params: any) =>
  request.get('/wms-outbound/portal/orders', { params })

/** 本货主某一单的明细，别家货主的单返回 404。 */
export const portalOrderDetail = (id: number) =>
  request.get(`/wms-outbound/portal/orders/${id}`)
