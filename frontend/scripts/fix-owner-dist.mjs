import { copyFileSync, existsSync } from 'node:fs'

/**
 * 门户构建的产物收尾。
 *
 * 入口固定在 owner/index.html（这样 base 与目录能对上），Vite 会按入口路径
 * 把它输出到 dist/owner/owner/index.html，而静态服务器与 SPA 回退都只认
 * dist/owner/index.html。这里补一次拷贝，不引额外依赖。
 */
const from = 'dist/owner/owner/index.html'
const to = 'dist/owner/index.html'

if (existsSync(from)) {
  copyFileSync(from, to)
  console.log('owner portal entry copied to dist/owner/index.html')
} else {
  console.warn('owner portal entry not found, skip copying:', from)
}
