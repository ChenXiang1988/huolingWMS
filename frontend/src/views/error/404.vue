<template>
  <div class="error-page">
    <div class="error-content">
      <h1>404</h1>
      <p>页面不存在或无权限访问</p>
      <el-button type="primary" @click="goHome">返回首页</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
// 同一组件被管理与货主门户复用，两端的首页路径不同
const goHome = () => {
  router.push(window.location.pathname.startsWith('/owner') ? '/dashboard' : '/dashboard-monitor')
}
</script>

<style scoped>
.error-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
}
.error-content {
  text-align: center;
}
.error-content h1 {
  font-size: 80px;
  font-weight: 700;
  color: var(--theme-default, #5a67f5);
  margin: 0 0 8px;
}
.error-content p {
  font-size: 16px;
  color: #909399;
  margin: 0 0 24px;
}
</style>
