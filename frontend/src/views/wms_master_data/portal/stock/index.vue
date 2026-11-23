<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { portalSkus, portalStockDetail, portalStocks, portalTxns } from '@/api/wms_portal'

const skus = ref<any[]>([])
const rows = ref<any[]>([])
const detail = ref<any[]>([])
const txns = ref<any[]>([])
const selectedSku = ref<number | null>(null)
const activeTab = ref('stocks')

function skuName(id: number) {
  const s = skus.value.find((x) => x.id === id)
  return s ? `${s.owner_sku_code} ${s.name}` : `#${id}`
}

async function loadStocks() {
  const res: any = await portalStocks()
  rows.value = res.items || []
}

async function loadTxns() {
  const res: any = await portalTxns()
  txns.value = res.items || []
}

async function onSkuChange(id: number | null) {
  selectedSku.value = id
  if (!id) { detail.value = []; return }
  const res: any = await portalStockDetail(id)
  detail.value = res.items || []
}

onMounted(async () => {
  skus.value = (await portalSkus()) as any
  await loadStocks()
  await loadTxns()
})
</script>

<template>
  <div class="wrap">
    <div class="head">
      <h2>库存查询</h2>
      <p>只看本货主的库存与流水。仓库编码由仓库分配，货主编码是你方系统的编码。</p>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="库存汇总" name="stocks">
        <el-table :data="rows" size="small" border style="width: 100%">
          <el-table-column label="商品" min-width="200">
            <template #default="{ row }">{{ skuName(row.sku_id) }}</template>
          </el-table-column>
          <el-table-column prop="stock_status" label="状态" width="120" />
          <el-table-column prop="qty" label="数量" width="100" />
          <el-table-column prop="lot_count" label="批次数" width="90" />
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button link type="primary" @click="onSkuChange(row.sku_id)">看明细</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!rows.length" description="暂无库存" />

        <div v-if="selectedSku" class="detail">
          <h3>{{ skuName(selectedSku) }} · 批次库位明细</h3>
          <el-table :data="detail" size="small" border>
            <el-table-column prop="lot_id" label="批次" width="100" />
            <el-table-column prop="location_id" label="库位" width="100" />
            <el-table-column prop="stock_status" label="状态" width="120" />
            <el-table-column prop="qty" label="数量" width="100" />
          </el-table>
          <el-empty v-if="!detail.length" description="该商品当前无在库明细" />
        </div>
      </el-tab-pane>

      <el-tab-pane label="库存流水" name="txns">
        <el-table :data="txns" size="small" border style="width: 100%">
          <el-table-column prop="created_at" label="时间" width="170" />
          <el-table-column label="商品" min-width="180">
            <template #default="{ row }">{{ skuName(row.sku_id) }}</template>
          </el-table-column>
          <el-table-column prop="ref_type" label="来源" width="110" />
          <el-table-column prop="action" label="动作" width="140" />
          <el-table-column prop="delta" label="变动" width="90" />
          <el-table-column prop="qty_after" label="变动后" width="90" />
        </el-table>
        <el-empty v-if="!txns.length" description="暂无流水" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.wrap { max-width: 1000px; }
.head h2 { margin: 0 0 6px; font-size: 18px; font-weight: 600; color: #1b2740; }
.head p { margin: 0 0 20px; font-size: 13px; color: #66748f; }
.detail { margin-top: 24px; }
.detail h3 { margin: 0 0 12px; font-size: 15px; font-weight: 600; color: #1b2740; }
</style>
