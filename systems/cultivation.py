import random
from typing import Dict, Any
from ..models.character import Character
from ..database.db_manager import DatabaseManager
from ..utils.llm_utils import LLMUtils
from ..utils.constants import CULTIVATION_SETTINGS, RANDOM_EVENTS


class CultivationSystem:
    """修炼系统"""

    def __init__(self, db_manager: DatabaseManager, llm_utils: LLMUtils):
        self.db_manager = db_manager
        self.llm_utils = llm_utils

    async def perform_cultivation(self, character: Character) -> Dict[str, Any]:
        """执行修炼 (已适配动态收益)"""
        
        # 动态计算真元消耗
        qi_cost = int(CULTIVATION_SETTINGS["base_qi_cost"] + (character.level * CULTIVATION_SETTINGS["qi_cost_level_multiplier"]))
        character.stats.qi -= qi_cost

        # 动态计算基础经验获得
        base_exp = int(CULTIVATION_SETTINGS["base_exp_gain"] + (character.level * CULTIVATION_SETTINGS["exp_gain_level_multiplier"]))
        spirit_root_multiplier = character.get_spirit_root_efficiency()

        # 随机波动
        variation = random.uniform(0.9, 1.1)
        exp_gained = int(base_exp * spirit_root_multiplier * variation)

        # 检查随机事件
        event_triggered = False
        event_message = ""

        for event_name, event_info in RANDOM_EVENTS["cultivation"].items():
            if random.random() < event_info["probability"]:
                event_triggered = True
                event_message = event_info["description"]

                # 应用事件效果
                effect = event_info["effect"]
                if effect["type"] == "exp_bonus":
                    exp_gained = int(exp_gained * effect["multiplier"])
                elif effect["type"] == "exp_penalty":
                    exp_gained = int(exp_gained * effect["multiplier"])
                break

        # 添加经验
        character.exp += exp_gained

        # 检查升级
        level_up_messages = character.level_up()

        # --- ↓↓↓ 此處是核心修正 ↓↓↓ ---
        # 生成修炼描述 (使用通用的 generate_text 方法)
        llm_prompt = f"为名为 {character.name}（境界：{character.get_realm_display()}），灵根为{character.spirit_root}的修士，生成一段修炼感悟的描述。本次修炼获得了{exp_gained}点经验。"
        cultivation_desc = await self.llm_utils.generate_text(llm_prompt, 80)
        # --- ↑↑↑ 修正結束 ↑↑↑ ---

        # 构建返回消息
        message = f"【修炼完成】\n\n"
        message += f"消耗真元：{qi_cost}点\n"
        message += f"获得经验：{exp_gained}点\n"
        message += f"当前真元：{character.stats.qi}/{character.stats.max_qi}\n\n"

        if event_triggered:
            message += f"特殊事件：{event_message}\n\n"

        message += f"{cultivation_desc}\n"

        if level_up_messages:
            message += "\n" + "\n".join(level_up_messages)

        return {
            "success": True,
            "exp_gained": exp_gained,
            "event": event_triggered,
            "level_up": len(level_up_messages) > 0,
            "message": message
        }

    async def practice_technique(self, character: Character, technique_name: str) -> Dict[str, Any]:
        """修炼特定功法"""
        techniques = {
            "基础吐纳术": {
                "qi_cost": 20,
                "exp_multiplier": 1.2,
                "special_effect": "restore_qi",
                "description": "最基础的修炼功法，有助于真元循环"
            },
            "金刚体": {
                "qi_cost": 30,
                "exp_multiplier": 0.8,
                "special_effect": "defense_boost",
                "description": "炼体功法，增强防御能力"
            },
            "御风术": {
                "qi_cost": 25,
                "exp_multiplier": 1.0,
                "special_effect": "speed_boost",
                "description": "身法修炼，提升速度"
            }
        }

        if technique_name not in techniques:
            return {
                "success": False,
                "message": f"未知功法：{technique_name}"
            }

        technique = techniques[technique_name]
        qi_cost = technique["qi_cost"]

        if character.stats.qi < qi_cost:
            return {
                "success": False,
                "message": f"真元不足，修炼{technique_name}需要{qi_cost}点真元"
            }

        # 消耗真元
        character.stats.qi -= qi_cost

        # 计算经验
        base_exp = CULTIVATION_SETTINGS["exp_per_cultivation"]
        exp_gained = int(base_exp * technique["exp_multiplier"] * character.get_spirit_root_efficiency())
        character.exp += exp_gained

        # 应用特殊效果
        special_message = ""
        if technique["special_effect"] == "restore_qi":
            qi_restored = min(10, character.stats.max_qi - character.stats.qi)
            character.stats.qi += qi_restored
            special_message = f"真元循环顺畅，额外恢复{qi_restored}点真元"
        elif technique["special_effect"] == "defense_boost":
            character.stats.defense += 1
            special_message = "体魄得到锤炼，防御力永久+1"
        elif technique["special_effect"] == "speed_boost":
            character.stats.speed += 1
            special_message = "身法精进，速度永久+1"

        # 检查升级
        level_up_messages = character.level_up()

        message = f"【{technique_name}修炼完成】\n\n"
        message += f"功法描述：{technique['description']}\n"
        message += f"消耗真元：{qi_cost}点\n"
        message += f"获得经验：{exp_gained}点\n"

        if special_message:
            message += f"特殊效果：{special_message}\n"

        if level_up_messages:
            message += "\n" + "\n".join(level_up_messages)

        return {
            "success": True,
            "exp_gained": exp_gained,
            "message": message
        }

    async def enlightenment_cultivation(self, character: Character) -> Dict[str, Any]:
        """顿悟修炼（高级修炼方式）"""
        # 检查顿悟条件（需要高境界和运气）
        min_level = 20
        if character.level < min_level:
            return {
                "success": False,
                "message": f"顿悟修炼需要{min_level}级以上"
            }

        # 顿悟成功率受气运影响
        success_rate = 0.1 + (character.stats.luck * 0.005)

        if random.random() > success_rate:
            return {
                "success": False,
                "message": "尝试顿悟但心境不够，无法进入顿悟状态..."
            }

        # 顿悟成功，大量经验获得
        base_exp = CULTIVATION_SETTINGS["exp_per_cultivation"] * 5
        spirit_root_multiplier = character.get_spirit_root_efficiency()
        exp_gained = int(base_exp * spirit_root_multiplier)

        character.exp += exp_gained

        # 顿悟还有概率获得属性提升
        if random.random() < 0.3:
            stat_boost = random.choice(["attack", "defense", "speed", "luck"])
            if stat_boost == "attack":
                character.stats.attack += 2
                boost_message = "攻击力+2"
            elif stat_boost == "defense":
                character.stats.defense += 2
                boost_message = "防御力+2"
            elif stat_boost == "speed":
                character.stats.speed += 2
                boost_message = "速度+2"
            else:
                character.stats.luck += 2
                boost_message = "气运+2"
        else:
            boost_message = ""

        # 检查升级
        level_up_messages = character.level_up()

        # 生成顿悟描述
        enlightenment_desc = await self.llm_utils.generate_random_event("inspiration")

        message = f"【顿悟修炼成功】\n\n"
        message += f"获得经验：{exp_gained}点\n"

        if boost_message:
            message += f"属性提升：{boost_message}\n"

        message += f"\n{enlightenment_desc}\n"

        if level_up_messages:
            message += "\n" + "\n".join(level_up_messages)

        return {
            "success": True,
            "exp_gained": exp_gained,
            "enlightenment": True,
            "message": message
        }

    async def group_cultivation(self, character: Character, participants: int = 1) -> Dict[str, Any]:
        """集体修炼（多人修炼效率提升）"""
        if participants < 2:
            return await self.perform_cultivation(character)

        # 集体修炼效率提升，但消耗更多真元
        qi_cost = CULTIVATION_SETTINGS["base_cultivation_cost"] * (1 + participants * 0.2)

        if character.stats.qi < qi_cost:
            return {
                "success": False,
                "message": f"真元不足，集体修炼需要{int(qi_cost)}点真元"
            }

        character.stats.qi -= int(qi_cost)

        # 计算经验（集体修炼有加成）
        base_exp = CULTIVATION_SETTINGS["exp_per_cultivation"]
        group_multiplier = 1 + (participants - 1) * 0.15  # 每多一人增加15%效率
        spirit_root_multiplier = character.get_spirit_root_efficiency()

        exp_gained = int(base_exp * group_multiplier * spirit_root_multiplier)
        character.exp += exp_gained

        # 检查升级
        level_up_messages = character.level_up()

        message = f"【集体修炼完成】（{participants}人）\n\n"
        message += f"消耗真元：{int(qi_cost)}点\n"
        message += f"获得经验：{exp_gained}点（集体加成{int((group_multiplier - 1) * 100)}%）\n"
        message += f"与同道一起修炼，互相印证，修炼效率大增！\n"

        if level_up_messages:
            message += "\n" + "\n".join(level_up_messages)

        return {
            "success": True,
            "exp_gained": exp_gained,
            "group_bonus": True,
            "message": message
        }