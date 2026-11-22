<script setup lang="ts">
// 货主门户的根组件：只有路由出口，没有后台的侧边栏与顶栏
</script>

<template>
  <router-view />
</template>

<style>
html,
body,
#app {
  height: 100%;
  margin: 0;
}
body {
  font-family: 'PingFang SC', -apple-system, BlinkMacSystemFont, 'Microsoft YaHei', sans-serif;
  background: #f5f7fb;
  color: #1b2740;
}
</style>
