# Infinite-Canvas / Yanwo Roadmap

> 用途：作为 Codex 的长期执行路线文件。  
> 目标：让 Codex 在不需要每个阶段都向用户确认的情况下，按既定边界持续推进项目；只有触发“停止条件”时才暂停并询问用户。

---

## 0. 执行方式

Codex 每次进入该项目时，应先阅读本文件，再检查当前 Git 状态、最近提交和已有测试结果，然后从**第一个尚未完成的阶段**继续。

推荐启动指令：

```text
读取 docs/CODEX_ROADMAP.md。

检查当前仓库状态和已完成阶段，从第一个未完成阶段开始执行。
满足当前阶段验收条件后，独立提交 commit，并自动进入下一阶段。

除非触发路线图中的“必须停止并询问用户”的条件，否则不要因为普通实现细节、命名、文件拆分、测试组织或内部 API 选择而停下来询问。

不要跳过测试，不要顺手重构无关代码，不要提前实现后续阶段。
```

---

# 1. 项目最终目标

将当前 Infinite-Canvas 逐步演进为一个：

- Ubuntu NAS + Docker 优先运行；
- 保持 upstream 可持续同步；
- 兼容现有 Canvas 数据；
- 支持仓库本地插件；
- 支持可组合工作流控制结构；
- 后续可逐步改造成类似 ComfyUI 的专业节点工作区；
- 新功能尽量通过插件扩展，而不是继续向超大的 `smart-canvas.js` 中追加硬编码分支；

的长期可维护版本。

最终希望形成的能力包括：

```text
现有 Smart Canvas
        ↓
Plugin Host
        ↓
通用插件节点
        ↓
List
        ↓
For Each
        ↓
IF / Switch
        ↓
更统一的工作流调度
        ↓
UI Extension
        ↓
Yanwo UI / ComfyUI 风格工作区
```

---

# 2. 当前基线

项目开发仓库：

```text
/srv/storage/Code/Infinite-Canvas
```

旧部署：

```text
/opt/docker/canvas/app
```

旧部署是已知可运行版本，除非明确进入正式迁移阶段，否则不要直接破坏或覆盖。

当前已完成：

## 2.1 Fork / upstream

Fork：

```text
yanwo-lab/Infinite-Canvas
```

Upstream：

```text
hero8152/Infinite-Canvas
```

已配置 GitHub Actions 自动同步 upstream。

同步原则：

- upstream 无更新时不产生无意义提交；
- 有更新时做正常 Git merge；
- 冲突则停止，不使用强制 ours/theirs 覆盖；
- 基础语法验证通过后再 push；
- 保持 Fork 尽量接近 upstream。

---

## 2.2 Docker 适配

已经完成 Ubuntu NAS + Docker 基础适配。

宿主机挂载变量：

```text
CANVAS_HOST_DATA_DIR
CANVAS_HOST_UPLOADS_DIR
CANVAS_HOST_CACHE_DIR
CANVAS_HOST_OUTPUT_DIR
```

容器进程变量：

```text
CANVAS_DATA_DIR
CANVAS_UPLOADS_DIR
CANVAS_CACHE_DIR
CANVAS_OUTPUT_DIR
```

容器内稳定路径：

```text
/data/app
/data/uploads
/data/cache
/data/output
```

Docker 镜像已验证：

- build 成功；
- healthcheck 正常；
- `ffmpeg` / `ffprobe` 可用；
- 容器重启次数为 0；
- 首页、Canvas 页面和 API 正常；
- runtime 数据能够写入宿主机 volume；
- 仓库敏感配置不会被错误 COPY 进镜像。

Docker 运行时依赖以：

```text
标准 Python 镜像 + requirements.txt
```

为准。

不得使用 upstream 自带的：

```text
python/
packages/
```

作为 NAS Docker 的 Python 环境或包来源。

---

## 2.3 Sparse Checkout

NAS 本地已经使用 non-cone sparse-checkout。

GitHub Fork 保持 upstream 完整，但本地工作树不检出明确与 Ubuntu NAS + Docker 无关的 Windows/macOS 便携发行资源。

重要原则：

- sparse-checkout 仅影响本机工作树；
- 不提交删除记录；
- 不改变 Git index 中的 tracked 文件；
- 不影响 fetch / merge / GitHub upstream 同步；
- 第三类“不确定但可能有用”的 Linux CLI、工具、connector 等继续保留。

---

# 3. 不可破坏的项目原则

以下原则适用于所有阶段。

## 3.1 Upstream 兼容优先

不要为了“项目看起来更干净”而大规模删除 upstream 内容。

可以通过：

- Docker build context；
- sparse-checkout；
- `.dockerignore`；
- 独立模块；
- 插件层；

实现隔离，而不是制造大量 upstream divergence。

---

## 3.2 不迁移现有内置节点

当前现有内置节点继续保持现状：

- Image
- Prompt
- Loop
- MiniMax
- Smart Group

在 Plugin Host 阶段及后续阶段中：

**不要顺手把这些节点迁移成插件。**

只有未来有明确收益并单独规划时才考虑。

---

## 3.3 旧 Canvas 数据必须兼容

任何新增字段都应采用可选方式。

例如 connection 现状：

```js
{
  from,
  to,
  kind
}
```

未来可扩展为：

```js
{
  from,
  to,
  kind,
  fromPort,
  toPort
}
```

但：

- 老数据缺少 `fromPort` / `toPort` 必须继续正常；
- 老节点 JSON 必须正常恢复；
- 保存旧 Canvas 时不得悄悄破坏未知字段；
- 插件缺失时不能直接丢掉节点原始 JSON。

---

## 3.4 不做无关重构

如果某段旧代码很丑，但与当前阶段无关：

不要顺手整理。

允许的重构仅限：

- 为当前功能建立必要 extension seam；
- 为测试隔离必要逻辑；
- 修复当前阶段明确暴露的兼容问题；
- 避免继续扩大巨型文件的最小拆分。

---

## 3.5 新功能优先插件化

只要插件系统已经具备足够能力：

```text
List
For Each
IF
Switch
Filter
Zip
UI Theme
Sidebar
Inspector
```

优先作为插件实现。

只有插件无法完成的底层基础能力，才进入核心。

---

# 4. Codex 的自主判断范围

以下问题不需要询问用户，可由 Codex 根据源码、测试和长期维护性自行决定：

- 函数名称；
- 类名称；
- 文件拆分；
- 模块位置；
- 测试文件组织；
- 内部 helper 设计；
- adapter 的具体形式；
- Manifest 解析实现；
- Registry 内部数据结构；
- 错误日志格式；
- CSS class 命名；
- 小型兼容 shim；
- 是否增加必要的单元测试、集成测试；
- 是否需要把某段小逻辑从 `smart-canvas.js` 拆到独立模块；
- 当前阶段范围内的合理 bug 修复；
- 实现某个已批准接口时的具体算法选择。

默认原则：

> 如果不会改变用户已经批准的产品行为、数据模型语义或整体架构方向，就自行判断。

---

# 5. 必须停止并询问用户的条件

仅在以下情况暂停路线图：

## 5.1 数据兼容性变化

例如：

- 必须修改旧 Canvas JSON 的含义；
- 必须迁移已有数据；
- 旧节点无法兼容；
- 旧 connection 必须强制新增字段；
- 保存后会造成不可逆变化。

---

## 5.2 用户可见行为发生重大变化

例如：

- 现有 Loop 行为需要重定义；
- Prompt 节点语义需要改变；
- 原有菜单/交互必须删除；
- 原有页面入口需要替换。

---

## 5.3 需要删除 upstream 功能

包括：

- 删除已有节点；
- 删除 API；
- 删除工具；
- 删除跨平台能力；
- 删除旧数据兼容逻辑。

---

## 5.4 需要大型新依赖

例如：

- 引入完整前端框架；
- 引入图执行引擎；
- 引入大型状态管理系统；
- 引入新的后端服务；
- 引入必须单独部署的数据库或消息队列。

小型、明确、必要的依赖可以自行判断。

---

## 5.5 路线图假设被源码证明错误

如果实现过程中发现：

- Plugin Host 无法通过小 extension seam 接入；
- `runSmartCascade` 的结构使后续方案完全不可行；
- 前端实际数据模型与此前分析有重大冲突；
- 某阶段必须提前完成后续大规模架构重写；

则停止，提供证据和 2–3 个可选方案。

---

## 5.6 出现无法解释的核心回归

如果：

- 原有 Canvas 大面积失效；
- Docker 基线无法恢复；
- 测试失败无法确定是否由本次修改引起；
- upstream 新版本与当前架构出现根本冲突；

停止并报告，不要用临时 hack 强行通过。

---

# 6. 全阶段开发纪律

每个阶段都应：

1. 检查当前 Git 状态；
2. 检查该阶段相关源码；
3. 使用 TDD；
4. 先写能证明需求的失败测试；
5. 实现最小可行功能；
6. 做回归验证；
7. 使用 `superpowers:verification-before-completion`；
8. `git diff --check`；
9. Docker build；
10. 需要时做容器级实际验证；
11. 满足验收后独立 commit；
12. 自动进入下一阶段。

不要把多个阶段混进一个 commit。

推荐 commit 类型：

```text
feat:
fix:
refactor:
test:
chore:
```

---

# 7. 阶段 1：Plugin Host

## 7.1 目标

建立正式的仓库本地插件机制，使未来增加节点不需要继续向 `smart-canvas.js` 添加节点类型硬编码。

插件模型：

```text
trusted
repository-local
same-page
ES Module
```

第一阶段不做安全沙箱。

---

## 7.2 插件目录

建议：

```text
plugins/
└─ example-text/
   ├─ plugin.json
   ├─ index.js
   └─ style.css
```

后端提供插件发现 API，例如：

```text
GET /api/plugins
```

扫描：

```text
plugins/*/plugin.json
```

不得把插件列表硬编码进 Python 或前端。

---

## 7.3 Manifest

最低支持：

```json
{
  "id": "example-text",
  "name": "Example Text",
  "version": "0.1.0",
  "apiVersion": 1,
  "main": "index.js",
  "styles": ["style.css"]
}
```

以后允许扩展，但第一阶段不设计复杂依赖管理。

---

## 7.4 Plugin Host

建立独立模块，不把全部逻辑继续写入 `smart-canvas.js`。

概念上至少包括：

```text
PluginLoader
PluginRegistry
PluginHost facade
```

插件入口形式建议：

```js
export async function activate(host) {
  host.registerNode(...)
}
```

具体命名允许 Codex 根据当前代码结构调整。

---

## 7.5 Node 注册能力

第一阶段至少要支持描述：

```text
type
title
category
icon
create
render
bindUI
inputs
outputs
execute
serialize
deserialize
```

Host 不应直接暴露整个 Canvas 内部状态。

建议能力：

```text
registerNode
updateNode
getNode
requestRender
requestSave
getIncomingConnections
getOutgoingConnections
toast
log
```

---

## 7.6 Port 兼容扩展

允许 connection 增加：

```js
fromPort
toPort
```

但保持：

```text
kind ≠ port
```

语义：

```text
kind
= flow / input / history 等连接类别

fromPort / toPort
= 节点内部具体端口
```

缺失 port 时使用默认端口。

---

## 7.7 执行结果协议

为未来工作流节点建立统一方向：

```js
{
  outputs: {
    output: [
      {
        type: "text",
        value: "hello"
      }
    ]
  },
  flow: {
    continue: ["output"]
  },
  repeat: []
}
```

第一阶段可只实现 Example Text 所需子集，但结构要能自然扩展到：

- List；
- IF；
- For Each。

不要现在重写整个 `runSmartCascade`。

只建立最小 adapter / execution seam。

---

## 7.8 Example Text 插件

不能只是 Hello World。

需要验证完整插件链路。

功能：

- 一个文本输入端口；
- 一个文本输出端口；
- 一个本地文本字段；
- 至少一个自定义 UI 控件或按钮；
- 有 upstream text 时使用 upstream；
- 没有 upstream 时使用本地文本；
- 输出：

```text
Example: <text>
```

支持：

```text
Example A
   ↓
Example B
```

---

## 7.9 插件异常隔离

以下边界独立捕获异常：

```text
manifest parse
module import
activate
create
render
bindUI
execute
serialize
deserialize
```

插件失败不得导致整个 Smart Canvas 白屏。

---

## 7.10 Unknown Plugin Node

如果 Canvas 中存在当前缺失插件节点：

必须显示占位节点。

要求：

- 保留原始 JSON；
- 显示缺失插件/type；
- 允许删除；
- 保存时不得静默破坏原始数据。

---

## 7.11 UI 扩展预留

Plugin Host 不应锁死为只能注册 Node。

未来可能增加：

```text
registerStyle
registerToolbarItem
registerContextMenuItem
registerSidebarPanel
registerInspectorPanel
```

第一阶段无需全部实现。

但 Manifest 中的 CSS 必须可加载。

---

## 7.12 非目标

本阶段禁止实现：

- List；
- For Each；
- IF；
- Switch；
- Filter；
- Zip；
- ComfyUI 风格界面；
- 插件商店；
- iframe sandbox；
- Worker sandbox；
- 第三方权限模型；
- 内置节点插件化；
- 全量替换 `runSmartCascade`。

---

## 7.13 验收条件

至少验证：

1. `/api/plugins` 可以发现 Example Text；
2. 浏览器启动成功加载插件；
3. 新增节点入口出现 Example Text；
4. 可以创建插件节点；
5. 自定义 UI 正常；
6. 本地字段保存后 reload 不丢失；
7. Example A → Example B 可以传 text；
8. 老 Canvas 正常加载；
9. 老 connection 无 port 仍正常；
10. 一个故意损坏的测试插件不能让页面崩溃；
11. 缺失插件显示 Unknown Plugin Node；
12. Docker build 成功；
13. Docker 容器运行正常；
14. 原有 Smart Canvas 基础功能正常；
15. `git diff --check` 通过。

完成后独立 commit，再进入阶段 2。

---

# 8. 阶段 2：List 数据类型与 List 插件

## 8.1 目标

建立一等公民的通用 List 数据能力。

List 不是 Prompt 专用结构，也不是 Loop 的附属功能。

List 应能够承载：

```text
text
image
number
boolean
object
future typed values
```

第一阶段重点支持文本列表。

---

## 8.2 用户场景

既支持：

```text
LLM
 ↓
List
```

也支持用户手写：

```text
List
├─ task 1
├─ task 2
├─ task 3
└─ task 4
```

这样用户不依赖 LLM，也能手工组织批量任务。

---

## 8.3 List 插件

实现为：

```text
plugins/list/
```

而不是核心节点。

最低功能：

- 手动新增 item；
- 删除 item；
- 调整 item 顺序；
- 编辑 item；
- 从 upstream 接收可转换为 List 的输入；
- 输出 typed list；
- 正确 serialize / deserialize。

---

## 8.4 数据语义

List 的长度属于数据本身：

```text
length(list)
```

后续 For Each 应根据 collection 长度迭代。

不要把 List 长度耦合到现有 Loop 的 `count`。

---

## 8.5 非目标

本阶段不要：

- 修改 Loop 行为；
- 实现 For Each；
- 实现 IF；
- 引入复杂 schema editor；
- 实现嵌套图形化 object 编辑器。

---

## 8.6 验收

至少：

- 可手动创建 0/1/N 项 List；
- reload 后内容和顺序一致；
- 下游插件可收到完整 List；
- 空 List 行为明确；
- 老 Canvas 不受影响；
- Docker 回归通过。

完成后独立 commit，进入阶段 3。

---

# 9. 阶段 3：For Each

## 9.1 目标

增加真正的 collection iteration。

For Each 的含义：

```text
对 collection 中每一个 item
执行一次下游分支
```

而不是：

```text
设置 Loop count = List.length
```

---

## 9.2 插件形式

实现为：

```text
plugins/for-each/
```

---

## 9.3 最低输入输出

输入概念：

```text
collection
```

每次迭代至少提供：

```text
item
index
```

建议未来可扩展：

```text
length
first
last
```

第一阶段无需全部 UI 暴露。

---

## 9.4 执行语义

For Each 应依赖 Plugin Host 的：

```text
repeat
```

或等价统一执行协议。

不要让核心通过：

```js
if (node.type === "for-each")
```

实现业务逻辑。

如果 Plugin Host 当前 execution seam 不足，可以扩展通用协议，但不要为 For Each 写类型专用 hardcode。

---

## 9.5 与现有 Loop 的关系

现有 Loop：

```text
Repeat N Times
```

For Each：

```text
For Each Item In Collection
```

两者都保留。

不要替换现有 Loop。

---

## 9.6 验收

测试：

```text
List ["A", "B", "C"]
    ↓
For Each
    ↓
Example Text
```

应产生三次下游执行，对应：

```text
A
B
C
```

还需要验证：

- 空 List；
- 单 item；
- item 顺序；
- index；
- 下游错误传播；
- reload；
- 与旧 Loop 共存。

完成后独立 commit，进入阶段 4。

---

# 10. 阶段 4：IF / Branch

## 10.1 目标

补齐工作流三类基本控制结构：

```text
顺序
分支
循环
```

顺序已由连接图存在。

循环已有：

```text
Loop
For Each
```

本阶段增加分支。

---

## 10.2 IF 插件

实现：

```text
plugins/if/
```

至少有：

```text
condition input
true flow port
false flow port
```

condition 初期支持：

```text
boolean
```

可选支持简单 truthy conversion，但语义必须明确。

---

## 10.3 多输出端口

本阶段应正式验证：

```text
fromPort
toPort
```

能够支持：

```text
true
false
```

两条独立 flow。

不要把 true / false 编进 `kind`。

---

## 10.4 执行协议

IF 应通过通用 flow 结果选择下游：

```js
flow: {
  continue: ["true"]
}
```

或：

```js
flow: {
  continue: ["false"]
}
```

具体格式可由当前实现调整，但不能依赖节点类型硬编码。

---

## 10.5 验收

至少：

```text
boolean true
    ↓
IF
 ├─ true  → A
 └─ false → B
```

仅 A 执行。

false 情况仅 B 执行。

另外验证：

- reload；
- 多端口 connection；
- 老 connection；
- 缺失 condition；
- 插件错误隔离。

完成后独立 commit，进入阶段 5。

---

# 11. 阶段 5：执行协议收敛

## 11.1 目标

此时已经实际拥有：

- 普通插件节点；
- List；
- For Each；
- IF；
- 现有内置 Loop。

利用真实使用情况重新审视当前 execution seam。

只有在前几阶段证明必要时，才进行最小范围的调度器收敛。

---

## 11.2 目标不是“重写一切”

禁止因为追求架构漂亮而直接重做整个 Canvas runtime。

应优先：

```text
保留 runSmartCascade
        ↓
提取通用 scheduler helper
        ↓
逐步让 plugin execution 使用统一路径
```

---

## 11.3 核心概念

执行模型至少需要能表达：

```text
data outputs
flow continuation
repeat / iteration
errors
execution context
```

可能的统一形式：

```js
{
  outputs: {},
  flow: {
    continue: []
  },
  repeat: [],
  meta: {}
}
```

最终结构由实际实现决定。

---

## 11.4 Execution Context

建议形成明确 execution context，而不是插件直接读取全局变量。

可能包括：

```text
node
inputs
connections
runId
iteration
abort signal
logger
host facade
```

只有真实需要的字段进入稳定接口。

---

## 11.5 验收

构建包含：

```text
List
  ↓
For Each
  ↓
IF
  ├─ true
  └─ false
```

的组合工作流。

验证：

- 顺序；
- 分支；
- 循环；
- 数据传递；
- reload；
- 错误隔离；
- 中断/失败不会污染后续运行；
- 现有节点仍可使用。

完成后独立 commit，进入阶段 6。

---

# 12. 阶段 6：插件 UI 扩展能力

## 12.1 目标

让 Plugin Host 从：

```text
Node Plugin Host
```

逐渐升级为：

```text
Canvas Extension Host
```

但仍坚持增量实现。

---

## 12.2 建议能力

根据实际页面结构逐步加入稳定 slot：

```text
registerStyle
registerToolbarItem
registerContextMenuItem
registerSidebarPanel
registerInspectorPanel
```

不要求一次全部实现。

优先顺序根据 Yanwo UI 的实际需求决定。

---

## 12.3 设计要求

UI 插件：

- trusted same-page；
- 错误隔离；
- 不应直接依赖大量内部 DOM selector；
- 优先通过 Host 提供的稳定挂载点；
- CSS 可独立加载/卸载；
- 一个 UI 插件失败不能使 Canvas 主功能不可用。

---

## 12.4 非目标

暂不做：

- 第三方插件市场；
- runtime 权限系统；
- 在线下载插件；
- 插件签名；
- iframe sandbox；
- Worker sandbox。

---

## 12.5 验收

创建最小测试 UI 插件，至少证明：

- 可加载 CSS；
- 可在一个正式 UI slot 中挂载控件；
- reload 正常；
- 插件失败不白屏；
- 插件禁用/缺失不会破坏 Canvas。

完成后独立 commit，进入阶段 7。

---

# 13. 阶段 7：Yanwo UI / ComfyUI 风格工作区

## 13.1 目标

在不破坏工作流数据模型的前提下，将 Smart Canvas 逐步调整为更专业的节点编辑器体验。

参考方向是 ComfyUI 的信息结构与专业工作区感，但不是像素级复制。

---

## 13.2 总体视觉

目标：

```text
深色专业工作区
清晰节点层级
明确端口
稳定网格
更清晰的连接线
更高效的节点搜索/创建
减少网页式 UI 感
```

---

## 13.3 UI 结构方向

可逐步形成：

```text
┌──────────────────────────────────────────────┐
│ Top Toolbar                                  │
├────────────┬──────────────────────┬──────────┤
│ Node       │                      │ Inspector│
│ Library    │    Canvas Workspace  │ / Props  │
│            │                      │          │
├────────────┴──────────────────────┴──────────┤
│ Status / Run Information                     │
└──────────────────────────────────────────────┘
```

但实际布局应先检查现有 Smart Canvas 交互，再做最小演进。

---

## 13.4 Yanwo UI 插件

优先实现成：

```text
plugins/yanwo-ui/
```

例如：

```text
plugin.json
index.js
style.css
```

纯视觉改动尽量通过 CSS。

需要结构性 UI 时使用阶段 6 的正式 extension slot。

避免重新直接修改大量 `smart-canvas.html`。

---

## 13.5 节点体验

逐步统一：

- Node header；
- body；
- port；
- selection；
- hover；
- disabled；
- running；
- success；
- error；
- unknown plugin；
- group。

节点类型仍可以保留自己的视觉特征，但不应完全各写各的。

---

## 13.6 工作区交互

根据当前实现评估后逐步优化：

- 缩放；
- 平移；
- 框选；
- 多选；
- 节点创建；
- 快速搜索；
- connection 拖拽；
- context menu；
- 属性编辑；
- 运行状态反馈。

不要在没有测试的情况下同时重写全部交互。

---

## 13.7 验收

至少：

- 插件节点与旧节点视觉一致性提升；
- List / For Each / IF 端口清晰；
- Canvas 操作不退化；
- 原有保存/加载不受影响；
- UI 插件移除后核心仍可用；
- Docker 浏览器实测。

完成后独立 commit，进入阶段 8。

---

# 14. 阶段 8：整体兼容与正式部署准备

## 14.1 目标

将前面所有阶段组合验证，并准备替换旧部署。

---

## 14.2 核心组合测试

建立至少一个完整真实工作流：

```text
Prompt / Manual Input
        ↓
List
        ↓
For Each
        ↓
IF
      ↙    ↘
 branch A branch B
        ↓
 downstream node
```

以及：

```text
现有内置节点
+
插件节点
```

混合工作流。

---

## 14.3 数据兼容

测试：

- 老 Canvas JSON；
- 新 Canvas JSON；
- 缺失插件；
- 插件恢复；
- 老 connection；
- port connection；
- List；
- For Each；
- IF；
- old Loop。

---

## 14.4 Docker

最终 Docker 验证：

- clean build；
- fresh volumes；
- existing volumes；
- restart；
- healthcheck；
- assets；
- uploads；
- output；
- Canvas JSON；
- cache；
- plugin discovery；
- static plugin modules；
- CSS；
- ffmpeg/ffprobe。

---

## 14.5 Upstream 合并演练

在临时分支或安全环境执行：

```text
fetch upstream
merge upstream/main
```

验证当前自定义架构没有产生不必要的大面积冲突。

如 upstream 没有新提交，也至少评估自定义修改集中度。

---

## 14.6 旧部署迁移

正式迁移前：

- 不直接删除旧部署；
- 记录旧 deployment 配置；
- 记录 volume / bind mount；
- 新版先运行在独立端口；
- 浏览器验收；
- 再修改 Nginx upstream；
- 保留快速回滚路径。

---

## 14.7 最终验收

最终必须确认：

```text
Docker
Plugin Host
Example Plugin
List
For Each
IF
Execution
UI Extension
Yanwo UI
Old Canvas Compatibility
Upstream Compatibility
```

全部通过。

最后形成独立 release/里程碑 commit。

---

# 15. 后续候选功能

以下功能不属于当前路线图强制范围。

除非前述阶段全部完成，否则不要提前实现。

可能包括：

```text
Switch
Filter
Map
Reduce
Zip
Merge
List Transform
Object
JSON
Number
Boolean
Delay
Retry
Error Branch
Reusable Subflow
Workflow Variables
Node Search
Plugin Enable/Disable
Plugin Settings
Plugin Dependency Metadata
```

这些应建立在已经验证过的 Plugin Host 与执行协议上。

---

# 16. 关于现有 Loop

现有 Loop 保持：

```text
Repeat N Times
```

不要为了 For Each 修改成 collection loop。

最终控制结构定义：

```text
Sequence
= 图连接自然顺序

Branch
= IF / Switch

Repeat
= 现有 Loop

Collection Iteration
= For Each
```

这是长期语义边界。

---

# 17. 关于 List

List 是数据结构，而不是控制结构。

错误设计：

```text
Prompt 输出 5 项
↓
自动把 Loop count 改成 5
```

正确设计：

```text
Prompt
↓
List
↓
For Each
```

或者：

```text
Manual List
↓
For Each
```

List 与 LLM、Prompt、Loop 均不应强耦合。

---

# 18. 关于 UI

长期原则：

> 工作流核心数据模型与 UI 主题分离。

不要因为未来做 ComfyUI 风格 UI 而改变：

- Canvas JSON 基本含义；
- node type 语义；
- connection 语义；
- plugin execution；
- workflow control。

UI 是视图和交互层，不是工作流数据模型。

---

# 19. 关于插件可信模型

当前插件仅面向：

```text
repository-local trusted plugins
```

因此第一阶段不需要复杂安全模型。

但必须保持：

```text
错误隔离
稳定 Host facade
不过度暴露内部状态
```

未来如果真的引入第三方插件生态，再单独规划：

- permissions；
- sandbox；
- signing；
- marketplace；
- version resolution。

不要提前设计。

---

# 20. 每阶段完成报告格式

每阶段完成后，Codex 应简洁报告：

```text
阶段：
Commit：

实现：
- ...

关键兼容策略：
- ...

测试：
- ...

Docker：
- ...

遗留：
- ...

git status：
...
```

如果验收全部通过：

**无需等待用户回复，继续下一阶段。**

如果触发第 5 节停止条件：

必须停止，并说明：

```text
发现的问题
为什么路线图假设不成立
影响范围
证据
方案 A
方案 B
推荐方案
```

---

# 21. 最终目标判断标准

项目最终不是为了“插件多”，也不是为了“像 ComfyUI”。

真正目标是：

```text
用户可以把工作流程拆成稳定的数据与控制结构，
新增能力不需要继续修改巨型核心文件，
现有工作流长期兼容，
Docker 部署稳定，
upstream 仍可持续合并，
UI 可以独立演进。
```

只有达到这个状态，路线图才算真正完成。
