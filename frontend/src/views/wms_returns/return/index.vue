<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listSkus } from '@/api/wms_master_data'
import { createReturn, getReturn, listReturns, receiveReturn } from '@/api/wms_returns'
import { usePagedList } from '@/composables/usePagedList'

const STATUS: Record<string, string> = {
  confirmed: '待入库', received: '已入库', draft: '草稿', cancelled: '已取消',
}
const skus = ref<any[]>([])
const { items, total, page, pageSize, loading, query, fetch, search, onPageChange, onSizeChange } =
  usePagedList(listReturns, { status: '' })
const createOpen = ref(false)
const detailOpen = ref(false)
const detail = ref<any>(null)
const busy = ref(false)
const form = reactive<any>({
  owner_id: 1, owner_doc_no: '', customer_name: '', source_order_code: '',
  remark: '', lines: [{ sku_id: null, lot_id: 0, qty: '', quality: 'good' }],
})

const skuOf = (id: number) => skus.value.find((s) => s.id === id)

function addLine() {
  form.lines.push({ sku_id: null, lot_id: 0, qty: '', quality: 'good' })
}

async function create() {
  const lines = form.lines.filter((l: any) => l.sku_id && Number(l.qty) > 0)
  if (!lines.length) {
    ElMessage.warning('至少一行有效明细')
    return
  }
  busy.value = true
  try {
    await createReturn({ ...form, lines })
    ElMessage.success('退货单已建')
    createOpen.value = false
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    busy.value = false
  }
}

async function openDetail(row: any) {
  detail.value = await getReturn(row.id)
  detailOpen.value = true
}

async function receive(row: any) {
  busy.value = true
  try {
    await receiveReturn(row.id)
    ElMessage.success('已入库，破损货生成了待处置记录')
    await fetch()
    if (detail.value?.id === row.id) detail.value = await getReturn(row.id)
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
      <el-select v-model="query.status" placeholder="状态" clearable style="width: 130px" @change="search">
        <el-option v-for="(v, k) in STATUS" :key="k" :label="v" :value="k" />
      </el-select>
      <el-button @click="search">查询</el-button>
      <div class="spacer" />
      <el-button v-permission="'wms_returns:return:create'" type="primary" @click="createOpen = true">
        新建退货单
      </el-button>
    </div>

    <el-table v-loading="loading" :data="items" border stripe height="calc(100vh - 240px)"
              @row-dblclick="openDetail">
      <el-table-column prop="code" label="退货单号" width="150" />
      <el-table-column prop="owner_doc_no" label="货主单号" width="160" />
      <el-table-column prop="customer_name" label="客户" min-width="130" />
      <el-table-column prop="source_order_code" label="原出库单" width="150" />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="row.status === 'received' ? 'success' : 'warning'" size="small">
            {{ STATUS[row.status] || row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">明细</el-button>
          <el-button v-if="row.status === 'confirmed'"
                     v-permission="'wms_returns:return:receive'" link type="primary"
                     :loading="busy" @click="receive(row)">确认入库</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty">还没有退货单。客户退回的货按品质分流，破损的会进待处置清单。</div>
      </template>
    </el-table>

    <el-pagination class="pagination" :current-page="page" :page-size="pageSize" :total="total"
                   :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next"
                   @current-change="onPageChange" @size-change="onSizeChange" />

    <el-dialog v-model="createOpen" title="新建退货单" width="680px">
      <el-form label-width="94px">
        <el-form-item label="货主"><el-input-number v-model="form.owner_id" :min="1" /></el-form-item>
        <el-form-item label="货主单号"><el-input v-model="form.owner_doc_no" /></el-form-item>
        <el-form-item label="客户"><el-input v-model="form.customer_name" /></el-form-item>
        <el-form-item label="原出库单"><el-input v-model="form.source_order_code" /></el-form-item>
        <el-form-item label="明细">
          <div class="lines">
            <div v-for="(l, i) in form.lines" :key="i" class="line">
              <el-select v-model="l.sku_id" filterable placeholder="商品" style="flex: 1">
                <el-option v-for="s in skus" :key="s.id" :label="`${s.code} ${s.name}`" :value="s.id" />
              </el-select>
              <el-input v-model="l.lot_id" placeholder="批次 ID" style="width: 100px" />
              <el-input v-model="l.qty" placeholder="数量" style="width: 100px" />
              <el-select v-model="l.quality" style="width: 110px">
                <el-option label="可发" value="good" />
                <el-option label="破损" value="damaged" />
              </el-select>
              <el-button link type="danger" @click="form.lines.splice(i, 1)">删</el-button>
            </div>
            <el-button link type="primary" @click="addLine">+ 加一行</el-button>
            <div class="hint">
              启用批次管理的商品必须填批次 ID，否则无法按先到期先出发货。
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createOpen = false">取消</el-button>
        <el-button type="primary" :loading="busy" @click="create">创建</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailOpen" :title="detail ? `退货 ${detail.code}` : '退货'" size="560px">
      <template v-if="detail">
        <div class="kv"><span>状态</span><b>{{ STATUS[detail.status] || detail.status }}</b></div>
        <div class="kv"><span>客户</span><b>{{ detail.customer_name || '—' }}</b></div>
        <div class="kv"><span>原出库单</span><b>{{ detail.source_order_code || '—' }}</b></div>
        <el-table :data="detail.lines" size="small" border style="margin-top: 14px">
          <el-table-column prop="sku_id" label="商品" width="90" />
          <el-table-column prop="lot_id" label="批次" width="80" />
          <el-table-column prop="qty" label="数量" width="100" align="right" class-name="num" />
          <el-table-column label="品质" width="90">
            <template #default="{ row }">
              <el-tag :type="row.quality === 'good' ? 'success' : 'danger'" size="small">
                {{ row.quality === 'good' ? '可发' : '破损' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="已过账" width="90">
            <template #default="{ row }">{{ row.posted ? '是' : '否' }}</template>
          </el-table-column>
        </el-table>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.page { padding: 4px; }
.toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.spacer { flex: 1; }
.pagination { margin-top: 12px; justify-content: flex-end; }
.empty { padding: 28px 0; color: #98a4bb; font-size: 13px; }
.lines { display: flex; flex-direction: column; gap: 8px; width: 100%; }
.line { display: flex; align-items: center; gap: 8px; }
.hint { font-size: 12px; line-height: 1.7; color: #98a4bb; }
.kv { display: flex; justify-content: space-between; padding: 6px 0; font-size: 13px; color: #1b2740; border-bottom: 1px dashed #eef1f6; }
.kv span { color: #66748f; }
:deep(.num) { font-family: ui-monospace, Menlo, monospace; font-variant-numeric: tabular-nums; }
</style>
