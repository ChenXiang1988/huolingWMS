<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listSkus } from '@/api/wms_master_data'
import { confirmPickLine, getPick, listPicks } from '@/api/wms_outbound'
import { usePagedList } from '@/composables/usePagedList'

const skus = ref<any[]>([])
const { items, total, page, pageSize, loading, query, fetch, search, onPageChange, onSizeChange } =
  usePagedList(listPicks, { status: '' })

const drawer = ref(false)
const busy = ref(false)
const head = ref<any>(null)
const scan = ref('')
const scanInput = ref<any>(null)

const skuLabel = (id: number) => {
  const s = skus.value.find((x) => x.id === id)
  return s ? `${s.code} ${s.name}` : `#${id}`
}

const nextLine = () => (head.value?.lines || []).find((l: any) => !l.picked)

async function openDetail(row: any) {
  head.value = await getPick(row.id)
  drawer.value = true
  await nextTick()
  scanInput.value?.focus()
}

async function doConfirm(code?: string) {
  const line = nextLine()
  if (!line) {
    ElMessage.success('这单已经拣完')
    return
  }
  busy.value = true
  try {
    await confirmPickLine(line.id, code ?? (scan.value || undefined))
    scan.value = ''
    head.value = await getPick(head.value.id)
    await fetch()
    await nextTick()
    scanInput.value?.focus()
  } catch (e) {
    console.error(e)
    scan.value = ''
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
      <el-select v-model="query.status" placeholder="状态" clearable style="width: 130px" @change="search">
        <el-option label="待拣" value="pending" />
        <el-option label="拣货中" value="doing" />
        <el-option label="已完成" value="done" />
      </el-select>
      <el-button @click="search">查询</el-button>
    </div>

    <el-table v-loading="loading" :data="items" border stripe height="calc(100vh - 240px)">
      <el-table-column prop="code" label="拣货单号" width="150" fixed />
      <el-table-column prop="order_id" label="订单 ID" width="110" />
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="row.status === 'done' ? 'success' : row.status === 'doing' ? 'primary' : 'warning'"
                  size="small">
            {{ row.status === 'done' ? '已完成' : row.status === 'doing' ? '拣货中' : '待拣' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">去拣货</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty">还没有拣货单。订单分配后点「生成拣货」才会出现。</div>
      </template>
    </el-table>

    <el-pagination class="pagination" :current-page="page" :page-size="pageSize" :total="total"
                   :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next"
                   @current-change="onPageChange" @size-change="onSizeChange" />

    <el-drawer v-model="drawer" :title="head ? `拣货 ${head.code}` : '拣货'" size="680px">
      <template v-if="head">
        <div class="scan-box">
          <label for="scan-input">扫库位编码确认当前行</label>
          <div class="scan-row">
            <input id="scan-input" ref="scanInput" v-model="scan" placeholder="扫库位条码或手工输入后回车"
                   @keyup.enter="doConfirm()" />
            <el-button type="primary" :loading="busy" @click="doConfirm()">确认</el-button>
          </div>
          <div class="hint">
            下一行：{{ nextLine() ? `库位 ${nextLine().location_id}` : '已全部拣完' }}
          </div>
        </div>

        <el-table :data="head.lines" size="small" border>
          <el-table-column prop="seq" label="#" width="60" align="center" />
          <el-table-column label="商品" min-width="150">
            <template #default="{ row }">{{ skuLabel(row.sku_id) }}</template>
          </el-table-column>
          <el-table-column prop="lot_id" label="批次" width="80" align="right" />
          <el-table-column prop="location_id" label="库位" width="80" align="right" />
          <el-table-column prop="qty" label="数量" width="90" align="right" class-name="num" />
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.picked" size="small" type="success">已拣</el-tag>
              <span v-else class="muted">待拣</span>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.page { padding: 4px; }
.toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.pagination { margin-top: 12px; justify-content: flex-end; }
.empty { padding: 28px 0; color: #98a4bb; font-size: 13px; }
.muted { color: #98a4bb; font-size: 12px; }
.scan-box { padding: 12px 14px; background: #f7fbfa; border: 1px solid #cdeae5; border-radius: 8px; margin-bottom: 12px; }
.scan-box label { display: block; font-size: 12px; color: #0e8c80; font-weight: 600; margin-bottom: 8px; }
.scan-row { display: flex; gap: 8px; }
.scan-row input { flex: 1; padding: 9px 12px; font-size: 14px; color: #1b2740; border: 1px solid #b9e5df; border-radius: 7px; outline: none; }
.scan-row input:focus { border-color: #10b3a3; box-shadow: 0 0 0 3px rgba(16, 179, 163, 0.14); }
.hint { margin-top: 8px; font-size: 12px; color: #66748f; }
:deep(.num) { font-family: ui-monospace, Menlo, monospace; font-variant-numeric: tabular-nums; }
</style>
