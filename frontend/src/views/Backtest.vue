<template>
  <div class="container">
    <div class="card">
      <h3>策略回测</h3>
      <div style="margin:12px 0">
        <label>股票代码: </label>
        <input v-model="tsCode" placeholder="如 000001.SZ" style="padding:8px; width:200px" />
      </div>
      <div style="margin:12px 0">
        <label>策略: </label>
        <select v-model="strategy" style="padding:8px">
          <option value="dual_ma">双均线</option>
          <option value="momentum">动量</option>
          <option value="low_valuation">低估值</option>
        </select>
      </div>
      <div style="margin:12px 0" v-if="strategy === 'dual_ma'">
        <label>短期均线: </label><input v-model.number="shortWindow" type="number" style="width:60px; padding:4px" />
        <label style="margin-left:16px">长期均线: </label><input v-model.number="longWindow" type="number" style="width:60px; padding:4px" />
      </div>
      <button class="btn btn-primary" @click="runBacktest" :disabled="loading">
        {{ loading ? '回测中...' : '开始回测' }}
      </button>
    </div>
    <div class="card" v-if="result">
      <h3>回测结果</h3>
      <p>总收益率: {{ (result.total_return * 100).toFixed(2) }}%</p>
      <p>年化收益率: {{ (result.annual_return * 100).toFixed(2) }}%</p>
      <p>最大回撤: {{ (result.max_drawdown * 100).toFixed(2) }}%</p>
      <p>夏普比率: {{ result.sharpe_ratio }}</p>
      <p>胜率: {{ (result.win_rate * 100).toFixed(2) }}%</p>
      <div ref="equityChart" style="height:350px; margin-top:16px"></div>
    </div>
  </div>
</template>
<script>
import api from '../api'
import * as echarts from 'echarts'
export default {
  name: 'Backtest',
  data() {
    return { tsCode: '000001.SZ', strategy: 'dual_ma', shortWindow: 5, longWindow: 20, result: null, loading: false }
  },
  methods: {
    async runBacktest() {
      this.loading = true
      try {
        const params = {}
        if (this.strategy === 'dual_ma') {
          params.short_window = this.shortWindow
          params.long_window = this.longWindow
        }
        this.result = await api.post('/api/quant/backtest', {
          ts_code: this.tsCode, strategy: this.strategy, params
        })
        this.renderEquity()
      } catch (e) { alert('回测失败: ' + e.message) }
      this.loading = false
    },
    renderEquity() {
      if (!this.result || !this.result.equity_curve) return
      const chart = echarts.init(this.$refs.equityChart)
      chart.setOption({
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: this.result.equity_curve.map(e => e.date) },
        yAxis: { type: 'value', scale: true },
        series: [{ type: 'line', data: this.result.equity_curve.map(e => e.value), smooth: true }]
      })
    }
  }
}
</script>