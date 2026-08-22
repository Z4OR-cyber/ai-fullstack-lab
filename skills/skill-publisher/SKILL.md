---
name: skill-publisher
description: 技能打包发布与全平台同步工具。覆盖从本地SKILL.md编写→zip打包→上传项目空间→Coze技能商店发布→GitHub推送→EvoMap发布的完整生命周期。当用户需要发布技能、打包技能、同步技能到多平台、更新技能版本、管理技能发布状态时使用此技能。
deprecated: true
replaced_by: multi-platform-publishing-engine
deprecated_date: 2026-08-22
---

> **DEPRECATED (2026-08-22)**: Use multi-platform-publishing-engine instead. 功能已整合入multi-platform-publishing-engine


# Skill Publisher — 技能打包发布与全平台同步

将本地编写的技能一键发布到 Coze「我的技能」，并同步推送到 GitHub、EvoMap 等平台。

## 核心工作流

### 第一步：本地编写

技能目录结构：
```
skills/{skill_name}/
├── SKILL.md              # 必需，含YAML frontmatter
├── scripts/              # 可选，Python/Shell脚本
│   └── main.py
├── references/           # 可选，参考文档
│   └── guide.md
└── docs/                 # 可选，使用文档
```

**SKILL.md 必须包含 YAML frontmatter**：
```yaml
---
name: skill-name
description: 一句话描述技能用途，50字以内，说明何时使用此技能。
---
```

### 第二步：zip 打包

⚠️ **关键**：`skill_draft_create` 无法直接检测 `write_file`/`bash` 写入的本地文件，必须先打包上传到项目空间。

```python
import zipfile, os

def package_skill(skill_dir, output_zip):
    """将技能目录打包为zip"""
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(skill_dir):
            # 排除隐藏文件和__pycache__
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
            for f in files:
                if f.startswith('.'):
                    continue
                filepath = os.path.join(root, f)
                arcname = os.path.relpath(filepath, os.path.dirname(skill_dir))
                zf.write(filepath, arcname)
    print(f"打包完成: {output_zip} ({os.path.getsize(output_zip)} bytes)")
```

### 第三步：上传到项目空间

```bash
coze agent file upload \
  --project-id {PROJECT_ID} \
  --local-file-path skills/{skill_name}.zip
```

返回 `project_file_path`（如 `/skill-name.zip`），用于下一步。

### 第四步：Coze 技能发布

首次发布（使用 artifact_url 触发上传模式）：
```
skill_draft_create(
    skill_name="skill-name",
    show_name="技能展示名",
    description="与SKILL.md中description一致",
    show_description="用户可见的详细描述",
    artifact_url="/skill-name.zip"
)
```

返回值判断：
- `intent=4, status=2`：上传模式成功，自动解压+打包+发布
- `intent=1, status=1`：全新创建（未检测到文件，检查zip路径）
- `intent=2, status=2`：编辑模式（已存在，自动打包更新）

**后续版本更新**：直接调用 `skill_draft_create(skill_name=..., icon_url=...)` 即可进入编辑模式，无需重新上传zip。更新后需手动调用 `skill_draft_publish(skill_id=...)` 发布。

### 第五步：GitHub 同步

```bash
# 使用 GitHub API 推送文件（无需git CLI）
curl -X PUT \
  -H "Authorization: token {GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/{owner}/{repo}/contents/skills/{skill_name}/SKILL.md \
  -d '{"message":"add skill: {skill_name}","content":"'$(base64 -w0 SKILL.md)'","sha":"{existing_sha_if_update}"}'
```

多文件推送时逐个文件PUT，更新文件需先GET获取sha。

### 第六步：EvoMap 发布（可选）

```bash
curl -X POST https://evomap.ai/a2a/publish \
  -H "Authorization: Bearer {NODE_SECRET}" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_type": "skill",
    "title": "技能名",
    "description": "描述",
    "content": "技能内容或URL",
    "tags": ["tag1", "tag2"]
  }'
```

注意：EvoMap API 使用 Bearer Token 认证（非POST body传node_secret），rate limit 10次/窗口/IP。

## 发布检查清单

发布前逐项检查：

- [ ] SKILL.md 包含 YAML frontmatter（name + description）
- [ ] description 与 skill_draft_create 参数一致
- [ ] 脚本有语法检查（`python3 -m py_compile`）
- [ ] 无绝对路径硬编码
- [ ] 无密钥/Token硬编码
- [ ] 依赖项在SKILL.md中声明
- [ ] 文件命名只用中英文、数字、下划线、短横线
- [ ] zip包不含 `.skills/`、`__pycache__/`、`.git/`

## 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| intent=1 每次新建 | zip未上传到TOS | 确认coze agent file upload成功，artifact_url用项目路径 |
| 打包后文件不完整 | zip路径层级错误 | arcname应保留skill_name目录层级 |
| 发布后未更新 | 编辑模式不自动发布 | 调用skill_draft_publish |
| GitHub 409冲突 | 缺少sha | 先GET获取最新sha再PUT |
| EvoMap 401 | 认证方式错误 | 使用Authorization: Bearer header |

## 版本管理

- 首次发布：自动发布到「我的技能」
- 后续更新：编辑模式打包后需手动 publish
- 版本号建议在SKILL.md中标注（如 v1.0.0）
- 重大更新在 description 中注明变更要点
