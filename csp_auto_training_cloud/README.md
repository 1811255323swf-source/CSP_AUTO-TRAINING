# CSP 云端自动训练 PDF 邮件系统

这个项目只走云端方案：GitHub Actions 每天自动运行，生成一份 CSP 风格 C++ 三题训练 PDF，然后通过 SMTP 发送到邮箱。

本地电脑不需要每天开机，也不需要 Windows 任务计划程序。

## 功能

- 每天自动选择 3 道 CSP 风格 C++ 训练题
- 生成中文 PDF
- 通过 SMTP 发送 PDF 附件
- 邮箱授权码只放在 GitHub Secrets，不写入代码
- 支持手动触发一次发送测试
- 预留后续接入 ChatGPT / OpenAI API 自动生成题目的接口

## 目录结构

```text
csp_auto_training/
├── .github/
│   └── workflows/
│       └── daily-csp-email.yml
├── csp_trainer/
│   ├── __init__.py
│   ├── config.py
│   ├── mailer.py
│   ├── models.py
│   ├── pdf_generator.py
│   └── question_provider.py
├── data/
│   └── questions.json
├── output/
│   └── .gitkeep
├── main.py
├── requirements.txt
└── README.md
```

## 1. 上传到 GitHub

新建一个 GitHub 仓库，把本项目所有文件上传进去。

建议用私有仓库。代码里没有邮箱授权码，但训练项目放私有仓库更清爽。

## 2. 配置 GitHub Secrets

进入你的 GitHub 仓库：

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

添加必填 Secrets：

```text
CSP_SMTP_PASSWORD = 你的邮箱 SMTP 授权码
CSP_SMTP_USER = 发件邮箱，例如 your_email@qq.com
CSP_MAIL_FROM = 发件邮箱，例如 your_email@qq.com
CSP_MAIL_TO = 收件邮箱，例如 your_email@qq.com
```

可选 Secrets：

```text
CSP_SMTP_HOST = smtp.qq.com
CSP_SMTP_PORT = 465
CSP_SUBJECT_PREFIX = CSP 每日训练
```

如果不填可选项，默认使用：

```text
smtp_host = smtp.qq.com
smtp_port = 465
subject_prefix = CSP 每日训练
```

常见邮箱配置：

```text
QQ 邮箱：smtp.qq.com，端口 465
163 邮箱：smtp.163.com，端口 465
Gmail：smtp.gmail.com，端口 465
```

注意：`CSP_SMTP_PASSWORD` 填的是邮箱 SMTP 授权码，不是邮箱登录密码。

## 3. 手动测试一次

进入仓库：

```text
Actions -> Daily CSP PDF Email -> Run workflow
```

点 `Run workflow` 后，GitHub 会立刻生成 PDF 并发送邮件。

如果发送成功，日志里会看到：

```text
[email] Sent successfully.
```

生成的 PDF 也会作为 GitHub Actions artifact 保存一份，方便排查。

## 4. 每天自动发送

项目已经配置好定时任务：

```yaml
cron: "5 6 * * *"
```

GitHub Actions 的 cron 使用 UTC 时间。`06:05 UTC` 等于北京时间 `14:05`，所以默认每天北京时间 14:05 发送。

选 14:05 是为了避开整点高峰。GitHub 官方说明里提到，定时 workflow 在高负载时可能延迟，整点附近更容易拥挤。

如果想改时间，编辑：

```text
.github/workflows/daily-csp-email.yml
```

例如每天北京时间 08:05 发送，要写成 UTC 00:05：

```yaml
cron: "5 0 * * *"
```

如果使用公开仓库，还要注意：GitHub 公开仓库在长时间无活动后，定时 workflow 可能会被自动停用。建议用私有仓库，或者偶尔更新题库/代码。

## 5. 修改题目

当前题目来自：

```text
data/questions.json
```

每天会按日期从本地题库轮换三道题：

- 第 1 题：CSP 第一题难度
- 第 2 题：CSP 第二题入门到中等
- 第 3 题：CSP 第二题后半或第三题入门

后续接入 ChatGPT / OpenAI API 时，主要扩展：

```text
csp_trainer/question_provider.py
```

新增一个 `ApiQuestionProvider`，让它返回 `list[Question]`，PDF 和邮件发送模块都不用改。

## 6. 常见问题

### 为什么不用本地定时任务？

已经放弃本地方案。现在每天发送完全由 GitHub Actions 执行，本地电脑不用开机。

### QQ 邮箱怎么拿授权码？

进入 QQ 邮箱设置，开启 SMTP 服务，然后生成授权码。发送邮件时使用授权码，不使用 QQ 登录密码。

### Gmail 怎么配置？

Gmail 通常需要开启两步验证后创建 App Password，然后把 App Password 填到 `CSP_SMTP_PASSWORD`。

### PDF 中文显示异常怎么办？

项目生成的是文本 PDF，使用 `STSong-Light` CJK 字体描述。常见 PDF 阅读器可以正常显示。邮件附件打开异常时，建议用 Microsoft Edge、Adobe Acrobat 或 WPS PDF 查看。
