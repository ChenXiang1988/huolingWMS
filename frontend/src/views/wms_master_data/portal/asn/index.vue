<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { portalContext, portalCreateAsn, portalSkus } from '@/api/wms_portal'

const ctx = ref<any>(null)
const skus = ref<any[]>([])
const busy = ref(false)
const done = ref<any>(null)
const form = reactive<any>({
  owner_doc_no: '',
  expect_arrive_at: null,
  remark: '',
  lines: [{ sku_id: null, expect_qty: '' }],
})

function addLine() {
  form.lines.push({ sku_id: null, expect_qty: '' })
}

function removeLine(i: number) {
  form.lines.splice(i, 1)
}

async function submit() {
  if (!form.owner_doc_no.trim()) {
    ElMessage.warning('请填货主单号')
    return
  }
  const lines = form.lines.filter((l: any) => l.sku_id && Number(l.expect_qty) > 0)
  if (!lines.length) {
    ElMessage.warning('至少一行有效明细')
    return
  }
  busy.value = true
  try {
    const res: any = await portalCreateAsn({
      owner_doc_no: form.owner_doc_no,
      expect_arrive_at: form.expect_arrive_at || null,
      remark: form.remark || null,
      lines,
    })
    done.value = res
    ElMessage.success(`预报 ${res.code} 已提交`)
    form.owner_doc_no = ''
    form.lines = [{ sku_id: null, expect_qty: '' }]
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
      <h2>新建入库预报</h2>
      <p v-if="ctx">当前货主：<b>{{ ctx.owner_name }}</b>（#{{ ctx.owner_id }}）</p>
    </div>

    <el-alert v-if="ctx && !ctx.can_create" type="warning" :closable="false" show-icon
              title="该货主已接入上游 ERP，预报由系统同步下发，门户不再建单"
              description="已有单据照常查询与推进，不受影响。如需临时建单请联系仓库。"
              style="margin-bottom: 16px" />

    <el-alert v-if="done" type="success" :closable="false" show-icon
              :title="`预报 ${done.code} 已提交，仓库可据此开收货单`"
              style="margin-bottom: 16px" />

    <el-form label-width="100px" :disabled="!ctx?.can_create">
      <el-form-item label="货主单号" required>
        <el-input v-model="form.owner_doc_no" placeholder="你自己系统里的单号，用于去重" />
      </el-form-item>
      <el-form-item label="预计到货">
        <el-date-picker v-model="form.expect_arrive_at" type="datetime"
                        value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.remark" type="textarea" :rows="2" />
      </el-form-item>
      <el-form-item label="商品明细">
        <div class="lines">
          <div v-for="(l, i) in form.lines" :key="i" class="line">
            <el-select v-model="l.sku_id" filterable placeholder="选择商品" style="flex: 1">
              <el-option v-for="s in skus" :key="s.id"
                         :label="`${s.owner_sku_code} ${s.name}`" :value="s.id" />
            </el-select>
            <el-input v-model="l.expect_qty" placeholder="应收数量" style="width: 130px" />
            <el-button link type="danger" @click="removeLine(i)">删除</el-button>
          </div>
          <el-button link type="primary" @click="addLine">+ 加一行</el-button>
        </div>
      </el-form-item>
    </el-form>

    <div class="foot">
      <button class="primary" :disabled="!ctx?.can_create || busy" @click="submit">
        {{ busy ? '提交中…' : '提交预报' }}
      </button>
      <span class="hint">提交后由仓库开收货单；分批到货可挂多张收货单。</span>
    </div>
  </div>
</template>

<style scoped>
.wrap { max-width: 720px; }
.head h2 { margin: 0 0 6px; font-size: 18px; font-weight: 600; color: #1b2740; }
.head p { margin: 0 0 20px; font-size: 13px; color: #66748f; }
.lines { display: flex; flex-direction: column; gap: 8px; width: 100%; }
.line { display: flex; align-items: center; gap: 8px; }
.foot { display: flex; align-items: center; gap: 12px; margin-top: 12px; }
button.primary { padding: 9px 20px; font-size: 13px; color: #fff; background: #10b3a3; border: none; border-radius: 7px; cursor: pointer; }
button.primary:hover { background: #0e8c80; }
button.primary:disabled { background: #98a4bb; cursor: not-allowed; }
.hint { font-size: 12px; color: #98a4bb; }
</style>
