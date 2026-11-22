<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listSkus } from '@/api/wms_master_data'
import { confirmPutawayLine, getPutaway, listPutaways } from '@/api/wms_inbound'
import { usePagedList } from '@/composables/usePagedList'

const STATUS: Record<string, { label: string; type: string }> = {
  pending: { label: '待上架', type: 'warning' },
  doing: { label: '上架中', type: 'primary' },
  done: { label: '已完成', type: 'success' },
  cancelled: { label: '已取消', type: 'danger' },
}

const skus = ref<any[]>([])
const { items, total, page, pageSize, loading, query, fetch, search, onPageChange, onSizeChange } =
  usePagedList(listPutaways, { status: '' })

const drawer = ref(false)
const busy = ref(false)
const head = ref<any>(null)

const skuLabel = (id: number) => {
  const s = skus.value.find((x) => x.id === id)
  return s ? `${s.code} ${s.name}` : `#${id}`
}

async function openDetail(row: any) {
  head.value = await getPutaway(row.id)
  drawer.value = true
}

/** 扫库位确认一行；不填目标库位时由服务端按温区优先选位。 */
async function confirmLine(line: any) {
  busy.value = true
  try {
    const res: any = await confirmPutawayLine(line.id)
    ElMessage.success(
      res.temp_mismatch
        ? `已上架到库位 ${res.to_location_id}（温区不匹配，已留痕）`
        : `已上架到库位 ${res.to_location_id}`,
    )
    head.value = await getPutaway(head.value.id)
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    busy.value = false
  }
}

const doneCount = () => (head.value?.lines || []).filter((l: any) => l.done).length

onMounted(async () => {
  const s: any = await listSkus({ page: 1, page_size: 200 })
  skus.value = s?.items || []
  await fetch()
})
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="query.status" placeholder="状态" clearable style="width: 130px" @change="search">
        <el-option v-for="(v, k) in STATUS" :key="k" :label="v.label" :value="k" />
      </el-select>
      <el-button @click="search">查询</el-button>
    </div>

    <el-table v-loading="loading" :data="items" border stripe height="calc(100vh - 240px)">
      <el-table-column prop="code" label="上架单号" width="150" fixed />
      <el-table-column prop="receipt_id" label="收货单 ID" width="120" />
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="STATUS[row.status]?.type as any" size="small">
            {{ STATUS[row.status]?.label || row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">去上架</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty">还没有上架任务。收货确认后会自动生成。</div>
      </template>
    </el-table>

    <el-pagination class="pagination" :current-page="page" :page-size="pageSize" :total="total"
                   :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next"
                   @current-change="onPageChange" @size-change="onSizeChange" />

    <el-drawer v-model="drawer" :title="head ? `上架 ${head.code}` : '上架'" size="640px">
      <template v-if="head">
        <div class="progress-line">
          <span>进度 {{ doneCount() }} / {{ head.lines.length }}</span>
          <el-tag :type="STATUS[head.status]?.type as any" size="small">
            {{ STATUS[head.status]?.label }}
          </el-tag>
        </div>

        <div v-for="ln in head.lines" :key="ln.id" class="row" :class="{ done: ln.done }">
          <div class="row-main">
            <div class="row-title">
              {{ skuLabel(ln.sku_id) }}
              <el-tag v-if="ln.sample_flag" size="small" type="warning" effect="plain">留样</el-tag>
              <el-tag v-if="ln.temp_mismatch" size="small" type="danger" effect="plain">温区不符</el-tag>
            </div>
            <div class="row-sub">
              数量 <b>{{ ln.qty }}</b> · 批次 <span class="mono">{{ ln.lot_id }}</span>
              · 从库位 <span class="mono">{{ ln.from_location_id }}</span>
              <template v-if="ln.to_location_id"> → 到库位 <span class="mono">{{ ln.to_location_id }}</span></template>
            </div>
          </div>
          <div class="row-act">
            <span v-if="ln.done" class="done-mark">已完成</span>
            <el-button v-else v-permission="'wms_inbound:putaway:execute'"
                       type="primary" size="small" :loading="busy" @click="confirmLine(ln)">
              确认上架
            </el-button>
          </div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.page { padding: 4px; }
.toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.pagination { margin-top: 12px; justify-content: flex-end; }
.empty { padding: 28px 0; color: #98a4bb; font-size: 13px; }
.progress-line { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; font-size: 13px; color: #66748f; }
.row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 14px; border: 1px solid #eef1f6; border-radius: 8px; margin-bottom: 10px; background: #fff; }
.row.done { background: #f7fbfa; border-color: #cdeae5; }
.row-title { font-size: 13px; font-weight: 600; color: #1b2740; display: flex; gap: 6px; align-items: center; }
.row-sub { margin-top: 4px; font-size: 12px; color: #66748f; }
.mono { font-family: ui-monospace, Menlo, monospace; }
.done-mark { font-size: 12px; color: #16a34a; }
</style>
