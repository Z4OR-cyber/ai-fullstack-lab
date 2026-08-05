#!/usr/bin/env python3
"""
卡牌数据验证器 - Card Data Validator
验证卡牌JSON数据是否符合设计规范，输出结构化验证报告。
"""

import json
import sys
import argparse
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Any, Optional


# ===== 默认配置 =====
DEFAULT_CONFIG = {
    "factions": ["fire", "tide", "thunder", "rock", "wind", "light"],
    "faction_names": {
        "fire": "烈焰", "tide": "潮汐", "thunder": "雷霆",
        "rock": "磐石", "wind": "疾风", "light": "辉光",
        "resonance": "共鸣"
    },
    "faction_aliases": {
        "烈焰": "fire", "潮汐": "tide", "雷霆": "thunder",
        "磐石": "rock", "疾风": "wind", "辉光": "light",
        "共鸣": "resonance", "fire": "fire", "tide": "tide",
        "thunder": "thunder", "rock": "rock", "wind": "wind",
        "light": "light", "resonance": "resonance",
    },
    "type_aliases": {
        "creature": "creature", "战灵": "creature", "生物": "creature",
        "spell": "spell", "法术": "spell",
        "enchantment": "enchantment", "领域": "enchantment", "结界": "enchantment",
        "共鸣卡": "spell", "共鸣": "spell",
    },
    "valid_rarities": ["N", "R", "SR", "SSR", "UR"],
    "valid_types": ["creature", "spell", "enchantment"],
    "max_cost": 10,
    "min_cost": 0,
    "max_deck_size": 20,
    "max_same_name": 2,
    "max_ur": 1,
    "max_ssr": 3,
    "max_hand_size": 10,
}

# 费用曲线参考（费用 -> (下限, 上限, 均值)）
COST_CURVE = {
    0: (1, 3, 2),
    1: (2, 4, 3),
    2: (3, 6, 4.5),
    3: (4, 8, 6),
    4: (6, 10, 8),
    5: (8, 13, 10.5),
    6: (10, 16, 13),
    7: (13, 18, 15.5),
    8: (15, 20, 17.5),
    9: (17, 22, 19.5),
    10: (19, 25, 22),
}

REQUIRED_FIELDS = {
    "creature": ["id", "name", "faction", "cost", "type", "rarity", "attack", "health"],
    "spell": ["id", "name", "faction", "cost", "type", "rarity"],
    "enchantment": ["id", "name", "faction", "cost", "type", "rarity"],
}

RARITY_ORDER = {"N": 0, "R": 1, "SR": 2, "SSR": 3, "UR": 4}


class ValidationResult:
    def __init__(self):
        self.errors: List[Dict] = []
        self.warnings: List[Dict] = []
        self.info: List[Dict] = []

    def add_error(self, card_id: str, message: str):
        self.errors.append({"card_id": card_id, "message": message})

    def add_warning(self, card_id: str, message: str):
        self.warnings.append({"card_id": card_id, "message": message})

    def add_info(self, card_id: str, message: str):
        self.info.append({"card_id": card_id, "message": message})

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0


def load_cards(file_path: str) -> List[Dict]:
    """加载卡牌JSON数据"""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        if "cards" in data:
            return data["cards"]
        elif "data" in data:
            return data["data"]
        else:
            return [data]
    elif isinstance(data, list):
        return data
    else:
        raise ValueError("无法识别的JSON格式，期望数组或包含cards字段的对象")


def validate_structure(cards: List[Dict], config: Dict, result: ValidationResult):
    """验证卡牌结构完整性"""
    seen_ids = set()
    seen_names = Counter()

    for i, card in enumerate(cards):
        card_id = card.get("id", f"index_{i}")
        card_type_raw = card.get("type", "unknown")
        type_aliases = config.get("type_aliases", {})
        card_type = type_aliases.get(card_type_raw, card_type_raw)
        card_name = card.get("name", "未命名")

        # 检查重复ID
        if card_id in seen_ids:
            result.add_error(card_id, f"重复的卡牌ID: {card_id}")
        seen_ids.add(card_id)

        # 统计同名卡牌
        seen_names[card_name] += 1

        # 检查必填字段
        required = REQUIRED_FIELDS.get(card_type, ["id", "name", "faction", "cost", "type", "rarity"])
        for field in required:
            if field not in card:
                result.add_error(card_id, f"缺少必填字段: {field}")

        # 检查费用范围
        cost = card.get("cost")
        if cost is not None:
            if not isinstance(cost, int) or cost < config["min_cost"] or cost > config["max_cost"]:
                result.add_error(card_id, f"费用 {cost} 超出有效范围 ({config['min_cost']}-{config['max_cost']})")

        # 检查稀有度
        rarity = card.get("rarity")
        if rarity and rarity not in config["valid_rarities"]:
            result.add_error(card_id, f"稀有度 '{rarity}' 不是有效值: {config['valid_rarities']}")

        # 检查流派（支持中英文）
        faction = card.get("faction")
        faction_aliases = config.get("faction_aliases", {})
        normalized_faction = faction_aliases.get(faction, faction)
        valid_factions = config["factions"] + ["resonance"]
        if faction and normalized_faction not in valid_factions:
            result.add_error(card_id, f"流派 '{faction}' 不是有效值: {valid_factions}")
        if faction:
            card["faction"] = normalized_faction  # 归一化为英文

        # 检查类型（支持中英文）
        type_aliases = config.get("type_aliases", {})
        normalized_type = type_aliases.get(card_type, card_type)
        if normalized_type not in config["valid_types"]:
            result.add_error(card_id, f"类型 '{card_type}' 不是有效值: {config['valid_types']}")
        card["type"] = normalized_type  # 归一化为英文

        # 检查生物卡属性
        if card_type == "creature":
            attack = card.get("attack")
            health = card.get("health")
            if attack is not None and (not isinstance(attack, int) or attack < 0):
                result.add_error(card_id, f"攻击力 {attack} 无效（应为非负整数）")
            if health is not None and (not isinstance(health, int) or health < 1):
                result.add_error(card_id, f"生命值 {health} 无效（应为正整数）")

        # 检查效果数组
        effects = card.get("effects", [])
        if effects is None:
            effects = []
        if not isinstance(effects, list):
            result.add_error(card_id, f"effects 字段应为数组，实际为 {type(effects).__name__}")

        # 信息级：空效果
        if card_type == "creature" and len(effects) == 0:
            result.add_info(card_id, f"纯白板生物（无效果）: {card_name}")

        # 信息级：技能描述过长
        skill_text = card.get("skill_text", "")
        if skill_text and len(skill_text) > 100:
            result.add_info(card_id, f"技能描述过长（{len(skill_text)}字符）: {card_name}")

        # 信息级：0费卡
        if cost == 0:
            result.add_info(card_id, f"0费卡牌，需关注平衡性: {card_name}")

    # 检查同名卡牌
    for name, count in seen_names.items():
        if count > config["max_same_name"]:
            result.add_warning("全局", f"同名卡牌 '{name}' 出现 {count} 次，超过上限 {config['max_same_name']}")


def validate_distribution(cards: List[Dict], config: Dict, result: ValidationResult):
    """验证卡牌分布"""
    total = len(cards)
    if total == 0:
        result.add_error("全局", "卡牌数据为空")
        return

    # 流派分布
    faction_counts = Counter(card.get("faction", "unknown") for card in cards)
    num_factions = len(config["factions"])
    expected_per_faction = total / num_factions
    threshold = expected_per_faction * 0.2  # 20%偏差

    for faction in config["factions"]:
        count = faction_counts.get(faction, 0)
        if count == 0:
            result.add_warning("全局", f"流派 '{config['faction_names'].get(faction, faction)}' 无卡牌")
        elif abs(count - expected_per_faction) > threshold:
            result.add_warning(
                "全局",
                f"流派 '{config['faction_names'].get(faction, faction)}' 卡牌数 {count}，"
                f"偏离平均值 {expected_per_faction:.1f} 超过20%"
            )

    # 费用曲线
    cost_counts = Counter(card.get("cost", 0) for card in cards)
    for cost in range(config["min_cost"], config["max_cost"] + 1):
        if cost_counts.get(cost, 0) == 0:
            result.add_warning("全局", f"费用 {cost} 档位无卡牌（费用曲线断层）")

    # 稀有度分布
    rarity_counts = Counter(card.get("rarity", "N") for card in cards)
    total_rarities = sum(rarity_counts.values())
    for rarity in config["valid_rarities"]:
        count = rarity_counts.get(rarity, 0)
        pct = count / total_rarities * 100 if total_rarities > 0 else 0
        if rarity == "UR" and pct > 10:
            result.add_warning("全局", f"UR卡牌占比 {pct:.1f}%，超过10%上限")
        if rarity == "N" and pct < 20:
            result.add_warning("全局", f"N(普通)卡牌占比仅 {pct:.1f}%，低于20%")

    # 类型分布
    type_counts = Counter(card.get("type", "unknown") for card in cards)
    creature_pct = type_counts.get("creature", 0) / total * 100
    if creature_pct < 40:
        result.add_warning("全局", f"生物卡占比仅 {creature_pct:.1f}%，建议保持在40%以上")


def validate_cost_curve(cards: List[Dict], config: Dict, result: ValidationResult):
    """验证费用-属性曲线合理性"""
    cost_stats = defaultdict(lambda: {"total_atk_hp": 0, "count": 0, "cards": []})

    for card in cards:
        if card.get("type") != "creature":
            continue
        cost = card.get("cost", 0)
        attack = card.get("attack", 0)
        health = card.get("health", 0)
        stat_sum = attack + health
        cost_stats[cost]["total_atk_hp"] += stat_sum
        cost_stats[cost]["count"] += 1
        cost_stats[cost]["cards"].append({
            "id": card.get("id"),
            "name": card.get("name"),
            "attack": attack,
            "health": health,
            "stat_sum": stat_sum,
            "effects": card.get("effects", []),
        })

    for cost, stats in sorted(cost_stats.items()):
        if stats["count"] == 0:
            continue
        avg = stats["total_atk_hp"] / stats["count"]
        curve = COST_CURVE.get(cost)
        if not curve:
            continue
        low, high, expected = curve

        for card_info in stats["cards"]:
            stat_sum = card_info["stat_sum"]
            has_effects = len(card_info["effects"]) > 0

            # 有效生物卡属性范围调整
            effective_low = low - (1 if has_effects else 0)
            effective_high = high + (1 if not has_effects else 0)

            if stat_sum < effective_low:
                deviation = (expected - stat_sum) / expected * 100 if expected > 0 else 0
                if deviation > 30:
                    result.add_warning(
                        card_info["id"],
                        f"属性总和 {stat_sum}({card_info['attack']}/{card_info['health']}) "
                        f"严重低于费用{cost}曲线均值 {expected}（偏差{deviation:.0f}%）"
                    )
            elif stat_sum > effective_high:
                deviation = (stat_sum - expected) / expected * 100 if expected > 0 else 0
                if deviation > 30:
                    result.add_warning(
                        card_info["id"],
                        f"属性总和 {stat_sum}({card_info['attack']}/{card_info['health']}) "
                        f"严重高于费用{cost}曲线均值 {expected}（偏差{deviation:.0f}%）"
                    )


def validate_deck_rules(cards: List[Dict], config: Dict, result: ValidationResult):
    """验证牌组构建规则"""
    # 检查UR/SSR数量
    rarity_counts = Counter(card.get("rarity", "N") for card in cards)
    ur_count = rarity_counts.get("UR", 0)
    ssr_count = rarity_counts.get("SSR", 0)

    if ur_count > config["max_ur"] * 5:  # 全库检查，放宽5倍
        result.add_warning("全局", f"UR卡牌 {ur_count} 张，全库数量较多，注意牌组构建限制（≤{config['max_ur']}/牌组）")
    if ssr_count > config["max_ssr"] * 5:
        result.add_warning("全局", f"SSR卡牌 {ssr_count} 张，全库数量较多，注意牌组构建限制（≤{config['max_ssr']}/牌组）")


def generate_report(cards: List[Dict], result: ValidationResult, config: Dict) -> str:
    """生成验证报告"""
    total = len(cards)
    lines = []
    lines.append("# 卡牌数据验证报告\n")
    lines.append(f"**验证时间**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**卡牌总数**: {total}")
    lines.append(f"**验证结果**: {'✅ 通过' if result.passed else '❌ 有错误需修复'}\n")

    # 摘要
    lines.append("## 摘要\n")
    lines.append(f"| 级别 | 数量 |")
    lines.append(f"|------|------|")
    lines.append(f"| ❌ 错误 | {len(result.errors)} |")
    lines.append(f"| ⚠️ 警告 | {len(result.warnings)} |")
    lines.append(f"| ℹ️ 信息 | {len(result.info)} |")
    lines.append("")

    # 错误列表
    if result.errors:
        lines.append("## ❌ 错误列表（必须修复）\n")
        for err in result.errors:
            lines.append(f"- **[{err['card_id']}]** {err['message']}")
        lines.append("")

    # 警告列表
    if result.warnings:
        lines.append("## ⚠️ 警告列表（建议修复）\n")
        for warn in result.warnings:
            lines.append(f"- **[{warn['card_id']}]** {warn['message']}")
        lines.append("")

    # 分布统计
    lines.append("## 分布统计\n")

    # 流派分布
    faction_counts = Counter(card.get("faction", "unknown") for card in cards)
    lines.append("### 流派分布\n")
    lines.append("| 流派 | 数量 | 占比 |")
    lines.append("|------|------|------|")
    for faction in config["factions"] + ["resonance"]:
        count = faction_counts.get(faction, 0)
        pct = count / total * 100 if total > 0 else 0
        name = config["faction_names"].get(faction, faction)
        lines.append(f"| {name} | {count} | {pct:.1f}% |")
    lines.append("")

    # 费用分布
    cost_counts = Counter(card.get("cost", 0) for card in cards)
    lines.append("### 费用分布\n")
    lines.append("| 费用 | 数量 | 占比 |")
    lines.append("|------|------|------|")
    for cost in range(config["min_cost"], config["max_cost"] + 1):
        count = cost_counts.get(cost, 0)
        pct = count / total * 100 if total > 0 else 0
        lines.append(f"| {cost} | {count} | {pct:.1f}% |")
    lines.append("")

    # 稀有度分布
    rarity_counts = Counter(card.get("rarity", "N") for card in cards)
    lines.append("### 稀有度分布\n")
    lines.append("| 稀有度 | 数量 | 占比 |")
    lines.append("|--------|------|------|")
    for rarity in config["valid_rarities"]:
        count = rarity_counts.get(rarity, 0)
        pct = count / total * 100 if total > 0 else 0
        lines.append(f"| {rarity} | {count} | {pct:.1f}% |")
    lines.append("")

    # 类型分布
    type_counts = Counter(card.get("type", "unknown") for card in cards)
    lines.append("### 类型分布\n")
    lines.append("| 类型 | 数量 | 占比 |")
    lines.append("|------|------|------|")
    for card_type in config["valid_types"]:
        count = type_counts.get(card_type, 0)
        pct = count / total * 100 if total > 0 else 0
        lines.append(f"| {card_type} | {count} | {pct:.1f}% |")
    lines.append("")

    # 费用曲线分析
    lines.append("## 费用曲线分析\n")
    lines.append("| 费用 | 生物卡数 | 平均属性总和 | 参考均值 | 偏差 | 评估 |")
    lines.append("|------|---------|------------|---------|------|------|")
    cost_stats = defaultdict(lambda: {"total": 0, "count": 0})
    for card in cards:
        if card.get("type") != "creature":
            continue
        cost = card.get("cost", 0)
        stat_sum = card.get("attack", 0) + card.get("health", 0)
        cost_stats[cost]["total"] += stat_sum
        cost_stats[cost]["count"] += 1

    for cost in range(config["min_cost"], config["max_cost"] + 1):
        stats = cost_stats.get(cost)
        if not stats or stats["count"] == 0:
            curve = COST_CURVE.get(cost)
            if curve:
                lines.append(f"| {cost} | 0 | - | {curve[2]} | - | ⚠️ 无卡牌 |")
            continue
        avg = stats["total"] / stats["count"]
        curve = COST_CURVE.get(cost, (0, 0, 0))
        expected = curve[2]
        deviation = (avg - expected) / expected * 100 if expected > 0 else 0
        if abs(deviation) <= 10:
            eval_str = "✅ 合理"
        elif abs(deviation) <= 20:
            eval_str = "⚠️ 轻微偏差"
        elif abs(deviation) <= 30:
            eval_str = "⚠️ 偏差较大"
        else:
            eval_str = "❌ 严重偏差"
        lines.append(f"| {cost} | {stats['count']} | {avg:.1f} | {expected} | {deviation:+.1f}% | {eval_str} |")
    lines.append("")

    # 信息列表
    if result.info:
        lines.append("## ℹ️ 信息列表（仅供参考）\n")
        for info in result.info:
            lines.append(f"- **[{info['card_id']}]** {info['message']}")
        lines.append("")

    # 结论
    lines.append("## 结论\n")
    if result.passed and len(result.warnings) <= 5:
        lines.append("✅ 卡牌数据验证通过，可以用于测试/上线。")
    elif result.passed:
        lines.append(f"✅ 无致命错误，但有 {len(result.warnings)} 个警告，建议修复后上线。")
    else:
        lines.append(f"❌ 发现 {len(result.errors)} 个错误，必须修复后才能使用。")
    lines.append("")

    return "\n".join(lines)


def validate_cards(file_path: str, config: Optional[Dict] = None) -> Tuple[ValidationResult, str]:
    """验证卡牌数据，返回结果和报告"""
    if config is None:
        config = DEFAULT_CONFIG.copy()

    # 加载数据
    cards = load_cards(file_path)

    # 执行验证
    result = ValidationResult()
    validate_structure(cards, config, result)
    validate_distribution(cards, config, result)
    validate_cost_curve(cards, config, result)
    validate_deck_rules(cards, config, result)

    # 生成报告
    report = generate_report(cards, result, config)

    return result, report


def main():
    parser = argparse.ArgumentParser(description="卡牌数据验证器")
    parser.add_argument("file", help="卡牌JSON文件路径")
    parser.add_argument("--output", "-o", help="报告输出文件路径（默认输出到stdout）")
    parser.add_argument("--factions", nargs="*", help="自定义流派列表")
    parser.add_argument("--max-deck-size", type=int, default=20, help="牌组最大张数")
    parser.add_argument("--max-same-name", type=int, default=2, help="同名卡上限")
    parser.add_argument("--max-ur", type=int, default=1, help="UR卡上限")
    parser.add_argument("--max-ssr", type=int, default=3, help="SSR卡上限")

    args = parser.parse_args()

    # 构建配置
    config = DEFAULT_CONFIG.copy()
    if args.factions:
        config["factions"] = args.factions
    config["max_deck_size"] = args.max_deck_size
    config["max_same_name"] = args.max_same_name
    config["max_ur"] = args.max_ur
    config["max_ssr"] = args.max_ssr

    # 执行验证
    result, report = validate_cards(args.file, config)

    # 输出报告
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"验证报告已保存到: {args.output}")
    else:
        print(report)

    # 退出码
    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
