<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  batchCreateLocations,
  createLocation,
  listLocations,
  listZones,
  updateLocation,
} from '@/api/wms_master_data'
import { usePagedList } from '@/composables/usePagedList'

const TYPES = [
  { value: 'receiving', label: '收货暂存' },
  { value: 'storage', label: '常规存储' },
  { value: 'picking', label: '拆零拣选' },
  { value: 'sorting', label: '分播区' },
  { value: 'packing', label: '打包区' },
  { value: 'staging', label: '发货暂存' },
  { value: 'sample', label: '留样区' },
]
const TEMPS = [
  { value: 'ambient', label: '常温' },
  { value: 'chilled', label: '冷藏' },
]

const zones = ref<any[]>([])
const { items, total, page, pageSize, loading, query, fetch, search, onPageChange, onSizeChange } =
  usePagedList(listLocations, { zone_id: '', location_type: '', temp_zone: '', keyword: '' })

const drawer = ref(false)
const saving = ref(false)
const editing = ref<any>(null)
const form = reactive<any>({
  zone_id: null, code: '', location_type: 'storage', temp_zone: '', floor_no: null,
  aisle: '', rack: '', level: '', bin: '', capacity: '0',
  replenish_min: null, replenish_max: null,
})

const batchOpen = ref(false)
const batch = reactive<any>({
  zone_id: null, prefix: '', start: 1, count: 10, width: 2,
  location_type: 'storage', temp_zone: '', capacity: '0',
})

/** 批量预览：先让人看到会建出哪几个编码，再提交。 */
const batchPreview = computed(() => {
  if (!batch.prefix) return []
  return Array.from({ length: Math.min(Number(batch.count) || 0, 5) }, (_, i) => {
    const n = Number(batch.start || 1) + i
    return `${batch.prefix}${String(n).padStart(Number(batch.width) || 2, '0')}`
  })
})

const zoneName = (id: number) => zones.value.find((z) => z.id === id)?.name || `#${id}`
const typeLabel = (v: string) => TYPES.find((t) => t.value === v)?.label || v
const tempLabel = (v: string) => TEMPS.find((t) => t.value === v)?.label || v

async function loadZones() {
  const data: any = await listZones()
  zones.value = data || []
  if (!query.zone_id && zones.value.length) query.zone_id = zones.value[0].id
}

function openCreate() {
  editing.value = null
  Object.assign(form, {
    zone_id: zones.value[0]?.id ?? null, code: '', location_type: 'storage', temp_zone: '',
    floor_no: null, aisle: '', rack: '', level: '', bin: '', capacity: '0',
    replenish_min: null, replenish_max: null,
  })
  drawer.value = true
}

function openEdit(row: any) {
  editing.value = row
  Object.assign(form, {
    zone_id: row.zone_id, code: row.code, location_type: row.location_type,
    temp_zone: row.temp_zone, floor_no: row.floor_no, aisle: row.aisle || '',
    rack: row.rack || '', level: row.level || '', bin: row.bin || '',
    capacity: row.capacity, replenish_min: row.replenish_min, replenish_max: row.replenish_max,
  })
  drawer.value = true
}

async function submit() {
  if (!form.zone_id || !form.code.trim()) {
    ElMessage.warning('库区与库位编码必填')
    return
  }
  saving.value = true
  try {
    if (editing.value) {
      await updateLocation(editing.value.id, form)
      ElMessage.success('已保存')
    } else {
      await createLocation(form)
      ElMessage.success('库位已创建')
    }
    drawer.value = false
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    saving.value = false
  }
}

async function submitBatch() {
  if (!batch.zone_id || !batch.prefix) {
    ElMessage.warning('库区与前缀必填')
    return
  }
  saving.value = true
  try {
    const res: any = await batchCreateLocations(batch)
    ElMessage.success(`已建 ${res.created} 个，跳过 ${res.skipped} 个已存在的编码`)
    batchOpen.value = false
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadZones()
  await fetch()
})
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="query.zone_id" placeholder="库区" clearable style="width: 150px" @change="search">
        <el-option v-for="z in zones" :key="z.id" :label="`${z.code} ${z.name}`" :value="z.id" />
      </el-select>
      <el-select v-model="query.location_type" placeholder="类型" clearable style="width: 130px" @change="search">
        <el-option v-for="t in TYPES" :key="t.value" :label="t.label" :value="t.value" />
      </el-select>
      <el-select v-model="query.temp_zone" placeholder="温区" clearable style="width: 110px" @change="search">
        <el-option v-for="t in TEMPS" :key="t.value" :label="t.label" :value="t.value" />
      </el-select>
      <el-input
        v-model="query.keyword"
        placeholder="库位编码"
        clearable
        style="width: 180px"
        @keyup.enter="search"
        @clear="search"
      />
      <el-button @click="search">查询</el-button>
      <div class="spacer" />
      <el-button v-permission="'wms_master_data:location:create'" @click="batchOpen = true">批量新建</el-button>
      <el-button v-permission="'wms_master_data:location:create'" type="primary" @click="openCreate">
        新建库位
      </el-button>
    </div>

    <el-table v-loading="loading" :data="items" border stripe height="calc(100vh - 260px)">
      <el-table-column prop="code" label="库位编码" width="160" fixed />
      <el-table-column label="库区" width="150">
        <template #default="{ row }">{{ zoneName(row.zone_id) }}</template>
      </el-table-column>
      <el-table-column label="类型" width="110">
        <template #default="{ row }">{{ typeLabel(row.location_type) }}</template>
      </el-table-column>
      <el-table-column label="温区" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.temp_zone === 'chilled' ? 'warning' : 'info'" size="small" effect="plain">
            {{ tempLabel(row.temp_zone) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="floor_no" label="楼层" width="80" align="center" />
      <el-table-column label="坐标" min-width="180">
        <template #default="{ row }">
          {{ [row.aisle, row.rack, row.level, row.bin].filter(Boolean).join('-') || '—' }}
        </template>
      </el-table-column>
      <el-table-column prop="capacity" label="容量(托)" width="110" align="right" />
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'wms_master_data:location:edit'" link type="primary" @click="openEdit(row)">
            编辑
          </el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty">还没有库位。可以先批量新建一排。</div>
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

    <el-drawer v-model="drawer" :title="editing ? '编辑库位' : '新建库位'" size="520px">
      <el-form label-width="92px">
        <el-form-item label="库区" required>
          <el-select v-model="form.zone_id" style="width: 100%">
            <el-option v-for="z in zones" :key="z.id" :label="`${z.code} ${z.name}`" :value="z.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="库位编码" required>
          <el-input v-model="form.code" :disabled="!!editing" placeholder="如 F2-A-01" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.location_type" style="width: 100%">
            <el-option v-for="t in TYPES" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="温区">
          <el-select v-model="form.temp_zone" clearable placeholder="留空则继承库区" style="width: 100%">
            <el-option v-for="t in TEMPS" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="楼层">
          <el-input-number v-model="form.floor_no" :min="1" :max="20" placeholder="继承库区" />
        </el-form-item>
        <el-form-item label="坐标">
          <div class="coord">
            <el-input v-model="form.aisle" placeholder="巷" />
            <el-input v-model="form.rack" placeholder="架" />
            <el-input v-model="form.level" placeholder="层" />
            <el-input v-model="form.bin" placeholder="位" />
          </div>
          <div class="hint">按仓型填写：平面仓不填层，立库必须填巷架层。</div>
        </el-form-item>
        <el-form-item label="容量(托)">
          <el-input v-model="form.capacity" />
        </el-form-item>
        <template v-if="form.location_type === 'picking'">
          <el-form-item label="补货下限">
            <el-input v-model="form.replenish_min" placeholder="低于此值触发补货" />
          </el-form-item>
          <el-form-item label="补货上限">
            <el-input v-model="form.replenish_max" placeholder="补到此值，按整箱取整" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="drawer = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-drawer>

    <el-dialog v-model="batchOpen" title="批量新建库位" width="520px">
      <el-form label-width="92px">
        <el-form-item label="库区" required>
          <el-select v-model="batch.zone_id" style="width: 100%">
            <el-option v-for="z in zones" :key="z.id" :label="`${z.code} ${z.name}`" :value="z.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="编码前缀" required>
          <el-input v-model="batch.prefix" placeholder="如 F2-A-" />
        </el-form-item>
        <el-form-item label="起始序号">
          <el-input-number v-model="batch.start" :min="1" />
        </el-form-item>
        <el-form-item label="数量">
          <el-input-number v-model="batch.count" :min="1" :max="200" />
        </el-form-item>
        <el-form-item label="补零位数">
          <el-input-number v-model="batch.width" :min="1" :max="6" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="batch.location_type" style="width: 100%">
            <el-option v-for="t in TYPES" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="容量(托)">
          <el-input v-model="batch.capacity" />
        </el-form-item>
        <el-form-item label="预览">
          <div class="preview">
            <span v-for="c in batchPreview" :key="c">{{ c }}</span>
            <span v-if="batch.count > 5" class="more">…共 {{ batch.count }} 个</span>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchOpen = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitBatch">确认新建</el-button>
      </template>
    </el-dialog>
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
  flex-wrap: wrap;
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
.coord {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  width: 100%;
}
.hint {
  width: 100%;
  margin-top: 4px;
  font-size: 12px;
  color: #98a4bb;
}
.preview {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.preview span {
  padding: 3px 8px;
  border-radius: 6px;
  background: #f3f6fb;
  font-size: 12px;
  color: #3a4a68;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.more {
  color: #98a4bb;
}
</style>
