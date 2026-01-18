# 爬虫平台扩展方案

## 一、方案概述

本方案旨在提供一套可扩展的爬虫架构，支持快速集成新的招标平台，同时保持向后兼容性和代码可维护性。

## 二、架构设计

### 2.1 设计原则

1. **开闭原则**：对扩展开放，对修改关闭
2. **接口统一**：所有爬虫遵循统一接口规范
3. **配置驱动**：平台配置与代码分离
4. **向后兼容**：不影响现有浙江省平台爬虫
5. **易于测试**：支持独立测试新平台爬虫

### 2.2 架构层次

```
┌─────────────────────────────────────┐
│     SpiderManager (统一管理器)       │
│   - 注册/发现爬虫                     │
│   - 统一调度执行                      │
│   - 配额分配                          │
└─────────────────────────────────────┘
              │
              ├─────────────────┬─────────────────┐
              ▼                 ▼                 ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │ BaseSpider   │  │ ZheJiang     │  │ HangZhou     │
    │ (基础接口)    │  │ TenderSpider │  │ TenderSpider │
    │              │  │              │  │  (新平台示例) │
    └──────────────┘  └──────────────┘  └──────────────┘
          ▲                 ▲                 ▲
          └─────────────────┴─────────────────┘
                   继承/实现统一接口
```

## 三、接口定义

### 3.1 基础爬虫接口（BaseSpider）

所有爬虫必须实现的接口：

```python
class BaseSpider:
    """爬虫基础接口"""
    
    # 平台标识（必填）
    PLATFORM_NAME: str = ""  # 如："浙江省政府采购网"
    PLATFORM_CODE: str = ""  # 如："zhejiang"
    
    def __init__(self, daily_limit=None, days_before=None, **kwargs):
        """
        初始化爬虫
        
        Args:
            daily_limit: 每日爬取限制数量
            days_before: 爬取最近N天内的文件（None表示只爬取当日）
            **kwargs: 其他平台特定参数
        """
        pass
    
    def run(self):
        """
        执行爬虫主逻辑
        
        Returns:
            list: 爬取到的项目列表，每个项目为 TenderProject 对象
        """
        pass
    
    def get_platform_info(self):
        """
        获取平台信息
        
        Returns:
            dict: {
                "name": "平台名称",
                "code": "平台代码",
                "base_url": "基础URL"
            }
        """
        pass
```

### 3.2 可执行请求函数接口

每个平台需要提供一个请求函数，用于执行HTTP请求：

```python
def execute_request(session, url, method="GET", params=None, data=None, 
                   headers=None, cookies=None, timeout=15):
    """
    执行HTTP请求（统一接口）
    
    Args:
        session: requests.Session 对象（由爬虫类管理）
        url: 请求URL
        method: HTTP方法（GET/POST）
        params: URL参数（字典）
        data: 请求体数据（字典或字符串）
        headers: 请求头（字典）
        cookies: Cookie（字典）
        timeout: 超时时间（秒）
    
    Returns:
        requests.Response: 响应对象，失败返回None
    """
    pass
```

## 四、实现方案

### 4.1 文件结构

```
spider/
├── __init__.py                 # 导出所有爬虫
├── base_spider.py              # 基础爬虫类（新增）
├── spider_manager.py           # 爬虫管理器（新增）
├── tender_spider.py            # 浙江省爬虫（现有，重构）
├── platforms/                  # 平台目录（新增）
│   ├── __init__.py
│   ├── zhejiang/              # 浙江省平台（可迁移）
│   │   ├── __init__.py
│   │   ├── spider.py          # 爬虫实现
│   │   └── config.py          # 平台配置
│   ├── hangzhou/              # 杭州市平台（示例）
│   │   ├── __init__.py
│   │   ├── spider.py
│   │   ├── config.py
│   │   └── request_handler.py # 可执行请求函数
│   └── ...
└── utils/                      # 爬虫通用工具（新增）
    ├── __init__.py
    └── request_utils.py        # 请求工具函数
```

### 4.2 核心组件

#### 4.2.1 基础爬虫类（base_spider.py）

```python
from abc import ABC, abstractmethod
from utils.db import get_db

class BaseSpider(ABC):
    """爬虫基础类"""
    
    PLATFORM_NAME: str = ""
    PLATFORM_CODE: str = ""
    
    def __init__(self, daily_limit=None, days_before=None, **kwargs):
        self.db = next(get_db())
        self.daily_limit = daily_limit or SPIDER_CONFIG["daily_limit"]
        self.days_before = days_before
        self.crawled_count = 0
        self.max_retries = SPIDER_CONFIG["anti_crawl"].get("retry_times", 3)
    
    @abstractmethod
    def run(self):
        """执行爬虫"""
        pass
    
    def get_platform_info(self):
        """获取平台信息"""
        return {
            "name": self.PLATFORM_NAME,
            "code": self.PLATFORM_CODE
        }
    
    def _is_duplicate(self, project_id):
        """检查项目是否已存在（通用方法）"""
        # 使用现有逻辑
        pass
```

#### 4.2.2 爬虫管理器（spider_manager.py）

```python
class SpiderManager:
    """爬虫管理器：负责注册、发现和调度爬虫"""
    
    _spiders = {}  # 注册的爬虫类
    
    @classmethod
    def register(cls, spider_class):
        """注册爬虫类"""
        platform_code = spider_class.PLATFORM_CODE
        cls._spiders[platform_code] = spider_class
        return spider_class
    
    @classmethod
    def get_spider(cls, platform_code):
        """获取爬虫类"""
        return cls._spiders.get(platform_code)
    
    @classmethod
    def list_spiders(cls):
        """列出所有注册的爬虫"""
        return list(cls._spiders.keys())
    
    @classmethod
    def create_spider(cls, platform_code, **kwargs):
        """创建爬虫实例"""
        spider_class = cls.get_spider(platform_code)
        if not spider_class:
            raise ValueError(f"未找到平台爬虫: {platform_code}")
        return spider_class(**kwargs)
    
    @classmethod
    def run_all_spiders(cls, days_before=None, enabled_platforms=None):
        """
        运行所有爬虫或指定平台爬虫
        
        Args:
            days_before: 时间间隔
            enabled_platforms: 启用的平台列表（None表示全部）
        """
        all_projects = []
        enabled = enabled_platforms or cls.list_spiders()
        
        for platform_code in enabled:
            try:
                spider = cls.create_spider(platform_code, days_before=days_before)
                projects = spider.run()
                all_projects.extend(projects)
            except Exception as e:
                log.error(f"平台 {platform_code} 爬取失败: {str(e)}")
        
        return all_projects
```

### 4.3 新平台集成步骤

#### 步骤1：创建平台目录和文件

```bash
mkdir -p spider/platforms/hangzhou
touch spider/platforms/hangzhou/__init__.py
touch spider/platforms/hangzhou/spider.py
touch spider/platforms/hangzhou/config.py
touch spider/platforms/hangzhou/request_handler.py
```

#### 步骤2：实现请求处理函数（request_handler.py）

```python
"""杭州市招标平台请求处理函数"""

import requests
import time
from utils.log import log

def execute_request(session, url, method="GET", params=None, data=None,
                   headers=None, cookies=None, timeout=15, retry_times=3):
    """
    执行HTTP请求
    
    Args:
        session: requests.Session 对象
        url: 请求URL
        method: HTTP方法
        params: URL参数
        data: 请求体
        headers: 请求头
        cookies: Cookie
        timeout: 超时时间
        retry_times: 重试次数
    
    Returns:
        requests.Response 或 None
    """
    for attempt in range(retry_times + 1):
        try:
            kwargs = {
                "timeout": timeout,
                "headers": headers or {},
                "cookies": cookies or {}
            }
            
            if method.upper() == "GET":
                response = session.get(url, params=params, **kwargs)
            elif method.upper() == "POST":
                response = session.post(url, params=params, data=data, json=data, **kwargs)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")
            
            response.raise_for_status()
            return response
            
        except requests.RequestException as e:
            if attempt < retry_times:
                wait_time = 2 * (attempt + 1)
                log.warning(f"请求失败（第{attempt+1}次），{wait_time}秒后重试: {str(e)}")
                time.sleep(wait_time)
            else:
                log.error(f"请求失败，已达最大重试次数: {str(e)}")
                return None
    
    return None
```

#### 步骤3：创建平台配置（config.py）

```python
"""杭州市招标平台配置"""

PLATFORM_CONFIG = {
    "name": "杭州市公共资源交易网",
    "code": "hangzhou",
    "base_url": "https://ggzy.hangzhou.gov.cn",
    "api_url": "https://ggzy.hangzhou.gov.cn/api/tender/list",
    "download_url": "https://ggzy.hangzhou.gov.cn/api/tender/download",
    "headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        # ... 其他请求头
    },
    "cookies": {
        # Cookie配置
    },
    "categories": [
        {"code": "001", "name": "建设工程"},
        {"code": "002", "name": "政府采购"}
    ],
    "districts": {
        "330100": "杭州市本级",
        "330102": "上城区",
        # ... 其他区域
    }
}
```

#### 步骤4：实现爬虫类（spider.py）

```python
"""杭州市招标平台爬虫"""

import requests
from datetime import datetime
from spider.base_spider import BaseSpider
from spider.platforms.hangzhou.config import PLATFORM_CONFIG
from spider.platforms.hangzhou.request_handler import execute_request
from utils.log import log
from utils.db import save_project, ProjectStatus
from config import SPIDER_CONFIG, FILES_DIR

@SpiderManager.register
class HangZhouTenderSpider(BaseSpider):
    """杭州市招标平台爬虫"""
    
    PLATFORM_NAME = PLATFORM_CONFIG["name"]
    PLATFORM_CODE = PLATFORM_CONFIG["code"]
    
    def __init__(self, daily_limit=None, days_before=None, **kwargs):
        super().__init__(daily_limit, days_before, **kwargs)
        self.base_url = PLATFORM_CONFIG["base_url"]
        self.api_url = PLATFORM_CONFIG["api_url"]
        self.download_url = PLATFORM_CONFIG["download_url"]
        self.headers = PLATFORM_CONFIG["headers"]
        self.cookies = PLATFORM_CONFIG["cookies"]
        self.categories = PLATFORM_CONFIG["categories"]
        self.districts = PLATFORM_CONFIG["districts"]
    
    def run(self):
        """执行爬虫主逻辑"""
        log.info(f"开始爬取{self.PLATFORM_NAME}，总配额: {self.daily_limit}")
        
        session = requests.Session()
        session.headers.update(self.headers)
        session.cookies.update(self.cookies)
        
        projects = []
        total_count = 0
        
        # 遍历分类和区域
        for category in self.categories:
            if total_count >= self.daily_limit:
                break
            
            for district_code, district_name in self.districts.items():
                if total_count >= self.daily_limit:
                    break
                
                # 调用可执行请求函数
                response = execute_request(
                    session=session,
                    url=self.api_url,
                    method="POST",
                    data={
                        "category": category["code"],
                        "district": district_code,
                        "page": 1,
                        "pageSize": 20
                    },
                    headers=self.headers,
                    cookies=self.cookies
                )
                
                if response:
                    try:
                        result = response.json()
                        items = result.get("data", {}).get("list", [])
                        
                        for item in items:
                            if total_count >= self.daily_limit:
                                break
                            
                            # 解析项目数据
                            project_data = self._parse_project(item, category, district_name)
                            
                            # 下载文件（如果需要）
                            if project_data:
                                # ... 下载逻辑
                                saved_project = save_project(self.db, project_data)
                                projects.append(saved_project)
                                total_count += 1
                                
                    except Exception as e:
                        log.error(f"解析数据失败: {str(e)}")
        
        session.close()
        self.db.close()
        self.crawled_count = total_count
        log.info(f"{self.PLATFORM_NAME}爬取完成，总获取: {total_count}个项目")
        return projects
    
    def _parse_project(self, item, category, district_name):
        """解析项目数据"""
        # 实现项目数据解析逻辑
        # 返回符合 save_project 函数要求的数据字典
        pass
```

#### 步骤5：注册爬虫（platforms/hangzhou/__init__.py）

```python
"""杭州市招标平台爬虫模块"""

from spider.platforms.hangzhou.spider import HangZhouTenderSpider

__all__ = ["HangZhouTenderSpider"]
```

#### 步骤6：更新主模块（spider/__init__.py）

```python
"""爬虫模块统一导出"""

# 导入基础类和管理器
from spider.base_spider import BaseSpider
from spider.spider_manager import SpiderManager

# 导入现有爬虫（保持向后兼容）
from spider.tender_spider import ZheJiangTenderSpider

# 导入新平台爬虫
from spider.platforms.hangzhou import HangZhouTenderSpider

# 自动注册所有爬虫
SpiderManager.register(ZheJiangTenderSpider)
SpiderManager.register(HangZhouTenderSpider)

__all__ = [
    "BaseSpider",
    "SpiderManager",
    "ZheJiangTenderSpider",
    "HangZhouTenderSpider",
]
```

## 五、配置管理

### 5.1 平台配置结构

每个平台的配置应包含：

```python
PLATFORM_CONFIG = {
    "name": "平台名称",
    "code": "平台代码（唯一）",
    "base_url": "基础URL",
    "api_url": "API接口URL",
    "download_url": "文件下载URL（可选）",
    "enabled": True,  # 是否启用
    "daily_limit": 100,  # 平台每日爬取限制（可选，使用全局配置）
    "headers": {},  # 请求头
    "cookies": {},  # Cookie
    "categories": [],  # 分类配置
    "districts": {},  # 区域配置
    "max_pages": 50,  # 最大爬取页数
    "request_interval": 2,  # 请求间隔（秒）
}
```

### 5.2 全局配置更新（config.py）

```python
# 爬虫配置
SPIDER_CONFIG = {
    "daily_limit": 4,  # 全局每日总爬取限制
    "zhejiang_max_pages": 35,
    "files_dir": FILES_DIR,
    "anti_crawl": {
        "request_interval": 2,
        "retry_times": 3,
        "timeout": 15
    },
    # 新增：平台启用配置
    "enabled_platforms": ["zhejiang"],  # 默认只启用浙江省平台
    # 新增：平台配额分配策略
    "quota_strategy": "equal",  # "equal"平均分配, "proportional"按比例分配
}
```

## 六、使用方式

### 6.1 运行所有爬虫

```python
from spider import SpiderManager

# 运行所有启用的爬虫
projects = SpiderManager.run_all_spiders(days_before=7)

# 运行指定平台爬虫
projects = SpiderManager.run_all_spiders(
    days_before=7,
    enabled_platforms=["zhejiang", "hangzhou"]
)
```

### 6.2 运行单个爬虫

```python
from spider import SpiderManager

# 创建并运行单个爬虫
spider = SpiderManager.create_spider(
    platform_code="hangzhou",
    daily_limit=50,
    days_before=7
)
projects = spider.run()
```

### 6.3 向后兼容（现有代码无需修改）

```python
# 现有代码仍然可用
from spider.tender_spider import ZheJiangTenderSpider, run_all_spiders

spider = ZheJiangTenderSpider(daily_limit=10, days_before=7)
projects = spider.run()

# 或使用统一函数
projects = run_all_spiders(days_before=7)
```

## 七、集成检查清单

添加新平台时，请确保：

- [ ] 创建平台目录和文件结构
- [ ] 实现 `execute_request` 请求处理函数
- [ ] 创建平台配置文件 `config.py`
- [ ] 实现爬虫类，继承 `BaseSpider`
- [ ] 实现 `run()` 方法
- [ ] 实现项目数据解析方法
- [ ] 实现文件下载逻辑（如需要）
- [ ] 注册爬虫到 `SpiderManager`
- [ ] 更新 `spider/__init__.py` 导入
- [ ] 编写单元测试
- [ ] 更新文档

## 八、测试指南

### 8.1 单元测试示例

```python
import unittest
from spider.platforms.hangzhou.spider import HangZhouTenderSpider
from spider.platforms.hangzhou.request_handler import execute_request

class TestHangZhouSpider(unittest.TestCase):
    
    def test_spider_init(self):
        spider = HangZhouTenderSpider(daily_limit=10)
        self.assertEqual(spider.PLATFORM_CODE, "hangzhou")
        self.assertEqual(spider.daily_limit, 10)
    
    def test_request_handler(self):
        import requests
        session = requests.Session()
        response = execute_request(
            session=session,
            url="https://example.com/api",
            method="GET"
        )
        # 验证响应...
```

### 8.2 集成测试

```python
from spider import SpiderManager

def test_integration():
    # 测试爬虫注册
    assert "hangzhou" in SpiderManager.list_spiders()
    
    # 测试爬虫创建
    spider = SpiderManager.create_spider("hangzhou", daily_limit=5)
    assert spider is not None
    
    # 测试运行（可选：使用mock数据）
    # projects = spider.run()
    # assert len(projects) > 0
```

## 九、注意事项

1. **数据格式统一**：所有平台返回的项目数据必须转换为统一的格式，符合 `save_project` 函数的要求
2. **错误处理**：每个平台爬虫应独立处理错误，避免影响其他平台
3. **配额管理**：如果多个平台共享配额，需要在 `SpiderManager` 中统一管理
4. **日志记录**：使用统一的日志接口，便于问题排查
5. **性能考虑**：大量平台时，考虑使用异步或并行执行
6. **配置热更新**：考虑支持动态加载平台配置，无需重启服务

## 十、后续优化方向

1. **异步爬取**：使用 `asyncio` 和 `aiohttp` 实现异步爬取
2. **分布式爬取**：支持多进程/多机分布式爬取
3. **配置中心**：将平台配置移至数据库或配置文件，支持动态管理
4. **监控告警**：添加爬虫运行状态监控和异常告警
5. **爬虫调度**：实现更灵活的调度策略（优先级、时间窗口等）
