import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { readFileSync } from 'node:fs'

/**
 * 一个工程出两个构建产物：
 *   vite build                → base /admin/、入口 index.html、产物 dist/admin
 *   vite build --mode owner   → base /owner/、入口 owner.html、产物 dist/owner
 *
 * 用 mode 而不是环境变量：npm 脚本在 Windows 上走 cmd，`APP_TARGET=x vite` 不生效，
 * 引 cross-env 又多一个依赖。mode 是 vite 原生参数，跨平台且不需要新包。
 *
 * 两套界面不能共用一个 base：Vite 的 base 是构建期常量，两条路径只能两次构建。
 * 好处是产物彻底分开，将来真要拆成两个工程，把对应目录搬走即可。
 */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const isOwner = mode === 'owner'
  const proxyTarget = env.VITE_API_PROXY_TARGET || 'http://localhost:8000'
  // 开发与预览共用同一份代理：只配 server 的话，`vite preview` 起来后所有 /api 都是 404
  const proxy = {
    '/api': { target: proxyTarget, changeOrigin: true },
    '/uploads': { target: proxyTarget, changeOrigin: true },
    '/media': { target: proxyTarget, changeOrigin: true },
    '/apehub-web': { target: proxyTarget, changeOrigin: true },
  }

  return {
    base: isOwner ? '/owner/' : '/admin/',
    plugins: [
      vue(),
      {
        name: 'owner-dev-entry',
        apply: 'serve' as const,
        transformIndexHtml: {
          order: 'pre' as const,
          handler(html: string) {
            // build 走 rollupOptions.input，dev 的 SPA fallback 永远读 root/index.html。
            // 门户 dev 必须换成自己的入口，否则加载后台 main.ts 后被 /admin/ 路由接管。
            if (!isOwner) return html
            return readFileSync(
              fileURLToPath(new URL('./owner/index.html', import.meta.url)),
              'utf-8'
            )
          },
        },
      },
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
        // vue3-verify package.json exports has a broken style.css mapping;
        // alias the css path directly to the real file
        'vue3-verify/dist/vue3-verify.css': fileURLToPath(
          new URL('./node_modules/vue3-verify/dist/vue3-verify.css', import.meta.url)
        ),
      },
    },
    server: {
      host: '127.0.0.1',
      port: isOwner ? 5174 : 5173,
      proxy,
    },
    preview: {
      host: '127.0.0.1',
      port: isOwner ? 4174 : 4173,
      proxy,
    },
    build: {
      outDir: isOwner ? 'dist/owner' : 'dist/admin',
      emptyOutDir: true,
      rollupOptions: {
        // 门户入口放在 owner/ 子目录下，产物才会落在 dist/owner/index.html，
        // 与 base '/owner/' 对应；否则产物叫 owner.html，SPA 回退找不到 index
        input: fileURLToPath(
          new URL(isOwner ? './owner/index.html' : './index.html', import.meta.url)
        ),
      },
    },
  }
})
