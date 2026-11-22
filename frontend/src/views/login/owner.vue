<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ownerLogin } from '@/api/wms_master_data'

const router = useRouter()
const form = reactive({ username: '', password: '' })
const loading = ref(false)
const error = ref('')

async function submit() {
  if (!form.username.trim() || !form.password) {
    error.value = '请输入账号与密码'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const res: any = await ownerLogin({
      username: form.username.trim(),
      password: form.password,
    })
    localStorage.setItem('apeadmin_token', res.access_token)
    ElMessage.success(`欢迎，${res.owner_name}`)
    router.push('/dashboard')
  } catch (e: any) {
    error.value = e?.response?.data?.msg || e?.message || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="stage">
    <aside class="brand">
      <div class="mark">
        <span class="dot" />
        <span class="mark-name">货灵仓储</span>
      </div>

      <div class="pitch">
        <h1>货主门户</h1>
        <p>查库存、看进度、对账单，都在这里。</p>
      </div>

      <ul class="points">
        <li>
          <strong>库存实时可见</strong>
          <span>按批次与效期拆开看，不用打电话问仓里还剩多少。</span>
        </li>
        <li>
          <strong>单据全程可追</strong>
          <span>入库预报、收货、上架、发货，每一步都有时间与操作人。</span>
        </li>
        <li>
          <strong>账号分级</strong>
          <span>主账号开子账号，按岗位给到只读或建单权限。</span>
        </li>
      </ul>

      <div class="foot">单仓三方仓储 · 批次与效期管理</div>
    </aside>

    <main class="panel">
      <div class="card">
        <h2>登录</h2>
        <p class="sub">使用货主主账号或子账号登录</p>

        <div class="field">
          <label for="owner-username">账号</label>
          <input
            id="owner-username"
            v-model="form.username"
            autocomplete="username"
            placeholder="货主编码或子账号"
            @keyup.enter="submit"
          />
        </div>

        <div class="field">
          <label for="owner-password">密码</label>
          <input
            id="owner-password"
            v-model="form.password"
            type="password"
            autocomplete="current-password"
            placeholder="登录密码"
            @keyup.enter="submit"
          />
        </div>

        <p v-if="error" class="error">{{ error }}</p>

        <button class="submit" :disabled="loading" @click="submit">
          {{ loading ? '登录中…' : '登录门户' }}
        </button>

        <p class="hint">
          员工请从
          <a href="/admin/">管理后台</a>
          登录
        </p>
      </div>
    </main>
  </div>
</template>

<style scoped>
.stage {
  display: flex;
  min-height: 100vh;
}
.brand {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 48px 56px;
  color: #eafaf7;
  background: linear-gradient(150deg, #0e8c80 0%, #10b3a3 52%, #0b6f66 100%);
}
.mark {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.4px;
}
.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #eafaf7;
  box-shadow: 0 0 0 5px rgba(234, 250, 247, 0.22);
}
.pitch {
  margin-top: 72px;
}
.pitch h1 {
  margin: 0;
  font-size: 34px;
  font-weight: 600;
  letter-spacing: 1px;
}
.pitch p {
  margin: 12px 0 0;
  font-size: 14px;
  opacity: 0.86;
}
.points {
  margin: 44px 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 22px;
  max-width: 420px;
}
.points li {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding-left: 14px;
  border-left: 2px solid rgba(234, 250, 247, 0.45);
}
.points strong {
  font-size: 13px;
  font-weight: 600;
}
.points span {
  font-size: 12.5px;
  line-height: 1.7;
  opacity: 0.82;
}
.foot {
  margin-top: auto;
  font-size: 12px;
  opacity: 0.62;
}
.panel {
  width: 520px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
}
.card {
  width: 340px;
}
.card h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: #1b2740;
}
.sub {
  margin: 6px 0 28px;
  font-size: 13px;
  color: #98a4bb;
}
.field {
  margin-bottom: 16px;
}
.field label {
  display: block;
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #3a4a68;
}
.field input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  font-size: 13px;
  color: #1b2740;
  background: #f7f9fc;
  border: 1px solid #e8ecf3;
  border-radius: 8px;
  outline: none;
  transition: border-color 0.16s ease, background 0.16s ease;
}
.field input::placeholder {
  color: #b3bece;
}
.field input:focus {
  background: #fff;
  border-color: #10b3a3;
  box-shadow: 0 0 0 3px rgba(16, 179, 163, 0.12);
}
.error {
  margin: 0 0 12px;
  padding: 8px 10px;
  font-size: 12.5px;
  color: #dc2626;
  background: #fef2f2;
  border-radius: 6px;
}
.submit {
  width: 100%;
  padding: 11px 0;
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  background: #10b3a3;
  border: 0;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.16s ease;
}
.submit:hover {
  background: #0e8c80;
}
.submit:disabled {
  background: #9ad9d1;
  cursor: not-allowed;
}
.hint {
  margin: 18px 0 0;
  font-size: 12px;
  color: #98a4bb;
  text-align: center;
}
.hint a {
  color: #0e8c80;
  text-decoration: none;
}
@media (max-width: 900px) {
  .brand {
    display: none;
  }
  .panel {
    width: 100%;
  }
}
</style>
