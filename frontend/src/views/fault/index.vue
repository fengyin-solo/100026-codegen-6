<template>
  <section class="page" data-module="fault">
    <header class="page-head">
      <div>
        <h2>故障处置管理</h2>
        <p class="page-desc">维护故障记录，围绕故障编号、故障设备、故障现象、发现人员做登记、筛选与状态流转。</p>
        <p class="shared-note">{{ viewHint }}</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记故障记录</button>
        <button class="btn" type="button" @click="exportRows">导出故障处置清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <div v-if="dispatchRow" class="dispatch-panel">
      <span>派发故障记录 {{ dispatchRow['故障编号'] }} 给：</span>
      <select v-model="dispatchTarget">
        <option disabled value="">选择账号</option>
        <option v-for="item in session.shareable" :key="item.id" :value="item.id">
          {{ item.name }}（{{ item.role_label }}）
        </option>
      </select>
      <span v-if="dispatchRow.shared_with?.length" class="shared-note">
        已共享：{{ dispatchRow.shared_with.join('、') }}
      </span>
      <button class="btn primary" type="button" @click="confirmDispatch">确认派发</button>
      <button class="btn ghost" type="button" @click="cancelDispatch">取消</button>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <template v-if="row.permissions?.can_dispatch || row.permissions?.can_operate">
              <button
                v-if="row.permissions?.can_dispatch"
                class="link"
                type="button"
                @click="openDispatch(row)"
              >
                派发
              </button>
              <button
                v-for="action in actions"
                v-show="row.permissions?.can_operate"
                :key="action"
                class="link"
                type="button"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
            </template>
            <span v-else class="collapsed-note">操作区已收起</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">{{ emptyHint }}</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条故障处置记录</span>
      <span v-if="noticeMessage" class="ok-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

interface RowPermissions {
  can_view_measure: boolean
  can_dispatch: boolean
  can_operate: boolean
}

interface Row {
  id?: number
  permissions?: RowPermissions
  shared_with?: string[]
  [key: string]: unknown
}

const ENDPOINT = '/api/fault'
const columns = ["故障编号", "故障设备", "故障现象", "发现人员", "发现时间", "严重等级", "处置措施", "故障状态"]
const actions = ["确认故障", "开始处置", "确认消除"]
const stats = [{"label": "未消除故障", "value": 0}, {"label": "处置中故障", "value": 0}, {"label": "本月故障数", "value": 0}]

const session = useSessionStore()

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const dispatchRow = ref<Row | null>(null)
const dispatchTarget = ref('')

// 受控视图说明：让当前账号能看到什么、能做什么一眼可见
const viewHint = computed(() => {
  if (session.role === 'handler' && session.onDuty) {
    return '当班处理人员：派发入口已开放，可执行处置动作'
  }
  if (session.role === 'handler') {
    return '处理人员未当班：操作区已收起，换班后按新的受控关系重算'
  }
  if (session.role === 'external') {
    return '外协账号：仅可查看被共享的记录，操作区已收起'
  }
  return '普通人员：未建立共享关系的记录不显示处置措施，操作区已收起'
})

const emptyHint = computed(() =>
  session.role === 'external' ? '暂无共享给当前账号的故障记录' : '暂无故障处置数据，可先登记故障记录',
)

function resetFilters() {
  filters.value = {}
  void reload()
}

async function exportRows() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/export`)
    if (!response.ok) {
      throw new Error('故障处置清单导出失败')
    }
    const payload = await response.json()
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = 'fault-export.json'
    link.click()
    URL.revokeObjectURL(link.href)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '故障处置清单导出失败'
  }
}

function openCreate() {
  errorMessage.value = '故障记录登记入口尚未接入审批流'
}

function openDispatch(row: Row) {
  dispatchRow.value = row
  dispatchTarget.value = ''
  errorMessage.value = ''
  noticeMessage.value = ''
}

function cancelDispatch() {
  dispatchRow.value = null
  dispatchTarget.value = ''
}

async function confirmDispatch() {
  const row = dispatchRow.value
  if (!row) {
    return
  }
  if (!dispatchTarget.value) {
    errorMessage.value = '请先选择派发对象'
    return
  }
  await submitAction(row, { action: '派发', target: dispatchTarget.value })
  if (!errorMessage.value) {
    cancelDispatch()
  }
}

async function runAction(action: string, row: Row) {
  await submitAction(row, { action })
}

async function submitAction(row: Row, values: Record<string, string>) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify(values),
    })
    const payload = (await response.json()) as { ok: boolean; message?: string }
    // 被拦截的提交：记录保持原样，重新拉取服务端数据后再提示原因
    await reload()
    if (!response.ok || !payload.ok) {
      errorMessage.value = payload.message ?? '故障处置动作已被拦截，记录保持原样'
      return
    }
    noticeMessage.value = payload.message ?? '故障处置动作已生效'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '故障处置操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  noticeMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('故障记录列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '故障处置列表读取失败'
  }
}

// 会话就绪、切换账号、换班后都按新的受控关系重算可见内容与按钮
watch(
  () => [session.ready, session.accountId, session.shiftLabel] as const,
  ([ready]) => {
    if (ready) {
      cancelDispatch()
      void reload()
    }
  },
  { immediate: true },
)
</script>
