"""嘉兴市招标平台爬虫包初始化"""

try:
    from .spider import JiaXingTenderSpider
    __all__ = ['JiaXingTenderSpider']
except ImportError as e:
    import logging
    logging.warning(f"导入嘉兴市爬虫失败: {str(e)}")
    __all__ = []
