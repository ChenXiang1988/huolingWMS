<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  createTeam,
  listStaffs,
  listTeams,
  setTeamLeader,
  toggleTeam,
  updateTeam,
} from '@/api/wms_master_data'

const TYPES = [
  { value: 'receiving', label: '收货' },
  { value: 'putaway', label: '上架' },
  { value: 'picking', label: '拣货' },
  { value: 'sorting', label: '分播' },
  { value: 'checking', label: '复核' },
  { value: 'shipping', label: '发运' },
  { value: 'internal_ops', label: '库内作业' },
  { value: 'other', label: '其他' },
]

const rows = ref<any[]>([])
const staffs = ref<any[]>([])
const loading = ref(false)
const query = reactive<any>({ status: '' })

const drawer = ref(false)
const editing = ref<number | null>(null)
const saving = ref(false)
const form = reactive<any>({ code: '', name: '', function_type: 'other', remark: '' })

const leaderDrawer = ref(false)
const leaderTeam = ref<any>(null)
const leaderId = ref<number | null>(null)

const staffName = (id: number | null) =>
  id == null ? '—' : staffs.value.find((s) => s.id === id)?.name || `#${id}`
const typeLabel = (v: string) => TYPES.find((t) => t.value === v)?.label || v

async function fetch() {
  loading.value = true
  try {
    const params: any = {}
    if (query.status !== '') params.status = query.status
    const data: any = await listTeams(params)
    rows.value = data || []
  } catch (e) {
    console.error(e)
    rows.value = []
  } finally {
    loading.value = false
  }
}

async function loadStaffs() {
  const data: any = await listStaffs({ status: 1 })
  staffs.value = data || []
}

function openCreate() {
  editing.value = null
  Object.assign(form, { code: '', name: '', function_type: 'other', remark: '' })
  drawer.value = true
}

function openEdit(row: any) {
  editing.value = row.id
  Object.assign(form, {
    code: row.code,
    name: row.name,
    function_type: row.function_type,
    remark: row.remark || '',
  })
  drawer.value = true
}

async function submit() {
  if (!form.code.trim() || !form.name.trim()) {
    ElMessage.warning('编码与名称必填')
    return
  }
  saving.value = true
  try {
    if (editing.value) await updateTeam(editing.value, form)
    else await createTeam(form)
    ElMessage.success('已保存')
    drawer.value = false
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    saving.value = false
  }
}

function openLeader(row: any) {
  leaderTeam.value = row
  leaderId.value = row.leader_staff_id
  leaderDrawer.value = true
}

async function submitLeader() {
  try {
    await setTeamLeader(leaderTeam.value.id, leaderId.value)
    ElMessage.success('班长已更新')
    leaderDrawer.value = false
    await fetch()
  } catch (e) {
    console.error(e)
  }
}

async function toggle(row: any) {
  try {
    await toggleTeam(row.id, row.status !== 1)
    ElMessage.success(row.status === 1 ? '已停用' : '已启用')
    await fetch()
  } catch (e) {
    console.error(e)
  }
}

onMounted(async () => {
  await fetch()
  await loadStaffs()
})
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="query.status" placeholder="状态" clearable style="width: 130px" @change="fetch">
        <el-option label="启用" :value="1" />
        <el-option label="停用" :value="0" />
      </el-select>
      <div class="spacer" />
      <el-button v-permission="'wms_master_data:team:create'" type="primary" @click="openCreate">
        新建班组
      </el-button>
    </div>

    <el-table v-loading="loading" :data="rows" border stripe height="calc(100vh - 240px)">
      <el-table-column prop="code" label="编码" width="150" />
      <el-table-column prop="name" label="班组名称" min-width="180" />
      <el-table-column label="职能" width="120">
        <template #default="{ row }">
          <el-tag size="small" effect="light">{{ typeLabel(row.function_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="班长" width="130">
        <template #default="{ row }">{{ staffName(row.leader_staff_id) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small" effect="light">
            {{ row.status === 1 ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'wms_master_data:team:edit'" link type="primary" @click="openEdit(row)">
            编辑
          </el-button>
          <el-button v-permission="'wms_master_data:team:edit'" link type="primary" @click="openLeader(row)">
            班长
          </el-button>
          <el-button
            v-permission="'wms_master_data:team:edit'"
            link
            :type="row.status === 1 ? 'danger' : 'success'"
            @click="toggle(row)"
          >
            {{ row.status === 1 ? '停用' : '启用' }}
          </el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty">还没有班组。按收货、拣货、复核等职能建组后即可编入人员。</div>
      </template>
    </el-table>

    <el-drawer v-model="drawer" :title="editing ? '编辑班组' : '新建班组'" size="480px">
      <el-form label-width="88px">
        <el-form-item label="编码" required>
          <el-input v-model="form.code" :disabled="!!editing" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="职能">
          <el-select v-model="form.function_type" style="width: 100%">
            <el-option v-for="t in TYPES" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="drawer = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-drawer>

    <el-drawer v-model="leaderDrawer" title="指定班长" size="420px">
      <el-form label-width="88px">
        <el-form-item label="班组">{{ leaderTeam?.name }}</el-form-item>
        <el-form-item label="班长">
          <el-select v-model="leaderId" clearable placeholder="留空表示清空" style="width: 100%">
            <el-option
              v-for="s in staffs.filter((x) => x.team_id === leaderTeam?.id)"
              :key="s.id"
              :label="`${s.code} ${s.name}`"
              :value="s.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="leaderDrawer = false">取消</el-button>
        <el-button type="primary" @click="submitLeader">保存</el-button>
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
