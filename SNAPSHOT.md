# AI News Radar 项目快照

本文件记录个人部署的运行维护事件。初始本地复刻、GitHub Pages 和飞书配置见 `README.md` 的“本地复刻与个人部署记录”。

## 2026-07-14：飞书日报漏推送修复

### 故障现象

- 北京时间 05:40 的 `Send Feishu AI Daily` 由 `workflow_run` 自动唤醒，工作流结论显示为成功。
- 因运行时间早于 09:00，北京时间守门逻辑正常判定为跳过；`Send Feishu daily brief` 和 `Record Feishu delivery` 两个步骤实际均为 `skipped`。
- 09:00 后，`Send Feishu AI Daily` 和 `Update AI News Snapshot` 都没有收到 GitHub 的 `schedule` 事件，因此当天早上没有任何代码运行到飞书 webhook。

### 根因

- 直接原因是 GitHub Actions 没有投递当天上午的定时事件。GitHub 的 cron 可能延迟或漏触发，不保证准点执行。
- 2026-07-13 的修复增加了 `workflow_run` 兜底，但该兜底仍依赖 `Update AI News Snapshot` 先被定时唤醒。两个工作流共用同一个上游调度条件，不能覆盖“GitHub 完全没有投递 schedule”的情况。
- Actions 页面只显示工作流 `success` 容易造成误判；必须继续检查发送步骤是 `success` 还是 `skipped`。

### 修复内容

- 提交 `3bf51d9`：在 `.github/workflows/update-news.yml` 中新增 `send-daily-fallback` job。
- 新闻更新成功后，在同一次工作流内直接执行“检查北京时间和当天状态 → 发送飞书日报 → 写入发送状态”，不再依赖第二个工作流接棒。
- fallback 显式检出远端分支最新数据，避免发送工作流启动时的旧快照。
- 保留常规错峰更新 `17,47 * * * *`，并在 UTC 01:00–04:59（北京时间 09:00–12:59）增加 `7,27,37,57 1-4 * * *` 上午唤醒点。
- 保留独立的 `Send Feishu AI Daily` 工作流，形成两条自动发送路径。
- 发送成功后继续写入 `data/feishu-daily-state.json`，按北京时间日期去重。
- 提交 `ae556b5`：当 `update-news.yml` 自身发生推送时自动运行一次自检。该触发器只匹配工作流文件，不会被日常 `data/` 自动提交递归触发。

### 验证结果

- 本地完整测试：`134 passed`。
- `update-news.yml` 通过 YAML 解析和 diff 检查。
- GitHub Actions 自动运行：`29302033366`，事件类型为 `push`，不依赖手动 `Run workflow`。
- `update`、`Send daily fallback after snapshot update`、`Send Feishu daily brief`、`Record Feishu delivery` 均执行成功。
- 远端状态最终记录：`last_sent_date = 2026-07-14`，`last_sent_at_beijing = 2026-07-14 10:51:51 +0800`。

### 后续排查顺序

1. 先看当天 09:00 后是否出现 `schedule` 或其他自动事件；没有运行记录说明代码根本没有执行，不能先归因于飞书 webhook。
2. 工作流显示成功时，继续展开检查 `Send Feishu daily brief` 是 `success` 还是 `skipped`。
3. 检查 `data/feishu-daily-state.json` 的 `last_sent_date` 是否为当天；它是自动去重和发送闭环的最终标志。
4. GitHub Scheduler 本身没有准点 SLA。当前方案通过上午多次错峰唤醒、更新工作流内直发和独立日报工作流三层兜底降低漏发概率，但不能让未被 GitHub 投递的事件凭空运行。
