# astrbot_plugin_cultivation/systems/generators.py

import random
from typing import Optional, Dict, Any, List
from astrbot.api import logger
from ..utils.config_manager import config
from ..models.character import Monster

class MonsterGenerator:
    """基于标签系统的怪物生成器"""

    @staticmethod
    def _generate_rewards(base_loot: List[Dict[str, Any]], level: int) -> List[Dict[str, Any]]:
        gained_items = []
        for entry in base_loot:
            if random.random() < entry.get("chance", 0):
                quantity_range = entry.get("quantity", [1, 1])
                min_qty = quantity_range[0]
                max_qty = quantity_range[1] if len(quantity_range) > 1 else min_qty
                
                item_name = entry.get("item_name")
                if item_name:
                    amount = random.randint(min_qty, max_qty)
                    gained_items.append({"name": item_name, "quantity": amount})
        return gained_items

    @classmethod
    def create_monster(cls, template_id: str, player_level: int) -> Optional[Monster]:
        template = config.monster_data.get(template_id)
        if not template:
            logger.warning(f"尝试创建怪物失败：找不到模板ID {template_id}")
            return None

        monster_level = template.get("level", player_level)
        
        base_hp = 20 * monster_level + 40
        base_attack = 4 * monster_level + 10
        base_defense = 2 * monster_level + 5
        base_spirit_stones = 3 * monster_level + 5
        base_exp = 5 * monster_level + 10

        final_name = template["name"]
        final_hp = base_hp
        final_attack = base_attack
        final_defense = base_defense
        final_spirit_stones = base_spirit_stones
        final_exp = base_exp
        combined_loot_table = template.get("drop_items", [])

        for tag_name in template.get("tags", []):
            tag_effect = config.tag_data.get(tag_name)
            if not tag_effect:
                continue
            
            if "name_prefix" in tag_effect:
                final_name = f"【{tag_effect['name_prefix']}】{final_name}"
            if "name_suffix" in tag_effect:
                final_name += tag_effect['name_suffix']
            
            final_hp *= tag_effect.get("hp_multiplier", 1.0)
            final_attack *= tag_effect.get("attack_multiplier", 1.0)
            final_defense *= tag_effect.get("defense_multiplier", 1.0)
            final_spirit_stones *= tag_effect.get("spirit_stones_multiplier", 1.0)
            final_exp *= tag_effect.get("exp_multiplier", 1.0)

            if "add_to_loot" in tag_effect:
                combined_loot_table.extend(tag_effect["add_to_loot"])
        
        final_hp = int(final_hp)
        instance = Monster(
            id=template_id,
            name=final_name,
            level=monster_level,
            hp=final_hp,
            max_hp=final_hp,
            attack=int(final_attack),
            defense=int(final_defense),
            exp_reward=int(final_exp),
            spirit_stones_reward=int(final_spirit_stones),
            drop_items=cls._generate_rewards(combined_loot_table, monster_level)
        )
        return instance