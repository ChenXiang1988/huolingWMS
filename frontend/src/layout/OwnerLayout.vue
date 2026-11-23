<script setup lang="ts">
/**
 * 货主门户布局：与后台同构的 ApeSidebar + ApeHeader 外壳，但只渲染 `/owner`
 * 这一支菜单，且不出现版本更新、系统设置等后台专属入口。
 *
 * 隔离靠路由与登录入口而不是隐藏按钮——员工进不到这个布局，货主进不到后台布局。
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import ApeSidebar from '@/components/ApeSidebar.vue'
import ApeHeader from '@/components/ApeHeader.vue'
import { useUserStore } from '@/stores/user'
import { useTheme } from '@/composables/useTheme'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const { isDark, toggleDark } = useTheme()

const collapsed = ref(false)
const isMobile = ref(false)
const mobileSidebarOpen = ref(false)

function checkMobile() {
  const w = window.innerWidth
  isMobile.value = w <= 1199
  if (isMobile.value) {
    mobileSidebarOpen.value = false
    collapsed.value = false
  } else if (w <= 1600) {
    collapsed.value = true
  } else {
    collapsed.value = false
  }
}

watch(() => route.path, () => {
  if (isMobile.value) mobileSidebarOpen.value = false
})
onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})
onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})

function toggleCollapse() { collapsed.value = !collapsed.value }
function toggleMobileSidebar() { mobileSidebarOpen.value = !mobileSidebarOpen.value }
function closeMobileSidebar() { mobileSidebarOpen.value = false }
function toggleTheme() { toggleDark() }

function logout() {
  userStore.reset()
  router.push('/login')
}
</script>

<template>
  <div class="layout">
    <Transition name="overlay-fade">
      <div v-if="isMobile && mobileSidebarOpen" class="sidebar-overlay" @click="closeMobileSidebar"></div>
    </Transition>

    <ApeSidebar
      portal
      :collapsed="collapsed"
      :isMobile="isMobile"
      :mobileOpen="mobileSidebarOpen"
      @toggle="toggleCollapse"
      @close-mobile="closeMobileSidebar"
    />

    <div class="layout-main" :class="{ 'is-collapsed': collapsed && !isMobile, 'is-mobile': isMobile }">
      <ApeHeader
        portal
        :isDark="isDark"
        :collapsed="collapsed"
        :isMobile="isMobile"
        @toggle-theme="toggleTheme"
        @logout="logout"
        @toggle-mobile-sidebar="toggleMobileSidebar"
      />
      <main class="main">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout {
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: row;
  overflow: hidden;
}
.layout-main {
  height: 100vh;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding-left: 258px;
  transition: padding-left 0.3s ease;
}
.layout-main.is-collapsed {
  padding-left: 86px;
}
.layout-main.is-mobile {
  padding-left: 0;
}
.main {
  flex: 1;
  background-color: var(--theme-body-bg, #eff3f9);
  padding: 20px;
  overflow-y: auto;
  overflow-x: hidden;
  margin-top: 64px;
  min-height: 0;
}
.sidebar-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.4);
  z-index: 8;
  cursor: pointer;
}
.overlay-fade-enter-active,
.overlay-fade-leave-active {
  transition: opacity 0.25s ease;
}
.overlay-fade-enter-from,
.overlay-fade-leave-to {
  opacity: 0;
}
@media (max-width: 991px) {
  .main { padding: 15px; }
}
@media (max-width: 575px) {
  .main { padding: 12px; margin-top: 56px; }
}
</style>
