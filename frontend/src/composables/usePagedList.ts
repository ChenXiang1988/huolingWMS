import { reactive, ref } from 'vue'

type Fetcher = (params: Record<string, any>) => Promise<any>

/**
 * 分页列表的通用状态机。
 *
 * 九个页面重复的是同一件事：查询条件、页码、总数、加载态、取数。
 * 抽这一层是为了让页面只写"列怎么展示"，而不是每页再抄一遍翻页逻辑。
 *
 * 页面模板本身不抽——每个页面字段不同，抽成配置驱动会让改一个列宽都要翻两层。
 */
export function usePagedList(fetcher: Fetcher, initialQuery: Record<string, any> = {}) {
  const items = ref<any[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const loading = ref(false)
  const query = reactive<Record<string, any>>({ ...initialQuery })

  async function fetch() {
    loading.value = true
    try {
      const data: any = await fetcher({
        ...cleanParams(query),
        page: page.value,
        page_size: pageSize.value,
      })
      items.value = data?.items || []
      total.value = data?.total || 0
    } catch (e) {
      console.error('列表加载失败', e)
      items.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  /** 换条件后回到第一页，否则会在一个不存在的页码上查询。 */
  async function search() {
    page.value = 1
    await fetch()
  }

  async function reset() {
    Object.keys(query).forEach((k) => {
      query[k] = initialQuery[k] ?? ''
    })
    page.value = 1
    await fetch()
  }

  function onPageChange(p: number) {
    page.value = p
    fetch()
  }

  function onSizeChange(s: number) {
    pageSize.value = s
    page.value = 1
    fetch()
  }

  return {
    items,
    total,
    page,
    pageSize,
    loading,
    query,
    fetch,
    search,
    reset,
    onPageChange,
    onSizeChange,
  }
}

/** 空字符串与 undefined 不作为筛选条件发给后端，否则会被当成"筛选空值"。 */
function cleanParams(query: Record<string, any>) {
  const out: Record<string, any> = {}
  Object.entries(query).forEach(([k, v]) => {
    if (v !== '' && v !== null && v !== undefined) out[k] = v
  })
  return out
}
