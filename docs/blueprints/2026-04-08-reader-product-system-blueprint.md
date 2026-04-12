# 2026-04-08 Reader Product System Blueprint

状态：target architecture blueprint，不是 current capability claim。
用途：定义 `SourceHarbor` reader-product reset 的产品对象模型、处理流水线、默认参数与改造边界。

依赖先读：

- `docs/start-here.md`
- `docs/architecture.md`
- `docs/project-status.md`
- `docs/testing.md`
- `.agents/Tasks/TASK_BOARD-4月8日-阅读器产品与无损合并主线.md`
- `.agents/Plans/2026-04-08__sourceharbor-reader-product-wave-program.md`
- `docs/blueprints/2026-04-09-reader-product-object-contract.md`
- `docs/blueprints/2026-04-09-reader-product-version-gap-contract.md`

谁应先读我：

- 任何要做 `W1-W5` 设计或实现的 worker
- 任何要写新的 handoff prompt 的 orchestrator

## 0. W1 Addenda

从 `2026-04-09` 开始，`W1` 已经拆成两份 addendum：

- `docs/blueprints/2026-04-09-reader-product-object-contract.md`
- `docs/blueprints/2026-04-09-reader-product-version-gap-contract.md`

这份 system blueprint 继续负责：

- 产品总图
- lane / stage 主链
- current truth vs target truth 分层

object contract addendum 负责：

- 每个对象到底是什么
- 它不是什么
- 谁创建 / 谁消费 / 谁允许修改
- 哪些细节留给 `W1-B`

version-gap contract addendum 负责：

- `window_id` / `cutoff_at`
- stable key / internal UUID / version
- `published_with_gap` / yellow warning
- `TraceabilityPack` minimum schema
- incremental rejudge / rebuild / repair 升级规则

而 `W1-A` / `W1-B` 的 closeout / handoff ledger 在这里：

- `.agents/Plans/2026-04-09__sourceharbor-W1-A-object-contract-closeout.md`
- `.agents/Plans/2026-04-09__sourceharbor-W1-B-version-gap-closeout.md`

## 0.1 W2 Addenda

从 `2026-04-09` 开始，`W2` 已经拆成两份 addenda：

- `docs/blueprints/2026-04-09-reader-product-lane-split-contract.md`
- `docs/blueprints/2026-04-09-reader-product-intake-front-door-contract.md`

这两份 addenda 分别负责：

- lane-split addendum：
  - `Track Lane` / `Consume Lane` 的 runtime 边界
  - pending pool / batch assignment / close semantics
  - `manual` / `auto` consume guard
  - `W3` 后续应消费的稳定 batch entrance
- intake-front-door addendum：
  - `manual source intake`
  - direct URL / handle / 空间页 canonicalization
  - batch paste 前门
  - creator-level source vs item-level source 的 current nearest-runtime bridge

对应 closeout / handoff ledger：

- `.agents/Plans/2026-04-09__sourceharbor-W2-A-lane-split-closeout.md`
- `.agents/Plans/2026-04-09__sourceharbor-W2-B-intake-front-door-closeout.md`

当前 shared truth 应按下面口径理解：

- `W2-A` 已把 `Track / Consume`、pending pool、`ConsumptionBatch` 与 manual-auto guard 接进 runtime
- `W2-B` 已把 `manual source intake`、URL / handle / 空间页 canonicalization 与 batch paste 前门接进正式 contract 与实现
- `W3` 后续不再需要重复补 `W2`，而是直接消费这个稳定 batch + front-door entrance

## 0.2 W3 Addenda

从 `2026-04-09` 开始，`W3-A` 已经先落成一份 addendum：

- `docs/blueprints/2026-04-09-reader-product-cluster-judge-contract.md`

这份 addendum 负责：

- `Cluster Judge` 当前真实吃什么输入
- dominant topic-based clustering 规则
- `merge_then_polish` vs `polish_only` 的 first working 判决边界
- `ClusterVerdictManifest` 的最小持久化与 API surface

对应 closeout / handoff ledger：

- `.agents/Plans/2026-04-09__omega-P1-cluster-judge-closeout.md`

## 0.3 2026-04-11 Video-First Raw Stage Addendum

从 `2026-04-11` 开始，视频类 `RawReaderDocument` 的底层 contract 再抬一档：

- 默认模式改为 `advanced`
- `economy` 只作为显式省 token 选项
- 小模型预处理层正式进入 `S2 初步解读阶段`
- 高级模式必须强制第二轮 Gemini 审稿
- 视频链必须 `fail-close`

这里最容易搞混的点，要先说清楚：

- 字幕
- 评论区
- metadata
- 抽帧

这些现在都仍然有价值，但它们只算**辅助证据层**，不再允许单独冒充“视频本体已经被理解”。

### 0.3.1 新的模式合同

#### `advanced`（默认）

1. 先用较轻模型读取：
   - 字幕
   - 评论区
   - metadata
2. 产出：
   - 初步结构
   - Raw 大纲
   - signal / risk 提示
3. 再让主模型读取：
   - 视频本体
   - 字幕 / metadata / 评论区
   - 上一步产出的预处理大纲
4. 产出第一版 raw digest
5. 强制第二轮 Gemini 审稿，再次带上视频本体与第一版草稿，补缺、修漏、压缩 unsupported claim

#### `economy`

- 不跑小模型预处理
- 不跑第二轮审稿
- 但主模型仍必须把**视频本体**作为 primary input 读取

### 0.3.2 新的 fail-close 边界

对视频类 `SourceItem`，以下情况不再允许以“degraded success”混过去：

- 没拿到视频文件 / 视频本体输入
- 主模型从 `video_text` 静默退到 `frames_text`
- 主模型从 `video_text` 静默退到 `text`
- 高级模式的第二轮审稿没有发生
- 高级模式第二轮审稿发生了，但再次没有真正吃到视频本体

说得更直白一点：

> 以后“还能写出一份摘要”不等于“这条视频 Raw 已达标”。
> 对视频内容，**吃到视频本体** 才是合格线。

### 0.3.3 当前 repo 内的最小落点

本 addendum 在当前 repo 的最小 contract 落点是：

- canonical override key = `overrides.llm.analysis_mode`
- 允许值：
  - `advanced`
  - `economy`
- artifact proof 需要额外写回：
  - primary/review 实际使用的 `media_input`
  - preprocess / review 是否真的发生
  - `video_contract_satisfied`

## 1. 产品一句话定义

`SourceHarbor` 的下一阶段目标是：把多源长内容 intake 先落成高保真单信息源文档，再按主题无损合并/润色成面向读者的阅读成品，并通过 reader-first 首页、详情页与导航日报交付给用户。

说得更直白一点：

- 现在的 repo 更像“operator-core + reader surfaces”
- 新阶段要把它收成“reader primary, operator backstage”

## 2. 为什么 Reader-First

reader-first 不是 cosmetic cleanup，而是产品主语变化。

### 当前问题

- 当前 Web 已有 `/feed`、`/briefings`、`/trends` 等阅读面，但 canonical framing 仍偏 operator command center。
- 当前 watchlists/trends/briefings 更像聚合对象 view，不是真正的读者成品层。

### 新原则

- `operator console` 负责配置、诊断、控制
- `reader` 负责消费、理解、回看、追踪
- 首页主语应该是 `PublishedReaderDocument`，而不是 jobs/runs/cards

## 3. 五层 / 八对象模型

### 五层产品心智

| 层 | 对象主语 | 解释 |
| --- | --- | --- |
| `L1` | `SubscriptionSource` | 一个持续产出更新的源头，比如一个 UP 主、一个 channel、一个 feed |
| `L2` | `SourceItem` | 订阅源在某个时点产出的一条更新，比如一个视频、一篇文章 |
| `L3` | `RawReaderDocument` | 对单个信息源做高保真抽取后得到的单源文档 |
| `L4` | `PublishedReaderDocument` | 面向读者的最终成品，可以是 merge 后的，也可以是单身 polish 后的 |
| `L5` | `NavigationBrief` | 对当天成品层做 30 秒导航，不承担正文职责 |

### 八个核心对象

| 对象 | 层级 | 作用 |
| --- | --- | --- |
| `SubscriptionSource` | `L1` | 用户长期订阅的源头 |
| `SourceItem` | `L2` | 一条具体更新 |
| `RawReaderDocument` | `L3` | 单信息源高保真文档 |
| `ConsumptionBatch` | `L3-L4 bridge` | 一次冻结消费批次，保证 LLM 吃的是封口集合 |
| `ClusterVerdictManifest` | `L3-L4 bridge` | AI 判官对一批 `RawReaderDocument` 的聚类判决书 |
| `PublishedReaderDocument` | `L4` | 面向读者的正式阅读对象 |
| `CoverageLedger` | `L4 audit` | 记录每个输入 item 的 topic/claim 是否被覆盖 |
| `NavigationBrief` | `L5` | 导航日报，只回答“今天该读什么” |

说明：

- `Traceability` 在本蓝图里不是单独第九个业务对象，而是 `PublishedReaderDocument` 的 companion payload，由 `Traceability Packer` 生成并供 drawer /审计消费。

## 4. `SubscriptionSource` vs `SourceItem`

这两个概念必须彻底分开。

| 对象 | 它是什么 | 不是什麼 |
| --- | --- | --- |
| `SubscriptionSource` | 一个持续提供更新的源，比如一个 B 站 UP 主、一个 YouTube channel、一个 RSS feed | 不是一次具体内容 |
| `SourceItem` | 这个源头在某个时间点产生的一条更新，比如一个视频、一篇文章 | 不是整个订阅源 |

冻结结论：

- merge 的最小输入单位是 `SourceItem`
- 不按订阅源合并，只按主题合并
- 同一订阅源一天发两条同主题内容，也可以一起进入同一 cluster

## 5. `RawReaderDocument` vs `PublishedReaderDocument`

### `RawReaderDocument`

这是“单信息源高保真提取层”。

它应该至少包含：

- 单源 Markdown 主文
- `transcript`
- `comments`
- `frames`
- `outline`
- `meta`
- 结构化 topic/claim 摘要

它的职责像做菜前的“备料盘”：

- 保真
- 细
- 不怕原始
- 给下游 AI 继续吃

### `PublishedReaderDocument`

这是“最终给人读的成品层”。

它可能来自：

- `merge_then_polish`
- `polish_only`

但展示层不区分它的出生方式。对读者来说，都是可阅读文章。

它应该具备：

- stable key
- version
- readable Markdown/富渲染正文
- section-level drawer entry points
- yellow warning state when `published_with_gap = true`

## 6. `Track Lane` vs `Consume Lane`

### `Track Lane`

作用：

- 自动发现新 `SourceItem`
- 更新待消费池
- 做轻量 metadata enrichment

不能做：

- 偷跑全文 AI 消费
- 来一条 item 就起一次 merge/polish 大流水线

冻结默认值：

- polling interval = `15 minutes`

### `Consume Lane`

作用：

- 冻结一个批次
- 跑 `Stage 1-5`
- 产出面向读者的成品层

冻结默认值：

- default = `manual`
- auto mode = optional
- cooldown = `60 minutes`

当前 runtime addendum：

- `docs/blueprints/2026-04-09-reader-product-lane-split-contract.md`

### 关键原则

系统必须是：

- `time-window driven`
- `incremental re-judge`
- `affected-cluster rebuild`

而不是：

- 来一条就临时 patch 整篇全文

## 7. `ConsumptionBatch` / `window_id` / versioning

### `window_id`

冻结默认值：

- 时间窗口按 `user timezone natural day`
- 跨天热点先按 `one snapshot per day`

`W1-B` 之后，`window_id` 的 exact string format、timezone suffix 规则、以及 `cutoff_at` contract 已正式冻结在：

- `docs/blueprints/2026-04-09-reader-product-version-gap-contract.md`

例如：

- `2026-04-08@America/Los_Angeles`

### `ConsumptionBatch`

每次消费都必须冻结这些字段：

- `consumption_batch_id`
- `window_id`
- `cutoff_at`
- `source_item_ids`
- `base_published_doc_versions`

作用：

- 把 LLM 的输入集合锁住
- 防止 11:30 / 11:40 新到 item 污染 10:06 的 batch

### versioning

`PublishedReaderDocument` 需要：

- human-readable stable key，例如 `topic-openclaw-2026-04-08`
- internal UUID
- monotonically increasing version，例如 `@v1`, `@v2`

增量策略冻结为：

- 新 item 到来后，不在旧正文上乱 patch
- 对受影响 cluster 做整篇重建
- 再重跑 polish
- 已发布对象保留 stable key，version 递增

## 8. Stage 1-5 输入输出

| Stage | 作用 | 必须消费的输入 | 输出 |
| --- | --- | --- | --- |
| `Stage 1. Source Extractor` | 单信息源高保真落地 | `SourceItem` 基础元数据、媒体/正文、字幕、评论、截图、locale/style config | `RawReaderDocument` + 副产物 |
| `Stage 2. Cluster Judge` | 判哪些 merge，哪些单身 | 当前 batch 的全部 `RawReaderDocument`、topic/claim 摘要、当前 `window_id`、旧文档摘要与成员账本 | `ClusterVerdictManifest` |
| `Stage 3. Merge Writer` | 把一个 cluster 重写成一篇合并稿 | cluster 全部底层 `RawReaderDocument` 及其 transcript/comments/frames/outline/digest、旧版本 PublishedDoc、旧 CoverageLedger | `MergedDraftDocument` |
| `Stage 4. Polish Writer` | 把草稿打磨成正式阅读成品 | merge 草稿或单身 raw doc、`reader_output_locale`、`reader_style_profile`、traceability companion payload | `PublishedReaderDocument` |
| `Stage 5. Navigation Brief Writer` | 生成导航日报 | 当天全部 `PublishedReaderDocument`、主题标签、novelty/read-time/priority | `NavigationBrief` |

## 9. `Coverage Auditor` / `Traceability Packer` / `Repair Writer`

### `Coverage Auditor`

职责：

- 检查每个 `SourceItem` 的 topic/claim 是否被最终文档覆盖
- 检查不同来源独有信息是否被 merge 冲没

冻结默认值：

- repair budget `<= 2`

### `Traceability Packer`

职责：

- 生成 section-level source contribution map
- 生成 UI drawer 需要的展开数据
- 生成内部审计锚点

冻结默认值：

- repair budget `<= 1`

### `Repair Writer`

职责：

- 读取 `GapReport`
- 只做缺口 section 的补丁式修复
- 不允许自由全文重写

冻结默认值：

- 允许新增 section，但只允许新增 `GapReport` 指明缺失主题的 section
- 默认优先 `patch/section repair`
- 明确禁止 blind full regeneration

## 10. `published_with_gap`

当 repair 超过预算，或者仍有覆盖/溯源缺口时，系统不能假装完美。

冻结策略：

- 文档仍然可读
- UI 显示 yellow warning
- 读者能继续阅读
- 系统明确说明“当前存在 coverage / traceability gap”

`W1-B` 之后，`published_with_gap` 的进入/退出条件、yellow warning minimum payload、以及 repair escalation rules 已正式冻结在：

- `docs/blueprints/2026-04-09-reader-product-version-gap-contract.md`

默认文案风格：

- 明确提醒
- 不要过度委婉

## 11. `manual source intake`

`manual source intake` 必须是一等公民，而不是临时后门。

这意味着目标状态下应支持：

- URL 直贴
- handle / 空间页解析
- 批量手动 source 注入

当前 repo truth：

- 已有强支持视频模板 + 泛化 RSSHub/RSS intake substrate
- 已有 formal `manual source intake` 前门：creator-level 输入默认落 `SubscriptionSource`，direct video URL 默认走 current one-off lane
- 但 generic article detail URL one-off，以及 `manual_injected SourceItem -> ConsumptionBatch -> PublishedReaderDocument` 的统一主链仍留给 `W3+`

## 12. i18n / `reader_output_locale` / `ui_locale` / `reader_style_profile`

语言与风格必须拆开。

### 冻结配置位

| 配置 | 作用 |
| --- | --- |
| `ui_locale` | 控制界面语言 |
| `reader_output_locale` | 控制最终文档语言 |
| `reader_style_profile` | 控制文风与阅读呈现偏好 |

### reader style profile 例子

- `teaching`
- `briefing`
- `executive`
- `deep-study`

可细化的偏好包括：

- emoji density
- table preference
- analogy preference
- screenshot density
- citation drawer default openness

## 13. 当前 repo 已做到 / 部分做到 / 未做到

### 已做到

- 真实 intake substrate
- formal `manual source intake` 前门与 creator/item 分流 contract
- first-cut `Cluster Judge` / `ClusterVerdictManifest` runtime + API surface
- 单信息源 artifacts/digests 链
- watchlists/trends/briefings/ask compounder surfaces
- story-aware Ask 与 Briefings 的 shared story payload
- builder-facing Web/API/MCP/CLI/SDK surfaces

### 部分做到

> Historical note:
> this blueprint still records the first-cut gap picture from 2026-04-08.
> Current code truth has already moved ahead on several fronts, including
> `PublishedReaderDocument` routes/pages, yellow-warning/frontstage delivery,
> and the new `/feed -> current reader edition` bridge.
> Use this section as historical contract context, not as current live truth.

- reader surfaces 已存在，但 canonical framing 仍偏 operator
- `Cluster Judge` 当前已能基于 knowledge-card topic 做 first-cut theme-first grouping，但还没有接入旧 published-doc 摘要 / old coverage ledger / affected-cluster rebuild
- merged story 仍主要是 view-level aggregation，不是 `PublishedReaderDocument`
- direct video one-off input 已有 current nearest-runtime bridge，但 `manual_injected SourceItem -> ConsumptionBatch -> PublishedReaderDocument` 主链仍未完成
- notifications / reports / live-smoke / computer-use / Gemini review 的 strongest proof 仍受外部门槛影响

### 未做到

- 真正的 `Merge Writer`
- 真正的 `Polish Writer`
- `PublishedReaderDocument` 正式对象层
- `CoverageLedger`
- traceability companion payload 的正式 contract
- reader-first 首页 /详情页 / yellow warning 成品层
- watchlists/trends/briefings/published docs 的 MCP 一等工具面

## 14. 明确不属于当前 claim 的内容

以下内容不能被新蓝图写成 current truth：

- hosted workspace
- autopilot shipped capability
- live external notification proof
- 全 RSSHub universe route-by-route validation
- official registry / marketplace 已 everywhere read-back 完成

## 15. 本蓝图与 legacy vocabulary 的关系

本蓝图是 **2026-04-08 reader-product reset**。

它不是：

- legacy `Mainline A/B`
- legacy `Wave A-F`
- legacy `Wave 0-4`
- legacy `Prompt 5-8`

后续引用时必须显式写清：

- `W0-W5` 指本蓝图坐标系
- 与旧 program 只存在历史参考关系，不存在续号关系
