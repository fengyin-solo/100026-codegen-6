import { defineStore } from 'pinia'

import { setIdentityHeaders } from '@/api/client'

export type Role = 'duty' | 'external' | 'viewer'

export interface Identity {
  key: string
  operator: string
  role: Role
  roleLabel: string
  shiftLabel: string
}

/** 预置身份：两个当班处理人员用于换班，外协账号与其他人员用于受控可见性演示。 */
export const IDENTITIES: Identity[] = [
  { key: 'duty-day', operator: '张伟', role: 'duty', roleLabel: '当班处理人员', shiftLabel: '白班 08:00-20:00' },
  { key: 'duty-night', operator: '李强', role: 'duty', roleLabel: '当班处理人员', shiftLabel: '夜班 20:00-08:00' },
  { key: 'external', operator: '王外协', role: 'external', roleLabel: '外协账号', shiftLabel: '外协驻场' },
  { key: 'viewer', operator: '赵参观', role: 'viewer', roleLabel: '其他人员', shiftLabel: '非当班' },
]

function findIdentity(key: string): Identity {
  return IDENTITIES.find((item) => item.key === key) ?? IDENTITIES[0]
}

function applyIdentityHeaders(identity: Identity) {
  // 姓名含非 ASCII 字符，按 URL 编码放进请求头，由后端解码还原。
  setIdentityHeaders({
    'X-Operator-Name': encodeURIComponent(identity.operator),
    'X-Operator-Role': identity.role,
  })
}

// 模块加载时先按默认身份落一次请求头，保证任何视图首次请求就带身份，不依赖挂载顺序。
applyIdentityHeaders(IDENTITIES[0])

export const useSessionStore = defineStore('session', {
  state: () => ({
    identityKey: IDENTITIES[0].key,
    scope: '光伏电站运维管理平台',
  }),
  getters: {
    identity: (state) => findIdentity(state.identityKey),
    operator(): string {
      return this.identity.operator
    },
    shiftLabel(): string {
      return this.identity.shiftLabel
    },
    canOperate(): boolean {
      return this.identity.role === 'duty'
    },
  },
  actions: {
    setIdentity(key: string) {
      if (this.identityKey === key) {
        return
      }
      this.identityKey = key
      applyIdentityHeaders(this.identity)
    },
    /** 换班：在两位当班处理人员之间交接，可见内容与按钮随新身份重算。 */
    switchShift() {
      this.setIdentity(this.identityKey === 'duty-day' ? 'duty-night' : 'duty-day')
    },
  },
})
