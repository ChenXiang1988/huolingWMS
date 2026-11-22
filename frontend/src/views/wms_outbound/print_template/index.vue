<script setup lang="ts">
/**
 * 打印模板入口（P4 待接入）。
 *
 * 菜单已经注册到出库域，这里先给一个明确的落地页而不是空白屏。
 * hiprint 客户端与模板表接入后，这个页面会换成设计器 + 模板列表。
 */
</script>

<template>
  <div class="wrap">
    <el-card shadow="never" class="card">
      <template #header>
        <div class="head">
          <span class="title">打印模板</span>
          <span class="sub">随波次与拣货单一起启用</span>
        </div>
      </template>

      <div class="body">
        <div class="lead">拣货单、装箱单、面单与各类标签的版式会在这里管理。</div>
        <p>接入前需要两件东西：</p>
        <ol>
          <li>后台存模板 JSON 的表与管理接口，改版式不需要重新发前端。</li>
          <li>工位本机安装 <code>electron-hiprint</code> 客户端，前端经 socket.io 把渲染结果下发，由 Windows 打印驱动出纸。</li>
        </ol>
        <el-alert type="info" :closable="false" show-icon
                  title="客户端未接入时不会静默失败，页面会给明确的离线提示" />
        <p class="todo">对应任务：P4 · 5.1–5.6（模板表、前端依赖、六类模板、离线提示、打印任务、真机扫码验收）。</p>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.wrap { display: flex; justify-content: center; padding-top: 8px; }
.card { width: 640px; border-radius: 10px; }
.head { display: flex; flex-direction: column; gap: 2px; }
.title { font-size: 15px; font-weight: 600; color: #1b2740; }
.sub { font-size: 12px; color: #98a4bb; }
.body { font-size: 13px; color: #3a4a68; line-height: 1.8; }
.lead { font-size: 14px; font-weight: 600; color: #1b2740; margin-bottom: 10px; }
.body ol { padding-left: 20px; margin: 8px 0 16px; }
.body li { padding: 3px 0; }
code { padding: 1px 5px; background: #f3f6fb; border-radius: 4px; font-size: 12px; }
.todo { margin: 16px 0 0; font-size: 12px; color: #98a4bb; }
</style>
