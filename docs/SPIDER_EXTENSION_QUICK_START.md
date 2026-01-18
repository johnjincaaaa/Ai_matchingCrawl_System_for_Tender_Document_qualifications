# 爬虫扩展快速参考指南

## 一、方案概述

本项目已实现可扩展的爬虫架构，支持快速添加新的招标平台。新平台只需要实现一个可执行请求函数和一个爬虫类即可集成到系统中。

## 二、核心组件

### 2.1 BaseSpider（基础爬虫类）

所有爬虫必须继承的基类，提供统一接口：

```python
from spider.base_spider import BaseSpider

class YourSpider(BaseSpider):
    PLATFORM_NAME = "平台名称"
    PLATFORM_CODE = "平台代码"  # 唯一标识
    
    def run(self):
        # 实现爬取逻辑
        return projects  # 返回项目列表
```

### 2.2 SpiderManager（爬虫管理器）

负责注册、创建和调度爬虫：

```python
from spider.spider_manager import SpiderManager

# 自动注册（推荐，使用装饰器）
@SpiderManager.register
class YourSpider(BaseSpider):
    ...

# 或手动注册
SpiderManager.register(YourSpider)

# 创建爬虫实例
spider = SpiderManager.create_spider("platform_code", daily_limit=10)

# 运行所有爬虫
projects = SpiderManager.run_all_spiders(days_before=7)
```

## 三、快速集成步骤

### 步骤1：创建平台目录

```bash
mkdir -p spider/platforms/your_platform
```

### 步骤2：实现可执行请求函数（request_handler.py）

**这是您需要实现的第一个函数：**

```python
def execute_request(session, url, method="GET", params=None, data=None,
                   headers=None, cookies=None, timeout=15, retry_times=3):
    """执行HTTP请求"""
    # 实现请求逻辑（参考 docs/PLATFORM_INTEGRATION_TEMPLATE.md）
    return response  # 返回 requests.Response 或 None
```

### 步骤3：创建平台配置（config.py）

```python
PLATFORM_CONFIG = {
    "name": "平台名称",
    "code": "平台代码",
    "base_url": "https://example.com",
    "api_url": "https://example.com/api/list",
    "headers": {...},
    "cookies": {...},
    # ... 其他配置
}
```

### 步骤4：实现爬虫类（spider.py）

```python
from spider.base_spider import BaseSpider
from spider.spider_manager import SpiderManager
from spider.platforms.your_platform.config import PLATFORM_CONFIG
from spider.platforms.your_platform.request_handler import execute_request

@SpiderManager.register
class YourPlatformTenderSpider(BaseSpider):
    PLATFORM_NAME = PLATFORM_CONFIG["name"]
    PLATFORM_CODE = PLATFORM_CONFIG["code"]
    
    def run(self):
        # 实现爬取逻辑（参考 docs/PLATFORM_INTEGRATION_TEMPLATE.md）
        return projects
```

### 步骤5：注册模块（__init__.py）

```python
from spider.platforms.your_platform.spider import YourPlatformTenderSpider
__all__ = ["YourPlatformTenderSpider"]
```

### 步骤6：更新主模块（spider/__init__.py）

在 `spider/__init__.py` 中添加导入：

```python
from spider.platforms.your_platform import YourPlatformTenderSpider
```

## 四、使用方式

### 4.1 运行所有爬虫

```python
from spider import SpiderManager

# 运行所有启用的爬虫
projects = SpiderManager.run_all_spiders(days_before=7)

# 运行指定平台
projects = SpiderManager.run_all_spiders(
    days_before=7,
    enabled_platforms=["zhejiang", "your_platform"]
)
```

### 4.2 运行单个爬虫

```python
from spider import SpiderManager

spider = SpiderManager.create_spider(
    platform_code="your_platform",
    daily_limit=50,
    days_before=7
)
projects = spider.run()
```

### 4.3 向后兼容（现有代码无需修改）

```python
# 现有代码仍然可用
from spider.tender_spider import ZheJiangTenderSpider, run_all_spiders

spider = ZheJiangTenderSpider(daily_limit=10, days_before=7)
projects = spider.run()

# 或使用统一函数
projects = run_all_spiders(days_before=7)
```

## 五、数据格式要求

项目数据字典必须包含以下字段：

```python
project_data = {
    "project_name": str,  # 必填
    "site_name": str,  # 必填
    "publish_time": datetime,  # 必填
    "publish_timestamp": int,  # 必填（毫秒时间戳）
    "download_url": str,  # 必填
    "project_id": str,  # 必填（唯一）
    "region": str,  # 可选
    "status": ProjectStatus,  # 必填
    "file_path": str,  # 可选
    "file_format": str,  # 可选
}
```

## 六、完整示例

参考 `docs/PLATFORM_INTEGRATION_TEMPLATE.md` 查看完整的代码模板和实现示例。

## 七、文件结构

```
spider/
├── __init__.py                 # 导出所有爬虫
├── base_spider.py              # 基础爬虫类
├── spider_manager.py           # 爬虫管理器
├── tender_spider.py            # 浙江省爬虫（现有）
└── platforms/                  # 平台目录（新增）
    ├── your_platform/
    │   ├── __init__.py
    │   ├── spider.py           # 爬虫实现
    │   ├── config.py           # 平台配置
    │   └── request_handler.py  # 可执行请求函数
    └── ...
```

## 八、注意事项

1. **平台代码唯一性**：`PLATFORM_CODE` 必须唯一，不能与其他平台重复
2. **接口实现**：必须实现 `run()` 方法
3. **错误处理**：每个平台应独立处理错误，避免影响其他平台
4. **日志记录**：使用统一的日志接口 `from utils.log import log`
5. **数据格式**：项目数据必须符合 `save_project` 函数的要求

## 九、测试建议

1. 先实现基本的请求函数，测试能否正常获取数据
2. 实现项目数据解析，确保格式正确
3. 测试日期筛选和去重逻辑
4. 测试文件下载功能（如果实现）
5. 完整测试整个爬取流程

## 十、获取帮助

- 查看完整文档：`docs/SPIDER_EXTENSION_PLAN.md`
- 查看集成模板：`docs/PLATFORM_INTEGRATION_TEMPLATE.md`
- 参考现有实现：`spider/tender_spider.py`（浙江省爬虫）
