<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listSkus } from '@/api/wms_master_data'
import { createTransfer, executeTransfer, listTransfers } from '@/api/wms_ops'
import { usePagedList } from '@/composables/usePagedList'

const { items, total, page, pageSize, loading, query, fetch, search, onPageChange, onSizeChange } =
  usePagedList(listTransfers, { status: '' })
const skus = ref<any[]>([])
const drawer = ref(false)
const busy = ref(false)
const form = reactive<any>({
  owner_id: 1, sku_id: null, lot_id: 0,
  from_location_id: null, to_location_id: null, qty: '', reason: '',
})

const skuLabel = (id: number) => skus.value.find((s) => s.id === id)?.name || `#${id}`

function openCreate() {
  Object.assign(form, {
    owner_id: 1, sku_id: null, lot_id: 0,
    from_location_id: null, to_location_id: null, qty: '', reason: '',
  })
  drawer.value = true
}

async function submit() {
  if (!form.sku_id || !form.from_location_id || !form.to_location_id || !Number(form.qty)) {
    ElMessage.warning('商品、源库位、目标库位、数量都要填')
    return
  }
  busy.value = true
  try {
    await createTransfer(form)
    ElMessage.success('移库单已建，可执行')
    drawer.value = false
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    busy.value = false
  }
}

async function run(row: any) {
  busy.value = true
  try {
    await executeTransfer(row.id)
    ElMessage.success('已移库，两条流水已记')
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  try {
    const s: any = await listSkus({ page: 1, page_size: 200 })
    skus.value = s?.items || []
  } catch {
    skus.value = []
  }
  await fetch()
})
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="query.status" placeholder="状态" clearable style="width: 140px" @change="search">
        <el-option label="待执行" value="pending" />
        <el-option label="已完成" value="done" />
        <el-option label="已取消" value="cancelled" />
      </el-select>
      <el-button @click="search">查询</el-button>
      <div class="spacer" />
      <el-button v-permission="'wms_internal_ops:transfer:create'" type="primary" @click="openCreate">
        新建移库单
      </el-button>
    </div>

    <el-table v-loading="loading" :data="items" border stripe height="calc(100vh - 240px)">
      <el-table-column prop="code" label="单号" width="140" fixed />
      <el-table-column label="商品" min-width="140">
        <template #default="{ row }">{{ skuLabel(row.sku_id) }}</template>
      </el-table-column>
      <el-table-column prop="lot_id" label="批次" width="80" align="right" />
      <el-table-column label="从 / 到" width="150">
        <template #default="{ row }">
          <span class="num">{{ row.from_location_id }} → {{ row.to_location_id }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="qty" label="数量" width="100" align="right" class-name="num" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'done' ? 'success' : row.status === 'pending' ? 'warning' : 'info'"
                  size="small">
            {{ row.status === 'done' ? '已完成' : row.status === 'pending' ? '待执行' : '已取消' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="110" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 'pending'"
                     v-permission="'wms_internal_ops:transfer:execute'" link type="primary"
                     :loading="busy" @click="run(row)">执行移库</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty">还没有移库单。货放错库位时在这里建单，执行后扣源位、加目标位。</div>
      </template>
    </el-table>

    <el-pagination class="pagination" :current-page="page" :page-size="pageSize" :total="total"
                   :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next"
                   @current-change="onPageChange" @size-change="onSizeChange" />

    <el-drawer v-model="drawer" title="新建移库单" size="520px">
      <el-form label-width="94px">
        <el-form-item label="货主"><el-input-number v-model="form.owner_id" :min="1" /></el-form-item>
        <el-form-item label="商品" required>
          <el-select v-model="form.sku_id" filterable style="width: 100%">
            <el-option v-for="s in skus" :key="s.id" :label="`${s.code} ${s.name}`" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="批次 ID"><el-input-number v-model="form.lot_id" :min="0" /></el-form-item>
        <el-form-item label="源库位 ID" required><el-input-number v-model="form.from_location_id" :min="1" /></el-form-item>
        <el-form-item label="目标库位 ID" required><el-input-number v-model="form.to_location_id" :min="1" /></el-form-item>
        <el-form-item label="数量" required><el-input v-model="form.qty" /></el-form-item>
        <el-form-item label="原因"><el-input v-model="form.reason" /></el-form-item>
      </el-form>
      <div class="hint">只移可发状态的货；冻结与破损的不能移。执行时同事务写两条流水。</div>
      <template #footer>
        <el-button @click="drawer = false">取消</el-button>
        <el-button type="primary" :loading="busy" @click="submit">创建</el-button>
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
.hint { padding: 0 12px 12px; font-size: 12px; color: #98a4bb; line-height: 1.7; }
.num { font-family: ui-monospace, Menlo, monospace; }
:deep(.num) { font-family: ui-monospace, Menlo, monospace; font-variant-numeric: tabular-nums; }
</style>
