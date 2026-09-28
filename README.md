# CSP 云端自动训练 PDF 邮件系统


## 功能

- 每天自动出 3 道 CSP 风格 C++ 训练题，来源二选一：
  - `provider = ai`：调用 DeepSeek 当天生成（默认）
  - `provider = static`：从 `data/questions.json` 按日期轮换
- 生成中文 PDF（内置 STSong 字体，无需额外字体文件）
- 通过 SMTP 发送 PDF 附件
- 邮箱授权码与 API Key 只放在 GitHub Secrets，不写入代码
- 支持手动触发一次发送测试
- AI 出题失败可自动回退到本地题库，保证每日任务不中断

## 快速开始

```bash
pip install -r requirements.txt
cp config.example.ini config.ini   # Windows: copy config.example.ini config.ini
```

**静态题库模式**（离线可用，无需 Key）：

```bash
python main.py --config config.ini --dry-run
```

**AI 出题模式**（需要 Key）：

```bash
export DEEPSEEK_API_KEY=sk-xxxxxx        # PowerShell: $env:DEEPSEEK_API_KEY="sk-xxxxxx"
python main.py --config config.ini --dry-run
```

`config.ini` 中 `app.provider` 决定出题来源。AI 模式建议加
`--allow-static-fallback`，这样 Key 失效或模型返回异常时会退回本地题库，
不至于当天开天窗。

## 配置项

| 段 | 键 | 说明 |
| --- | --- | --- |
| `app` | `provider` | `static` 或 `ai` |
| `ai` | `api_key_env` | 读取 API Key 的环境变量名，默认 `DEEPSEEK_API_KEY` |
| `ai` | `base_url` / `model` | 兼容 OpenAI 接口，默认 DeepSeek |
| `ai` | `timeout` / `max_retries` / `temperature` | 超时秒数、重试次数、采样温度 |
| `ai` | `fallback_to_static` | 失败时是否允许回退（需配合 `--allow-static-fallback`） |
| `email` | `enabled` 等 | 邮件开关与 SMTP 参数 |

`ai.*` 与 `email.subject_prefix` 均可用环境变量覆盖：
`CSP_AI_BASE_URL`、`CSP_AI_MODEL`、`CSP_AI_TIMEOUT`、`CSP_AI_MAX_RETRIES`、
`CSP_AI_TEMPERATURE`、`CSP_SUBJECT_PREFIX`。

## GitHub Actions 配置

在仓库 **Settings → Secrets and variables → Actions** 中配置：

- Secrets：`CSP_SMTP_PASSWORD`、`CSP_SMTP_USER`、`CSP_MAIL_FROM`、`CSP_MAIL_TO`、`DEEPSEEK_API_KEY`
- Variables（可选）：`CSP_QUESTION_PROVIDER`（`ai` 或 `static`，默认 `ai`）

工作流每天 UTC 06:05（北京时间 14:05）运行，也支持
**Actions → Daily CSP PDF Email → Run workflow** 手动触发。
运行时会生成 `config.cloud.ini`（已被 git 忽略）并带
`--require-email --allow-static-fallback`。

## 测试

```bash
python tests/test_ai_provider.py
```

覆盖 AI 返回值的解析（纯 JSON / ```json 代码块 / 夹带闲聊 / markdown
【】结构）、异常处理，以及重试与回退逻辑，不需要 API Key。

## 目录结构

```text
CSP_AUTO-TRAINING/
├── .github/
│   └── workflows/
│       └── daily-csp-email.yml
├── csp_trainer/
│   ├── __init__.py
│   ├── ai_question_provider.py   # AI 出题
│   ├── config.py
│   ├── mailer.py
│   ├── models.py
│   ├── pdf_generator.py
│   └── question_provider.py      # 本地题库
├── data/
│   └── questions.json
├── tests/
│   └── test_ai_provider.py
├── output/
│   └── .gitkeep
├── config.example.ini
├── main.py
├── requirements.txt
└── README.md
```

