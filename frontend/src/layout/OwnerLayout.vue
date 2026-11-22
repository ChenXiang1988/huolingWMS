<script setup lang="ts">
/**
 * 货主门户布局。
 *
 * 与后台布局并列，只渲染 `/owner` 这一支菜单——员工不会进到这个布局，
 * 货主也进不到后台布局，隔离靠路由而不是靠隐藏按钮。
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

/** 门户菜单：从用户菜单树里取 path 为 /owner 的那个目录。 */
const portalMenu = computed(() =>
  (userStore.menus as any[]).find((m) => m.path === '/owner')
)

const children = computed<any[]>(() => portalMenu.value?.children || [])

const activePath = computed(() => route.path)

function go(child: any) {
  const p = child.path?.startsWith('/') ? child.path : `/${child.path}`
  router.push(p)
}

function logout() {
  userStore.reset()
  router.push('/login')
}
</script>

<template>
  <div class="owner-shell">
    <aside class="owner-side">
      <div class="owner-brand">
        <span class="dot" />
        <div>
          <div class="brand-name">货主门户</div>
          <div class="brand-sub">{{ userStore.nickname || userStore.username || '' }}</div>
        </div>
      </div>

      <nav class="owner-nav">
        <button
          v-for="item in children"
          :key="item.id"
          class="nav-item"
          :class="{ active: activePath === '/' + item.path }"
          @click="go(item)"
        >
          {{ item.name }}
        </button>
      </nav>

      <button class="logout" @click="logout">退出登录</button>
    </aside>

    <main class="owner-main">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.owner-shell {
  display: flex;
  min-height: 100vh;
  background: #f5f7fb;
}
.owner-side {
  width: 220px;
  flex: none;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-right: 1px solid #e8ecf3;
  padding: 18px 12px;
}
.owner-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 8px 18px;
  border-bottom: 1px solid #eef1f6;
}
.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #10b3a3;
  box-shadow: 0 0 0 4px rgba(16, 179, 163, 0.15);
}
.brand-name {
  font-size: 14px;
  font-weight: 700;
  color: #1b2740;
}
.brand-sub {
  font-size: 12px;
  color: #66748f;
  margin-top: 2px;
}
.owner-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-top: 14px;
}
.nav-item {
  text-align: left;
  border: 0;
  background: transparent;
  padding: 9px 12px;
  border-radius: 8px;
  font-size: 13px;
  color: #3a4a68;
  cursor: pointer;
}
.nav-item:hover {
  background: #f3f6fb;
}
.nav-item.active {
  background: #eaf5f3;
  color: #0e8c80;
  font-weight: 600;
}
.logout {
  border: 1px solid #e8ecf3;
  background: #fff;
  border-radius: 8px;
  padding: 8px;
  font-size: 12px;
  color: #66748f;
  cursor: pointer;
}
.owner-main {
  flex: 1;
  padding: 24px 28px;
  overflow: auto;
}
</style>
