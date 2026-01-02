# 标书AI匹配系统 - 项目说明文档

## 项目概述
![img_1.png](pics/img_1.png)
![img.png](pics/img.png)

这是一个基于Python和Streamlit开发的标书资质自动匹配系统，主要用于：
- 自动爬取浙江省政府采购网的招标公告
- 解析标书文件（PDF、DOC、DOCX等格式）
- 使用AI分析项目资质要求
- 自动匹配公司资质库（A类证书库和B类规则库）
- 生成Excel格式的匹配报告

## 技术栈

- **前端框架**: Streamlit 1.51.0
- **后端语言**: Python 3.12
- **数据库**: SQLite
- **AI模型**: Ollama (支持本地模型和云模型)
- **主要依赖**: 
  - LangChain (AI框架)
  - SQLAlchemy (ORM)
  - PyPDF2, PyMuPDF (PDF解析)
  - python-docx (Word文档解析)
  - win32com (Windows COM组件，用于DOC文件)
  - openpyxl (Excel生成)
  - requests (HTTP请求)

## 项目结构

```
a/
├── app.py                      # Streamlit主应用入口
├── config.py                   # 配置文件（爬虫、AI、数据库等配置）
├── auto_run_full_process.py    # 命令行全流程执行脚本
├── check_task_status.py        # 任务状态检查脚本
├── requirements.txt            # Python依赖包列表
├── tender_system.db           # SQLite数据库文件
├── task_schedules.json        # 定时任务配置
│
├── spider/                    # 爬虫模块
│   └── tender_spider.py      # 浙江省招标网爬虫
│
├── parser/                    # 文件解析模块
│   └── file_parser.py        # 文件解析器（支持PDF、DOC、DOCX、ZIP）
│
├── ai/                        # AI分析模块
│   └── qualification_analyzer.py  # 资质分析器
│
├── report/                    # 报告生成模块
│   └── report_generator.py   # Excel报告生成器
│
├── utils/                     # 工具模块
│   ├── db.py                 # 数据库操作
│   ├── log.py                # 日志管理
│   ├── task_scheduler.py     # Windows任务计划管理
│   ├── storage_manager.py    # 存储空间管理
│   └── auto_cleanup.py       # 自动清理脚本
│
├── tasks/                     # 任务调度模块
│   └── scheduler.py          # Celery任务调度（可选）
│
├── prompts/                   # AI提示词模板
│   ├── extract_prompt.txt    # 资质提取提示词
│   ├── compare_prompt.txt    # 资质比对提示词
│   └── service_check_prompt.txt  # 服务类判断提示词
│
├── docs/                      # 文档目录
│   ├── SPIDER_QUOTA_LOGIC.md
│   ├── SPIDER_DAYS_BEFORE_LOGIC.md
│   └── ...
│
├── tender_files/              # 标书文件存储目录
├── reports/                   # 报告文件存储目录
└── logs/                      # 日志文件目录
```

## 核心功能模块

### 1. 爬虫模块 (spider/tender_spider.py)

**功能**：
- 爬取浙江省政府采购网（zfcg.czt.zj.gov.cn）的招标公告
- 支持政府类和非政府类两个分类
- 支持12个地级市的区域筛选
- 自动下载标书文件（PDF、DOC、DOCX等）

**主要配置**（config.py）：
- `daily_limit`: 每日爬取限制（默认4个）
- `zhejiang_max_pages`: 最大爬取页数（默认35页）
- `days_before`: 时间间隔，爬取最近N天内的文件

**特点**：
- 自动去重（基于project_id）
- 支持重试机制
- 按区域和分类均衡爬取

### 2. 文件解析模块 (parser/file_parser.py)

**支持格式**：
- PDF: 使用PyPDF2解析，失败时使用OCR（Tesseract）
- DOCX: 使用python-docx解析
- DOC: 使用Word COM组件或LibreOffice转换
- DOCM: 启用宏的Word文档，转换为DOCX后解析
- ZIP: 自动解压并识别招标文件
- TXT: 直接读取

**特点**：
- 完整提取表格内容（评分表）
- 支持合并单元格处理
- 自动清理Word进程，防止堵塞
- 支持文件锁机制，防止并发冲突

### 3. AI分析模块 (ai/qualification_analyzer.py)

**功能**：
1. **资质提取**：从标书文本中提取评分办法和资质要求
2. **资质比对**：将项目要求与公司资质库进行匹配
3. **服务类判断**：自动识别并过滤服务类项目

**AI模型配置**：
- 支持本地模型（llama3:8b）和云模型（qwen3-coder:480b-cloud）
- 通过Ollama服务调用
- 支持CUDA加速

**匹配规则**：
- **A类证书库**：精确匹配证书要求
- **B类规则库**：规则匹配（如业绩要求、检测报告、承诺响应等）
- 排除规则：明确要求政府官方网站备案的，不适用B类规则

**请求频率控制**：
- 每小时最多80个请求
- 最小间隔30秒
- 支持突发请求

### 4. 报告生成模块 (report/report_generator.py)

**功能**：
- 生成Excel格式的匹配报告
- 支持按时间、区域、采购类型筛选
- 自动提取客观分可得分
- 格式化输出（表头样式、自动筛选等）

**报告字段**：
- 项目ID、项目名称、省份、城市、区域
- 采购类型、来源网站、发布时间
- 文件格式、状态、最终判定
- 客观分总分值、错误信息

### 5. 数据库模块 (utils/db.py)

**数据表**：
1. **tender_projects**: 项目主表
   - 基本信息：项目名称、来源网站、发布时间等
   - 文件信息：文件路径、文件格式
   - 分析结果：解析内容、资质要求、比对结果、最终判定
   - 状态管理：项目状态（待处理、已下载、已解析、已比对、异常）

2. **company_qualifications**: 公司资质表
   - 分类：企业资质、人员资质、设备要求、业绩要求、其他要求

3. **class_a_certificates**: A类证书库
   - 证书名称、证书编号、颁发机构、有效期等

4. **class_b_rules**: B类规则库
   - 规则名称、触发条件、结论、规则类型

**索引优化**：
- project_id、status、publish_time、final_decision、region等字段已建立索引

## 配置文件说明 (config.py)

### 爬虫配置
```python
SPIDER_CONFIG = {
    "daily_limit": 4,              # 每日爬取限制
    "zhejiang_max_pages": 35,      # 最大页数
    "anti_crawl": {
        "request_interval": 2,     # 请求间隔（秒）
        "retry_times": 3,          # 重试次数
        "timeout": 15              # 超时时间（秒）
    }
}
```

### AI配置
```python
AI_CONFIG = {
    "provider": "ollama",
    "ollama": {
        "default_model": "cloud",  # 默认模型类型
        "local_model": {...},      # 本地模型配置
        "cloud_model": {...}       # 云模型配置
    },
    "rate_limiting": {
        "enable": True,
        "max_requests_per_hour": 80,
        "min_interval_seconds": 30
    }
}
```

### 存储配置
```python
STORAGE_CONFIG = {
    "auto_cleanup_enabled": True,
    "cleanup_interval_days": 30,      # 保留最近30天
    "disk_warning_threshold": 80.0,   # 磁盘使用率警告阈值
}
```

## 使用方式

### 1. Web界面使用（Streamlit）

启动命令：
```bash
streamlit run app.py
```

主要功能页面：
- **项目列表**：查看所有项目，支持筛选和搜索
- **流程控制**：执行爬虫、解析、AI分析、生成报告
- **资质管理**：管理公司资质、A类证书库、B类规则库
- **定时任务**：创建和管理Windows定时任务
- **存储管理**：查看存储空间，执行清理

### 2. 命令行使用

全流程执行：
```bash
python auto_run_full_process.py --daily-limit 10 --days-before 0 --model-type cloud
```

参数说明：
- `--daily-limit`: 爬取数量限制
- `--days-before`: 时间间隔（0表示只爬取当日）
- `--model-type`: AI模型类型（local/cloud）
- `--test-mode`: 测试模式（只爬取2个文件）

### 3. 定时任务

使用Windows任务计划程序创建定时任务：
- 在Web界面"定时任务"页面创建
- 或使用 `utils/task_scheduler.py` 手动创建

## 项目状态流转

```
待处理 → 已下载 → 已解析 → 已比对
  ↓         ↓         ↓         ↓
异常      异常      异常      异常
```

- **待处理**: 初始状态
- **已下载**: 文件下载完成
- **已解析**: 文件解析完成，提取了评分表内容
- **已比对**: AI分析完成，生成了匹配结果
- **异常**: 处理过程中出错

## 重要特性

### 1. 自动重试机制
- 解析失败自动重试（最多3次）
- AI分析失败自动重试（最多3次）
- 多次失败后标记为"跳过-多次失败"

### 2. 服务类项目过滤
- 自动识别服务类项目（如图书编辑、咨询服务等）
- 服务类项目自动删除，不参与分析

### 3. 客观分判定
- 自动区分客观分和主观分
- 价格相关评分项归类为主观分
- 计算客观分可得分和得分率

### 4. 存储管理
- 自动清理旧文件（默认保留30天）
- 磁盘使用率监控
- 支持按项目状态清理

## 依赖安装

```bash
pip install -r requirements.txt
```

**特殊依赖**：
- **Tesseract OCR**: 用于PDF OCR识别
  - 安装路径需配置在 `config.py` 的 `PARSE_CONFIG["tesseract_path"]`
- **Poppler**: 用于PDF处理
  - 安装路径需配置在 `config.py` 的 `PARSE_CONFIG["poppler_path"]`
- **Microsoft Word**: 用于DOC文件解析（可选，也可使用LibreOffice）

## 日志系统

- 主日志：`logs/tender_system.log`
- 自动运行日志：`logs/auto_run_YYYYMMDD_HHMMSS.log`
- 日志轮转：100MB自动轮转
- 日志保留：7天

## 常见问题

### 1. Word COM组件不可用
- 确保已安装Microsoft Word（完整版）
- 以管理员身份运行程序
- 或安装LibreOffice作为备用方案

### 2. Ollama服务连接失败
- 确保Ollama服务已启动：`ollama serve`
- 检查端口11434是否被占用
- 检查防火墙设置

### 3. 文件解析超时
- 大文件（>50MB）可能需要较长时间
- 可在 `file_parser.py` 中调整 `parse_timeout_seconds`

### 4. 数据库锁定
- SQLite支持多线程，但建议避免并发写入
- 如遇锁定，等待片刻后重试

## 开发说明

### 添加新的爬虫源
1. 在 `spider/` 目录创建新的爬虫类
2. 实现 `run()` 方法
3. 在 `spider/tender_spider.py` 的 `run_all_spiders()` 中注册

### 添加新的B类规则
1. 在Web界面"资质管理" → "B类规则库"中添加
2. 或在 `config.py` 的 `B_RULE_CONFIG["default_rules"]` 中添加

### 修改AI提示词
- 编辑 `prompts/` 目录下的对应文件
- 修改后重启应用生效

## 版本信息

- **Python版本**: 3.x
- **Streamlit版本**: 1.51.0
- **数据库**: SQLite
- **最后更新**: 2025-01-02

## 注意事项

1. **数据备份**：定期备份 `tender_system.db` 数据库文件
2. **存储空间**：定期清理旧文件，避免磁盘空间不足
3. **AI模型**：确保Ollama服务正常运行，模型已下载
4. **网络环境**：爬虫需要稳定的网络连接
5. **Windows环境**：部分功能（如Word COM）仅支持Windows系统

---

**项目立项兼维护者**: Johnjincaaa 
## 未经允许禁止商用

