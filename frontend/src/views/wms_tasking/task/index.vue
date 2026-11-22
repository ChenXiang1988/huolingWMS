<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  claimTask,
  generateTasks,
  listTasks,
  recycleTasks,
  submitTask,
} from '@/api/wms_ops'
import { usePagedList } from '@/composables/usePagedList'

const TYPES: Record<string, string> = {
  transfer: '移库', count: '盘点', putaway: '上架', pick: '拣货', check: '复核',
}
const STATUS: Record<string, { label: string; type: string }> = {
  pending: { label: '待领取', type: 'warning' },
  claimed: { label: '进行中', type: 'primary' },
  done: { label: '已完成', type: 'success' },
  cancelled: { label: '已取消', type: 'info' },
}

const { items, total, page, pageSize, loading, query, fetch, search, onPageChange, onSizeChange } =
  usePagedList(listTasks, { status: '', task_type: '' })
const busy = ref(false)

async function generate() {
  const res: any = await generateTasks()
  ElMessage.success(res.created ? `生成 ${res.created} 条任务` : '没有新的待办作业')
  await fetch()
}

async function act(row: any, kind: 'claim' | 'submit') {
  busy.value = true
  try {
    if (kind === 'claim') await claimTask(row.id)
    else await submitTask(row.id, {})
    ElMessage.success(kind === 'claim' ? '已领取' : '已提交')
    await fetch()
  } catch (e) {
    console.error(e)
  } finally {
    busy.value = false
  }
}

async function recycle() {
  const res: any = await recycleTasks()
  ElMessage.success(res.recycled ? `回收 ${res.recycled} 条超时任务` : '没有超时任务')
  await fetch()
}

onMounted(fetch)
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-select v-model="query.task_type" placeholder="类型" clearable style="width: 130px" @change="search">
        <el-option v-for="(v, k) in TYPES" :key="k" :label="v" :value="k" />
      </el-select>
      <el-select v-model="query.status" placeholder="状态" clearable style="width: 130px" @change="search">
        <el-option v-for="(v, k) in STATUS" :key="k" :label="v.label" :value="k" />
      </el-select>
      <el-button @click="search">查询</el-button>
      <div class="spacer" />
      <el-button @click="recycle">回收超时</el-button>
      <el-button v-permission="'wms_tasking:task:create'" type="primary" @click="generate">
        生成任务
      </el-button>
    </div>

    <el-table v-loading="loading" :data="items" border stripe height="calc(100vh - 240px)">
      <el-table-column prop="code" label="任务号" width="140" fixed />
      <el-table-column label="类型" width="100">
        <template #default="{ row }">{{ TYPES[row.task_type] || row.task_type }}</template>
      </el-table-column>
      <el-table-column prop="title" label="任务" min-width="180" show-overflow-tooltip />
      <el-table-column label="来源" width="160">
        <template #default="{ row }"><span class="num">{{ row.ref_type }} #{{ row.ref_id }}</span></template>
      </el-table-column>
      <el-table-column prop="target_location_id" label="目标库位" width="100" align="right" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="STATUS[row.status]?.type as any" size="small">
            {{ STATUS[row.status]?.label || row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 'pending'"
                     v-permission="'wms_tasking:task:claim'" link type="primary"
                     :loading="busy" @click="act(row, 'claim')">领取</el-button>
          <el-button v-if="row.status === 'claimed'"
                     v-permission="'wms_tasking:task:submit'" link type="primary"
                     :loading="busy" @click="act(row, 'submit')">提交</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty">还没有任务。点「生成任务」把待办作业拆出来。</div>
      </template>
    </el-table>

    <el-pagination class="pagination" :current-page="page" :page-size="pageSize" :total="total"
                   :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next"
                   @current-change="onPageChange" @size-change="onSizeChange" />
  </div>
</template>

<style scoped>
.page { padding: 4px; }
.toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.spacer { flex: 1; }
.pagination { margin-top: 12px; justify-content: flex-end; }
.empty { padding: 28px 0; color: #98a4bb; font-size: 13px; }
.num { font-family: ui-monospace, Menlo, monospace; font-size: 12px; }
</style>
