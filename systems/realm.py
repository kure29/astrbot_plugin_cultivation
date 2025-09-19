# astrbot_plugin_cultivation/systems/realm.py

import random
from typing import Dict, Any, Optional
from ..database.db_manager import DatabaseManager
from ..utils.llm_utils import LLMUtils
from ..models.character import Character
from ..utils.constants import REALMS, SPIRIT_ROOTS

class RealmSystem:
    """境界系统处理类"""
    
    def __init__(self, db_manager: DatabaseManager, llm_utils: Optional[LLMUtils] = None):
        self.db_manager = db_manager
        self.llm_utils = llm_utils

    async def attempt_breakthrough(self, character: Character) -> Dict[str, Any]:
        """尝试境界突破"""
        current_level = character.level
        current_realm = character.get_major_realm()
        
        # 检查是否可以突破
        breakthrough_info = self._get_breakthrough_requirements(current_level)
        if not breakthrough_info:
            return {
                "success": False,
                "message": "当前等级无法突破，请继续修炼提升等级。"
            }
        
        # 检查突破条件
        requirements_check = self._check_breakthrough_requirements(character, breakthrough_info)
        if not requirements_check["can_breakthrough"]:
            return {
                "success": False,
                "message": requirements_check["message"]
            }
        
        # 进行突破尝试
        breakthrough_result = await self._perform_breakthrough(character, breakthrough_info)
        
        return breakthrough_result

    def _get_breakthrough_requirements(self, level: int) -> Optional[Dict[str, Any]]:
        """获取突破要求"""
        breakthrough_levels = {
            10: {
                "from_realm": "凡人",
                "to_realm": "炼气期",
                "requires_tribulation": False,
                "spirit_stones_cost": 500,
                "required_items": [],
                "base_success_rate": 0.8
            },
            25: {
                "from_realm": "炼气期", 
                "to_realm": "筑基期",
                "requires_tribulation": True,
                "spirit_stones_cost": 2000,
                "required_items": ["筑基丹"],
                "base_success_rate": 0.6
            },
            40: {
                "from_realm": "筑基期",
                "to_realm": "金丹期", 
                "requires_tribulation": True,
                "spirit_stones_cost": 5000,
                "required_items": ["结丹灵药"],
                "base_success_rate": 0.4
            },
            60: {
                "from_realm": "金丹期",
                "to_realm": "元婴期",
                "requires_tribulation": True,
                "spirit_stones_cost": 10000,
                "required_items": ["破婴丹"],
                "base_success_rate": 0.3
            }
        }
        
        return breakthrough_levels.get(level)

    def _check_breakthrough_requirements(self, character: Character, breakthrough_info: Dict[str, Any]) -> Dict[str, Any]:
        """检查突破条件是否满足"""
        # 检查灵石
        spirit_stones_cost = breakthrough_info["spirit_stones_cost"]
        if character.spirit_stones < spirit_stones_cost:
            return {
                "can_breakthrough": False,
                "message": f"突破需要 {spirit_stones_cost} 灵石，你当前只有 {character.spirit_stones} 灵石。"
            }
        
        # 检查必需物品
        required_items = breakthrough_info["required_items"]
        if required_items:
            for item_name in required_items:
                if not character.has_item(item_name):
                    return {
                        "can_breakthrough": False,
                        "message": f"突破需要 {item_name}，请先获得此物品。"
                    }
        
        return {"can_breakthrough": True}

    async def _perform_breakthrough(self, character: Character, breakthrough_info: Dict[str, Any]) -> Dict[str, Any]:
        """执行突破过程"""
        old_realm = breakthrough_info["from_realm"]
        new_realm = breakthrough_info["to_realm"]
        
        # 消耗资源
        character.spirit_stones -= breakthrough_info["spirit_stones_cost"]
        
        # 消耗必需物品
        for item_name in breakthrough_info["required_items"]:
            character.remove_item(item_name, 1)
        
        # 计算成功率
        success_rate = self._calculate_breakthrough_success_rate(character, breakthrough_info)
        
        # 判断是否需要渡劫
        tribulation_success = True
        if breakthrough_info["requires_tribulation"]:
            tribulation_result = await self._perform_tribulation(character, new_realm)
            tribulation_success = tribulation_result["success"]
        
        # 判断突破是否成功
        breakthrough_success = random.random() < success_rate and tribulation_success
        
        if breakthrough_success:
            # 突破成功
            character.realm = new_realm
            character.stats.max_hp += 100
            character.stats.max_qi += 50
            character.stats.attack += 20
            character.stats.defense += 15
            character.stats.hp = character.stats.max_hp  # 突破后满血满蓝
            character.stats.qi = character.stats.max_qi
            
            # 生成突破成功描述
            breakthrough_desc = ""
            if self.llm_utils:
                try:
                    breakthrough_desc = await self.llm_utils.generate_breakthrough_description(
                        character, old_realm, new_realm, True
                    )
                except Exception:
                    # LLM生成失败时使用默认描述
                    breakthrough_desc = f"{character.name}盘坐修炼，突然间天地灵气疯狂涌入体内。经过一番苦战，终于冲破了境界桎梏，从{old_realm}成功突破至{new_realm}！"
            else:
                breakthrough_desc = f"突破成功！{character.name}从{old_realm}成功突破至{new_realm}！"
            
            message = f"【境界突破成功】\n\n"
            message += f"境界提升：{old_realm} → {new_realm}\n"
            message += f"属性提升：\n"
            message += f"  生命值上限 +100\n"
            message += f"  真元上限 +50\n"
            message += f"  攻击力 +20\n"
            message += f"  防御力 +15\n\n"
            message += breakthrough_desc
            
            return {
                "success": True,
                "level_changed": True,
                "message": message
            }
        else:
            # 突破失败
            failure_reason = "渡劫失败" if breakthrough_info["requires_tribulation"] and not tribulation_success else "境界感悟不足"
            
            # 生成突破失败描述
            breakthrough_desc = ""
            if self.llm_utils:
                try:
                    breakthrough_desc = await self.llm_utils.generate_breakthrough_description(
                        character, old_realm, new_realm, False
                    )
                except Exception:
                    # LLM生成失败时使用默认描述
                    breakthrough_desc = f"{character.name}尝试冲击更高境界，但在关键时刻功力不继，突破失败。虽有遗憾，但此次经历让你对{new_realm}的门槛有了更深理解。"
            else:
                breakthrough_desc = f"突破失败！{failure_reason}，请继续努力修炼。"
            
            message = f"【境界突破失败】\n\n"
            message += f"失败原因：{failure_reason}\n"
            message += f"消耗的资源不会返还，请继续努力！\n\n"
            message += breakthrough_desc
            
            return {
                "success": False,
                "level_changed": False,
                "message": message
            }

    def _calculate_breakthrough_success_rate(self, character: Character, breakthrough_info: Dict[str, Any]) -> float:
        """计算突破成功率"""
        base_rate = breakthrough_info["base_success_rate"]
        
        # 灵根影响
        spirit_root_bonus = SPIRIT_ROOTS[character.spirit_root]['efficiency'] - 1.0
        spirit_root_factor = min(spirit_root_bonus * 0.2, 0.3)  # 灵根最多提供30%加成
        
        # 气运影响
        luck_factor = (character.stats.luck - 50) * 0.002  # 气运每点相对50的差值提供0.2%成功率
        
        # 等级影响（超过突破等级的额外等级提供小幅加成）
        level_bonus = max(0, character.level - breakthrough_info.get("min_level", character.level)) * 0.01
        
        final_rate = base_rate + spirit_root_factor + luck_factor + level_bonus
        return max(0.1, min(0.95, final_rate))  # 成功率限制在10%-95%之间

    async def _perform_tribulation(self, character: Character, target_realm: str) -> Dict[str, Any]:
        """执行渡劫过程"""
        tribulation_types = {
            "筑基期": "筑基天劫",
            "金丹期": "金丹雷劫", 
            "元婴期": "元婴心魔劫"
        }
        
        tribulation_type = tribulation_types.get(target_realm, "未知天劫")
        
        # 渡劫成功率计算
        base_success_rate = 0.7
        
        # 生命值和真元状态影响
        health_factor = character.stats.hp / character.stats.max_hp
        qi_factor = character.stats.qi / character.stats.max_qi
        condition_factor = (health_factor + qi_factor) / 2 - 0.5  # 状态好时加成，状态差时减成
        
        # 灵根影响
        spirit_root_factor = (SPIRIT_ROOTS[character.spirit_root]['efficiency'] - 1.0) * 0.1
        
        # 气运影响（渡劫时气运很重要）
        luck_factor = (character.stats.luck - 50) * 0.003
        
        final_success_rate = base_success_rate + condition_factor + spirit_root_factor + luck_factor
        final_success_rate = max(0.2, min(0.9, final_success_rate))  # 限制在20%-90%
        
        success = random.random() < final_success_rate
        
        # 生成渡劫描述
        tribulation_desc = ""
        if self.llm_utils:
            try:
                tribulation_desc = await self.llm_utils.generate_tribulation_description(
                    character, tribulation_type, success
                )
            except Exception:
                # LLM生成失败时使用默认描述
                if success:
                    tribulation_desc = f"乌云密布，雷声阵阵。{character.name}毫不畏惧，直面天劫。经过一番惊心动魄的较量，终于成功渡过{tribulation_type}！"
                else:
                    tribulation_desc = f"{tribulation_type}威力超出预期，{character.name}虽全力应对，但终究功力不足，渡劫失败。好在性命无虞，来日可期。"
        else:
            if success:
                tribulation_desc = f"成功渡过{tribulation_type}！"
            else:
                tribulation_desc = f"渡劫失败，{tribulation_type}威力太强。"
        
        if not success:
            # 渡劫失败，受到伤害
            damage = character.stats.max_hp // 3
            character.stats.hp = max(1, character.stats.hp - damage)
        
        return {
            "success": success,
            "tribulation_type": tribulation_type,
            "description": tribulation_desc
        }

    def get_realm_info(self, realm: str) -> Dict[str, Any]:
        """获取境界信息"""
        return REALMS.get(realm, {
            "name": realm,
            "description": "未知境界",
            "level_range": (1, 100),
            "lifespan": 100
        })