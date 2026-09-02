# email_assistant

`email_assistant` 是一个自动邮件日报助手：每天读取 Gmail 中的学校邮件，用 LLM 判断哪些邮件需要处理、哪些只是活动或学术通知，然后生成一封简体中文 digest 自动发到指定邮箱。

项目最初用于 PolyU 学生邮箱场景，但核心流程不依赖 PolyU。你可以替换发件人域名、目标邮箱、提示词规则和日报文案，把它改成适合其他学校、实验室、社团或组织邮箱的自动日报系统。

## 适合什么场景

- 学校邮箱通知太多，希望每天只看一封摘要
- 邮件经常包含活动海报、HTML 图片或长通知，需要自动提取时间、地点、deadline
- 想区分“必须处理”和“可选关注”，减少漏看重要事项
- 希望用 GitHub Actions 执行任务，但不依赖 GitHub 内置 cron 的准时性

## Pipeline

邮件处理链路：

```text
学校邮件 / 转发邮件
        ↓
Gmail 收件箱
        ↓
Gmail API 读取邮件
        ↓
Parser 清理正文、提取附件和 HTML 图片
        ↓
n1n / OpenAI-compatible LLM 分类与总结
        ↓
SQLite 保存分析结果
        ↓
Daily Digest 生成中文日报
        ↓
Gmail API 自动发送
        ↓
你的日报收件箱
```

自动触发链路：

```text
cron-job.org
        ↓  每天 11:40 Asia/Hong_Kong
GitHub REST API workflow_dispatch
        ↓
GitHub Actions
        ↓
python -m email_assistant.main daily --yesterday
        ↓
发送每日 Email Digest
```

## 为什么用外部 Cron

GitHub Actions 自带的 `schedule` 是 best-effort cron。实际测试中，这个仓库出现过 workflow 处于 active、YAML 已在默认分支、cron 表达式正确，但 scheduled event 没有被创建的情况。

日报属于“每天必须稳定发送”的任务，因此当前设计是：

- GitHub Actions 只保留 `workflow_dispatch`
- 定时触发交给外部 cron 服务
- 推荐使用 [cron-job.org](https://console.cron-job.org/dashboard)
- GitHub 只负责执行 workflow 和发送邮件

这种方案更容易观测：如果没有邮件，可以分别检查 cron-job.org 请求记录、GitHub Actions run、以及 Gmail Sent。

## 功能

- 自动读取 Gmail 中最近一天的邮件
- 按发件人域名过滤，例如只处理 `polyu.edu.hk`
- 支持纯文本、HTML 邮件、图片附件和远程 HTML 图片
- 使用 LLM 提取摘要、分类、deadline、活动时间和地点
- 生成简体中文每日 digest
- 通过 Gmail API 自动发送 digest
- 发送前检查 Gmail Sent，避免同一天重复发送同标题日报
- workflow 日志只记录处理数量和发送状态，不打印邮件正文、判断依据或 digest 内容
- 图片只在运行时下载到内存，不持久化保存

## 邮件分类规则

```text
MUST_ACTION      需要完成明确动作，例如提交、注册、确认、付款、上传
MUST_ATTEND      明确要求必须参加
ACADEMIC_NOTICE  重要学术通知，但没有立即要做的个人任务
OPTIONAL_EVENT   可选活动、讲座、seminar、workshop
GENERAL          普通通知
```

关键规则：

- `You are invited to attend` 默认是可选活动
- 只有出现 compulsory、required、mandatory 等明确强制措辞，才会判为必须参加
- 长期学术要求，例如 RPg departmental seminar credit requirement，不进入“必须关注”
- 判断依据不会写入 GitHub Actions 日志

## 快速开始

准备 Python 环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

填写 `.env`，最小配置如下：

```env
MAIL_PROVIDER=gmail
GMAIL_USER=me
GMAIL_ACCOUNT_EMAIL=your-gmail@example.com
GOOGLE_OAUTH_CLIENT_SECRETS=credentials/google_oauth_client.json
GOOGLE_OAUTH_TOKEN_FILE=data/google_token.json

TARGET_EMAIL=your-gmail@example.com
ALLOWED_SENDER_DOMAINS=polyu.edu.hk
LOCAL_TIMEZONE=Asia/Hong_Kong

N1N_API_KEY=xxxxx
N1N_BASE_URL=https://api.n1n.ai/v1
LLM_MODEL=YOUR_MODEL

DATABASE_URL=sqlite:///data/emails.db

DIGEST_RECIPIENT_EMAIL=your-digest-recipient@example.com
DIGEST_FROM_EMAIL=your-gmail@example.com
DIGEST_SUBJECT_PREFIX=PolyU 每日 Email Digest
```

## 手动发送

本地手动跑一次完整日报流程：

```bash
python -m email_assistant.main daily --yesterday
```

这条命令会处理本地时区中“昨天 00:00 到 24:00”的邮件，并发送一封以今天日期命名的 digest。

## 配置说明

| 变量 | 作用 |
| --- | --- |
| `MAIL_PROVIDER` | 邮件 provider，目前默认使用 `gmail` |
| `GMAIL_USER` | Gmail API user，一般使用 `me` |
| `GMAIL_ACCOUNT_EMAIL` | 用于校验当前 OAuth token 属于哪个 Gmail 账号 |
| `GOOGLE_OAUTH_CLIENT_SECRETS` | Google OAuth client JSON 路径 |
| `GOOGLE_OAUTH_TOKEN_FILE` | Google OAuth token JSON 路径 |
| `TARGET_EMAIL` | 要读取和过滤的目标收件邮箱 |
| `ALLOWED_SENDER_DOMAINS` | 允许处理的发件人域名，逗号分隔 |
| `LOCAL_TIMEZONE` | 本地日期窗口时区，例如 `Asia/Hong_Kong` |
| `N1N_API_KEY` | n1n API key |
| `N1N_BASE_URL` | OpenAI-compatible API base URL |
| `LLM_MODEL` | 用于分析邮件的模型名 |
| `N1N_TIMEOUT_SECONDS` | LLM 请求超时时间 |
| `DATABASE_URL` | SQLite 数据库地址 |
| `DIGEST_RECIPIENT_EMAIL` | digest 收件人 |
| `DIGEST_FROM_EMAIL` | digest 发件人 |
| `DIGEST_SUBJECT_PREFIX` | digest 邮件标题前缀 |
| `ENABLE_IMAGE_ANALYSIS` | 是否分析图片附件和 HTML 图片 |
| `ENABLE_REMOTE_IMAGE_URLS` | 是否下载并分析远程 HTML 图片 |
| `MAX_IMAGE_ATTACHMENTS` | 单封邮件最多分析多少张图片 |
| `MAX_IMAGE_BYTES` | 单张图片最大字节数 |

## Gmail OAuth

Gmail 读信和发信都通过 OAuth 完成。需要在 Google Cloud Console 中准备凭据：

1. 创建或选择一个 Google Cloud project
2. Enable Gmail API
3. 配置 OAuth consent screen
4. 创建 OAuth Client ID，类型选择 `Desktop app`
5. 下载 JSON，保存到 `credentials/google_oauth_client.json`

首次运行 Gmail 相关命令时会打开浏览器授权。授权成功后，refresh token 会保存到 `data/google_token.json`。

不要提交以下文件：

```text
credentials/google_oauth_client.json
data/google_token.json
data/emails.db
```

项目需要的 Gmail scope：

```text
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/gmail.send
```

## 数据与图片存储

图片处理是运行时完成的，不会长期保存图片文件：

```text
Gmail attachment / HTML image URL
        ↓
下载为内存中的 bytes
        ↓
检查 content-type 和大小限制
        ↓
转换成 data:image/...;base64
        ↓
随 LLM 请求发送
        ↓
进程结束后释放
```

默认限制：

```env
MAX_IMAGE_ATTACHMENTS=4
MAX_IMAGE_BYTES=2000000
```

也就是说，单封邮件最多取 4 张图片，单张图片默认最大 2 MB。base64 编码会比原始图片大约多三分之一，所以一次运行的图片内存占用是有上限的。

SQLite 中会保存：

- 邮件 ID、标题、发件人、收件人和时间
- 邮件正文的 SHA-256 hash
- 附件 metadata
- HTML 图片 metadata
- LLM 分析结果

SQLite 不保存原始邮件正文，也不保存图片 bytes。当前没有定期清理数据库的机制；本地长期运行时，`data/emails.db` 会随已分析邮件数量增长。GitHub Actions runner 是临时环境，每次 workflow 运行后本地数据库文件都会随 runner 销毁。

## GitHub Actions 部署

仓库中保留一个 dispatch-only workflow：

```text
.github/workflows/daily-digest.yml
```

GitHub Actions 需要以下 repository secrets：

```text
GOOGLE_OAUTH_CLIENT_JSON_B64
GOOGLE_OAUTH_TOKEN_JSON_B64
N1N_API_KEY
```

本地生成 base64 后填入 GitHub Secrets：

```bash
base64 -i credentials/google_oauth_client.json | pbcopy
base64 -i data/google_token.json | pbcopy
```

workflow 每次运行时会在临时 runner 中还原 OAuth 文件和 SQLite 数据库。运行时文件不会提交到仓库。

## cron-job.org 配置

在 [cron-job.org](https://console.cron-job.org/dashboard) 新建一个 cron job，每天 11:40 Asia/Hong_Kong 调用 GitHub workflow dispatch API。

如果 cron 服务支持时区：

```text
40 11 * * *
```

时区选择：

```text
Asia/Hong_Kong
```

如果只能使用 UTC：

```text
40 3 * * *
```

创建 GitHub fine-grained personal access token，只给目标仓库：

```text
Actions: Read and write
```

HTTP 请求：

```bash
curl -L \
  -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/OWNER/REPO/actions/workflows/daily-digest.yml/dispatches \
  -d '{"ref":"main"}'
```

把 `OWNER/REPO` 替换成你的仓库，例如 `ZionPeng112/email_assist`。不要把 token 写进仓库。

## 项目结构

```text
email_assistant/
  main.py              CLI 入口和 daily 流程
  config.py            环境变量配置
  parser.py            邮件正文清理和 HTML 图片提取
  analyzer.py          LLM 提示词、分类和规则兜底
  digest.py            中文日报格式化
  database.py          SQLite 存储
  providers/gmail.py   Gmail 读取和发送
  providers/n1n.py     OpenAI-compatible LLM provider
  providers/resend.py  Resend inbound fallback provider
```

## 开发

运行测试：

```bash
python -m pytest
```

当前测试覆盖 Gmail 解析、发送 provider、图片处理、发件人过滤、LLM 分类兜底、SQLite 存储和 digest 输出规则。

## 许可证

本项目使用 MIT License。完整文本见 [LICENSE](LICENSE)。
