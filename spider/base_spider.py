"""爬虫基础类

提供所有爬虫需要实现的统一接口和通用功能
"""

from abc import ABC, abstractmethod
from utils.db import get_db, TenderProject
from utils.log import log
from config import SPIDER_CONFIG


class BaseSpider(ABC):
    """爬虫基础类
    
    所有平台爬虫必须继承此类并实现 run() 方法
    
    属性:
        PLATFORM_NAME: 平台名称（必填）
        PLATFORM_CODE: 平台代码（必填，唯一标识）
    """
    
    PLATFORM_NAME: str = ""
    PLATFORM_CODE: str = ""
    
    def __init__(self, daily_limit=None, days_before=None, **kwargs):
        """
        初始化爬虫
        
        Args:
            daily_limit: 每日爬取限制数量（None时使用全局配置）
            days_before: 爬取最近N天内的文件（None表示只爬取当日）
            **kwargs: 其他平台特定参数（兼容性参数，可忽略）
        """
        self.db = next(get_db())
        # 每日总爬取限制：优先使用传入的 daily_limit，否则回退到配置
        self.daily_limit = daily_limit if daily_limit is not None else SPIDER_CONFIG["daily_limit"]
        # 时间间隔：爬取最近N天内的文件（如10表示爬取最近10天内的文件，从今天往前10天）
        # None表示不限制，只爬取当日文件
        self.days_before = days_before
        # 爬取计数（供外部访问）
        self.crawled_count = 0
        # 重试次数
        self.max_retries = SPIDER_CONFIG["anti_crawl"].get("retry_times", 3)
    
    @abstractmethod
    def run(self):
        """
        执行爬虫主逻辑（必须实现）
        
        Returns:
            list: 爬取到的项目列表，每个项目为 TenderProject 对象
        """
        pass
    
    def get_platform_info(self):
        """
        获取平台信息
        
        Returns:
            dict: {
                "name": "平台名称",
                "code": "平台代码"
            }
        """
        return {
            "name": self.PLATFORM_NAME,
            "code": self.PLATFORM_CODE
        }
    
    def _is_duplicate(self, project_id):
        """
        检查项目是否已存在（通用方法）
        
        Args:
            project_id: 项目ID
            
        Returns:
            bool: True表示已存在，False表示不存在
        """
        if not project_id:
            return False
        return self.db.query(TenderProject).filter(
            TenderProject.project_id == project_id
        ).first() is not None
    
    def _check_platform_config(self):
        """
        检查平台配置是否正确（子类可覆盖）
        
        Returns:
            bool: True表示配置正确
        """
        if not self.PLATFORM_NAME or not self.PLATFORM_CODE:
            log.error(f"爬虫类 {self.__class__.__name__} 未设置 PLATFORM_NAME 或 PLATFORM_CODE")
            return False
        return True
