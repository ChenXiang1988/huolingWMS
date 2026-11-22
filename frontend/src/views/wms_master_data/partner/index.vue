<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createPartner, listOwners, listPartners } from '@/api/wms_master_data'

const TYPES = [
  { value: 'supplier', label: '供应商' },
  { value: 'customer', label: '客户' },
]

const owners = ref<any[]>([])
const rows = ref<any[]>([])
const loading = ref(false)
const query = reactive<any>({ owner_id: '', partner_type: '' })

const drawer = ref(false)
const saving = ref(false)
const form = reactive<any>({
  owner_id: null, code: '', name: '', partner_type: 'supplier', contact: '', phone: '',
})

const ownerName = (id: number) => owners.value.find((o) => o.id === id)?.name || `#${id}`

async function loadOwners() {
  const data: any = await listOwners({ page: 1, page_size: 200 })
  owners.value = data?.items || []
  if (!query.owner_id && owners.value.length) query.owner_id = owners.value[0].id
}

async function fetch() {
  loading.value = true
  try {
    const params: any = {}
    if (query.owner_id) params.owner_id = query.owner_id
    if (query.partner_type) params.partner_type = query.partner_type
    const data: any = await listPartners(params)
    rows.value = data || []
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
    code: '', name: '', partner_type: 'supplier', contact: '', phone: '',
  })
  drawer.value = true
}

async function submit() {
  if (!form.owner_id || !form.code.trim() || !form.name.trim()) {
    ElMessage.warning('货主、编码与名称必填')
    return
  }
  saving.value = true
  try {
    await createPartner(form)
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
  await loadOwners()
  await fetch()
})
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="query.owner_id" placeholder="货主" clearable style="width: 180px" @change="fetch">
        <el-option v-for="o in owners" :key="o.id" :label="`${o.code} ${o.name}`" :value="o.id" />
      </el-select>
      <el-select v-model="query.partner_type" placeholder="类型" clearable style="width: 130px" @change="fetch">
        <el-option v-for="t in TYPES" :key="t.value" :label="t.label" :value="t.value" />
      </el-select>
      <div class="spacer" />
      <el-button v-permission="'wms_master_data:partner:create'" type="primary" @click="openCreate">
        新建合作方
      </el-button>
    </div>

    <el-table v-loading="loading" :data="rows" border stripe height="calc(100vh - 240px)">
      <el-table-column prop="code" label="编码" width="150" />
      <el-table-column prop="name" label="名称" min-width="200" show-overflow-tooltip />
      <el-table-column label="类型" width="110">
        <template #default="{ row }">
          <el-tag :type="row.partner_type === 'supplier' ? 'info' : 'success'" size="small" effect="light">
            {{ TYPES.find((t) => t.value === row.partner_type)?.label || row.partner_type }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="所属货主" min-width="160">
        <template #default="{ row }">{{ ownerName(row.owner_id) }}</template>
      </el-table-column>
      <el-table-column prop="contact" label="联系人" width="110" />
      <el-table-column prop="phone" label="电话" width="140" />
      <template #empty>
        <div class="empty">还没有合作方。供应商与客户都在这里登记，入库与逆向会用到。</div>
      </template>
    </el-table>

    <el-drawer v-model="drawer" title="新建合作方" size="480px">
      <el-form label-width="88px">
        <el-form-item label="货主" required>
          <el-select v-model="form.owner_id" style="width: 100%">
            <el-option v-for="o in owners" :key="o.id" :label="`${o.code} ${o.name}`" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.partner_type">
            <el-radio v-for="t in TYPES" :key="t.value" :value="t.value">{{ t.label }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="编码" required>
          <el-input v-model="form.code" placeholder="货主内部的供应商或客户编码" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="form.contact" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" />
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
.empty {
  padding: 28px 0;
  color: #98a4bb;
  font-size: 13px;
}
</style>
