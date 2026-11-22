import { onMounted, onUnmounted, ref } from 'vue'

/**
 * 扫码枪接入：广播优先，键盘模拟兜底。
 *
 * 两种形态走同一条判定——能拿到广播就用广播，拿不到就吃键盘模拟。
 * APK 形态由原生层注入 `window.__scanBroadcast`；浏览器形态没有这条通道，
 * 扫码枪以极快速度敲字符并以 Enter 结尾，靠时间间隔把它和人工输入区分开。
 *
 * 输入框聚焦时本 composable 不介入，字符由输入框自己收，
 * 避免同一串编码被消费两次。这也意味着焦点丢失时扫码不会丢——见 `recover`。
 */
const CHAR_GAP_MS = 60
const MIN_LENGTH = 3

type ScanHandler = (code: string) => void

export function useScanGun(onScan: ScanHandler) {
  let buffer = ''
  let lastAt = 0
  const usingBroadcast = ref(false)

  function handleKey(e: KeyboardEvent) {
    const tag = (e.target as HTMLElement)?.tagName
    // 输入框自己处理，全局不再收一遍
    if (tag === 'INPUT' || tag === 'TEXTAREA') return

    const now = Date.now()
    if (now - lastAt > CHAR_GAP_MS) buffer = ''
    lastAt = now

    if (e.key === 'Enter') {
      if (buffer.length >= MIN_LENGTH) {
        e.preventDefault()
        onScan(buffer)
      }
      buffer = ''
      return
    }
    if (e.key.length === 1) buffer += e.key
  }

  onMounted(() => {
    const native = (window as any).__scanBroadcast
    if (typeof native === 'function') {
      usingBroadcast.value = true
      ;(window as any).__scanHandler = onScan
      return
    }
    window.addEventListener('keydown', handleKey, true)
  })

  onUnmounted(() => {
    if (usingBroadcast.value) {
      delete (window as any).__scanHandler
      return
    }
    window.removeEventListener('keydown', handleKey, true)
  })

  return { usingBroadcast }
}
