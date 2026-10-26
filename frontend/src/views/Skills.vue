<template>
  <main class="container skills-page">
    <header class="page-heading">
      <div>
        <h1>Skill 插件管理</h1>
        <p>独立安装和运行标准化投研能力。安装 ZIP 会执行其中的 Python 代码，请只使用可信来源。</p>
      </div>
      <button class="btn" :disabled="loading" @click="load">刷新列表</button>
    </header>

    <section class="card">
      <h2>管理员密钥</h2>
      <p class="muted">在后端配置 X2STOCK_ADMIN_KEY 后输入。密钥仅保存在当前浏览器会话。</p>
      <div class="inline-form">
        <input v-model="adminKey" type="password" autocomplete="current-password" placeholder="X-Admin-Key">
        <button class="btn" @click="saveKey">保存到本次会话</button>
        <button class="btn" @click="clearKey">清除</button>
      </div>
    </section>

    <section class="card">
      <h2>安装或升级 Skill</h2>
      <div class="inline-form">
        <input ref="fileInput" type="file" accept=".zip,application/zip" @change="selectFile">
        <button class="btn btn-primary" :disabled="!file || !adminKey || installing" @click="install">
          {{ installing ? '提交中…' : '安装 ZIP' }}
        </button>
      </div>
      <p v-if="job" class="job-state">安装任务 {{ job.status }}：{{ job.message || job.job_id }}</p>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="notice" class="success">{{ notice }}</p>
    </section>

    <section class="card">
      <h2>已安装 Skills <span class="count">{{ skills.length }}</span></h2>
      <div v-if="!skills.length" class="empty">暂无已安装 Skill。可以先安装低估值筛选示例包。</div>
      <article v-for="skill in skills" :key="skill.skill_id" class="skill-row">
        <div class="skill-summary">
          <h3>{{ skill.name }} <small>{{ skill.version }}</small></h3>
          <div class="muted">{{ skill.skill_id }} · {{ skill.api_version }} · {{ skill.status }}</div>
          <div class="permissions">数据能力：{{ (skill.manifest?.permissions || []).join('、') || '无' }}</div>
        </div>
        <div class="actions">
          <button class="btn" :disabled="!adminKey" @click="toggle(skill)">{{ skill.enabled ? '禁用' : '启用' }}</button>
          <button class="btn btn-primary" :disabled="!adminKey || !skill.enabled || running === skill.skill_id" @click="run(skill)">
            {{ running === skill.skill_id ? '运行中…' : '运行示例' }}
          </button>
          <button class="btn btn-danger" :disabled="!adminKey" @click="uninstall(skill)">卸载</button>
        </div>
        <div v-if="runOutput[skill.skill_id]" class="output">
          <div class="output-title">最近运行结果</div>
          <pre>{{ JSON.stringify(runOutput[skill.skill_id], null, 2) }}</pre>
        </div>
      </article>
    </section>
  </main>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import api from '../api'

const skills = ref([])
const adminKey = ref(sessionStorage.getItem('x2stock-admin-key') || '')
const file = ref(null)
const fileInput = ref(null)
const job = ref(null)
const loading = ref(false)
const installing = ref(false)
const running = ref('')
const error = ref('')
const notice = ref('')
const runOutput = ref({})
let pollTimer

async function load() {
  loading.value = true
  error.value = ''
  try { skills.value = await api.get('/api/skills') }
  catch (e) { error.value = e.message }
  finally { loading.value = false }
}
function saveKey() {
  sessionStorage.setItem('x2stock-admin-key', adminKey.value)
  notice.value = '密钥已保存到当前浏览器会话。'
  error.value = ''
}
function clearKey() {
  sessionStorage.removeItem('x2stock-admin-key')
  adminKey.value = ''
  notice.value = '已清除当前会话中的密钥。'
}
function selectFile(event) { file.value = event.target.files?.[0] || null }
async function install() {
  if (!file.value) return
  installing.value = true
  error.value = ''
  notice.value = ''
  job.value = null
  try {
    const form = new FormData()
    form.append('file', file.value)
    job.value = await api.admin('/api/skills/install', 'POST', adminKey.value, form)
    pollTimer = setInterval(pollInstall, 1500)
    await pollInstall()
  } catch (e) { error.value = e.message }
  finally { installing.value = false }
}
async function pollInstall() {
  if (!job.value?.job_id) return
  try {
    job.value = await api.get('/api/skills/install/' + encodeURIComponent(job.value.job_id))
    if (['completed', 'failed'].includes(job.value.status)) {
      clearInterval(pollTimer)
      if (job.value.status === 'completed') { notice.value = job.value.message; await load() }
      else error.value = job.value.message || 'Skill 安装失败'
    }
  } catch (e) { clearInterval(pollTimer); error.value = e.message }
}
async function toggle(skill) {
  error.value = ''
  try {
    await api.admin('/api/skills/' + encodeURIComponent(skill.skill_id) + (skill.enabled ? '/disable' : '/enable'), 'POST', adminKey.value)
    await load()
  } catch (e) { error.value = e.message }
}
async function run(skill) {
  running.value = skill.skill_id
  error.value = ''
  try {
    const result = await api.admin('/api/skills/' + encodeURIComponent(skill.skill_id) + '/run', 'POST', adminKey.value, { params: {} })
    runOutput.value = { ...runOutput.value, [skill.skill_id]: result }
  } catch (e) { error.value = e.message }
  finally { running.value = '' }
}
async function uninstall(skill) {
  if (!window.confirm('确定卸载 ' + skill.name + '？这会删除该 Skill 的代码与独立 Python 环境。')) return
  error.value = ''
  try {
    await api.admin('/api/skills/' + encodeURIComponent(skill.skill_id), 'DELETE', adminKey.value)
    delete runOutput.value[skill.skill_id]
    await load()
  } catch (e) { error.value = e.message }
}
onMounted(load)
onUnmounted(() => clearInterval(pollTimer))
</script>

<style scoped>
.page-heading { display:flex; justify-content:space-between; align-items:center; gap:16px; margin:8px 0 20px; }
h1 { font-size:26px; margin-bottom:8px; }
h2 { font-size:18px; margin-bottom:14px; }
.muted, .page-heading p { color:#718096; line-height:1.6; }
.inline-form { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-top:12px; }
input[type=password] { min-width:280px; padding:9px 12px; border:1px solid #d5dce5; border-radius:5px; }
.count { color:#718096; font-weight:400; }
.empty { padding:18px 0; color:#718096; }
.skill-row { display:grid; grid-template-columns:minmax(200px,1fr) auto; gap:12px; padding:18px 0; border-top:1px solid #edf0f4; }
.skill-row h3 { margin-bottom:7px; }
.skill-row small { color:#718096; font-weight:400; }
.permissions { margin-top:7px; color:#536273; font-size:13px; }
.actions { display:flex; flex-wrap:wrap; align-items:center; gap:8px; }
.btn-danger { color:#bd2c2c; border-color:#e2b5b5; }
.output { grid-column:1/-1; min-width:0; }
.output-title { font-weight:600; margin:5px 0 8px; }
pre { max-height:480px; overflow:auto; padding:14px; border-radius:6px; background:#111827; color:#e2e8f0; font-size:12px; white-space:pre-wrap; overflow-wrap:anywhere; }
.error { color:#b42318; margin-top:10px; }
.success { color:#137333; margin-top:10px; }
.job-state { margin-top:12px; color:#334155; }
@media (max-width:760px) { .skill-row { grid-template-columns:1fr; } .page-heading { align-items:flex-start; flex-direction:column; } }
</style>
