<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  addBarcode,
  createSku,
  deleteBarcode,
  listBarcodes,
  listOwners,
  listSkus,
  listZones,
  updateSku,
  updateSkuStorage,
} from '@/api/wms_master_data'
import { usePagedList } from '@/composables/usePagedList'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const owners = ref<any[]>([])
const zones = ref<any[]>([])

const { items, total, page, pageSize, loading, query, fetch, search, onPageChange, onSizeChange } =
  usePagedList(listSkus, { owner_id: '', keyword: '' })

const drawer = ref(false)
const saving = ref(false)
const editing = ref<any>(null)
const barcodes = ref<any[]>([])
const newBarcode = reactive({ barcode: '', is_primary: false })

/** 两组字段各自一段，权限也各管一段——这是本页唯一需要解释的地方。 */
const canEditBase = computed(() => userStore.hasPermission('wms_master_data:sku:edit'))
const canEditStorage = computed(() => userStore.hasPermission('wms_master_data:sku:configure'))

const base = reactive<any>({})
const storage = reactive<any>({})

function resetBase() {
  Object.assign(base, {
    owner_id: null, owner_sku_code: '', name: '', spec: '', unit_code: '件',
    category: '', weight: null, volume: null, temp_requirement: 'ambient',
    lot_required: false, expiry_warn_days: 30, qty_per_box: '1',
  })
  Object.assign(storage, { default_zone_id: null, qty_per_pallet: null, putaway_note: '' })
}

function openCreate() {
  editing.value = null
  barcodes.value = []
  resetBase()
  base.owner_id = query.owner_id || owners.value[0]?.id || null
  drawer.value = true
}

async function openEdit(row: any) {
  editing.value = row
  Object.assign(base, {
    owner_id: row.owner_id,
    owner_sku_code: row.owner_sku_code,
    name: row.name,
    spec: row.spec || '',
    unit_code: row.unit_code,
    category: row.category || '',
    weight: row.weight,
    volume: row.volume,
    temp_requirement: row.temp_requirement,
    lot_required: row.lot_required,
    expiry_warn_days: row.expiry_warn_days,
    qty_per_box: row.qty_per_box,
  })
  Object.assign(storage, {
    default_zone_id: row.default_zone_id,
    qty_per_pallet: row.qty_per_pallet,
    putaway_note: row.putaway_note || '',
  })
  drawer.value = true
  await loadBarcodes(row.id)
}

async function loadBarcodes(skuId: number) {
  const data: any = await listBarcodes(skuId)
  barcodes.value = data || []
}

async function submit() {
  if (!base.owner_id || !base.owner_sku_code.trim() || !base.name.trim()) {
    ElMessage.warning('货主、货主编码与名称必填')
    return
  }
  saving.value = true
  try {
    if (editing.value) {
      if (canEditBase.value) await updateSku(editing.value.id, base)
      if (canEditStorage.value) await updateSkuStorage(editing.value.id, storage)
      ElMessage.success('已保存')
    } else {
      const res: any = await createSku(base)
      ElMessage.success(`已创建，仓库编码 ${res.code}`)
      // 新建后转成编辑态，方便继续加条码
      editing.value = { id: res.id, ...base, code: res.code }
      await loadBarcodes(res.id)
      await fetch()
      saving.value = false
      return
    }
    drawer.value = false
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    saving.value = false
  }
}

async function onAddBarcode() {
  if (!newBarcode.barcode.trim() || !editing.value?.id) return
  try {
    await addBarcode(editing.value.id, { ...newBarcode })
    newBarcode.barcode = ''
    newBarcode.is_primary = false
    await loadBarcodes(editing.value.id)
  } catch (e) {
    console.error(e)
  }
}

async function onDeleteBarcode(row: any) {
  await ElMessageBox.confirm(`删除条码 ${row.barcode}？`, '确认', { type: 'warning' })
  await deleteBarcode(row.id)
  await loadBarcodes(editing.value.id)
}

const ownerName = (id: number) => owners.value.find((o) => o.id === id)?.name || `#${id}`

onMounted(async () => {
  const [o, z] = await Promise.all([
    listOwners({ page: 1, page_size: 200 }),
    listZones(),
  ])
  owners.value = (o as any)?.items || []
  zones.value = (z as any) || []
  await fetch()
})
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="query.owner_id" placeholder="货主" clearable style="width: 180px" @change="search">
        <el-option v-for="o in owners" :key="o.id" :label="`${o.code} ${o.name}`" :value="o.id" />
      </el-select>
      <el-input
        v-model="query.keyword"
        placeholder="仓库编码 / 货主编码 / 名称"
        clearable
        style="width: 260px"
        @keyup.enter="search"
        @clear="search"
      />
      <el-button @click="search">查询</el-button>
      <div class="spacer" />
      <el-button v-permission="'wms_master_data:sku:create'" type="primary" @click="openCreate">
        新建商品
      </el-button>
    </div>

    <el-table v-loading="loading" :data="items" border stripe height="calc(100vh - 260px)">
      <el-table-column prop="code" label="仓库编码" width="130" fixed />
      <el-table-column prop="owner_sku_code" label="货主编码" width="130" />
      <el-table-column prop="name" label="名称" min-width="180" show-overflow-tooltip />
      <el-table-column label="所属货主" width="160" show-overflow-tooltip>
        <template #default="{ row }">{{ ownerName(row.owner_id) }}</template>
      </el-table-column>
      <el-table-column prop="spec" label="规格" width="130" show-overflow-tooltip />
      <el-table-column label="批次" width="80" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.lot_required" size="small" type="success">管</el-tag>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="温区" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.temp_requirement === 'chilled' ? 'warning' : 'info'" size="small" effect="plain">
            {{ row.temp_requirement === 'chilled' ? '冷藏' : '常温' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty">还没有商品。货主编码用于对接，仓库编码由系统自动生成。</div>
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

    <el-drawer v-model="drawer" :title="editing ? `编辑商品 ${editing.code || ''}` : '新建商品'" size="640px">
      <div class="section">
        <div class="section-title">基础信息</div>
        <div class="section-hint">{{ canEditBase ? '货主维护：这是什么货' : '当前账号无编辑权限，只读' }}</div>
        <el-form label-width="96px" :disabled="!canEditBase">
          <el-form-item label="货主" required>
            <el-select v-model="base.owner_id" :disabled="!!editing" style="width: 100%">
              <el-option v-for="o in owners" :key="o.id" :label="`${o.code} ${o.name}`" :value="o.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="货主编码" required>
            <el-input v-model="base.owner_sku_code" placeholder="货主系统里的编码" />
          </el-form-item>
          <el-form-item label="名称" required>
            <el-input v-model="base.name" />
          </el-form-item>
          <el-form-item label="规格">
            <el-input v-model="base.spec" placeholder="如 12×24 包/箱" />
          </el-form-item>
          <el-form-item label="单位 / 分类">
            <div class="two">
              <el-input v-model="base.unit_code" placeholder="最小单位，如 件" />
              <el-input v-model="base.category" placeholder="分类" />
            </div>
          </el-form-item>
          <el-form-item label="重量 / 体积">
            <div class="two">
              <el-input v-model="base.weight" placeholder="单件重量 kg" />
              <el-input v-model="base.volume" placeholder="单件体积 m³" />
            </div>
          </el-form-item>
          <el-form-item label="一箱几件">
            <el-input v-model="base.qty_per_box" style="width: 160px" />
          </el-form-item>
          <el-form-item label="温区要求">
            <el-select v-model="base.temp_requirement" style="width: 160px">
              <el-option label="常温" value="ambient" />
              <el-option label="冷藏" value="chilled" />
            </el-select>
          </el-form-item>
          <el-form-item label="启用批次">
            <el-switch v-model="base.lot_required" />
          </el-form-item>
          <el-form-item v-if="base.lot_required" label="临期预警">
            <el-input-number v-model="base.expiry_warn_days" :min="0" :max="365" />
            <span class="unit-text">天（0 表示到期当天才冻结）</span>
          </el-form-item>
        </el-form>
      </div>

      <div class="section">
        <div class="section-title">存储要求</div>
        <div class="section-hint">{{ canEditStorage ? '仓库维护：这货怎么存' : '当前账号无编辑权限，只读' }}</div>
        <el-form label-width="96px" :disabled="!canEditStorage">
          <el-form-item label="优先库区">
            <el-select v-model="storage.default_zone_id" clearable style="width: 100%">
              <el-option v-for="z in zones" :key="z.id" :label="`${z.code} ${z.name}`" :value="z.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="一托几件">
            <el-input v-model="storage.qty_per_pallet" style="width: 160px" />
          </el-form-item>
          <el-form-item label="上架要求">
            <el-input v-model="storage.putaway_note" type="textarea" :rows="2" placeholder="如 不可倒置、限高 1.5 米" />
          </el-form-item>
        </el-form>
      </div>

      <div v-if="editing?.id" class="section">
        <div class="section-title">条码</div>
        <div class="section-hint">一品多码。收货扫码时按条码找到这个商品。</div>
        <div class="barcode-add">
          <el-input v-model="newBarcode.barcode" placeholder="条码" style="width: 220px" />
          <el-checkbox v-model="newBarcode.is_primary">主条码</el-checkbox>
          <el-button v-permission="'wms_master_data:sku:edit'" @click="onAddBarcode">添加</el-button>
        </div>
        <el-table :data="barcodes" size="small" border>
          <el-table-column prop="barcode" label="条码" min-width="200" />
          <el-table-column label="主条码" width="90" align="center">
            <template #default="{ row }">{{ row.is_primary ? '是' : '否' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="80" align="center">
            <template #default="{ row }">
              <el-button v-permission="'wms_master_data:sku:edit'" link type="danger" @click="onDeleteBarcode(row)">
                删除
              </el-button>
            </template>
          </el-table-column>
          <template #empty>
            <div class="empty-small">还没有条码</div>
          </template>
        </el-table>
      </div>

      <template #footer>
        <el-button @click="drawer = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
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
.empty-small {
  padding: 12px 0;
  color: #98a4bb;
  font-size: 12px;
}
.muted {
  color: #c3ccdb;
}
.section + .section {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid #eef1f6;
}
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #1b2740;
}
.section-hint {
  margin: 2px 0 10px;
  font-size: 12px;
  color: #98a4bb;
}
.two {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  width: 100%;
}
.unit-text {
  margin-left: 8px;
  font-size: 12px;
  color: #98a4bb;
}
.barcode-add {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
</style>
