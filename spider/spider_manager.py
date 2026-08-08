"""爬虫管理器

负责爬虫的注册、发现、创建和统一调度
"""

from typing import List, Dict, Optional, Type, Any
import os
from datetime import datetime
from sqlalchemy import func
from utils.log import log
from config import FILES_DIR
from utils.db import get_db, TenderProject, ProjectStatus
# 兼容相对导入和绝对导入
try:
    from .base_spider import BaseSpider
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    from spider.base_spider import BaseSpider


class SpiderManager:
    """爬虫管理器：负责注册、发现和调度爬虫
    
    使用示例:
        # 注册爬虫（自动注册）
        @SpiderManager.register
        class MySpider(BaseSpider):
            PLATFORM_CODE = "my_platform"
            ...
        
        # 或者手动注册
        SpiderManager.register(MySpider)
        
        # 获取爬虫类
        spider_class = SpiderManager.get_spider("my_platform")
        
        # 创建爬虫实例
        spider = SpiderManager.create_spider("my_platform", daily_limit=10)
        
        # 运行所有爬虫
        projects = SpiderManager.run_all_spiders(days_before=7)
    """
    
    _spiders: Dict[str, Type[BaseSpider]] = {}  # 注册的爬虫类字典
    
    @classmethod
    def register(cls, spider_class: Type[BaseSpider]):
        """
        注册爬虫类
        
        Args:
            spider_class: 爬虫类（必须继承BaseSpider）
            
        Returns:
            Type[BaseSpider]: 返回注册的爬虫类（支持装饰器用法）
            
        Raises:
            ValueError: 如果爬虫类无效或平台代码重复
        """
        if not issubclass(spider_class, BaseSpider):
            raise ValueError(f"爬虫类 {spider_class.__name__} 必须继承 BaseSpider")
        
        platform_code = spider_class.PLATFORM_CODE
        if not platform_code:
            raise ValueError(f"爬虫类 {spider_class.__name__} 未设置 PLATFORM_CODE")
        
        if platform_code in cls._spiders:
            log.warning(f"平台 {platform_code} 已注册，将覆盖现有爬虫类")
        
        cls._spiders[platform_code] = spider_class
        log.info(f"注册爬虫: {platform_code} ({spider_class.PLATFORM_NAME})")
        return spider_class
    
    @classmethod
    def unregister(cls, platform_code: str):
        """
        注销爬虫类
        
        Args:
            platform_code: 平台代码
        """
        if platform_code in cls._spiders:
            del cls._spiders[platform_code]
            log.info(f"注销爬虫: {platform_code}")
        else:
            log.warning(f"未找到要注销的爬虫: {platform_code}")
    
    @classmethod
    def get_spider(cls, platform_code: str) -> Optional[Type[BaseSpider]]:
        """
        获取爬虫类
        
        Args:
            platform_code: 平台代码
            
        Returns:
            Type[BaseSpider] 或 None
        """
        return cls._spiders.get(platform_code)
    
    @classmethod
    def list_spiders(cls) -> List[str]:
        """
        列出所有注册的爬虫平台代码
        
        Returns:
            List[str]: 平台代码列表
        """
        return list(cls._spiders.keys())
    
    @classmethod
    def get_spider_info(cls, platform_code: str) -> Optional[Dict]:
        """
        获取爬虫信息
        
        Args:
            platform_code: 平台代码
            
        Returns:
            dict 或 None: {
                "code": "平台代码",
                "name": "平台名称",
                "class": "爬虫类名"
            }
        """
        spider_class = cls.get_spider(platform_code)
        if not spider_class:
            return None
        
        return {
            "code": platform_code,
            "name": spider_class.PLATFORM_NAME,
            "class": spider_class.__name__
        }
    
    @classmethod
    def list_all_spider_info(cls) -> List[Dict]:
        """
        列出所有爬虫信息
        
        Returns:
            List[Dict]: 爬虫信息列表
        """
        return [
            cls.get_spider_info(code)
            for code in cls.list_spiders()
        ]
    
    @classmethod
    def create_spider(cls, platform_code: str, **kwargs) -> BaseSpider:
        """
        创建爬虫实例
        
        Args:
            platform_code: 平台代码
            **kwargs: 传递给爬虫构造函数的参数
            
        Returns:
            BaseSpider: 爬虫实例
            
        Raises:
            ValueError: 如果未找到平台爬虫
        """
        spider_class = cls.get_spider(platform_code)
        if not spider_class:
            available = ", ".join(cls.list_spiders()) or "无"
            raise ValueError(
                f"未找到平台爬虫: {platform_code}。"
                f"可用的平台: {available}"
            )
        
        try:
            spider = spider_class(**kwargs)
            # 检查平台配置
            if not spider._check_platform_config():
                log.warning(f"平台 {platform_code} 配置检查未通过，但继续执行")
            return spider
        except Exception as e:
            log.error(f"创建爬虫 {platform_code} 失败: {str(e)}")
            raise
    
    @classmethod
    def run_all_spiders(cls, days_before=None, enabled_platforms=None, total_limit=None,
                        gov_cities=None, ent_cities=None) -> List:
        """
        运行所有爬虫或指定平台爬虫

        Args:
            days_before: 时间间隔，爬取最近N天内的文件（None表示只爬取当日）
            enabled_platforms: 启用的平台列表（None表示全部启用）
            total_limit: 总爬取数量限制（None表示不限制）
            gov_cities: 政府采购地级市筛选（None/空=不限，仅用于政采云zhejiang平台）
            ent_cities: 国企采购地级市筛选（None/空=不限，用于zcyxxw等企业平台）

        Returns:
            List: 所有爬虫返回的项目列表（合并后）
        """
        all_projects = []
        
        # 确定要运行的平台
        if enabled_platforms is None:
            enabled_platforms = cls.list_spiders()
        else:
            # 验证平台是否存在
            available = set(cls.list_spiders())
            requested = set(enabled_platforms)
            invalid = requested - available
            if invalid:
                log.warning(f"以下平台不存在，将被忽略: {', '.join(invalid)}")
            enabled_platforms = list(requested & available)
        
        if not enabled_platforms:
            log.warning("没有可运行的爬虫平台")
            return all_projects
        
        log.info(f"准备运行 {len(enabled_platforms)} 个平台爬虫: {', '.join(enabled_platforms)}")
        
        # 依次运行每个平台的爬虫
        for platform_code in enabled_platforms:
            # 检查是否已达到总爬取限制
            if total_limit is not None and len(all_projects) >= total_limit:
                log.info(f"已达到总爬取限制 {total_limit}，停止爬取")
                break
            
            try:
                log.info(f"=" * 50)
                log.info(f"开始运行平台: {platform_code}")
                log.info(f"=" * 50)
                
                # 计算当前平台可爬取的数量
                remaining_limit = None
                if total_limit is not None:
                    remaining_limit = total_limit - len(all_projects)
                    log.info(f"当前平台剩余可爬取数量: {remaining_limit}")
                
                # 政府采购→gov_cities，国企采购→ent_cities（zhejiang 是唯一政府平台）
                extra_kwargs = {}
                if platform_code == "zhejiang" and gov_cities:
                    extra_kwargs["gov_cities"] = gov_cities
                elif platform_code != "zhejiang" and ent_cities:
                    extra_kwargs["gov_cities"] = ent_cities
                spider = cls.create_spider(platform_code, days_before=days_before, daily_limit=remaining_limit, **extra_kwargs)
                projects = spider.run()
                
                # 如果有总限制，只添加剩余数量的项目
                if total_limit is not None:
                    remaining = total_limit - len(all_projects)
                    if len(projects) > remaining:
                        projects = projects[:remaining]
                        log.info(f"平台 {platform_code} 实际爬取 {len(projects)} 个项目（已达到总限制）")
                
                all_projects.extend(projects)
                
                log.info(f"平台 {platform_code} 爬取完成，获取 {len(projects)} 个项目，累计已爬取 {len(all_projects)} 个项目")
                
            except Exception as e:
                log.error(f"平台 {platform_code} 爬取失败: {str(e)}", exc_info=True)
                # 继续运行其他平台，不中断整个流程
                continue
        
        log.info(f"=" * 50)
        log.info(f"所有爬虫运行完成，总共获取 {len(all_projects)} 个项目")
        log.info(f"=" * 50)
        
        return all_projects
    
    @classmethod
    def is_registered(cls, platform_code: str) -> bool:
        """
        检查平台是否已注册
        
        Args:
            platform_code: 平台代码
            
        Returns:
            bool: True表示已注册
        """
        return platform_code in cls._spiders

    @classmethod
    def download_one_from_homepage_per_platform(
        cls,
        days_before: Optional[int] = None,
        enabled_platforms: Optional[List[str]] = None,
        per_platform_daily_limit: int = 1,
        verify_download: bool = True,
        exclude_new_projects: bool = True,
        exclude_error_msg: str = "[测试-单文件下载验证已排除]",
    ) -> List[Dict[str, Any]]:
        """
        独立下载验证：对每个平台仅下载“首页首个可用标书文件”（通过 daily_limit=1 实现）。

        返回每个平台的下载结果，UI 可直接展示：
        - 平台爬取入口（project.download_url）
        - 本地服务器文件（project.file_path/file_format，并由 UI 生成 /tender-files/ 链接）

        为避免污染后续解析/AI流程：
        - 默认只将“本次新增的项目”置为 ProjectStatus.EXCLUDED。
        """
        results: List[Dict[str, Any]] = []

        if enabled_platforms is None:
            enabled_platforms = cls.list_spiders()
        else:
            available = set(cls.list_spiders())
            requested = set(enabled_platforms)
            invalid = requested - available
            if invalid:
                log.warning(f"以下平台不存在，将被忽略: {', '.join(invalid)}")
            enabled_platforms = list(requested & available)

        if not enabled_platforms:
            return results

        def _is_valid_file(file_path: Optional[str]) -> bool:
            if not file_path:
                return False
            fp = file_path
            if not os.path.isabs(fp):
                fp = os.path.join(FILES_DIR, fp)
            try:
                return os.path.exists(fp) and os.path.getsize(fp) > 0
            except Exception:
                return False

        def _pick_first_valid(projects: List[TenderProject]) -> tuple[Optional[TenderProject], bool]:
            for p in projects:
                if verify_download:
                    if _is_valid_file(getattr(p, "file_path", None)):
                        return p, True
                else:
                    if getattr(p, "file_path", None):
                        return p, True
            return None, False

        for platform_code in enabled_platforms:
            start_dt = datetime.now()
            status = "success"
            error_msg: Optional[str] = None
            used_fallback = False

            platform_info = cls.get_spider_info(platform_code) or {
                "code": platform_code,
                "name": platform_code,
                "class": "",
            }
            platform_name = platform_info.get("name") or platform_code

            selected_project: Optional[TenderProject] = None
            new_project_ids: List[int] = []
            # 把需要的 ORM 字段在 Session 关闭前“拷贝”成普通变量，
            # 避免 Session 关闭后触发 refresh（你现在遇到的异常就是这个原因）。
            project_id: Optional[str] = None
            project_name: Optional[str] = None
            download_url: Optional[str] = None
            file_path: Optional[str] = None
            file_format: Optional[str] = None
            file_size_kb: Optional[float] = None
            download_verified = False

            try:
                db = next(get_db())
                try:
                    max_id_before = db.query(func.max(TenderProject.id)).scalar() or 0

                    spider = cls.create_spider(
                        platform_code,
                        days_before=days_before,
                        daily_limit=per_platform_daily_limit,
                    )
                    spider.run()

                    new_projects = db.query(TenderProject).filter(
                        TenderProject.id > max_id_before
                    ).all()
                    new_project_ids = [p.id for p in new_projects if p.id is not None]

                    selected_project, _download_ok = _pick_first_valid(new_projects)

                    # 若本次新增没有有效文件，则回退到历史最新项目（不修改其状态）
                    if selected_project is None and verify_download:
                        history_projects = (
                            db.query(TenderProject)
                            .filter(TenderProject.site_name.like(f"%{platform_name}%"))
                            .order_by(TenderProject.id.desc())
                            .limit(30)
                            .all()
                        )
                        selected_project, _download_ok = _pick_first_valid(history_projects)
                        used_fallback = selected_project is not None

                    # Session 仍在作用域内：把 ORM 对象字段拷贝出来
                    if selected_project is not None:
                        project_id = getattr(selected_project, "project_id", None)
                        project_name = getattr(selected_project, "project_name", None)
                        download_url = getattr(selected_project, "download_url", None)
                        file_path = getattr(selected_project, "file_path", None)
                        file_format = getattr(selected_project, "file_format", None)

                    # 仅排除本次新增项目，避免污染后续解析/AI流程
                    if exclude_new_projects and new_project_ids:
                        db.query(TenderProject).filter(
                            TenderProject.id.in_(new_project_ids)
                        ).update(
                            {
                                "status": ProjectStatus.EXCLUDED,
                                "error_msg": exclude_error_msg,
                            },
                            synchronize_session=False,
                        )
                        db.commit()
                finally:
                    try:
                        db.close()
                    except Exception:
                        pass
            except Exception as e:
                status = "failed"
                error_msg = str(e)
                log.error(f"平台 {platform_code} 单文件下载验证失败: {error_msg}", exc_info=True)

            # 生成结果字段（此处只使用上面拷贝的普通变量，不再访问 ORM 对象）
            if verify_download:
                try:
                    if file_path and _is_valid_file(file_path):
                        fp = file_path if os.path.isabs(file_path) else os.path.join(FILES_DIR, file_path)
                        file_size_kb = os.path.getsize(fp) / 1024
                        download_verified = True
                except Exception:
                    pass

            if verify_download and not download_verified:
                status = "failed"
                if not error_msg:
                    error_msg = "未找到有效下载文件（无 file_path 或文件不存在/大小为0）"

            elapsed_ms = int((datetime.now() - start_dt).total_seconds() * 1000)
            results.append(
                {
                    "platform_code": platform_info.get("code"),
                    "platform_name": platform_info.get("name"),
                    "spider_class": platform_info.get("class"),
                    "status": status,
                    "error": error_msg,
                    "elapsed_ms": elapsed_ms,
                    "used_fallback": used_fallback,
                    "per_platform_daily_limit": per_platform_daily_limit,
                    "new_projects_created": len(new_project_ids),
                    "project_id": project_id,
                    "project_name": project_name,
                    "download_url": download_url,
                    "file_path": file_path,
                    "file_format": file_format,
                    "file_size_kb": file_size_kb,
                    "download_verified": download_verified if verify_download else None,
                }
            )

        return results
