<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listOwners } from '@/api/wms_master_data'
import { createAdjustment, listStockDetail, listStocks } from '@/api/wms_inventory'
import { usePagedList } from '@/composables/usePagedList'

const STATUS_LABEL: Record<string, string> = {
  available: '可发',
  frozen: '冻结',
  damaged: '破损',
}
const STATUS_TYPE: Record<string, string> = {
  available: 'success',
  frozen: 'warning',
  damaged: 'danger',
}

const owners = ref<any[]>([])
const { items, total, page, pageSize, loading, query, fetch, search, onPageChange, onSizeChange } =
  usePagedList(listStocks, { owner_id: '' })

/** 展开行才去拉批次明细——首屏把每个商品的批次都拉下来会拖垮列表。 */
const details = reactive<Record<number, any[]>>({})
const detailLoading = reactive<Record<number, boolean>>({})

async function onExpand(row: any, expanded: any[]) {
  if (!expanded.length) return
  if (details[row.sku_id]) return
  detailLoading[row.sku_id] = true
  try {
    const res: any = await listStockDetail({ sku_id: row.sku_id, owner_id: row.owner_id, page_size: 200 })
    details[row.sku_id] = res?.items || []
  } catch (e) {
    console.error(e)
    details[row.sku_id] = []
  } finally {
    detailLoading[row.sku_id] = false
  }
}

const drawer = ref(false)
const saving = ref(false)
const form = reactive<any>({
  request_id: 0, sku_id: null, lot_id: 0, location_id: null,
  stock_status: 'available', delta: '', reason: '',
})

function openAdjust(row?: any) {
  Object.assign(form, {
    // 幂等键在这里生成一次，重试时保持不变；每次点击都新生成会失去幂等性
    request_id: Date.now(),
    sku_id: row?.sku_id ?? null,
    lot_id: 0,
    location_id: null,
    stock_status: row?.stock_status ?? 'available',
    delta: '',
    reason: '',
  })
  drawer.value = true
}

async function submit() {
  if (!form.sku_id || !form.location_id || !form.delta) {
    ElMessage.warning('商品、库位与数量必填')
    return
  }
  saving.value = true
  try {
    const res: any = await createAdjustment({ ...form })
    ElMessage.success(res.applied ? `已调整，当前 ${res.qty_after}` : '这次调整已经记过账，未重复入账')
    drawer.value = false
    delete details[form.sku_id]
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    saving.value = false
  }
}

const ownerName = (id: number) => owners.value.find((o) => o.id === id)?.name || `#${id}`

onMounted(async () => {
  const data: any = await listOwners({ page: 1, page_size: 200 })
  owners.value = data?.items || []
  await fetch()
})
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="query.owner_id" placeholder="货主" clearable style="width: 200px" @change="search">
        <el-option v-for="o in owners" :key="o.id" :label="`${o.code} ${o.name}`" :value="o.id" />
      </el-select>
      <el-button @click="search">查询</el-button>
      <div class="spacer" />
      <el-button v-permission="'wms_inventory:adjust:create'" type="primary" @click="openAdjust()">
        调整库存
      </el-button>
    </div>

    <el-table
      v-loading="loading"
      :data="items"
      border
      stripe
      row-key="sku_id"
      height="calc(100vh - 260px)"
      @expand-change="onExpand"
    >
      <el-table-column type="expand">
        <template #default="{ row }">
          <div v-loading="detailLoading[row.sku_id]" class="detail">
            <div class="detail-title">批次与库位明细</div>
            <el-table :data="details[row.sku_id] || []" size="small" border>
              <el-table-column prop="lot_id" label="批次 ID" width="110" />
              <el-table-column prop="location_id" label="库位 ID" width="110" />
              <el-table-column label="状态" width="100">
                <template #default="s">
                  <el-tag :type="STATUS_TYPE[s.row.stock_status] as any" size="small" effect="light">
                    {{ STATUS_LABEL[s.row.stock_status] || s.row.stock_status }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="qty" label="数量" align="right" class-name="num" />
              <template #empty>
                <div class="detail-empty">这个商品还没有任何库存记录</div>
              </template>
            </el-table>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="货主" width="160" show-overflow-tooltip>
        <template #default="{ row }">{{ ownerName(row.owner_id) }}</template>
      </el-table-column>
      <el-table-column prop="sku_id" label="商品 ID" width="110" />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="STATUS_TYPE[row.stock_status] as any" size="small" effect="light">
            {{ STATUS_LABEL[row.stock_status] || row.stock_status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="qty" label="数量" width="140" align="right" class-name="num" />
      <el-table-column label="批次数" width="100" align="right">
        <template #default="{ row }">{{ row.lot_count }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'wms_inventory:adjust:create'" link type="primary" @click="openAdjust(row)">
            调整
          </el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty">还没有库存。库存只能通过收货、调整等记账动作产生，不能手工改数。</div>
      </template>
    </el-table>

    <el-pagination
      class="pagination"
      :current-page="page"
      :page-size="pageSize"
      :total="total"
      :page-sizes="[20, 50, 100]"
      layout="total, sizes, prev, pager, next"
      @current-change="onPageChange"
      @size-change="onSizeChange"
    />

    <el-drawer v-model="drawer" title="调整库存" size="480px">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="调整会写一条库存流水。同一笔调整重复提交只记一次账。"
        style="margin-bottom: 14px"
      />
      <el-form label-width="88px">
        <el-form-item label="商品 ID" required>
          <el-input-number v-model="form.sku_id" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="批次 ID">
          <el-input-number v-model="form.lot_id" :min="0" style="width: 100%" />
          <div class="hint">0 表示该商品不启用批次管理</div>
        </el-form-item>
        <el-form-item label="库位 ID" required>
          <el-input-number v-model="form.location_id" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="库存状态">
          <el-select v-model="form.stock_status" style="width: 100%">
            <el-option label="可发" value="available" />
            <el-option label="冻结" value="frozen" />
            <el-option label="破损" value="damaged" />
          </el-select>
        </el-form-item>
        <el-form-item label="数量" required>
          <el-input v-model="form.delta" placeholder="正数增加，负数扣减，如 -30" />
        </el-form-item>
        <el-form-item label="原因">
          <el-input v-model="form.reason" type="textarea" :rows="2" placeholder="如 期初建档、盘盈" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="drawer = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">提交调整</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.page {
  padding: 4px;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.spacer {
  flex: 1;
}
.pagination {
  margin-top: 12px;
  justify-content: flex-end;
}
.empty {
  padding: 28px 0;
  color: #98a4bb;
  font-size: 13px;
}
.detail {
  padding: 10px 16px 14px;
  background: #fafcff;
}
.detail-title {
  font-size: 12px;
  color: #66748f;
  margin-bottom: 8px;
}
.detail-empty {
  padding: 12px 0;
  color: #98a4bb;
  font-size: 12px;
}
.hint {
  width: 100%;
  margin-top: 4px;
  font-size: 12px;
  color: #98a4bb;
}
:deep(.num) {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-variant-numeric: tabular-nums;
}
</style>
