import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { isOwnerPortal } from '@/api/wms_master_data'

/**
 * 货主门户路由。
 *
 * 与后台完全独立：不同的 base、不同的登录页、不同的守卫。
 * 员工账号进不来——守卫会先问一次 `/me/portal`，不是货主就清 token 回登录页，
 * 而不是像以前那样"重定向到后台"。
 */
const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'OwnerLogin',
    component: () => import('@/views/login/owner.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/',
    name: 'OwnerLayout',
    component: () => import('@/layout/OwnerLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'OwnerDashboard',
        component: () => import('@/views/wms_master_data/portal/dashboard/index.vue'),
        meta: { title: '概览', permission: 'wms_master_data:portal:view' },
      },
      {
        path: 'account',
        name: 'OwnerAccount',
        component: () => import('@/views/wms_master_data/portal/account/index.vue'),
        meta: { title: '子账号', permission: 'wms_master_data:subaccount:list' },
      },
      {
        path: 'asn',
        name: 'OwnerAsn',
        component: () => import('@/views/wms_master_data/portal/asn/index.vue'),
        meta: { title: '入库预报' },
      },
      {
        path: 'order',
        name: 'OwnerOrder',
        component: () => import('@/views/wms_master_data/portal/order/index.vue'),
        meta: { title: '出库订单' },
      },
      {
        path: 'sku',
        name: 'OwnerSku',
        component: () => import('@/views/wms_master_data/portal/sku/index.vue'),
        meta: { title: '商品档案', permission: 'wms_master_data:portal:view' },
      },
      {
        path: 'stock',
        name: 'OwnerStock',
        component: () => import('@/views/wms_master_data/portal/stock/index.vue'),
        meta: { title: '库存查询', permission: 'wms_inventory:portal:stock:view' },
      },
      {
        path: 'bill',
        name: 'OwnerBill',
        component: () => import('@/views/wms_master_data/portal/bill/index.vue'),
        meta: { title: '账单查询', permission: 'wms_billing:portal:bill:view' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'OwnerCatchAll',
    component: () => import('@/views/error/404.vue'),
    meta: { title: '404' },
  },
]

const ownerRouter = createRouter({
  history: createWebHistory('/owner/'),
  routes,
})

let identity: boolean | null = null

async function assertOwner(): Promise<boolean> {
  if (identity === null) {
    try {
      const res: any = await isOwnerPortal()
      identity = !!res?.is_owner
    } catch {
      identity = false
    }
  }
  return identity
}

ownerRouter.beforeEach(async (to, _from, next) => {
  const token = localStorage.getItem('apeadmin_token')

  if (to.path === '/login') {
    if (!token) {
      next()
      return
    }
    if (await assertOwner()) {
      next('/dashboard')
      return
    }
    // 拿着员工 token 打开门户登录页：清掉，让他去后台登录
    localStorage.removeItem('apeadmin_token')
    identity = null
    next()
    return
  }

  if (!token) {
    next('/login')
    return
  }

  const userStore = useUserStore()
  if (!userStore.menus.length) {
    try {
      await userStore.fetchUserInfo()
    } catch (e) {
      console.error('门户加载用户信息失败', e)
      localStorage.removeItem('apeadmin_token')
      next('/login')
      return
    }
  }

  // 员工账号拿着 token 也进不了门户
  if (!(await assertOwner())) {
    userStore.reset()
    identity = null
    next('/login')
    return
  }

  const permission = to.meta?.permission as string | undefined
  if (permission && !userStore.hasPermission(permission)) {
    next('/404')
    return
  }
  next()
})

export function resetOwnerRouter() {
  identity = null
}

export default ownerRouter
