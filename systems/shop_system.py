from typing import Dict, Any
from ..models.character import Character
from ..utils.constants import SHOPS, ITEMS

class ShopSystem:
    """商店系统"""

    def __init__(self, db_manager, llm_utils):
        self.db_manager = db_manager
        self.llm_utils = llm_utils

    def get_shop_info(self, location_name: str) -> Dict[str, Any]:
        """获取商店信息"""
        return SHOPS.get(location_name)

    def format_shop_inventory(self, shop_info: Dict[str, Any]) -> str:
        """格式化商店库存信息"""
        if not shop_info:
            return "此地没有商店。"

        inventory_text = f"【{shop_info['name']}】\n\n"
        inventory_text += "商品列表 (使用 /商店 购买 [商品名] [数量])：\n"
        for item in shop_info["inventory"]:
            inventory_text += f"- {item['item_name']}: {item['price']} 灵石 (库存: {item['stock']})\n"
        
        return inventory_text

    async def buy_item(self, character: Character, item_name: str, quantity: int) -> Dict[str, Any]:
        """购买物品"""
        shop_info = self.get_shop_info(character.location)
        if not shop_info:
            return {"success": False, "message": "你所在的地方没有商店。"}

        item_to_buy = None
        for item in shop_info["inventory"]:
            if item["item_name"] == item_name:
                item_to_buy = item
                break

        if not item_to_buy:
            return {"success": False, "message": f"“{shop_info['name']}”不销售“{item_name}”。"}

        if item_to_buy["stock"] < quantity:
            return {"success": False, "message": f"“{item_name}”库存不足，仅剩 {item_to_buy['stock']} 件。"}

        total_cost = item_to_buy["price"] * quantity
        if character.spirit_stones < total_cost:
            return {"success": False, "message": f"灵石不足，购买 {quantity} 件“{item_name}”需要 {total_cost} 灵石。"}

        # 更新玩家数据
        character.spirit_stones -= total_cost
        
        item_info = ITEMS.get(item_name, {})
        character.add_item(
            item_name=item_name,
            quantity=quantity,
            item_type=item_info.get("type", "道具"),
            description=item_info.get("description", ""),
            effect=item_info.get("effect")
        )

        # 更新库存 (简单实现，不持久化)
        item_to_buy["stock"] -= quantity

        return {
            "success": True,
            "message": f"购买成功！花费 {total_cost} 灵石购买了 {quantity} 件“{item_name}”。"
        }