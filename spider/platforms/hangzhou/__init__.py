"""杭州市招标平台爬虫模块"""

# 兼容相对导入和绝对导入
try:
    from .spider import HangZhouTenderSpider
except ImportError:
    try:
        from spider.platforms.hangzhou.spider import HangZhouTenderSpider
    except ImportError:
        HangZhouTenderSpider = None

__all__ = ["HangZhouTenderSpider"] if HangZhouTenderSpider is not None else []
