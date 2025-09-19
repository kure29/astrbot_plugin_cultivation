# astrbot_plugin_cultivation/main.py

import json
import os
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import AstrBotConfig
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

from .database.db_manager import DatabaseManager
from .utils.llm_utils import LLMUtils
# --- ↓↓↓ 核心修正：导入新的 Config 管理器和常量 ↓↓↓ ---
from .utils.config_manager import config
from .utils.constants import (LOCATIONS, MONSTERS, ITEMS, ALCHEMY_DATA,
                              BREAKTHROUGH_REQUIREMENTS, RECIPES_DATA, GATHERING_DATA)
# --- ↑↑↑ 修正结束 ↑↑↑ ---
from .commands.basic import BasicCommands
from .commands.cultivation import CultivationCommands
from .commands.exploration import ExplorationCommands
from .systems.crafting_system import CraftingSystem
from .systems.gathering_system import GatheringSystem

@register("astrbot_plugin_cultivation", "kure29", "基於AstrBot的史詩級修真RPG遊戲插件", "2.0.0", "https://github.com/kure29/astrbot_plugin_cultivation")
class CultivationPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config_manager = config # <-- 使用导入的config实例
        self.db_manager = DatabaseManager()
        self.llm_utils = LLMUtils(context)
        self.basic_commands = BasicCommands(self.db_manager, self.llm_utils)
        self.cultivation_commands = CultivationCommands(self.db_manager, self.llm_utils)
        self.exploration_commands = ExplorationCommands(self.db_manager, self.llm_utils)
        self.crafting_system = CraftingSystem(self.db_manager)
        self.gathering_system = GatheringSystem(self.db_manager)

        logger.info("修仙RPG完整版插件初始化成功")

    async def initialize(self):
        await self.db_manager.init_database()
        # The new config_manager loads data automatically on import,
        # so we can remove the manual loading calls here.
        logger.info("修仙插件数据加载完成。")

    # ... (the rest of the main.py file remains the same) ...
    # --- 指令註冊 ---
    @filter.command("前往")
    async def travel(self, event: AstrMessageEvent, *, destination: str = ""):
        async for result in self.exploration_commands.travel_to(event, destination.strip()): yield result

    @filter.command("开始游戏", alias={'创建角色', '开始修仙'})
    async def start_game(self, event: AstrMessageEvent, *, character_name: str = ""):
        async for result in self.basic_commands.start_game(event, character_name): yield result

    @filter.command("帮助", alias={'指令', '菜单'})
    async def help(self, event: AstrMessageEvent):
        async for result in self.basic_commands.help(event): yield result

    @filter.command("状态", alias={'信息', '属性'})
    async def status(self, event: AstrMessageEvent):
        async for result in self.basic_commands.status(event): yield result

    @filter.command("储物袋", alias={'物品', '道具', '背包'})
    async def inventory(self, event: AstrMessageEvent):
        async for result in self.basic_commands.inventory(event): yield result

    @filter.command("签到")
    async def daily_checkin(self, event: AstrMessageEvent):
        async for result in self.basic_commands.daily_checkin(event): yield result

    @filter.command("排行榜", alias={'排名', '榜单'})
    async def leaderboard(self, event: AstrMessageEvent):
        async for result in self.basic_commands.leaderboard(event): yield result

    @filter.command("战力", alias={'评估', '评级'})
    async def power_rating(self, event: AstrMessageEvent):
        async for result in self.basic_commands.power_rating(event): yield result

    @filter.command("改名", alias={'重命名', '更换道号'})
    async def rename(self, event: AstrMessageEvent, new_name: str):
        async for result in self.basic_commands.rename(event, new_name): yield result

    @filter.command("使用", alias={'服用', '装备', '穿戴'})
    async def use_item(self, event: AstrMessageEvent, *, args: str):
        async for result in self.basic_commands.use_item(event, args): yield result

    @filter.command("闭关", alias={'練功', '打坐'})
    async def start_retreat(self, event: AstrMessageEvent):
        async for result in self.cultivation_commands.start_retreat(event): yield result

    @filter.command("出关", alias={'结束闭关'})
    async def end_retreat(self, event: AstrMessageEvent):
        async for result in self.cultivation_commands.end_retreat(event): yield result

    @filter.command("炼丹")
    async def alchemy(self, event: AstrMessageEvent, pill_type: str = ""):
        async for result in self.cultivation_commands.alchemy(event, pill_type): yield result

    @filter.command("境界", alias={'等级系统', '修为'})
    async def realm_info(self, event: AstrMessageEvent):
        async for result in self.cultivation_commands.show_realm_info(event): yield result

    @filter.command("地图", alias={'区域', '位置'})
    async def map_info(self, event: AstrMessageEvent):
        async for result in self.exploration_commands.show_map(event): yield result

    @filter.command("探索", alias={'冒险', '历练'})
    async def explore(self, event: AstrMessageEvent):
        async for result in self.exploration_commands.explore(event): yield result

    @filter.command("战斗", alias={'攻击', '出手'})
    async def attack(self, event: AstrMessageEvent):
        character = await self.db_manager.get_character(event.get_sender_id())
        if not character or not character.combat_state:
            yield event.plain_result("你当前不在战斗中。")
            return
        combat_data = json.loads(character.combat_state)
        async for result in self.combat_system.player_attack(character, combat_data):
            yield result

    @filter.command("逃跑", alias={'逃离', '退避'})
    async def flee(self, event: AstrMessageEvent):
        character = await self.db_manager.get_character(event.get_sender_id())
        if not character or not character.combat_state:
            yield event.plain_result("你当前不在战斗中。")
            return
        async for result in self.combat_system.attempt_flee(character):
            yield result

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("重置数据")
    async def reset_data(self, event: AstrMessageEvent, confirm: str = ""):
        if confirm != "确认重置":
            yield event.plain_result("危险操作！使用 `/重置数据 确认重置` 来确认重置所有数据")
            return
        try:
            await self.db_manager.reset_all_data()
            yield event.plain_result("所有游戏数据已重置")
        except Exception as e:
            logger.error(f"重置数据失败: {e}")
            yield event.plain_result(f"重置数据失败: {str(e)}")

    @filter.command("商店", alias={'shop'})
    async def shop(self, event: AstrMessageEvent, action: str = "", item_name: str = "", quantity: int = 1):
        async for result in self.basic_commands.shop(event, action, item_name, quantity): yield result

    @filter.command("购买", alias={'buy'})
    async def buy(self, event: AstrMessageEvent, item_name: str = "", quantity: int = 1):
        async for result in self.basic_commands.shop(event, "购买", item_name, quantity): yield result

    @filter.command("锻造")
    async def craft_item(self, event: AstrMessageEvent, *, item_name: str = ""):
        character = await self.db_manager.get_character(event.get_sender_id())
        if not character: yield event.plain_result("你尚未踏入仙途。"); return
        if not item_name: yield event.plain_result("你要锻造何物？\n(指令格式: /锻造 [装备名])"); return
        result = await self.crafting_system.perform_crafting(character, item_name.strip())
        yield event.plain_result(result["message"])

    @filter.command("采集")
    async def gather_resources(self, event: AstrMessageEvent):
        character = await self.db_manager.get_character(event.get_sender_id())
        if not character: yield event.plain_result("你尚未踏入仙途。"); return
        result = await self.gathering_system.perform_gathering(character)
        yield event.plain_result(result["message"])

    async def terminate(self):
        if hasattr(self, 'db_manager'):
            await self.db_manager.close()
        logger.info("修仙RPG插件已卸载")