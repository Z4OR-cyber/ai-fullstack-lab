"""
AI科技资讯简报收集技能

本技能主要通过 search_web 和 fetch_web 工具完成，
SKILL.md 中已定义完整的执行流程，无需额外代码逻辑。

使用说明：
1. 加载技能后，按照 SKILL.md 中的执行流程操作
2. 使用 search_web 搜索资讯
3. 使用 fetch_web 验证来源
4. 输出简报并保存为 Markdown 文件
"""

def run():
    """
    本技能为指令型技能，核心逻辑在 SKILL.md 中定义。
    执行时请遵循 SKILL.md 中的流程：
    1. 搜索资讯
    2. 验证来源
    3. 交叉验证
    4. 输出简报
    """
    print("AI科技资讯简报技能已加载，请遵循 SKILL.md 中的执行流程。")

if __name__ == "__main__":
    run()
