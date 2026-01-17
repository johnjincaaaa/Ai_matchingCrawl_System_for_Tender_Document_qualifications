"""爬虫管理器

负责爬虫的注册、发现、创建和统一调度
"""

from typing import List, Dict, Optional, Type
from utils.log import log
# 兼容相对导入和绝对导入
try:
    from .base_spider import BaseSpider
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    from spider.base_spider import BaseSpider


class SpiderManager:
    """爬虫管理器：负责注册、发现和调度爬虫
    
    使用示例:
        # 注册爬虫（自动注册）
        @SpiderManager.register
        class MySpider(BaseSpider):
            PLATFORM_CODE = "my_platform"
            ...
        
        # 或者手动注册
        SpiderManager.register(MySpider)
        
        # 获取爬虫类
        spider_class = SpiderManager.get_spider("my_platform")
        
        # 创建爬虫实例
        spider = SpiderManager.create_spider("my_platform", daily_limit=10)
        
        # 运行所有爬虫
        projects = SpiderManager.run_all_spiders(days_before=7)
    """
    
    _spiders: Dict[str, Type[BaseSpider]] = {}  # 注册的爬虫类字典
    
    @classmethod
    def register(cls, spider_class: Type[BaseSpider]):
        """
        注册爬虫类
        
        Args:
            spider_class: 爬虫类（必须继承BaseSpider）
            
        Returns:
            Type[BaseSpider]: 返回注册的爬虫类（支持装饰器用法）
            
        Raises:
            ValueError: 如果爬虫类无效或平台代码重复
        """
        if not issubclass(spider_class, BaseSpider):
            raise ValueError(f"爬虫类 {spider_class.__name__} 必须继承 BaseSpider")
        
        platform_code = spider_class.PLATFORM_CODE
        if not platform_code:
            raise ValueError(f"爬虫类 {spider_class.__name__} 未设置 PLATFORM_CODE")
        
        if platform_code in cls._spiders:
            log.warning(f"平台 {platform_code} 已注册，将覆盖现有爬虫类")
        
        cls._spiders[platform_code] = spider_class
        log.info(f"注册爬虫: {platform_code} ({spider_class.PLATFORM_NAME})")
        return spider_class
    
    @classmethod
    def unregister(cls, platform_code: str):
        """
        注销爬虫类
        
        Args:
            platform_code: 平台代码
        """
        if platform_code in cls._spiders:
            del cls._spiders[platform_code]
            log.info(f"注销爬虫: {platform_code}")
        else:
            log.warning(f"未找到要注销的爬虫: {platform_code}")
    
    @classmethod
    def get_spider(cls, platform_code: str) -> Optional[Type[BaseSpider]]:
        """
        获取爬虫类
        
        Args:
            platform_code: 平台代码
            
        Returns:
            Type[BaseSpider] 或 None
        """
        return cls._spiders.get(platform_code)
    
    @classmethod
    def list_spiders(cls) -> List[str]:
        """
        列出所有注册的爬虫平台代码
        
        Returns:
            List[str]: 平台代码列表
        """
        return list(cls._spiders.keys())
    
    @classmethod
    def get_spider_info(cls, platform_code: str) -> Optional[Dict]:
        """
        获取爬虫信息
        
        Args:
            platform_code: 平台代码
            
        Returns:
            dict 或 None: {
                "code": "平台代码",
                "name": "平台名称",
                "class": "爬虫类名"
            }
        """
        spider_class = cls.get_spider(platform_code)
        if not spider_class:
            return None
        
        return {
            "code": platform_code,
            "name": spider_class.PLATFORM_NAME,
            "class": spider_class.__name__
        }
    
    @classmethod
    def list_all_spider_info(cls) -> List[Dict]:
        """
        列出所有爬虫信息
        
        Returns:
            List[Dict]: 爬虫信息列表
        """
        return [
            cls.get_spider_info(code)
            for code in cls.list_spiders()
        ]
    
    @classmethod
    def create_spider(cls, platform_code: str, **kwargs) -> BaseSpider:
        """
        创建爬虫实例
        
        Args:
            platform_code: 平台代码
            **kwargs: 传递给爬虫构造函数的参数
            
        Returns:
            BaseSpider: 爬虫实例
            
        Raises:
            ValueError: 如果未找到平台爬虫
        """
        spider_class = cls.get_spider(platform_code)
        if not spider_class:
            available = ", ".join(cls.list_spiders()) or "无"
            raise ValueError(
                f"未找到平台爬虫: {platform_code}。"
                f"可用的平台: {available}"
            )
        
        try:
            spider = spider_class(**kwargs)
            # 检查平台配置
            if not spider._check_platform_config():
                log.warning(f"平台 {platform_code} 配置检查未通过，但继续执行")
            return spider
        except Exception as e:
            log.error(f"创建爬虫 {platform_code} 失败: {str(e)}")
            raise
    
    @classmethod
    def run_all_spiders(cls, days_before=None, enabled_platforms=None) -> List:
        """
        运行所有爬虫或指定平台爬虫
        
        Args:
            days_before: 时间间隔，爬取最近N天内的文件（None表示只爬取当日）
            enabled_platforms: 启用的平台列表（None表示全部启用）
            
        Returns:
            List: 所有爬虫返回的项目列表（合并后）
        """
        all_projects = []
        
        # 确定要运行的平台
        if enabled_platforms is None:
            enabled_platforms = cls.list_spiders()
        else:
            # 验证平台是否存在
            available = set(cls.list_spiders())
            requested = set(enabled_platforms)
            invalid = requested - available
            if invalid:
                log.warning(f"以下平台不存在，将被忽略: {', '.join(invalid)}")
            enabled_platforms = list(requested & available)
        
        if not enabled_platforms:
            log.warning("没有可运行的爬虫平台")
            return all_projects
        
        log.info(f"准备运行 {len(enabled_platforms)} 个平台爬虫: {', '.join(enabled_platforms)}")
        
        # 依次运行每个平台的爬虫
        for platform_code in enabled_platforms:
            try:
                log.info(f"=" * 50)
                log.info(f"开始运行平台: {platform_code}")
                log.info(f"=" * 50)
                
                spider = cls.create_spider(platform_code, days_before=days_before)
                projects = spider.run()
                
                all_projects.extend(projects)
                
                log.info(f"平台 {platform_code} 爬取完成，获取 {len(projects)} 个项目")
                
            except Exception as e:
                log.error(f"平台 {platform_code} 爬取失败: {str(e)}", exc_info=True)
                # 继续运行其他平台，不中断整个流程
                continue
        
        log.info(f"=" * 50)
        log.info(f"所有爬虫运行完成，总共获取 {len(all_projects)} 个项目")
        log.info(f"=" * 50)
        
        return all_projects
    
    @classmethod
    def is_registered(cls, platform_code: str) -> bool:
        """
        检查平台是否已注册
        
        Args:
            platform_code: 平台代码
            
        Returns:
            bool: True表示已注册
        """
        return platform_code in cls._spiders
