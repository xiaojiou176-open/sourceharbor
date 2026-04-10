# 2026-04-09 Reader Product Version And Gap Contract

状态：`W1-B` canonical version / gap contract。
用途：冻结 reader-product program 的时间语义、批次生命周期、版本规则、`published_with_gap` 规则、yellow warning、`TraceabilityPack` companion payload、以及增量重判/重建 contract；供 `W2 ~ W5` 直接引用。
边界：本文是 **target contract addendum**，不是 current capability claim；不替代 [2026-04-08-reader-product-system-blueprint.md](./2026-04-08-reader-product-system-blueprint.md) 的系统总图，也不回滚 [2026-04-09-reader-product-object-contract.md](./2026-04-09-reader-product-object-contract.md) 已冻结的对象边界。

依赖先读：

- `AGENTS.md`
- `docs/start-here.md`
- `docs/architecture.md`
- `docs/project-status.md`
- `docs/testing.md`
- `.agents/Tasks/TASK_BOARD-4月8日-阅读器产品与无损合并主线.md`
- `docs/blueprints/2026-04-08-reader-product-system-blueprint.md`
- `docs/blueprints/2026-04-09-reader-product-object-contract.md`
- `.agents/Plans/2026-04-09__sourceharbor-W1-A-object-contract-closeout.md`
- `.agents/Plans/2026-04-08__sourceharbor-reader-product-wave-program.md`
- `.agents/Plans/2026-04-08__sourceharbor-reader-product-context-index.md`

谁应先读我：

- `W2` worker
- `W3-A cluster-judge` worker
- `W3-B merge-polish` worker
- `W4/W5` 所有要处理 warning、drawer、repair、proof 的 worker

## 1. 本文职责与边界

`W1-A` 解决的是“世界里有哪些对象”。
`W1-B` 解决的是“这些对象怎么按时间切片、怎么编号、怎么增量重算、什么时候必须黄标、drawer 到底最少吃什么 payload”。

说得更直白一点：

- `W1-A` 像把房间和门牌号的存在性钉死
- `W1-B` 像把楼层编号、刊期规则、缺口告示、增量修缮流程钉死

本文正式冻结：

1. `window_id` contract
2. `ConsumptionBatch` lifecycle contract
3. `PublishedReaderDocument stable key / internal UUID / version` contract
4. `published_with_gap` contract
5. yellow warning contract
6. `TraceabilityPack` companion payload minimum schema
7. incremental judge / affected-cluster rebuild contract
8. `Patch Repair` / `Section Rebuild` / `Cluster Rebuild` 升级规则

本文明确不做：

- DB migration
- ORM / API / MCP / UI runtime implementation
- Track/Consume runtime split code
- Cluster Judge / Merge Writer / Polish Writer / Repair Writer 实现
- yellow warning UI 视觉实现

## 2. 与 Object Contract 的关系

[2026-04-09-reader-product-object-contract.md](./2026-04-09-reader-product-object-contract.md) 已经冻结了：

- 8 个核心对象 + `TraceabilityPack` companion payload 定位
- definition / non-definition
- owner / producer / consumer / mutability
- minimum required fields
- minimum states

本文继续负责：

- `window_id` 最终格式
- `cutoff_at` 计算与 batch 冻结规则
- stable key / internal UUID / version 各自职责
- gap / yellow-warning / payload / rebuild 的最终语义

使用规则：

- 对象存在性与边界冲突：以 `W1-A object contract` 为准
- 时间 / 版本 / 缺口 / companion payload 细节冲突：以本文为准
- 低优先级 surface（task board / blueprint / later prompt）若与本文冲突，必须回写

## 3. `W1-B` 与 `W2` 的 Scope Split

| 主题 | `W1-B` 冻结什么 | `W2` 承接什么 |
| --- | --- | --- |
| 时间语义 | `window_id`、`cutoff_at`、batch lifecycle、同日增量如何进入旧文版本 | Track / Consume runtime split、scheduler / button wiring |
| 文档版本语义 | stable key、internal UUID、version bump、supersede/new-doc 边界 | runtime persistence、route / storage implementation |
| 缺口语义 | `published_with_gap` 进入/退出条件、yellow warning 最小语义 | UI / API / MCP 暴露 warning surface |
| traceability | `TraceabilityPack` minimum schema 与 drawer contract | payload 生成器与 UI/MCP 消费实现 |
| 增量重判 | judge 输入 contract、affected-cluster rebuild 边界 | actual incremental judge / merge pipeline |
| repair 升级 | patch / section / cluster rebuild 条件与版本交互 | Repair Writer runtime 与 lane orchestration |

一句话总结：

> `W1-B` 把“法律文本”钉死；
> `W2` 开始把这些法律接上运行时按钮、调度和入口。

## 4. `window_id` Contract

### 4.1 冻结结论

- 时间窗口按 **用户时区自然日** 切
- `window_id` 不是完整时间戳，而是 **date key + timezone suffix**
- canonical string format：
  - `YYYY-MM-DD@IANA_TZ`
  - 例：`2026-04-08@America/Los_Angeles`

### 4.2 `window_id` 计算基准

`window_id` 由 `source_effective_at` 推导：

1. 优先用 `SourceItem.published_at`
2. 若缺失，再回退到 `SourceItem.discovered_at`

原因：

- 如果只用 `discovered_at`，晚发现的早晨内容会错误漂到下一天
- 如果只用 `published_at`，又没法表达“今天 10:06 冻结时只吃到哪些 item”

所以正式规则是：

- `window_id` = `source_effective_at` 在用户时区映射到的自然日
- `cutoff_at` 决定 **这次 batch 到底吃到哪一刻已经被系统看见的 item**

### 4.3 与“每天一篇快照”的关系

- 跨天热点当前按 `one snapshot per day`
- 同一主题在同一 `window_id` 下可以多次出版本
- 跨天后默认是新的 `window_id`，因此是新的文档快照，不是旧 stable key 继续长大

## 5. `ConsumptionBatch` Lifecycle Contract

### 5.1 批次创建时机

每次 `Consume Lane` 启动时，必须先创建一个 `ConsumptionBatch`。

触发来源允许两类：

- `manual`
  - 用户显式点击 consume
- `auto`
  - 用户开启 auto consume，且满足最小 cooldown

auto/manual 的差异只在 `trigger_mode`，**不影响 batch 语义本身**。

### 5.2 `cutoff_at` 计算

- `cutoff_at` = batch 进入 `frozen` 的时刻
- 必须是 timezone-aware timestamp
- 推荐存储为 RFC 3339 / UTC 可逆 instant

候选 `SourceItem` 进入某次 batch，必须同时满足：

1. 它的 `window_id` 与本 batch 相同
2. 它已经在系统里被看见：
   - `discovered_at <= cutoff_at`

这条规则直接解决：

- `10:06` consume 一次
- `11:30` 又来 1 条
- `11:40` 又来 1 条

的边界情况。
`11:30` 和 `11:40` 的条目不会污染 `10:06` 的 batch，只会进入下一次 batch。

### 5.3 输入集合是否允许追加

- `ConsumptionBatch` 一旦进入 `frozen`，`source_item_ids` 不可追加
- 新条目只能进入下一次 batch
- 旧 batch 只允许状态前进，不允许输入集合回写

### 5.4 生命周期

| 状态 | 进入条件 | 退出条件 |
| --- | --- | --- |
| `frozen` | `window_id`、`cutoff_at`、`source_item_ids`、`base_published_doc_versions` 已锁定 | `Cluster Judge` 输出最终 manifest |
| `judged` | `ClusterVerdictManifest` 已定稿 | 所有受影响 published docs 已 materialize 成新版本 |
| `materialized` | 受影响 `PublishedReaderDocument`、warning state、`TraceabilityPack` companion payload、必要的 `CoverageLedger` 已写出 | audit/repair loop 结束，或 NavigationBrief lane 完成 |
| `closed` | 本批次不再产生新的 published-doc mutation | 完结态 |

## 6. `PublishedReaderDocument` Stable Key / UUID / Version Contract

### 6.1 三层身份的职责

| 标识 | 作用 | 是否人类可读 |
| --- | --- | --- |
| `stable_key` | 同一阅读快照对象的长期可读身份 | 是 |
| `published_doc_id` / internal UUID | 某个具体版本实例的内部唯一身份 | 否 |
| `version` | 同一 `stable_key` 下的单调递增版本号 | 半可读 |

### 6.2 `stable_key` 格式

冻结格式：

- 首选：`topic-{focus_slug}-{window_date}`
- 例：`topic-openclaw-2026-04-08`

补充规则：

- `stable_key` 默认不直接嵌入 IANA 时区字符串
- 时区语义由 `window_id` 负责，不再在 `stable_key` 上重复编码
- 当主题 slug 暂时不可稳定解析时，允许 fallback：
  - `item-{source_item_short_id}-{window_date}`

### 6.3 internal UUID 的角色

`published_doc_id` / internal UUID：

- 永远代表一个具体版本实例
- 供 DB row、artifact path、internal joins、future API/MCP payload 使用
- 不承诺给人类直接阅读，也不承诺跨版本不变

### 6.4 什么时候 bump version

同一 `stable_key` 下，只要以下任一变化发生，就必须 `version + 1`：

1. `source_item_ids` 变化
2. 文档正文内容变化
3. section 结构变化
4. `published_with_gap` / yellow warning 状态变化
5. `TraceabilityPack` companion payload 的 section/source/evidence mapping 变化

### 6.5 什么时候只是 supersede 旧版本

满足下面条件时，属于**同一文档的新版本**：

- `window_id` 不变
- 主题身份不变
- 新增内容只是同一主题在同一天的增量更新
- 或是同一 stable key 下的 repair / rebuild

此时：

- 旧版本进入 `superseded`
- 新版本沿用同一 `stable_key`

### 6.6 什么时候必须视为新文档

满足下面任一项时，必须是**新 stable key / 新文档**：

1. `window_id` 变化
2. 主题身份变化，且旧 `stable_key` 无法诚实继续代表新对象
3. 原先 fallback `item-*` 单篇在后续被确认应进入另一个不同主题 stable key

## 7. `published_with_gap` Contract

### 7.1 进入条件

以下任一条件成立时，允许进入 `published_with_gap`：

1. `Coverage Auditor` 仍检测到 coverage gap，且 repair 已超预算
2. `TraceabilityPack` 仍存在 traceability gap，且 repair 已超预算
3. 原始 extraction 明确 `degraded`，导致正文仍可读，但完整证据/覆盖链条不成立
4. `Patch Repair` / `Section Rebuild` 后正文可读，但仍无法诚实宣称完整覆盖

### 7.2 退出条件

`published_with_gap` **不原地改状态**。退出方式是：

- 生成同一 `stable_key` 的新版本
- 新版本通过 coverage + traceability checks
- 旧 gap 版本被 `superseded`

### 7.3 是否允许持续黄标迭代

允许。
也就是说：

- `topic-openclaw-2026-04-08@v2` 可以是 `published_with_gap`
- `topic-openclaw-2026-04-08@v3` 仍然可以是 `published_with_gap`

前提是：

- 每一版都诚实保留 warning state
- 不能把 warning 当成临时 UI 装饰，必须进入版本 contract

### 7.4 “可读但黄标”的最小 contract

只要文档对读者仍有价值，就允许发布，但必须同时满足：

1. 正文可阅读
2. warning 显式可见
3. gap 原因明确
4. 受影响范围可定位
5. drawer / evidence layer 可继续打开已有证据

## 8. Yellow Warning Contract

yellow warning 不是 CSS 效果，而是 contract 的一部分。

### 8.1 warning 面向谁

必须同时对两类消费者可理解：

- 人类读者
- agent / MCP / API consumer

### 8.2 最小语义字段

每个 yellow warning 至少要包含：

- `warning_kinds[]`
  - `coverage_gap`
  - `traceability_gap`
  - `repair_budget_exhausted`
  - `degraded_extraction`
- `summary`
- `affected_scope`
  - 受影响 section / source item count / coverage domain 的简述
- `version`
- `generated_at`

### 8.3 文案语气

冻结要求：

- 明确提醒
- 不使用“也许”“可能稍后更完整”这类过度委婉语气
- 对人类说人话，对 agent 给结构化字段

## 9. `TraceabilityPack` Companion Payload Minimum Schema

### 9.1 Companion payload 定位

`TraceabilityPack` 继续是 `PublishedReaderDocument` 的 companion payload，不升级为新的业务主对象。

### 9.2 minimum top-level fields

```json
{
  "published_doc_id": "uuid",
  "stable_key": "topic-openclaw-2026-04-08",
  "version": 3,
  "status": "ready|gap_detected",
  "section_contributions": [],
  "source_items": [],
  "evidence_routes": {},
  "warning_summary": null
}
```

### 9.3 section-level contribution map 最小字段

每个 `section_contributions[]` 元素至少包含：

- `section_id`
- `section_heading`
- `source_item_ids[]`
- `primary_source_item_ids[]`
- `claim_refs[]`
- `evidence_anchor_refs[]`

### 9.4 source item 引用最小字段

每个 `source_items[]` 元素至少包含：

- `source_item_id`
- `title`
- `platform`
- `source_url`
- `published_at`
- `job_id`
- `raw_artifacts`
  - `digest`
  - `transcript`
  - `comments`
  - `outline`
  - `frames`

### 9.5 evidence anchor 可达性要求

`timestamp / frame / quote` 不要求默认展开在主文，但必须在 payload 中可达。
最小可达方式允许：

- `evidence_anchor_refs[]`
- `evidence_routes.job_bundle`
- `evidence_routes.job_compare`
- `evidence_routes.job_knowledge_cards`

## 10. Incremental Judge / Affected-Cluster Rebuild Contract

### 10.1 第二个 batch 到来时，judge 必须吃什么

追加版 `Cluster Judge` 最少输入：

1. 新 `RawReaderDocument[]`
2. 旧 `PublishedReaderDocument` 摘要
3. 旧 cluster membership ledger
4. 旧 `CoverageLedger`

说明：

- 旧 `PublishedReaderDocument` 只作为“上一轮已产出什么”的摘要输入
- 真正重建时，writer 不能只吃旧成品文，必须回到底层 raw docs

### 10.2 什么叫 affected cluster

以下任一情况成立，该 cluster 视为 `affected`：

1. 新 `SourceItem` 被判入现有 stable key
2. 新证据导致现有 cluster 需要 split / merge / retitle
3. 当前 stable key 在同一 `window_id` 下仍处于 `published_with_gap`

### 10.3 affected-cluster rebuild 边界

affected-cluster rebuild 的正式规则：

- 不对旧正文做 blind patch
- 必须取该 cluster 的**全量 member raw docs**
- 重新跑 merge
- 再跑 polish

### 10.4 旧版本如何 supersede

- 同 stable key 的旧版本进入 `superseded`
- 新版本继承 stable key、提升 version
- 若 cluster identity 已变化到旧 stable key 不能诚实代表，则生成新 stable key，并在旧版本上记录 superseded / redirect metadata

## 11. Repair Level Transition Table

| Repair level | 触发条件 | 允许修改范围 | version interaction | 与 `published_with_gap` 的关系 |
| --- | --- | --- | --- | --- |
| `Patch Repair` | 某节缺一个 topic/claim、source contribution 漏挂、warning summary 不完整 | 只改 `GapReport` 指明的 section、warning metadata、companion payload 局部映射 | 同一 `stable_key`，`version + 1` | 修复后过审则回到 `published`；失败可继续黄标 |
| `Section Rebuild` | 某节结构错误或整节信息不足，但整篇主题与 stable key 仍成立 | 只重建指明 section；允许新增 `GapReport` 指明的缺失主题 section | 同一 `stable_key`，`version + 1` | 仍失败则进入/保留 `published_with_gap` |
| `Cluster Rebuild` | cluster membership 错、主题身份漂、coverage 结构性失败 | 重跑受影响 cluster 的 merge + polish；重新 materialize 全文 | 同 stable key `version + 1`；若主题身份变了则新 stable key | 失败但可读则 `published_with_gap`；不可读则不 materialize |

## 12. Current Code Anchor Table

### 12.1 时间语义邻近实现表

| 主题 | 当前锚点 | 读法 |
| --- | --- | --- |
| repo 统一时间戳 mixin | `apps/api/app/models/base.py:21-29` | 当前持久层普遍以 `created_at / updated_at` 为基础时间账本 |
| ingest-run lifecycle | `apps/api/app/models/ingest_run.py:13-60` | 当前最接近“批次”的对象是 `IngestRun`，有 `created_at / updated_at / completed_at / status`，但不是 consume batch |
| ingest-run item 时间字段 | `apps/api/app/models/ingest_run.py:69-124` | 当前 `IngestRunItem` 已有 `published_at / created_at / updated_at`，可作为 `SourceItem` 时间语义邻近锚点 |
| job 时间与 degrade 状态 | `apps/api/app/models/job.py:14-61` | 当前单 job 已有 `created_at / updated_at / pipeline_final_status / degradation_count` |
| internal evidence bundle 时间 | `apps/api/app/services/jobs.py:531-583` | 当前 evidence bundle 已区分 `generated_at`、job `created_at`、job `updated_at` |

### 12.2 版本 / identity 邻近实现表

| 主题 | 当前锚点 | 读法 |
| --- | --- | --- |
| current merged-story grouping | `apps/api/app/services/watchlists.py:741-815` | 当前 story aggregation 已有 `story_key`、`id`、`latest_created_at`，但还不是 `PublishedReaderDocument` |
| story key 解析 | `apps/api/app/services/watchlists.py:965-996` | 当前 `topic_key -> source_url -> card_title -> card_id` 的 fallback 说明 story identity 仍是 view-level、机械聚类键 |
| selected story payload | `apps/api/app/services/story_read_model.py:18-71` | 当前 `/briefings` 已有 server-owned `selected_story` payload、`selected_story_id`、`selection_basis` |
| selected story route contract | `apps/api/app/services/story_read_model.py:183-237` | 当前 page payload 已能带 `briefing / ask / compare / bundle / knowledge_cards` 路由 |

### 12.3 gap / degraded / warning 邻近实现表

| 主题 | 当前锚点 | 读法 |
| --- | --- | --- |
| artifact 写出失败可 degraded | `apps/worker/worker/pipeline/steps/artifacts.py:453-458` | 当前 pipeline 已有 `degraded=True` 这种“可继续但不完美”的邻近语义 |
| degradation 收集 | `apps/api/app/services/jobs.py:340-380` | 当前 jobs service 已把 failed/skipped/degraded step 汇总成 degradations |
| degraded status 变 warning | `apps/web/components/status-badge.tsx:30-39` | 当前前端已经把 `degraded` / `skipped` 归入 warning tone |
| ops 把 degraded/failed 拉进需要处理队列 | `apps/api/app/services/ops.py:366-420`, `apps/api/app/services/ops.py:600-680` | 当前 operator 面已承认 warning/critical 分层，但还不是 reader yellow warning contract |

### 12.4 traceability / evidence payload 邻近实现表

| 主题 | 当前锚点 | 读法 |
| --- | --- | --- |
| briefing evidence story payload | `apps/api/app/services/watchlists.py:594-639` | 当前已有 `story_id / story_key / topic_key / evidence_cards / routes`，是最接近 drawer payload 的邻近结构 |
| briefing routes | `apps/api/app/services/watchlists.py:672-725` | 当前 payload 已可跳 `briefing / ask / job_compare / job_bundle / job_knowledge_cards` |
| selected story page payload | `apps/api/app/services/story_read_model.py:55-71` | 当前 page payload 已把 `selection`、`selected_story`、`routes` 分层 |
| job evidence bundle | `apps/api/app/services/jobs.py:531-603` | 当前已有 internal evidence bundle：`trace_summary / digest / digest_meta / comparison / knowledge_cards / artifact_manifest / step_summary` |

## 13. Negative-Search / Absent-Runtime-Object Evidence

命令：

```bash
rg -n "ClusterVerdictManifest|PublishedReaderDocument|CoverageLedger|NavigationBrief|TraceabilityPack|published_with_gap|window_id|cutoff_at|manual_injected|subscription_tracked|consumption_batch_id" apps contracts config
```

结果：

- `exit 1`
- no hits

解释：

- 这些对象/字段已经在 `W0/W1` 文档层被命名
- 但在 current runtime / contracts / config 层还没有 first-class implementation
- 这恰好说明 `W1-B` 当前做的是 contract freeze，不是实现收口

## 14. What Remains For `W2`

`W2` 需要承接但本文不实现的内容：

1. Track / Consume runtime split
2. `ConsumptionBatch` 的真实创建与存储
3. manual source intake 的 UI/API/front-door
4. URL / handle / 空间页 canonicalization
5. auto consume cooldown wiring
6. batch creation button / automation hooks

## 15. Explicit Non-Goals

本文明确不做：

- 新增第九、第十个业务主对象
- 把 `TraceabilityPack` 升格成主对象
- 把 `watchlists / trends / briefings` 直接宣称成 `PublishedReaderDocument`
- runtime batch/judge/merge/polish/repair code
- yellow warning UI 视觉稿
- drawer 组件实现

一句话收尾：

> `W1-B` 的交付物不是“把阅读器做出来”，
> 而是确保后面所有人说的“这一篇是哪一版、为什么黄标、追加后该怎么重建”，指的是同一套法律。
