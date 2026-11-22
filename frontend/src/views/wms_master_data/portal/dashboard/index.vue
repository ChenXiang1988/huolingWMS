<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { portalContext } from '@/api/wms_portal'

const router = useRouter()
const ctx = ref<any>(null)

onMounted(async () => {
  ctx.value = await portalContext()
})
</script>

<template>
  <div class="wrap">
    <div class="hero">
      <div class="hello">你好，{{ ctx?.owner_name || '货主' }}</div>
      <p>这里是货主自助端。可以提交入库预报与出库订单，已提交的单据由仓库接着处理。</p>
    </div>

    <div class="cards">
      <button class="card" @click="router.push('/asn')">
        <span class="label">入库预报</span>
        <span class="desc">登记即将到货的商品与数量，仓库据此开收货单</span>
        <span class="go">去建单 →</span>
      </button>
      <button class="card" @click="router.push('/order')">
        <span class="label">出库订单</span>
        <span class="desc">提交发货需求，仓库按先到期先出分配批次</span>
        <span class="go">去建单 →</span>
      </button>
    </div>

    <div v-if="ctx" class="meta">
      <div><span>货主编号</span><b>#{{ ctx.owner_id }}</b></div>
      <div><span>上游同步</span><b>{{ ctx.sync_enabled ? '已接入 ERP' : '未接入' }}</b></div>
      <div><span>门户建单</span><b :class="ctx.can_create ? 'ok' : 'off'">
        {{ ctx.can_create ? '可用' : '由上游下发' }}
      </b></div>
    </div>

    <div class="note">
      库存、单据与账单的查询页将随报表一起在最终验收前补齐；当前版本先把能改变
      单据与库存的动作做实。
    </div>
  </div>
</template>

<style scoped>
.wrap { max-width: 760px; }
.hero { margin-bottom: 20px; }
.hello { font-size: 20px; font-weight: 600; color: #1b2740; }
.hero p { margin: 8px 0 0; font-size: 13px; line-height: 1.8; color: #66748f; }
.cards { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.card { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; padding: 18px; text-align: left; background: #fff; border: 1px solid #e8ecf3; border-radius: 10px; cursor: pointer; }
.card:hover { border-color: #10b3a3; box-shadow: 0 4px 16px rgba(16,179,163,0.10); }
.label { font-size: 15px; font-weight: 600; color: #1b2740; }
.desc { font-size: 12px; line-height: 1.7; color: #66748f; }
.go { margin-top: 4px; font-size: 12px; font-weight: 600; color: #0e8c80; }
.meta { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 18px; }
.meta div { padding: 12px 14px; background: #f7f9fc; border-radius: 8px; }
.meta span { display: block; font-size: 12px; color: #98a4bb; }
.meta b { display: block; margin-top: 4px; font-size: 14px; color: #1b2740; }
.meta b.ok { color: #16a34a; }
.meta b.off { color: #d97706; }
.note { margin-top: 18px; font-size: 12px; line-height: 1.8; color: #98a4bb; }
</style>
