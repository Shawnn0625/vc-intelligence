# VC Intelligence V2

按研究工作台界面重构，延续原有技术方案：**Streamlit + Gemini + SQLite + n8n + Python**。

## 快速开始

```bash
cd vc_intelligence_v2
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

第一次打开页面，左侧 `>` 展开 Gemini 设置，填入你之前已经使用过的 **Gemini API Key** 和能够调用的模型 ID。也可以通过环境变量 `GEMINI_API_KEY` / `GEMINI_MODEL` 配置（注意：程序不会自动加载 .env，请用 shell 或部署环境加载）。

主页初始统计为 0，**不冒充实时数据**。点击左侧「载入 5 条演示新闻」展示交互；演示项目均明确标记为 `DEMO`。

## 功能

- **AI News**：分组入口、新闻明细、统计、n8n JSON 导入；新闻为本地持久化数据
- **公司研究**：调用已有 Gemini API，可选 Google Search，自动保存报告与引用，支持研究笔记和历史记录
- **产业链**：简化行业分层框架 + Gemini 公司生态位研究（不是可编辑知识图谱）
- **可比公司**：Gemini 生成比较与筛选逻辑（不是自动同步的结构化财务数据库）
- **继续追问**：依据当前模块和最新公司研究上下文回答；追问对话目前仅保留浏览器 session

### n8n 接入方式 1：导出 JSON
在 n8n 里将新闻整理成如下数组，下载为 `.json`，从 Streamlit 侧边栏导入：

```json
[
  {
    "title": "新闻标题",
    "summary": "中文摘要",
    "category": "基模及 Agent",
    "company": "公司名",
    "source": "来源机构",
    "url": "https://example.com/article-unique-id",
    "published_at": "2026-11-21",
    "noteworthy": true,
    "project_update": false
  }
]
```

`category` 只接受「基模及 Agent」「融资与创业公司」「AI Infra & Robotics」。建议每条提供唯一 URL，以便重复同步时去重；**没有 URL 的条目不会自动去重**。

### n8n 接入方式 2：已有工作流调用本地接收器

在另一个终端启动（示例命令适用于 macOS/Linux；Windows PowerShell 使用 `$env:INGEST_TOKEN="..."`）：

```bash
export INGEST_TOKEN='YOUR_LONG_RANDOM_SECRET'
python ingest_news.py
```

在 n8n 的 HTTP Request 节点中 POST 至 `http://127.0.0.1:8765/ingest/news`，设置 `Authorization: Bearer YOUR_LONG_RANDOM_SECRET` 和 `Content-Type: application/json`，body 为上方数组或 `{"items":[...]}`。

**注意**：这个 localhost 地址仅对同一台电脑上的 n8n 有效。若 n8n 在 Docker、云服务器或其他设备，需要配置可访问的安全网络地址、鉴权与 HTTPS；不要直接将此简易接收器公开到互联网。

## 数据与安全

SQLite 文件自动创建在 `data/vc_intelligence.sqlite3`，属于本地文件；不会默认上传云端。若之前的报告需要迁移，可先以 Markdown 手动保留；V1 不带数据库，因此没有自动迁移的旧记录。模型调用可能收费或触发额度限制，所选模型需支持当前检索配置。新闻和 AI 输出应核实，避免上传未获授权的保密数据。

## 后续真正要开发的部分

1. n8n 采集源去重、时间标注、来源质量、人工审核
2. 公司/赛道知识实体归一及关联图谱（当前只有展示框架）
3. 可比数据结构化、真实来源链和多时点快照
4. 持续研究记忆：投资假设、证据、反证、变更追踪（当前是报告历史 + 笔记）
5. 跨设备访问时从 SQLite 迁移 Supabase/PostgreSQL + 用户鉴权

这是一版可以运行、能保存研究和接收新闻的 **V2 基础骨架**，不是宣称已完全实现上述后续功能。
