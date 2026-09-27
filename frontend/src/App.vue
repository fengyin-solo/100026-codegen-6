<template>
  <div class="app-shell">
    <aside class="app-side">
      <h1 class="app-title">光伏电站运维管理平台</h1>
      <nav class="nav-list">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item">
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="app-main">
      <header class="app-head">
        <span class="head-desc">面向集中式与分布式光伏电站的巡检计划、组件清洗、逆变器检修、发电监测、备品备件与故障处置的综合运维管理后台。</span>
        <span class="head-user">
          当前值班：{{ store.operator }}（{{ store.identity.roleLabel }}） · {{ store.shiftLabel }}
          <select class="identity-select" :value="store.identityKey" @change="onIdentityChange">
            <option v-for="item in IDENTITIES" :key="item.key" :value="item.key">
              {{ item.operator }} · {{ item.roleLabel }}
            </option>
          </select>
          <button class="btn ghost" type="button" @click="store.switchShift()">换班</button>
        </span>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { IDENTITIES, useSessionStore } from '@/stores/session'

const store = useSessionStore()

function onIdentityChange(event: Event) {
  store.setIdentity((event.target as HTMLSelectElement).value)
}

const navItems = [{ label: "运营概览", path: "/" }, { label: "电站档案", path: "/plant" }, { label: "巡检计划", path: "/inspection" }, { label: "组件清洗", path: "/panel_clean" }, { label: "逆变器管理", path: "/inverter" }, { label: "发电监测", path: "/power_data" }, { label: "故障处置", path: "/fault" }, { label: "备件管理", path: "/spare_part" }, { label: "箱变管理", path: "/transformer" }, { label: "开关站管理", path: "/switchgear" }, { label: "关口计量", path: "/meter" }, { label: "气象监测", path: "/weather" }, { label: "并网调度", path: "/grid_connect" }, { label: "电缆线路", path: "/cable" }, { label: "安防巡视", path: "/security" }, { label: "定期检修", path: "/maintenance" }, { label: "汇流箱管理", path: "/dc_box" }, { label: "能效分析", path: "/energy_saving" }, { label: "安全培训", path: "/training" }]
</script>
