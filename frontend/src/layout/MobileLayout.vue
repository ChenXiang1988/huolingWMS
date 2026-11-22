<script setup lang="ts">
/**
 * 作业端布局。
 *
 * 窄屏容器，桌面浏览器打开时居中显示而不是拉满全宽——作业端按 390–430 宽度设计，
 * 在 1920 屏上拉满会让按钮变得不可点。
 *
 * 浏览器门槛在这里卡：低于 Chrome 110 / Safari 16.4，或缺关键 API，直接给提示页。
 * 放布局而不是路由守卫，是因为门口这道提示本身也得能渲染出来。
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { checkMobileBrowser } from '@/composables/useBrowserGate'

const route = useRoute()
const router = useRouter()

const gate = checkMobileBrowser()

const tabs = [
  { path: '/m/tasks', label: '任务' },
  { path: '/m/scan', label: '扫码' },
]

const active = computed(() => route.path)
</script>

<template>
  <div class="mobile-stage">
    <div class="mobile-shell">
      <template v-if="gate.blocked">
        <div class="gate">
          <div class="gate-title">浏览器版本不受支持</div>
          <p class="gate-reason">{{ gate.reason }}</p>
          <p class="gate-hint">换一台设备或用 APK 作业端，扫码与提交都能继续。</p>
        </div>
      </template>

      <template v-else>
        <header class="mobile-head">
          <span class="title">货灵作业端</span>
          <span class="hint">扫码作业</span>
        </header>

        <main class="mobile-body">
          <router-view />
        </main>

        <nav class="mobile-tabs">
          <button
            v-for="t in tabs"
            :key="t.path"
            class="tab"
            :class="{ active: active.startsWith(t.path) }"
            @click="router.push(t.path)"
          >
            {{ t.label }}
          </button>
        </nav>
      </template>
    </div>
  </div>
</template>

<style scoped>
.mobile-stage {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  background: #eef1f6;
}
.mobile-shell {
  width: 100%;
  max-width: 430px;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #fff;
  box-shadow: 0 0 24px rgba(27, 39, 64, 0.08);
}
.mobile-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #eef1f6;
}
.title {
  font-size: 15px;
  font-weight: 700;
  color: #1b2740;
}
.hint {
  font-size: 11px;
  color: #98a4bb;
}
.mobile-body {
  flex: 1;
  padding: 16px;
  overflow: auto;
}
.mobile-tabs {
  display: flex;
  border-top: 1px solid #eef1f6;
}
.tab {
  flex: 1;
  border: 0;
  background: #fff;
  padding: 12px 0;
  font-size: 13px;
  color: #66748f;
  cursor: pointer;
}
.tab.active {
  color: #10b3a3;
  font-weight: 700;
}
.gate { padding: 48px 20px; }
.gate-title { font-size: 17px; font-weight: 700; color: #b42318; }
.gate-reason { margin: 12px 0 8px; font-size: 13px; line-height: 1.8; color: #1b2740; }
.gate-hint { font-size: 12px; line-height: 1.8; color: #66748f; }
</style>
