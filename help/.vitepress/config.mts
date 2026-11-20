import { defineConfig } from 'vitepress'

export default defineConfig({
  lang: 'zh-CN',
  title: 'Conflua 用户帮助',
  description: 'Conflua 协作使用手册与桌面版参考',
  base: '/conflua/',
  srcDir: 'content',
  cleanUrls: false,
  ignoreDeadLinks: false,
  vite: {
    publicDir: false,
  },
  themeConfig: {
    nav: [{ text: '手册首页', link: '/' }],
    sidebar: [
      {
        text: '使用手册',
        items: [
          { text: '跑通一轮实现与审查', link: '/guide/first-handoff.html' },
          { text: '组织工作空间', link: '/guide/workspaces.html' },
          { text: '配置协作成员', link: '/guide/members.html' },
          { text: '把消息交给正确的人', link: '/guide/routing.html' },
          { text: '跟踪执行与介入', link: '/guide/tracking.html' },
          { text: '让 Agent 参与协作', link: '/guide/agents.html' },
        ],
      },
      {
        text: '参考',
        items: [
          { text: '运行与排障', link: '/reference/troubleshooting.html' },
          { text: 'Windows 桌面使用指南', link: '/reference/windows.html' },
          { text: 'macOS 桌面使用指南', link: '/reference/macos.html' },
        ],
      },
    ],
  },
})
