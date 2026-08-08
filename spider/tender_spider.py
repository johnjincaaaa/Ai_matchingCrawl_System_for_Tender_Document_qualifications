# 兼容相对导入和绝对导入
try:
    from .base_spider import BaseSpider
    from .spider_manager import SpiderManager
except ImportError:
    # 如果相对导入失败，尝试绝对导入（用于直接运行脚本时）
    from spider.base_spider import BaseSpider
    from spider.spider_manager import SpiderManager


class ZheJiangTenderSpider(BaseSpider):
    """浙江省招标网爬虫（支持多分类均衡爬取）

    说明：
    - daily_limit 为可选参数，不传时使用 config 中的默认值；
    - 通过 **kwargs 兼容旧代码中可能传入的多余关键词参数，避免出现
      "got an unexpected keyword argument" 之类的错误，使调用更健壮。
    """
    PLATFORM_NAME = "浙江省政府采购网"
    PLATFORM_CODE = "zhejiang"
    
    BASE_URL = "https://zfcg.czt.zj.gov.cn"

    def __init__(self, daily_limit=None, days_before=None, gov_cities=None, **kwargs):
        # 调用父类初始化
        super().__init__(daily_limit=daily_limit, days_before=days_before, **kwargs)
        self.gov_cities = gov_cities
        # 兼容性处理：忽略未使用的关键字参数，防止旧脚本或外部调用传入多余参数时报错。
        # 说明：政采云已解耦为「exe 下载」与「系统入库」两条独立链路——
        #   - exe 下载：run_zcy_download.py 每日 19:00 定时跑（获取编号→批量下载→合并 total_下载记录.csv）；
        #   - 系统入库：本类 run() 只读 total_下载记录.csv，按数量/时间范围入库，不触发 exe。


    def run(self):
        """读取政采云 total_下载记录.csv，按数量/时间范围去重入库（不触发 exe）。"""
        from spider.zcy_external import run_zcy_external_spider

        projects = run_zcy_external_spider(
            db=self.db,
            daily_limit=self.daily_limit,
            days_before=self.days_before,
            gov_cities=self.gov_cities,
        )
        self.crawled_count = len(projects)
        return projects


def run_all_spiders(days_before=None, enabled_platforms=None):
    """运行所有爬虫（保持向后兼容）
    
    Args:
        days_before: 时间间隔，爬取最近N天内的文件（如10表示爬取最近10天内的文件，从今天往前10天），None表示只爬取当日文件
        enabled_platforms: 启用的平台列表（None表示全部启用）
    
    Returns:
        list: 所有爬虫返回的项目列表（合并后）
    """
    # 使用新的 SpiderManager 统一管理
    return SpiderManager.run_all_spiders(days_before=days_before, enabled_platforms=enabled_platforms)


# 自动注册浙江省爬虫
SpiderManager.register(ZheJiangTenderSpider)