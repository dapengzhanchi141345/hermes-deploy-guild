# 02 · Hermes 配置指南（模型 / 端点 / 密钥）（v2 · 2026-10-01 全网修订）

> 结论先行：
> **配置 provider 必须用 `hermes model` 向导**（它一次写对 `config.yaml`+`.env`）。
> **Custom endpoint（OpenAI 兼容端点）的端点 `base_url` 必须写进 `~/.hermes/config.yaml` 的 `model` 块。**
> **`OPENAI_BASE_URL` 只对 `provider: openai-api`（官方 OpenAI 直连）生效，对 custom 端点无效** —— 这是昨日"key 在、连不上模型 / no API key"的根本原因。
> key 放 `~/.hermes/.env` 没问题，**但端点不能只塞 `.env` 的 `OPENAI_BASE_URL`**。

## ⚠️ 根因修订（v2 重点）

| 旧认知（v1，已证伪） | 新认知（v2，依官方文档） |
|:----|:----|
| `OPENAI_BASE_URL` 写进 `.env` 即可让 Hermes 用自定义端点 | `OPENAI_BASE_URL` **仅** override `openai-api` provider 的端点；custom 端点必须走 `config.yaml` 的 `model.base_url` |
| 端点+key 都放 `.env` | key 可在 `.env`，**端点 `base_url` 一定在 `config.yaml`** |
| 旧 `LLM_MODEL`/`OPENAI_BASE_URL` 通用 | 旧变量对 custom 已失效，下次 `hermes setup`/迁移会自动清理 |

`config.yaml` 的 custom 端点正确写法：
```yaml
model:
  provider: custom
  default: <模型名>
  base_url: https://api.agnes-ai.cn/v1     # ← 端点在这里，不是 .env
  api_mode: chat_completions               # 标准 OpenAI 兼容
  # api_key 可留空，key 放 .env
```

## 为什么优先用 `hermes model` 向导（而非纯手写）

- 官网文档的 schema **常常比实际安装的版本新**（例如 0.19.0 与最新文档不一致）
- 手写 `config.yaml`（如 `model.provider: custom` + `base_url` + `api_key`）会导致 Hermes **不认配置**，回退到内置默认（openrouter / z-ai / glm 之类）并报 **401**
- `hermes model` 向导写出的配置才是**与当前版本匹配**的正确格式
- 且仅把 key 写进 `config.yaml` 的 `model.api_key` 会被判 **"no API key"** —— key 属于机密，必须进 `.env`

## 关键文件

| 文件 | 位置 | 内容 |
|------|------|------|
| `.env` | `~/.hermes/.env`（Windows：`C:\Users\<用户名>\.hermes\.env`） | **API Key 与 Base URL（机密）** |
| `config.yaml` | `~/.hermes/config.yaml` | 模型、provider 等非机密设置（由向导写入） |

`.env` 内容示例：
```
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
OPENAI_BASE_URL=https://api.example.com/v1
```

## 配置前：先验端点（强烈建议）

用 `/v1/models` 确认 Key 有效并拿到可用模型清单：
```bash
curl -s https://<端点>/v1/models -H "Authorization: Bearer <KEY>" | head -c 3000
```
再验一条对话：
```bash
curl -s https://<端点>/v1/chat/completions \
 -H "Authorization: Bearer <KEY>" -H "Content-Type: application/json" \
 -d '{"model":"<模型>","messages":[{"role":"user","content":"回复两个字：正常"}],"max_tokens":20}'
```

## 向导配置全流程（`hermes model`）

1. 远程终端运行 `hermes model` → 打开 provider 列表
2. 选 **`Custom endpoint (enter URL manually)`**（编号随版本变化，按文字找）
3. **API base URL**：输入或直接回车沿用（如 `https://api.agnes-ai.cn/v1`）
4. **API key**：输入或直接回车沿用
5. 向导请求 `/v1/models` 验证 → 出现 `Verified endpoint via /v1/models` 即通过
6. **兼容模式**：选 **`Chat Completions`**（标准 OpenAI 兼容端点都选这个）
7. **模型**：向导列出该端点返回的全部模型，按序号选（如 `6. agnes-3.0-flash`）
8. **上下文长度**：**留空回车**（自动检测，如 256K）
9. **显示名**：回车接受默认
10. 成功标志：
    ```
    Default model set to: <模型名>
    Saved to custom providers as "<端点host>"
    ```

## 若报 "It looks like Hermes isn't configured yet -- no API key"

多因端点没进 `config.yaml` 或 key 没进 `.env`。处理：
1. 先重跑 `hermes model` 向导（会自动写对两处）；
2. 或手动分文件写：
   - `~/.hermes/config.yaml`：`model.base_url = <端点>/v1`、`model.provider = custom`、`model.default = <模型>`（端点在这里）
   - `~/.hermes/.env`：`OPENAI_API_KEY=<KEY>`（key 在这里）
3. 重新 `hermes` 发 `hi` 验证。
> 不要只把端点写进 `.env` 的 `OPENAI_BASE_URL`——对 custom 无效。

## 写入 `.env`（key）的可靠方式（远控场景）

远控下粘贴/键入长内容易被 IME 破坏 → 用 **ntfy base64 中继**：
```bash
# 本机：base64 上传到新 topic
python -c "import base64;open('env.b64','wb').write(base64.b64encode(open('remote_env.txt','rb').read()))"
curl -s -d @env.b64 "https://ntfy.sh/hermesenv<随机后缀>"
curl -s "https://ntfy.sh/hermesenv<随机后缀>/raw?poll=1"   # 本机先验证能读回
```
```powershell
# 远程：拉取 → 解码 → 写文件 → 回报字节数
$d="$env:USERPROFILE\.hermes"
curl.exe -s "https://ntfy.sh/hermesenv<随机后缀>/raw?poll=1" -o "$d\env.b64"
[IO.File]::WriteAllText("$d\.env", [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String((gc "$d\env.b64" -Raw).Trim())))
"ENVW "+((gc "$d\.env" -Raw).Length)
```
> 本地文件的字节数与远程回报的字节数一致，即可确认写入无损。

## 使用方法

```
hermes                    # 启动，直接对话
hermes --resume <会话ID>   # 恢复上次会话
hermes model              # 换模型 / 换端点
hermes config             # 查看当前配置
```

启动后留意：
- 底部状态栏显示的模型名应与配置一致（如 `agnes-3.0-flash`）
- **不应**再出现 `isn't configured yet -- no API key`
- 发一条 `hi`，能收到回复即配置成功

## 安全

- API Key 明文存在远程 `~/.hermes/.env` 与配置中，只有能登上该机的人可见
- 交付报告与回传消息中 **Key 一律用掩码**（`sk-5Wq4****`）
- 不要把 Key 写进任何代码、日志或截图
