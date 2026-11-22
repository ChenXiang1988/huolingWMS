<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { claimTask, generateTasks, listTasks, submitTask } from '@/api/wms_ops'

const TYPES: Record<string, string> = {
  transfer: '移库', count: '盘点', putaway: '上架', pick: '拣货', check: '复核',
}
const rows = ref<any[]>([])
const loading = ref(false)
const busy = ref<number | null>(null)
const tab = ref<'pending' | 'claimed'>('pending')

async function load() {
  loading.value = true
  try {
    const res: any = await listTasks({ status: tab.value, page: 1, page_size: 50 })
    rows.value = res?.items || []
  } catch (e) {
    console.error(e)
    rows.value = []
  } finally {
    loading.value = false
  }
}

async function generate() {
  await generateTasks()
  await load()
}

async function act(row: any) {
  busy.value = row.id
  try {
    if (row.status === 'pending') await claimTask(row.id)
    else await submitTask(row.id, {})
    await load()
  } catch (e) {
    console.error(e)
  } finally {
    busy.value = null
  }
}

function switchTab(v: 'pending' | 'claimed') {
  tab.value = v
  load()
}

onMounted(load)
</script>

<template>
  <div class="wrap">
    <div class="head">
      <div>
        <div class="title">我的任务</div>
        <div class="sub">作业端 · 领取后扫码执行</div>
      </div>
      <button class="gen" @click="generate">刷新待办</button>
    </div>

    <div class="tabs">
      <button :class="{ on: tab === 'pending' }" @click="switchTab('pending')">待领取</button>
      <button :class="{ on: tab === 'claimed' }" @click="switchTab('claimed')">进行中</button>
    </div>

    <div v-loading="loading" class="list">
      <div v-for="r in rows" :key="r.id" class="card">
        <div class="card-top">
          <span class="type">{{ TYPES[r.task_type] || r.task_type }}</span>
          <span class="code">{{ r.code }}</span>
        </div>
        <div class="card-title">{{ r.title }}</div>
        <div class="card-sub">
          来源 {{ r.ref_type }} #{{ r.ref_id }}
          <template v-if="r.target_location_id"> · 库位 {{ r.target_location_id }}</template>
        </div>
        <button class="act" :disabled="busy === r.id" @click="act(r)">
          {{ busy === r.id ? '处理中…' : r.status === 'pending' ? '领取任务' : '提交完成' }}
        </button>
      </div>
      <div v-if="!loading && !rows.length" class="empty">
        {{ tab === 'pending' ? '当前没有待领任务，点上方「刷新待办」拉取' : '当前没有进行中的任务' }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.wrap { max-width: 520px; margin: 0 auto; padding: 12px; }
.head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.title { font-size: 18px; font-weight: 600; color: #1b2740; }
.sub { margin-top: 2px; font-size: 12px; color: #98a4bb; }
.gen { padding: 8px 12px; font-size: 12px; color: #0e8c80; background: #eaf5f3; border: 1px solid #b9e5df; border-radius: 7px; cursor: pointer; }
.gen:hover { background: #d8f0ec; }
.tabs { display: flex; gap: 8px; margin-bottom: 12px; }
.tabs button { flex: 1; padding: 9px; font-size: 13px; color: #66748f; background: #fff; border: 1px solid #e8ecf3; border-radius: 7px; cursor: pointer; }
.tabs button.on { color: #fff; background: #10b3a3; border-color: #10b3a3; font-weight: 600; }
.list { display: flex; flex-direction: column; gap: 10px; }
.card { padding: 14px; background: #fff; border: 1px solid #e8ecf3; border-radius: 10px; }
.card-top { display: flex; align-items: center; justify-content: space-between; }
.type { padding: 2px 8px; font-size: 11px; color: #0e8c80; background: #eaf5f3; border-radius: 4px; }
.code { font-size: 11px; color: #98a4bb; font-family: ui-monospace, Menlo, monospace; }
.card-title { margin-top: 8px; font-size: 15px; font-weight: 600; color: #1b2740; }
.card-sub { margin-top: 4px; font-size: 12px; color: #66748f; }
.act { width: 100%; margin-top: 12px; padding: 10px; font-size: 14px; color: #fff; background: #10b3a3; border: none; border-radius: 7px; cursor: pointer; }
.act:hover { background: #0e8c80; }
.act:disabled { background: #98a4bb; cursor: not-allowed; }
.empty { padding: 32px 12px; text-align: center; font-size: 13px; color: #98a4bb; }
</style>
