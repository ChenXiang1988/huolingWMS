<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { portalBills } from '@/api/wms_portal'

const period = ref('')
const rows = ref<any[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const res: any = await portalBills(period.value ? { period: period.value } : undefined)
    rows.value = res.items || []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="wrap">
    <div class="head">
      <h2>账单查询</h2>
      <p>账单由仓库的计费域按月生成，货主在此查看自己账期的费用与明细，不能修改。</p>
    </div>

    <div class="filter">
      <el-input v-model="period" placeholder="账期，如 2026-11" clearable style="width: 200px" />
      <el-button type="primary" :loading="loading" @click="load">查询</el-button>
    </div>

    <el-alert v-if="!rows.length" type="info" :closable="false" show-icon
              title="账单随计费上线开放"
              description="当前账期没有可展示的账单。计费能力上线后，已确认的账单会按账期出现在这里。"
              style="margin: 16px 0" />

    <el-table v-if="rows.length" :data="rows" size="small" border style="width: 100%">
      <el-table-column prop="period" label="账期" width="120" />
      <el-table-column prop="status" label="状态" width="120" />
      <el-table-column prop="amount" label="金额" width="140" />
      <el-table-column prop="created_at" label="生成时间" />
    </el-table>
  </div>
</template>

<style scoped>
.wrap { max-width: 900px; }
.head h2 { margin: 0 0 6px; font-size: 18px; font-weight: 600; color: #1b2740; }
.head p { margin: 0 0 20px; font-size: 13px; color: #66748f; }
.filter { display: flex; gap: 10px; align-items: center; }
</style>
