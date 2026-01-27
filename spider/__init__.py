"""爬虫模块统一导出

提供统一的爬虫接口，支持多平台扩展
"""

# 注意：在包初始化时，使用相对导入以避免循环导入问题
# 外部调用时使用：from spider import BaseSpider

# 导入基础类和管理器（首先导入，避免循环导入）
from .base_spider import BaseSpider
from .spider_manager import SpiderManager

# 导入现有爬虫（保持向后兼容）
from .tender_spider import ZheJiangTenderSpider, run_all_spiders

# 导入新平台爬虫
try:
    from .platforms.hangzhou import HangZhouTenderSpider
except ImportError as e:
    # 如果相对导入失败，尝试绝对导入
    try:
        from spider.platforms.hangzhou import HangZhouTenderSpider
    except ImportError as e2:
        # 导入失败时记录错误，但不阻止整个包的加载
        try:
            from utils.log import log
            log.warning(f"导入杭州市爬虫失败（相对导入: {str(e)}, 绝对导入: {str(e2)}），将只显示浙江省平台")
        except:
            pass  # 如果日志也失败，静默忽略
        HangZhouTenderSpider = None

try:
    from .platforms.jiaxing import JiaXingTenderSpider
except ImportError as e:
    # 如果相对导入失败，尝试绝对导入
    try:
        from spider.platforms.jiaxing import JiaXingTenderSpider
    except ImportError as e2:
        # 导入失败时记录错误，但不阻止整个包的加载
        try:
            from utils.log import log
            log.warning(f"导入嘉兴市爬虫失败（相对导入: {str(e)}, 绝对导入: {str(e2)}），将只显示其他平台")
        except:
            pass  # 如果日志也失败，静默忽略
        JiaXingTenderSpider = None

try:
    from .platforms.ningbo import NingBoTenderSpider
except ImportError as e:
    # 如果相对导入失败，尝试绝对导入
    try:
        from spider.platforms.ningbo import NingBoTenderSpider
    except ImportError as e2:
        # 导入失败时记录错误，但不阻止整个包的加载
        try:
            from utils.log import log
            log.warning(f"导入宁波市爬虫失败（相对导入: {str(e)}, 绝对导入: {str(e2)}），将只显示其他平台")
        except:
            pass  # 如果日志也失败，静默忽略
        NingBoTenderSpider = None

try:
    from .platforms.shaoxing import ShaoXingTenderSpider
except ImportError as e:
    try:
        from spider.platforms.shaoxing import ShaoXingTenderSpider
    except ImportError as e2:
        try:
            from utils.log import log
            log.warning(f"导入绍兴市爬虫失败（相对导入: {str(e)}, 绝对导入: {str(e2)}），将只显示其他平台")
        except:
            pass
        ShaoXingTenderSpider = None

try:
    from .platforms.huzhou import HuZhouTenderSpider
except ImportError as e:
    try:
        from spider.platforms.huzhou import HuZhouTenderSpider
    except ImportError as e2:
        try:
            from utils.log import log
            log.warning(f"导入湖州市爬虫失败（相对导入: {str(e)}, 绝对导入: {str(e2)}），将只显示其他平台")
        except:
            pass
        HuZhouTenderSpider = None

try:
    from .platforms.yiwu import YiWuTenderSpider
except ImportError as e:
    try:
        from spider.platforms.yiwu import YiWuTenderSpider
    except ImportError as e2:
        try:
            from utils.log import log
            log.warning(f"导入义乌市爬虫失败（相对导入: {str(e)}, 绝对导入: {str(e2)}），将只显示其他平台")
        except:
            pass
        YiWuTenderSpider = None

try:
    from .platforms.lishui import LiShuiTenderSpider
except ImportError as e:
    try:
        from spider.platforms.lishui import LiShuiTenderSpider
    except ImportError as e2:
        try:
            from utils.log import log
            log.warning(f"导入丽水市爬虫失败（相对导入: {str(e)}, 绝对导入: {str(e2)}），将只显示其他平台")
        except:
            pass
        LiShuiTenderSpider = None

__all__ = [
    # 基础类和管理器
    "BaseSpider",
    "SpiderManager",
    
    # 现有爬虫（向后兼容）
    "ZheJiangTenderSpider",
    "run_all_spiders",
]

# 添加新平台爬虫到导出列表（如果存在）
if HangZhouTenderSpider is not None:
    __all__.append("HangZhouTenderSpider")

if JiaXingTenderSpider is not None:
    __all__.append("JiaXingTenderSpider")

if NingBoTenderSpider is not None:
    __all__.append("NingBoTenderSpider")

if ShaoXingTenderSpider is not None:
    __all__.append("ShaoXingTenderSpider")

if HuZhouTenderSpider is not None:
    __all__.append("HuZhouTenderSpider")

if YiWuTenderSpider is not None:
    __all__.append("YiWuTenderSpider")

if LiShuiTenderSpider is not None:
    __all__.append("LiShuiTenderSpider")
