/** 统一请求封装：拼后端地址、带上当前操作者身份、抛网络错误、给页脚留一句可读的说明。 */
const API_BASE = import.meta.env.VITE_API_BASE ?? ''

let identityHeaders: Record<string, string> = {}

/** 会话身份变化时由 session store 调用，后续请求都按新的受控关系出数。 */
export function setIdentityHeaders(headers: Record<string, string>) {
  identityHeaders = headers
}

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  return fetch(url, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...identityHeaders, ...(init?.headers ?? {}) },
  }).catch((error: unknown) => {
    const detail = error instanceof Error ? error.message : '请求未送达'
    throw new Error(`接口请求失败：${detail}`)
  })
}

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await request(path)
  if (!response.ok) {
    throw new Error(`接口返回 ${response.status}，数据未更新`)
  }
  return (await response.json()) as T
}
