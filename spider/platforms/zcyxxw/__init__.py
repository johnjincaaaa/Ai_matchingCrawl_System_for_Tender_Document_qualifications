"""浙江企业采购信息网（b.zhengcaiyun.cn）爬虫模块"""

# 兼容相对导入和绝对导入
try:
    from .spider import ZcyXxwTenderSpider
except ImportError:
    try:
        from spider.platforms.zcyxxw.spider import ZcyXxwTenderSpider
    except ImportError:
        ZcyXxwTenderSpider = None

__all__ = ["ZcyXxwTenderSpider"] if ZcyXxwTenderSpider else []
