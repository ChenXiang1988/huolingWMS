<script setup lang="ts">
/**
 * 作业端布局。
 *
 * 窄屏容器，桌面浏览器打开时居中显示而不是拉满全宽——作业端按 390–430 宽度设计，
 * 在 1920 屏上拉满会让按钮变得不可点。
 *
 * P5 才填真实作业流程，P0 只保证布局与路由能跑通。
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const tabs = [
  { path: '/m/tasks', label: '任务' },
  { path: '/m/scan', label: '扫码' },
]

const active = computed(() => route.path)
</script>

<template>
  <div class="mobile-stage">
    <div class="mobile-shell">
      <header class="mobile-head">
        <span class="title">货灵作业端</span>
        <span class="hint">P0 占位</span>
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
</style>
