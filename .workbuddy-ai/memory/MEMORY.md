# CSP_AUTO-TRAINING 项目长期记忆

## 项目定位

每天自动出 3 道 CSP 风格 C++ 训练题 → 生成中文 PDF → SMTP 邮件推送。
GitHub 仓库：`git@github.com:1811255323swf-source/CSP_AUTO-TRAINING.git`（HTTPS 同址）。
每日定时任务：`.github/workflows/daily-csp-email.yml`，UTC 06:05（北京 14:05）。

## 呆呆的约定（必须遵守）

- **不要动 README.md**。改代码时不要附带更新文档，除非呆呆明确要求。

## 架构要点

- 出题来源由 `config.ini` 的 `app.provider` 决定：`static`（本地题库）或 `ai`（DeepSeek）。
- `config.py` 的 `project_root` = 配置文件所在目录。**config.ini 必须放项目根**，
  否则 `data/`、`output/` 等相对路径会解析错。
- API Key 只从环境变量读（默认 `DEEPSEEK_API_KEY`），不写入任何文件。
- **DeepSeek 模型名：`deepseek-chat` / `deepseek-reasoner` 已于 2026-07-24 退役**，
  现用 `deepseek-flash`（默认）或 `deepseek-v4-pro`。改配置时别再写旧名。
- thinking 模式服务端**默认开启**且会忽略 `temperature`；本项目默认
  `thinking = false`（见 `[ai]` 段）。`max_tokens` 必须设置，否则 3 道题的 JSON
  可能被截断导致解析失败。
- AI 出题失败可回退本地题库：需同时满足 `ai.fallback_to_static = true`
  与命令行 `--allow-static-fallback`。daily 任务必须带这个 flag。
- 来源标识（AI / 题库）会出现在：邮件主题后缀、邮件正文、PDF 副标题、附件文件名
  （AI 模式带 `_AI` 后缀）。
- PDF 用自研的 `SimpleChinesePdf`（`pdf_generator.py`），内置 STSong-Light，
  文本以 UTF-16BE hex 写入内容流，不需要外部字体文件。

## 本机执行

- 依赖装在隔离 venv：`C:/Users/18112/.workbuddy-ai/binaries/python/envs/default`
  （openai + pyyaml）。
- `git push` 会被 WorkBuddy 自带代理掐断 TLS，必须走 Clash 7897：
  `env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY git -c http.proxy=http://127.0.0.1:7897 -c https.proxy=http://127.0.0.1:7897 push origin main`
- 未安装 `gh` CLI，无法远程触发 workflow。
