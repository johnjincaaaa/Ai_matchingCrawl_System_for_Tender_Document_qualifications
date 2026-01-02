from celery import Celery
from celery.schedules import crontab
import os
from utils.log import log  # 新增：导入日志实例（之前缺失导致 NameError）
from utils.db import save_project, ProjectStatus, get_db  # 新增：导入 get_db
# 初始化 Celery
app = Celery(
    "tender_system",
    broker="redis://localhost:6379/0",  # 若未安装 Redis，可先注释（仅测试单模块）
    backend="redis://localhost:6379/0",
    include=[
        "spider.tender_spider",
        "parser.file_parser",
        "ai.qualification_analyzer",
        "report.report_generator"
    ]
)

# 配置 Celery
app.conf.update(
    result_expires=3600,  # 结果过期时间（1小时）
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
)

# 定义定时任务（每天凌晨2点执行）
# 测试模式：设置 test_mode=True 和 daily_limit=2 来限制爬取数量
# 示例：("local", True, 2) 表示 (model_type="local", test_mode=True, daily_limit=2)
# 注意：test_mode=True 时会自动将 daily_limit 设为 2，即使传入了其他值
app.conf.beat_schedule = {
    "daily-tender-task": {
        "task": "tasks.scheduler.run_daily_task",
        "schedule": crontab(hour=2, minute=0),
        "args": (),  # 测试模式示例：("local", True, 2) 或 (None, True, None)
    },
}

@app.task
def run_daily_task(model_type=None, test_mode=False, daily_limit=None):
    """每日任务主流程（适配本地文件测试）
    
    Args:
        model_type: AI模型类型（'local' 或 'cloud'）
        test_mode: 是否为测试模式（True时只爬取2个文件）
        daily_limit: 爬取数量限制（None时使用config中的默认值，test_mode=True时自动设为2）
    """
    log.info("="*50)
    log.info("开始执行每日标书资质匹配任务")
    if test_mode:
        log.info("⚠️ 测试模式：限制爬取数量为2个文件")
    log.info("="*50)

    try:
        from config import TEST_CONFIG
        from utils.db import save_project, ProjectStatus
        from datetime import datetime
        import os

        # 测试模式：跳过爬虫，直接使用本地文件创建项目数据
        if TEST_CONFIG["enable_test_mode"]:
            log.info("启用本地测试模式，跳过爬虫环节")
            all_projects = []
            db = next(get_db())

            for file_path in TEST_CONFIG["test_files"]:
                if not os.path.exists(file_path):
                    log.warning(f"测试文件不存在：{file_path}，跳过")
                    continue

                # 构造项目数据（模拟爬虫爬取的结果）
                file_name = os.path.basename(file_path)
                project_name = file_name.split(".")[0]  # 从文件名提取项目名称
                file_format = file_name.split(".")[-1].lower()  # 提取文件格式

                project_data = {
                    "project_name": project_name,
                    "site_name": "本地测试文件",
                    "publish_time": datetime.now(),  # 模拟发布时间
                    "download_url": "local_file://" + file_path,  # 模拟下载链接
                    "file_path": file_path,
                    "file_format": file_format,
                    "status": ProjectStatus.DOWNLOADED  # 标记为已下载
                }

                # 保存到数据库
                saved_project = save_project(db, project_data)
                all_projects.append(saved_project)
                log.info(f"已添加本地测试项目：{project_name}")

            db.close()
            log.info(f"本地测试项目加载完成，共 {len(all_projects)} 个项目")

            # 无测试项目时退出
            if len(all_projects) == 0:
                log.warning("未找到有效本地测试文件，任务终止")
                return
        else:
            # 正常模式：执行爬虫（保留原有逻辑）
            from spider.tender_spider import run_all_spiders, ZheJiangTenderSpider
            
            log.info("第一步：开始爬取项目")
            
            # 测试运行：只爬取2个文件
            if test_mode:
                log.info("⚠️ 测试模式：限制爬取数量为2个文件")
                spider = ZheJiangTenderSpider(daily_limit=2)
                all_projects = spider.run()
            elif daily_limit is not None:
                log.info(f"📊 使用指定的爬取数量限制：{daily_limit}")
                spider = ZheJiangTenderSpider(daily_limit=daily_limit)
                all_projects = spider.run()
            else:
                all_projects = run_all_spiders()
            
            if len(all_projects) == 0:
                log.info("未爬取到有效项目，跳过后续步骤")
                return

        # 2. 解析文件（本地文件与爬虫文件逻辑一致，无需修改）
        from parser.file_parser import FileParser
        log.info("第二步：开始解析项目文件")
        parser = FileParser()
        parser.run()

        # 3. AI分析与比对
        from ai.qualification_analyzer import AIAnalyzer
        log.info("第三步：开始AI资质分析与比对")
        analyzer = AIAnalyzer(model_type=model_type)
        analyzer.run()

        # 4. 生成报告
        from report.report_generator import ReportGenerator
        log.info("第四步：开始生成每日报告")
        generator = ReportGenerator()
        generator.generate_report()

        log.info("="*50)
        log.info("每日标书资质匹配任务（本地测试模式）执行完成")
        log.info("="*50)
    except Exception as e:
        log.error(f"每日任务执行失败：{str(e)}", exc_info=True)
        raise