<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AppFormDrawer from '@/components/AppFormDrawer.vue'
import { portalCreateSku, portalSkus } from '@/api/wms_portal'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const canCreate = userStore.hasPermission('wms_master_data:sku:create')

const skus = ref<any[]>([])
const busy = ref(false)
const drawerVisible = ref(false)
const sections = [
  { key: 'base', label: '基本信息' },
  { key: 'batch', label: '批次与效期' },
]
const form = reactive<any>({
  owner_sku_code: '',
  name: '',
  spec: '',
  unit_code: '件',
  category: '',
  lot_required: false,
  expiry_warn_days: 30,
  qty_per_box: 1,
})

function resetForm() {
  form.owner_sku_code = ''
  form.name = ''
  form.spec = ''
  form.unit_code = '件'
  form.category = ''
  form.lot_required = false
  form.expiry_warn_days = 30
  form.qty_per_box = 1
}

function openCreate() {
  resetForm()
  drawerVisible.value = true
}

async function load() {
  skus.value = (await portalSkus()) as any
}

async function submit() {
  if (!form.owner_sku_code.trim() || !form.name.trim()) {
    ElMessage.warning('货主编码与商品名称必填')
    return
  }
  busy.value = true
  try {
    const res: any = await portalCreateSku({
      owner_sku_code: form.owner_sku_code.trim(),
      name: form.name.trim(),
      spec: form.spec || null,
      unit_code: form.unit_code,
      category: form.category || null,
      lot_required: form.lot_required,
      expiry_warn_days: Number(form.expiry_warn_days) || 0,
      qty_per_box: Number(form.qty_per_box) || 1,
    })
    drawerVisible.value = false
    ElMessage.success(`商品 ${res.code} 已建档`)
    await load()
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <div>
        <h2>商品档案</h2>
      </div>
      <el-button v-if="canCreate" type="primary" @click="openCreate">新建商品</el-button>
    </div>

    <el-table :data="skus" style="width: 100%" size="small" border>
      <el-table-column prop="code" label="仓库编码" width="140" />
      <el-table-column prop="owner_sku_code" label="货主编码" min-width="140" />
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column label="批次" width="100">
        <template #default="{ row }">{{ row.lot_required ? '启用' : '不启用' }}</template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!skus.length" description="还没有商品，点「新建商品」建档" />

    <AppFormDrawer
      v-model="drawerVisible"
      title="新建商品"
      subtitle="填写商品信息，带 * 号的必填"
      :sections="sections"
    >
      <template #section-base>
        <el-form label-width="110px">
          <el-form-item label="货主编码" required>
            <el-input v-model="form.owner_sku_code" placeholder="你方系统里的商品编码，同货主内唯一" />
          </el-form-item>
          <el-form-item label="商品名称" required>
            <el-input v-model="form.name" placeholder="商品名称" />
          </el-form-item>
          <el-form-item label="规格">
            <el-input v-model="form.spec" placeholder="如 100g/袋" />
          </el-form-item>
          <el-form-item label="分类">
            <el-input v-model="form.category" placeholder="可选" />
          </el-form-item>
          <el-form-item label="单位">
            <el-input v-model="form.unit_code" placeholder="件" />
          </el-form-item>
        </el-form>
      </template>
      <template #section-batch>
        <el-form label-width="110px">
          <el-form-item label="启用批次">
            <el-switch v-model="form.lot_required" />
            <span class="hint">启用后收发货必带批次</span>
          </el-form-item>
          <el-form-item label="临期预警天数">
            <el-input-number v-model="form.expiry_warn_days" :min="0" :max="3650" />
          </el-form-item>
          <el-form-item label="每箱件数">
            <el-input-number v-model="form.qty_per_box" :min="0.0001" :precision="4" />
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="drawerVisible = false">取消</el-button>
        <el-button type="primary" :loading="busy" @click="submit">建档</el-button>
      </template>
    </AppFormDrawer>
  </div>
</template>

<style scoped>
.page { max-width: 1000px; }
.toolbar { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 18px; }
.toolbar h2 { margin: 0 0 6px; font-size: 18px; font-weight: 600; color: #1b2740; }
.toolbar p { margin: 0; font-size: 13px; color: #66748f; }
.hint { font-size: 12px; color: #98a4bb; margin-left: 8px; }
</style>
