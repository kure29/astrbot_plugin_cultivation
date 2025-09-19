# astrbot_plugin_cultivation/systems/crafting_system.py
import random
from typing import Dict, Any
from ..models.character import Character, Equipment
from ..utils.constants import ITEMS, RECIPES_DATA # 確保 RECIPES_DATA 能被正確加載

class CraftingSystem:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def get_next_level_exp(self, level: int) -> int:
        """計算下一級煉器經驗"""
        return 100 + (level - 1) * 50

    async def perform_crafting(self, character: Character, item_name: str) -> Dict[str, Any]:
        recipe = RECIPES_DATA.get(item_name)
        if not recipe:
            return {"success": False, "message": f"你尚未掌握【{item_name}】的锻造图纸。"}

        # 1. 檢查條件
        if character.stats.crafting_level < recipe.get("crafting_level_req", 1):
            return {"success": False, "message": f"你的炼器等级不足，无法锻造【{item_name}】。需要炼器等级 {recipe['crafting_level_req']}。"}

        missing_items = []
        for material, required_qty in recipe.get("materials", {}).items():
            if not character.has_item(material, required_qty):
                missing_items.append(f"{material}x{required_qty}")
        
        if missing_items:
            return {"success": False, "message": f"锻造【{item_name}】失败：缺少材料 {', '.join(missing_items)}。"}

        # 2. 計算成功率 (受煉器等級和氣運影響)
        success_rate = recipe.get("success_rate_base", 0.8) + (character.stats.luck * 0.005) + (character.stats.crafting_level * 0.01)
        success_rate = min(success_rate, 0.98) # 最高98%成功率

        # 3. 扣除材料
        for material, required_qty in recipe["materials"].items():
            character.remove_item(material, required_qty)
        
        message = f"你将各种材料投入锻造炉，催动真火，开始锻造【{item_name}】...\n\n"

        if random.random() > success_rate:
            message += "突然，锻造炉内传来一声闷响，一炉珍贵的材料化为了飞灰...锻造失败了。"
            await self.db_manager.save_character(character)
            return {"success": True, "crafted": False, "message": message}

        # 4. 鍛造成功
        item_info = ITEMS.get(item_name, {})
        new_equipment = Equipment.from_dict(item_info)

        # 品質浮動
        quality_roll = random.random()
        if quality_roll > 0.95: # 5% 极品
            new_equipment.attack = int(new_equipment.attack * 1.2)
            new_equipment.defense = int(new_equipment.defense * 1.2)
            new_equipment.name += " (极)"
            message += "霞光万道！你竟锻造出了一件极品！\n"
        elif quality_roll > 0.7: # 25% 上品
            new_equipment.attack = int(new_equipment.attack * 1.1)
            new_equipment.defense = int(new_equipment.defense * 1.1)
            new_equipment.name += " (上)"
            message += "炉火纯青！你锻造出了一件上品！\n"
        
        character.add_item(item_name=new_equipment.name, quantity=1, item_type=new_equipment.item_type)
        
        # 增加煉器經驗
        exp_gain = recipe.get("crafting_level_req", 1) * 10
        character.stats.crafting_exp += exp_gain
        message += f"锻造成功！你获得了【{new_equipment.name}】。\n炼器经验增加了 {exp_gain} 点。"

        # 檢查煉器等級提升
        exp_needed = self.get_next_level_exp(character.stats.crafting_level)
        if character.stats.crafting_exp >= exp_needed:
            character.stats.crafting_level += 1
            character.stats.crafting_exp -= exp_needed
            message += f"\n你的炼器术有所精进，提升到了 {character.stats.crafting_level} 级！"

        await self.db_manager.save_character(character)
        return {"success": True, "crafted": True, "message": message}