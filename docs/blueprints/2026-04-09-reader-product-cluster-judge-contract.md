# 2026-04-09 Reader Product Cluster Judge Contract

状态：`W3-A` canonical cluster-judge contract。
用途：冻结 `Cluster Judge` 如何从一个稳定 `ConsumptionBatch` 产出 `ClusterVerdictManifest`，以及它当前真实使用的证据源、分群规则、输出边界与诚实限制。
边界：本文记录的是 **当前已落地的 first working judge/manifest runtime**；它不是 `Merge Writer`、`Polish Writer`、`PublishedReaderDocument` 或 reader UI 已完成的声明。

依赖先读：

- `docs/blueprints/2026-04-09-reader-product-object-contract.md`
- `docs/blueprints/2026-04-09-reader-product-version-gap-contract.md`
- `docs/blueprints/2026-04-09-reader-product-lane-split-contract.md`
- `docs/blueprints/2026-04-09-reader-product-intake-front-door-contract.md`
- `.agents/Plans/2026-04-09__sourceharbor-W2-A-lane-split-closeout.md`
- `.agents/Plans/2026-04-09__sourceharbor-W2-B-intake-front-door-closeout.md`

## 1. 本文职责

这份文档解决的是：

> 给一批已经 freeze 的 `ConsumptionBatch`，
> 系统现在到底怎么判断哪些 item 应该 merge，哪些只做 `polish_only`。

说得更直白一点：

- `W2-A` 负责把货装进一辆车
- `W2-B` 负责把货从前门诚实地送进仓
- `W3-A` 才负责第一次看这车货，说“哪些应该合并写成一篇，哪些应该各写各的”

本文正式冻结：

1. `Cluster Judge` 的当前输入来源
2. dominant topic-based clustering 规则
3. `ClusterVerdictManifest` 的最小结构
4. `merge_then_polish` vs `polish_only` 的当前判定语义
5. 当前诚实边界

## 2. 当前输入来源

当前 judge 不靠凭空脑补，它吃的是这三类已有证据：

1. `ConsumptionBatch.items`
   - 提供稳定输入集合、`window_id`、`source_origin`、`job_id`
2. job digest markdown
   - 提供单源文档的最短可读摘要
3. job knowledge cards
   - 提供 `topic_key` / `topic_label` / `claim_kind`

换句话说：

> 现在的 judge 不是凭标题硬猜主题，
> 而是优先吃现有 knowledge-card 的 topic 语义；
> digest 只作为 preview 和后续 merge/polish 的邻近输入。

## 3. 当前判定规则

### 3.1 dominant topic rule

每个 source item 先从自己的 knowledge cards 里取：

- `topic_key`
- `topic_label`
- `claim_kind`

若一个 item 有多个 topic，当前规则取 **出现次数最多的 dominant topic** 作为当前 clustering key。

### 3.2 cluster vs singleton

冻结当前规则：

- 当同一 `topic_key` 在 batch 内命中 **2 个或以上** source item：
  - `decision = merge_then_polish`
  - 形成一个 merge-ready cluster
- 否则：
  - `decision = polish_only`
  - 该 item 落入 singleton

### 3.3 fallback rule

如果某个 item 没有可用 `topic_key`：

- 当前不假装它已经能被 theme-merge
- 直接按 singleton 处理

这条规则很重要，因为它让当前 runtime 先诚实，而不是为了凑 cluster 去编主题。

## 4. `ClusterVerdictManifest` Minimum Shape

当前 manifest 至少包含：

- `consumption_batch_id`
- `window_id`
- `status`
- `source_item_count`
- `cluster_count`
- `singleton_count`
- `clusters[]`
- `singletons[]`

其中：

- `clusters[]` 至少要有 `cluster_key`、`topic_key`、`topic_label`、`decision=merge_then_polish`、`source_item_ids[]`、`job_ids[]`、`claim_kinds[]`
- `singletons[]` 至少要有 `source_item_id`、`decision=polish_only`、`topic_key?`、`claim_kinds[]`

## 5. 当前 persistence / route surface

当前 judge 已经落到真实代码，并暴露出两条 API：

- `POST /api/v1/reader/batches/{batch_id}/judge`
- `GET /api/v1/reader/batches/{batch_id}/manifest`

持久化层：

- `cluster_verdict_manifests`

这意味着 current repo truth 已经不是“只在文档里说 judge”，而是：

> 给一个真实 batch，系统现在已经能写出一份可持久化、可回读的 manifest。

## 6. 当前诚实边界

这轮已经完成的，是：

- batch -> judge -> manifest
- dominant topic-based grouping
- merge-ready clusters 与 polish-only singletons 的 first working split

这轮还**没有**完成的，是：

1. `Merge Writer`
2. `Polish Writer`
3. `PublishedReaderDocument` materialization
4. `CoverageLedger`
5. `TraceabilityPack` 生产器

一句话收尾：

> `W3-A` 这轮不是把 reader 产品做完，
> 而是让系统第一次真正能对一批稳定 source items 给出可持久化的“合并判决书”。
