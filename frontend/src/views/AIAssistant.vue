<template>
  <div class="container">
    <div class="card" style="min-height:400px">
      <h3>AI 投研助手</h3>
      <div style="margin:12px 0">
        <label>股票代码(可选): </label>
        <input v-model="tsCode" placeholder="如 000001.SZ" style="padding:8px; width:200px" />
      </div>
      <div style="display:flex; gap:8px; margin-bottom:16px">
        <input v-model="question" placeholder="输入你的问题..." @keyup.enter="ask" style="flex:1; padding:10px" />
        <button class="btn btn-primary" @click="ask" :disabled="loading">发送</button>
      </div>
      <div v-if="answer" class="card" style="background:#f8f9fa" v-html="answerHtml"></div>
    </div>
  </div>
</template>
<script>
import api from '../api'
import { marked } from 'marked'
export default {
  name: 'AIAssistant',
  data() { return { tsCode: '', question: '', answer: '', loading: false } },
  computed: {
    answerHtml() { return this.answer ? marked(this.answer) : '' }
  },
  methods: {
    async ask() {
      if (!this.question) return
      this.loading = true
      try {
        const res = await api.post('/api/ai/ask', { question: this.question, ts_code: this.tsCode })
        this.answer = res.answer
      } catch (e) { this.answer = '请求失败: ' + e.message }
      this.loading = false
    }
  }
}
</script>