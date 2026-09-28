# CSP 云端自动训练 PDF 邮件系统


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

