# astrbot_plugin_cultivation/systems/gathering_system.py
import time
import random
from typing import Dict, Any
from ..models.character import Character
from ..utils.constants import GATHERING_DATA # 確保 GATHERING_DATA 能被正確加載

class GatheringSystem:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    async def perform_gathering(self, character: Character) -> Dict[str, Any]:
        location_name = character.location
        gather_info = GATHERING_DATA.get(location_name)

        if not gather_info:
            return {"success": False, "message": "此地靈氣稀薄，似乎沒有什麼天材地寶。"}
        
        if character.level < gather_info.get("level_req", 1):
            return {"success": False, "message": "你的境界尚淺，無法在此地采集。"}

        cooldown = gather_info.get("cooldown", 300)
        time_since_last = time.time() - character.stats.last_gathering
        if time_since_last < cooldown:
            return {"success": False, "message": f"此地的靈氣尚未恢復，請在 {int(cooldown - time_since_last)} 秒後再嘗試。"}

        character.stats.last_gathering = int(time.time())

        gathered_items = []
        # 隨機獲取1-3種物品
        num_items_to_gather = random.randint(1, 3)
        
        # 根據權重隨機選擇多種不重複的物品
        items = list(gather_info["items"].keys())
        weights = list(gather_info["items"].values())
        
        # 確保選擇的物品數量不超過可用的物品種類
        num_items_to_gather = min(num_items_to_gather, len(items))
        
        chosen_items = random.choices(items, weights=weights, k=num_items_to_gather)
        
        # 移除重複的選擇，確保每種物品只添加一次
        chosen_items = list(set(chosen_items))

        for chosen_item in chosen_items:
            quantity = 1
            character.add_item(chosen_item, quantity)
            gathered_items.append(f"{chosen_item} x{quantity}")

        if not gathered_items:
            message = "你搜寻了許久，卻最終一無所獲，看來是時運不濟。"
        else:
            message = "一番探尋之下，你採集到了些許天材地寶：\n- " + "\n- ".join(gathered_items)

        await self.db_manager.save_character(character)
        return {"success": True, "message": message}