import { defineStore } from 'pinia'

import { fetchJson, request, setSessionAccount } from '@/api/client'

export interface AccountItem {
  id: string
  name: string
  role: string
  role_label: string
}

interface SessionView {
  account: AccountItem
  on_duty: boolean
  shift_label: string
  duty_handlers: string[]
  shareable?: AccountItem[]
}

export const useSessionStore = defineStore('session', {
  state: () => ({
    accountId: 'op_chen',
    operator: '陈当班',
    role: 'handler',
    roleLabel: '处理人员',
    onDuty: true,
    shiftLabel: '白班 08:00-20:00',
    scope: '光伏电站运维管理平台',
    ready: false,
    accounts: [] as AccountItem[],
    shareable: [] as AccountItem[],
  }),
  getters: {
    // 是否当班处理人员：决定派发入口与操作区是否放开
    canOperate: (state) => state.role === 'handler' && state.onDuty,
  },
  actions: {
    applySession(view: SessionView) {
      this.accountId = view.account.id
      this.operator = view.account.name
      this.role = view.account.role
      this.roleLabel = view.account.role_label
      this.onDuty = view.on_duty
      this.shiftLabel = view.shift_label
      this.shareable = view.shareable ?? []
    },
    async bootstrap() {
      // 起页时对齐后端受控关系：账号清单 + 当前会话快照
      setSessionAccount(this.accountId)
      const [accounts, session] = await Promise.all([
        fetchJson<{ items: AccountItem[] }>('/api/access/accounts'),
        fetchJson<SessionView>('/api/access/session'),
      ])
      this.accounts = accounts.items
      this.applySession(session)
      this.ready = true
    },
    async switchAccount(accountId: string) {
      setSessionAccount(accountId)
      const session = await fetchJson<SessionView>('/api/access/session')
      this.applySession(session)
    },
    async rotateShift() {
      // 换班：后端移交当班关系，再拉会话快照，页面按新的受控关系重算
      const response = await request('/api/access/shift/rotate', { method: 'POST' })
      if (!response.ok) {
        throw new Error('换班请求未生效，请稍后重试')
      }
      const session = await fetchJson<SessionView>('/api/access/session')
      this.applySession(session)
    },
    setShift(label: string) {
      this.shiftLabel = label
    },
  },
})
