<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listOwners } from '@/api/wms_master_data'
import { getOrder, listOrders, recordCheck, shipOrder } from '@/api/wms_outbound'
import { usePagedList } from '@/composables/usePagedList'

const owners = ref<any[]>([])
const { items, total, page, pageSize, loading, query, fetch, search, onPageChange, onSizeChange } =
  usePagedList(listOrders, { owner_id: '', status: 'checked' })

const drawer = ref(false)
const busy = ref(false)
const order = ref<any>(null)
const form = reactive({ weight_actual: '', tolerance: '' })
const result = ref<any>(null)

const ownerName = (id: number) => owners.value.find((o) => o.id === id)?.name || `#${id}`

async function openDetail(row: any) {
  order.value = await getOrder(row.id)
  form.weight_actual = order.value.weight_actual || ''
  form.tolerance = ''
  result.value = null
  drawer.value = true
}

/** 先把实称记下来，再决定能不能发运——复核员不能因为超差就发不出去，
 *  他还可以重新称一次。 */
async function doCheck() {
  if (!Number(form.weight_actual)) {
    ElMessage.warning('请填实称重量')
    return
  }
  busy.value = true
  try {
    const payload: any = { weight_actual: String(form.weight_actual) }
    if (form.tolerance) payload.tolerance = String(form.tolerance)
    result.value = await recordCheck(order.value.id, payload)
    ElMessage.success(result.value.passed ? '称重通过' : '超出偏差，已拦下')
    order.value = await getOrder(order.value.id)
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    busy.value = false
  }
}

async function doShip() {
  await ElMessageBox.confirm('发运后库存立即扣减，且不可撤销。确认发运？', '发运', { type: 'warning' })
  busy.value = true
  try {
    const res: any = await shipOrder(order.value.id, { tracking_no: null })
    ElMessage.success(`已发运 ${res.code}`)
    drawer.value = false
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    busy.value = false
  }
}

const deviationText = () => {
  const d = result.value?.deviation
  if (d === null || d === undefined) return '—'
  return (Number(d) * 100).toFixed(2) + '%'
}

onMounted(async () => {
  const o: any = await listOwners({ page: 1, page_size: 200 })
  owners.value = o?.items || []
  await fetch()
})
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="query.owner_id" placeholder="货主" clearable style="width: 170px" @change="search">
        <el-option v-for="o in owners" :key="o.id" :label="`${o.code} ${o.name}`" :value="o.id" />
      </el-select>
      <el-select v-model="query.status" placeholder="状态" clearable style="width: 140px" @change="search">
        <el-option label="已分配" value="allocated" />
        <el-option label="拣货中" value="picking" />
        <el-option label="已复核" value="checked" />
        <el-option label="已发运" value="shipped" />
      </el-select>
      <el-button @click="search">查询</el-button>
    </div>

    <el-table v-loading="loading" :data="items" border stripe height="calc(100vh - 240px)">
      <el-table-column prop="code" label="订单号" width="140" fixed />
      <el-table-column label="货主" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">{{ ownerName(row.owner_id) }}</template>
      </el-table-column>
      <el-table-column prop="receiver" label="收件人" width="120" />
      <el-table-column label="理论 / 实称" width="160">
        <template #default="{ row }">
          <span class="num">{{ row.weight_theory || '—' }} / {{ row.weight_actual || '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="row.status === 'shipped' ? 'success' : row.status === 'checked' ? 'primary' : 'warning'"
                  size="small">
            {{ row.status === 'shipped' ? '已发运' : row.status === 'checked' ? '已复核' : '待复核' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="130" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">
            {{ row.status === 'shipped' ? '查看' : '复核发运' }}
          </el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty">没有待复核的订单。拣货完成后这里就会出现。</div>
      </template>
    </el-table>

    <el-pagination class="pagination" :current-page="page" :page-size="pageSize" :total="total"
                   :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next"
                   @current-change="onPageChange" @size-change="onSizeChange" />

    <el-drawer v-model="drawer" :title="order ? `复核 ${order.code}` : '复核'" size="560px">
      <template v-if="order">
        <div class="weigh">
          <div class="weight-cell">
            <div class="label">理论重量</div>
            <div class="value">{{ order.weight_theory || '—' }}</div>
          </div>
          <div class="weight-cell" :class="{ bad: result && !result.passed }">
            <div class="label">实称重量</div>
            <div class="value">{{ order.weight_actual || '—' }}</div>
          </div>
          <div class="weight-cell">
            <div class="label">偏差</div>
            <div class="value" :class="{ bad: result && !result.passed }">{{ deviationText() }}</div>
          </div>
        </div>

        <el-alert v-if="result && !result.passed" type="error" :closable="false" show-icon
                  title="超出允许偏差，请重新称重或核实商品重量" style="margin-bottom: 12px" />
        <el-alert v-else-if="result && result.reason" type="info" :closable="false" show-icon
                  :title="result.reason" style="margin-bottom: 12px" />

        <el-form label-width="92px" :disabled="order.status === 'shipped'">
          <el-form-item label="实称重量">
            <div class="two">
              <input v-model="form.weight_actual" class="plain-input" placeholder="kg" />
              <el-button :loading="busy" @click="doCheck">记录</el-button>
            </div>
          </el-form-item>
          <el-form-item label="允许偏差">
            <input v-model="form.tolerance" class="plain-input" placeholder="留空用默认 0.05（5%）" />
          </el-form-item>
        </el-form>

        <div class="sub-title">明细</div>
        <el-table :data="order.lines" size="small" border>
          <el-table-column prop="sku_id" label="商品" width="90" />
          <el-table-column prop="qty" label="数量" width="90" align="right" class-name="num" />
          <el-table-column prop="allocated_qty" label="已分配" width="90" align="right" class-name="num" />
        </el-table>
      </template>

      <template #footer>
        <el-button @click="drawer = false">关闭</el-button>
        <el-button v-if="order?.status !== 'shipped'"
                   v-permission="'wms_outbound:check:ship'" type="primary"
                   :disabled="result ? !result.passed : false"
                   :loading="busy" @click="doShip">
          发运
        </el-button>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.page { padding: 4px; }
.toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.pagination { margin-top: 12px; justify-content: flex-end; }
.empty { padding: 28px 0; color: #98a4bb; font-size: 13px; }
.sub-title { margin: 16px 0 8px; font-size: 13px; font-weight: 600; color: #3a4a68; }
.weigh { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 14px; }
.weight-cell { padding: 12px; background: #f7f9fc; border-radius: 8px; text-align: center; }
.weight-cell .label { font-size: 12px; color: #66748f; }
.weight-cell .value { margin-top: 6px; font-size: 18px; font-weight: 600; color: #1b2740; font-family: ui-monospace, Menlo, monospace; }
.weight-cell.bad { background: #fef2f2; }
.weight-cell .value.bad { color: #dc2626; }
.two { display: flex; gap: 8px; width: 100%; }
.plain-input { flex: 1; padding: 8px 10px; font-size: 13px; color: #1b2740; border: 1px solid #e8ecf3; border-radius: 6px; outline: none; }
.plain-input:focus { border-color: #10b3a3; box-shadow: 0 0 0 3px rgba(16, 179, 163, 0.12); }
:deep(.num) { font-family: ui-monospace, Menlo, monospace; font-variant-numeric: tabular-nums; }
</style>
