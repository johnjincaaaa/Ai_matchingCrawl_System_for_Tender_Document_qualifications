"""丽水市平台爬虫模块"""

# 兼容相对导入和绝对导入
try:
    from .spider import LiShuiTenderSpider
except ImportError:
    try:
        from spider.platforms.lishui.spider import LiShuiTenderSpider
    except ImportError:
        LiShuiTenderSpider = None

__all__ = ["LiShuiTenderSpider"] if LiShuiTenderSpider else []

