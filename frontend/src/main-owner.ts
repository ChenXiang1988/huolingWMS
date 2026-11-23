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
import { useSettingsStore } from './stores/settings'
import i18n, { getLocale, setLocale } from './locales'

import elZhCn from 'element-plus/es/locale/lang/zh-cn'
import elEn from 'element-plus/es/locale/lang/en'

/**
 * 货主门户的独立启动入口。
 *
 * 与后台共用组件、请求封装、主题与 i18n，但产物、base 路径、登录页、路由表
 * 和守卫都是分开的——货主的 token 进不了后台的界面，反之亦然。
 * 外壳组件（ApeSidebar / ApeHeader）通过 portal 开关切换菜单与后台专属入口，
 * 组件复用不等于身份合并。
 */
const app = createApp(OwnerApp)
initTheme()

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

const pinia = createPinia()
app.use(pinia)
app.use(ownerRouter)
app.use(i18n)

const elLocaleMap: Record<string, any> = { 'zh-CN': elZhCn, 'en-US': elEn }
app.use(ElementPlus, { locale: elLocaleMap[getLocale()] || elZhCn })
setLocale(getLocale())

import { watch } from 'vue'
watch(() => (i18n.global.locale as any).value, (newLocale) => {
  app.provide('elLocale', elLocaleMap[newLocale] || elZhCn)
})

app.directive('permission', permissionDirective)

const settingsStore = useSettingsStore()
settingsStore.fetchPublicSettings().finally(() => {
  app.mount('#app')
})
