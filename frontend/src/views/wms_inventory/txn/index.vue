<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { listOwners } from '@/api/wms_master_data'
import { listTxns } from '@/api/wms_inventory'
import { usePagedList } from '@/composables/usePagedList'

const ACTIONS = [
  { value: 'adjust', label: '手工调整' },
  { value: 'receipt', label: '收货' },
  { value: 'putaway', label: '上架' },
  { value: 'pick', label: '拣货' },
  { value: 'shipment', label: '发运' },
]

const owners = ref<any[]>([])
const { items, total, page, pageSize, loading, query, fetch, search, onPageChange, onSizeChange } =
  usePagedList(listTxns, { owner_id: '', sku_id: '', action: '' })

const ownerName = (id: number) => owners.value.find((o) => o.id === id)?.name || `#${id}`
const actionLabel = (v: string) => ACTIONS.find((a) => a.value === v)?.label || v

/** 正数用绿色、负数用红色——一眼能看出这笔是进还是出。 */
function deltaClass(delta: string) {
  return Number(delta) >= 0 ? 'in' : 'out'
}

function showSign(delta: string) {
  const n = Number(delta)
  return n > 0 ? `+${delta}` : delta
}

onMounted(async () => {
  const data: any = await listOwners({ page: 1, page_size: 200 })
  owners.value = data?.items || []
  await fetch()
})
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="query.owner_id" placeholder="货主" clearable style="width: 170px" @change="search">
        <el-option v-for="o in owners" :key="o.id" :label="`${o.code} ${o.name}`" :value="o.id" />
      </el-select>
      <el-input
        v-model="query.sku_id"
        placeholder="商品 ID"
        clearable
        style="width: 130px"
        @keyup.enter="search"
        @clear="search"
      />
      <el-select v-model="query.action" placeholder="动作" clearable style="width: 130px" @change="search">
        <el-option v-for="a in ACTIONS" :key="a.value" :label="a.label" :value="a.value" />
      </el-select>
      <el-button @click="search">查询</el-button>
    </div>

    <el-table v-loading="loading" :data="items" border stripe height="calc(100vh - 240px)">
      <el-table-column label="时间" width="170">
        <template #default="{ row }">{{ (row.created_at || '').replace('T', ' ').slice(0, 19) }}</template>
      </el-table-column>
      <el-table-column label="动作" width="110">
        <template #default="{ row }">{{ actionLabel(row.action) }}</template>
      </el-table-column>
      <el-table-column label="来源" width="140">
        <template #default="{ row }">
          <span class="mono">{{ row.ref_type }}/{{ row.ref_id }}</span>
        </template>
      </el-table-column>
      <el-table-column label="货主" width="150" show-overflow-tooltip>
        <template #default="{ row }">{{ ownerName(row.owner_id) }}</template>
      </el-table-column>
      <el-table-column prop="sku_id" label="商品" width="80" align="right" />
      <el-table-column prop="lot_id" label="批次" width="80" align="right" />
      <el-table-column prop="location_id" label="库位" width="80" align="right" />
      <el-table-column label="状态变动" width="140">
        <template #default="{ row }">
          <span v-if="row.from_status" class="mono">
            {{ row.from_status }} → {{ row.to_status }}
          </span>
          <span v-else class="mono">{{ row.stock_status }}</span>
        </template>
      </el-table-column>
      <el-table-column label="变动" width="110" align="right">
        <template #default="{ row }">
          <span :class="['num', deltaClass(row.delta)]">{{ showSign(row.delta) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="变动后" width="110" align="right">
        <template #default="{ row }"><span class="num">{{ row.qty_after }}</span></template>
      </el-table-column>
      <template #empty>
        <div class="empty">还没有流水。库存流水只追加不修改，任何数量变动都会在这里留痕。</div>
      </template>
    </el-table>

    <el-pagination
      class="pagination"
      :current-page="page"
      :page-size="pageSize"
      :total="total"
      :page-sizes="[20, 50, 100]"
      layout="total, sizes, prev, pager, next"
      @current-change="onPageChange"
      @size-change="onSizeChange"
    />
  </div>
</template>

<style scoped>
.page {
  padding: 4px;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.pagination {
  margin-top: 12px;
  justify-content: flex-end;
}
.empty {
  padding: 28px 0;
  color: #98a4bb;
  font-size: 13px;
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}
.num {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-variant-numeric: tabular-nums;
}
.in {
  color: #16a34a;
}
.out {
  color: #dc2626;
}
</style>
