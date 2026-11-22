<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { portalContext, portalCreateOrder, portalSkus } from '@/api/wms_portal'

const ctx = ref<any>(null)
const skus = ref<any[]>([])
const busy = ref(false)
const done = ref<any>(null)
const form = reactive<any>({
  owner_doc_no: '', order_type: 'C',
  receiver: '', receiver_phone: '', receiver_address: '', carrier_code: '',
  lines: [{ sku_id: null, qty: '', lot_id: null }],
})

const skuOf = (id: number) => skus.value.find((s) => s.id === id)

function addLine() {
  form.lines.push({ sku_id: null, qty: '', lot_id: null })
}

function removeLine(i: number) {
  form.lines.splice(i, 1)
}

async function submit() {
  if (!form.owner_doc_no.trim()) {
    ElMessage.warning('请填货主单号')
    return
  }
  const lines = form.lines
    .filter((l: any) => l.sku_id && Number(l.qty) > 0)
    .map((l: any) => ({ sku_id: l.sku_id, qty: String(l.qty), lot_id: l.lot_id || null }))
  if (!lines.length) {
    ElMessage.warning('至少一行有效明细')
    return
  }
  busy.value = true
  try {
    const res: any = await portalCreateOrder({
      owner_doc_no: form.owner_doc_no,
      order_type: form.order_type,
      receiver: form.receiver || null,
      receiver_phone: form.receiver_phone || null,
      receiver_address: form.receiver_address || null,
      carrier_code: form.carrier_code || null,
      lines,
    })
    done.value = res
    ElMessage.success(`订单 ${res.code} 已提交`)
    form.owner_doc_no = ''
    form.lines = [{ sku_id: null, qty: '', lot_id: null }]
  } catch (e) {
    console.error(e)
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  ctx.value = await portalContext()
  skus.value = (await portalSkus()) as any
})
</script>

<template>
  <div class="wrap">
    <div class="head">
      <h2>新建出库订单</h2>
      <p v-if="ctx">当前货主：<b>{{ ctx.owner_name }}</b>（#{{ ctx.owner_id }}）</p>
    </div>

    <el-alert v-if="ctx && !ctx.can_create" type="warning" :closable="false" show-icon
              title="该货主已接入上游 ERP，订单由系统同步下发，门户不再建单"
              description="已有订单照常发货，不受影响。"
              style="margin-bottom: 16px" />

    <el-alert v-if="done" type="success" :closable="false" show-icon
              :title="`订单 ${done.code} 已提交，仓库按先到期先出分配`"
              style="margin-bottom: 16px" />

    <el-form label-width="100px" :disabled="!ctx?.can_create">
      <el-form-item label="货主单号" required>
        <el-input v-model="form.owner_doc_no" placeholder="你自己系统里的单号，用于去重" />
      </el-form-item>
      <el-form-item label="订单类型">
        <el-radio-group v-model="form.order_type">
          <el-radio value="C">C 端电商</el-radio>
          <el-radio value="B">B 端大货</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="收件人">
        <div class="two">
          <el-input v-model="form.receiver" placeholder="姓名" />
          <el-input v-model="form.receiver_phone" placeholder="电话" />
        </div>
      </el-form-item>
      <el-form-item label="收货地址">
        <el-input v-model="form.receiver_address" type="textarea" :rows="2" />
      </el-form-item>
      <el-form-item label="承运商">
        <el-input v-model="form.carrier_code" placeholder="如 SF / JD" />
      </el-form-item>
      <el-form-item label="商品明细">
        <div class="lines">
          <div v-for="(l, i) in form.lines" :key="i" class="line">
            <el-select v-model="l.sku_id" filterable placeholder="选择商品" style="flex: 1">
              <el-option v-for="s in skus" :key="s.id"
                         :label="`${s.owner_sku_code} ${s.name}`" :value="s.id" />
            </el-select>
            <el-input v-model="l.qty" placeholder="数量" style="width: 110px" />
            <el-input v-model="l.lot_id" placeholder="批次 ID" style="width: 110px" />
            <el-button link type="danger" @click="removeLine(i)">删除</el-button>
          </div>
          <el-button link type="primary" @click="addLine">+ 加一行</el-button>
          <div class="hint-line">
            批次留空即按先到期先出；填了批次就只从这个批次取，不够会整行失败。<template v-if="form.lines.some((l: any) => skuOf(l.sku_id)?.lot_required)">
              当前有商品启用批次管理，请填批次 ID。
            </template>
          </div>
        </div>
      </el-form-item>
    </el-form>

    <div class="foot">
      <button class="primary" :disabled="!ctx?.can_create || busy" @click="submit">
        {{ busy ? '提交中…' : '提交订单' }}
      </button>
      <span class="hint">分配只锁定量，发运时才真正扣减库存。</span>
    </div>
  </div>
</template>

<style scoped>
.wrap { max-width: 720px; }
.head h2 { margin: 0 0 6px; font-size: 18px; font-weight: 600; color: #1b2740; }
.head p { margin: 0 0 20px; font-size: 13px; color: #66748f; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; width: 100%; }
.lines { display: flex; flex-direction: column; gap: 8px; width: 100%; }
.line { display: flex; align-items: center; gap: 8px; }
.hint-line { font-size: 12px; line-height: 1.7; color: #98a4bb; }
.foot { display: flex; align-items: center; gap: 12px; margin-top: 12px; }
button.primary { padding: 9px 20px; font-size: 13px; color: #fff; background: #10b3a3; border: none; border-radius: 7px; cursor: pointer; }
button.primary:hover { background: #0e8c80; }
button.primary:disabled { background: #98a4bb; cursor: not-allowed; }
.hint { font-size: 12px; color: #98a4bb; }
</style>
