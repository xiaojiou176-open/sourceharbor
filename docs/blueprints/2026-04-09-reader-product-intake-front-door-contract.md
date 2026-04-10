# 2026-04-09 Reader Product Intake Front Door Contract

状态：`W2-B` canonical intake front-door contract。
用途：冻结 `manual source intake`、direct URL / handle / 空间页输入、batch paste、以及它们如何接入 `SubscriptionSource` 与 `manual_injected SourceItem` 世界。
边界：本文是 **target contract + current nearest-runtime bridge**，不是 `W2-A lane split / ConsumptionBatch` 主实现，不替代 `W1-A/W1-B` 对对象与版本语义的上游真理源。

依赖先读：

- `AGENTS.md`
- `docs/start-here.md`
- `docs/architecture.md`
- `docs/project-status.md`
- `docs/testing.md`
- `.agents/Tasks/TASK_BOARD-4月8日-阅读器产品与无损合并主线.md`
- `docs/blueprints/2026-04-08-reader-product-system-blueprint.md`
- `docs/blueprints/2026-04-09-reader-product-object-contract.md`
- `docs/blueprints/2026-04-09-reader-product-version-gap-contract.md`
- `.agents/Plans/2026-04-09__sourceharbor-W1-A-object-contract-closeout.md`
- `.agents/Plans/2026-04-09__sourceharbor-W1-B-version-gap-closeout.md`

谁应先读我：

- `W2-A lane-split` worker
- `W3-A judge-and-manifest` worker
- `W3-B merge-and-polish` worker
- 任意要接 `/subscriptions`、manual intake、或 builder intake contract 的后续 worker

## 1. 本文职责与边界

这份文档解决的不是“今天前端多了一个输入框”，而是：

> 当用户直接贴进一堆 URL / handle / 创作者空间页时，系统到底把这些输入当成什么、默认落到哪条路、失败时怎么诚实返回、以及哪些事情还必须留给 `W2-A`。

说得更直白一点：

- `Subscription Intake` 像办长期会员卡
- `Manual Source Intake` 像临时把一堆今天就想看的资料塞进阅读流
- 这两条路最终都要接到同一个 reader-product 世界
- 但它们不能被糊成同一件事

本文负责冻结：

1. `Subscription Intake` vs `Manual Source Intake` 的角色分工
2. direct URL / handle / 空间页 / batch paste 的支持边界
3. canonicalization contract
4. partial success / partial failure 的 batch 语义
5. `manual_injected SourceItem` 的最小入口语义
6. current runtime 能诚实承接到哪一步
7. 与 `W2-A lane split / batch freeze` 的清晰边界

本文明确不做：

- `Track Lane / Consume Lane` runtime split
- `ConsumptionBatch` 真实存储与生命周期实现
- `manual_injected` DB model 正式落地
- article direct-item one-off runtime
- `W3` judge / merge / polish 实现
- reader 首页 / yellow warning UI / MCP published-doc surface

## 2. 与 `W1-A / W1-B` Contract 的关系

`W1-A` 已经冻结：

- `SourceItem.source_origin = subscription_tracked | manual_injected`
- `manual_injected SourceItem` 进入消费层后与订阅流一视同仁
- `manual_injected` 不要求先绑定 `SubscriptionSource`

`W1-B` 已经冻结：

- `window_id`
- `cutoff_at`
- `ConsumptionBatch`
- `published_with_gap`
- yellow warning
- `TraceabilityPack`

因此 `W2-B` 在这里**不能**回头重定义这些上游合同。它只负责回答：

- 哪些输入先落成 `SubscriptionSource`
- 哪些输入先落成 `manual_injected SourceItem`
- 哪些输入当前必须被拒绝
- 前门输入如何对后续 `W2-A / W3` 保持诚实

## 3. `Subscription Intake` vs `Manual Source Intake`

### 3.1 `Subscription Intake`

它是什么：

- 长期、持续、会被后续 Track Lane 自动轮询的 source identity
- 适合 creator page、channel、space page、feed、RSSHub route

它不是什么：

- 不等于“今天只想读一次”的 one-off item
- 不等于 direct video/article detail URL

### 3.2 `Manual Source Intake`

它是什么：

- 用户临时贴进来、现在就想让系统处理的输入集合
- 可以是一条，也可以是一批
- 其目标不是“先存长期订阅”，而是“先把内容接进今天的消费世界”

它不是什么：

- 不是测试后门
- 不是 subscription-only 的换壳 UI
- 不是要求用户先想清楚订阅源身份

### 3.3 当前默认分流原则

冻结默认值：

| 输入形态 | 默认落点 | 解释 |
| --- | --- | --- |
| creator-level source（YouTube `@handle` / channel URL / Bilibili 空间页 / RSSHub route / feed URL） | `SubscriptionSource` | 这类输入天然是“以后还会继续更新”的源头 |
| item-level source（YouTube/Bilibili 具体视频 URL） | `manual_injected SourceItem` | 这类输入天然是“这条内容我现在就想读” |
| 无法诚实归类的 raw URL | `unsupported` | 不准假装系统已经支持 |

## 4. Supported Input Forms

### 4.1 当前这轮正式支持的 front-door 输入

| 输入形态 | 例子 | 默认动作 | 当前 runtime bridge |
| --- | --- | --- | --- |
| YouTube channel ID | `UCxxxxxxxx` | 保存订阅 | upsert `SubscriptionSource` |
| YouTube `@handle` | `@MindAmend` / `https://www.youtube.com/@MindAmend` | 保存订阅 | upsert `SubscriptionSource`，route=`/youtube/user/@MindAmend` |
| YouTube channel URL | `https://www.youtube.com/channel/UC...` | 保存订阅 | upsert `SubscriptionSource` |
| YouTube video URL | `https://www.youtube.com/watch?v=...` / `https://youtu.be/...` / `/shorts/...` | 加入 today | 走现有 `/api/v1/videos/process` one-off lane |
| Bilibili UID | `13416784` | 保存订阅 | upsert `SubscriptionSource` |
| Bilibili 空间页 URL | `https://space.bilibili.com/13416784` | 保存订阅 | 先提 UID，再 upsert `SubscriptionSource` |
| Bilibili 视频 URL / b23 短链 | `https://www.bilibili.com/video/BV...` / `https://b23.tv/...` | 加入 today | 走现有 `/api/v1/videos/process` one-off lane |
| RSSHub route | `/36kr/newsflashes` | 保存订阅 | upsert `SubscriptionSource` |
| Generic RSS/Atom feed URL | `https://example.com/feed.xml` | 保存订阅 | upsert `SubscriptionSource` |
| 多条混合输入 | 多行 paste | 按行独立分流 | 允许部分成功、部分失败 |

### 4.2 当前明确不支持的 direct-item 输入

| 输入形态 | 当前状态 | 为什么不能假装支持 |
| --- | --- | --- |
| 通用 article detail URL | `unsupported` | repo 当前没有 generic article one-off processing runtime |
| “靠 URL 自动还原所有 creator identity” 的任意网站页 | `unsupported` | 当前只有 YouTube/Bilibili/RSSHub/feed 这几类前门规则 |
| 未知 host 的 raw URL | `unsupported` | 既没有可信 canonicalization，也没有安全的一次性处理链 |

## 5. Canonicalization Contract

### 5.1 总原则

canonicalization 不是让用户记内部字段，而是把“人类自然会贴进来的东西”收成系统能认的稳定键。

但系统必须诚实：

- 只对当前真的能认的形态做 canonicalization
- 认不出来就明确拒绝
- 不准把原始 URL 盲拼成 route

### 5.2 YouTube 规则

| 输入 | canonical source_type | canonical source_value | derived route |
| --- | --- | --- | --- |
| `UC...` | `youtube_channel_id` | 原值 | `/youtube/channel/{id}` |
| `@handle` | `youtube_user` | `@handle` | `/youtube/user/{@handle}` |
| `/channel/UC...` URL | `youtube_channel_id` | `UC...` | `/youtube/channel/{id}` |
| `/@handle` URL | `youtube_user` | `@handle` | `/youtube/user/{@handle}` |
| `/user/{name}` / `/c/{name}` URL | `youtube_user` | `{name}` | `/youtube/user/{name}` |
| watch / shorts / youtu.be 视频 URL | item-level，不转 subscription | 不生成 source identity | 加入 today |

### 5.3 Bilibili 规则

| 输入 | canonical source_type | canonical source_value | derived route |
| --- | --- | --- | --- |
| UID 数字 | `bilibili_uid` | 原值 | `/bilibili/user/video/{uid}` |
| `space.bilibili.com/{uid}` URL | `bilibili_uid` | `{uid}` | `/bilibili/user/video/{uid}` |
| `/video/BV...` / `b23.tv/...` | item-level，不转 subscription | 不生成 source identity | 加入 today |

### 5.4 Generic 规则

| 输入 | canonical source_type | canonical source_value | derived route / adapter |
| --- | --- | --- | --- |
| RSSHub route（以 `/` 开头） | `rsshub_route` | 原值 | `adapter_type=rsshub_route`，`rsshub_route=原值` |
| feed URL | `url` | 原值 | `adapter_type=rss_generic`，`source_url=原值` |

### 5.5 失败语义

以下情况必须返回结构化失败，而不是偷偷猜：

- 不能从 Bilibili 空间页里提到 UID
- YouTube URL 既不是 creator page，也不是 direct video URL
- generic URL 看起来不像 feed，当前又没有 article one-off lane
- 输入为空、scheme 非 `http/https`、或命中 blocked host

## 6. Batch Paste Contract

### 6.1 最小语义

batch paste 的最小 contract 不是“把整段文本都丢给后端”，而是：

1. 一行一个输入
2. 空行跳过
3. 每行独立 canonicalize
4. 每行独立决定：
   - `save_subscription`
   - `add_to_today`
   - `unsupported`

### 6.2 部分成功原则

允许：

- 3 条 creator page 成功保存订阅
- 2 条 direct video URL 成功加入 today
- 1 条 article detail URL 被明确拒绝

这一批的整体返回必须告诉用户：

- 共处理了几条
- 新建了多少订阅
- 更新了多少订阅
- today 里排了多少条 one-off item
- 拒绝了多少条
- 每一条为什么被分到这条路

### 6.3 不做的事

这轮 batch paste **不**做：

- 整批 transactional all-or-nothing
- article detail URL 的自动 feed 发现
- 自动把 creator input 全部强制变成 today item

## 7. `manual_injected SourceItem` Contract

### 7.1 目标语义

上游合同已经冻结：

> `manual_injected SourceItem` 和 `subscription_tracked SourceItem` 在进入消费层后必须一视同仁。

### 7.2 当前 nearest-runtime bridge

在 current repo truth 里，这个目标语义目前只能通过最接近的运行时桥来承接：

| 目标语义 | 当前 nearest runtime bridge | 说明 |
| --- | --- | --- |
| manual one-off video item | `/api/v1/videos/process` | 这条链已经存在，能让 direct video URL 进入 jobs/videos/feed 侧现有 runtime |
| manual one-off article item | 尚无正式桥 | 当前必须诚实返回 unsupported |

### 7.3 这轮的正式承诺

这轮不是把 `manual_injected` DB object 全部落库，而是先把前门和 contract 钉住：

- direct video URL 可以不经 `SubscriptionSource` 就进入 current one-off processing lane
- creator page / feed 输入默认进 `SubscriptionSource`
- 后续 `W2-A / W3` 要做的，是把这条 front door 真正接成 `manual_injected SourceItem` + `ConsumptionBatch`

## 8. 与 `W2-A lane split` 的边界

`W2-B` 负责：

- intake front door
- URL / handle / 空间页 canonicalization
- batch paste 入口
- manual vs subscription 的分流 contract

`W2-A` 负责：

- `Track Lane / Consume Lane` runtime split
- `ConsumptionBatch` create / freeze / close
- auto consume cooldown wiring
- consume guard / batch lifecycle

一句话：

> `W2-B` 决定“门口怎么认人”；
> `W2-A` 决定“进门后怎么分车道、怎么锁批次”。

## 9. Current Code Anchor Table

### 9.1 当前 intake 前门证据表

| 面向 | 当前锚点 | 读法 |
| --- | --- | --- |
| `/subscriptions` 页面 | `apps/web/app/subscriptions/page.tsx:168-199, 539-671` | 当前真实 front door，同时拉 subscriptions + template catalog，并挂 guided editor |
| current server action | `apps/web/app/subscriptions/actions.ts:30-82` | 当前只有 subscription-style upsert action，没有 manual batch intake action |
| Web schema | `apps/web/app/action-security.ts:208-219` | 当前 Web side 只接受单条 subscription payload |
| current batch panel | `apps/web/components/subscription-batch-panel.tsx:396-667` | 现有“批量”只针对已有 subscriptions 的分类/删除 |

### 9.2 template catalog / source-value 处理链证据表

| 面向 | 当前锚点 | 读法 |
| --- | --- | --- |
| template catalog config | `config/source-templates/subscriptions.intake_templates.json:20-97` | 只有 4 个 template；YouTube/Bilibili 还是 creator/source-level 模板 |
| template catalog loader | `apps/api/app/services/subscription_templates.py:14-51, 70-99` | loader 只做静态规范化，不做 parser |
| API request/response | `apps/api/app/routers/subscriptions.py:23-33, 115-137, 169-196` | 当前公开 contract 仍是 single-entry subscription upsert |
| service normalization | `apps/api/app/services/subscriptions.py:61-138, 159-201` | URL 校验、adapter 分流、route synthesis 都在这里 |
| repo identity key | `apps/api/app/repositories/subscriptions.py:33-155` | 当前 canonical source identity 还是 `(platform, source_type, source_value)` |
| DB truth | `apps/api/app/models/subscription.py:21-56` | `SubscriptionSource` 最近邻字段 |

### 9.3 URL / handle / 空间页 canonicalization 邻近实现表

| 面向 | 当前锚点 | 解释 |
| --- | --- | --- |
| item-level video parsing | `apps/api/app/services/videos.py:44-104` | 已有 direct video URL 解析，但它属于 `SourceItem/Video` 级 |
| worker item normalizer | `apps/worker/worker/rss/normalizer.py:53-79` | worker 侧也只是在抽 item identity，不是在解 creator source identity |
| feed adapter bridge | `apps/worker/worker/rss/adapters.py:67-135` | 只把 route/source_url 变成 feed_url，发生在 canonicalization 之后 |
| source name fallback | `apps/api/app/services/source_names.py:44-78` | 适合 canonicalization 成功后的显示名 fallback |

### 9.4 manual source injection / batch paste 负搜索证据表

命令：

```bash
rg -n "manual_injected|subscription_tracked|add_to_today|batch paste|manual source intake|multiple urls|youtube.*handle parser|space\\.bilibili\\.com.*uid" apps contracts config packages
```

当前结果（formal implementation 面）：

- `manual_injected`：no hits
- `subscription_tracked`：no hits
- `add_to_today`：no hits
- 多 URL intake schema：no hits
- Bilibili space-page -> UID parser：no hits
- YouTube handle parser：no hits

解释：

- 这些语义已经在 `W1/W2` 文档层被冻结
- 但在 current runtime / contracts / config 里还没长成正式实现

## 10. Negative Search / Absent Runtime Object Evidence

当前 repo 里还不存在：

1. 正式 `manual_injected` runtime object
2. 独立 `Add To Today` API/front-door route
3. 多 URL / mixed-source manual intake payload
4. Bilibili 空间页 URL -> UID parser
5. YouTube `@handle` / `/user/` source-level parser
6. generic article detail URL one-off runtime

这意味着 `W2-B` 这轮要做的是：

- 把 creator-level input 和 item-level input 分账
- 把 formal front door 建出来
- 用现有 one-off video lane 做 current nearest bridge

而不是假装 `manual_injected` 已经全量 runtime 化。

## 11. What Remains For `W3`

`W2-B` 做完后，仍明确留给 `W3` 的内容：

1. `Cluster Judge`
2. `Merge Writer`
3. `Polish Writer`
4. `CoverageLedger`
5. `TraceabilityPack` 生产器
6. `manual_injected SourceItem` 真正进入 `ConsumptionBatch` / published-doc 主链

## 12. Explicit Non-Goals

本文明确不做：

- `W2-A` lane split runtime
- `ConsumptionBatch` 真实模型与状态迁移
- article detail URL 的 one-off processing engine
- `W3` judge / merge / polish runtime
- reader 首页 / detail page / yellow warning UI
- watchlists / trends / briefings / published-doc MCP surface

一句话收尾：

> `W2-B` 不是去把所有输入都“硬吃进去”，
> 而是去把用户最自然会贴进来的东西，先诚实地分成“长期订阅源”和“今天就想读的一次性 item”，并给后续 `W2-A / W3` 留下稳定、可继续实现的入口合同。
