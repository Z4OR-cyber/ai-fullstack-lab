# Bug Bounty 每日监控自动化技能

## 概述
自动化每日监控HackerOne和Bugcrowd赏金项目变化，生成简报并推送。

## 数据源
- H1: raw.githubusercontent.com/arkadiyt/bounty-targets-data/main/data/hackerone_data.json
- BC: raw.githubusercontent.com/arkadiyt/bounty-targets-data/main/data/bugcrowd_data.json

## 核心功能
1. 拉取最新赏金项目数据
2. 与baseline对比识别新增/下线
3. 按友好度、赏金范围、Scope筛选
4. 生成TOP5推荐和简报
5. 上传到项目文件空间

## 关键配置
- 超时120s + 3次重试 + 5s间隔
- 每天上午9:00 Calendar调度
- time_range: 0830-0930

## 文件结构
codeact/scripts/daily_bounty_monitor.py
codeact/output/bounty_briefing_YYYY-MM-DD.md

## 经验
- raw.githubusercontent.com偶尔超时
- 约690个程序需高效筛选
- baseline JSON保存已知程序用于增量对比

## 许可
MIT
