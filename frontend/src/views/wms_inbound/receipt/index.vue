<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listSkus } from '@/api/wms_master_data'
import {
  confirmReceipt,
  getReceipt,
  listReceipts,
  openReceipt,
  saveReceiptLines,
  scanReceiptBarcode,
} from '@/api/wms_inbound'
import { usePagedList } from '@/composables/usePagedList'

const STATUS: Record<string, { label: string; type: string }> = {
  open: { label: '录入中', type: 'warning' },
  checked: { label: '已收货', type: 'primary' },
  putaway_done: { label: '已上架', type: 'success' },
  cancelled: { label: '已取消', type: 'danger' },
}

const skus = ref<any[]>([])
const { items, total, page, pageSize, loading, query, fetch, search, onPageChange, onSizeChange } =
  usePagedList(listReceipts, { asn_id: '', status: '' })

const drawer = ref(false)
const saving = ref(false)
const receipt = ref<any>(null)
const openAsnId = ref<number | null>(null)
const scanCode = ref('')
const scanHit = ref<number | null>(null)
const scanMsg = ref('')
const scanInput = ref<any>(null)

const skuOf = (id: number) => skus.value.find((s) => s.id === id)
const skuLabel = (id: number) => {
  const s = skuOf(id)
  return s ? `${s.code} ${s.name}` : `#${id}`
}
const lotRequired = (id: number) => !!skuOf(id)?.lot_required

const canEdit = computed(() => receipt.value?.status === 'open')

async function openFromAsn() {
  if (!openAsnId.value) {
    ElMessage.warning('先填预报 ID')
    return
  }
  try {
    const res: any = await openReceipt(openAsnId.value)
    ElMessage.success(`已开收货单 ${res.code}`)
    await fetch()
    await openDetail({ id: res.id })
  } catch (e) {
    console.error(e)
  }
}

async function openDetail(row: any) {
  const data: any = await getReceipt(row.id)
  // 批次录入需要就地编辑，先把结构备好
  data.lines.forEach((ln: any) => {
    if (!ln.lots.length) ln.lots = []
    ln.lots.forEach((l: any) => {
      l.expiry_date = l.expiry_date || ''
    })
  })
  receipt.value = data
  scanCode.value = ''
  scanHit.value = null
  scanMsg.value = ''
  drawer.value = true
  await nextTick()
  scanInput.value?.focus()
}

function addLot(line: any) {
  line.lots.push({ lot_code: '', expiry_date: '', received_qty: '', damaged_qty: '0' })
}

function removeLot(line: any, i: number) {
  line.lots.splice(i, 1)
}

function lotSum(line: any) {
  return line.lots.reduce((s: number, l: any) => s + Number(l.received_qty || 0), 0)
}

async function save() {
  const lines = receipt.value.lines.map((ln: any) => ({
    sku_id: ln.sku_id,
    received_qty: String(ln.received_qty || 0),
    damaged_qty: String(ln.damaged_qty || 0),
    lots: ln.lots
      .filter((l: any) => l.lot_code)
      .map((l: any) => ({
        lot_code: l.lot_code,
        expiry_date: l.expiry_date || null,
        received_qty: String(l.received_qty || 0),
        damaged_qty: String(l.damaged_qty || 0),
      })),
  }))
  saving.value = true
  try {
    await saveReceiptLines(receipt.value.id, { lines })
    ElMessage.success('已保存')
  } catch (e) {
    console.error(e)
  } finally {
    saving.value = false
  }
}

async function confirm() {
  await ElMessageBox.confirm(
    '确认收货后好货入可发、破损入破损，并生成上架任务。确认前请先保存。',
    '确认收货',
    { type: 'warning' },
  )
  saving.value = true
  try {
    const res: any = await confirmReceipt(receipt.value.id)
    ElMessage.success(`已收货，上架单 #${res.putaway_id}`)
    drawer.value = false
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    saving.value = false
  }
}

async function scan() {
  const code = scanCode.value.trim()
  scanCode.value = ''
  scanHit.value = null
  scanMsg.value = ''
  if (!code || !receipt.value) return
  try {
    const res: any = await scanReceiptBarcode(receipt.value.id, code)
    const line = receipt.value.lines.find((ln: any) => ln.sku_id === res.sku_id)
    scanHit.value = line ? line.id : null
    scanMsg.value = line
      ? `已定位 ${res.code} ${res.name}`
      : `${res.code} ${res.name} 已建档，但不在这张收货单上`
  } catch (e) {
    console.error(e)
  } finally {
    await nextTick()
    scanInput.value?.focus()
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
        <el-option v-for="(v, k) in STATUS" :key="k" :label="v.label" :value="k" />
      </el-select>
      <el-button @click="search">查询</el-button>
      <div class="spacer" />
      <el-input-number v-model="openAsnId" :min="1" placeholder="预报 ID" style="width: 150px" />
      <el-button v-permission="'wms_inbound:receipt:create'" type="primary" @click="openFromAsn">
        按预报开收货单
      </el-button>
    </div>

    <el-table v-loading="loading" :data="items" border stripe height="calc(100vh - 260px)">
      <el-table-column prop="code" label="收货单号" width="150" fixed />
      <el-table-column prop="asn_id" label="预报 ID" width="110" />
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="STATUS[row.status]?.type as any" size="small">
            {{ STATUS[row.status]?.label || row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="收货时间" width="180">
        <template #default="{ row }">{{ (row.received_at || '').replace('T', ' ').slice(0, 19) || '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="110" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">录入</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty">还没有收货单。按预报开一张，然后录入实收与批次。</div>
      </template>
    </el-table>

    <el-pagination class="pagination" :current-page="page" :page-size="pageSize" :total="total"
                   :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next"
                   @current-change="onPageChange" @size-change="onSizeChange" />

    <el-drawer v-model="drawer" :title="receipt ? `收货 ${receipt.code}` : '收货'" size="720px">
      <template v-if="receipt">
        <el-alert v-if="!canEdit" type="info" :closable="false" show-icon
                  title="这张单已收货，只能查看" style="margin-bottom: 12px" />

        <div class="scan-bar">
          <input ref="scanInput" v-model="scanCode" :disabled="!canEdit"
                 placeholder="扫商品条码定位明细行" @keyup.enter="scan" />
          <el-button :disabled="!canEdit" @click="scan">扫码</el-button>
        </div>
        <div v-if="scanMsg" class="scan-msg">{{ scanMsg }}</div>

        <div v-for="ln in receipt.lines" :key="ln.id" class="line-card"
             :class="{ hit: scanHit === ln.id }">
          <div class="line-head">
            <span class="name">{{ skuLabel(ln.sku_id) }}</span>
            <span class="expect">应收 {{ ln.expect_qty }}</span>
          </div>

          <div class="grid">
            <div class="field">
              <label>实收</label>
              <input v-model="ln.received_qty" :disabled="!canEdit" />
            </div>
            <div class="field">
              <label>破损</label>
              <input v-model="ln.damaged_qty" :disabled="!canEdit" />
            </div>
          </div>

          <template v-if="lotRequired(ln.sku_id)">
            <div class="lots-head">
              <span>批次（合计 {{ lotSum(ln) }} / 实收 {{ ln.received_qty || 0 }}）</span>
              <el-button v-if="canEdit" link type="primary" @click="addLot(ln)">+ 加批次</el-button>
            </div>
            <el-table :data="ln.lots" size="small" border>
              <el-table-column label="批号" min-width="130">
                <template #default="{ row }">
                  <el-input v-model="row.lot_code" :disabled="!canEdit" placeholder="如 L2026-01" />
                </template>
              </el-table-column>
              <el-table-column label="到期日" width="150">
                <template #default="{ row }">
                  <el-date-picker v-model="row.expiry_date" type="date" value-format="YYYY-MM-DD"
                                  :disabled="!canEdit" style="width: 100%" />
                </template>
              </el-table-column>
              <el-table-column label="数量" width="110">
                <template #default="{ row }">
                  <el-input v-model="row.received_qty" :disabled="!canEdit" />
                </template>
              </el-table-column>
              <el-table-column label="破损" width="100">
                <template #default="{ row }">
                  <el-input v-model="row.damaged_qty" :disabled="!canEdit" />
                </template>
              </el-table-column>
              <el-table-column v-if="canEdit" label="" width="60">
                <template #default="{ $index }">
                  <el-button link type="danger" @click="removeLot(ln, $index)">删</el-button>
                </template>
              </el-table-column>
              <template #empty>
                <div class="empty-small">这个商品启用批次管理，至少要录一个批次</div>
              </template>
            </el-table>
          </template>
        </div>
      </template>

      <template #footer>
        <el-button @click="drawer = false">关闭</el-button>
        <el-button v-if="canEdit" :loading="saving" @click="save">保存</el-button>
        <el-button v-if="canEdit" v-permission="'wms_inbound:receipt:confirm'"
                   type="primary" :loading="saving" @click="confirm">确认收货</el-button>
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
.line-card { padding: 12px 14px; border: 1px solid #eef1f6; border-radius: 8px; margin-bottom: 12px; background: #fbfcfe; }
.line-card.hit { border-color: #10b3a3; box-shadow: 0 0 0 2px rgba(16, 179, 163, 0.18); }
.line-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px; }
.name { font-size: 13px; font-weight: 600; color: #1b2740; }
.expect { font-size: 12px; color: #66748f; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 10px; }
.field label { display: block; font-size: 12px; color: #66748f; margin-bottom: 4px; }
.field input { width: 100%; box-sizing: border-box; padding: 7px 10px; font-size: 13px; color: #1b2740; background: #fff; border: 1px solid #e8ecf3; border-radius: 6px; outline: none; }
.field input:focus { border-color: #10b3a3; box-shadow: 0 0 0 3px rgba(16, 179, 163, 0.12); }
.field input:disabled { background: #f3f6fb; color: #98a4bb; }
.lots-head { display: flex; justify-content: space-between; align-items: center; margin: 6px 0; font-size: 12px; color: #66748f; }
.scan-bar { display: flex; gap: 8px; margin-bottom: 8px; }
.scan-bar input { flex: 1; padding: 8px 10px; font-size: 13px; color: #1b2740; background: #fff; border: 1px solid #b9e5df; border-radius: 6px; outline: none; }
.scan-bar input:focus { border-color: #10b3a3; box-shadow: 0 0 0 3px rgba(16, 179, 163, 0.12); }
.scan-bar input:disabled { background: #f3f6fb; color: #98a4bb; }
.scan-msg { margin-bottom: 10px; padding: 7px 10px; font-size: 12px; color: #0e8c80; background: #f0faf8; border-radius: 6px; }
</style>
