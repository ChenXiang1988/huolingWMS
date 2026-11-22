<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { listOwners } from '@/api/wms_master_data'
import { listLots } from '@/api/wms_inventory'
import { usePagedList } from '@/composables/usePagedList'

const RANGES = [
  { value: 7, label: '7 天内到期' },
  { value: 30, label: '30 天内到期' },
  { value: 90, label: '90 天内到期' },
]

const owners = ref<any[]>([])
const { items, total, page, pageSize, loading, query, fetch, search, onPageChange, onSizeChange } =
  usePagedList(listLots, { owner_id: '', sku_id: '', expiring_days: '' })

const ownerName = (id: number) => owners.value.find((o) => o.id === id)?.name || `#${id}`

/** 30 天内标黄，已过期标红——临期清单的价值就在这里。 */
function daysClass(days: number | null) {
  if (days === null || days === undefined) return ''
  if (days < 0) return 'expired'
  if (days <= 30) return 'warn'
  return ''
}

function daysText(days: number | null) {
  if (days === null || days === undefined) return '无到期日'
  if (days < 0) return `已过期 ${Math.abs(days)} 天`
  return `剩 ${days} 天`
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
      <el-select v-model="query.expiring_days" placeholder="临期筛选" clearable style="width: 150px" @change="search">
        <el-option v-for="r in RANGES" :key="r.value" :label="r.label" :value="r.value" />
      </el-select>
      <el-button @click="search">查询</el-button>
    </div>

    <el-table v-loading="loading" :data="items" border stripe height="calc(100vh - 240px)">
      <el-table-column prop="lot_code" label="批号" width="170" fixed />
      <el-table-column label="货主" width="160" show-overflow-tooltip>
        <template #default="{ row }">{{ ownerName(row.owner_id) }}</template>
      </el-table-column>
      <el-table-column prop="sku_id" label="商品" width="90" align="right" />
      <el-table-column prop="production_date" label="生产日期" width="130" />
      <el-table-column prop="expiry_date" label="到期日" width="130" />
      <el-table-column label="剩余" width="140">
        <template #default="{ row }">
          <span :class="['days', daysClass(row.days_left)]">{{ daysText(row.days_left) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag
            :type="row.status === 'active' ? 'success' : row.status === 'frozen' ? 'warning' : 'info'"
            size="small"
          >
            {{ row.status === 'active' ? '可发' : row.status === 'frozen' ? '冻结' : '已清空' }}
          </el-tag>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty">还没有批次。启用批次管理的商品在收货时才会产生批次。</div>
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
.days {
  font-size: 12px;
  color: #66748f;
}
.days.warn {
  color: #d97706;
  font-weight: 600;
}
.days.expired {
  color: #dc2626;
  font-weight: 600;
}
</style>
