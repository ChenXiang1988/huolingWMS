<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  cancelWave,
  createWave,
  createWaveRule,
  listWaveRules,
  listWaves,
} from '@/api/wms_wave'
import { usePagedList } from '@/composables/usePagedList'

const STATUS: Record<string, { label: string; type: string }> = {
  pending: { label: '等待生成', type: 'info' },
  generating: { label: '生成中', type: 'warning' },
  ready: { label: '待拣货', type: 'primary' },
  picking: { label: '拣货中', type: 'primary' },
  done: { label: '已完成', type: 'success' },
  cancelled: { label: '已中止', type: 'danger' },
  interrupted: { label: '已中断', type: 'danger' },
}

const { items, total, page, pageSize, loading, query, fetch, search, onPageChange, onSizeChange } =
  usePagedList(listWaves, { status: '' })
const rules = ref<any[]>([])
const summary = reactive({ pending: 0, running: 0, ready: 0, done: 0 })
const ruleOpen = ref(false)
const form = reactive<any>({
  code: '', name: '', cutoff_at: '', carrier_code: '', region_prefix: '',
  hot_only: false, hot_line_limit: 2, max_orders: 200, rule_id: null,
})
let timer: any = null

async function loadRules() {
  rules.value = (await listWaveRules()) as any
}

async function refresh() {
  await fetch()
  const all = (await listWaves({ page: 1, page_size: 200 })) as any
  const rows = all?.items || []
  summary.pending = rows.filter((r: any) => r.status === 'pending').length
  summary.running = rows.filter((r: any) => r.status === 'generating').length
  summary.ready = rows.filter((r: any) => r.status === 'ready').length
  summary.done = rows.filter((r: any) => r.status === 'done' || r.status === 'ready').length
  if (rows.some((r: any) => ['pending', 'generating'].includes(r.status))) {
    if (!timer) timer = setInterval(refresh, 1500)
  } else if (timer) {
    clearInterval(timer)
    timer = null
  }
}

async function generate() {
  const res: any = await createWave({ rule_id: form.rule_id ?? null })
  ElMessage.success(`已发起 ${res.code}，共 ${res.total} 单`)
  await refresh()
}

async function onCancel(row: any) {
  const { value } = await ElMessageBox.prompt(
    '中止后已生成的拣货单会作废，库存数量不变。确认中止？',
    '中止波次', { inputPlaceholder: '填写原因', type: 'warning' },
  )
  await cancelWave(row.id, value || undefined)
  ElMessage.success('已中止')
  await refresh()
}

async function saveRule() {
  await createWaveRule({ ...form, cutoff_at: form.cutoff_at || null })
  ElMessage.success('规则已保存')
  ruleOpen.value = false
  await loadRules()
}

onMounted(async () => {
  await loadRules()
  await refresh()
})
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<template>
  <div class="page">
    <div class="cards">
      <div class="card"><span>等待生成</span><b>{{ summary.pending }}</b></div>
      <div class="card"><span>生成中</span><b>{{ summary.running }}</b></div>
      <div class="card"><span>待拣货</span><b>{{ summary.ready }}</b></div>
      <div class="card"><span>可发波次</span><b>{{ summary.done }}</b></div>
    </div>

    <div class="toolbar">
      <el-select v-model="query.status" placeholder="状态" clearable style="width: 140px" @change="search">
        <el-option v-for="(v, k) in STATUS" :key="k" :label="v.label" :value="k" />
      </el-select>
      <el-select v-model="form.rule_id" placeholder="波次规则（可空）" clearable style="width: 190px">
        <el-option v-for="r in rules" :key="r.id" :label="r.name" :value="r.id" />
      </el-select>
      <el-button @click="search">查询</el-button>
      <div class="spacer" />
      <el-button @click="ruleOpen = true">规则管理</el-button>
      <el-button v-permission="'wms_outbound:wave:create'" type="primary" @click="generate">
        生成波次
      </el-button>
    </div>

    <el-table v-loading="loading" :data="items" border stripe height="calc(100vh - 330px)">
      <el-table-column prop="code" label="波次号" width="140" fixed />
      <el-table-column prop="rule_id" label="规则" width="90" />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="STATUS[row.status]?.type as any" size="small">
            {{ STATUS[row.status]?.label || row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="进度" min-width="200">
        <template #default="{ row }">
          <div class="prog">
            <el-progress :percentage="row.progress" :stroke-width="8" />
            <span class="mono">{{ row.processed }}/{{ row.total }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="failed" label="失败单" width="90" align="right" />
      <el-table-column label="操作" width="110" fixed="right">
        <template #default="{ row }">
          <el-button v-if="['pending', 'generating', 'ready'].includes(row.status)"
                     v-permission="'wms_outbound:wave:cancel'" link type="danger"
                     @click="onCancel(row)">中止</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty">还没有波次。选一条规则点「生成波次」，进度会自己往前走。</div>
      </template>
    </el-table>

    <el-pagination class="pagination" :current-page="page" :page-size="pageSize" :total="total"
                   :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next"
                   @current-change="onPageChange" @size-change="onSizeChange" />

    <el-drawer v-model="ruleOpen" title="波次规则" size="520px">
      <el-form label-width="94px">
        <el-form-item label="编码" required><el-input v-model="form.code" /></el-form-item>
        <el-form-item label="名称" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="截单时间"><el-input v-model="form.cutoff_at" placeholder="HH:MM，留空不限" /></el-form-item>
        <el-form-item label="承运商"><el-input v-model="form.carrier_code" placeholder="如 SF" /></el-form-item>
        <el-form-item label="区域前缀"><el-input v-model="form.region_prefix" /></el-form-item>
        <el-form-item label="仅热门单"><el-switch v-model="form.hot_only" /></el-form-item>
        <el-form-item v-if="form.hot_only" label="行数上限">
          <el-input-number v-model="form.hot_line_limit" :min="1" />
        </el-form-item>
        <el-form-item label="单波上限"><el-input-number v-model="form.max_orders" :min="1" :max="2000" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ruleOpen = false">关闭</el-button>
        <el-button type="primary" @click="saveRule">新建规则</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.page { padding: 4px; }
.cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 12px; }
.card { padding: 12px 14px; background: #fff; border: 1px solid #e8ecf3; border-radius: 8px; }
.card span { font-size: 12px; color: #66748f; }
.card b { display: block; margin-top: 6px; font-size: 22px; color: #1b2740; font-variant-numeric: tabular-nums; }
.toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.spacer { flex: 1; }
.pagination { margin-top: 12px; justify-content: flex-end; }
.empty { padding: 28px 0; color: #98a4bb; font-size: 13px; }
.prog { display: flex; align-items: center; gap: 10px; }
.prog :deep(.el-progress) { flex: 1; }
.mono { font-size: 12px; font-family: ui-monospace, Menlo, monospace; color: #66748f; white-space: nowrap; }
</style>
