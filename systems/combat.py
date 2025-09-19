# astrbot_plugin_cultivation/systems/combat.py

import random
import json
from typing import Dict, Any, Optional
from ..models.character import Character, Monster
from ..database.db_manager import DatabaseManager
from ..utils.llm_utils import LLMUtils
from ..utils.constants import COMBAT_SETTINGS
from .generators import MonsterGenerator # <-- 引入新的生成器

class CombatSystem:
    """战斗系统"""

    def __init__(self, db_manager: DatabaseManager, llm_utils: LLMUtils):
        self.db_manager = db_manager
        self.llm_utils = llm_utils

    async def start_combat(self, character: Character, monster_template_id: str) -> Dict[str, Any]:
        """开始战斗"""
        # 使用 MonsterGenerator 动态创建怪物实例
        monster = MonsterGenerator.create_monster(monster_template_id, character.level)
        if not monster:
            return {"success": False, "message": f"未知怪物模板：{monster_template_id}"}

        # 创建战斗状态
        combat_data = {
            "monster_id": monster.id,
            "monster_name": monster.name,
            "monster_hp": monster.hp,
            "monster_max_hp": monster.max_hp,
            "monster_attack": monster.attack,
            "monster_defense": monster.defense,
            "monster_level": monster.level,
            "turn": "player",
            "round": 1
        }

        character.combat_state = json.dumps(combat_data)

        # 生成遭遇描述
        encounter_desc = await self.llm_utils.generate_exploration_description(
            character.location, "monster"
        )

        message = f"战斗开始！\n\n"
        message += f"遭遇敌人：{monster.name} (等级{monster.level})\n"
        message += f"敌人生命：{monster.hp}/{monster.max_hp}\n"
        message += f"敌人攻击：{monster.attack}\n"
        message += f"敌人防御：{monster.defense}\n\n"
        message += f"{encounter_desc}\n\n"
        message += f"请使用 /战斗 或 /逃跑"

        return {
            "success": True,
            "combat_started": True,
            "message": message
        }

    # player_attack, _monster_attack, _handle_monster_death, _handle_player_death, attempt_flee, use_combat_item
    # 这些方法的逻辑基本保持不变，因为它们已经是从 combat_data 中动态读取怪物属性，
    # 只是现在 combat_data 中的数据源头变成了动态生成的怪物。
    # 唯一需要调整的是 _handle_monster_death，以处理新的掉落物格式。

    async def _handle_monster_death(self, character: Character, combat_data: Dict, attack_message: str) -> Dict[str, Any]:
        """处理怪物死亡"""
        monster_template_id = combat_data["monster_id"]
        monster_template = config.monster_data.get(monster_template_id, {})
        
        # 重新生成一次怪物以获取其奖励信息
        monster = MonsterGenerator.create_monster(monster_template_id, character.level)

        # 获得奖励
        exp_reward = monster.exp_reward
        spirit_stones_reward = monster.spirit_stones_reward

        # 等级差异影响奖励
        level_diff = character.level - monster.level
        if level_diff > 5:
            exp_reward = max(1, exp_reward // (level_diff - 4))

        character.exp += exp_reward
        character.spirit_stones += spirit_stones_reward

        # 掉落物品
        dropped_items = monster.drop_items
        dropped_item_names = []
        for item in dropped_items:
            character.add_item(item["name"], item["quantity"], "材料")
            dropped_item_names.append(f"{item['name']} x{item['quantity']}")

        # 检查升级
        level_up_messages = character.level_up()

        # 结束战斗
        character.combat_state = None

        message = attack_message + "\n"
        message += f"击败了{monster.name}！\n\n"
        message += f"获得经验：{exp_reward}点\n"
        message += f"获得灵石：{spirit_stones_reward}枚\n"

        if dropped_item_names:
            message += f"掉落物品：{', '.join(dropped_item_names)}\n"

        if level_up_messages:
            message += "\n" + "\n".join(level_up_messages)

        return {
            "success": True,
            "combat_won": True,
            "exp_gained": exp_reward,
            "spirit_stones_gained": spirit_stones_reward,
            "items_gained": dropped_items,
            "message": message
        }
    
    # ... a large portion of the original combat.py remains unchanged ...
    # player_attack, _monster_attack, _handle_player_death, attempt_flee, use_combat_item
    # can largely stay the same, as they read from the combat_data dictionary.
    # The only other change needed is to add a `Monster` model to `models/character.py`

    # ... (the rest of the combat system methods remain the same)
    async def player_attack(self, character: Character, combat_data: Dict) -> Dict[str, Any]:
        """玩家攻击 (已适配新属性系统)"""
        if combat_data["turn"] != "player":
            return {
                "success": False,
                "message": "现在不是你的回合"
            }

        monster_name = combat_data["monster_name"]
        player_stats = character.get_total_stats()

        # 计算伤害
        total_attack = player_stats['attack']
        defense_reduction = combat_data["monster_defense"] // 2
        damage = max(1, total_attack - defense_reduction)

        # 随机波动
        damage_variation = random.uniform(0.8, 1.2)
        damage = int(damage * damage_variation)

        # 暴击检查
        is_critical = random.random() < player_stats['crit_rate']
        if is_critical:
            damage = int(damage * player_stats['crit_damage'])

        # 应用伤害
        combat_data["monster_hp"] -= damage

        # 生成攻击描述
        attack_desc = await self.llm_utils.generate_text(
            f"为名为{character.name}的修士攻击名为{monster_name}的怪物，造成了{damage}点伤害的战斗场景，生成一段生动的描述。{'暴击了！' if is_critical else ''}", 100
        )

        message = f"【{character.name}的攻击】\n\n"
        message += f"{attack_desc}\n\n"
        message += f"造成伤害：{damage}点"
        if is_critical:
            message += " (暴击！)"
        message += "\n"
        message += f"{monster_name}生命：{combat_data['monster_hp']}/{combat_data['monster_max_hp']}\n"

        # 检查怪物是否死亡
        if combat_data["monster_hp"] <= 0:
            return await self._handle_monster_death(character, combat_data, message)

        # 怪物反击
        combat_data["turn"] = "monster"
        character.combat_state = json.dumps(combat_data)

        monster_attack_result = await self._monster_attack(character, combat_data)
        message += "\n" + monster_attack_result["message"]

        # 检查玩家是否死亡
        if character.stats.hp <= 0:
            return await self._handle_player_death(character, message)

        combat_data["turn"] = "player"
        combat_data["round"] += 1
        character.combat_state = json.dumps(combat_data)

        message += f"\n\n第{combat_data['round']}回合，请继续使用 /战斗"

        return {
            "success": True,
            "combat_continues": True,
            "message": message
        }

    async def _monster_attack(self, character: Character, combat_data: Dict) -> Dict[str, Any]:
        """怪物攻击 (已适配新属性系统)"""
        monster_name = combat_data["monster_name"]
        player_stats = character.get_total_stats()

        # 计算怪物伤害
        monster_attack = combat_data["monster_attack"]
        total_defense = player_stats['defense']

        damage = max(1, monster_attack - total_defense // 2)

        # 闪避检查
        dodge_rate = COMBAT_SETTINGS["base_dodge_rate"] + (player_stats['speed'] * 0.005)
        if random.random() < dodge_rate:
            message = f"{character.name}敏捷地闪避了{monster_name}的攻击！"
            return {"success": True, "message": message}

        # 随机波动
        damage_variation = random.uniform(0.8, 1.2)
        damage = int(damage * damage_variation)

        # 应用伤害
        character.stats.hp -= damage

        message = f"【{monster_name}的反击】\n"
        message += f"对{character.name}造成{damage}点伤害\n"
        message += f"{character.name}生命：{character.stats.hp}/{character.stats.max_hp}"

        return {"success": True, "message": message}

    async def _handle_player_death(self, character: Character, battle_message: str) -> Dict[str, Any]:
        """处理玩家死亡"""
        # 死亡惩罚
        exp_loss = character.exp // 10
        spirit_stones_loss = character.spirit_stones // 20

        character.exp = max(0, character.exp - exp_loss)
        character.spirit_stones = max(0, character.spirit_stones - spirit_stones_loss)

        # 恢复一点生命值避免无限死亡
        character.stats.hp = 1

        # 结束战斗
        character.combat_state = None

        message = battle_message + "\n"
        message += f"战斗失败！{character.name}重伤倒下...\n\n"
        message += f"损失经验：{exp_loss}点\n"
        message += f"损失灵石：{spirit_stones_loss}枚\n"
        message += f"已紧急治疗，生命值恢复到1点\n"
        message += f"建议先恢复状态再继续冒险"

        return {
            "success": True,
            "combat_lost": True,
            "exp_lost": exp_loss,
            "spirit_stones_lost": spirit_stones_loss,
            "message": message
        }

    async def attempt_flee(self, character: Character) -> Dict[str, Any]:
        """尝试逃跑"""
        try:
            combat_data = json.loads(character.combat_state)
        except:
            return {
                "success": False,
                "message": "战斗状态异常"
            }

        player_stats = character.get_total_stats()
        # 计算逃跑成功率
        base_flee_rate = COMBAT_SETTINGS["base_flee_rate"]
        level_diff = character.level - combat_data["monster_level"]
        speed_bonus = player_stats['speed'] * 0.01

        flee_rate = base_flee_rate + (level_diff * 0.05) + speed_bonus
        flee_rate = max(0.1, min(0.95, flee_rate))

        if random.random() < flee_rate:
            character.combat_state = None
            message = f"{character.name}成功逃离了战斗！\n"
            message += f"逃跑成功率：{int(flee_rate * 100)}%"
            return { "success": True, "fled": True, "message": message }
        else:
            monster_attack_result = await self._monster_attack(character, combat_data)
            if character.stats.hp <= 0:
                return await self._handle_player_death(character, f"逃跑失败！\n{monster_attack_result['message']}")
            
            combat_data["turn"] = "player"
            character.combat_state = json.dumps(combat_data)
            message = f"逃跑失败！\n"
            message += monster_attack_result["message"]
            message += f"\n\n请继续使用 /战斗"
            return { "success": True, "fled": False, "message": message }
