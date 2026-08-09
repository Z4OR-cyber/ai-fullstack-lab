# GitHub Git Database API 推送技能

## 概述
当git push到github.com网络不可达时，使用GitHub Git Database API替代推送。

## API流程（6步）
1. GET /git/refs/heads/main 获取分支SHA
2. GET /git/commits/{sha} 获取tree SHA
3. POST /git/blobs 创建文件blob
4. POST /git/trees 创建新tree
5. POST /git/commits 创建commit
6. PATCH /git/refs/heads/main 更新ref

## 关键注意
- 文件内容直接作为JSON字符串传入blob API
- 删除文件时sha设为null
- 大批量文件分批创建blob（每批10个+0.5s间隔）
- Token需要repo scope
- Fork同步: POST /repos/{owner}/{repo}/merge-upstream

## 许可
MIT
