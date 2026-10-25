<template>
  <div class="container">
    <div class="card">
      <input v-model="search" placeholder="搜索代码或名称" @input="load" style="padding:8px; width:300px" />
      <button class="btn btn-primary" style="margin-left:8px" @click="load">搜索</button>
    </div>
    <div class="card">
      <table class="table">
        <thead><tr><th>代码</th><th>名称</th><th>行业</th><th>地区</th><th>市场</th></tr></thead>
        <tbody>
          <tr v-for="s in stocks" :key="s.ts_code">
            <td><router-link :to="'/stocks/' + s.ts_code">{{ s.ts_code }}</router-link></td>
            <td>{{ s.name }}</td>
            <td>{{ s.industry }}</td>
            <td>{{ s.area }}</td>
            <td>{{ s.market }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="!stocks.length">暂无数据。请在设置 TUSHARE_TOKEN 后运行采集，或加载示例数据。</p>
    </div>
  </div>
</template>
<script>
import api from '../api'
export default {
  name: 'StockList',
  data() { return { stocks: [], search: '' } },
  async mounted() { this.load() },
  methods: {
    async load() {
      try {
        const res = await api.get('/api/stocks/?search=' + encodeURIComponent(this.search))
        this.stocks = res.items
      } catch (e) { console.error(e) }
    }
  }
}
</script>