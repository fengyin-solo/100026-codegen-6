<template>
  <section class="page" data-module="fault">
    <header class="page-head">
      <div>
        <h2>故障处置管理</h2>
        <p class="page-desc">维护故障记录，围绕故障编号、故障设备、故障现象、发现人员做登记、筛选与状态流转。</p>
        <p v-if="session.identity.role === 'external'" class="scope-note">
          外协账号仅可查看被共享的故障记录，操作区已收起。
        </p>
        <p v-else-if="session.identity.role === 'viewer'" class="scope-note">
          当前身份未建立共享关系，列表中的处置措施已隐藏。
        </p>
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

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <span v-if="column === MEASURE_FIELD && row._access && !row._access.canViewMeasures" class="muted-note">
              已隐藏
            </span>
            <template v-else>{{ cell(row, column) }}</template>
          </td>
          <td class="row-actions">
            <template v-if="row._access?.canOperate">
              <button
                v-for="action in actions"
                :key="action"
                class="link"
                type="button"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
              <button v-if="row._access.canDispatch" class="link" type="button" @click="openDispatch(row)">
                派发
              </button>
            </template>
            <span v-else class="muted-note">仅查看</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">{{ emptyHint }}</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条故障处置记录</span>
      <span v-if="notice" :class="noticeOk ? 'notice-ok' : 'error-text'">{{ notice }}</span>
    </footer>

    <div v-if="dispatchRow" class="modal-mask" @click.self="closeDispatch">
      <div class="modal-card">
        <h3>派发故障记录 {{ dispatchRow['故障编号'] ?? '' }}</h3>
        <p class="muted-note">派发后，目标外协账号即可查看该记录及其处置措施。</p>
        <p v-if="sharedLabel" class="muted-note">已共享：{{ sharedLabel }}</p>
        <label class="filter-item">
          <span>外协账号</span>
          <select v-model="dispatchTarget">
            <option v-for="target in dispatchTargets" :key="target" :value="target">{{ target }}</option>
          </select>
        </label>
        <div class="modal-actions">
          <button class="btn primary" type="button" :disabled="!dispatchTarget" @click="confirmDispatch">确认派发</button>
          <button class="btn ghost" type="button" @click="closeDispatch">取消</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

interface RowAccess {
  role: string
  roleLabel: string
  canOperate: boolean
  canDispatch: boolean
  canViewMeasures: boolean
}

interface Row {
  id?: number
  _access?: RowAccess
  shared_with?: string[]
  [key: string]: unknown
}

interface ActionReply {
  ok: boolean
  message: string
}

const ENDPOINT = '/api/fault'
const MEASURE_FIELD = '处置措施'
const DISPATCH_ACTION = '派发'
const columns = ["故障编号", "故障设备", "故障现象", "发现人员", "发现时间", "严重等级", "处置措施", "故障状态"]
const actions = ["确认故障", "开始处置", "确认消除"]
const stats = [{"label": "未消除故障", "value": 0}, {"label": "处置中故障", "value": 0}, {"label": "本月故障数", "value": 0}]

const session = useSessionStore()

const rows = ref<Row[]>([])
const total = ref(0)
const notice = ref('')
const noticeOk = ref(true)
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const dispatchRow = ref<Row | null>(null)
const dispatchTarget = ref('')
const dispatchTargets = ref<string[]>([])

const emptyHint = computed(() =>
  session.identity.role === 'external'
    ? '暂无共享给你的故障记录'
    : '暂无故障处置数据，可先登记故障记录',
)

const sharedLabel = computed(() => {
  const shared = dispatchRow.value?.shared_with
  return shared && shared.length ? shared.join('、') : ''
})

function cell(row: Row, column: string): string {
  const value = row[column]
  return value === null || value === undefined || value === '' ? '—' : String(value)
}

function resetFilters() {
  filters.value = {}
  void reload()
}

async function exportRows() {
  notice.value = ''
  try {
    const response = await request(`${ENDPOINT}/export`)
    if (!response.ok) {
      throw new Error(`接口返回 ${response.status}，导出未完成`)
    }
    const url = URL.createObjectURL(await response.blob())
    const link = document.createElement('a')
    link.href = url
    link.download = 'fault-export.json'
    link.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    noticeOk.value = false
    notice.value = error instanceof Error ? error.message : '故障处置清单导出失败'
  }
}

function openCreate() {
  noticeOk.value = false
  notice.value = '故障记录登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  notice.value = ''
  try {
    const reply = await postAction(row, { action })
    noticeOk.value = reply.ok
    notice.value = reply.message
    // 无论生效还是被拦截都重取一遍：被拦截时列表保持原样，与后端对齐。
    await reload()
  } catch (error) {
    noticeOk.value = false
    notice.value = error instanceof Error ? error.message : '故障处置操作失败'
  }
}

function openDispatch(row: Row) {
  dispatchRow.value = row
  dispatchTarget.value = dispatchTargets.value[0] ?? ''
}

function closeDispatch() {
  dispatchRow.value = null
}

async function confirmDispatch() {
  const row = dispatchRow.value
  if (!row || !dispatchTarget.value) {
    return
  }
  notice.value = ''
  try {
    const reply = await postAction(row, { action: DISPATCH_ACTION, target: dispatchTarget.value })
    noticeOk.value = reply.ok
    notice.value = reply.message
    if (reply.ok) {
      closeDispatch()
    }
    await reload()
  } catch (error) {
    noticeOk.value = false
    notice.value = error instanceof Error ? error.message : '故障记录派发失败'
  }
}

async function postAction(row: Row, values: Record<string, string>): Promise<ActionReply> {
  const response = await request(`${ENDPOINT}/${row.id}/actions`, {
    method: 'POST',
    body: JSON.stringify({ values }),
  })
  if (!response.ok) {
    throw new Error(`接口返回 ${response.status}，动作未送达`)
  }
  return (await response.json()) as ActionReply
}

async function loadDispatchTargets() {
  if (session.identity.role !== 'duty') {
    dispatchTargets.value = []
    return
  }
  try {
    const response = await request(`${ENDPOINT}/dispatch-targets`)
    if (!response.ok) {
      throw new Error(`接口返回 ${response.status}`)
    }
    const payload = (await response.json()) as { targets?: string[] }
    dispatchTargets.value = payload.targets ?? []
  } catch {
    dispatchTargets.value = []
  }
}

async function reload() {
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error(`接口返回 ${response.status}，列表未更新`)
    }
    const payload = (await response.json()) as { items?: Row[]; total?: number }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    noticeOk.value = false
    notice.value = error instanceof Error ? error.message : '故障处置列表读取失败'
  }
}

// 换班或切换身份后，可见内容与可执行按钮按新的受控关系重算。
watch(() => session.identityKey, () => {
  closeDispatch()
  void reload()
  void loadDispatchTargets()
})

onMounted(() => {
  void reload()
  void loadDispatchTargets()
})
</script>
