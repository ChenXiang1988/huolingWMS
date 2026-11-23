<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  createStaff,
  joinStaffTeam,
  leaveStaffTeam,
  listStaffs,
  listTeams,
  transferStaffTeam,
  updateStaff,
} from '@/api/wms_master_data'

const rows = ref<any[]>([])
const teams = ref<any[]>([])
const loading = ref(false)
const query = reactive<any>({ team_id: null, status: 1 })

const drawer = ref(false)
const editing = ref<number | null>(null)
const saving = ref(false)
const form = reactive<any>({ code: '', name: '', phone: '', user_id: null, status: 1 })

const teamDrawer = ref(false)
const teamStaff = ref<any>(null)
const targetTeam = ref<number | null>(null)

const teamName = (id: number | null) =>
  id == null ? '未编组' : teams.value.find((t) => t.id === id)?.name || `#${id}`

async function fetch() {
  loading.value = true
  try {
    const params: any = {}
    if (query.team_id) params.team_id = query.team_id
    if (query.status !== '') params.status = query.status
    const data: any = await listStaffs(params)
    rows.value = data || []
  } catch (e) {
    console.error(e)
    rows.value = []
  } finally {
    loading.value = false
  }
}

async function loadTeams() {
  const data: any = await listTeams({ status: 1 })
  teams.value = data || []
}

function openCreate() {
  editing.value = null
  Object.assign(form, { code: '', name: '', phone: '', user_id: null, status: 1 })
  drawer.value = true
}

function openEdit(row: any) {
  editing.value = row.id
  Object.assign(form, {
    code: row.code,
    name: row.name,
    phone: row.phone || '',
    user_id: row.user_id,
    status: row.status,
  })
  drawer.value = true
}

async function submit() {
  if (!form.code.trim() || !form.name.trim()) {
    ElMessage.warning('工号与姓名必填')
    return
  }
  saving.value = true
  try {
    if (editing.value) {
      await updateStaff(editing.value, {
        name: form.name,
        phone: form.phone,
        status: form.status,
      })
    } else {
      await createStaff(form)
    }
    ElMessage.success('已保存')
    drawer.value = false
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    saving.value = false
  }
}

function openTeam(row: any) {
  teamStaff.value = row
  targetTeam.value = row.team_id
  teamDrawer.value = true
}

async function submitTeam() {
  const staff = teamStaff.value
  try {
    if (!targetTeam.value) {
      if (!staff.team_id) {
        ElMessage.warning('请选择班组')
        return
      }
      await leaveStaffTeam(staff.id)
      ElMessage.success('已退出班组')
    } else if (!staff.team_id) {
      await joinStaffTeam(staff.id, targetTeam.value)
      ElMessage.success('已加入班组')
    } else {
      await transferStaffTeam(staff.id, targetTeam.value)
      ElMessage.success('已调组')
    }
    teamDrawer.value = false
    await fetch()
  } catch (e) {
    console.error(e)
  }
}

onMounted(async () => {
  await loadTeams()
  await fetch()
})
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="query.team_id" placeholder="班组" clearable style="width: 180px" @change="fetch">
        <el-option v-for="t in teams" :key="t.id" :label="t.name" :value="t.id" />
      </el-select>
      <el-select v-model="query.status" placeholder="状态" clearable style="width: 130px" @change="fetch">
        <el-option label="在职" :value="1" />
        <el-option label="离职" :value="0" />
      </el-select>
      <div class="spacer" />
      <el-button v-permission="'wms_master_data:staff:create'" type="primary" @click="openCreate">
        新建人员
      </el-button>
    </div>

    <el-table v-loading="loading" :data="rows" border stripe height="calc(100vh - 240px)">
      <el-table-column prop="code" label="工号" width="140" />
      <el-table-column prop="name" label="姓名" width="140" />
      <el-table-column prop="phone" label="联系方式" width="150" />
      <el-table-column label="绑定账号" width="120">
        <template #default="{ row }">{{ row.user_id ? `#${row.user_id}` : '临时工' }}</template>
      </el-table-column>
      <el-table-column label="班组" min-width="160">
        <template #default="{ row }">{{ teamName(row.team_id) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small" effect="light">
            {{ row.status === 1 ? '在职' : '离职' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'wms_master_data:staff:edit'" link type="primary" @click="openEdit(row)">
            编辑
          </el-button>
          <el-button v-permission="'wms_master_data:staff:edit'" link type="primary" @click="openTeam(row)">
            班组
          </el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty">还没有人员档案。正式员工绑定登录账号，临时工留空即可。</div>
      </template>
    </el-table>

    <el-drawer v-model="drawer" :title="editing ? '编辑人员' : '新建人员'" size="480px">
      <el-form label-width="88px">
        <el-form-item label="工号" required>
          <el-input v-model="form.code" :disabled="!!editing" />
        </el-form-item>
        <el-form-item label="姓名" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="联系方式">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item label="绑定账号">
          <el-input-number
            v-model="form.user_id"
            :min="1"
            :disabled="!!editing"
            controls-position="right"
            placeholder="留空=临时工"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="在职状态">
          <el-radio-group v-model="form.status">
            <el-radio :value="1">在职</el-radio>
            <el-radio :value="0">离职</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="drawer = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-drawer>

    <el-drawer v-model="teamDrawer" title="班组归属" size="420px">
      <el-form label-width="88px">
        <el-form-item label="人员">{{ teamStaff?.name }}</el-form-item>
        <el-form-item label="当前班组">{{ teamName(teamStaff?.team_id) }}</el-form-item>
        <el-form-item label="目标班组">
          <el-select v-model="targetTeam" clearable placeholder="留空表示退出班组" style="width: 100%">
            <el-option v-for="t in teams" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="teamDrawer = false">取消</el-button>
        <el-button type="primary" @click="submitTeam">保存</el-button>
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
