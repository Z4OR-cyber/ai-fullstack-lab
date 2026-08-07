# 安全检查清单

## SQL 注入
- [ ] 是否使用参数化查询？
- [ ] 是否避免字符串拼接 SQL？

## 命令注入
- [ ] 是否避免 os.system()？
- [ ] 是否使用 subprocess.run() 而非 subprocess.call()？

## 路径遍历
- [ ] 是否验证文件路径？
- [ ] 是否使用 os.path.normpath()？

## 序列化
- [ ] 是否避免 pickle.loads()？
- [ ] 是否使用 yaml.safe_load()？
