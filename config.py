import os
from datetime import timedelta

# 基础配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
FILES_DIR = os.path.join(BASE_DIR, "tender_files")
REPORT_DIR = os.path.join(BASE_DIR, "reports")

# 创建目录
for dir_path in [LOG_DIR, FILES_DIR, REPORT_DIR]:
    os.makedirs(dir_path, exist_ok=True)

# 爬虫配置
# ========== 爬虫配置 ==========
# config.py

# 爬虫配置
SPIDER_CONFIG = {
    "daily_limit": 4,  # 每日总爬取限制（每个分类平均150个）
    "zhejiang_max_pages": 35,
    "files_dir": FILES_DIR,  # 使用绝对路径
    "anti_crawl": {
        "request_interval": 2,
        "retry_times": 3,
        "timeout": 15  # 增加超时时间以适应文件下载
    }
}

# 新增：测试模式配置（本地文件测试时启用）
TEST_CONFIG = {
    "enable_test_mode": False,  # 开启测试模式（跳过爬虫）
    "test_files": [  # 本地测试文件列表（自动读取 tender_files/ 目录，也可手动指定）
        os.path.join(FILES_DIR, "招标变更公告.pdf"),
        os.path.join(FILES_DIR, "XX市综合管廊及配套工程标书.pdf"),
    ]
}

# 解析配置
PARSE_CONFIG = {
    "support_formats": ["pdf", "docx", "doc"],  # 支持的文件格式
    "ocr_lang": "chi_sim",  # OCR识别语言（中文）
    "tesseract_path": r"E:\标书ai匹配系统ByJohnjincaaa\a\Tesseract-OCR\Tesseract-OCR\tesseract.exe",
    'poppler_path': r'E:\标书ai匹配系统ByJohnjincaaa\a\Release-24.02.0-0\poppler-24.02.0\Library\bin'
}

# AI配置 - 支持本地和云模型两套流程
AI_CONFIG = {
    "provider": "ollama",  # 只保留Ollama配置
    "ollama": {
        # 默认使用云模型
        "default_model": "cloud",  # 可选值: "local" 或 "cloud "
        
        # 本地模型配置
        "local_model": {
            "model_name": "llama3:8b",  # 本地轻量级模型
            "base_url": "http://localhost:11434",  # Ollama服务地址
            "temperature": 0.05,  # 低温度保证结果稳定性
            "cuda": True  # CUDA加速选项
        },
        
        # 云模型配置
        "cloud_model": {
            "model_name": "qwen3-coder:480b-cloud",  # 云模型
            "base_url": "http://localhost:11434",  # Ollama服务地址
            "temperature": 0.05,  # 低温度保证结果稳定性
            "cuda": True  # CUDA加速选项
        }
    },
    "extract_prompt_path": os.path.join(BASE_DIR, "prompts", "extract_prompt.txt"),
    "compare_prompt_path": os.path.join(BASE_DIR, "prompts", "compare_prompt.txt"),
    "service_check_prompt_path": os.path.join(BASE_DIR, "prompts", "service_check_prompt.txt"),
    
    # 文本预处理优化配置（已禁用预处理优化，使用完整文本）
    "preprocessing": {
        "enable_preprocessing": False,  # 是否启用文本预处理（False：使用完整文本，不进行任何压缩或优化）
        "max_text_length": 1000000,  # 预处理后最大文本长度（字符），设置为很大的值以禁用压缩
        "context_before": 10000,  # 表格前保留的上下文（字符）
        "context_after": 10000,  # 表格后保留的上下文（字符）
        "extract_range": 6000,  # 关键词后提取的文本范围（字符）
        "enable_aggressive_compression": False,  # 禁用智能压缩模式（使用完整文本）
        "remove_redundant_content": False,  # 禁用移除冗余内容（保留所有内容）
        "min_score_table_length": 2000,  # 评分表最小保留长度（字符）
    },
    
    # 请求频率控制配置
    "rate_limiting": {
        "enable": True,  # 启用请求频率控制
        "max_requests_per_hour": 80,  # 每小时最大请求数（留出缓冲，实际约37-38个）
        "min_interval_seconds": 30,  # 两次请求之间的最小间隔（秒）
        "burst_allowance": 5,  # 突发请求允许数量（用于处理积压）
    },
    
    # 规则匹配配置
    "rule_matching": {
        "use_semantic_match": True,  # 是否启用语义匹配（True：使用语义匹配，False：使用关键词匹配）
        "semantic_threshold": 0.7,  # 语义相似度阈值（0-1之间，越高越严格，建议0.6-0.8）
        "embedding_model": "nomic-embed-text",  # 使用的embedding模型（需要支持中文）
    }
}

# 公司资质库（支持从Excel导入，此处为示例）
COMPANY_QUALIFICATIONS = {
    # "企业资质": [
    #     "满足"
    # ],
    # "人员资质": [
    #     "满足"
    # ],
    # "设备要求": [
    #     "满足"
    # ],
    # "业绩要求": [
    #     "满足"
    # ],
    # "其他要求": [
    #    "满足"
    # ]
}

# A类证书管理默认配置
# A类证书管理默认配置
A_CERTIFICATE_CONFIG = {
    "default_certificates": [
        # 1. 体系认证（原有三体系，修正职业健康安全认证标准）
        {
            "certificate_name": "质量管理体系认证证书",
            "certificate_number": "ISO9001-2020-00001",
            "issuing_authority": "中国认证认可监督管理委员会",
            "certificate_type": "体系认证",
            "is_active": 1
        },
        {
            "certificate_name": "环境管理体系认证证书",
            "certificate_number": "ISO14001-2015-00001",
            "issuing_authority": "中国认证认可监督管理委员会",
            "certificate_type": "体系认证",
            "is_active": 1
        },
        {
            "certificate_name": "职业健康安全管理体系认证证书",
            "certificate_number": "ISO45001-2018-00001",  # 修正：ISO45001而非14001
            "issuing_authority": "中国认证认可监督管理委员会",
            "certificate_type": "体系认证",
            "is_active": 1
        },
        
 
        {
            "certificate_name": "信息技术服务管理体系认证", 
            "certificate_number": "iso/iec 20000-1:2018",
            "issuing_authority": "中国认证认可监督管理委员会",
            "certificate_type": "信息技术服务管理体系认证",
            "is_active": 1
        },
        # 3. 许可证（新增示例）
        {
            "certificate_name": "信息安全管理体系认证",
            "certificate_number": "iso/iec 27001-1:2022",
            "issuing_authority": "中国认证认可监督管理委员会",
            "certificate_type": "信息安全管理体系认证",
            "is_active": 1
        },
      
    ],
    "certificate_types": ["体系认证", "资质证书", "许可证", "检测报告", "其他证书"]
}

# B类规则管理默认配置
B_RULE_CONFIG = {
    "default_rules": [

        {
            "rule_name": "业绩要求",
            "trigger_condition": "项目要求有类似项目业绩",
            "conclusion": "无论是否拥有类似项目业绩，均满足本条款要求，无需提供任何业绩相关证明材料",
            "rule_type": "业绩类",
            "is_active": 1
        },
        {
            "rule_name": "检测报告都具备",
            "trigger_condition": "项目要求有检测报告的，且未明确要求政府官方网站备案或可查询验证",
            "conclusion": "我公司可以出具任何的检测报告,判定为满足",
            "rule_type": "检测报告类",
            "is_active": 1
        },
        {
            "rule_name": "政府官方网站备案要求排除规则",
            "trigger_condition": "要求通过政府官方网站备案、可查询验证、官方网站截屏、备案公告截屏、能效标识网、备案查询、官方备案",
            "conclusion": "该要求明确需要政府官方网站备案或可查询验证，不符合B类规则覆盖范围，需要提供真实的政府官方网站备案材料",
            "rule_type": "排除类",
            "is_active": 1
        },
         {
            "rule_name": "人员资质与经验通用判定",
            "trigger_condition": """评分标准未明确要求需通过政府官方网站（含人社、行业主管部门、人力资源和社会保障局等）备案 / 可查询验证的官方颁发文件，且涉及以下任意类别的：
                        1. 职称类：含编审、编辑相关中级 / 高级 / 副高级及以上职称，或行业对应专业技术职业资格证书；
                        2. 经验类：含指定年限的岗位工作经验、特定领域（如图书 / 历史文献 / 专业丛书）的业务经验、审校 / 编辑类实操经验；
                        3. 其他类：非政府背书的培训等级证书、行业协会 / 机构出具的资质证明""",
            "conclusion": "我公司自行出具的对应职称证明、工作经验证明、业务经验材料、资质 / 证书文件，均判定为满足",
            "rule_type": "人员资质类",
            "is_active": 1
        },
        {
            "rule_name": "承诺响应",
            "trigger_condition": "项目要求有承诺响应、提供承诺、提供说明和承诺、承诺文件、承诺书、书面承诺",
            "conclusion": "我公司可以出具任何承诺响应的文件,判定为满足",
            "rule_type": "其他类",
            "is_active": 1
        },
        {
            "rule_name": "技术参数响应",
            "trigger_condition": "项目对产品参数响应情况进行打分",
            "conclusion": "无论是否有对产品参数的响应情况，该项均判定为满分。",
            "rule_type": "技术参数类",
            "is_active": 1
        },
        {
            "rule_name": "提供生产设备发票",
            "trigger_condition": "项目评分有要求提供设备发票加分的",
            "conclusion": "无论是否拥有类似设备发票，均满足本条款要求，无需提供任何发票相关证明材料",
            "rule_type": " 提供设备发票",
            "is_active": 1
        },
        {
            "rule_name": "价格类评分项满分",
            "trigger_condition": "项目评分项中包含价格、报价、投标报价、价格分、报价分、价格评审、价格评分、价格响应、报价响应、价格合理性、价格优势、价格竞争力、投标价格、报价金额、价格因素、价格部分、报价部分、投标价等相关关键词",
            "conclusion": "价格类评分项均判定为满分，无需提供任何证明材料",
            "rule_type": "价格类",
            "is_active": 1
        },
        {
            "rule_name": "认证范围智能匹配要求",
            "trigger_condition": "项目要求中包含 “认证范围需覆盖 [具体类别]”",
            "conclusion": "1. 项目类别是 “金属结构 / 机械设备 / 电子专用设备销售” 的子类别（如农用机械设备→机械设备）→符合得分；2. 项目类别与上述范围（含同义词）匹配→符合得分；3. 项目类别超范围→不符合不得分；4. 无认证范围要求→符合得分",
            "rule_type": "认证范围智能匹配要求",
            "is_active": 1
        },
        {
            "rule_name": "软件著作权证书要求",
            "trigger_condition": "项目要求有软件著作权的",
            "conclusion": "涉及到具体名称的软件著作权则不符合（不得分），不涉及到具体名称的则符合要求（得分）。",
            "rule_type": "软件著作权证书要求",
            "is_active": 1
        }



    ],
    "rule_types": ["证书类", "业绩类", "检测报告类", "人员资质类", "排除类", "其他类", "价格类"]
}

# 数据库配置（原 PostgreSQL 配置注释/删除，替换为以下内容）
DB_CONFIG = {
    "db_type": "sqlite",  # 改为 sqlite
    "db_path": os.path.join(BASE_DIR, "tender_system.db"),  # SQLite 数据库文件路径
}

# 日志配置
LOG_CONFIG = {
    "level": "INFO",
    "file_name": os.path.join(LOG_DIR, "tender_system.log"),
    "rotation": "100 MB",  # 日志轮转大小
    "retention": "7 days",  # 日志保留时间
}

# 存储管理配置
STORAGE_CONFIG = {
    "auto_cleanup_enabled": True,  # 是否启用自动清理
    "cleanup_interval_days": 30,  # 自动清理间隔（保留最近N天的文件）
    "cleanup_schedule": "daily",  # 清理计划：daily（每天）、weekly（每周）、monthly（每月）
    "cleanup_time": "02:00",  # 清理时间（24小时制）
    "disk_warning_threshold": 80.0,  # 磁盘使用率警告阈值（百分比）
    "disk_critical_threshold": 90.0,  # 磁盘使用率严重警告阈值（百分比）
    "clean_by_status": {
        "enabled": False,  # 是否根据项目状态清理
        "statuses": ["已比对"],  # 要清理的项目状态
        "keep_days": 90  # 即使状态匹配，也保留最近N天的文件
    },
    "report_retention_days": 90,  # 报告文件保留天数
    "file_retention_days": 30,  # 标书文件保留天数（已比对的项目）
}

# 客观分判定配置
OBJECTIVE_SCORE_CONFIG = {
    "loss_score_threshold": 1.0,  # 客观分丢分阈值（默认1.0分），丢分≤此阈值时，即使判定为"客观分不满分"也改为"推荐参与"；失分>此阈值时，即使AI判定为"推荐参与"也改为"不推荐参与"
    "enable_loss_score_adjustment": True,  # 是否启用丢分阈值调整功能
}