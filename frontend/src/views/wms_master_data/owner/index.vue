<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createOwner,
  listOwners,
  toggleOwner,
  updateOwner,
} from '@/api/wms_master_data'
import { usePagedList } from '@/composables/usePagedList'

const { items, total, page, pageSize, loading, query, fetch, search, onPageChange, onSizeChange } =
  usePagedList(listOwners, { keyword: '' })

const drawer = ref(false)
const saving = ref(false)
const editing = ref<any>(null)
const form = reactive({
  code: '',
  name: '',
  contact: '',
  phone: '',
  address: '',
  sync_enabled: false,
  with_primary_account: true,
})

/** 初始密码只返回一次，用弹窗挡住，避免用户没看到就关了抽屉。 */
const credential = ref<{ username: string; password: string } | null>(null)

function openCreate() {
  editing.value = null
  Object.assign(form, {
    code: '', name: '', contact: '', phone: '', address: '',
    sync_enabled: false, with_primary_account: true,
  })
  drawer.value = true
}

function openEdit(row: any) {
  editing.value = row
  Object.assign(form, {
    code: row.code,
    name: row.name,
    contact: row.contact || '',
    phone: row.phone || '',
    address: row.address || '',
    sync_enabled: row.sync_enabled,
    with_primary_account: false,
  })
  drawer.value = true
}

async function submit() {
  if (!form.code.trim() || !form.name.trim()) {
    ElMessage.warning('货主编码与名称必填')
    return
  }
  saving.value = true
  try {
    if (editing.value) {
      await updateOwner(editing.value.id, form)
      ElMessage.success('已保存')
    } else {
      const res: any = await createOwner(form)
      ElMessage.success('货主已创建')
      if (res?.initial_password) {
        credential.value = { username: res.username, password: res.initial_password }
      }
    }
    drawer.value = false
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    saving.value = false
  }
}

async function onToggle(row: any) {
  const next = row.status !== 1
  await ElMessageBox.confirm(
    next ? `确认启用「${row.name}」？启用后该货主账号可以登录。` : `确认停用「${row.name}」？停用后其账号将无法登录。`,
    '确认',
    { type: 'warning' },
  )
  await toggleOwner(row.id, next)
  ElMessage.success(next ? '已启用' : '已停用')
  await fetch()
}

onMounted(fetch)
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-input
        v-model="query.keyword"
        placeholder="按编码或名称搜索"
        clearable
        style="width: 240px"
        @keyup.enter="search"
        @clear="search"
      />
      <el-button @click="search">查询</el-button>
      <div class="spacer" />
      <el-button v-permission="'wms_master_data:owner:create'" type="primary" @click="openCreate">
        新建货主
      </el-button>
    </div>

    <el-table v-loading="loading" :data="items" border stripe height="calc(100vh - 260px)">
      <el-table-column prop="code" label="货主编码" width="140" fixed />
      <el-table-column prop="name" label="名称" min-width="180" show-overflow-tooltip />
      <el-table-column prop="contact" label="联系人" width="110" />
      <el-table-column prop="phone" label="电话" width="140" />
      <el-table-column label="接入上游" width="110" align="center">
        <template #default="{ row }">
          <el-tag :type="row.sync_enabled ? 'success' : 'info'" size="small" effect="light">
            {{ row.sync_enabled ? '已接入' : '未接入' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
            {{ row.status === 1 ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'wms_master_data:owner:edit'" link type="primary" @click="openEdit(row)">
            编辑
          </el-button>
          <el-button
            v-permission="'wms_master_data:owner:edit'"
            link
            :type="row.status === 1 ? 'danger' : 'success'"
            @click="onToggle(row)"
          >
            {{ row.status === 1 ? '停用' : '启用' }}
          </el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty">还没有货主。新建一个货主后，系统会自动为其开一个主账号。</div>
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

    <el-drawer v-model="drawer" :title="editing ? '编辑货主' : '新建货主'" size="520px">
      <el-form label-width="96px" label-position="right">
        <el-form-item label="货主编码" required>
          <el-input v-model="form.code" :disabled="!!editing" placeholder="如 OWN001" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="公司全称或简称" />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="form.contact" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="form.address" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="接入上游">
          <el-switch v-model="form.sync_enabled" />
          <div class="hint">开启后该货主只能查询，建单入口关闭，订单改由上游下发。</div>
        </el-form-item>
        <el-form-item v-if="!editing" label="开主账号">
          <el-switch v-model="form.with_primary_account" />
          <div class="hint">用户名取货主编码的小写形式，初始密码创建后只显示一次。</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="drawer = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-drawer>

    <el-dialog :model-value="!!credential" title="主账号已创建" width="440px" @close="credential = null">
      <el-alert type="warning" :closable="false" show-icon title="密码只显示这一次，请立即转交货主" />
      <div class="cred">
        <div><span>用户名</span><b>{{ credential?.username }}</b></div>
        <div><span>初始密码</span><b>{{ credential?.password }}</b></div>
      </div>
      <template #footer>
        <el-button type="primary" @click="credential = null">我已记下</el-button>
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
.pagination {
  margin-top: 12px;
  justify-content: flex-end;
}
.empty {
  padding: 28px 0;
  color: #98a4bb;
  font-size: 13px;
}
.hint {
  width: 100%;
  margin-top: 4px;
  font-size: 12px;
  color: #98a4bb;
  line-height: 1.6;
}
.cred {
  margin-top: 14px;
  padding: 12px 14px;
  background: #f3f6fb;
  border-radius: 8px;
  font-size: 13px;
  color: #1b2740;
}
.cred div {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
}
.cred span {
  color: #66748f;
}
</style>
