<template>
  <div class="container">
    <h2 style="margin-bottom:16px">市场概览</h2>
    <div v-if="overview" class="card">
      <p>股票总数: {{ overview.total_stocks }}</p>
      <p>最新交易日: {{ overview.latest_date || '无数据' }}</p>
      <p v-if="overview.latest_date">
        上涨: <span class="up">{{ overview.advancers }}</span> |
        下跌: <span class="down">{{ overview.decliners }}</span> |
        平盘: {{ overview.flat }}
      </p>
    </div>
    <div class="card" v-if="topUp.length">
      <h3>涨幅榜</h3>
      <table class="table">
        <thead><tr><th>代码</th><th>名称</th><th>收盘</th><th>涨跌幅</th></tr></thead>
        <tbody>
          <tr v-for="s in topUp" :key="s.ts_code">
            <td><router-link :to="'/stocks/' + s.ts_code">{{ s.ts_code }}</router-link></td>
            <td>{{ s.name }}</td>
            <td>{{ s.close }}</td>
            <td class="up">{{ s.pct_chg }}%</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="card" v-if="topDown.length">
      <h3>跌幅榜</h3>
      <table class="table">
        <thead><tr><th>代码</th><th>名称</th><th>收盘</th><th>涨跌幅</th></tr></thead>
        <tbody>
          <tr v-for="s in topDown" :key="s.ts_code">
            <td><router-link :to="'/stocks/' + s.ts_code">{{ s.ts_code }}</router-link></td>
            <td>{{ s.name }}</td>
            <td>{{ s.close }}</td>
            <td class="down">{{ s.pct_chg }}%</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
<script>
import api from '../api'
export default {
  name: 'Dashboard',
  data() { return { overview: null, topUp: [], topDown: [] } },
  async mounted() {
    try {
      this.overview = await api.get('/api/market/overview')
      this.topUp = await api.get('/api/market/top-movers?direction=up&limit=10')
      this.topDown = await api.get('/api/market/top-movers?direction=down&limit=10')
    } catch (e) { console.error(e) }
  }
}
</script>