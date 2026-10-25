<template>
  <div class="container" v-if="stock">
    <div class="card">
      <h2>{{ stock.name }} ({{ stock.ts_code }})</h2>
      <p>行业: {{ stock.industry }} | 市场: {{ stock.market }} | 上市日期: {{ stock.list_date }}</p>
      <p>最新收盘: {{ stock.latest_close }} | 涨跌幅: {{ stock.latest_pct_chg }}% | PE: {{ stock.pe }} | PB: {{ stock.pb }}</p>
    </div>
    <div class="card">
      <h3>K线图</h3>
      <div ref="kchart" style="height:400px"></div>
    </div>
    <div class="card" v-if="announcements.length">
      <h3>近期公告</h3>
      <ul>
        <li v-for="a in announcements" :key="a.id">
          [{{ a.date }}] <a :href="a.url" target="_blank">{{ a.title }}</a>
        </li>
      </ul>
    </div>
    <div class="card">
      <button class="btn btn-primary" @click="generateReport" :disabled="reportLoading">
        {{ reportLoading ? '生成中...' : '生成 AI 报告' }}
      </button>
      <div v-if="report" style="margin-top:16px" v-html="reportHtml"></div>
    </div>
  </div>
</template>
<script>
import api from '../api'
import * as echarts from 'echarts'
import { marked } from 'marked'
export default {
  name: 'StockDetail',
  data() { return { stock: null, quotes: [], announcements: [], report: null, reportLoading: false, chart: null } },
  computed: {
    reportHtml() { return this.report ? marked(this.report) : '' }
  },
  async mounted() {
    const code = this.$route.params.ts_code
    try {
      this.stock = await api.get('/api/stocks/' + code)
      this.quotes = await api.get('/api/stocks/' + code + '/quotes')
      const news = await api.get('/api/stocks/' + code + '/news')
      this.announcements = news.announcements
      this.renderChart()
    } catch (e) { console.error(e) }
  },
  methods: {
    renderChart() {
      if (!this.quotes.length) return
      const chart = echarts.init(this.$refs.kchart)
      const dates = this.quotes.map(q => q.date)
      const kdata = this.quotes.map(q => [q.open, q.close, q.low, q.high])
      const volumes = this.quotes.map(q => q.volume)
      chart.setOption({
        tooltip: { trigger: 'axis' },
        grid: [{ left: '10%', right: '8%', height: '50%' }, { left: '10%', right: '8%', top: '68%', height: '16%' }],
        xAxis: [
          { type: 'category', data: dates },
          { type: 'category', gridIndex: 1, data: dates, axisLabel: { show: false } }
        ],
        yAxis: [{ scale: true }, { gridIndex: 1, axisLabel: { show: false } }],
        series: [
          { type: 'candlestick', data: kdata, itemStyle: { color: '#f5222d', color0: '#52c41a' } },
          { type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: volumes }
        ]
      })
    },
    async generateReport() {
      this.reportLoading = true
      try {
        const res = await api.post('/api/ai/report', { ts_code: this.$route.params.ts_code })
        this.report = res.content
      } catch (e) { alert('生成失败: ' + e.message) }
      this.reportLoading = false
    }
  }
}
</script>