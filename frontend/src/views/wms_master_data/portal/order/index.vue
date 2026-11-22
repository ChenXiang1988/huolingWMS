<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  portalContext,
  portalCreateOrder,
  portalOrderDetail,
  portalOrders,
  portalSkus,
} from '@/api/wms_portal'

const ctx = ref<any>(null)
const skus = ref<any[]>([])
const busy = ref(false)
const done = ref<any>(null)

const orders = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)
const keyword = ref('')
const detail = ref<any>(null)
const detailVisible = ref(false)

/** 货主只关心「走到哪一步」，内部状态码不外露。 */
const STATUS_TEXT: Record<string, string> = {
  draft: '草稿',
  confirmed: '待分配',
  allocated: '已分配',
  picking: '拣货中',
  checked: '待发运',
  shipped: '已发运',
  cancelled: '已取消',
}
const STATUS_TAG: Record<string, any> = {
  draft: 'info',
  confirmed: 'info',
  allocated: 'warning',
  picking: 'primary',
  checked: 'warning',
  shipped: 'success',
  cancelled: 'danger',
}

async function fetchOrders() {
  loading.value = true
  try {
    const res: any = await portalOrders({
      page: page.value,
      page_size: pageSize,
      keyword: keyword.value || undefined,
    })
    orders.value = res.items || []
    total.value = res.total || 0
  } finally {
    loading.value = false
  }
}

async function openDetail(row: any) {
  detail.value = await portalOrderDetail(row.id)
  detailVisible.value = true
}

function onPageChange(p: number) {
  page.value = p
  fetchOrders()
}
const form = reactive<any>({
  owner_doc_no: '', order_type: 'C',
  receiver: '', receiver_phone: '', receiver_address: '', carrier_code: '',
  lines: [{ sku_id: null, qty: '', lot_id: null }],
})

const skuOf = (id: number) => skus.value.find((s) => s.id === id)

function addLine() {
  form.lines.push({ sku_id: null, qty: '', lot_id: null })
}

function removeLine(i: number) {
  form.lines.splice(i, 1)
}

async function submit() {
  if (!form.owner_doc_no.trim()) {
    ElMessage.warning('请填货主单号')
    return
  }
  const lines = form.lines
    .filter((l: any) => l.sku_id && Number(l.qty) > 0)
    .map((l: any) => ({ sku_id: l.sku_id, qty: String(l.qty), lot_id: l.lot_id || null }))
  if (!lines.length) {
    ElMessage.warning('至少一行有效明细')
    return
  }
  busy.value = true
  try {
    const res: any = await portalCreateOrder({
      owner_doc_no: form.owner_doc_no,
      order_type: form.order_type,
      receiver: form.receiver || null,
      receiver_phone: form.receiver_phone || null,
      receiver_address: form.receiver_address || null,
      carrier_code: form.carrier_code || null,
      lines,
    })
    done.value = res
    ElMessage.success(`订单 ${res.code} 已提交`)
    form.owner_doc_no = ''
    form.lines = [{ sku_id: null, qty: '', lot_id: null }]
    page.value = 1
    await fetchOrders()
  } catch (e) {
    console.error(e)
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  ctx.value = await portalContext()
  skus.value = (await portalSkus()) as any
  await fetchOrders()
})
</script>

<template>
  <div class="wrap">
    <div class="head">
      <h2>我的出库订单</h2>
      <p v-if="ctx">当前货主：<b>{{ ctx.owner_name }}</b>（#{{ ctx.owner_id }}）</p>
    </div>

    <div class="toolbar">
      <el-input v-model="keyword" placeholder="按仓库单号或货主单号搜索" clearable
                style="width: 260px" @keyup.enter="page = 1; fetchOrders()" />
      <el-button @click="page = 1; fetchOrders()">查询</el-button>
      <span class="hint">点任意一行看明细</span>
    </div>

    <el-table :data="orders" v-loading="loading" border size="small"
              style="cursor: pointer" @row-click="openDetail">
      <el-table-column prop="code" label="仓库单号" width="110" />
      <el-table-column prop="owner_doc_no" label="货主单号" min-width="150" show-overflow-tooltip />
      <el-table-column label="类型" width="80">
        <template #default="{ row }">{{ row.order_type === 'B' ? 'B 端' : 'C 端' }}</template>
      </el-table-column>
      <el-table-column label="件数" width="80">
        <template #default="{ row }">{{ Number(row.qty_total) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="STATUS_TAG[row.status] || 'info'">
            {{ STATUS_TEXT[row.status] || row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="receiver" label="收件人" width="110" show-overflow-tooltip />
      <el-table-column label="下单时间" width="150">
        <template #default="{ row }">
          {{ (row.created_at || '').replace('T', ' ').slice(0, 16) }}
        </template>
      </el-table-column>
      <template #empty>
        <span class="hint">还没有订单，下面填一张试试</span>
      </template>
    </el-table>

    <div class="pager">
      <el-pagination layout="prev, pager, next, total" :total="total"
                     :page-size="pageSize" :current-page="page"
                     @current-change="onPageChange" />
    </div>

    <div class="head" style="margin-top: 28px">
      <h2>新建出库订单</h2>
    </div>

    <el-alert v-if="ctx && !ctx.can_create" type="warning" :closable="false" show-icon
              title="该货主已接入上游 ERP，订单由系统同步下发，门户不再建单"
              description="已有订单照常发货，不受影响。"
              style="margin-bottom: 16px" />

    <el-alert v-if="done" type="success" :closable="false" show-icon
              :title="`订单 ${done.code} 已提交，仓库按先到期先出分配`"
              style="margin-bottom: 16px" />

    <el-form label-width="100px" :disabled="!ctx?.can_create">
      <el-form-item label="货主单号" required>
        <el-input v-model="form.owner_doc_no" placeholder="你自己系统里的单号，用于去重" />
      </el-form-item>
      <el-form-item label="订单类型">
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
      <el-form-item label="收货地址">
        <el-input v-model="form.receiver_address" type="textarea" :rows="2" />
      </el-form-item>
      <el-form-item label="承运商">
        <el-input v-model="form.carrier_code" placeholder="如 SF / JD" />
      </el-form-item>
      <el-form-item label="商品明细">
        <div class="lines">
          <div v-for="(l, i) in form.lines" :key="i" class="line">
            <el-select v-model="l.sku_id" filterable placeholder="选择商品" style="flex: 1">
              <el-option v-for="s in skus" :key="s.id"
                         :label="`${s.owner_sku_code} ${s.name}`" :value="s.id" />
            </el-select>
            <el-input v-model="l.qty" placeholder="数量" style="width: 110px" />
            <el-input v-model="l.lot_id" placeholder="批次 ID" style="width: 110px" />
            <el-button link type="danger" @click="removeLine(i)">删除</el-button>
          </div>
          <el-button link type="primary" @click="addLine">+ 加一行</el-button>
          <div class="hint-line">
            批次留空即按先到期先出；填了批次就只从这个批次取，不够会整行失败。<template v-if="form.lines.some((l: any) => skuOf(l.sku_id)?.lot_required)">
              当前有商品启用批次管理，请填批次 ID。
            </template>
          </div>
        </div>
      </el-form-item>
    </el-form>

    <div class="foot">
      <button class="primary" :disabled="!ctx?.can_create || busy" @click="submit">
        {{ busy ? '提交中…' : '提交订单' }}
      </button>
      <span class="hint">分配只锁定量，发运时才真正扣减库存。</span>
    </div>
  </div>

  <el-drawer v-model="detailVisible" title="订单详情" size="520px">
    <template v-if="detail">
      <div class="d-head">
        <div>
          <div class="d-code">{{ detail.code }}</div>
          <div class="hint">货主单号 {{ detail.owner_doc_no }}</div>
        </div>
        <el-tag :type="STATUS_TAG[detail.status] || 'info'">
          {{ STATUS_TEXT[detail.status] || detail.status }}
        </el-tag>
      </div>

      <el-descriptions :column="1" border size="small" style="margin: 16px 0">
        <el-descriptions-item label="订单类型">
          {{ detail.order_type === 'B' ? 'B 端大货' : 'C 端电商' }}
        </el-descriptions-item>
        <el-descriptions-item label="收件人">
          {{ detail.receiver || '—' }} {{ detail.receiver_phone || '' }}
        </el-descriptions-item>
        <el-descriptions-item label="收货地址">{{ detail.receiver_address || '—' }}</el-descriptions-item>
        <el-descriptions-item label="承运商 / 运单号">
          {{ detail.carrier_code || '—' }} / {{ detail.tracking_no || '未出单' }}
        </el-descriptions-item>
        <el-descriptions-item label="下单时间">
          {{ (detail.created_at || '').replace('T', ' ').slice(0, 16) }}
        </el-descriptions-item>
        <el-descriptions-item label="发运时间">
          {{ detail.shipped_at ? detail.shipped_at.replace('T', ' ').slice(0, 16) : '—' }}
        </el-descriptions-item>
      </el-descriptions>

      <el-table :data="detail.lines" border size="small">
        <el-table-column label="商品" min-width="160">
          <template #default="{ row }">
            {{ row.owner_sku_code }} {{ row.sku_name }}
          </template>
        </el-table-column>
        <el-table-column label="数量" width="80">
          <template #default="{ row }">{{ Number(row.qty) }}</template>
        </el-table-column>
        <el-table-column label="已分配" width="90">
          <template #default="{ row }">{{ Number(row.allocated_qty) }}</template>
        </el-table-column>
        <el-table-column label="批次" width="80">
          <template #default="{ row }">{{ row.lot_id ? row.lot_id : '默认' }}</template>
        </el-table-column>
      </el-table>
    </template>
  </el-drawer>
</template>

<style scoped>
.wrap { max-width: 960px; }
.head h2 { margin: 0 0 6px; font-size: 18px; font-weight: 600; color: #1b2740; }
.head p { margin: 0 0 20px; font-size: 13px; color: #66748f; }
.toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.pager { display: flex; justify-content: flex-end; margin-top: 12px; }
.d-head { display: flex; align-items: center; justify-content: space-between; }
.d-code { font-size: 16px; font-weight: 600; color: #1b2740; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; width: 100%; }
.lines { display: flex; flex-direction: column; gap: 8px; width: 100%; }
.line { display: flex; align-items: center; gap: 8px; }
.hint-line { font-size: 12px; line-height: 1.7; color: #98a4bb; }
.foot { display: flex; align-items: center; gap: 12px; margin-top: 12px; }
button.primary { padding: 9px 20px; font-size: 13px; color: #fff; background: #10b3a3; border: none; border-radius: 7px; cursor: pointer; }
button.primary:hover { background: #0e8c80; }
button.primary:disabled { background: #98a4bb; cursor: not-allowed; }
.hint { font-size: 12px; color: #98a4bb; }
</style>
