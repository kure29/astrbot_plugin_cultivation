# astrbot_plugin_cultivation/systems/exploration.py

import random
import json
import os
from typing import Dict, Any
from ..models.character import Character, Equipment
from ..database.db_manager import DatabaseManager
from ..utils.llm_utils import LLMUtils
from ..systems.combat import CombatSystem
from ..utils.constants import LOCATIONS, MONSTERS, COMBAT_SETTINGS, RANDOM_EVENTS, EXPLORATION_SETTINGS, ALCHEMY_DATA
from ..utils.path_utils import PLUGIN_DATA_DIR


class ExplorationSystem:
    """探索系统"""

    def __init__(self, db_manager: DatabaseManager, llm_utils: LLMUtils):
        self.db_manager = db_manager
        self.llm_utils = llm_utils
        self.combat_system = CombatSystem(db_manager, llm_utils)
        self.alchemy_data_path = os.path.join(PLUGIN_DATA_DIR, "alchemy.json")

    async def explore_area(self, character: Character) -> Dict[str, Any]:
        """探索当前区域"""
        location = character.location
        location_info = LOCATIONS.get(location, {})
        result_type = self._determine_exploration_result(character, location_info)

        if result_type == "monster_encounter":
            return await self._handle_monster_encounter(character, location_info)
        elif result_type == "treasure_found":
            return await self._handle_treasure_discovery(character)
        elif result_type == "special_event":
            return await self._handle_special_event(character, location_info)
        elif result_type == "boss_encounter":
            return await self._handle_boss_encounter(character, location_info)
        elif result_type == "nothing":
            return await self._handle_empty_exploration(character, character.location)
        else:
            return await self._handle_normal_exploration(character, character.location)

    def _determine_exploration_result(self, character: Character, location_info: Dict) -> str:
        """确定探索结果类型"""
        probabilities = {
            "monster_encounter": 0.4, "treasure_found": 0.15, "special_event": 0.1,
            "nothing": 0.15, "normal": 0.2, "boss_encounter": 0.02
        }
        luck_modifier = character.stats.luck * 0.01
        probabilities["treasure_found"] += luck_modifier
        probabilities["monster_encounter"] -= luck_modifier * 0.5

        if not location_info.get("monsters"):
            probabilities["monster_encounter"] = 0
            probabilities["normal"] += 0.4

        if not location_info.get("bosses"):
            probabilities["boss_encounter"] = 0
            probabilities["normal"] += 0.02

        rand = random.random()
        cumulative = 0
        for result_type, prob in probabilities.items():
            cumulative += prob
            if rand <= cumulative:
                return result_type
        return "normal"
        
    async def _handle_boss_encounter(self, character: Character, location_info: Dict) -> Dict[str, Any]:
        """处理Boss遭遇"""
        bosses = location_info.get("bosses", {})
        if not bosses:
            return await self._handle_normal_exploration(character, character.location)
        
        chosen_boss = random.choice(list(bosses.keys()))
        combat_result = await self.combat_system.start_combat(character, chosen_boss, is_boss=True)
        return {"success": True, "encounter_type": "boss", "monster": chosen_boss, "message": combat_result["message"]}

    async def _handle_monster_encounter(self, character: Character, location_info: Dict) -> Dict[str, Any]:
        """处理怪物遭遇"""
        monsters = location_info.get("monsters", [])
        if not monsters:
            return await self._handle_normal_exploration(character, character.location)
        
        suitable_monsters = [m for m in monsters if abs(MONSTERS.get(m, {}).get("level", 1) - character.level) <= 5]
        if not suitable_monsters:
            suitable_monsters = monsters
        
        chosen_monster = random.choice(suitable_monsters)
        combat_result = await self.combat_system.start_combat(character, chosen_monster)
        return {"success": True, "encounter_type": "monster", "monster": chosen_monster, "message": combat_result["message"]}

    async def _handle_treasure_discovery(self, character: Character) -> Dict[str, Any]:
        """处理宝藏发现（LLM驱动）"""
        event_data = await self.llm_utils.generate_treasure_discovery_event(character)
        description = event_data.get("description", "你在一个隐蔽的山洞里发现了一个前人留下的储物袋。")
        rewards = event_data.get("rewards", {})
        
        spirit_stones_reward = rewards.get("spirit_stones", 0)
        exp_reward = rewards.get("exp", 0)
        items_reward = rewards.get("items", [])
        
        character.spirit_stones += spirit_stones_reward
        character.exp += exp_reward
        
        reward_messages = []
        if spirit_stones_reward > 0:
            reward_messages.append(f"获得{spirit_stones_reward}灵石")
        if exp_reward > 0:
            reward_messages.append(f"获得{exp_reward}经验")
            
        for item_data in items_reward:
            item_name = item_data.get("name", "神秘物品")
            item_type = item_data.get("type", "道具")
            quantity = item_data.get("quantity", 1)
            item_desc = item_data.get("description", "")
            item_effect = item_data.get("effect")
            
            if item_type == "装备":
                new_equipment = Equipment.from_dict(item_data)
                character.add_item(item_name, 1, "装备", item_desc, new_equipment.to_dict())
                reward_messages.append(f"获得装备：{item_name}")
            else:
                character.add_item(item_name, quantity, item_type, item_desc, item_effect)
                reward_messages.append(f"获得{item_name} x{quantity}")

        level_up_messages = character.level_up()
        if level_up_messages:
            reward_messages.extend(level_up_messages)

        message = f"【发现宝藏】\n\n{description}\n\n" + "\n".join(reward_messages)
        return {"success": True, "encounter_type": "treasure", "treasure": rewards, "message": message}

    async def _handle_normal_exploration(self, character: Character, location: str) -> Dict[str, Any]:
        """处理普通探索 (已适配动态收益)"""
        location_info = LOCATIONS.get(location, {})
        reward_multiplier = location_info.get("reward_multiplier", 1.0)

        exp_gain = int((EXPLORATION_SETTINGS["base_exp_gain"] + (character.level * EXPLORATION_SETTINGS["exp_gain_level_multiplier"])) * reward_multiplier * random.uniform(0.8, 1.2))
        spirit_stones_gain = int((EXPLORATION_SETTINGS["base_spirit_stones_gain"] + (character.level * EXPLORATION_SETTINGS["spirit_stones_gain_level_multiplier"])) * reward_multiplier * random.uniform(0.8, 1.2))

        character.exp += exp_gain
        character.spirit_stones += spirit_stones_gain
        level_up_messages = character.level_up()
        
        exploration_desc = await self.llm_utils.generate_exploration_description(location, "normal")
        message = f"【探索{location}】\n\n{exploration_desc}\n\n获得经验：{exp_gain}点\n获得灵石：{spirit_stones_gain}枚"
        if level_up_messages:
            message += "\n\n" + "\n".join(level_up_messages)
        return {"success": True, "encounter_type": "normal", "exp_gained": exp_gain, "spirit_stones_gained": spirit_stones_gain, "message": message}

    async def _handle_empty_exploration(self, character: Character, location: str) -> Dict[str, Any]:
        """处理空手而归的探索"""
        exploration_desc = await self.llm_utils.generate_text(f"为一名修士在【{location}】中探索良久但最终一无所获的场景，生成一段富有仙侠小说风格的生动情景描述", 80)
        message = f"【探索{location}】\n\n{exploration_desc}"
        return {"success": True, "encounter_type": "nothing", "message": message}
        
    async def _handle_special_event(self, character: Character, location_info: Dict) -> Dict[str, Any]:
        """处理特殊事件"""
        event = random.choice(list(RANDOM_EVENTS["exploration"].values()))
        
        event_desc_context = f"为在{character.location}探索时触发了【{event['name']}】事件的修士，生成一段富有仙侠小说风格的生动情景描述，要体现出事件特色。"
        event_description = await self.llm_utils.generate_text(event_desc_context, 100)
        
        message = f"【奇遇：{event['name']}】\n\n{event_description}\n\n"
        
        reward = event["reward"]
        reward_messages = []
        
        # 新增：属性中文翻译字典
        stat_translation = {
            "attack": "攻击",
            "defense": "防御",
            "speed": "速度",
            "luck": "气运"
        }

        if reward["type"] == "exp":
            exp_gain = eval(reward["exp"])
            character.exp += exp_gain
            reward_messages.append(f"获得经验: {exp_gain}点")
        elif reward["type"] == "restore":
            if reward.get("hp_restore"):
                character.stats.hp = character.stats.max_hp
            if reward.get("qi_restore"):
                character.stats.qi = character.stats.max_qi
            reward_messages.append("你的状态已完全恢复！")
        elif reward["type"] == "treasure":
            spirit_stones_gain = eval(reward["spirit_stones"])
            character.spirit_stones += spirit_stones_gain
            reward_messages.append(f"获得灵石: {spirit_stones_gain}枚")
            for item in reward["items"]:
                character.add_item(item, 1)
                reward_messages.append(f"获得物品: {item}")
        elif reward["type"] == "combat":
            return await self._handle_monster_encounter(character, location_info)
        elif reward["type"] == "items":
            for item in reward["items"]:
                character.add_item(item, 1)
                reward_messages.append(f"获得物品: {item}")
        elif reward["type"] == "damage":
            damage = eval(reward["damage"])
            character.stats.hp = max(1, character.stats.hp - damage)
            reward_messages.append(f"你受到了{damage}点伤害！")
        elif reward["type"] == "shop":
            reward_messages.append("你可以使用 /购买 指令与他们交易。")
        elif reward["type"] == "enlightenment":
            exp_gain = eval(reward["exp"])
            character.exp += exp_gain
            reward_messages.append(f"获得经验: {exp_gain}点")
            if reward.get("stats_boost"):
                stat_to_boost = random.choice(["attack", "defense", "speed", "luck"])
                setattr(character.stats, stat_to_boost, getattr(character.stats, stat_to_boost) + 1)
                translated_stat = stat_translation.get(stat_to_boost, stat_to_boost) # 使用翻译
                reward_messages.append(f"你的{translated_stat}属性永久提升了！")
        elif reward["type"] == "discovery" and reward.get("new_material"):
            # Since we removed the LLM function, this part will be simplified.
            # You can add a pre-defined list of materials to discover here.
            reward_messages.append("你似乎发现了一种奇特的植物，但仔细一看，却又平平无奇。")

        message += "\n".join(reward_messages)
        level_up_messages = character.level_up()
        if level_up_messages:
            message += "\n\n" + "\n".join(level_up_messages)

        return {"success": True, "encounter_type": "special_event", "message": message}