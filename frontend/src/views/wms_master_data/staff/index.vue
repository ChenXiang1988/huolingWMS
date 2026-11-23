<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  bulkStaffTeam,
  confirmStaffLeave,
  joinStaffTeam,
  leaveStaffTeam,
  listStaffs,
  listTeams,
  setStaffCerts,
  setStaffSkills,
  staffLogs,
  transferStaffTeam,
  updateStaff,
} from '@/api/wms_master_data'

const route = useRoute()
const router = useRouter()

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
const CERTS = [
  { value: 'forklift', label: '叉车证' },
  { value: 'quality_inspector', label: '质检员证' },
]

const rows = ref<any[]>([])
const teams = ref<any[]>([])
const logs = ref<any[]>([])
const loading = ref(false)
const tab = ref('all')
const expanded = ref(false)
const selected = ref<number[]>([])
const bulkTarget = ref<number | null>(null)

const query = reactive<any>({
  keyword: '', team_id: null, role: '', leader_flag: '', process_code: '',
  cert_type: '', config_state: '', employment_state: '', bound_state: '',
  cert_expiry: '', last_op_from: '', last_op_to: '',
})

const drawer = ref(false)
const editing = ref<number | null>(null)
const readOnly = ref(false)
const saving = ref(false)
const form = reactive<any>({
  code: '', name: '', phone: '', user_id: null, account_status: null, role: '', status: 1,
  team_id: null, leader: false, employment_state: 'active',
  left_at: null, left_pending_at: null, bound_unit: null,
  skills: [], certs: [], quality_cert: 0, quality_team: '',
})

const roles = computed(() =>
  [...new Set(rows.value.map((r) => r.role).filter(Boolean))] as string[],
)
const chips = computed(() => {
  const labels: Record<string, string> = {
    keyword: '关键词', team_id: '班组', role: '角色', leader_flag: '组内身份',
    process_code: '可做工序', cert_type: '认证名称', config_state: '配置状态',
    employment_state: '在职状态', bound_state: '绑定单元', cert_expiry: '认证到期',
    last_op_from: '最近操作起', last_op_to: '最近操作止',
  }
  return Object.keys(labels)
    .filter((k) => query[k] !== '' && query[k] != null)
    .map((k) => ({
      key: k,
      label: labels[k],
      value: k === 'team_id'
        ? teams.value.find((t) => t.id === query[k])?.name || `#${query[k]}`
        : String(query[k]),
    }))
})
const labelOf = (list: { value: string; label: string }[], v: string) =>
  list.find((x) => x.value === v)?.label || v
const teamName = (id: number | null) =>
  id == null ? '未分组' : teams.value.find((t) => t.id === id)?.name || `#${id}`

async function fetch() {
  loading.value = true
  try {
    const params: any = {}
    if (tab.value === 'on') params.status = 1
    else if (tab.value === 'off') params.status = 0
    for (const key of Object.keys(query)) {
      if (query[key] !== '' && query[key] != null) params[key] = query[key]
    }
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

function resetQuery() {
  Object.keys(query).forEach((k) => { query[k] = k === 'team_id' || k === 'status' ? null : '' })
  fetch()
}

async function openDrawer(row: any, view: boolean) {
  editing.value = row.id
  readOnly.value = view
  Object.assign(form, {
    code: row.code, name: row.name, phone: row.phone || '', user_id: row.user_id,
    account_status: row.account_status, role: row.role || '', status: row.status, team_id: row.team_id,
    leader: !!row.leader, employment_state: row.employment_state,
    left_at: row.left_at, left_pending_at: row.left_pending_at,
    bound_unit: row.bound_unit || null,
    skills: [...(row.skills || [])],
    certs: (row.certs || []).map((c: any) => ({
      cert_type: c.cert_type,
      expire_on: c.expire_on || '',
    })),
    quality_cert: row.quality_cert || 0, quality_team: row.quality_team || '',
  })
  try {
    const data: any = await staffLogs(row.id)
    logs.value = data || []
  } catch (e) {
    logs.value = []
  }
  drawer.value = true
}

async function submit() {
  if (!form.code.trim()) {
    ElMessage.warning('工号必填')
    return
  }
  const staffId = editing.value
  if (staffId === null) return
  saving.value = true
  try {
    await updateStaff(staffId, {
      status: form.status, role: form.role || null,
      quality_cert: form.quality_cert, quality_team: form.quality_team || null,
    })
    if (form.employment_state !== 'left') {
      await setStaffSkills(staffId, form.skills)
      await setStaffCerts(staffId, form.certs.map((c: any) => ({
        cert_type: c.cert_type, expire_on: c.expire_on || null,
      })))
      const row = rows.value.find((r) => r.id === staffId)
      if (!form.leader && form.team_id !== row?.team_id) {
        if (!form.team_id && row?.team_id) await leaveStaffTeam(staffId)
        else if (form.team_id && !row?.team_id) await joinStaffTeam(staffId, form.team_id)
        else if (form.team_id) await transferStaffTeam(staffId, form.team_id)
      }
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

async function finishLeave(row: any) {
  try {
    await ElMessageBox.confirm('确认在办任务已回池或改派、绑定单元已释放？确认后离职生效且不可回退。', '离职生效', {
      type: 'warning',
    })
    await confirmStaffLeave(row.id)
    ElMessage.success('已离职')
    drawer.value = false
    await fetch()
  } catch (e) {
    console.error(e)
  }
}

function goTransfer(row: any) {
  router.push({ path: '/wms-tasking/task', query: { assignee: String(row.id) } })
}

async function applyBulk() {
  if (!selected.value.length || !bulkTarget.value) {
    ElMessage.warning('请先勾选人员并选择目标班组')
    return
  }
  try {
    const res: any = await bulkStaffTeam(selected.value, bulkTarget.value)
    const skipped = res?.skipped || []
    ElMessage.success(
      `已调整 ${res?.moved?.length || 0} 人；跳过 ${skipped.length} 人` +
      (skipped.length ? '：' + skipped.map((s: any) => `#${s.staff_id} ${s.reason}`).join('；') : ''),
    )
    selected.value = []
    await fetch()
  } catch (e) {
    console.error(e)
  }
}

function onSelect(rowsSelected: any[]) {
  selected.value = rowsSelected.map((r) => r.id)
}

onMounted(async () => {
  const teamId = route.query.team_id
  if (teamId) query.team_id = Number(teamId)
  await loadTeams()
  await fetch()
})
</script>

<template>
  <div class="page">
    <el-tabs v-model="tab" @tab-change="fetch">
      <el-tab-pane label="全部" name="all" />
      <el-tab-pane label="在岗" name="on" />
      <el-tab-pane label="不在岗" name="off" />
    </el-tabs>

    <div class="query">
      <el-input v-model="query.keyword" placeholder="工号／姓名／手机／绑定单元" clearable style="width: 190px" />
      <el-select v-model="query.team_id" placeholder="班组" clearable style="width: 150px">
        <el-option v-for="t in teams" :key="t.id" :label="t.name" :value="t.id" />
      </el-select>
      <el-select v-model="query.role" placeholder="角色" clearable style="width: 130px">
        <el-option v-for="r in roles" :key="r" :label="r" :value="r" />
      </el-select>
      <template v-if="expanded">
        <el-select v-model="query.leader_flag" placeholder="组内身份" clearable style="width: 130px">
          <el-option label="班组长" value="leader" />
          <el-option label="组员" value="member" />
        </el-select>
        <el-select v-model="query.process_code" placeholder="可做工序" clearable style="width: 140px">
          <el-option v-for="t in TYPES" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
        <el-select v-model="query.cert_type" placeholder="认证名称" clearable style="width: 140px">
          <el-option v-for="c in CERTS" :key="c.value" :label="c.label" :value="c.value" />
        </el-select>
        <el-select v-model="query.config_state" placeholder="配置状态" clearable style="width: 130px">
          <el-option label="已配置" value="configured" />
          <el-option label="待配置" value="pending" />
        </el-select>
        <el-select v-model="query.employment_state" placeholder="在职状态" clearable style="width: 130px">
          <el-option label="在职" value="active" />
          <el-option label="待离职" value="pending" />
          <el-option label="已离职" value="left" />
        </el-select>
        <el-select v-model="query.bound_state" placeholder="绑定单元" clearable style="width: 130px">
          <el-option label="已绑定" value="bound" />
          <el-option label="未绑定" value="unbound" />
        </el-select>
        <el-select v-model="query.cert_expiry" placeholder="认证到期" clearable style="width: 140px">
          <el-option label="已过期" value="expired" />
          <el-option label="30 天内到期" value="within_30" />
          <el-option label="未到期" value="valid" />
        </el-select>
        <el-date-picker
          v-model="query.last_op_from" type="datetime" placeholder="操作起"
          value-format="YYYY-MM-DDTHH:mm:ss" style="width: 175px"
        />
        <el-date-picker
          v-model="query.last_op_to" type="datetime" placeholder="操作止"
          value-format="YYYY-MM-DDTHH:mm:ss" style="width: 175px"
        />
      </template>
      <el-button type="primary" @click="fetch">查询</el-button>
      <el-button @click="resetQuery">重置</el-button>
      <el-button link @click="expanded = !expanded">{{ expanded ? '收起全部条件' : '展开全部条件' }}</el-button>
    </div>

    <div v-if="chips.length" class="chips">
      <el-tag
        v-for="c in chips" :key="c.key" closable size="small"
        @close="query[c.key] = (c.key === 'team_id' ? null : ''); fetch()"
      >{{ c.label }}：{{ c.value }}</el-tag>
    </div>

    <div class="toolbar">
      <template v-if="selected.length">
        <el-select v-model="bulkTarget" placeholder="目标班组（可留空移出）" clearable style="width: 220px">
          <el-option v-for="t in teams" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
        <el-button
          v-permission="'wms_master_data:staff:bulk-team'" type="primary"
          @click="applyBulk"
        >调整班组（{{ selected.length }} 人）</el-button>
      </template>
      <div class="spacer" />
      <el-button v-permission="'wms_master_data:staff:list'" @click="ElMessage.info('导出字段与格式尚未定稿')">导出</el-button>
    </div>

    <el-table v-loading="loading" :data="rows" border stripe height="calc(100vh - 340px)" @selection-change="onSelect">
      <el-table-column type="selection" width="45" />
      <el-table-column prop="code" label="工号" width="120" />
      <el-table-column prop="name" label="姓名" width="100" />
      <el-table-column label="仓库" width="90"><template #default>当前仓</template></el-table-column>
      <el-table-column label="班组" min-width="170">
        <template #default="{ row }">
          {{ teamName(row.team_id) }}
          <el-tag v-if="row.leader" size="small" type="warning" effect="light">班组长</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="role" label="角色" width="100" />
      <el-table-column label="可做工序" min-width="150">
        <template #default="{ row }">{{ (row.skills || []).map((s: string) => labelOf(TYPES, s)).join('、') || '—' }}</template>
      </el-table-column>
      <el-table-column label="认证" min-width="140">
        <template #default="{ row }">
          <span v-if="!row.certs?.length">—</span>
          <span v-else>
            {{ row.certs.map((c: any) => labelOf(CERTS, c.cert_type)).join('、') }}
            <el-tag v-if="row.cert_expiry === 'expired'" size="small" type="danger">已过期</el-tag>
            <el-tag v-else-if="row.cert_expiry === 'within_30'" size="small" type="warning">30 天内到期</el-tag>
          </span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small" effect="light">
            {{ row.status === 1 ? '在岗' : '不在岗' }}
          </el-tag>
          <el-tag v-if="row.employment_state === 'left'" size="small" type="info">已离职</el-tag>
          <el-tag v-else-if="row.employment_state === 'pending'" size="small" type="warning">待离职</el-tag>
          <el-tag v-if="row.config_state === 'pending'" size="small" type="warning">待配置</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="账号状态" width="100">
        <template #default="{ row }">
          <el-tag
            v-if="row.account_status === 1 || row.account_status === 0"
            :type="row.account_status === 1 ? 'success' : 'danger'" size="small" effect="light"
          >{{ row.account_status === 1 ? '启用' : '禁用' }}</el-tag>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="绑定单元" width="110">
        <template #default="{ row }">{{ row.bound_unit || '未登录' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="row.user_id" v-permission="'wms_master_data:staff:edit'"
            link type="primary" @click="openDrawer(row, false)"
          >编辑</el-button>
          <el-button link type="primary" @click="openDrawer(row, true)">查看</el-button>
        </template>
      </el-table-column>
      <template #empty><div class="empty">当前筛选条件下无结果。</div></template>
    </el-table>

    <el-drawer v-model="drawer" :title="readOnly ? '查看人员' : '编辑人员'" size="560px">
      <el-form label-width="96px" :disabled="readOnly">
        <el-form-item label="工号"><el-input v-model="form.code" disabled /></el-form-item>
        <el-form-item label="员工账号"><span>已绑定员工账号，不可更换</span></el-form-item>
        <el-form-item label="姓名"><span>{{ form.name || '—' }}</span></el-form-item>
        <el-form-item label="手机号"><span>{{ form.phone || '—' }}</span></el-form-item>
        <el-form-item label="账号状态">
          <span>{{ form.account_status === 1 ? '启用' : form.account_status === 0 ? '禁用' : '—' }}</span>
        </el-form-item>
        <el-form-item label="角色"><el-input v-model="form.role" placeholder="用户中心同步" /></el-form-item>
        <el-form-item label="仓库"><span>当前仓（单仓）</span></el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio :value="1">在岗</el-radio>
            <el-radio :value="0">不在岗</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="绑定单元">{{ form.bound_unit || '未登录' }}</el-form-item>
      </el-form>

      <el-divider content-position="left">班组归属</el-divider>
      <el-form label-width="96px" :disabled="readOnly">
        <el-form-item label="所属班组">
          <el-select v-model="form.team_id" clearable :disabled="form.leader" style="width: 100%" placeholder="待配置">
            <el-option
              v-for="t in teams" :key="t.id" :label="`${t.name}${t.floor_no ? ` · ${t.floor_no}F` : ''}`"
              :value="t.id"
            />
          </el-select>
          <span v-if="form.leader" class="hint">班组长请先在班组视图更换</span>
        </el-form-item>
        <el-form-item label="配置状态">
          {{ form.team_id && form.skills.length ? '已配置' : '待配置' }}
        </el-form-item>
      </el-form>

      <template v-if="form.employment_state === 'pending'">
        <el-divider content-position="left">离职处置</el-divider>
        <div class="pending">
          待离职，仍有在办任务或绑定单元，离职暂未生效。
          <el-button
            v-permission="'wms_master_data:staff:leave'" type="danger" size="small"
            @click="finishLeave({ id: editing })"
          >全部回池并确认离职</el-button>
          <el-button size="small" @click="goTransfer({ id: editing })">去作业任务页改派</el-button>
        </div>
      </template>

      <el-divider content-position="left">可做工序</el-divider>
      <el-select v-model="form.skills" multiple :disabled="readOnly" style="width: 100%">
        <el-option v-for="t in TYPES" :key="t.value" :label="t.label" :value="t.value" />
      </el-select>

      <el-divider content-position="left">认证与质检持证</el-divider>
      <div v-for="(c, i) in form.certs" :key="i" class="cert-row">
        <el-select v-model="c.cert_type" :disabled="readOnly" style="width: 160px">
          <el-option v-for="x in CERTS" :key="x.value" :label="x.label" :value="x.value" />
        </el-select>
        <el-date-picker v-model="c.expire_on" type="date" value-format="YYYY-MM-DD" :disabled="readOnly" />
        <el-button :disabled="readOnly" link type="danger" @click="form.certs.splice(i, 1)">移除</el-button>
      </div>
      <el-button :disabled="readOnly" size="small" @click="form.certs.push({ cert_type: 'forklift', expire_on: '' })">
        添加认证
      </el-button>
      <el-form label-width="96px" :disabled="readOnly">
        <el-form-item label="质检持证">
          <el-radio-group v-model="form.quality_cert">
            <el-radio :value="0">未持证</el-radio>
            <el-radio :value="1">持证</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.quality_cert === 1" label="质检组">
          <el-input v-model="form.quality_team" />
        </el-form-item>
      </el-form>

      <el-divider content-position="left">最近记录</el-divider>
      <div v-if="!logs.length" class="hint">暂无记录</div>
      <div v-for="l in logs" :key="l.id" class="log-row">
        {{ l.occurred_at }}
        <template v-if="l.kind === 'team'">
          {{ teamName(l.from_team_id) }} → {{ l.to_team_id ? teamName(l.to_team_id) : '未分组' }}（{{ l.reason }}）
        </template>
        <template v-else>{{ l.reason || l.kind }}</template>
      </div>

      <template #footer>
        <el-button @click="drawer = false">关闭</el-button>
        <el-button v-if="!readOnly" type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.page { padding: 4px; }
.query { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 8px 0; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.spacer { flex: 1; }
.empty { padding: 28px 0; color: #98a4bb; font-size: 13px; }
.hint { color: #98a4bb; font-size: 12px; }
.pending { padding: 10px 12px; background: #fdf6ec; border-radius: 4px; font-size: 13px; display: flex; gap: 8px; align-items: center; }
.cert-row { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; }
.log-row { padding: 4px 0; color: #5c6675; font-size: 12px; }
</style>
