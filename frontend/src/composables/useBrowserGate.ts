/**
 * 作业端的浏览器门槛。
 *
 * 先看功能，再看版本号：UA 可以伪装，缺 API 的浏览器装不出来。
 * UA 只用于把提示写具体——「Chrome 96 过低」比「浏览器不受支持」有用。
 */
const MIN_CHROME = 110
const SAFARI_MIN: [number, number] = [16, 4]

/** 作业端实际用到的能力。缺一个就不该放进来，而不是进来后点不动。 */
const NEEDED_APIS: Array<[string, () => boolean]> = [
  [
    'crypto.randomUUID',
    () => typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function',
  ],
  ['structuredClone', () => typeof structuredClone === 'function'],
  ['ResizeObserver', () => typeof ResizeObserver !== 'undefined'],
]

export interface GateResult {
  blocked: boolean
  reason: string
}

function parseVersion(ua: string): {
  chrome: number | null
  safari: [number, number] | null
} {
  // Chrome 的 UA 里也带 Safari 字样，先认 Chrome
  const chrome = ua.match(/Chrome\/(\d+)/)
  const safari = ua.match(/Version\/(\d+)\.(\d+).*Safari/)
  return {
    chrome: chrome ? Number(chrome[1]) : null,
    safari: safari ? [Number(safari[1]), Number(safari[2])] : null,
  }
}

export function checkMobileBrowser(ua: string = navigator.userAgent): GateResult {
  const missing = NEEDED_APIS.filter(([, ok]) => !ok()).map(([name]) => name)
  if (missing.length) {
    return {
      blocked: true,
      reason:
        `当前浏览器缺少作业端依赖的能力：${missing.join('、')}。` +
        `请升级到 Chrome ${MIN_CHROME} 或 Safari ${SAFARI_MIN.join('.')} 以上。`,
    }
  }

  const { chrome, safari } = parseVersion(ua)
  if (chrome !== null && chrome < MIN_CHROME) {
    return {
      blocked: true,
      reason: `检测到 Chrome ${chrome}，作业端需要 Chrome ${MIN_CHROME} 及以上。请升级浏览器后重试。`,
    }
  }
  if (safari !== null) {
    const [major, minor] = safari
    if (major < SAFARI_MIN[0] || (major === SAFARI_MIN[0] && minor < SAFARI_MIN[1])) {
      return {
        blocked: true,
        reason: `检测到 Safari ${major}.${minor}，作业端需要 Safari ${SAFARI_MIN.join('.')} 及以上。请升级系统后重试。`,
      }
    }
  }
  return { blocked: false, reason: '' }
}
