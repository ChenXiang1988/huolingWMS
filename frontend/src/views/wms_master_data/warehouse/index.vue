<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getWarehouse, saveWarehouse } from '@/api/wms_master_data'

const loading = ref(false)
const saving = ref(false)
const form = reactive({ name: '货灵一号仓', topology: 'FLAT' })

/**
 * 仓型决定坐标字段怎么解释，改一次就是一次库位语义变更，
 * 所以这里把三种仓型的差别直接写给人看，而不是只给一个下拉。
 */
const TOPOLOGIES = [
  {
    value: 'FLAT',
    label: '平面仓',
    desc: '单层，用巷—架—位定位。没有楼层概念，容量按单库位可放托数。',
  },
  {
    value: 'MULTI_FLOOR',
    label: '楼层仓',
    desc: '多层楼板，坐标在巷—架—位前多一层楼层。收货通常在 1 层，存储往上排。',
  },
  {
    value: 'ASRS',
    label: '钢结构立库',
    desc: '货架到顶，必须能定位到巷—架—层，否则取不到具体货格。',
  },
]

async function load() {
  loading.value = true
  try {
    const data: any = await getWarehouse()
    if (data) {
      form.name = data.name
      form.topology = data.topology
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function submit() {
  saving.value = true
  try {
    await saveWarehouse({ ...form })
    ElMessage.success('已保存')
  } catch (e) {
    console.error(e)
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="wrap">
    <el-card v-loading="loading" shadow="never" class="card">
      <template #header>
        <div class="head">
          <span class="title">仓库配置</span>
          <span class="sub">单仓部署，这里只有一份配置</span>
        </div>
      </template>

      <el-form label-width="88px">
        <el-form-item label="仓库名称">
          <el-input v-model="form.name" />
        </el-form-item>

        <el-form-item label="仓型">
          <div class="topo-list">
            <label
              v-for="t in TOPOLOGIES"
              :key="t.value"
              class="topo"
              :class="{ active: form.topology === t.value }"
            >
              <input v-model="form.topology" type="radio" :value="t.value" />
              <div>
                <div class="topo-name">{{ t.label }}</div>
                <div class="topo-desc">{{ t.desc }}</div>
              </div>
            </label>
          </div>
        </el-form-item>

        <el-form-item>
          <el-button v-permission="'wms_master_data:warehouse:edit'" type="primary" :loading="saving" @click="submit">
            保存配置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.wrap {
  display: flex;
  justify-content: center;
  padding-top: 8px;
}
.card {
  width: 640px;
  border-radius: 10px;
}
.head {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.title {
  font-size: 15px;
  font-weight: 600;
  color: #1b2740;
}
.sub {
  font-size: 12px;
  color: #98a4bb;
}
.topo-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}
.topo {
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid #e8ecf3;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.16s ease;
}
.topo:hover {
  border-color: #b9e5df;
  background: #fafdfd;
}
.topo.active {
  border-color: #10b3a3;
  background: #eaf5f3;
}
.topo input {
  margin-top: 2px;
  accent-color: #10b3a3;
}
.topo-name {
  font-size: 13px;
  font-weight: 600;
  color: #1b2740;
}
.topo-desc {
  margin-top: 2px;
  font-size: 12px;
  color: #66748f;
  line-height: 1.6;
}
</style>
