"""衢州市平台爬虫模块"""

# 兼容相对导入和绝对导入
try:
    from .spider import QuZhouTenderSpider
except ImportError:
    try:
        from spider.platforms.quzhou.spider import QuZhouTenderSpider
    except ImportError:
        QuZhouTenderSpider = None

__all__ = ["QuZhouTenderSpider"] if QuZhouTenderSpider else []
