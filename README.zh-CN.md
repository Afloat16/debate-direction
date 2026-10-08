# Debate Direction

**在投入实现一项模糊需求之前，先让两个 agent 提出方案、质疑并修订方向。**

给它一个问题和相关上下文。正方负责提出备选方案，反方负责找出重要缺陷。双方围绕同一个方案反复修订，协调器维护问题台账，最后返回核心交锋、当前建议、剩余分歧和验证步骤。

共识不等于正确性证明。使用相同模型的两个角色也可能共享盲区。输出是一个有待验证的方向，其中的假设仍会明确保留。

[English](README.md) · [安装指南](docs/installation.md) · [模型服务商](docs/providers.md) · [宿主兼容性](skills/debate-direction/references/host-compatibility.md) · [验证记录](docs/validation.md) · [MIT](LICENSE)

## 一条命令安装

### macOS 和 Linux

```sh
curl -fsSL https://raw.githubusercontent.com/Afloat16/debate-direction/main/install.sh | sh
```

### Windows PowerShell

```powershell
& ([scriptblock]::Create((Invoke-RestMethod https://raw.githubusercontent.com/Afloat16/debate-direction/main/install.ps1)))
```

安装程序会为当前用户创建独立环境，并通过 [uv](https://docs.astral.sh/uv/) 自动获取 Python。无需事先安装 Python 或 Git。首次安装需要联网，运行平台也必须受到 uv 所使用的 Python 发行版支持。在 Linux 上，上述下载命令需要 `curl`；[安装指南](docs/installation.md) 还介绍其他安装方式、已有 Python 的使用方法、WSL、更新和卸载。

安装完成后，可立即使用程序输出的完整可执行文件路径。如果终端还找不到 `debate-direction`，按输出提示把对应目录加入当前终端的 PATH；若要在以后的终端中直接使用，再把该目录加入用户 PATH。安装不会修改 shell 配置文件，也不需要管理员权限。

先试试固定的离线示例：

```sh
debate-direction --demo
```

打开生成的 `report.html`。演示**不会调用任何模型**，用于展示方案如何因质疑而变化。它使用固定案例，不分析自定义问题。

## 在 Codex、Claude Code 或 Kimi Code 内使用

选择宿主，即可同时安装 CLI 和原生技能：

```sh
curl -fsSL https://raw.githubusercontent.com/Afloat16/debate-direction/main/install.sh | sh -s -- --host codex
```

```powershell
& ([scriptblock]::Create((Invoke-RestMethod https://raw.githubusercontent.com/Afloat16/debate-direction/main/install.ps1))) -Host claude
```

可选值为 `codex`、`claude`、`kimi` 或 `all`。如果已经安装了 CLI：

```sh
debate-direction install-skill --host codex
debate-direction install-skill --host claude
debate-direction install-skill --host kimi
```

| 宿主 | 默认个人技能目录 | 在宿主中的调用方式 |
| --- | --- | --- |
| Codex | `~/.agents/skills/debate-direction` | `$debate-direction` |
| Claude Code | `~/.claude/skills/debate-direction` | `/debate-direction` |
| 当前版本的 Kimi Code | `~/.kimi-code/skills/debate-direction`，或 `$KIMI_CODE_HOME/skills/debate-direction` | `/skill:debate-direction` |

安装后刷新宿主的技能列表，或开启新会话。例如在 Codex 中输入：

```text
$debate-direction
Find feasible changes to our support dashboard within two weeks.
Preserve existing permissions. Return the core exchanges, recommended
direction, unresolved issues and validation steps.
```

**若要保留发起会话的模型和思考强度，应使用原生模式。** 它会创建且只创建两个持续保留的子 agent，并始终继续同一对角色。模型和思考强度这两项设置，都必须有适用于当前宿主的继承保证或运行时证据。子 agent 默认配置发生冲突、出现模型回退，或宿主没有可恢复的 agent 时，程序会明确说明限制。它不会猜测界面中不可见的设置，也不会写入固定模型来覆盖会话配置。

安装程序只复制技能，不会安装 Codex、Claude Code 或 Kimi Code，也不会替这些宿主登录。原生辩论复用宿主已有的身份认证。[宿主兼容性](skills/debate-direction/references/host-compatibility.md) 记录了各宿主的要求和当前官方资料。没有真实子 agent 工具的普通聊天界面无法运行原生模式。

使用 `--project` 可安装到当前项目，使用 `--project PATH` 可安装到其他项目，使用 `--skills-dir PATH` 可指定自定义或旧版技能根目录。内容相同的重复安装不会执行修改。已被改动的技能会保留，只有明确传入 `--force` 才允许替换；替换时会在宿主扫描的技能目录之外保留备份。安装不会改变宿主的模型设置。

## 通过 CLI 使用 DeepSeek、Kimi、Claude、OpenAI 或 Gemini

独立 CLI 提供六种服务商预设。两个 agent 使用同一组不可变的服务商、模型和思考配置。**CLI 无法读取其他应用的模型选择器。** 可以明确配置一次，也可以在每次运行时传入参数。

| 预设 | API | API 密钥环境变量 |
| --- | --- | --- |
| `openai` | OpenAI Responses | `OPENAI_API_KEY` |
| `anthropic` | Anthropic Messages | `ANTHROPIC_API_KEY` |
| `deepseek` | DeepSeek Chat Completions | `DEEPSEEK_API_KEY` |
| `kimi` | Moonshot/Kimi Chat Completions | `MOONSHOT_API_KEY` |
| `gemini` | Gemini 的 OpenAI 兼容接口 | `GEMINI_API_KEY` |
| `openai-compatible` | 明确指定的兼容 HTTPS 接口 | `OPENAI_COMPATIBLE_API_KEY` |

服务商与宿主是两个概念：如果在 Claude Code 中使用 DeepSeek，应按 Claude 的方式安装技能；CLI 的 DeepSeek 预设则直接连接 DeepSeek API。

### 配置一次，重复使用

运行引导式设置：

```sh
debate-direction setup
```

也可以提供完整配置，例如：

```sh
debate-direction setup --provider deepseek --model deepseek-flash --reasoning-effort high
```

在当前终端设置 API 密钥。macOS/Linux：

```sh
export DEEPSEEK_API_KEY='your-api-key'
```

Windows PowerShell：

```powershell
$env:DEEPSEEK_API_KEY = 'your-api-key'
```

然后就可以直接提问，无需重复填写设置：

```sh
debate-direction "Which changes should we pilot in our support dashboard?"
```

设置功能只保存非敏感配置，不会索取或保存密钥。请通过平时使用的环境变量或密钥管理工具提供凭据；`.env.example` 只是说明文件，不会被自动加载。[服务商配置](docs/providers.md) 介绍了各个预设、模型特定的思考控制、区域接口和自定义密钥变量名。

### 显式参数或调用方元数据

```sh
debate-direction "Which direction should we validate first?" --provider kimi --model kimi-k3 --reasoning-effort high
```

对于较长的需求说明：

```sh
debate-direction --question-file examples/question.txt --context-file examples/context.txt --provider openai --session-config examples/session-config.example.json
```

会话 JSON 必须且仅包含 `model` 和 `reasoning_effort`。它是调用方提供的配置，不是对其他聊天会话的认证证据。也可以同时提供完整的一组 `DEBATE_MODEL` 与 `DEBATE_REASONING_EFFORT`，必要时再设置 `DEBATE_PROVIDER`。

显式配置优先于自动加载的已保存配置。新选择的服务商不会静默沿用另一服务商保存的模型。显式传入 `--config PATH` 时，其内容必须与同时提供的设置一致。只有半组模型／强度配置，或者不同来源的完整配置彼此冲突，都会被拒绝。

### 思考设置因模型而异

`high` 不是统一的 token 预算。例如，当前 DeepSeek 模型提供 `none`、`low`、`high` 和 `max`；Kimi K3 提供 `low`、`high` 和 `max`；部分 Kimi 模型只提供开启／关闭思考的控制。适配器会验证模型支持哪些控制，不会把不支持的标签转换成一个声称等价的设置。

对于自定义接口，`provider_default` 表示明确省略思考强度参数，不承诺精确控制强度。若要直接透传强度标签，调用方必须先确认该接口对标签的实际定义。程序会记录接口返回的模型标识；发生模型漂移时会停止。CLI 无法独立验证服务商内部隐藏的配置。

## 常用命令

```sh
debate-direction providers
debate-direction doctor
debate-direction install-skill --host all --dry-run
debate-direction --help
```

`doctor` 检查本地安装、已保存的配置、凭据是否存在，以及技能所在位置。它不会输出密钥值，也不会调用模型。它不能认证原生模式的继承行为或实际 API 访问能力。服务商列表、诊断和技能安装命令均支持 `--json`，方便程序读取结果。

## 辩论如何运行

1. 正方与反方分别独立开场，维护各自分离的公开历史。
2. 反方评审第一版方案，这计为第一轮评审。
3. 正方逐项回应未决异议，并提交新版本。
4. 反方评审这个确切版本，以及全部历史问题，包括此前已经解决的项。
5. 达成收敛、缺少必要输入、讨论停滞、触及限制、被取消或发生故障时停止。

默认至少两轮、最多四轮评审，最多九次服务商调用。只有反方接受了实际答复，异议才能被解决。省略问题或认可旧版本都不能关闭异议。仍有 critical/high 级别的问题时，不能进入就绪状态。最终报告由确定性协调器生成，不会增加第三个模型来改写结论。

如果问题没有明确对象或上下文，合理结果可能只是几条必要的澄清问题。可以留作验证条件的未知项，不必阻止先选择一个方向。

## 结果与证据

每次运行会保存 `report.html`、`report.md` 和 `report.json`。报告保留方案版本、异议台账、公开交锋、服务商／模型配置、已上报用量、停止原因和后续步骤。

| 判断 | 含义 |
| --- | --- |
| `ready_to_validate` | 两个角色都接受当前方向，可以进入现实验证 |
| `conditional` | 建议仍附带需要保留的风险或条件 |
| `blocked` | 重要的未决问题阻止进入就绪状态 |
| `needs_clarification` | 缺失信息可能改变决策 |
| `undetermined` | 执行过程或公开记录不足以支持完整结论 |

CLI 始终记录 `verification_status: not_checked`：它不会自动浏览证据、执行代码或运行建议中的测试。问题被标为 `resolved`，只表示它在讨论中得到处理，不表示已经实证修复。

报告包含你的问题和上下文，分享前请先检查。服务商的私有推理和签名不会出现在报告与事件中。为了延续同一角色的会话，适配器可能在内存中单独暂存接口要求的协议字段，并在运行结束时清除。HTML 不包含脚本，并对模型文本进行转义。

## 限制与故障处理

```sh
debate-direction "Your question" --min-rounds 2 --max-rounds 4 --max-output-tokens 12000 --max-total-tokens 150000 --timeout 180 --max-duration 900 --out runs/my-review
```

该示例使用你已保存的配置。显式传入模型／服务商参数时，也可以搭配相同的限制选项。`--stall-rounds` 控制连续多少轮没有变化后停止。更高的思考强度可能需要更大的输出额度；截断、拒绝、格式错误和不完整响应都不会计为认可。

用量和总时长是根据实际观察值判断的停止阈值。正在处理的请求可能使阈值被超过，或在时限之后才完成；失败调用也可能有未上报的用量。程序不会自动重试或回退到其他模型。取消会阻止后续调用，但无法撤回服务商已经处理的请求。已有报告只有在明确传入 `--overwrite` 时才会被覆盖。

`--json` 把报告写到标准输出，进度仍写到标准错误；`--quiet` 隐藏进度。退出码：`0` 表示完整讨论，`1` 表示配置／输入／文件系统错误，`2` 表示缺少输入或方向仍未确定，`3` 表示部分执行，`130` 表示取消。退出码为零不代表建议已经被证明正确。

## 开发与验证

需要 Python 3.11+，没有第三方运行时依赖：

```sh
python -m pip install -e .
python scripts/sync_skill.py --check
python -m unittest discover -s tests -v
debate-direction --demo
```

GitHub Actions 会在 Windows、macOS 和 Linux 上运行平台检查，包括包安装和安装器演练。适配器测试使用受控传输，不需要 API 密钥。[验证记录](docs/validation.md) 区分实际完成的检查、之前的原生演练、依据文档判断的宿主兼容性，以及尚未测试的真实服务商组合。

修改随包分发的原生技能时，编辑 `skills/debate-direction`，再于构建前运行 `python scripts/sync_skill.py`。适配器应实现 `complete(...) -> Completion`，支持两个并发开场，保持共享配置，并返回真实的用量和模型元数据。详见[设计说明](docs/design.md)、[贡献指南](CONTRIBUTING.md)和[安全说明](SECURITY.md)。

v0.2 增加了各操作系统的安装器、本地设置／诊断、原生宿主技能安装，以及多个 API 适配器。自动检索、执行验证、从持久记录恢复辩论、托管服务，以及经过认证地读取其他应用的会话设置，仍不属于当前实现。

项目说明、元数据、CLI 提示、报告标签和示例均使用英文。辩论回复默认使用英文，除非明确要求其他语言；用户输入保留原文。[README.zh-CN.md](README.zh-CN.md) 提供完整中文使用说明。

## 许可证

[MIT](LICENSE)。欢迎贡献和改编。
