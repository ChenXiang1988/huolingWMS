<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { listTasks } from '@/api/wms_ops'
import { useScanGun } from '@/composables/useScanGun'

const keyword = ref('')
const input = ref<any>(null)
const result = ref<any>(null)
const message = ref('')

const TYPES: Record<string, string> = {
  transfer: '移库', count: '盘点', putaway: '上架', pick: '拣货', check: '复核',
}

async function refocus() {
  await nextTick()
  input.value?.focus()
}

/** 通用扫码：按库位 ID、任务号或单据 ID 找当前作业员名下的任务。
 *  真扫码枪接入后这里换成条码解析，业务判定不变。 */
async function scan() {
  const key = keyword.value.trim()
  message.value = ''
  result.value = null
  if (!key) return

  const tasks: any = await listTasks({ status: 'claimed', page: 1, page_size: 100 })
  const rows = tasks?.items || []
  const hit = rows.find((r: any) =>
    r.code === key ||
    String(r.ref_id) === key ||
    String(r.target_location_id) === key
  )
  if (hit) {
    result.value = hit
  } else {
    message.value = `没有匹配「${key}」的进行中任务，请先到「我的任务」领取`
  }
  keyword.value = ''
  await refocus()
}

// 焦点被弹窗、切后台之类的事抢走后，扫码字符仍能被全局监听收到，
// 落到这里补一次录入并重新聚焦，扫 20 次不会因为丢焦点少字符
const { usingBroadcast } = useScanGun(async (code) => {
  keyword.value = code
  await scan()
})

onMounted(refocus)
</script>

<template>
  <div class="wrap">
    <div class="title">扫码执行</div>
    <div class="sub">扫库位码、任务号或单据号，回车定位任务</div>

    <div class="scan-box">
      <input id="mobile-scan" ref="input" v-model="keyword"
             placeholder="扫码或手工输入" @keyup.enter="scan" />
      <button @click="scan">确认</button>
    </div>

    <div v-if="result" class="hit">
      <div class="hit-type">{{ TYPES[result.task_type] || result.task_type }}</div>
      <div class="hit-title">{{ result.title }}</div>
      <div class="hit-row"><span>任务号</span><b>{{ result.code }}</b></div>
      <div class="hit-row"><span>来源</span><b>{{ result.ref_type }} #{{ result.ref_id }}</b></div>
      <div class="hit-row" v-if="result.target_location_id">
        <span>目标库位</span><b>{{ result.target_location_id }}</b>
      </div>
      <div class="hit-row"><span>状态</span><b>进行中</b></div>
    </div>

    <div v-if="message" class="miss">{{ message }}</div>

    <div class="note">
      这页只做定位，真正的业务动作在对应作业页完成：上架去「上架」、拣货去「拣货」、
      移库与盘点在「库内作业」。
    </div>

    <div class="channel">
      扫码通道：{{ usingBroadcast ? '广播' : '键盘模拟' }}
    </div>
  </div>
</template>

<style scoped>
.wrap { max-width: 520px; margin: 0 auto; padding: 12px; }
.title { font-size: 18px; font-weight: 600; color: #1b2740; }
.sub { margin-top: 2px; font-size: 12px; color: #98a4bb; }
.scan-box { display: flex; gap: 8px; margin: 16px 0; }
.scan-box input { flex: 1; padding: 12px; font-size: 15px; color: #1b2740; border: 1px solid #b9e5df; border-radius: 8px; outline: none; }
.scan-box input:focus { border-color: #10b3a3; box-shadow: 0 0 0 3px rgba(16,179,163,0.14); }
.scan-box button { padding: 0 18px; font-size: 14px; color: #fff; background: #10b3a3; border: none; border-radius: 8px; cursor: pointer; }
.scan-box button:hover { background: #0e8c80; }
.hit { padding: 16px; background: #f7fbfa; border: 1px solid #cdeae5; border-radius: 10px; }
.hit-type { display: inline-block; padding: 2px 8px; font-size: 11px; color: #0e8c80; background: #eaf5f3; border-radius: 4px; }
.hit-title { margin: 10px 0 12px; font-size: 16px; font-weight: 600; color: #1b2740; }
.hit-row { display: flex; justify-content: space-between; padding: 5px 0; font-size: 13px; border-bottom: 1px dashed #e2eeeb; }
.hit-row span { color: #66748f; }
.hit-row b { color: #1b2740; font-family: ui-monospace, Menlo, monospace; }
.miss { padding: 14px; font-size: 13px; color: #d97706; background: #fffdf5; border: 1px solid #f5c976; border-radius: 8px; }
.note { margin-top: 16px; font-size: 12px; line-height: 1.8; color: #98a4bb; }
.channel { margin-top: 10px; font-size: 11px; color: #b0bacd; }
</style>
