# astrbot_plugin_cultivation/systems/equipment.py

import random
from typing import Dict, Any, Optional, List
from ..models.character import Character, Equipment
from ..database.db_manager import DatabaseManager
from ..utils.llm_utils import LLMUtils
from ..utils.constants import EQUIPMENT_TYPES, EQUIPMENT_LEVEL_MAP
import re


class EquipmentSystem:
    """装备系统"""

    def __init__(self, db_manager: DatabaseManager, llm_utils: LLMUtils):
        self.db_manager = db_manager
        self.llm_utils = llm_utils

    async def generate_equipment(self, character_level: int, equipment_type: str = None) -> Equipment:
        """生成随机装备"""
        if not equipment_type:
            equipment_type = random.choice(EQUIPMENT_TYPES)

        # 基础属性计算
        base_stats = self._calculate_base_stats(character_level, equipment_type)

        # 生成装备名称
        equipment_name = self._generate_equipment_name(equipment_type, character_level)

        # 创建装备
        equipment = Equipment(
            name=equipment_name,
            item_type=equipment_type,
            level=EQUIPMENT_LEVEL_MAP.get(character_level, "凡品"),
            rank=character_level,
            atk_buff=base_stats["attack"],
            def_buff=base_stats["defense"],
            crit_buff=0,  # Initialize with default values
            critatk=0,
            mp_buff=0,
            zw=0,
            type="装备",
            description=await self._generate_equipment_description(equipment_name)
        )

        # 随机特殊效果
        if character_level > 20: # 假设超过20级就有几率出特效
            equipment.special_effect = self._generate_special_effect(character_level)

        return equipment

    def _calculate_base_stats(self, character_level: int, equipment_type: str) -> Dict[str, int]:
        """计算装备基础属性"""
        level_factor = character_level // 5 + 1
        base_stats = {"attack": 0, "defense": 0, "hp": 0, "qi": 0}

        if equipment_type == "武器":
            base_stats["attack"] = int(10 + level_factor * 3)
            base_stats["qi"] = int(5 + level_factor)
        elif equipment_type == "防具":
            base_stats["defense"] = int(8 + level_factor * 2)
            base_stats["hp"] = int(20 + level_factor * 5)
        elif equipment_type == "饰品":
            base_stats["attack"] = int(3 + level_factor)
            base_stats["defense"] = int(3 + level_factor)
            base_stats["hp"] = int(10 + level_factor * 2)
            base_stats["qi"] = int(10 + level_factor * 2)
        elif equipment_type == "法宝":
            base_stats["attack"] = int(5 + level_factor * 2)
            base_stats["qi"] = int(15 + level_factor * 3)

        # 随机波动
        for stat in base_stats:
            variation = random.uniform(0.8, 1.2)
            base_stats[stat] = int(base_stats[stat] * variation)

        return base_stats

    def _generate_equipment_name(self, equipment_type: str, character_level: int) -> str:
        """生成装备名称"""
        prefixes = ["铁制", "青铜", "基础", "精制", "强化", "改良", "符文", "魔法", "精品", "传承", "英雄", "远古", "传说", "神话", "永恒", "天神", "创世", "混沌"]

        weapon_names = ["剑", "刀", "枪", "斧", "弓", "法杖"]
        armor_names = ["甲", "袍", "靴", "护手", "头盔"]
        accessory_names = ["戒指", "项链", "护符", "腰带"]
        treasure_names = ["宝珠", "如意", "印玺", "铃铛", "镜子"]

        prefix = random.choice(prefixes)

        if equipment_type == "武器":
            suffix = random.choice(weapon_names)
        elif equipment_type == "防具":
            suffix = random.choice(armor_names)
        elif equipment_type == "饰品":
            suffix = random.choice(accessory_names)
        else:  # 法宝
            suffix = random.choice(treasure_names)

        return f"{prefix}{suffix}"

    async def _generate_equipment_description(self, equipment_name: str) -> str:
        """生成装备描述"""
        description = await self.llm_utils.generate_text(f"为名为【{equipment_name}】的装备生成一段仙侠风格的描述。", 80)

        if description in ["生成失败，请稍后重试", "LLM服务暂不可用"]:
            description = f"一件看似不凡的{equipment_name}。"

        return description

    def _generate_special_effect(self, character_level: int) -> str:
        """生成特殊效果"""
        effects = [
            "战斗时有10%几率触发护盾",
            "攻击时有15%几率造成额外伤害",
            "受到攻击时有10%几率反弹伤害"
        ]
        if character_level > 40:
            effects.extend([
                "战斗时有20%几率完全免疫伤害",
                "攻击时有25%几率造成双倍伤害",
                "每回合恢复少量生命值",
                "提升20%经验获得"
            ])
        if character_level > 70:
            effects.extend([
                "战斗时有30%几率进入无敌状态",
                "攻击必定暴击",
                "每次击败敌人恢复全部生命值",
                "修炼经验获得翻倍",
                "死亡时有50%几率复活"
            ])

        return random.choice(effects)

    async def equip_item(self, character: Character, equipment: Equipment) -> Dict[str, Any]:
        """装备物品"""
        equipment_type = equipment.type

        old_equipment = character.equipment.get(equipment_type)
        character.equipment[equipment_type] = equipment

        equip_desc = await self.llm_utils.generate_text(
            f"生成装备{equipment.name}的描述", 80
        )

        message = f"装备成功！\n\n"
        message += f"装备类型：{equipment_type}\n"
        message += f"装备名称：{equipment.name} ({equipment.level})\n"

        # Check for attribute bonuses before adding to message
        if hasattr(equipment, 'attack_bonus') and equipment.attack_bonus > 0:
            message += f"攻击力：+{equipment.attack_bonus}\n"
        if hasattr(equipment, 'defense_bonus') and equipment.defense_bonus > 0:
            message += f"防御力：+{equipment.defense_bonus}\n"
        if hasattr(equipment, 'hp_bonus') and equipment.hp_bonus > 0:
            message += f"生命值：+{equipment.hp_bonus}\n"
        if hasattr(equipment, 'qi_bonus') and equipment.qi_bonus > 0:
            message += f"真元值：+{equipment.qi_bonus}\n"
        if hasattr(equipment, 'special_effect') and equipment.special_effect:
            message += f"特殊效果：{equipment.special_effect}\n"

        if old_equipment:
            message += f"\n替换了：{old_equipment.name}"

        if equip_desc not in ["生成失败，请稍后重试", "LLM服务暂不可用"]:
            message += f"\n\n{equip_desc}"

        return {
            "success": True,
            "equipped": equipment,
            "replaced": old_equipment,
            "message": message
        }

    async def unequip_item(self, character: Character, equipment_type: str) -> Dict[str, Any]:
        """卸下装备"""
        if equipment_type not in character.equipment:
            return {
                "success": False,
                "message": f"无效的装备类型：{equipment_type}"
            }

        equipment = character.equipment[equipment_type]
        if not equipment:
            return {
                "success": False,
                "message": f"当前没有装备{equipment_type}"
            }

        character.equipment[equipment_type] = None
        character.add_item(equipment.name, 1, "装备", equipment.description)

        message = f"已卸下{equipment.name}并放入背包"

        return {
            "success": True,
            "unequipped": equipment,
            "message": message
        }

    async def enhance_equipment(self, character: Character, equipment_type: str, enhancement_material: str) -> Dict[
        str, Any]:
        """强化装备"""
        if equipment_type not in character.equipment:
            return {
                "success": False,
                "message": f"无效的装备类型：{equipment_type}"
            }

        equipment = character.equipment[equipment_type]
        if not equipment:
            return {
                "success": False,
                "message": f"没有装备{equipment_type}可以强化"
            }

        if not character.has_item(enhancement_material):
            return {
                "success": False,
                "message": f"缺少强化材料：{enhancement_material}"
            }

        success_rate = 0.7
        enhancement_cost = 100

        if character.gold < enhancement_cost:
            return {
                "success": False,
                "message": f"强化需要{enhancement_cost}金币"
            }

        character.remove_item(enhancement_material, 1)
        character.gold -= enhancement_cost

        if random.random() < success_rate:
            enhancement_bonus = random.randint(2, 8)
            if hasattr(equipment, 'attack_bonus'):
                equipment.attack_bonus += enhancement_bonus if equipment.attack_bonus > 0 else 0
            if hasattr(equipment, 'defense_bonus'):
                equipment.defense_bonus += enhancement_bonus if equipment.defense_bonus > 0 else 0
            if hasattr(equipment, 'hp_bonus'):
                equipment.hp_bonus += enhancement_bonus * 2 if equipment.hp_bonus > 0 else 0
            if hasattr(equipment, 'qi_bonus'):
                equipment.qi_bonus += enhancement_bonus if equipment.qi_bonus > 0 else 0
            
            match = re.search(r'\+(\d+)', equipment.name)
            if match:
                current_level = int(match.group(1))
                equipment.name = re.sub(r'\+\d+', f'+{current_level + 1}', equipment.name)
            else:
                equipment.name += " +1"

            message = f"强化成功！\n\n"
            message += f"装备：{equipment.name}\n"
            message += f"属性提升：+{enhancement_bonus}\n"
            message += f"消耗：{enhancement_cost}金币，{enhancement_material} x1"
        else:
            message = f"强化失败！\n\n"
            message += f"装备：{equipment.name}\n"
            message += f"损失：{enhancement_cost}金币，{enhancement_material} x1\n"
            message += f"装备未受损，可以再次尝试"

        return {
            "success": True,
            "enhancement_success": random.random() < success_rate,
            "message": message
        }

    def calculate_equipment_power(self, character: Character) -> int:
        """计算装备总战力"""
        total_power = 0
        for equipment in character.equipment.values():
            if equipment:
                power = (getattr(equipment, 'attack_bonus', 0) * 2 +
                         getattr(equipment, 'defense_bonus', 0) +
                         getattr(equipment, 'hp_bonus', 0) // 10)
                total_power += power
        return total_power

    async def get_equipment_info(self, character: Character) -> Dict[str, Any]:
        """获取装备详情"""
        equipment_info = {}
        total_bonuses = {"attack": 0, "defense": 0, "hp": 0, "qi": 0}

        for eq_type, equipment in character.equipment.items():
            if equipment:
                equipment_info[eq_type] = {
                    "name": equipment.name,
                    "level": equipment.level,
                    "attack_bonus": getattr(equipment, 'attack_bonus', 0),
                    "defense_bonus": getattr(equipment, 'defense_bonus', 0),
                    "hp_bonus": getattr(equipment, 'hp_bonus', 0),
                    "qi_bonus": getattr(equipment, 'qi_bonus', 0),
                    "special_effect": getattr(equipment, 'special_effect', None),
                    "description": equipment.description
                }

                total_bonuses["attack"] += getattr(equipment, 'attack_bonus', 0)
                total_bonuses["defense"] += getattr(equipment, 'defense_bonus', 0)
                total_bonuses["hp"] += getattr(equipment, 'hp_bonus', 0)
                total_bonuses["qi"] += getattr(equipment, 'qi_bonus', 0)
            else:
                equipment_info[eq_type] = None

        return {
            "equipment": equipment_info,
            "total_bonuses": total_bonuses,
            "total_power": self.calculate_equipment_power(character)
        }