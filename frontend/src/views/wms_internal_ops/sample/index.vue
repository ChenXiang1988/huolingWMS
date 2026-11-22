<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { backfillSamples, disposeSample, listSamples } from '@/api/wms_ops'
import { usePagedList } from '@/composables/usePagedList'

const { items, total, page, pageSize, loading, query, fetch, search, onPageChange, onSizeChange } =
  usePagedList(listSamples, { status: 'holding' })
const busy = ref(false)

const METHODS: Record<string, string> = {
  scrap: '报废', return_owner: '退回货主', restock: '转回可发', extend: '延长留样',
}

async function doBackfill() {
  const res: any = await backfillSamples()
  ElMessage.success(res.created ? `回填 ${res.created} 条` : '没有需要回填的历史留样')
  await fetch()
}

async function dispose(row: any, method: string) {
  if (method !== 'extend') {
    await ElMessageBox.confirm(
      `确认${METHODS[method]}？库存会立即变动，且不可撤销。`,
      '留样处置', { type: 'warning' },
    )
  }
  busy.value = true
  try {
    await disposeSample(row.id, { method, reason: undefined })
    ElMessage.success(method === 'extend' ? `到期日顺延 ${row.retain_days} 天` : `${METHODS[method]}完成`)
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    busy.value = false
  }
}

const daysClass = (n: number | null) => n === null ? '' : n < 0 ? 'over' : n <= 7 ? 'soon' : ''
const statusText = (s: string) => s === 'holding' ? '留样中' : '已处置'

onMounted(fetch)
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="query.status" placeholder="状态" clearable style="width: 140px" @change="search">
        <el-option label="留样中" value="holding" />
        <el-option label="已处置" value="disposed" />
      </el-select>
      <el-button @click="search">查询</el-button>
      <div class="spacer" />
      <el-button v-permission="'wms_internal_ops:sample:create'" @click="doBackfill">
        回填历史留样
      </el-button>
    </div>

    <el-table v-loading="loading" :data="items" border stripe height="calc(100vh - 240px)">
      <el-table-column prop="id" label="#" width="70" />
      <el-table-column prop="sku_id" label="商品" width="90" />
      <el-table-column prop="lot_id" label="批次" width="80" />
      <el-table-column prop="location_id" label="留样位" width="90" />
      <el-table-column prop="qty" label="数量" width="100" align="right" class-name="num" />
      <el-table-column label="到期日" width="170">
        <template #default="{ row }">{{ (row.expire_at || '').replace('T', ' ').slice(0, 16) || '—' }}</template>
      </el-table-column>
      <el-table-column label="剩余" width="100">
        <template #default="{ row }">
          <span :class="['num', daysClass(row.days_left)]">
            {{ row.days_left === null ? '—' : row.days_left < 0 ? `超期 ${-row.days_left} 天` : `${row.days_left} 天` }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="到期处置" width="110">
        <template #default="{ row }">{{ METHODS[row.on_expiry] || row.on_expiry }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'holding' ? 'warning' : 'success'" size="small">
            {{ statusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row }">
          <template v-if="row.status === 'holding'">
            <el-button v-for="(label, key) in METHODS" :key="key"
                       v-permission="'wms_internal_ops:sample:dispose'" link
                       :type="key === 'scrap' || key === 'return_owner' ? 'danger' : 'primary'"
                       :loading="busy" @click="dispose(row, String(key))">{{ label }}</el-button>
          </template>
          <span v-else class="muted">{{ METHODS[row.method] || row.method }}</span>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty">还没有留样记录。收货时按比例留的样，上架完成后会进台账。</div>
      </template>
    </el-table>

    <el-pagination class="pagination" :current-page="page" :page-size="pageSize" :total="total"
                   :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next"
                   @current-change="onPageChange" @size-change="onSizeChange" />
  </div>
</template>

<style scoped>
.page { padding: 4px; }
.toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.spacer { flex: 1; }
.pagination { margin-top: 12px; justify-content: flex-end; }
.empty { padding: 28px 0; color: #98a4bb; font-size: 13px; }
.muted { font-size: 12px; color: #98a4bb; }
.num { font-family: ui-monospace, Menlo, monospace; font-variant-numeric: tabular-nums; }
.num.soon { color: #d97706; font-weight: 600; }
.num.over { color: #dc2626; font-weight: 600; }
:deep(.num) { font-family: ui-monospace, Menlo, monospace; font-variant-numeric: tabular-nums; }
</style>
