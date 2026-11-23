<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AppFormDrawer from '@/components/AppFormDrawer.vue'
import {
  portalAsns,
  portalAsnDetail,
  portalContext,
  portalCreateAsn,
  portalSkus,
} from '@/api/wms_portal'

const ctx = ref<any>(null)
const skus = ref<any[]>([])
const busy = ref(false)
const createVisible = ref(false)
const detailVisible = ref(false)
const detail = ref<any>(null)

const asns = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)
const detailSections = [
  { key: 'info', label: '预报信息' },
  { key: 'lines', label: '商品明细' },
]

const STATUS_TEXT: Record<string, string> = {
  draft: '草稿', confirmed: '已确认', receiving: '收货中', received: '已收货', cancelled: '已取消',
}

const form = reactive<any>({
  owner_doc_no: '',
  expect_arrive_at: null,
  remark: '',
  lines: [{ sku_id: null, expect_qty: '' }],
})

function resetForm() {
  form.owner_doc_no = ''
  form.expect_arrive_at = null
  form.remark = ''
  form.lines = [{ sku_id: null, expect_qty: '' }]
}

function openCreate() {
  resetForm()
  createVisible.value = true
}

function addLine() { form.lines.push({ sku_id: null, expect_qty: '' }) }
function removeLine(i: number) { form.lines.splice(i, 1) }

async function load() {
  loading.value = true
  try {
    const res: any = await portalAsns({ page: page.value, page_size: pageSize })
    asns.value = res.items || []
    total.value = res.total || 0
  } finally {
    loading.value = false
  }
}

async function openDetail(row: any) {
  detail.value = await portalAsnDetail(row.id)
  detailVisible.value = true
}

async function submit() {
  if (!form.owner_doc_no.trim()) {
    ElMessage.warning('请填货主单号')
    return
  }
  const lines = form.lines.filter((l: any) => l.sku_id && Number(l.expect_qty) > 0)
  if (!lines.length) {
    ElMessage.warning('至少一行有效明细')
    return
  }
  busy.value = true
  try {
    const res: any = await portalCreateAsn({
      owner_doc_no: form.owner_doc_no,
      expect_arrive_at: form.expect_arrive_at || null,
      remark: form.remark || null,
      lines,
    })
    createVisible.value = false
    ElMessage.success(`预报 ${res.code} 已提交`)
    page.value = 1
    await load()
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  ctx.value = await portalContext()
  skus.value = (await portalSkus()) as any
  await load()
})
</script>

<template>
  <div class="wrap">
    <div class="head">
      <h2>我的入库预报</h2>
      <p v-if="ctx">当前货主：<b>{{ ctx.owner_name }}</b>（#{{ ctx.owner_id }}）</p>
    </div>

    <div class="toolbar">
      <el-button v-if="ctx?.can_create" type="primary" @click="openCreate">新建预报</el-button>
      <span class="hint">点任意一行看明细</span>
    </div>

    <el-alert v-if="ctx && !ctx.can_create" type="warning" :closable="false" show-icon
              title="该货主已接入上游 ERP，预报由系统同步下发，门户不再建单"
              description="已有单据照常查询与推进，不受影响。如需临时建单请联系仓库。"
              style="margin-bottom: 16px" />

    <el-table :data="asns" v-loading="loading" border size="small"
              style="cursor: pointer" @row-click="openDetail">
      <el-table-column prop="code" label="仓库单号" width="130" />
      <el-table-column prop="owner_doc_no" label="货主单号" min-width="150" show-overflow-tooltip />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="row.status === 'received' ? 'success' : 'info'">
            {{ STATUS_TEXT[row.status] || row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="预计到货" width="150">
        <template #default="{ row }">{{ (row.expect_arrive_at || '').replace('T', ' ').slice(0, 16) || '—' }}</template>
      </el-table-column>
      <el-table-column label="提交时间" width="150">
        <template #default="{ row }">{{ (row.created_at || '').replace('T', ' ').slice(0, 16) }}</template>
      </el-table-column>
      <template #empty><span class="hint">还没有预报，点「新建预报」提交一张</span></template>
    </el-table>

    <div class="pager">
      <el-pagination layout="prev, pager, next, total" :total="total"
                     :page-size="pageSize" :current-page="page"
                     @current-change="(p: number) => { page = p; load() }" />
    </div>

    <AppFormDrawer
      v-model="createVisible"
      title="新建入库预报"
      subtitle="提交后仓库据此开收货单；分批到货可挂多张收货单"
      width="720px"
    >
      <template #content>
        <el-form label-width="100px">
          <el-form-item label="货主单号" required>
            <el-input v-model="form.owner_doc_no" placeholder="你自己系统里的单号，用于去重" />
          </el-form-item>
          <el-form-item label="预计到货">
            <el-date-picker v-model="form.expect_arrive_at" type="datetime"
                            value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" />
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="form.remark" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="商品明细">
            <div class="lines">
              <div v-for="(l, i) in form.lines" :key="i" class="line">
                <el-select v-model="l.sku_id" filterable placeholder="选择商品" style="flex: 1">
                  <el-option v-for="s in skus" :key="s.id"
                             :label="`${s.owner_sku_code} ${s.name}`" :value="s.id" />
                </el-select>
                <el-input v-model="l.expect_qty" placeholder="应收数量" style="width: 120px" />
                <el-button link type="danger" @click="removeLine(i)">删除</el-button>
              </div>
              <el-button link type="primary" @click="addLine">+ 加一行</el-button>
            </div>
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="busy" @click="submit">提交预报</el-button>
      </template>
    </AppFormDrawer>

    <AppFormDrawer
      v-model="detailVisible"
      title="预报详情"
      :subtitle="detail ? `货主单号 ${detail.owner_doc_no}` : ''"
      :status="detail ? (STATUS_TEXT[detail.status] || detail.status) : ''"
      :sections="detailSections"
      width="680px"
    >
      <template #section-info>
        <el-descriptions v-if="detail" :column="2" border size="small">
          <el-descriptions-item label="仓库单号">{{ detail.code }}</el-descriptions-item>
          <el-descriptions-item label="来源">{{ detail.source === 'portal' ? '货主门户' : detail.source }}</el-descriptions-item>
          <el-descriptions-item label="预计到货">{{ (detail.expect_arrive_at || '—').replace('T', ' ').slice(0, 16) }}</el-descriptions-item>
          <el-descriptions-item label="提交时间">{{ (detail.created_at || '').replace('T', ' ').slice(0, 16) }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">{{ detail.remark || '—' }}</el-descriptions-item>
        </el-descriptions>
      </template>
      <template #section-lines>
        <el-table v-if="detail" :data="detail.lines" border size="small">
          <el-table-column label="商品 ID" prop="sku_id" width="100" />
          <el-table-column label="预报数量" prop="expect_qty" width="120" />
        </el-table>
      </template>
      <template #footer><el-button @click="detailVisible = false">关闭</el-button></template>
    </AppFormDrawer>
  </div>
</template>

<style scoped>
.wrap { max-width: 960px; }
.head h2 { margin: 0 0 6px; font-size: 18px; font-weight: 600; color: #1b2740; }
.head p { margin: 0 0 20px; font-size: 13px; color: #66748f; }
.toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.pager { display: flex; justify-content: flex-end; margin-top: 12px; }
.lines { display: flex; flex-direction: column; gap: 8px; width: 100%; }
.line { display: flex; align-items: center; gap: 8px; }
.hint { font-size: 12px; color: #98a4bb; }
</style>
