<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { initCells, listCells, listWaves, scanSeed } from '@/api/wms_wave'

const rows = ref<any[]>([])
const waves = ref<any[]>([])
const waveId = ref<number | null>(null)
const cells = ref<any[]>([])
const scan = ref('')
const last = ref<any>(null)
const busy = ref(false)
const scanInput = ref<any>(null)

const doneCount = computed(() => cells.value.filter((c) => c.status === 'full').length)

async function loadWaves() {
  const data: any = await listWaves({ page: 1, page_size: 100 })
  rows.value = data?.items || []
  waves.value = rows.value.filter((w) => w.status === 'ready' || w.status === 'picking')
}

async function loadCells() {
  if (!waveId.value) return
  cells.value = (await listCells(waveId.value)) as any
}

async function choose(id: number) {
  waveId.value = id
  await initCells(id)
  await loadCells()
  await nextTick()
  scanInput.value?.focus()
}

async function doScan() {
  if (!waveId.value || !scan.value) return
  busy.value = true
  try {
    last.value = await scanSeed(waveId.value, { sku_id: Number(scan.value) })
    scan.value = ''
    await loadCells()
  } catch (e) {
    console.error(e)
    scan.value = ''
  } finally {
    busy.value = false
    await nextTick()
    scanInput.value?.focus()
  }
}

onMounted(loadWaves)
</script>

<template>
  <div class="page">
    <div class="top">
      <div class="pick-wave">
        <label>选择波次</label>
        <div class="chips">
          <button v-for="w in waves" :key="w.id" class="chip"
                  :class="{ active: waveId === w.id }" @click="choose(w.id)">
            {{ w.code }} · {{ w.total }} 单
          </button>
          <span v-if="!waves.length" class="muted">还没有待分播的波次</span>
        </div>
      </div>
      <div class="progress">
        <b>{{ doneCount }} / {{ cells.length }}</b>
        <span>格口已完成</span>
      </div>
    </div>

    <div class="scan-box">
      <label for="seed-scan">扫商品 ID 或条码</label>
      <div class="scan-row">
        <input id="seed-scan" ref="scanInput" v-model="scan" :disabled="!waveId"
               placeholder="扫码后自动显示应放格口" @keyup.enter="doScan" />
        <el-button type="primary" :disabled="!waveId" :loading="busy" @click="doScan">确认</el-button>
      </div>
      <div v-if="last" class="result" :class="{ ok: last.status === 'full' }">
        放入格口 <b>{{ last.cell_no }}</b>
        <span>（{{ last.placed_qty }} / {{ last.required_qty }}）</span>
      </div>
    </div>

    <div class="grid">
      <div v-for="c in cells" :key="c.id" class="cell" :class="c.status">
        <div class="cell-no">{{ c.cell_no }}</div>
        <div class="cell-order">订单 #{{ c.order_id }}</div>
        <div class="cell-qty">{{ c.placed_qty }} / {{ c.required_qty }}</div>
      </div>
      <div v-if="waveId && !cells.length" class="empty">这个波次还没有格口，请先选波次生成。</div>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 4px; }
.top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; }
.pick-wave label { display: block; font-size: 12px; color: #66748f; margin-bottom: 8px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { padding: 6px 12px; font-size: 12px; color: #3a4a68; background: #fff; border: 1px solid #e8ecf3; border-radius: 6px; cursor: pointer; }
.chip:hover { border-color: #b9e5df; }
.chip.active { background: #eaf5f3; border-color: #10b3a3; color: #0e8c80; font-weight: 600; }
.progress { text-align: right; }
.progress b { display: block; font-size: 22px; color: #1b2740; font-variant-numeric: tabular-nums; }
.progress span { font-size: 12px; color: #66748f; }
.muted { font-size: 12px; color: #98a4bb; }
.scan-box { padding: 12px 14px; background: #f7fbfa; border: 1px solid #cdeae5; border-radius: 8px; margin-bottom: 14px; }
.scan-box label { display: block; font-size: 12px; color: #0e8c80; font-weight: 600; margin-bottom: 8px; }
.scan-row { display: flex; gap: 8px; }
.scan-row input { flex: 1; padding: 9px 12px; font-size: 14px; border: 1px solid #b9e5df; border-radius: 7px; outline: none; }
.scan-row input:focus { border-color: #10b3a3; box-shadow: 0 0 0 3px rgba(16,179,163,0.14); }
.result { margin-top: 10px; padding: 8px 10px; background: #fff; border-radius: 6px; font-size: 13px; color: #d97706; }
.result b { font-size: 16px; }
.result.ok { color: #16a34a; }
.result span { font-size: 12px; color: #66748f; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 8px; }
.cell { padding: 10px; background: #fff; border: 1px solid #e8ecf3; border-radius: 8px; }
.cell.filling { border-color: #f5c976; background: #fffdf5; }
.cell.full { border-color: #a7dfc4; background: #f5fcf8; }
.cell-no { font-size: 16px; font-weight: 700; color: #1b2740; font-family: ui-monospace, Menlo, monospace; }
.cell-order { font-size: 11px; color: #98a4bb; margin-top: 2px; }
.cell-qty { font-size: 12px; color: #66748f; margin-top: 6px; font-variant-numeric: tabular-nums; }
.empty { padding: 28px 0; color: #98a4bb; font-size: 13px; }
</style>
