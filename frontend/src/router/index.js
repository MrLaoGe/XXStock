import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import StockList from '../views/StockList.vue'
import StockDetail from '../views/StockDetail.vue'
import Backtest from '../views/Backtest.vue'
import AIAssistant from '../views/AIAssistant.vue'
const routes = [
  { path: '/', component: Dashboard },
  { path: '/stocks', component: StockList },
  { path: '/stocks/:ts_code', component: StockDetail },
  { path: '/backtest', component: Backtest },
  { path: '/assistant', component: AIAssistant }
]
export default createRouter({ history: createWebHistory(), routes })