"""湖州市平台爬虫模块"""

# 兼容相对导入和绝对导入
try:
    from .spider import HuZhouTenderSpider
except ImportError:
    try:
        from spider.platforms.huzhou.spider import HuZhouTenderSpider
    except ImportError:
        HuZhouTenderSpider = None

__all__ = ["HuZhouTenderSpider"] if HuZhouTenderSpider else []
