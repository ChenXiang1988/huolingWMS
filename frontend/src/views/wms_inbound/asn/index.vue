<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listOwners, listSkus } from '@/api/wms_master_data'
import { cancelAsn, closeAsn, confirmAsn, createAsn, getAsn, listAsns } from '@/api/wms_inbound'
import { usePagedList } from '@/composables/usePagedList'

const STATUS: Record<string, { label: string; type: string }> = {
  draft: { label: '草稿', type: 'info' },
  confirmed: { label: '已确认', type: 'primary' },
  receiving: { label: '收货中', type: 'warning' },
  received: { label: '已收完', type: 'success' },
  closed: { label: '已结案', type: 'info' },
  cancelled: { label: '已取消', type: 'danger' },
}

const owners = ref<any[]>([])
const skus = ref<any[]>([])
const { items, total, page, pageSize, loading, query, fetch, search, onPageChange, onSizeChange } =
  usePagedList(listAsns, { owner_id: '', status: '', keyword: '' })

const drawer = ref(false)
const saving = ref(false)
const form = reactive<any>({ owner_id: null, owner_doc_no: '', expect_arrive_at: null, remark: '', lines: [] })

const detailOpen = ref(false)
const detail = ref<any>(null)

const ownerName = (id: number) => owners.value.find((o) => o.id === id)?.name || `#${id}`
const skuName = (id: number) => skus.value.find((s) => s.id === id)?.name || `#${id}`

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
    owner_doc_no: '',
    expect_arrive_at: null,
    remark: '',
    lines: [{ sku_id: null, expect_qty: '' }],
  })
  drawer.value = true
}

function addLine() {
  form.lines.push({ sku_id: null, expect_qty: '' })
}

function removeLine(i: number) {
  form.lines.splice(i, 1)
}

async function submit() {
  if (!form.owner_id || !form.owner_doc_no.trim()) {
    ElMessage.warning('货主与货主单号必填')
    return
  }
  const lines = form.lines.filter((l: any) => l.sku_id && Number(l.expect_qty) > 0)
  if (!lines.length) {
    ElMessage.warning('至少一行有效明细')
    return
  }
  saving.value = true
  try {
    const res: any = await createAsn({ ...form, lines, confirm: true })
    ElMessage.success(`已建预报 ${res.code}`)
    drawer.value = false
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    saving.value = false
  }
}

async function openDetail(row: any) {
  detail.value = await getAsn(row.id)
  detailOpen.value = true
}

async function act(row: any, kind: 'confirm' | 'cancel' | 'close') {
  const text = {
    confirm: '确认这张预报？确认后可以开收货单。',
    cancel: '取消后这张预报作废，不能恢复。',
    close: '结案会把未收的差额定性为放弃，之后不再接受新收货。',
  }[kind]
  await ElMessageBox.confirm(text, '确认', { type: 'warning' })
  if (kind === 'confirm') await confirmAsn(row.id)
  if (kind === 'cancel') await cancelAsn(row.id)
  if (kind === 'close') await closeAsn(row.id)
  ElMessage.success('已处理')
  await fetch()
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
      <el-input v-model="query.keyword" placeholder="预报号 / 货主单号" clearable style="width: 220px"
                @keyup.enter="search" @clear="search" />
      <el-button @click="search">查询</el-button>
      <div class="spacer" />
      <el-button v-permission="'wms_inbound:asn:create'" type="primary" @click="openCreate">
        新建预报
      </el-button>
    </div>

    <el-table v-loading="loading" :data="items" border stripe height="calc(100vh - 260px)">
      <el-table-column prop="code" label="预报号" width="140" fixed />
      <el-table-column prop="owner_doc_no" label="货主单号" width="160" />
      <el-table-column label="货主" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">{{ ownerName(row.owner_id) }}</template>
      </el-table-column>
      <el-table-column label="预计到货" width="170">
        <template #default="{ row }">{{ (row.expect_arrive_at || '').replace('T', ' ').slice(0, 16) || '—' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="STATUS[row.status]?.type as any" size="small">
            {{ STATUS[row.status]?.label || row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button v-if="row.status === 'draft'" v-permission="'wms_inbound:asn:edit'"
                     link type="primary" @click="act(row, 'confirm')">确认</el-button>
          <el-button v-if="['confirmed', 'receiving'].includes(row.status)"
                     v-permission="'wms_inbound:asn:close'" link type="warning"
                     @click="act(row, 'close')">结案</el-button>
          <el-button v-if="['draft', 'confirmed'].includes(row.status)"
                     v-permission="'wms_inbound:asn:edit'" link type="danger"
                     @click="act(row, 'cancel')">取消</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty">还没有入库预报。货主推送或手工建一张，到货才能开收货单。</div>
      </template>
    </el-table>

    <el-pagination class="pagination" :current-page="page" :page-size="pageSize" :total="total"
                   :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next"
                   @current-change="onPageChange" @size-change="onSizeChange" />

    <el-drawer v-model="drawer" title="新建入库预报" size="640px">
      <el-form label-width="94px">
        <el-form-item label="货主" required>
          <el-select v-model="form.owner_id" style="width: 100%">
            <el-option v-for="o in owners" :key="o.id" :label="`${o.code} ${o.name}`" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="货主单号" required>
          <el-input v-model="form.owner_doc_no" placeholder="货主侧单号，用于去重" />
        </el-form-item>
        <el-form-item label="预计到货">
          <el-date-picker v-model="form.expect_arrive_at" type="datetime" style="width: 100%"
                          value-format="YYYY-MM-DDTHH:mm:ss" placeholder="选填" />
        </el-form-item>
        <el-form-item label="明细">
          <div class="lines">
            <div v-for="(l, i) in form.lines" :key="i" class="line">
              <el-select v-model="l.sku_id" filterable placeholder="商品" style="flex: 1">
                <el-option v-for="s in skus.filter((x) => !form.owner_id || x.owner_id === form.owner_id)"
                           :key="s.id" :label="`${s.code} ${s.name}`" :value="s.id" />
              </el-select>
              <el-input v-model="l.expect_qty" placeholder="应收数量" style="width: 130px" />
              <el-button link type="danger" @click="removeLine(i)">删除</el-button>
            </div>
            <el-button link type="primary" @click="addLine">+ 加一行</el-button>
          </div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="drawer = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">创建并确认</el-button>
      </template>
    </el-drawer>

    <el-drawer v-model="detailOpen" title="预报详情" size="560px">
      <template v-if="detail">
        <div class="kv"><span>预报号</span><b>{{ detail.code }}</b></div>
        <div class="kv"><span>货主单号</span><b>{{ detail.owner_doc_no }}</b></div>
        <div class="kv"><span>状态</span><b>{{ STATUS[detail.status]?.label || detail.status }}</b></div>
        <div class="kv"><span>已开收货单</span><b>{{ detail.receipts?.length || 0 }} 张</b></div>
        <div class="sub-title">明细</div>
        <el-table :data="detail.lines" size="small" border>
          <el-table-column label="商品" min-width="160">
            <template #default="{ row }">{{ skuName(row.sku_id) }}</template>
          </el-table-column>
          <el-table-column prop="expect_qty" label="应收" width="110" align="right" class-name="num" />
        </el-table>
        <div v-if="detail.receipts?.length" class="sub-title">收货单</div>
        <div v-for="r in detail.receipts" :key="r.id" class="receipt-row">
          <span class="mono">{{ r.code }}</span>
          <el-tag size="small" effect="plain">{{ r.status }}</el-tag>
        </div>
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
.kv { display: flex; justify-content: space-between; padding: 6px 0; font-size: 13px; color: #1b2740; border-bottom: 1px dashed #eef1f6; }
.kv span { color: #66748f; }
.sub-title { margin: 16px 0 8px; font-size: 13px; font-weight: 600; color: #3a4a68; }
.receipt-row { display: flex; align-items: center; justify-content: space-between; padding: 6px 0; }
.mono { font-family: ui-monospace, Menlo, monospace; font-size: 12px; }
:deep(.num) { font-family: ui-monospace, Menlo, monospace; font-variant-numeric: tabular-nums; }
</style>
