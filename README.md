# AI 日报

一个无需自建服务器的 AI 资讯网站。GitHub Actions 每小时第 17 分钟尝试更新，GitHub Pages 发布静态页面；定时任务可能排队，页面会显示实际更新时间。

- 网站：https://homerzhou6778-tech.github.io/ai-daily/
- [使用与信源说明](https://homerzhou6778-tech.github.io/ai-daily/about.html) · [运行与维护](docs/OPERATIONS.md)
- 工作流：仓库 Actions → **Update and publish AI daily** → Run workflow
- 手机与桌面视图、搜索、来源筛选、24 小时列表、规则精选及 RSS 订阅。
- 无需自备 API Key；保留原始标题，不生成模型点评或虚构摘要。

## 当前信源

公开 RSS/Atom：OpenAI News、Hugging Face、Google DeepMind、Google AI、Microsoft AI、NVIDIA Generative AI、Wired AI、InfoQ 中文、宝玉、Simon Willison。

另外采集 Anthropic News 的公开页面、Follow Builders 的三个公开 JSON 文件。

公开示例地址见 `feeds/follow.example.opml`。采集入口为 `scripts/update_news.py --public-only`；它强制使用公开示例，不接受私人 OPML，不调用 AgentMail、X API、SocialData、TikHub、Jina 或模型 API。原项目的其他适配器仍保留供维护参考，但不会进入部署流程。

只有至少 6 个来源成功时才生成新快照。单个信源异常在来源状态中显示；超过 4 小时没有新快照，页面显示过期提示。已抓取的公开历史通过 Actions cache 保存 21 天；缓存不是永久备份。日历日期筛选严格使用发布时间，历史记录不会被伪装成新消息。

## 本地运行

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scripts/update_news.py --public-only --output-dir data
python scripts/generate_feed.py --data-dir data
python scripts/build_site.py --output _site
python -m http.server 8080 --directory _site
```

`_site` 必须是一个尚不存在的目录，以免覆盖错误路径；重复构建可通过 `--output` 指定新目录。

```sh
python -m pytest -q tests/test_public_profile.py tests/test_ai_relevance.py tests/test_story_merge.py tests/test_published_at_guard.py tests/test_health.py
node --check assets/app.js
node --check assets/public-health.js
```

## 部署

GitHub 仓库 Settings → Pages → Source 选择 **GitHub Actions**。首次推送 main 或手动运行工作流即可部署；之后每小时自动采集。工作流使用 GitHub 自动提供的短期身份发布，无需另存 PAT。

公开仓库的定时任务长时间无仓库活动可能被 GitHub 停用，需要在 Actions 重新启用；这属于 GitHub 托管服务的限制。失败运行会保留上次成功的部署，不能把旧页面仍能打开理解为采集正常。

每次发布后，工作流还会读取真正的线上页面、RSS 和数据，确认本次新快照已可见。维护者另设每天两次的 Codex 巡检，只报告异常或恢复；该本地任务不随仓库复制。详见[运行与维护](docs/OPERATIONS.md)。

## 发布边界

API Key、token、cookie、登录状态、私有订阅和任何邮件内容不得提交。`data/` 和 `_site/` 均忽略，不提交生成数据；Pages 构建只复制明确列出的公开 JSON、RSS 和静态资源，不发布原始归档、邮件摘要或运行环境。日志只输出抓取状态和条数。

未来如要接邮件，应另设私有处理流程；不要在此公共站点打开邮件发布开关。不要把私有订阅 URL 放进公开示例文件。

## 来源与许可

基于 [LearnPrompt/ai-news-radar](https://github.com/LearnPrompt/ai-news-radar)，初始版本 `f138685aea3f928c50ab00507a8848a5463e3654`。保留上游 MIT 许可与伯乐 Skill，感谢原作者的采集器、筛选规则和双视图页面。

本衍生版的入口和部署以本 README、`docs/PUBLIC_PROFILE.md` 及 `.github/workflows/update-pages.yml` 为准；其他上游文档包含原站点和高级集成的历史说明，不代表本站启用了它们。
