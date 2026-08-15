---
name: calendar-automation
description: Calendar定时任务与CodeAct脚本自动化模式。指导如何创建可靠的定时调度任务，包括Calendar工单编写、time_range弹性调度窗口设置、CodeAct脚本执行、结果通知与失败重试。当用户需要创建定时任务、周期性任务、自动化工作流、定时简报、定时监控时使用此技能。
---

# Calendar Automation — 定时任务自动化模式

将周期性任务（简报、监控、复盘、数据采集）通过 Calendar 日程 + 独立 session 脚本实现全自动执行。

## 标准架构

```
Calendar触发 → 独立session读取工单description → 脚本执行 → 结果返回主agent → 通知用户
```

## 一、Calendar 工单设计

### 1.1 summary（任务标题）
用清晰的动作短语，例如：
- ✅ "生成每日AI科技简报"
- ✅ "EvoMap资产健康检查"
- ❌ "任务" / "每日执行"

### 1.2 description（执行工单）
写给独立执行 session 看的完整工单，必须包含：

```markdown
## 任务目标
一句话说明要做什么、产出什么。

## 执行步骤
1. 加载XXX技能（skill_load: xxx）
2. 按技能指引执行...
3. 输出文件保存到 {路径}
4. 上传到项目文件空间

## 质量要求
- 具体的量化标准
- 文件大小/条数/格式要求

## 上下文
- 相关文件路径
- API认证方式
- 已知限制
```

**关键原则**：执行 session 没有主对话的记忆，所有关键信息必须写在 description 里。

### 1.3 dtstart（开始时间）
- 避免整点（00分），用非整点非半点（如 08:03、14:07）降低并发
- 用户明确指定时间则按用户指定
- 定时任务的 dtstart 同时是 rrule 的锚点

### 1.4 time_range（弹性调度窗口）
除时间严格敏感任务外都应设置：

| 场景 | 窗口 |
|------|------|
| 用户未指定时间 | ±30min |
| 指定大致时段 | ±10min |
| 指定具体时间 | ±5min |

```
time_range: {
  earliest_schedule_time: "202601010730",
  latest_schedule_time: "202601010830"
}
```

### 1.5 rrule（重复规则）

**常规重复只设 freq + interval**：
```python
# 每天
rrule = {"freq": "DAILY", "interval": 1}
# 每周一
rrule = {"freq": "WEEKLY", "interval": 1}
# 每月1号
rrule = {"freq": "MONTHLY", "interval": 1}
```

⚠️ 不要额外填 byhour/byminute/byday，除非用户明确要求复杂规则。这些字段与 dtstart 冲突会导致实例时间不一致。

**结束方式**：
- `count: N` — 重复N次后结束
- `until: "202612312359"` — 指定结束时间
- 不填 — 永久重复

## 二、执行脚本最佳实践

### 2.1 脚本位置
放在项目目录下的固定路径，如 `scripts/` 或 `codeact/scripts/`。

### 2.2 输出规范
脚本应：
1. 将结果写入文件（Markdown/JSON）
2. 在 stdout 打印简要摘要和文件路径
3. 退出码 0 表示成功，非 0 表示失败

### 2.3 失败处理
- 网络请求设置 timeout（建议 10-30s）
- API 调用加重试（最多2次，指数退避）
- 关键步骤失败时打印明确错误信息，不要静默失败
- 单个来源失败不应导致整个任务失败（降级策略）

## 三、常见任务模板

### 每日简报
```
summary: 生成每日XX简报
dtstart: 每日08:03
rrule: DAILY interval=1
time_range: ±30min
description: 加载XX技能→搜索→筛选→生成→保存到 用户上传/XX_YYYYMMDD.md→上传项目空间
```

### 每周监控
```
summary: 每周XX状态检查
dtstart: 每周日21:03
rrule: WEEKLY interval=1
time_range: ±10min
```

### 一次性提醒
```
summary: 提醒XX事项
dtstart: 具体日期时间
不设rrule
time_range: ±5min
```

## 四、可靠性检查清单

- [ ] description 包含完整执行步骤，执行session无需主对话记忆
- [ ] dtstart 使用非整点时间
- [ ] 设置了 time_range 弹性窗口
- [ ] rrule 只填必要字段（freq + interval）
- [ ] 脚本有错误处理和超时设置
- [ ] 输出文件路径在 description 中明确
- [ ] 文件大小有预期范围（异常时可发现失败）
- [ ] 关键凭证通过环境变量或SECRET获取，不硬编码

## 五、任务管理

### 查询现有任务
```
calendar_query(start_date, end_date, return_mode="event")
```

### 修改任务
使用 `calendar_update`，修改重复主事件时必须同时提供新的 rrule。

### 删除任务
使用 `calendar_delete`，`delete_series=true` 删除整个系列。

### 任务健康度
- 连续3天执行成功 = 稳定
- 执行成功率 < 80% = 需优化（检查time_range、脚本稳定性、API可用性）
- 定时任务产物应定期检查文件大小和内容质量
