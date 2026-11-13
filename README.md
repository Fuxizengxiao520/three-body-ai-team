# 三体 AI 团队，本地最小闭环

一个用《三体》角色命名、能派单交接、能临时开会、能独立验收、能记账的本地多智能体项目。零第三方依赖，Python 3.10 以上直接跑。

## 定位与边界

Grok Bot 属于 xAI 的闭源商业服务，本项目为独立开源实现，与 xAI 无官方关联。功能形态参考 xAI 公开描述的多 Bot 并行、群聊互派活、共享上下文（来源 x.ai/news/introducing-grok-bot）。原版附带的云端电脑、跨应用登录与 24/7 常驻不在本项目内，本项目用本地状态文件承载共享上下文，用结构化消息承载内部沟通。

模型默认走 DeepSeek 的 OpenAI 兼容接口（来源 api-docs.deepseek.com），也可以指向任意兼容端点。账号与网络可达性请自行评估，本项目不提供任何绕过做法。

## 角色

| 角色 | 岗位 | 状态 |
|---|---|---|
| 维德 | 统筹商务合作，拆单、主持会议、独立验收 | 启用 |
| 罗辑 | 抓前沿资讯，交简报 | 启用 |
| 云天明 | 写文案，基于上游简报成稿 | 启用 |
| 智子 | 筛选题 | 待命 |
| 章北海 | 管剪辑 | 待命 |
| 程心 | 管剪辑，复核 | 待命 |
| 庄颜 | 盯账单行程 | 账务模块常驻，不占对话角色 |

默认只跑 3 个角色。理由在文末的设计取舍里。

## 快速开始

```bash
cd three-body-ai-team
python3 run.py demo
python3 -m unittest discover -s tests -v
```

`demo` 走离线 mock，不需要 API key，不联网，不花钱，会把完整链路跑一遍。

接真实模型时：

```bash
export DEEPSEEK_API_KEY="你的密钥"
python3 run.py run "多智能体协作的成本"
python3 run.py meeting "下周选题方向"
python3 run.py ledger
python3 run.py status
python3 run.py roster
```

`run` 默认停在人工放行门，看完验收项再输入 `y`。加 `--auto-approve` 跳过，加 `--model deepseek-v4-pro` 换模型，加 `--peak` 按峰时价格记账。

自定义端点时，把 `config/settings.example.json` 复制为 `config/settings.json` 再改。密钥始终从环境变量读取，不写入配置文件。

## 运行链路

```
任务卡，写清验收标准
  -> 维德发起临时启动会，三人依次发言
  -> 罗辑产出资讯简报，写入 handoff 消息
  -> 云天明读取上游简报，产出文案，写入 handoff 消息
  -> 维德逐条验收，执行者不自评
  -> 人工放行，决策留痕
```

所有中间产物落在 `state/`，可审计，可回放。

| 文件 | 内容 |
|---|---|
| `state/task_cards.json` | 任务卡与验收标准 |
| `state/mailbox.jsonl` | 内部沟通与交接消息 |
| `state/meetings.jsonl` | 临时会议纪要与决议 |
| `state/artifacts/` | 每个角色的产出物 |
| `state/verdict.json` | 独立验收逐项结果 |
| `state/decisions.jsonl` | 人工放行记录 |
| `state/ledger.jsonl` | 庄颜账本，token 与估算成本 |
| `state/last_report.json` | 本次运行摘要 |

`state/` 已加入 `.gitignore`，不会进仓库。

## 成本

账本按官方定价页的谷时基准价估算，峰时按两倍计，单位美元每 1M tokens。快照日期 2026-11-13，来源 api-docs.deepseek.com/quick_start/pricing。价格会调整，运行前请核对当前页面。mock 模式成本为零，账本会标记 `simulated`。

按 3 个角色、每角色 1 到 2 次调用估算，单个任务大致落在 0.01 到 0.10 美元区间。真实账单取决于上游简报长度、重试次数与模型选择。

## 设计取舍

* **只跑 3 个角色。** 并行 agent 的 token 消耗约为普通对话的 15 倍（来源 github.com/ashishpatel26/engineering-handbook 的 multi-agent-orchestration 章节）。16 个并行 agent 完成编译器用了约 2000 次会话与约 20000 美元（来源 anthropic.com/engineering/building-c-compiler）。角色数增加带来的协调开销增长快于质量增益，先跑通闭环再扩编更划算。
* **确定性拆单。** 维德的拆解用模板生成，省掉一次模型调用，同时让验收标准能被机器检查。
* **验收与执行分离。** 维德只核对任务卡，不产出业务内容。让执行者评价自己的产出会系统性偏宽松（来源 anthropic.com/engineering/harness-design-long-running-apps）。
* **已知局限。** 当前验收检查的是格式与可数项，语义质量、事实准确性、来源真实性仍需要人工判断，或后续接入独立评审模型。真实模型输出未必满足格式要求，验收失败属于预期行为，会拦在人工门前。
* **庄颜常驻。** 账本做成模块，随每次调用自动记录，比多开一个对话角色更省额度。

## 扩编到 7 个角色

改 `config/roster.json` 的 `active` 列表并打开对应 `enabled`，可以扩大会议参与人。执行环节的新增需要在 `src/team.py` 的 `run` 里加对应步骤，仅改 JSON 不会自动生成新岗位的工作流。

## 推送到 GitHub

本机缺 gh CLI，github.com 网页直连超时，api.github.com 可达。仓库已在本地完成初始化与提交，配好 Personal Access Token 后可直接用方式三发布。推送任选一种。

**方式一，网页端建空仓库后推**

```bash
git remote add origin https://github.com/<你的用户名>/three-body-ai-team.git
git push -u origin main
```

**方式二，安装 gh 后一条命令**

```bash
brew install gh
gh auth login
gh repo create three-body-ai-team --public --source=. --push
```

**方式三，API 一键发布，网页域名不可达时适用**

先在 GitHub 账户设置里生成一个具备仓库创建与内容写入权限的 Personal Access Token，存到本机文件，不要贴进对话或仓库。

```bash
mkdir -p ~/.workbuddy
read -s TOKEN && printf '%s' "$TOKEN" > ~/.workbuddy/github_pat && chmod 600 ~/.workbuddy/github_pat
```

然后执行：

```bash
python3 scripts/publish_github.py --dry-run
python3 scripts/publish_github.py
```

首次发布时加 `--private` 建私有仓库，默认公开。脚本只读取环境变量 `GITHUB_TOKEN` 或上述文件，不会把 token 写进仓库、日志或标准输出，并在上传前校验 token 所属账号与 `--owner` 一致。脚本可重复运行，内容未变的文件自动跳过，变化的文件带 sha 更新，适合本地改动后随时同步。

## 文件结构

```
config/          角色名册与端点配置样例
src/llm.py       OpenAI 兼容客户端，标准库实现
src/models.py    任务卡、消息、产出物
src/team.py      编排、会议、交接、验收、放行
src/ledger.py    庄颜账本
src/cli.py       命令行
tests/           离线闭环自检
scripts/         GitHub API 发布脚本
run.py           一键入口
```

## 许可证

MIT，见 LICENSE。
