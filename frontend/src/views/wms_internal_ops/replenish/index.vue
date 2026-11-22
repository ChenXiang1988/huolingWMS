<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listSkus } from '@/api/wms_master_data'
import {
  executeReplenish,
  listReplenishments,
  suggestReplenish,
} from '@/api/wms_wave'
import { usePagedList } from '@/composables/usePagedList'

const skus = ref<any[]>([])
const { items, total, page, pageSize, loading, query, fetch, search, onPageChange, onSizeChange } =
  usePagedList(listReplenishments, { status: 'suggested' })
const busy = ref(false)

const skuLabel = (id: number) => {
  const s = skus.value.find((x) => x.id === id)
  return s ? `${s.code} ${s.name}` : `#${id}`
}

async function suggest() {
  busy.value = true
  try {
    const res: any = await suggestReplenish()
    ElMessage.success(res.created ? `生成 ${res.created} 条建议` : '没有需要补货的拣选位')
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    busy.value = false
  }
}

async function execute(row: any) {
  busy.value = true
  try {
    await executeReplenish(row.id)
    ElMessage.success(`已补 ${row.qty} 件`)
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    busy.value = false
  }
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
      <el-select v-model="query.status" placeholder="状态" clearable style="width: 140px" @change="search">
        <el-option label="待处理" value="suggested" />
        <el-option label="已完成" value="done" />
        <el-option label="已取消" value="cancelled" />
      </el-select>
      <el-button @click="search">查询</el-button>
      <div class="spacer" />
      <el-button v-permission="'wms_internal_ops:replenish:create'" :loading="busy" @click="suggest">
        扫描并生成建议
      </el-button>
    </div>

    <el-table v-loading="loading" :data="items" border stripe height="calc(100vh - 240px)">
      <el-table-column label="商品" min-width="170" show-overflow-tooltip>
        <template #default="{ row }">{{ skuLabel(row.sku_id) }}</template>
      </el-table-column>
      <el-table-column prop="lot_id" label="批次" width="80" align="right" />
      <el-table-column prop="from_location_id" label="来源库位" width="100" align="right" />
      <el-table-column prop="to_location_id" label="拣选库位" width="100" align="right" />
      <el-table-column label="当前 / 下限" width="130">
        <template #default="{ row }">
          <span class="num">{{ row.current_qty }} / {{ row.min_qty }}</span>
        </template>
      </el-table-column>
      <el-table-column label="建议补货" width="110" align="right">
        <template #default="{ row }"><b class="num">{{ row.qty }}</b></template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'done' ? 'success' : row.status === 'suggested' ? 'warning' : 'info'"
                  size="small">
            {{ row.status === 'done' ? '已完成' : row.status === 'suggested' ? '待处理' : '已取消' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="110" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 'suggested'"
                     v-permission="'wms_internal_ops:replenish:execute'" link type="primary"
                     :loading="busy" @click="execute(row)">执行补货</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty">还没有补货建议。点「扫描并生成建议」，系统会找出低于下限的拣选位。</div>
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
.num { font-family: ui-monospace, Menlo, monospace; font-variant-numeric: tabular-nums; }
</style>
