#!/usr/bin/env python3
"""
卡牌游戏平衡测试引擎
接收卡牌JSON数据和战斗配置，运行大规模模拟对战，生成平衡性报告。
"""

import json
import random
import argparse
import sys
import os
from datetime import datetime, timezone
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any


# ============ 数据结构 ============

@dataclass
class CardEffect:
    type: str
    value: int = 0
    target: str = "enemy_unit"  # enemy_unit, enemy_player, self_unit, self_player, all_enemy_units
    duration: int = 0

@dataclass
class Card:
    id: str
    name: str
    faction: str
    rarity: str
    cost: int
    type: str  # 战灵, 法术, 领域
    attack: int = 0
    health: int = 0
    effects: List[CardEffect] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

@dataclass
class Unit:
    card_id: str
    name: str
    faction: str
    attack: int
    health: int
    max_health: int
    statuses: List[Dict] = field(default_factory=list)  # {id, duration, value}
    can_attack: bool = False
    has_attacked: bool = False

@dataclass
class Player:
    name: str
    hp: int
    max_hp: int
    energy: int
    max_energy: int
    deck: List[Card] = field(default_factory=list)
    hand: List[Card] = field(default_factory=list)
    field: List[Unit] = field(default_factory=list)
    discard: List[Card] = field(default_factory=list)
    is_first: bool = True

# ============ 卡牌数据解析 ============

def parse_card(raw: dict) -> Card:
    """从原始JSON解析卡牌，支持多种字段命名格式"""
    effects = []
    raw_effects = raw.get("effects", raw.get("skill_mechanics", {}).get("effects", []))
    if isinstance(raw_effects, list):
        for eff in raw_effects:
            if isinstance(eff, dict):
                effects.append(CardEffect(
                    type=eff.get("type", eff.get("effect_type", "damage")),
                    value=eff.get("value", eff.get("magnitude", 0)),
                    target=eff.get("target", "enemy_unit"),
                    duration=eff.get("duration", 0)
                ))
            elif isinstance(eff, str):
                # 简单字符串效果，如 "damage:3"
                parts = eff.split(":")
                effects.append(CardEffect(
                    type=parts[0].strip(),
                    value=int(parts[1]) if len(parts) > 1 else 0
                ))

    return Card(
        id=raw.get("id", raw.get("card_id", "")),
        name=raw.get("name", raw.get("card_name", "")),
        faction=raw.get("faction", raw.get("element", raw.get("law", ""))),
        rarity=raw.get("rarity", raw.get("grade", "N")),
        cost=raw.get("cost", raw.get("energy_cost", 0)),
        type=raw.get("type", raw.get("card_type", "战灵")),
        attack=raw.get("attack", raw.get("atk", 0)),
        health=raw.get("health", raw.get("hp", raw.get("def", 0))),
        effects=effects,
        tags=raw.get("tags", raw.get("keywords", []))
    )

def load_cards(filepath: str) -> List[Card]:
    """从JSON文件加载卡牌数据"""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 支持多种JSON结构
    if isinstance(data, list):
        raw_cards = data
    elif isinstance(data, dict):
        raw_cards = data.get("cards", data.get("data", data.get("card_list", [])))
        if not raw_cards and all(k.startswith("CARD") or k.startswith("card") for k in data.keys()):
            raw_cards = list(data.values())
    else:
        raw_cards = []

    cards = []
    for raw in raw_cards:
        try:
            cards.append(parse_card(raw))
        except Exception:
            continue

    return cards

# ============ 牌组构建 ============

def build_deck(cards: List[Card], faction: str, max_deck=20, max_same=2, max_ur=1, max_ssr=3) -> List[Card]:
    """为指定流派构建合法牌组"""
    faction_cards = [c for c in cards if c.faction == faction]
    if len(faction_cards) < 5:
        return []

    # 按费用排序，构建合理曲线
    sorted_cards = sorted(faction_cards, key=lambda c: (c.cost, -c.attack))

    deck = []
    name_count = defaultdict(int)
    ur_count = 0
    ssr_count = 0

    for card in sorted_cards:
        if len(deck) >= max_deck:
            break
        if name_count[card.name] >= max_same:
            continue
        if card.rarity == "UR" and ur_count >= max_ur:
            continue
        if card.rarity == "SSR" and ssr_count >= max_ssr:
            continue

        deck.append(card)
        name_count[card.name] += 1
        if card.rarity == "UR":
            ur_count += 1
        if card.rarity == "SSR":
            ssr_count += 1

    # 如果不够max_deck张，允许重复添加
    if len(deck) < max_deck:
        for card in sorted_cards:
            if len(deck) >= max_deck:
                break
            if name_count[card.name] >= max_same:
                continue
            deck.append(card)
            name_count[card.name] += 1

    return deck[:max_deck]

# ============ 战斗逻辑 ============

class BattleSimulator:
    def __init__(self, config: dict, rng: random.Random):
        self.config = config
        self.rng = rng

    def init_player(self, name: str, deck: List[Card], is_first: bool) -> Player:
        cfg = self.config
        hp = cfg.get("initial_hp", 20)
        energy_cap = cfg.get("energy_cap", 10)
        draw_first = cfg.get("draw_first", 3)
        draw_second = cfg.get("draw_second", 4)

        player = Player(
            name=name, hp=hp, max_hp=hp,
            energy=1, max_energy=1,
            deck=list(deck), is_first=is_first
        )

        self.rng.shuffle(player.deck)
        draw_count = draw_first if is_first else draw_second
        for _ in range(draw_count):
            if player.deck:
                player.hand.append(player.deck.pop(0))

        return player

    def run_battle(self, deck_a: List[Card], deck_b: List[Card]) -> str:
        """运行一场战斗，返回 'A', 'B', or 'draw'"""
        player_a = self.init_player("A", deck_a, is_first=True)
        player_b = self.init_player("B", deck_b, is_first=False)
        max_turns = self.config.get("max_turns", 8)
        field_cap = self.config.get("field_cap", 5)
        hand_cap = self.config.get("hand_cap", 7)

        for turn in range(1, max_turns + 1):
            # Player A's turn
            self.start_turn(player_a, turn)
            self.ai_play(player_a, player_b, field_cap, hand_cap)
            self.end_turn_attack(player_a, player_b)

            if player_b.hp <= 0:
                return "A"

            # Player B's turn
            self.start_turn(player_b, turn)
            self.ai_play(player_b, player_a, field_cap, hand_cap)
            self.end_turn_attack(player_b, player_a)

            if player_a.hp <= 0:
                return "B"

        # 超时按HP百分比判定
        hp_a_pct = player_a.hp / player_a.max_hp
        hp_b_pct = player_b.hp / player_b.max_hp
        if abs(hp_a_pct - hp_b_pct) < 0.05:
            return "draw"
        return "A" if hp_a_pct > hp_b_pct else "B"

    def start_turn(self, player: Player, turn: int):
        """回合开始：恢复能量、抽牌"""
        energy_cap = self.config.get("energy_cap", 10)
        player.max_energy = min(turn, energy_cap)
        player.energy = player.max_energy

        # 抽1张牌
        if player.deck:
            card = player.deck.pop(0)
            hand_cap = self.config.get("hand_cap", 7)
            if len(player.hand) < hand_cap:
                player.hand.append(card)
            else:
                player.discard.append(card)

        # 后手第一回合额外抽1张（补偿机制）
        if not player.is_first and turn == 1:
            if player.deck and len(player.hand) < self.config.get("hand_cap", 7):
                player.hand.append(player.deck.pop(0))

        # 处理状态效果（燃烧伤害、冻结解除等）
        new_statuses = []
        for status in player.field_units_statuses():
            status["duration"] -= 1
            if status["id"] == "burn" and status["duration"] >= 0:
                # 燃烧在回合末造成伤害
                pass  # 在end_turn处理
            if status["duration"] > 0:
                new_statuses.append(status)
        # 简化：状态在单位上处理

        for unit in player.field:
            unit.has_attacked = False
            unit.can_attack = True
            # 处理状态
            for s in unit.statuses:
                s["duration"] -= 1
            unit.statuses = [s for s in unit.statuses if s["duration"] > 0]

    def ai_play(self, player: Player, opponent: Player, field_cap: int, hand_cap: int):
        """简单AI：优先打出费用最高的卡"""
        # 按费用降序排序手牌
        playable = sorted([c for c in player.hand if c.cost <= player.energy],
                         key=lambda c: c.cost, reverse=True)

        for card in playable[:]:  # copy because we modify hand
            if card.cost > player.energy:
                continue
            if len(player.field) >= field_cap and card.type == "战灵":
                continue

            player.energy -= card.cost
            player.hand.remove(card)

            if card.type == "战灵":
                unit = Unit(
                    card_id=card.id, name=card.name, faction=card.faction,
                    attack=card.attack, health=card.health, max_health=card.health,
                    can_attack=True
                )
                player.field.append(unit)
            elif card.type == "法术":
                self.resolve_effects(card, player, opponent)
                player.discard.append(card)
            elif card.type == "领域":
                self.resolve_effects(card, player, opponent)
                player.discard.append(card)

            # 重新计算可出的牌
            playable = sorted([c for c in player.hand if c.cost <= player.energy],
                            key=lambda c: c.cost, reverse=True)

    def resolve_effects(self, card: Card, player: Player, opponent: Player):
        """解析卡牌效果"""
        for eff in card.effects:
            if eff.type == "damage":
                # 攻击对手主战者或场上单位
                if opponent.field:
                    target = self.rng.choice(opponent.field)
                    target.health -= eff.value
                    if target.health <= 0:
                        opponent.field.remove(target)
                else:
                    opponent.hp -= eff.value

            elif eff.type == "heal":
                player.hp = min(player.hp + eff.value, player.max_hp)

            elif eff.type == "shield":
                # 给场上单位加护盾
                if player.field:
                    target = self.rng.choice(player.field)
                    target.statuses.append({"id": "shield", "duration": 1, "value": eff.value})

            elif eff.type == "freeze":
                if opponent.field:
                    target = self.rng.choice(opponent.field)
                    target.statuses.append({"id": "freeze", "duration": 1, "value": 0})

            elif eff.type == "burn":
                if opponent.field:
                    target = self.rng.choice(opponent.field)
                    target.statuses.append({"id": "burn", "duration": 2, "value": eff.value})
                else:
                    opponent.hp -= eff.value

            elif eff.type == "shock":
                if opponent.field:
                    target = self.rng.choice(opponent.field)
                    target.statuses.append({"id": "shock", "duration": 1, "value": eff.value})

            elif eff.type == "taunt":
                if player.field:
                    target = self.rng.choice(player.field)
                    target.statuses.append({"id": "taunt", "duration": 1, "value": 0})

            elif eff.type == "draw_card":
                for _ in range(eff.value or 1):
                    if player.deck and len(player.hand) < self.config.get("hand_cap", 7):
                        player.hand.append(player.deck.pop(0))

            elif eff.type == "cost_reduce":
                # 简化：暂时降低手牌费用
                for c in player.hand:
                    c.cost = max(0, c.cost - (eff.value or 1))

            elif eff.type == "buff":
                if player.field:
                    target = self.rng.choice(player.field)
                    target.attack += eff.value or 1
                    target.health += eff.value or 1
                    target.max_health += eff.value or 1

            elif eff.type == "debuff":
                if opponent.field:
                    target = self.rng.choice(opponent.field)
                    target.attack = max(0, target.attack - (eff.value or 1))

            elif eff.type == "pierce":
                # 穿透伤害直接打主战者
                opponent.hp -= eff.value

    def end_turn_attack(self, attacker: Player, defender: Player):
        """回合末：所有单位攻击"""
        # 处理燃烧伤害
        for unit in attacker.field:
            burn = next((s for s in unit.statuses if s["id"] == "burn"), None)
            if burn:
                unit.health -= burn.get("value", 1)

        # 移除死亡单位
        attacker.field = [u for u in attacker.field if u.health > 0]

        # 单位攻击
        for unit in attacker.field:
            if not unit.can_attack or unit.has_attacked:
                continue
            # 检查冻结
            is_frozen = any(s["id"] == "freeze" for s in unit.statuses)
            if is_frozen:
                continue

            unit.has_attacked = True

            # 检查嘲讽
            taunt_units = [u for u in defender.field if any(s["id"] == "taunt" for s in u.statuses)]

            if taunt_units:
                target = self.rng.choice(taunt_units)
            elif defender.field:
                target = self.rng.choice(defender.field)
            else:
                # 直接攻击主战者
                defender.hp -= unit.attack
                continue

            # 计算伤害
            damage = unit.attack
            # 检查感电（受击+50%）
            shock = next((s for s in target.statuses if s["id"] == "shock"), None)
            if shock:
                damage = int(damage * 1.5)

            # 检查护盾
            shield = next((s for s in target.statuses if s["id"] == "shield"), None)
            if shield:
                absorbed = min(shield["value"], damage)
                shield["value"] -= absorbed
                damage -= absorbed
                if shield["value"] <= 0:
                    target.statuses = [s for s in target.statuses if s["id"] != "shield"]

            # 穿透检查
            has_pierce = any(s["id"] == "pierce" for s in unit.statuses)

            if damage > 0:
                target.health -= damage
                if has_pierce and target.health < 0:
                    # 穿透溢出伤害打主战者
                    defender.hp += target.health  # health是负数，加回去等于减

                if target.health <= 0:
                    defender.field.remove(target)

    def check_resonance(self, player: Player):
        """检查同法则共鸣"""
        faction_count = defaultdict(int)
        for unit in player.field:
            faction_count[unit.faction] += 1

        for faction, count in faction_count.items():
            if count >= 2:
                # 2张同流派：攻击力+1
                for unit in player.field:
                    if unit.faction == faction:
                        unit.attack += 1
            if count >= 3:
                # 3张：对对手主战者2伤害
                # 简化处理
                pass


# 给Player添加辅助方法
def field_units_statuses(self):
    return []
Player.field_units_statuses = field_units_statuses

# ============ 批量模拟 ============

def run_simulations(cards: List[Card], config: dict, total_games: int = 3000) -> dict:
    """运行所有流派两两对局"""
    factions = sorted(set(c.faction for c in cards if c.faction))

    # 为每个流派构建牌组
    decks = {}
    for f in factions:
        deck = build_deck(cards, f)
        if deck:
            decks[f] = deck
        else:
            print(f"⚠️ 流派 {f} 卡牌不足，跳过")

    valid_factions = list(decks.keys())
    n_factions = len(valid_factions)
    games_per_matchup = max(total_games // (n_factions * n_factions), 10)

    rng = random.Random(42)  # 固定种子确保可复现
    sim = BattleSimulator(config, rng)

    # 结果统计
    results = {}
    stats = {f: {"wins": 0, "losses": 0, "draws": 0, "turns": []} for f in valid_factions}

    for f_a in valid_factions:
        for f_b in valid_factions:
            if f_a == f_b:
                continue  # 跳过镜像对局统计

            a_wins = 0
            b_wins = 0
            draws = 0

            for _ in range(games_per_matchup):
                result = sim.run_battle(list(decks[f_a]), list(decks[f_b]))
                if result == "A":
                    a_wins += 1
                    stats[f_a]["wins"] += 1
                    stats[f_b]["losses"] += 1
                elif result == "B":
                    b_wins += 1
                    stats[f_b]["wins"] += 1
                    stats[f_a]["losses"] += 1
                else:
                    draws += 1
                    stats[f_a]["draws"] += 1
                    stats[f_b]["draws"] += 1

            results[f"{f_a}_vs_{f_b}"] = {
                "attacker": f_a,
                "defender": f_b,
                "attacker_wins": a_wins,
                "defender_wins": b_wins,
                "draws": draws,
                "total": games_per_matchup,
                "attacker_winrate": round(a_wins / games_per_matchup * 100, 1),
                "defender_winrate": round(b_wins / games_per_matchup * 100, 1),
            }

    return {"factions": valid_factions, "results": results, "stats": stats}

# ============ 报告生成 ============

def generate_report(sim_data: dict, config: dict, total_games: int) -> str:
    """生成Markdown格式平衡性报告"""
    factions = sim_data["factions"]
    results = sim_data["results"]
    stats = sim_data["stats"]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    actual_games = sum(r["total"] for r in results.values())

    lines = [
        f"# 卡牌游戏 - 数值平衡性报告",
        f"",
        f"> 生成时间: {now}",
        f"> 测试总局数: {actual_games}",
        f"> 流派数量: {len(factions)}",
        f"",
    ]

    # 1. 胜率矩阵
    lines.append("## 1. 流派对局胜率总览")
    lines.append("")
    header = "| 进攻方 \\ 防守方 | " + " | ".join(factions) + " |"
    separator = "| --- |" + " --- |" * len(factions)
    lines.append(header)
    lines.append(separator)

    for f_a in factions:
        row = [f"**{f_a}**"]
        for f_b in factions:
            if f_a == f_b:
                row.append("-")
            else:
                key = f"{f_a}_vs_{f_b}"
                r = results.get(key)
                if r:
                    row.append(f"{r['attacker_winrate']}%")
                else:
                    row.append("-")
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")

    # 2. 综合表现
    lines.append("## 2. 各流派综合表现")
    lines.append("")
    lines.append("| 流派 | 总胜场 | 总负场 | 平局 | 综合胜率 | 平衡性评估 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")

    faction_stats = []
    for f in factions:
        s = stats[f]
        total = s["wins"] + s["losses"] + s["draws"]
        winrate = round(s["wins"] / total * 100, 1) if total > 0 else 0
        assessment = "✅ 平衡" if 40 <= winrate <= 60 else ("⚠️ 偏强" if winrate > 60 else "⚠️ 偏弱")
        lines.append(f"| {f} | {s['wins']} | {s['losses']} | {s['draws']} | {winrate}% | {assessment} |")
        faction_stats.append((f, winrate, assessment))

    lines.append("")

    # 3. 极端对局
    lines.append("## 3. 极端对局分析")
    lines.append("")

    sorted_results = sorted(results.values(), key=lambda r: r["attacker_winrate"], reverse=True)
    if sorted_results:
        highest = sorted_results[0]
        lowest = sorted_results[-1]
        lines.append(f"- **最高单场胜率**: {highest['attacker']} vs {highest['defender']} = {highest['attacker_winrate']}%")
        lines.append(f"- **最低单场胜率**: {lowest['attacker']} vs {lowest['defender']} = {lowest['attacker_winrate']}%")

    lines.append("")

    # 4. 平衡性分析
    lines.append("## 4. 平衡性分析")
    lines.append("")

    issues = []
    for f, winrate, assessment in faction_stats:
        if winrate < 40 or winrate > 60:
            issues.append(f"- {f}综合胜率{winrate}%，{'超过60%阈值' if winrate > 60 else '低于40%阈值'}")

    if issues:
        lines.append("⚠️ **发现以下平衡性问题：**")
        lines.extend(issues)
    else:
        lines.append("✅ **所有流派胜率在40%-60%区间内，平衡性良好。**")

    # 胜率极差
    winrates = [w for _, w, _ in faction_stats]
    if winrates:
        spread = round(max(winrates) - min(winrates), 1)
        lines.append(f"- 流派胜率极差: {spread}%")

    if spread > 30:
        lines.append(f"- **评估: 平衡性存在明显问题**，建议重点调整强势和弱势流派。")
    elif spread > 15:
        lines.append(f"- **评估: 平衡性一般**，部分流派需微调。")
    else:
        lines.append(f"- **评估: 平衡性良好**。")

    lines.append("")

    # 5. 调整建议
    lines.append("## 5. 调整建议")
    lines.append("")

    strong = [(f, w) for f, w, a in faction_stats if w > 60]
    weak = [(f, w) for f, w, a in faction_stats if w < 40]

    if strong:
        lines.append("**需要削弱的流派：**")
        for f, w in strong:
            lines.append(f"- {f}（{w}%）：降低高伤害卡牌攻击力、提高高效果卡牌费用、缩短强力状态效果持续时间")
    if weak:
        lines.append("**需要加强的流派：**")
        for f, w in weak:
            lines.append(f"- {f}（{w}%）：提升攻击力、降低高费卡牌费用、增强效果数值")

    if not strong and not weak:
        lines.append("当前数值平衡性良好，无需大幅调整。")

    lines.append("")
    lines.append("---")
    lines.append("*本报告由 card-game-balance-tester 自动生成*")

    return "\n".join(lines)


# ============ 主入口 ============

def main():
    parser = argparse.ArgumentParser(description="卡牌游戏平衡测试工具")
    parser.add_argument("--cards", required=True, help="卡牌数据JSON文件路径")
    parser.add_argument("--config", default=None, help="战斗配置JSON文件路径（可选）")
    parser.add_argument("--games", type=int, default=3000, help="模拟总局数（默认3000）")
    parser.add_argument("--output", default=None, help="报告输出路径（默认 balance_report.md）")
    parser.add_argument("--seed", type=int, default=42, help="随机种子（默认42）")

    args = parser.parse_args()

    # 加载卡牌数据
    print(f"📁 加载卡牌数据: {args.cards}")
    cards = load_cards(args.cards)
    print(f"   ✅ 加载了 {len(cards)} 张卡牌")

    if not cards:
        print("❌ 未加载到任何卡牌数据，请检查文件格式")
        sys.exit(1)

    # 统计流派分布
    faction_count = defaultdict(int)
    for c in cards:
        faction_count[c.faction] += 1
    print(f"   流派分布: {dict(faction_count)}")

    # 加载战斗配置
    config = {
        "initial_hp": 20,
        "energy_cap": 10,
        "hand_cap": 7,
        "field_cap": 5,
        "max_turns": 8,
        "draw_first": 3,
        "draw_second": 4,
    }
    if args.config:
        with open(args.config, 'r', encoding='utf-8') as f:
            user_config = json.load(f)
        config.update(user_config)
        print(f"📁 加载战斗配置: {args.config}")

    print(f"⚙️ 战斗配置: HP={config['initial_hp']}, 能量上限={config['energy_cap']}, 最大回合={config['max_turns']}")
    print(f"🎮 开始模拟 {args.games} 局对战...")

    # 运行模拟
    sim_data = run_simulations(cards, config, args.games)

    actual_games = sum(r["total"] for r in sim_data["results"].values())
    print(f"   ✅ 完成 {actual_games} 局模拟")

    # 生成报告
    report = generate_report(sim_data, config, actual_games)

    # 输出报告
    output_path = args.output or "balance_report.md"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"📊 平衡性报告已保存: {output_path}")

    # 打印关键指标摘要
    print("\n" + "=" * 50)
    print("关键指标摘要:")
    print("=" * 50)
    for f in sim_data["factions"]:
        s = sim_data["stats"][f]
        total = s["wins"] + s["losses"] + s["draws"]
        winrate = round(s["wins"] / total * 100, 1) if total > 0 else 0
        status = "✅" if 40 <= winrate <= 60 else "⚠️"
        print(f"  {status} {f}: {winrate}% (胜{s['wins']} 负{s['losses']} 平{s['draws']})")


if __name__ == "__main__":
    main()
