<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listOwners, listSkus } from '@/api/wms_master_data'
import {
  allocateOrder,
  cancelOrder,
  createOrder,
  getOrder,
  listOrders,
  makePick,
} from '@/api/wms_outbound'
import { usePagedList } from '@/composables/usePagedList'

const STATUS: Record<string, { label: string; type: string }> = {
  draft: { label: '草稿', type: 'info' },
  confirmed: { label: '待分配', type: 'warning' },
  allocated: { label: '已分配', type: 'primary' },
  picking: { label: '拣货中', type: 'primary' },
  checked: { label: '已复核', type: 'success' },
  shipped: { label: '已发运', type: 'success' },
  cancelled: { label: '已取消', type: 'danger' },
}

const owners = ref<any[]>([])
const skus = ref<any[]>([])
const { items, total, page, pageSize, loading, query, fetch, search, onPageChange, onSizeChange } =
  usePagedList(listOrders, { owner_id: '', status: '', keyword: '' })

const drawer = ref(false)
const saving = ref(false)
const form = reactive<any>({
  owner_id: null, owner_doc_no: '', order_type: 'C',
  receiver: '', receiver_phone: '', receiver_address: '', carrier_code: '',
  lines: [{ sku_id: null, qty: '', lot_id: null }],
})

const detailOpen = ref(false)
const detail = ref<any>(null)

const ownerName = (id: number) => owners.value.find((o) => o.id === id)?.name || `#${id}`
const skuLabel = (id: number) => {
  const s = skus.value.find((x) => x.id === id)
  return s ? `${s.code} ${s.name}` : `#${id}`
}

async function loadRefs() {
  const [o, s] = await Promise.all([
    listOwners({ page: 1, page_size: 200 }),
    listSkus({ page: 1, page_size: 200 }),
  ])
  owners.value = (o as any)?.items || []
  skus.value = (s as any)?.items || []
}

function openCreate() {
  Object.assign(form, {
    owner_id: query.owner_id || owners.value[0]?.id || null,
    owner_doc_no: '', order_type: 'C',
    receiver: '', receiver_phone: '', receiver_address: '', carrier_code: '',
    lines: [{ sku_id: null, qty: '', lot_id: null }],
  })
  drawer.value = true
}

async function submit() {
  if (!form.owner_id || !form.owner_doc_no.trim()) {
    ElMessage.warning('货主与货主单号必填')
    return
  }
  const lines = form.lines
    .filter((l: any) => l.sku_id && Number(l.qty) > 0)
    .map((l: any) => ({ sku_id: l.sku_id, qty: String(l.qty), lot_id: l.lot_id || null }))
  if (!lines.length) {
    ElMessage.warning('至少一行有效明细')
    return
  }
  saving.value = true
  try {
    const res: any = await createOrder({ ...form, lines })
    ElMessage.success(`已建单 ${res.code}`)
    drawer.value = false
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    saving.value = false
  }
}

async function openDetail(row: any) {
  detail.value = await getOrder(row.id)
  detailOpen.value = true
}

async function allocate(row: any) {
  await ElMessageBox.confirm(
    '分配只锁定量，不动库存；发运时才真正扣减。确认分配？',
    '分配',
    { type: 'info' },
  )
  saving.value = true
  try {
    const res: any = await allocateOrder(row.id)
    ElMessage.success(`已分配 ${res.allocations} 条，共 ${res.qty}`)
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    saving.value = false
  }
}

async function startPick(row: any) {
  const res: any = await makePick(row.id)
  ElMessage.success(`拣货单 ${res.code} 已生成`)
  await fetch()
}

async function cancel(row: any) {
  await ElMessageBox.confirm(
    '取消后分配量作废，已发运订单不能取消。确认取消？',
    '取消订单',
    { type: 'warning' },
  )
  saving.value = true
  try {
    await cancelOrder(row.id)
    ElMessage.success('订单已取消')
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadRefs()
  await fetch()
})
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="query.owner_id" placeholder="货主" clearable style="width: 170px" @change="search">
        <el-option v-for="o in owners" :key="o.id" :label="`${o.code} ${o.name}`" :value="o.id" />
      </el-select>
      <el-select v-model="query.status" placeholder="状态" clearable style="width: 130px" @change="search">
        <el-option v-for="(v, k) in STATUS" :key="k" :label="v.label" :value="k" />
      </el-select>
      <el-input v-model="query.keyword" placeholder="订单号 / 货主单号" clearable style="width: 220px"
                @keyup.enter="search" @clear="search" />
      <el-button @click="search">查询</el-button>
      <div class="spacer" />
      <el-button v-permission="'wms_outbound:order:create'" type="primary" @click="openCreate">
        新建订单
      </el-button>
    </div>

    <el-table v-loading="loading" :data="items" border stripe height="calc(100vh - 260px)">
      <el-table-column prop="code" label="订单号" width="140" fixed />
      <el-table-column prop="owner_doc_no" label="货主单号" width="160" />
      <el-table-column label="货主" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">{{ ownerName(row.owner_id) }}</template>
      </el-table-column>
      <el-table-column label="类型" width="80" align="center">
        <template #default="{ row }">
          <el-tag size="small" :type="row.order_type === 'B' ? 'warning' : 'info'" effect="plain">
            {{ row.order_type }} 端
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="receiver" label="收件人" width="110" />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="STATUS[row.status]?.type as any" size="small">
            {{ STATUS[row.status]?.label || row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="290" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button v-if="row.status === 'confirmed'" v-permission="'wms_outbound:order:allocate'"
                     link type="primary" :loading="saving" @click="allocate(row)">分配</el-button>
          <el-button v-if="row.status === 'allocated'"
                     link type="primary" @click="startPick(row)">生成拣货</el-button>
          <el-button v-if="row.status !== 'shipped' && row.status !== 'cancelled'"
                     v-permission="'wms_outbound:order:cancel'"
                     link type="danger" :loading="saving" @click="cancel(row)">取消</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty">还没有出库订单。货主可经开放接口推单，也可在这里建单。</div>
      </template>
    </el-table>

    <el-pagination class="pagination" :current-page="page" :page-size="pageSize" :total="total"
                   :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next"
                   @current-change="onPageChange" @size-change="onSizeChange" />

    <el-drawer v-model="drawer" title="新建出库订单" size="640px">
      <el-form label-width="94px">
        <el-form-item label="货主" required>
          <el-select v-model="form.owner_id" style="width: 100%">
            <el-option v-for="o in owners" :key="o.id" :label="`${o.code} ${o.name}`" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="货主单号" required>
          <el-input v-model="form.owner_doc_no" placeholder="货主侧单号，用于去重" />
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.order_type">
            <el-radio value="C">C 端电商</el-radio>
            <el-radio value="B">B 端大货</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="收件人">
          <div class="two">
            <el-input v-model="form.receiver" placeholder="姓名" />
            <el-input v-model="form.receiver_phone" placeholder="电话" />
          </div>
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="form.receiver_address" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="承运商">
          <el-input v-model="form.carrier_code" placeholder="如 SF / JD" />
        </el-form-item>
        <el-form-item label="明细">
          <div class="lines">
            <div v-for="(l, i) in form.lines" :key="i" class="line">
              <el-select v-model="l.sku_id" filterable placeholder="商品" style="flex: 1">
                <el-option v-for="s in skus.filter((x) => !form.owner_id || x.owner_id === form.owner_id)"
                           :key="s.id" :label="`${s.code} ${s.name}`" :value="s.id" />
              </el-select>
              <el-input v-model="l.qty" placeholder="数量" style="width: 110px" />
              <el-input-number v-model="l.lot_id" :min="0" placeholder="指定批次" style="width: 130px" />
              <el-button link type="danger" @click="form.lines.splice(i, 1)">删</el-button>
            </div>
            <el-button link type="primary" @click="form.lines.push({ sku_id: null, qty: '', lot_id: null })">
              + 加一行
            </el-button>
            <div class="hint">批次留空即按先到期先出；填了批次就只从这个批次取，不够会整行失败。</div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="drawer = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">创建订单</el-button>
      </template>
    </el-drawer>

    <el-drawer v-model="detailOpen" title="订单详情" size="560px">
      <template v-if="detail">
        <div class="kv"><span>订单号</span><b>{{ detail.code }}</b></div>
        <div class="kv"><span>货主单号</span><b>{{ detail.owner_doc_no }}</b></div>
        <div class="kv"><span>状态</span><b>{{ STATUS[detail.status]?.label || detail.status }}</b></div>
        <div class="kv"><span>理论重量</span><b>{{ detail.weight_theory || '—' }}</b></div>
        <div class="kv"><span>实称重量</span><b>{{ detail.weight_actual || '—' }}</b></div>

        <div class="sub-title">明细</div>
        <el-table :data="detail.lines" size="small" border>
          <el-table-column label="商品" min-width="150">
            <template #default="{ row }">{{ skuLabel(row.sku_id) }}</template>
          </el-table-column>
          <el-table-column prop="qty" label="数量" width="90" align="right" class-name="num" />
          <el-table-column prop="allocated_qty" label="已分配" width="90" align="right" class-name="num" />
          <el-table-column label="指定批次" width="90" align="center">
            <template #default="{ row }">{{ row.lot_id || 'FEFO' }}</template>
          </el-table-column>
        </el-table>

        <div class="sub-title">分配明细（批次 / 库位）</div>
        <el-table :data="detail.allocations" size="small" border>
          <el-table-column prop="lot_id" label="批次" width="80" />
          <el-table-column prop="location_id" label="库位" width="80" />
          <el-table-column prop="qty" label="数量" width="90" align="right" class-name="num" />
          <template #empty>
            <div class="empty-small">尚未分配</div>
          </template>
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
.empty-small { padding: 10px 0; color: #98a4bb; font-size: 12px; }
.lines { display: flex; flex-direction: column; gap: 8px; width: 100%; }
.line { display: flex; align-items: center; gap: 8px; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; width: 100%; }
.hint { font-size: 12px; color: #98a4bb; line-height: 1.6; }
.kv { display: flex; justify-content: space-between; padding: 6px 0; font-size: 13px; color: #1b2740; border-bottom: 1px dashed #eef1f6; }
.kv span { color: #66748f; }
.sub-title { margin: 16px 0 8px; font-size: 13px; font-weight: 600; color: #3a4a68; }
:deep(.num) { font-family: ui-monospace, Menlo, monospace; font-variant-numeric: tabular-nums; }
</style>
