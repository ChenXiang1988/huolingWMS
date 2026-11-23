<script setup lang="ts">
/**
 * 两端共用的右侧抽屉骨架。
 *
 * 只负责外壳：头部标题/副标题/状态标签/关闭，左侧分段目录（sections ≥ 2 时显示），
 * 右侧内容按命名插槽 section-<key> 填充，底部操作右对齐。字段控件与业务表单由使用方提供。
 */
import { computed, ref, watch } from 'vue'

interface Section {
  key: string
  label: string
}

const props = withDefaults(defineProps<{
  modelValue: boolean
  title: string
  subtitle?: string
  status?: string
  sections?: Section[]
  width?: string
}>(), {
  subtitle: '',
  status: '',
  sections: () => [],
  width: '720px',
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'close'): void
}>()

const active = ref(props.sections[0]?.key ?? '')
const showNav = computed(() => props.sections.length >= 2)
const visible = ref(props.modelValue)

watch(() => props.modelValue, (v) => { visible.value = v })
watch(visible, (v) => {
  if (v !== props.modelValue) emit('update:modelValue', v)
})
watch(() => props.sections, (sections) => {
  if (!sections.some((s) => s.key === active.value)) {
    active.value = sections[0]?.key ?? ''
  }
}, { deep: true })

function close() {
  visible.value = false
  emit('close')
}

function scrollTo(key: string) {
  active.value = key
  const el = document.getElementById(`drawer-section-${key}`)
  el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>

<template>
  <el-drawer
    v-model="visible"
    :size="width"
    :with-header="false"
    direction="rtl"
  >
    <div class="drawer-shell">
      <header class="drawer-header">
        <div class="head-text">
          <h3>{{ title }}</h3>
          <p v-if="subtitle">{{ subtitle }}</p>
        </div>
        <el-tag v-if="status" size="small" type="info" class="status-tag">{{ status }}</el-tag>
        <button class="drawer-close" aria-label="关闭" @click="close">×</button>
      </header>

      <div class="drawer-body" :class="{ 'with-nav': showNav }">
        <nav v-if="showNav" class="section-nav">
          <button
            v-for="section in sections"
            :key="section.key"
            :class="{ active: active === section.key }"
            @click="scrollTo(section.key)"
          >
            {{ section.label }}
          </button>
        </nav>
        <div class="section-content">
          <template v-if="showNav">
            <section
              v-for="section in sections"
              :id="`drawer-section-${section.key}`"
              :key="section.key"
              class="section-block"
            >
              <h4>{{ section.label }}</h4>
              <slot :name="`section-${section.key}`" />
            </section>
          </template>
          <slot v-else name="section-default" />
          <slot name="content" />
        </div>
      </div>

      <footer class="drawer-footer">
        <slot name="footer">
          <el-button @click="close">取消</el-button>
        </slot>
      </footer>
    </div>
  </el-drawer>
</template>

<style scoped>
.drawer-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.drawer-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 20px 24px 16px;
  border-bottom: 1px solid #eef0f4;
  flex-shrink: 0;
}
.head-text {
  flex: 1;
  min-width: 0;
}
.head-text h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1b2740;
}
.head-text p {
  margin: 6px 0 0;
  font-size: 12px;
  color: #98a4bb;
}
.status-tag {
  margin-top: 2px;
}
.drawer-close {
  border: 0;
  background: transparent;
  font-size: 24px;
  line-height: 1;
  color: #9aa3b2;
  cursor: pointer;
  padding: 0 4px;
}
.drawer-close:hover {
  color: #1b2740;
}
.drawer-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 24px;
}
.drawer-body.with-nav {
  display: flex;
  gap: 20px;
  padding: 0;
}
.section-nav {
  width: 150px;
  flex-shrink: 0;
  padding: 20px 0;
  border-right: 1px solid #eef0f4;
  background: #fafbfe;
}
.section-nav button {
  display: block;
  width: 100%;
  text-align: left;
  border: 0;
  background: transparent;
  padding: 10px 18px;
  font-size: 13px;
  color: #5a6273;
  cursor: pointer;
}
.section-nav button:hover {
  color: var(--theme-default, #5A67F5);
  background: #eff3f9;
}
.section-nav button.active {
  color: var(--theme-default, #5A67F5);
  font-weight: 600;
  border-left: 3px solid var(--theme-default, #5A67F5);
  padding-left: 15px;
}
.section-content {
  flex: 1;
  min-width: 0;
  padding: 20px 24px;
  overflow-y: auto;
}
.section-block + .section-block {
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px dashed #eef0f4;
}
.section-block h4 {
  margin: 0 0 14px;
  font-size: 14px;
  font-weight: 600;
  color: #1b2740;
}
.drawer-footer {
  padding: 14px 24px;
  border-top: 1px solid #eef0f4;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  flex-shrink: 0;
}
</style>
