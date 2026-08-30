# 境外涉华监测日报（云端 · 不依赖电脑）

每天北京时间 08:00，在 **GitHub Actions 云端**自动抓取 Reuters / AP / AFP / BBC / DW / France24 / FT / NYT / WSJ / The Economist / Bloomberg / The Guardian 的涉华报道，生成一份**移动端优先的中文日报**，托管到 **GitHub Pages**。手机浏览器打开固定网址就是最新一期，加到主屏即是一个"新闻 App"。**整个过程不依赖你的电脑开机。**

## 你要做的 3 步（一次性）

1. **建仓库**：在 GitHub 新建一个公开仓库（如 `china-media-digest`），把本目录内容 push 上去。
   ```bash
   git init
   git add .
   git commit -m "init"
   git remote add origin https://github.com/<你的用户名>/china-media-digest.git
   git push -u origin main
   ```
2. **开 Pages**：仓库 Settings → Pages → Source 选 `main` 分支、`/docs` 目录 → Save。
   几分钟后访问 `https://<你的用户名>.github.io/china-media-digest/`。
3. **（可选）配 LLM**：Settings → Secrets → 添加 `OPENAI_API_KEY`（及可选的 `OPENAI_BASE_URL`、`OPENAI_MODEL`）。
   不配也能跑，只是摘要退化为英文原文摘录；配了就是中文摘要 + 立场标注 + 要点。

之后每天 08:00 自动出报，无需任何操作。想立刻看效果，在仓库 Actions 页点 `Run workflow` 手动跑一次。

## 手机端"自动更新"怎么用

- 打开上面的 Pages 网址 → 浏览器菜单「添加到主屏幕」→ 起名"外媒涉华日报"。
- 之后像开 App 一样点它：内容已是当天 08:00 的最新日报，无需刷新、不依赖电脑。

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `sources.yaml` | 媒体 RSS 源 + 关键词，按需增删 |
| `generate.py` | 抓取→过滤→主题分类→(LLM)摘要→渲染 HTML |
| `.github/workflows/daily.yml` | 云端定时任务，每天 08:00（UTC 00:00） |
| `docs/index.html` | 生成的日报（Pages 托管，每次覆盖为最新） |
| `docs/digest-YYYY-MM-DD.html` | 往期归档，可回溯 |

## 说明

- RSS 抓取免费、无需 Key；仅中文摘要用到可选 LLM。
- 立场标注为模型辅助判断，日报带免责声明，重要信息以原文为准。
- 涉及台湾、香港、澳门统一表述为"中国台湾/中国香港/中国澳门"。
