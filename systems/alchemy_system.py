# astrbot_plugin_cultivation/systems/alchemy_system.py

import random
import json
import os
from typing import Dict, Any, List

from ..models.character import Character
from ..database.db_manager import DatabaseManager  # <-- 修正：導入 DatabaseManager
from ..utils.llm_utils import LLMUtils            # <-- 修正：導入 LLMUtils
from ..utils.constants import ALCHEMY_DATA, ITEMS
from ..utils.path_utils import PLUGIN_DATA_DIR     # <-- 修正：導入 PLUGIN_DATA_DIR

class AlchemySystem:
    """
    独立的炼丹系统，负责所有与炼丹相关的逻辑。
    - 处理预设丹方
    - 调用LLM生成动态丹方
    - 进行成功率和产出品质判定
    """

    def __init__(self, db_manager: DatabaseManager, llm_utils: LLMUtils):
        self.db_manager = db_manager
        self.llm_utils = llm_utils
        # 注意：写入路径应该是 pills.json，但为了代码健壮性，保留 alchemy_data_path 的概念
        # 在 perform_alchemy 中会使用具体的 pills.json 路径
        self.alchemy_data_path = os.path.join(os.path.dirname(__file__), '..', 'data')


    async def perform_alchemy(self, character: Character, pill_name: str) -> Dict[str, Any]:
        """
        执行炼丹的核心方法。
        """
        recipe = ALCHEMY_DATA["pills"].get(pill_name)
        pills_data_path = os.path.join(self.alchemy_data_path, "pills.json") # 定义正确的写入路径

        if not recipe:
            # 丹方不存在，检查玩家是否为道祖
            if character.get_major_realm() != "道祖":
                return {"success": False, "message": f"你的境界尚未达到道祖，无法自行领悟【{pill_name}】的丹方。"}

            # 尝试调用LLM动态生成新丹方
            print(f"道祖 {character.name} 正在尝试创造新丹药：{pill_name}")
            recipe = await self.llm_utils.generate_alchemy_recipe(character, pill_name)
            
            if not recipe:
                return {"success": False, "message": f"你虽已是道祖，但创造【{pill_name}】似乎还缺少一些灵感，天机未到。"}
            
            # 将新生成的丹方永久写入 pills.json
            ALCHEMY_DATA["pills"][pill_name] = recipe
            with open(pills_data_path, "w", encoding="utf-8") as f: # 使用正确的路径
                json.dump(ALCHEMY_DATA["pills"], f, ensure_ascii=False, indent=4)
            
            ITEMS[pill_name] = recipe

        # --- 后续逻辑与之前类似，但现在是系统内部的方法 ---

        # 1. 检查条件 (境界, 材料, 灵石, 炼丹等级)
        # 境界检查
        required_realm = recipe.get("境界限制")
        if required_realm and character.get_major_realm() != required_realm and character.get_major_realm() != "道祖": # 道祖可无视低级限制
             return {"success": False, "message": f"炼制【{pill_name}】失败：你的境界（{character.get_major_realm()}）未达到【{required_realm}】的要求。"}

        # 材料检查
        missing_items = []
        for material, required_qty in recipe.get("materials", {}).items():
            if not character.has_item(material, required_qty):
                missing_items.append(f"{material}x{required_qty}")
        
        if missing_items:
            return {"success": False, "message": f"炼制【{pill_name}】失败：缺少材料 {', '.join(missing_items)}。"}
            
        # 灵石检查 (暂定为丹药价格的10%，LLM生成的丹方需要有价格)
        cost = recipe.get("price", 100) // 10
        if character.spirit_stones < cost:
            return {"success": False, "message": f"炼制【{pill_name}】失败：灵石不足，需要 {cost} 灵石。"}

        # 2. 扣除资源
        for material, required_qty in recipe.get("materials", {}).items():
            character.remove_item(material, required_qty)
        character.spirit_stones -= cost

        # 3. 动态成功率判定 (遵循你的设计原则)
        base_success_rate = 0.6 # 基础成功率
        # (可以加入更多影响因素：炼丹等级, 气运, 炼丹炉等)
        luck_bonus = character.stats.luck * 0.01 # 气运加成
        final_success_rate = min(0.95, base_success_rate + luck_bonus)

        # 4. 丰富的结果层次
        roll = random.random()
        message = f"你将药材投入丹炉，催动真火，开始炼制【{pill_name}】...\n\n"

        if roll <= final_success_rate * 0.1: # 大成功 (10%概率)
            num_pills = random.randint(2, 5)
            character.add_item(pill_name, num_pills, "丹药", recipe.get("效果", ""))
            message += f"丹炉霞光四射，丹香扑鼻！你福至心灵，一炉竟炼出了 {num_pills} 颗极品【{pill_name}】！"
        elif roll <= final_success_rate: # 成功
            character.add_item(pill_name, 1, "丹药", recipe.get("效果", ""))
            message += f"丹炉嗡嗡作响，片刻后归于平静。一枚圆润的【{pill_name}】已然炼成！"
        else: # 失败
            message += f"突然，丹炉内传来一声闷响，一股焦糊味弥漫开来。唉，一炉珍贵的药材就此报废..."
        
        await self.db_manager.save_character(character)
        return {"success": True, "message": message}