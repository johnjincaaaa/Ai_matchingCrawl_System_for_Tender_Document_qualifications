"""义乌市平台爬虫模块"""

# 兼容相对导入和绝对导入
try:
    from .spider import YiWuTenderSpider
except ImportError:
    try:
        from spider.platforms.yiwu.spider import YiWuTenderSpider
    except ImportError:
        YiWuTenderSpider = None

__all__ = ["YiWuTenderSpider"] if YiWuTenderSpider else []
