# email_assistant

一个面向学生邮箱的自动日报助手。它会每天读取指定 Gmail 收件箱中的学校邮件，解析正文和图片内容，用 LLM 判断邮件是否需要处理、是否是活动通知或学术 notice，然后自动整理成一封中文 digest 发到你的邮箱。

这个项目最初用于 PolyU 邮件场景，但整体结构可以复用到其他学校或组织邮箱：只需要替换发件人域名、目标邮箱和提示词规则。

## Pipeline

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

## 为什么不用 GitHub Actions schedule

GitHub Actions 自带的 `schedule` 是 best-effort cron。实际测试中，这个仓库出现过 workflow 处于 active、YAML 在默认分支、cron 表达式正确，但 scheduled event 没有被创建的情况。对于“每天必须稳定发日报”的任务，这种不确定性不可接受。

因此当前方案是：

- GitHub Actions 只保留 `workflow_dispatch`
- 使用外部 cron 服务定时调用 GitHub REST API
- 推荐使用 [cron-job.org](https://console.cron-job.org/dashboard)

这样 GitHub 只负责执行任务，定时触发交给专门的 cron 服务。

## 功能

- 自动读取最近一天的 Gmail 邮件
- 只处理指定发件人域名，例如 `polyu.edu.hk`
- 支持 HTML 邮件、纯文本邮件和图片附件
- 使用 LLM 输出分类、摘要、deadline、活动时间和地点
- 生成中文每日 digest
- 自动通过 Gmail API 发出日报
- 发送前检查 Gmail Sent，避免同一天重复发送同标题 digest
- workflow 日志只记录处理数量和发送状态，不打印邮件正文、判断依据或 digest 内容

## 邮件分类

项目会把邮件分成几类：

```text
MUST_ACTION      需要你完成明确动作，例如提交、注册、确认、付款、上传
MUST_ATTEND      明确要求必须参加
ACADEMIC_NOTICE  重要学术通知，但没有立即要做的个人任务
OPTIONAL_EVENT   可选活动、讲座、seminar、workshop
GENERAL          普通通知
```

一个重要规则是：`You are invited to attend` 默认只是可选活动。只有邮件明确写出 compulsory、required、mandatory 等强制措辞，才会被判为必须参加。

长期学术要求，例如 “RPg students must earn departmental seminar credits”，不会进入“必须关注”，也不会把判断依据打印到 workflow 日志里。

## 本地准备

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

然后填写 `.env`：

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

## Gmail OAuth

需要在 Google Cloud Console 中创建 Gmail OAuth 凭据：

1. 创建或选择一个 Google Cloud project
2. Enable Gmail API
3. 配置 OAuth consent screen
4. 创建 OAuth Client ID，类型选择 `Desktop app`
5. 下载 JSON，保存到：

```text
credentials/google_oauth_client.json
```

首次本地运行 Gmail 相关命令时会打开浏览器授权。授权成功后，refresh token 会保存到：

```text
data/google_token.json
```

这两个文件都不应该提交到 Git。

项目需要的 Gmail scope：

```text
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/gmail.send
```

## 手动发送

如果你想手动跑一次完整日报流程，只保留这一条命令即可：

```bash
python -m email_assistant.main daily --yesterday
```

它会处理昨天 00:00 到 24:00 的邮件，并发送当天日期的 digest。

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

workflow 每次运行时会在临时 runner 中还原：

```text
credentials/google_oauth_client.json
data/google_token.json
data/emails.db
```

这些运行时文件不会提交到仓库。

## 外部 Cron 配置

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

创建 GitHub fine-grained personal access token，只给当前仓库：

```text
Actions: Read and write
```

HTTP 请求：

```bash
curl -L \
  -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/ZionPeng112/email_assist/actions/workflows/daily-digest.yml/dispatches \
  -d '{"ref":"main"}'
```

不要把 token 写进仓库。

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
```

## 测试

```bash
python -m pytest
```

当前测试覆盖 Gmail 解析、发送 provider、图片处理、发件人过滤、LLM 分类兜底和 digest 输出规则。
