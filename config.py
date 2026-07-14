import os
from datetime import timedelta

try:
    # 可选依赖：未安装python-dotenv时也允许系统启动
    from dotenv import load_dotenv  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    def load_dotenv(*args, **kwargs):
        return False

# 加载环境变量
load_dotenv()

# 基础配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
FILES_DIR = os.path.join(BASE_DIR, "tender_files")
REPORT_DIR = os.path.join(BASE_DIR, "reports")

# 报告导出（宁波等）：「来源网站」指向本机已下载标书的 HTTP 根地址，勿带尾部斜杠。
# 示例：http://192.168.1.10:8766 或对 tender_files 做了反向代理的站点根。
# 未配置时，在 Streamlit 内生成报告会尝试用浏览器请求的 Host 推断（仍需网关把
# TENDER_FILES_URL_PREFIX 映射到 FILES_DIR，否则链接需自行可访问）。
APP_PUBLIC_BASE_URL = os.getenv("APP_PUBLIC_BASE_URL", "").strip().rstrip("/")
_tfiles_prefix = os.getenv("TENDER_FILES_URL_PREFIX")
if _tfiles_prefix is None:
    TENDER_FILES_URL_PREFIX = "/tender-files"
else:
    TENDER_FILES_URL_PREFIX = _tfiles_prefix.strip().rstrip("/")

# 日志配置（供 utils/log.py 使用）
LOG_CONFIG = {
    "file_name": os.path.join(LOG_DIR, "tender_system.log"),  # 主日志文件
    "level": os.getenv("LOG_LEVEL", "INFO"),  # 日志级别：DEBUG/INFO/WARNING/ERROR
    "rotation": "100 MB",  # 单个日志文件最大大小，自动轮转
    "retention": "7 days",  # 保留7天历史日志
}

# 数据库配置
# 默认使用SQLite（零配置），也可通过环境变量切换到PostgreSQL
DB_CONFIG = {
    # sqlite / postgresql
    "db_type": os.getenv("DB_TYPE", "sqlite").lower(),

    # SQLite配置
    "db_path": os.getenv("SQLITE_DB_PATH", os.path.join(BASE_DIR, "tender_system.db")),

    # PostgreSQL配置（db_type=postgresql时使用）
    "host": os.getenv("PG_HOST", "127.0.0.1"),
    "port": int(os.getenv("PG_PORT", "5432")),
    "user": os.getenv("PG_USER", "postgres"),
    "password": os.getenv("PG_PASSWORD", "postgres"),
    "db_name": os.getenv("PG_DB_NAME", "tender_system"),
}

# 政采云双 exe 流水线配置
# EXE A（gui_app.exe）获取当日项目编号并复制到剪贴板；
# EXE B（政采云.exe）粘贴编号批量下载，生成「下载记录.csv」并按编号建子文件夹。
_ZCY_SAVE_DIR = os.getenv("ZCY_SAVE_DIR", os.path.join(FILES_DIR, "zcy"))
ZCY_CONFIG = {
    # EXE A：项目编号获取器
    "code_exe": {
        "path": os.path.join(BASE_DIR, "gui_app.exe"),
        "window_title": "浙江政府采购网 - 项目编号获取",
        # Tkinter 程序按钮无文字，改用相对坐标点击：点击前窗口会被调整到 ref_size。
        # 坐标为按钮中心相对窗口左上角的 (x, y)。ref_size = (宽, 高)。
        "ref_size": (918, 661),
        "fetch_button_xy": (658, 123),   # 「获取当日项目编号」中心
        "copy_button_xy": (808, 123),    # 「复制全部项目编号」中心
    },
    # EXE B：批量下载工具
    "download_exe": {
        "path": os.path.join(BASE_DIR, "政采云.exe"),
        "window_title": "政采云批量下载工具 (智能解析+重试)",
        # 坐标点击（同 EXE A）。ref_size = (宽, 高)，坐标为控件中心相对窗口左上角。
        "ref_size": (818, 697),
        "save_dir_xy": (366, 65),    # 「保存目录」输入框中心
        "codes_xy": (409, 211),      # 「项目编号」文本框中心
        "start_button_xy": (281, 325),  # 「开始批量处理」按钮中心（最左，蓝色高亮）
    },
    # 标书文件与记录表保存目录（= tender_files/zcy）
    "save_dir": _ZCY_SAVE_DIR,
    # 兼容旧字段名：解析逻辑读取 output_dir
    "output_dir": _ZCY_SAVE_DIR,
    "csv_name": "下载记录.csv",              # EXE B 每次生成，会被下次覆盖
    "total_csv_name": "total_下载记录.csv",  # 累积历史表（本系统维护，不被覆盖）
    "supported_extensions": (".doc", ".docx", ".pdf"),
    # 超时（秒）
    "fetch_timeout": int(os.getenv("ZCY_FETCH_TIMEOUT", "300")),        # A 抓编号上限
    "download_timeout": int(os.getenv("ZCY_DOWNLOAD_TIMEOUT", "7200")),  # B 下载上限
    "no_activity_timeout": int(os.getenv("ZCY_NO_ACTIVITY_TIMEOUT", "180")),  # 无活动快速失败
    "skip_gui": os.getenv("ZCY_SKIP_GUI", "false").lower() == "true",   # 调试：跳过exe直接解析
}

# 区划码（地区列）→ 城市名映射，取前4位定市；3399=省本级
ZCY_DISTRICT_MAP = {
    "3301": "杭州市", "3302": "宁波市", "3303": "温州市", "3304": "嘉兴市",
    "3305": "湖州市", "3306": "绍兴市", "3307": "金华市", "3308": "衢州市",
    "3309": "舟山市", "3310": "台州市", "3311": "丽水市", "3399": "浙江省本级",
}

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

# 存储与清理配置
# 用于磁盘告警、自动清理以及定时清理设置
STORAGE_CONFIG = {
    "auto_cleanup_enabled": True,  # 是否启用自动清理
    "cleanup_interval_days": 30,  # 保留最近N天的文件
    "cleanup_schedule": "daily",  # 清理频率：daily/weekly/monthly
    "cleanup_time": "02:00",  # 清理执行时间（24小时制 HH:MM）
    "disk_warning_threshold": 80.0,  # 磁盘使用率告警阈值（%）
    "disk_critical_threshold": 90.0  # 磁盘使用率严重告警阈值（%）
}

# AI配置 - 支持本地和云模型两套流程
AI_CONFIG = {
    "provider": "dashscope",  # 默认使用DashScope

    # 阿里云DashScope配置
    "dashscope": {
        "api_key": os.getenv("DASHSCOPE_API_KEY", "sk-bbd04b19f31c4c1b930fbe51bec2eb80"),
        "base_url": os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        "model_name": os.getenv("DASHSCOPE_MODEL_NAME", "qwen-plus-2025-07-28"),  # 支持长文本的模型
        "temperature": 0.05,
        "max_tokens": 4000  # 适当的输出token限制
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
        "enable": False,  # 启用请求频率控制
        "max_requests_per_hour": 80,  # 每小时最大请求数（留出缓冲，实际约37-38个）
        "min_interval_seconds": 30,  # 两次请求之间的最小间隔（秒）
        "burst_allowance": 5,  # 突发请求允许数量（用于处理积压）
    },

    # 规则匹配配置
    "rule_matching": {
        "use_semantic_match": True,  # 是否启用语义匹配（True：使用语义匹配，False：使用关键词匹配）
        "semantic_threshold": 0.7,  # 语义相似度阈值（0-1之间，越高越严格，建议0.6-0.8）
        "embedding_model": "nomic-embed-text",  # 使用的embedding模型（需要支持中文）
    },

    # 服务类项目判断配置
    "service_check": {
        "enable": True,  # 是否启用服务类项目判断（False：手动启用，需要时设为True）
    },

    # 资质关键词检查配置
    "qualification_keyword_check": {
        "enable": False,  # 是否启用资质关键词检查（False：手动启用，需要时设为True）
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
        },

        {
            "rule_name": "软件演示/截图类评分项自动满分",
            "trigger_condition": "标书评分项中出现以下任一关键词时触发：'软件截图','系统截图','界面截图','功能演示','现场演示','系统演示','软件著作权','软件登记证','系统功能','平台功能','管理后台','数据大屏','可视化展示','驾驶舱','APP','小程序','微信公众号','操作界面','用户界面','UI','信息化系统','管理平台','智慧平台','软件平台','Web端','移动端','PC端','后台管理系统'",
            "conclusion": "✅ 自动满分。软件/界面类需求可通过开发演示终端满足，不构成履约障碍。战术：投标前用Claude搭建可演示终端，截图编入标书，演示环节现场操作。例外（不触发）：'已部署运行≥3年','与现有系统对接','等保测评','密评','CMMI'",
            "rule_type": "评分穿透（自动满分）",
            "is_active": 1
        },
        {
            "rule_name": "现场踏勘",
            "trigger_condition": "项目要求现场踏勘得分的",
            "conclusion": "项目要求现场踏勘都，项目地址在衢州大市的范围内的，该项得满分，否则该项不得分。",
            "rule_type": "未填写",
            "is_active": 1
        },
        {
            "rule_name": "多子项客观评分拆分计分规则",
            "trigger_condition": "项目客观评分条目包含2个及以上独立计分小项(体系认证多项计分、软件著作权多项计分、人员多证书分项计分、业绩多条累加计分等)",
            "conclusion": "本条目禁止整体直接判定满分，各子项独立核算得分，同一条目总分为所有子项得分累加值，单项子项无材料不得分，仅豁免“无材料直接整条目计0分”否决规则",
            "rule_type": "计分逻辑约束规则",
            "is_active": 1
        },
        {
            "rule_name": "体系认证与软件著作权分项计分规则",
            "trigger_condition": "招标文件评分分项拆分设置:1项专项体系认证固定分值+多项通用体系认证累加分值+软件著作权累加分值",
            "conclusion": "三类子项独立分别计分，无对应证书的子项计0分，不得因任意一个子项得分就将整个评分条目判定为满分",
            "rule_type": "证书类评分规则",
            "is_active": 1
        }

    ],
    "rule_types": ["证书类", "业绩类", "检测报告类", "人员资质类", "排除类", "其他类", "价格类"]
}

# 客观分判定配置
OBJECTIVE_SCORE_CONFIG = {
    "loss_score_threshold": 1.0,  # 客观分丢分阈值（默认1.0分），丢分≤此阈值时，即使判定为"客观分不满分"也改为"推荐参与"；失分>此阈值时，即使AI判定为"推荐参与"也改为"不推荐参与"
    "enable_loss_score_adjustment": True,  # 是否启用丢分阈值调整功能
}
