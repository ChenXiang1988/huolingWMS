<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listOwners, listSkus } from '@/api/wms_master_data'
import { createServiceOrder, listServiceOrders } from '@/api/wms_inbound'

const owners = ref<any[]>([])
const skus = ref<any[]>([])
const rows = ref<any[]>([])
const loading = ref(false)
const query = reactive<any>({ owner_id: '', asn_id: '' })

const drawer = ref(false)
const saving = ref(false)
const form = reactive<any>({
  owner_id: null,
  asn_id: null,
  sku_id: null,
  service_type: 'sample',
  sample_mode: 'ratio',
  sample_ratio: '0.05',
  sample_qty: '',
  retain_days: 30,
  on_expiry: 'scrap',
})

const ownerName = (id: number) => owners.value.find((o) => o.id === id)?.name || `#${id}`
const skuName = (id: number | null) =>
  id ? skus.value.find((s) => s.id === id)?.name || `#${id}` : '全部商品'

async function loadRefs() {
  const [o, s] = await Promise.all([
    listOwners({ page: 1, page_size: 200 }),
    listSkus({ page: 1, page_size: 200 }),
  ])
  owners.value = (o as any)?.items || []
  skus.value = (s as any)?.items || []
  if (!query.owner_id && owners.value.length) query.owner_id = owners.value[0].id
}

async function fetch() {
  loading.value = true
  try {
    const params: any = {}
    if (query.owner_id) params.owner_id = query.owner_id
    if (query.asn_id) params.asn_id = query.asn_id
    rows.value = (await listServiceOrders(params)) as any
  } catch (e) {
    console.error(e)
    rows.value = []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(form, {
    owner_id: query.owner_id || owners.value[0]?.id || null,
    asn_id: query.asn_id ? Number(query.asn_id) : null,
    sku_id: null,
    service_type: 'sample',
    sample_mode: 'ratio',
    sample_ratio: '0.05',
    sample_qty: '',
    retain_days: 30,
    on_expiry: 'scrap',
  })
  drawer.value = true
}

async function submit() {
  if (!form.owner_id) {
    ElMessage.warning('货主必填')
    return
  }
  if (form.sample_mode === 'ratio' && !Number(form.sample_ratio)) {
    ElMessage.warning('按比例留样要填比例')
    return
  }
  if (form.sample_mode === 'fixed' && !Number(form.sample_qty)) {
    ElMessage.warning('固定留样要填数量')
    return
  }
  saving.value = true
  try {
    const payload: any = {
      owner_id: form.owner_id,
      asn_id: form.asn_id || null,
      sku_id: form.sku_id || null,
      service_type: form.service_type,
      sample_mode: form.sample_mode,
      retain_days: form.retain_days,
      on_expiry: form.on_expiry,
    }
    if (form.sample_mode === 'ratio') payload.sample_ratio = String(form.sample_ratio)
    else payload.sample_qty = String(form.sample_qty)
    await createServiceOrder(payload)
    ElMessage.success('已创建')
    drawer.value = false
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
      <el-select v-model="query.owner_id" placeholder="货主" clearable style="width: 180px" @change="fetch">
        <el-option v-for="o in owners" :key="o.id" :label="`${o.code} ${o.name}`" :value="o.id" />
      </el-select>
      <el-input v-model="query.asn_id" placeholder="预报 ID" clearable style="width: 140px"
                @keyup.enter="fetch" @clear="fetch" />
      <el-button @click="fetch">查询</el-button>
      <div class="spacer" />
      <el-button v-permission="'wms_inbound:service_order:create'" type="primary" @click="openCreate">
        新建服务订单
      </el-button>
    </div>

    <el-table v-loading="loading" :data="rows" border stripe height="calc(100vh - 240px)">
      <el-table-column prop="code" label="单号" width="150" />
      <el-table-column label="货主" width="160" show-overflow-tooltip>
        <template #default="{ row }">{{ ownerName(row.owner_id) }}</template>
      </el-table-column>
      <el-table-column label="关联预报" width="120">
        <template #default="{ row }">{{ row.asn_id ? `#${row.asn_id}` : '—' }}</template>
      </el-table-column>
      <el-table-column label="适用商品" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">{{ skuName(row.sku_id) }}</template>
      </el-table-column>
      <el-table-column label="留样" width="170">
        <template #default="{ row }">
          {{ row.sample_mode === 'ratio' ? `按比例 ${row.sample_ratio}` : `固定 ${row.sample_qty}` }}
        </template>
      </el-table-column>
      <el-table-column label="保留" width="100">
        <template #default="{ row }">{{ row.retain_days }} 天</template>
      </el-table-column>
      <el-table-column label="到期处置" width="120">
        <template #default="{ row }">
          {{ row.on_expiry === 'scrap' ? '报废' : '退回货主' }}
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty">还没有服务订单。留样要求随预报提交，收货时按比例或固定数量拆出。</div>
      </template>
    </el-table>

    <el-drawer v-model="drawer" title="新建服务订单" size="520px">
      <el-form label-width="96px">
        <el-form-item label="货主" required>
          <el-select v-model="form.owner_id" style="width: 100%">
            <el-option v-for="o in owners" :key="o.id" :label="`${o.code} ${o.name}`" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联预报">
          <el-input-number v-model="form.asn_id" :min="1" style="width: 100%" placeholder="选填" />
        </el-form-item>
        <el-form-item label="适用商品">
          <el-select v-model="form.sku_id" clearable placeholder="留空表示全部商品" style="width: 100%">
            <el-option v-for="s in skus.filter((x) => !form.owner_id || x.owner_id === form.owner_id)"
                       :key="s.id" :label="`${s.code} ${s.name}`" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="留样方式">
          <el-radio-group v-model="form.sample_mode">
            <el-radio value="ratio">按比例</el-radio>
            <el-radio value="fixed">固定数量</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.sample_mode === 'ratio'" label="比例">
          <el-input v-model="form.sample_ratio" placeholder="0–1 之间，如 0.05 表示 5%" />
          <div class="hint">按实收计算并向上取整，最多不超过实收数量。</div>
        </el-form-item>
        <el-form-item v-else label="数量">
          <el-input v-model="form.sample_qty" placeholder="固定留几件" />
        </el-form-item>
        <el-form-item label="保留天数">
          <el-input-number v-model="form.retain_days" :min="1" :max="3650" />
        </el-form-item>
        <el-form-item label="到期处置">
          <el-radio-group v-model="form.on_expiry">
            <el-radio value="scrap">报废</el-radio>
            <el-radio value="return_owner">退回货主</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="drawer = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.page { padding: 4px; }
.toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.spacer { flex: 1; }
.empty { padding: 28px 0; color: #98a4bb; font-size: 13px; }
.hint { width: 100%; margin-top: 4px; font-size: 12px; color: #98a4bb; line-height: 1.6; }
</style>
