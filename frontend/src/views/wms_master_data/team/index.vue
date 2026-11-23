<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createTeam,
  deleteTeam,
  listStaffs,
  listTeams,
  listZones,
  teamCoverage,
  toggleTeam,
  updateTeam,
} from '@/api/wms_master_data'

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
const rows = ref<any[]>([])
const staffs = ref<any[]>([])
const zones = ref<any[]>([])
const coverage = ref<any>({ total: 0, no_team: 0, multi_team: 0 })
const loading = ref(false)
const tab = ref('all')
const query = reactive<any>({
  keyword: '', leader_name: '', floor_no: '', process_code: '',
  zone_id: '', updated_from: '', updated_to: '',
})

const drawer = ref(false)
const editing = ref<number | null>(null)
const saving = ref(false)
const form = reactive<any>({
  name: '', function_type: 'other', leader_staff_id: null, floor_no: null,
  zone_ids: [], dispatch_limit_default: null, status: 1, remark: '',
})

const floors = computed(() =>
  [...new Set(zones.value.filter((z) => z.status === 1).map((z) => z.floor_no))]
    .sort((a, b) => a - b),
)
const zoneOptions = computed(() =>
  zones.value.filter((z) => z.status === 1 && (!form.floor_no || z.floor_no === form.floor_no)),
)
const leaderOptions = computed(() =>
  staffs.value.filter(
    (s) => s.status === 1 && s.leader !== true && (!editing.value || s.team_id === editing.value),
  ),
)
const chips = computed(() => {
  const labels: Record<string, string> = {
    keyword: '关键词', leader_name: '班组长', floor_no: '楼层', process_code: '可承接工序',
    zone_id: '管辖区域', updated_from: '更新时间起', updated_to: '更新时间止',
  }
  return Object.keys(labels)
    .filter((k) => query[k] !== '' && query[k] != null)
    .map((k) => ({ key: k, label: labels[k], value: String(query[k]) }))
})

const typeLabel = (v: string) => TYPES.find((t) => t.value === v)?.label || v
const zoneNames = (ids: number[] = []) =>
  ids.map((id) => zones.value.find((z) => z.id === id)?.name || `#${id}`).join('、') || '—'
const skillsText = (skills: string[] = []) =>
  skills.length ? skills.map((s) => typeLabel(s)).join('、') : '—'

async function fetch() {
  loading.value = true
  try {
    const params: any = {}
    if (tab.value === 'enabled') params.status = 1
    else if (tab.value === 'disabled') params.status = 0
    else if (tab.value.startsWith('floor:')) params.floor_no = Number(tab.value.slice(6))
    for (const key of ['keyword', 'leader_name', 'floor_no', 'process_code', 'zone_id', 'updated_from', 'updated_to']) {
      if (query[key] !== '' && query[key] != null) params[key] = query[key]
    }
    const data: any = await listTeams(params)
    rows.value = data || []
  } catch (e) {
    console.error(e)
    rows.value = []
  } finally {
    loading.value = false
  }
}

async function loadCoverage() {
  try {
    const data: any = await teamCoverage()
    coverage.value = data || coverage.value
  } catch (e) {
    console.error(e)
  }
}

async function loadStaffs() {
  const data: any = await listStaffs({ status: 1 })
  staffs.value = data || []
}

function openCreate() {
  editing.value = null
  Object.assign(form, {
    name: '', function_type: 'other', leader_staff_id: null,
    floor_no: floors.value[0] ?? null, zone_ids: [], dispatch_limit_default: null,
    status: 1, remark: '',
  })
  drawer.value = true
}

function openEdit(row: any) {
  editing.value = row.id
  Object.assign(form, {
    name: row.name, function_type: row.function_type,
    leader_staff_id: row.leader_staff_id, floor_no: row.floor_no,
    zone_ids: [...(row.zone_ids || [])],
    dispatch_limit_default: row.dispatch_limit_default,
    status: row.status, remark: row.remark || '',
  })
  drawer.value = true
}

function onFloorChange() {
  const before = form.zone_ids.length
  form.zone_ids = form.zone_ids.filter((id: number) =>
    zones.value.some((z) => z.id === id && z.floor_no === form.floor_no),
  )
  const cleared = before - form.zone_ids.length
  if (cleared) ElMessage.info(`已清空 ${cleared} 个不属于该楼层的区域`)
}

function resetQuery() {
  Object.keys(query).forEach((k) => { query[k] = '' })
  fetch()
}

async function submit() {
  const name = form.name.trim()
  if (!name || name.length > 20) {
    ElMessage.warning('班组名称必填且不超过 20 字')
    return
  }
  if (!form.floor_no) {
    ElMessage.warning('请选择楼层')
    return
  }
  if (!form.zone_ids.length) {
    ElMessage.warning('至少选择一个管辖区域')
    return
  }
  if (!form.leader_staff_id) {
    ElMessage.warning('请从候选中选择班组长')
    return
  }
  saving.value = true
  try {
    const payload = {
      name, function_type: form.function_type, leader_staff_id: form.leader_staff_id,
      floor_no: form.floor_no, zone_ids: form.zone_ids,
      dispatch_limit_default: form.dispatch_limit_default, status: form.status,
      remark: form.remark || null,
    }
    if (editing.value) await updateTeam(editing.value, payload)
    else await createTeam(payload)
    ElMessage.success('已保存')
    drawer.value = false
    await Promise.all([fetch(), loadCoverage(), loadStaffs()])
  } catch (e) {
    console.error(e)
  } finally {
    saving.value = false
  }
}

async function remove(row: any) {
  try {
    await ElMessageBox.confirm(`确认删除班组「${row.name}」？最后一名班组长将转为未分组。`, '删除班组', {
      type: 'warning',
    })
    await deleteTeam(row.id)
    ElMessage.success('已删除')
    await Promise.all([fetch(), loadCoverage(), loadStaffs()])
  } catch (e) {
    console.error(e)
  }
}

async function toggle(row: any) {
  try {
    const res: any = await toggleTeam(row.id, row.status !== 1)
    const affected = res?.affected_staff_ids?.length || 0
    ElMessage.success(
      row.status === 1
        ? `已停用；${affected} 名成员移出候选，已派未开工任务需由任务中心退回待派`
        : '已启用，成员重新进入候选',
    )
    await Promise.all([fetch(), loadCoverage()])
  } catch (e) {
    console.error(e)
  }
}

function viewMembers(row: any) {
  router.push({ path: '/wms-master-data/staff', query: { team_id: String(row.id) } })
}

onMounted(async () => {
  const data: any = await listZones()
  zones.value = data || []
  await Promise.all([fetch(), loadCoverage(), loadStaffs()])
})
</script>

<template>
  <div class="page">
    <el-tabs v-model="tab" @tab-change="fetch">
      <el-tab-pane label="全部" name="all" />
      <el-tab-pane v-for="f in floors" :key="f" :label="`${f}F`" :name="`floor:${f}`" />
      <el-tab-pane label="启用" name="enabled" />
      <el-tab-pane label="停用" name="disabled" />
    </el-tabs>

    <div class="query">
      <el-input v-model="query.keyword" placeholder="编号或名称" clearable style="width: 180px" />
      <el-input v-model="query.leader_name" placeholder="班组长" clearable style="width: 140px" />
      <el-select v-model="query.floor_no" placeholder="楼层" clearable style="width: 110px">
        <el-option v-for="f in floors" :key="f" :label="`${f}F`" :value="f" />
      </el-select>
      <el-select v-model="query.process_code" placeholder="可承接工序" clearable style="width: 140px">
        <el-option v-for="t in TYPES" :key="t.value" :label="t.label" :value="t.value" />
      </el-select>
      <el-select v-model="query.zone_id" placeholder="管辖区域" clearable style="width: 150px">
        <el-option v-for="z in zones.filter((x) => x.status === 1)" :key="z.id" :label="z.name" :value="z.id" />
      </el-select>
      <el-date-picker
        v-model="query.updated_from" type="datetime" placeholder="更新起" value-format="YYYY-MM-DDTHH:mm:ss"
        style="width: 175px"
      />
      <el-date-picker
        v-model="query.updated_to" type="datetime" placeholder="更新止" value-format="YYYY-MM-DDTHH:mm:ss"
        style="width: 175px"
      />
      <el-button type="primary" @click="fetch">查询</el-button>
      <el-button @click="resetQuery">重置</el-button>
    </div>

    <div v-if="chips.length" class="chips">
      <el-tag v-for="c in chips" :key="c.key" closable size="small" @close="query[c.key] = ''; fetch()">
        {{ c.label }}：{{ c.value }}
      </el-tag>
    </div>

    <div class="coverage">
      本仓 {{ coverage.total }} 个启用区域，无组 {{ coverage.no_team }} 个，多组共管 {{ coverage.multi_team }} 个
    </div>

    <div class="toolbar">
      <div class="spacer" />
      <el-button v-permission="'wms_master_data:team:create'" type="primary" @click="openCreate">新建班组</el-button>
      <el-button v-permission="'wms_master_data:team:list'" @click="ElMessage.info('导出字段与格式尚未定稿')">导出</el-button>
    </div>

    <el-table v-loading="loading" :data="rows" border stripe height="calc(100vh - 320px)">
      <el-table-column prop="code" label="班组编号" width="110" />
      <el-table-column prop="name" label="班组名称" min-width="150" />
      <el-table-column label="仓库" width="100"><template #default>当前仓</template></el-table-column>
      <el-table-column label="楼层" width="80">
        <template #default="{ row }">{{ row.floor_no ? `${row.floor_no}F` : '—' }}</template>
      </el-table-column>
      <el-table-column label="管辖区域" min-width="180">
        <template #default="{ row }">{{ zoneNames(row.zone_ids) }}</template>
      </el-table-column>
      <el-table-column prop="leader_name" label="班组长" width="100" />
      <el-table-column prop="member_count" label="成员数" width="85" />
      <el-table-column prop="active_count" label="在岗" width="70" />
      <el-table-column prop="dispatchable_count" label="可派人数" width="95" />
      <el-table-column label="可承接工序" min-width="160">
        <template #default="{ row }">{{ skillsText(row.skills) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="85">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small" effect="light">
            {{ row.status === 1 ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="250" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'wms_master_data:team:edit'" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="primary" @click="viewMembers(row)">成员</el-button>
          <el-button
            v-permission="'wms_master_data:team:edit'"
            link
            :type="row.status === 1 ? 'danger' : 'success'"
            @click="toggle(row)"
          >{{ row.status === 1 ? '停用' : '启用' }}</el-button>
          <el-button
            v-permission="'wms_master_data:team:delete'"
            link
            type="danger"
            @click="remove(row)"
          >删除</el-button>
        </template>
      </el-table-column>
      <template #empty><div class="empty">当前筛选条件下无结果。</div></template>
    </el-table>

    <el-drawer v-model="drawer" :title="editing ? '编辑班组' : '新建班组'" size="520px">
      <el-form label-width="100px">
        <el-form-item label="班组名称" required>
          <el-input v-model="form.name" maxlength="20" placeholder="1 至 20 字，本仓唯一" />
        </el-form-item>
        <el-form-item label="仓库"><span>当前仓（单仓）</span></el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio :value="1">启用</el-radio>
            <el-radio :value="0">停用</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="楼层" required>
          <el-select v-model="form.floor_no" style="width: 100%" @change="onFloorChange">
            <el-option v-for="f in floors" :key="f" :label="`${f}F`" :value="f" />
          </el-select>
        </el-form-item>
        <el-form-item label="管辖区域" required>
          <el-select v-model="form.zone_ids" multiple style="width: 100%" placeholder="至少选择一个">
            <el-option v-for="z in zoneOptions" :key="z.id" :label="z.name" :value="z.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="班组长" required>
          <el-select v-model="form.leader_staff_id" style="width: 100%" placeholder="从候选中选择">
            <el-option
              v-for="s in leaderOptions"
              :key="s.id"
              :label="`${s.code} ${s.name}（${s.team_name || '未分组'}）`"
              :value="s.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="在办上限默认">
          <el-input-number v-model="form.dispatch_limit_default" :min="1" :max="20" controls-position="right" />
          <span class="hint">留空继承仓级默认 3</span>
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
  </div>
</template>

<style scoped>
.page { padding: 4px; }
.query { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 8px 0; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.coverage { padding: 8px 12px; margin-bottom: 8px; background: #f5f7fa; border-radius: 4px; color: #5c6675; font-size: 13px; }
.toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.spacer { flex: 1; }
.empty { padding: 28px 0; color: #98a4bb; font-size: 13px; }
.hint { margin-left: 8px; color: #98a4bb; font-size: 12px; }
</style>
