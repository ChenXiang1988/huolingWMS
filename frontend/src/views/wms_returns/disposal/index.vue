<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listSkus } from '@/api/wms_master_data'
import { handleDisposal, listDisposals } from '@/api/wms_returns'
import { usePagedList } from '@/composables/usePagedList'

const skus = ref<any[]>([])
const { items, total, page, pageSize, loading, query, fetch, search, onPageChange, onSizeChange } =
  usePagedList(listDisposals, { status: 'pending' })

const skuLabel = (id: number) => {
  const s = skus.value.find((x) => x.id === id)
  return s ? `${s.code} ${s.name}` : `#${id}`
}

/** 滞留天数：超过 7 天整行标黄，提醒该处理了。 */
function agingDays(createdAt: string) {
  if (!createdAt) return 0
  const ms = Date.now() - new Date(createdAt).getTime()
  return Math.floor(ms / 86400000)
}

function rowClass({ row }: any) {
  return agingDays(row.created_at) >= 7 ? 'aging' : ''
}

async function act(row: any, method: 'restock' | 'scrap') {
  const { value } = await ElMessageBox.prompt(
    method === 'restock'
      ? '转回可发：确认这批货外箱完好、可以正常发出？'
      : '报废：确认这批货无法再销售？此操作会扣减库存。',
    method === 'restock' ? '转回可发' : '报废',
    { inputPlaceholder: '填写原因（会记入流水）', type: 'warning' },
  )
  await handleDisposal(row.id, { method, reason: value || undefined })
  ElMessage.success('已处理')
  await fetch()
}

onMounted(async () => {
  const s: any = await listSkus({ page: 1, page_size: 200 })
  skus.value = s?.items || []
  await fetch()
})
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="query.status" placeholder="状态" style="width: 130px" @change="search">
        <el-option label="待处置" value="pending" />
        <el-option label="已处置" value="handled" />
      </el-select>
      <el-button @click="search">查询</el-button>
    </div>

    <el-table v-loading="loading" :data="items" border stripe height="calc(100vh - 240px)"
              :row-class-name="rowClass">
      <el-table-column label="商品" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ skuLabel(row.sku_id) }}</template>
      </el-table-column>
      <el-table-column prop="lot_id" label="批次" width="80" align="right" />
      <el-table-column prop="location_id" label="库位" width="80" align="right" />
      <el-table-column prop="qty" label="数量" width="110" align="right" class-name="num" />
      <el-table-column label="滞留" width="110">
        <template #default="{ row }">
          <span :class="['aging-text', agingDays(row.created_at) >= 7 ? 'warn' : '']">
            {{ agingDays(row.created_at) }} 天
          </span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'pending' ? 'warning' : 'success'" size="small">
            {{ row.status === 'pending' ? '待处置' : '已处置' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <template v-if="row.status === 'pending'">
            <el-button v-permission="'wms_returns:disposal:restock'" link type="primary"
                       @click="act(row, 'restock')">转回可发</el-button>
            <el-button v-permission="'wms_returns:disposal:scrap'" link type="danger"
                       @click="act(row, 'scrap')">报废</el-button>
          </template>
          <span v-else class="muted">{{ row.method === 'restock' ? '已转回' : '已报废' }}</span>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty">没有待处置的破损货。收货时录了破损，这里才会出现。</div>
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
.pagination { margin-top: 12px; justify-content: flex-end; }
.empty { padding: 28px 0; color: #98a4bb; font-size: 13px; }
.muted { font-size: 12px; color: #98a4bb; }
.aging-text { font-size: 12px; color: #66748f; }
.aging-text.warn { color: #d97706; font-weight: 600; }
:deep(.num) { font-family: ui-monospace, Menlo, monospace; font-variant-numeric: tabular-nums; }
:deep(.aging) { background: #fffdf5; }
</style>
