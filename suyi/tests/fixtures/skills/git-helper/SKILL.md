---
name: git-helper
description: Git 版本控制辅助工具，处理分支管理和提交规范
---
# Git 辅助技能

## 使用步骤

1. 使用 `git status` 检查当前工作区状态
2. 使用 `git branch` 查看分支信息
3. 根据用户需求执行对应操作：
   - 创建分支：`git checkout -b feature/xxx`
   - 提交变更：`git add` + `git commit`
   - 合并分支：`git merge`
4. 输出操作结果和建议

## 注意事项

- 不执行 `git push` 操作（需用户手动确认）
- 提交信息遵循约定式提交规范
- 合并冲突时，提示用户手动解决
