<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  confirmCount,
  createCount,
  getCount,
  listCounts,
  saveCountLines,
} from '@/api/wms_ops'
import { usePagedList } from '@/composables/usePagedList'

const { items, total, page, pageSize, loading, fetch, onPageChange, onSizeChange } =
  usePagedList(listCounts, {})
const drawer = ref(false)
const busy = ref(false)
const detail = ref<any>(null)
const draft = reactive<Record<number, string>>({})
const form = reactive<any>({ owner_id: 1, sku_id: null, note: '' })
const createOpen = ref(false)

const diffOf = (row: any) => {
  const v = draft[row.id]
  return v === undefined || v === '' ? null : (Number(v) - Number(row.qty_book)).toFixed(4)
}

async function openDetail(row: any) {
  detail.value = await getCount(row.id)
  Object.keys(draft).forEach((k) => delete draft[Number(k)])
  detail.value.lines.forEach((x: any) => {
    draft[x.id] = x.qty_actual ?? x.qty_book
  })
  drawer.value = true
}

async function create() {
  busy.value = true
  try {
    const res: any = await createCount({
      owner_id: form.owner_id,
      sku_id: form.sku_id || null,
      note: form.note || null,
    })
    ElMessage.success(`已生成 ${res.code}`)
    createOpen.value = false
    await fetch()
    await openDetail({ id: res.id })
  } catch (e) {
    console.error(e)
  } finally {
    busy.value = false
  }
}

async function save() {
  const lines = detail.value.lines
    .filter((x: any) => !x.adjusted)
    .map((x: any) => ({ line_id: x.id, qty_actual: String(draft[x.id] ?? x.qty_book) }))
  busy.value = true
  try {
    await saveCountLines(detail.value.id, { lines })
    detail.value = await getCount(detail.value.id)
    ElMessage.success('实盘数已保存')
  } catch (e) {
    console.error(e)
  } finally {
    busy.value = false
  }
}

async function confirm() {
  await ElMessageBox.confirm(
    '按差异调整库存并写流水，确认后不能再改实盘数。',
    '确认盘点', { type: 'warning' },
  )
  busy.value = true
  try {
    await confirmCount(detail.value.id)
    ElMessage.success('盘点已确认，差异已过账')
    detail.value = await getCount(detail.value.id)
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    busy.value = false
  }
}

onMounted(fetch)
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <div class="spacer" />
      <el-button v-permission="'wms_internal_ops:count:create'" type="primary" @click="createOpen = true">
        生成盘点单
      </el-button>
    </div>

    <el-table v-loading="loading" :data="items" border stripe height="calc(100vh - 240px)"
              @row-dblclick="openDetail">
      <el-table-column prop="code" label="盘点单号" width="150" />
      <el-table-column prop="owner_id" label="货主" width="100" />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="row.status === 'done' ? 'success' : 'warning'" size="small">
            {{ row.status === 'done' ? '已确认' : '待盘点' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="note" label="备注" min-width="160" />
      <el-table-column label="操作" width="110" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">明细</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty">还没有盘点单。生成时会冻结账面快照，之后账面变化不刷新。</div>
      </template>
    </el-table>

    <el-pagination class="pagination" :current-page="page" :page-size="pageSize" :total="total"
                   :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next"
                   @current-change="onPageChange" @size-change="onSizeChange" />

    <el-dialog v-model="createOpen" title="生成盘点单" width="440px">
      <el-form label-width="90px">
        <el-form-item label="货主"><el-input-number v-model="form.owner_id" :min="1" /></el-form-item>
        <el-form-item label="商品 ID">
          <el-input v-model="form.sku_id" placeholder="留空盘全部商品" />
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="form.note" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createOpen = false">取消</el-button>
        <el-button type="primary" :loading="busy" @click="create">生成</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="drawer" :title="detail ? `盘点 ${detail.code}` : '盘点'" size="720px">
      <template v-if="detail">
        <el-alert v-if="detail.status === 'done'" type="success" :closable="false" show-icon
                  title="已确认，差异已过账，实盘数不可再改" style="margin-bottom: 12px" />
        <el-table :data="detail.lines" size="small" border>
          <el-table-column prop="sku_id" label="商品" width="80" />
          <el-table-column prop="lot_id" label="批次" width="80" />
          <el-table-column prop="location_id" label="库位" width="80" />
          <el-table-column prop="qty_book" label="账面" width="100" align="right" class-name="num" />
          <el-table-column label="实盘" width="130">
            <template #default="{ row }">
              <input v-model="draft[row.id]" class="cell-input" :disabled="row.adjusted || detail.status === 'done'" />
            </template>
          </el-table-column>
          <el-table-column label="差异" width="100" align="right">
            <template #default="{ row }">
              <span :class="['num', Number(diffOf(row)) < 0 ? 'neg' : Number(diffOf(row)) > 0 ? 'pos' : '']">
                {{ diffOf(row) ?? '—' }}
              </span>
            </template>
          </el-table-column>
        </el-table>
        <div class="hint">确认时按「差异」过账，不把实盘数直接写回账面——中间发生的变动会单独留一条流水。</div>
      </template>
      <template #footer>
        <el-button @click="drawer = false">关闭</el-button>
        <el-button v-if="detail?.status !== 'done'" :loading="busy" @click="save">保存实盘</el-button>
        <el-button v-if="detail?.status !== 'done'"
                   v-permission="'wms_internal_ops:count:confirm'" type="primary"
                   :loading="busy" @click="confirm">确认盘点</el-button>
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
.hint { margin-top: 12px; font-size: 12px; color: #98a4bb; line-height: 1.7; }
.cell-input { width: 100%; box-sizing: border-box; padding: 5px 8px; font-size: 13px; border: 1px solid #e8ecf3; border-radius: 5px; outline: none; }
.cell-input:focus { border-color: #10b3a3; }
.cell-input:disabled { background: #f3f6fb; color: #98a4bb; }
:deep(.num) { font-family: ui-monospace, Menlo, monospace; font-variant-numeric: tabular-nums; }
.num.neg { color: #dc2626; }
.num.pos { color: #16a34a; }
</style>
