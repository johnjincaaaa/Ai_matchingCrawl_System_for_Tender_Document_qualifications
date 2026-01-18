# 新平台集成模板

本文档提供了一个完整的模板，用于快速集成新的招标平台爬虫。

## 一、快速开始

### 步骤1：创建平台目录结构

```bash
mkdir -p spider/platforms/your_platform
cd spider/platforms/your_platform
```

创建以下文件：
- `__init__.py` - 模块初始化文件
- `spider.py` - 爬虫主类
- `config.py` - 平台配置
- `request_handler.py` - 可执行请求函数

### 步骤2：实现可执行请求函数（request_handler.py）

```python
"""平台可执行请求函数

这是您需要实现的第一个函数，用于处理HTTP请求。
"""

import requests
import time
from utils.log import log


def execute_request(session, url, method="GET", params=None, data=None,
                   headers=None, cookies=None, timeout=15, retry_times=3):
    """
    执行HTTP请求（统一接口）
    
    Args:
        session: requests.Session 对象（由爬虫类管理）
        url: 请求URL
        method: HTTP方法（GET/POST/PUT/DELETE等）
        params: URL参数（字典）
        data: 请求体数据（字典或字符串）
        headers: 请求头（字典，可选）
        cookies: Cookie（字典，可选）
        timeout: 超时时间（秒）
        retry_times: 重试次数
    
    Returns:
        requests.Response: 响应对象，失败返回None
        
    示例:
        import requests
        session = requests.Session()
        
        # GET请求
        response = execute_request(
            session=session,
            url="https://example.com/api/list",
            method="GET",
            params={"page": 1, "size": 20},
            headers={"User-Agent": "Mozilla/5.0..."},
            timeout=15
        )
        
        # POST请求
        response = execute_request(
            session=session,
            url="https://example.com/api/search",
            method="POST",
            data={"keyword": "招标", "date": "2024-01-01"},
            headers={"Content-Type": "application/json"},
            timeout=15
        )
    """
    for attempt in range(retry_times + 1):
        try:
            # 准备请求参数
            kwargs = {
                "timeout": timeout,
            }
            
            # 添加请求头
            if headers:
                kwargs["headers"] = headers
            
            # 添加Cookie
            if cookies:
                kwargs["cookies"] = cookies
            
            # 执行请求
            if method.upper() == "GET":
                response = session.get(url, params=params, **kwargs)
            elif method.upper() == "POST":
                # 根据Content-Type自动判断使用data还是json
                if headers and "application/json" in headers.get("Content-Type", ""):
                    response = session.post(url, params=params, json=data, **kwargs)
                else:
                    response = session.post(url, params=params, data=data, **kwargs)
            elif method.upper() == "PUT":
                response = session.put(url, params=params, json=data, **kwargs)
            elif method.upper() == "DELETE":
                response = session.delete(url, params=params, **kwargs)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")
            
            # 检查响应状态
            response.raise_for_status()
            
            # 成功返回响应
            return response
            
        except requests.exceptions.Timeout as e:
            if attempt < retry_times:
                wait_time = 2 * (attempt + 1)
                log.warning(f"请求超时（第{attempt+1}次），{wait_time}秒后重试: {url}")
                time.sleep(wait_time)
            else:
                log.error(f"请求超时，已达最大重试次数: {url}")
                return None
                
        except requests.exceptions.ConnectionError as e:
            if attempt < retry_times:
                wait_time = 5 * (attempt + 1)
                log.warning(f"连接错误（第{attempt+1}次），{wait_time}秒后重试: {url}")
                time.sleep(wait_time)
            else:
                log.error(f"连接错误，已达最大重试次数: {url}")
                return None
                
        except requests.exceptions.HTTPError as e:
            # HTTP错误（4xx, 5xx）通常不需要重试，直接返回
            log.error(f"HTTP错误 {response.status_code}: {url}, 错误: {str(e)}")
            return None
            
        except Exception as e:
            if attempt < retry_times:
                wait_time = 2 * (attempt + 1)
                log.warning(f"请求失败（第{attempt+1}次），{wait_time}秒后重试: {url}, 错误: {str(e)}")
                time.sleep(wait_time)
            else:
                log.error(f"请求失败，已达最大重试次数: {url}, 错误: {str(e)}")
                return None
    
    return None


def download_file(session, download_url, save_path, headers=None, cookies=None, timeout=120):
    """
    下载文件（可选功能）
    
    Args:
        session: requests.Session 对象
        download_url: 文件下载URL
        save_path: 保存路径
        headers: 请求头
        cookies: Cookie
        timeout: 超时时间（秒，文件下载可能需要更长时间）
    
    Returns:
        bool: True表示下载成功，False表示失败
    """
    try:
        response = execute_request(
            session=session,
            url=download_url,
            method="GET",
            headers=headers,
            cookies=cookies,
            timeout=timeout
        )
        
        if response:
            # 保存文件
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            log.info(f"文件下载成功: {save_path}")
            return True
        else:
            log.error(f"文件下载失败: {download_url}")
            return False
            
    except Exception as e:
        log.error(f"文件下载异常: {download_url}, 错误: {str(e)}")
        return False
```

### 步骤3：创建平台配置（config.py）

```python
"""平台配置

包含平台的所有配置信息，包括URL、请求头、分类、区域等
"""

PLATFORM_CONFIG = {
    # 平台基本信息
    "name": "平台名称",  # 如："杭州市公共资源交易网"
    "code": "platform_code",  # 唯一标识，如："hangzhou"
    
    # URL配置
    "base_url": "https://example.com",  # 基础URL
    "api_url": "https://example.com/api/tender/list",  # 列表API
    "detail_url": "https://example.com/api/tender/detail",  # 详情API（可选）
    "download_url": "https://example.com/api/tender/download",  # 下载API（可选）
    
    # 请求配置
    "headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Content-Type": "application/json;charset=UTF-8",
        # ... 其他请求头
    },
    "cookies": {
        # Cookie配置（如果需要）
    },
    
    # 分类配置
    "categories": [
        {"code": "001", "name": "建设工程"},
        {"code": "002", "name": "政府采购"},
        # ... 其他分类
    ],
    
    # 区域配置（如果有）
    "districts": {
        "330100": "杭州市本级",
        "330102": "上城区",
        # ... 其他区域
    },
    
    # 爬取配置
    "max_pages": 50,  # 最大爬取页数
    "page_size": 20,  # 每页数量
    "request_interval": 2,  # 请求间隔（秒）
    
    # 其他平台特定配置
    "extra_params": {
        # 平台特定的额外参数
    },
}
```

### 步骤4：实现爬虫类（spider.py）

```python
"""平台爬虫实现

继承BaseSpider，实现run()方法和相关辅助方法
"""

import requests
import json
from datetime import datetime
from spider.base_spider import BaseSpider
from spider.spider_manager import SpiderManager
from spider.platforms.your_platform.config import PLATFORM_CONFIG
from spider.platforms.your_platform.request_handler import execute_request, download_file
from utils.log import log
from utils.db import save_project, ProjectStatus
from config import SPIDER_CONFIG, FILES_DIR
import os
import time


@SpiderManager.register
class YourPlatformTenderSpider(BaseSpider):
    """平台名称爬虫
    
    实现平台特定的爬取逻辑
    """
    
    PLATFORM_NAME = PLATFORM_CONFIG["name"]
    PLATFORM_CODE = PLATFORM_CONFIG["code"]
    
    def __init__(self, daily_limit=None, days_before=None, **kwargs):
        """初始化爬虫"""
        super().__init__(daily_limit=daily_limit, days_before=days_before, **kwargs)
        
        # 平台URL配置
        self.base_url = PLATFORM_CONFIG["base_url"]
        self.api_url = PLATFORM_CONFIG["api_url"]
        self.download_url = PLATFORM_CONFIG.get("download_url")
        self.detail_url = PLATFORM_CONFIG.get("detail_url")
        
        # 请求配置
        self.headers = PLATFORM_CONFIG["headers"]
        self.cookies = PLATFORM_CONFIG.get("cookies", {})
        
        # 分类和区域配置
        self.categories = PLATFORM_CONFIG.get("categories", [])
        self.districts = PLATFORM_CONFIG.get("districts", {})
        
        # 爬取配置
        self.max_pages = PLATFORM_CONFIG.get("max_pages", 50)
        self.page_size = PLATFORM_CONFIG.get("page_size", 20)
        self.request_interval = PLATFORM_CONFIG.get("request_interval", 2)
    
    def run(self):
        """
        执行爬虫主逻辑
        
        Returns:
            list: 爬取到的项目列表
        """
        log.info(f"开始爬取{self.PLATFORM_NAME}，总配额: {self.daily_limit}")
        
        if self.days_before is not None:
            log.info(f"时间间隔限制：爬取最近 {self.days_before} 天内的文件")
        
        # 创建会话
        session = requests.Session()
        session.headers.update(self.headers)
        session.cookies.update(self.cookies)
        
        # 初始化
        projects = []
        total_count = 0
        today = datetime.now().date()
        
        # 批量查询已存在的项目ID（性能优化）
        from utils.db import TenderProject
        existing_project_ids = set(
            row[0] for row in self.db.query(TenderProject.project_id)
            .filter(TenderProject.project_id.isnot(None))
            .all()
        )
        processed_project_ids = set(existing_project_ids)
        log.info(f"已加载 {len(existing_project_ids)} 个已存在的项目ID到内存缓存")
        
        # 计算最早允许的发布日期（如果设置了days_before）
        earliest_date = None
        if self.days_before is not None and self.days_before > 0:
            from datetime import timedelta
            earliest_date = today - timedelta(days=self.days_before)
            log.info(f"时间范围：{earliest_date} 至 {today}（最近 {self.days_before} 天内）")
        
        # 遍历分类和区域（根据平台实际情况调整）
        for category in self.categories:
            if total_count >= self.daily_limit:
                break
            
            category_code = category["code"]
            category_name = category["name"]
            log.info(f"开始爬取分类: {category_name}（{category_code}）")
            
            # 如果有区域配置，遍历区域
            if self.districts:
                for district_code, district_name in self.districts.items():
                    if total_count >= self.daily_limit:
                        break
                    
                    # 爬取该分类和区域的项目
                    category_projects = self._crawl_category_district(
                        session, category_code, category_name,
                        district_code, district_name,
                        today, earliest_date, processed_project_ids
                    )
                    
                    projects.extend(category_projects)
                    total_count += len(category_projects)
            else:
                # 没有区域配置，直接爬取分类
                category_projects = self._crawl_category(
                    session, category_code, category_name,
                    today, earliest_date, processed_project_ids
                )
                
                projects.extend(category_projects)
                total_count += len(category_projects)
        
        # 关闭会话和数据库连接
        session.close()
        self.db.close()
        
        self.crawled_count = total_count
        log.info(f"{self.PLATFORM_NAME}爬取完成，总获取: {total_count}个项目")
        
        return projects
    
    def _crawl_category_district(self, session, category_code, category_name,
                                 district_code, district_name, today, earliest_date,
                                 processed_project_ids):
        """爬取指定分类和区域的项目"""
        projects = []
        page_no = 1
        
        while page_no <= self.max_pages:
            # 反爬控制
            if page_no > 1:
                time.sleep(self.request_interval)
            
            # 构建请求参数（根据平台API调整）
            request_data = {
                "category": category_code,
                "district": district_code,
                "page": page_no,
                "pageSize": self.page_size,
            }
            
            # 执行请求
            log.debug(f"[{category_name}-{district_name}]正在请求第{page_no}页数据")
            response = execute_request(
                session=session,
                url=self.api_url,
                method="POST",  # 根据平台API调整
                data=request_data,
                headers=self.headers,
                cookies=self.cookies,
                timeout=SPIDER_CONFIG["anti_crawl"].get("timeout", 15)
            )
            
            if not response:
                log.warning(f"[{category_name}-{district_name}]第{page_no}页请求失败")
                break
            
            # 解析响应（根据平台响应格式调整）
            try:
                result = response.json()
                
                # 解析数据列表（根据平台响应结构调整）
                items = result.get("data", {}).get("list", [])
                # 或者：items = result.get("list", [])
                # 或者：items = result.get("items", [])
                
                if not items:
                    log.info(f"[{category_name}-{district_name}]第{page_no}页无数据，停止爬取")
                    break
                
                log.debug(f"[{category_name}-{district_name}]第{page_no}页获取到{len(items)}个项目")
                
                # 处理每个项目
                for item in items:
                    if len(projects) >= self.daily_limit:
                        break
                    
                    # 解析项目数据
                    project_data = self._parse_project(
                        item, category_name, district_name, today, earliest_date
                    )
                    
                    if not project_data:
                        continue
                    
                    # 检查是否已存在
                    project_id = project_data.get("project_id")
                    if project_id in processed_project_ids:
                        log.debug(f"项目已存在，跳过: {project_id}")
                        continue
                    
                    # 添加到已处理集合
                    processed_project_ids.add(project_id)
                    
                    # 下载文件（如果需要）
                    file_path, file_format = self._download_document(
                        session, project_data
                    )
                    if file_path:
                        project_data["file_path"] = file_path
                        project_data["file_format"] = file_format
                    
                    # 保存项目
                    try:
                        saved_project = save_project(self.db, project_data)
                        projects.append(saved_project)
                        log.debug(f"已爬取项目: {project_data['project_name'][:50]}...")
                    except Exception as e:
                        log.error(f"保存项目失败: {str(e)}")
                
            except Exception as e:
                log.error(f"解析响应失败: {str(e)}")
                break
            
            page_no += 1
        
        return projects
    
    def _crawl_category(self, session, category_code, category_name,
                       today, earliest_date, processed_project_ids):
        """爬取指定分类的项目（无区域配置时使用）"""
        # 实现逻辑类似 _crawl_category_district，但不包含区域参数
        # 根据平台实际情况实现
        pass
    
    def _parse_project(self, item, category_name, district_name, today, earliest_date):
        """
        解析项目数据
        
        Args:
            item: API返回的项目数据（字典）
            category_name: 分类名称
            district_name: 区域名称
            today: 今日日期
            earliest_date: 最早允许的发布日期
        
        Returns:
            dict: 项目数据字典，格式需符合save_project函数要求
            如果解析失败或不符合条件，返回None
        """
        try:
            # 提取项目ID（必填）
            project_id = item.get("id") or item.get("articleId") or item.get("tenderId")
            if not project_id:
                log.warning("项目缺少ID，跳过")
                return None
            
            # 提取项目标题（必填）
            project_name = item.get("title") or item.get("name") or item.get("projectName")
            if not project_name:
                log.warning(f"项目ID {project_id} 缺少标题，跳过")
                return None
            
            # 提取发布时间（必填）
            publish_time = self._extract_publish_time(item)
            if not publish_time:
                log.warning(f"项目 {project_name[:50]}... 缺少发布时间，跳过")
                return None
            
            # 检查日期是否符合要求
            project_date = publish_time.date()
            if self.days_before is not None:
                if project_date < earliest_date or project_date > today:
                    return None  # 日期不符合要求，不记录日志
            else:
                if project_date < today:
                    return None  # 不是当日项目，不记录日志
            
            # 提取区域名称（可选）
            region = item.get("districtName") or item.get("region") or district_name
            
            # 构建项目数据字典（格式需符合save_project函数要求）
            project_data = {
                "project_name": project_name,
                "site_name": f"{self.PLATFORM_NAME}-{region}",
                "publish_time": publish_time,
                "publish_timestamp": int(publish_time.timestamp() * 1000),  # 毫秒时间戳
                "download_url": f"{self.base_url}/detail/{project_id}",  # 详情页URL
                "project_id": str(project_id),
                "region": region,
                "status": ProjectStatus.DOWNLOADED,
            }
            
            return project_data
            
        except Exception as e:
            log.error(f"解析项目数据失败: {str(e)}")
            return None
    
    def _extract_publish_time(self, item):
        """
        提取发布时间
        
        Args:
            item: API返回的项目数据
        
        Returns:
            datetime: 发布时间对象，解析失败返回None
        """
        # 尝试多种字段名
        possible_fields = [
            "publishDate", "publishTime", "pubDate", "pubTime",
            "releaseDate", "releaseTime", "createDate", "createTime"
        ]
        
        for field_name in possible_fields:
            field_value = item.get(field_name)
            
            if field_value is None:
                continue
            
            try:
                # 如果是时间戳（毫秒）
                if isinstance(field_value, (int, float)):
                    timestamp_ms = int(field_value)
                    timestamp = timestamp_ms // 1000 if timestamp_ms > 1e10 else timestamp_ms
                    return datetime.fromtimestamp(timestamp)
                
                # 如果是时间戳字符串
                elif isinstance(field_value, str) and field_value.strip().isdigit():
                    timestamp_ms = int(field_value.strip())
                    timestamp = timestamp_ms // 1000 if timestamp_ms > 1e10 else timestamp_ms
                    return datetime.fromtimestamp(timestamp)
                
                # 如果是日期字符串
                elif isinstance(field_value, str):
                    # 尝试多种日期格式
                    date_formats = [
                        "%Y-%m-%d %H:%M:%S",
                        "%Y-%m-%dT%H:%M:%S",
                        "%Y-%m-%d",
                        "%Y/%m/%d %H:%M:%S",
                        "%Y/%m/%d",
                    ]
                    
                    for date_format in date_formats:
                        try:
                            return datetime.strptime(field_value, date_format)
                        except ValueError:
                            continue
                            
            except (ValueError, OverflowError) as e:
                log.debug(f"解析发布时间字段 {field_name} 失败: {str(e)}")
                continue
        
        return None
    
    def _download_document(self, session, project_data):
        """
        下载项目文档（可选功能）
        
        Args:
            session: requests.Session对象
            project_data: 项目数据字典
        
        Returns:
            tuple: (file_path, file_format) 或 (None, None)
        """
        if not self.download_url:
            return None, None
        
        try:
            project_id = project_data.get("project_id")
            project_name = project_data.get("project_name", "")
            
            # 构建下载请求参数（根据平台API调整）
            download_params = {
                "id": project_id,
                "timestamp": int(time.time() * 1000)
            }
            
            # 获取下载链接
            response = execute_request(
                session=session,
                url=self.download_url,
                method="GET",
                params=download_params,
                headers=self.headers,
                cookies=self.cookies,
                timeout=30
            )
            
            if not response:
                return None, None
            
            result = response.json()
            download_link = result.get("downloadUrl") or result.get("url") or result.get("data")
            
            if not download_link:
                log.warning(f"未获取到下载链接: {project_id}")
                return None, None
            
            # 生成文件名
            safe_article_id = str(project_id).replace('/', '_').replace('\\', '_')
            safe_title = project_name[:50]
            for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|', ' ']:
                safe_title = safe_title.replace(char, '_')
            
            file_extension = download_link.split('.')[-1].split('?')[0]
            filename = f"{self.PLATFORM_CODE}_{safe_title}_{safe_article_id}.{file_extension}"
            filepath = os.path.join(FILES_DIR, filename)
            
            # 下载文件
            if download_file(session, download_link, filepath, self.headers, self.cookies):
                return filepath, file_extension
            else:
                return None, None
                
        except Exception as e:
            log.error(f"下载文档失败: {str(e)}")
            return None, None
```

### 步骤5：注册爬虫（__init__.py）

```python
"""平台爬虫模块"""

from spider.platforms.your_platform.spider import YourPlatformTenderSpider

__all__ = ["YourPlatformTenderSpider"]
```

### 步骤6：更新主模块（spider/__init__.py）

在 `spider/__init__.py` 中添加：

```python
# 导入新平台爬虫
from spider.platforms.your_platform import YourPlatformTenderSpider

# 注意：爬虫已在类定义时通过 @SpiderManager.register 装饰器自动注册
# 如果未使用装饰器，需要手动注册：
# SpiderManager.register(YourPlatformTenderSpider)
```

## 二、数据格式要求

项目数据字典必须包含以下字段（符合 `save_project` 函数要求）：

```python
project_data = {
    "project_name": str,  # 项目名称（必填）
    "site_name": str,  # 站点名称（必填）
    "publish_time": datetime,  # 发布时间（必填）
    "publish_timestamp": int,  # 发布时间戳（毫秒，必填）
    "download_url": str,  # 详情页URL（必填）
    "project_id": str,  # 项目ID（必填，唯一）
    "region": str,  # 区域名称（可选）
    "status": ProjectStatus,  # 项目状态（必填，枚举类型）
    "file_path": str,  # 文件路径（可选）
    "file_format": str,  # 文件格式（可选）
}
```

## 三、测试检查清单

- [ ] 请求函数能正常执行HTTP请求
- [ ] 爬虫类能正常初始化
- [ ] run()方法能正常执行
- [ ] 项目数据能正确解析
- [ ] 日期筛选逻辑正确
- [ ] 去重逻辑正确
- [ ] 文件下载功能正常（如果实现）
- [ ] 数据能正确保存到数据库
- [ ] 日志输出正确
- [ ] 错误处理完善

## 四、常见问题

### Q1: 如何确定API接口和参数格式？

A: 使用浏览器开发者工具（F12）监控网络请求，查看实际API调用和参数格式。

### Q2: 如何处理需要登录的平台？

A: 在 `config.py` 中配置有效的 Cookie 或 Session，或者在请求函数中实现登录逻辑。

### Q3: 如何处理反爬虫机制？

A: 在 `request_handler.py` 中调整请求间隔、添加随机延迟、使用代理等方式。

### Q4: 如何调试新平台爬虫？

A: 可以先实现基本的请求和解析逻辑，使用少量数据测试，逐步完善。

## 五、参考示例

可以参考 `spider/tender_spider.py` 中的浙江省爬虫实现，了解完整的数据处理和错误处理逻辑。
