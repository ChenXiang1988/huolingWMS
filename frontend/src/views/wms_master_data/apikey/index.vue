<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createApiKey, listApiKeys, listOwners, rotateApiKey } from '@/api/wms_master_data'

const owners = ref<any[]>([])
const rows = ref<any[]>([])
const loading = ref(false)
const query = reactive<any>({ owner_id: '' })

const drawer = ref(false)
const saving = ref(false)
const form = reactive<any>({ owner_id: null, name: '' })

/** 明文只在签发与重置时返回一次，所以用一个只读弹窗挡住。 */
const issued = ref<{ name: string; api_key: string } | null>(null)

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
    const data: any = await listApiKeys(params)
    rows.value = data || []
  } catch (e) {
    console.error(e)
    rows.value = []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(form, { owner_id: query.owner_id || owners.value[0]?.id || null, name: '' })
  drawer.value = true
}

async function submit() {
  if (!form.owner_id || !form.name.trim()) {
    ElMessage.warning('货主与名称必填')
    return
  }
  saving.value = true
  try {
    const res: any = await createApiKey(form)
    drawer.value = false
    issued.value = { name: form.name, api_key: res.api_key }
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    saving.value = false
  }
}

async function onRotate(row: any) {
  await ElMessageBox.confirm(
    `重置后旧密钥立即失效，货主侧对接需要同步更新。确认重置「${row.name}」？`,
    '确认重置',
    { type: 'warning' },
  )
  const res: any = await rotateApiKey(row.id)
  issued.value = { name: row.name, api_key: res.api_key }
  await fetch()
}

async function copyKey() {
  const key = issued.value?.api_key
  if (!key) return
  await navigator.clipboard.writeText(key)
  ElMessage.success('已复制')
}

onMounted(async () => {
  await loadOwners()
  await fetch()
})
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="query.owner_id" placeholder="货主" clearable style="width: 200px" @change="fetch">
        <el-option v-for="o in owners" :key="o.id" :label="`${o.code} ${o.name}`" :value="o.id" />
      </el-select>
      <div class="spacer" />
      <el-button v-permission="'wms_master_data:apikey:create'" type="primary" @click="openCreate">
        签发凭证
      </el-button>
    </div>

    <el-table v-loading="loading" :data="rows" border stripe height="calc(100vh - 240px)">
      <el-table-column prop="name" label="用途" min-width="180" />
      <el-table-column label="所属货主" min-width="180">
        <template #default="{ row }">{{ ownerName(row.owner_id) }}</template>
      </el-table-column>
      <el-table-column label="密钥前缀" width="180">
        <template #default="{ row }">
          <span class="mono">{{ row.key_prefix }}…</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
            {{ row.status === 1 ? '有效' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="110" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'wms_master_data:apikey:create'" link type="warning" @click="onRotate(row)">
            重置
          </el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty">还没有凭证。货主系统对接需要一把密钥，签发给对方后请妥善保管。</div>
      </template>
    </el-table>

    <el-drawer v-model="drawer" title="签发 API 凭证" size="440px">
      <el-form label-width="88px">
        <el-form-item label="货主" required>
          <el-select v-model="form.owner_id" style="width: 100%">
            <el-option v-for="o in owners" :key="o.id" :label="`${o.code} ${o.name}`" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="用途" required>
          <el-input v-model="form.name" placeholder="如 入库预报对接" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="drawer = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">签发</el-button>
      </template>
    </el-drawer>

    <el-dialog :model-value="!!issued" title="请立即保存密钥" width="520px" @close="issued = null">
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="密钥只显示这一次，关闭后无法再查看，只能重置"
      />
      <div class="key-box">
        <div class="key-label">{{ issued?.name }}</div>
        <div class="key-value">{{ issued?.api_key }}</div>
      </div>
      <template #footer>
        <el-button @click="copyKey">复制密钥</el-button>
        <el-button type="primary" @click="issued = null">我已保存</el-button>
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
}
.spacer {
  flex: 1;
}
.empty {
  padding: 28px 0;
  color: #98a4bb;
  font-size: 13px;
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  color: #3a4a68;
}
.key-box {
  margin-top: 14px;
  padding: 12px 14px;
  background: #f3f6fb;
  border-radius: 8px;
}
.key-label {
  font-size: 12px;
  color: #66748f;
  margin-bottom: 6px;
}
.key-value {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px;
  color: #1b2740;
  word-break: break-all;
  line-height: 1.6;
}
</style>
