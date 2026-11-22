<script setup lang="ts">
import { computed } from 'vue'
import { useUserStore } from '@/stores/user'
import { portalContext } from '@/api/wms_portal'
import { onMounted, ref } from 'vue'

const userStore = useUserStore()
const ctx = ref<any>(null)
const perms = computed<string[]>(() =>
  ((userStore as any).permissions || []).filter((p: string) => p.startsWith('wms_'))
)

onMounted(async () => {
  ctx.value = await portalContext()
})
</script>

<template>
  <div class="wrap">
    <h2>账号与权限</h2>
    <p class="lead">当前登录账号的信息，以及它在货主门户里能做什么。</p>

    <div class="kv"><span>账号</span><b>{{ userStore.username || '—' }}</b></div>
    <div class="kv"><span>显示名</span><b>{{ userStore.nickname || '—' }}</b></div>
    <div class="kv"><span>所属货主</span><b>{{ ctx?.owner_name || '—' }}</b></div>
    <div class="kv"><span>门户建单</span><b>{{ ctx?.can_create ? '可用' : '由上游下发' }}</b></div>

    <div class="sub">已授予的门户权限</div>
    <div class="chips">
      <span v-for="p in perms" :key="p" class="chip">{{ p }}</span>
      <span v-if="!perms.length" class="muted">没有单独的门户权限，按菜单可见性控制</span>
    </div>

    <div class="note">
      子账号的新增与停用由仓库在「主数据 → 货主管理」里维护；三个货主角色
      （主账号 / 操作员 / 只读）决定各自能看到哪些菜单。
    </div>
  </div>
</template>

<style scoped>
.wrap { max-width: 640px; }
h2 { margin: 0 0 6px; font-size: 18px; font-weight: 600; color: #1b2740; }
.lead { margin: 0 0 20px; font-size: 13px; color: #66748f; }
.kv { display: flex; justify-content: space-between; padding: 10px 0; font-size: 13px; color: #1b2740; border-bottom: 1px dashed #eef1f6; }
.kv span { color: #66748f; }
.sub { margin: 22px 0 10px; font-size: 13px; font-weight: 600; color: #3a4a68; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { padding: 4px 9px; font-size: 11px; color: #0e8c80; background: #eaf5f3; border-radius: 5px; font-family: ui-monospace, Menlo, monospace; }
.muted { font-size: 12px; color: #98a4bb; }
.note { margin-top: 20px; font-size: 12px; line-height: 1.8; color: #98a4bb; }
</style>
