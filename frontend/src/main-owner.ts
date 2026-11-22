import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import '@/styles/apeui-theme.css'

import OwnerApp from './OwnerApp.vue'
import ownerRouter from './router/owner'
import { permissionDirective } from './directives/permission'
import { initTheme } from './composables/useTheme'

import elZhCn from 'element-plus/es/locale/lang/zh-cn'

/**
 * 货主门户的独立启动入口。
 *
 * 与后台共用组件与请求封装，但产物、base 路径、登录页、路由表都是分开的——
 * 货主的 token 进不了后台的界面，反之亦然。
 */
const app = createApp(OwnerApp)
initTheme()

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(ownerRouter)
app.use(ElementPlus, { locale: elZhCn })
app.directive('permission', permissionDirective)

app.mount('#app')
