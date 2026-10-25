<template>
  <div class="app">
    <nav class="nav">
      <div class="container nav-inner">
        <a href="/" class="logo">X2Stock</a>
        <router-link to="/">仪表盘</router-link>
        <router-link to="/stocks">股票列表</router-link>
        <router-link to="/backtest">回测</router-link>
        <router-link to="/assistant">AI 助手</router-link>
      </div>
    </nav>
    <router-view />
  </div>
</template>
<style>
.nav { background: #001529; padding: 0; }
.nav-inner { display: flex; align-items: center; gap: 24px; height: 48px; }
.nav-inner a { color: rgba(255,255,255,0.65); font-size: 14px; }
.nav-inner a.router-link-active { color: #fff; }
.logo { color: #fff !important; font-weight: bold; font-size: 18px; margin-right: 16px; }
</style>