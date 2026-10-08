# Debate Direction · 方向辩论

**让两个 agent 通过提案、反驳和修订，把模糊需求变成可以验证的方向。**

正方负责给出具体方案，反方负责找关键漏洞。每轮都保留问题编号、实际回应和方案版本，最后返回核心交锋、建议方向、未解决问题与验证步骤。

**双方同意不等于方案已经正确或可行。** 项目帮助你更清楚地决定下一步；现实可行性仍需材料、测试和用户反馈来确认。相同模型的两个角色也可能共享盲区。

[English](README.md) · [协议设计](docs/design.md) · [验证记录](docs/validation.md) · [真实运行示例](docs/native-example.md) · [MIT License](LICENSE)

项目以英文作为默认语言：文档、技能说明、命令行提示、报告标签和内置示例均使用英文；本文件保留完整中文说明。辩论回复默认使用英文，也可以明确要求其他语言；用户提交的问题和上下文会保留原文。

## 能做什么

- 将“帮我找改进方向”拆成目标、约束、备选方案和验收标准。
- 两个角色先独立开场，再交换公开论据；避免反方只跟着正方的框架走。
- 逐轮追踪异议：正方不能自行关闭问题，反方不能靠省略让旧问题消失。
- 只接受对当前方案版本的评审，保留每轮方案和关键修订。
- 区分收敛、分歧、资料不足、停滞、轮数耗尽和调用故障。
- 导出 Markdown、JSON 和没有外部依赖的 HTML 决策报告。
- 用固定离线案例先了解流程，无需 API 密钥。

## 两种使用方式

| | 原生会话技能 | 独立命令行 |
| --- | --- | --- |
| 使用入口 | 支持子 agent 的 ChatGPT Work / Codex 宿主 | Python 3.11+ |
| 两位 agent | 宿主实际创建、保持并继续两个子 agent 线程 | 两份隔离角色历史，经真实模型调用交锋 |
| 模型与思考强度 | 按宿主支持的父会话继承规则，不覆盖配置 | 必须明确传入同一组参数 |
| 单独 API 密钥 | 原生技能不需要 | 实际运行需要 `OPENAI_API_KEY` |
| 证据能力 | 取决于宿主实际提供的工具与授权 | 不自动检索或执行测试，输出验证清单 |

**关于“与提问会话一致”**：原生技能只能在宿主明确支持继承时承诺这一行为。CLI 不能读取 ChatGPT 的模型选择器。`--session-config` 是调用方传来的配置，不是对外部会话身份或设置的认证。两名角色每次请求共用不可变配置；不支持的模型或思考强度会报错，不会静默降级。

## 先体验离线演示

在仓库目录中运行，只有 Python 标准库，没有运行时第三方依赖：

```bash
PYTHONPATH=src python3 -m debate_direction --demo
```

程序输出一个新报告目录，打开其中的 `report.html`。也可以先安装命令：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
debate-direction --demo
```

Windows PowerShell：先运行 `.venv\Scripts\Activate.ps1`，再执行安装和命令行。未安装时可用 `$env:PYTHONPATH = "src"` 后运行 `python -m debate_direction --demo`。

演示使用固定的客服工单案例和脚本回复，**真实模型调用为 0 次**。`--demo` 不接收自定义问题，避免把脚本内容冒充对任意问题的分析。

演示中能看到这样的演变：

1. 正方提出重做搜索与智能推荐。
2. 反方指出缺少瓶颈证据，整体重做范围过大，且权限边界不清。
3. 正方改成先测量、再试点组合筛选和个人视图，补上权限测试与回退条件。
4. 反方接受试点方向，结果进入验证阶段；没有声称生产数据或测试已通过。

## 在当前会话中使用技能

技能目录是 [`skills/debate-direction`](skills/debate-direction)。将整个目录安装到支持 Agent Skills 与真实子 agent 的宿主中，或者让宿主读取该目录的 `SKILL.md` 来执行。宿主必须确实提供子 agent 编排能力；仅支持聊天提示词的界面不满足要求。

安装后可以直接说：

> 使用 $debate-direction，让两个 agent 辩论：我们要改进客服工单后台，两周内优先做什么？已有状态筛选和关键词搜索，现有权限不能改变。请返回关键交锋、建议方向和验证步骤。

技能默认完成至少 2 轮、最多 4 轮评审，并始终继续原有两个 agent。若宿主无法保证模型/强度继承，或不能创建两个真实子 agent，会说明限制，不会用一条回复假扮双方。

如果你只说“为我找出可行的修改方案”，而没有任何修改对象或上下文，技能会先要求补齐最关键的信息。

## 用真实模型运行 CLI

设置 API 密钥，以及你实际希望双方使用的模型和思考强度。以下示例的模型和 `high` **只是示例配置**，请按自己的调用权限及发起会话的实际设置替换：

```bash
export OPENAI_API_KEY='your-api-key'

debate-direction \
  '我们的工单后台查找很慢，两周内有哪些可试点的改进方向？' \
  --model gpt-6-astra \
  --reasoning-effort high \
  --context-file examples/context.txt
```

也可以由上层应用传入整组配置：

```json
{
  "model": "gpt-6-astra",
  "reasoning_effort": "high"
}
```

```bash
debate-direction \
  --question-file examples/question.txt \
  --context-file examples/context.txt \
  --session-config examples/session-config.example.json
```

第三种方式是同时设置 `DEBATE_MODEL` 与 `DEBATE_REASONING_EFFORT`。程序不把显式参数和环境变量拼成来源不明的半组配置；与 `--session-config` 冲突的参数也会被拒绝。

`.env.example` 仅作为设置说明，CLI 不自动读取 `.env`。API 密钥只通过环境变量输入，不要写进问题、会话配置或仓库。

## 输出长什么样

每次运行生成：

| 文件 | 内容 |
| --- | --- |
| `report.html` | 可直接打开、可打印的结果页；显示核心交锋、异议与下一步 |
| `report.md` | 方便阅读与复核的文本报告 |
| `report.json` | 完整公开记录、问题历史、方案版本、调用用量及停止原因 |

报告包含你提交的问题和上下文；发布或分享前应自行检查。原始隐藏推理不被收集为辩论记录。HTML 不执行模型文本或加载外部脚本。

关键状态分别表示：

| 结果 | 含义 |
| --- | --- |
| `ready_to_validate` | 双方接受当前方向，进入现实验证 |
| `conditional` | 有条件建议，仍有已接受风险或保留事项 |
| `blocked` | 仍有严重问题阻断推进 |
| `needs_clarification` | 缺少会改变决策的关键信息 |
| `undetermined` | 调用、结构或流程不完整，不能形成完整结论 |

CLI 的 `verification_status` 始终为 `not_checked`。`resolved` 表示某条异议在论证中被处理，不表示该问题已经通过真实测试。

## 控制深度和消耗

```bash
debate-direction '你的问题' \
  --model gpt-6-astra --reasoning-effort high \
  --min-rounds 2 --max-rounds 4 \
  --max-output-tokens 12000 \
  --max-total-tokens 150000 \
  --timeout 180 --max-duration 900 \
  --out runs/my-review
```

- 默认最大 4 轮、最多 9 次 provider 调用；独立开场并行，后续交锋顺序进行。
- `max_output_tokens` 包含推理 token。高强度运行可能需要提高这个值；截断被视为未完成，不会当作认可。
- `max_total_tokens` 是已返回用量的停止阈值，进行中的调用可能超过它；它不是精确的金额上限。
- 总时长达到阈值后不再发起新调用，进行中的请求受单次 timeout 限制。
- 不自动重试，不自动切换模型。取消后停止启动后续调用；已经发出的请求可能仍由服务端处理。
- 已存在的报告不会默认覆盖。明确使用 `--overwrite` 才会替换同名报告。

`--json` 将完整 JSON 写到标准输出，进度留在标准错误；`--quiet` 隐藏进度。退出码：`0` 表示完整讨论，`1` 是配置/输入/文件错误，`2` 是需要信息或无法确定方向，`3` 是部分完成，`130` 是取消。**退出码 0 也不代表方案已被验证正确。**

## 开发与测试

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

测试使用假 provider 和受控回复，覆盖模型配置、初始上下文隔离、异议不能丢失、过期版本认可、错误与截断、取消、预算边界、报告转义和文件覆盖。离线测试不需要密钥，也不证明模型生成质量。原生技能需要在有子 agent 能力的宿主中演练。

扩展集成可实现 `provider.complete(...) -> Completion` 并复用 `DebateEngine`。自定义 provider 需支持两个同时进行的开场调用、返回真实用量和接口模型元数据，并尊重传入的模型/强度配置。具体字段见源码和 [协议设计](docs/design.md)。

## 已有范围与后续方向

v0.1 提供原生技能、Responses API CLI、确定性问题账本、报告与离线测试。后续可依据实际失败案例增加材料检索、可复用验证记录、从已保存报告继续讨论，以及更多明确传递模型设置的宿主适配。当前版本没有自动实施修改、网页服务或可认证的跨应用会话设置读取功能。

## 官方资料

- [子 agent、模型与思考强度继承](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- [Responses API 推理参数与 token 限制](https://developers.openai.com/api/docs/guides/reasoning)
- [结构化输出](https://developers.openai.com/api/docs/guides/structured-outputs)

## License

[MIT](LICENSE)。欢迎使用、修改和贡献。
