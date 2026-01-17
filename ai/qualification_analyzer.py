from langchain_community.llms import Ollama
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from pydantic import BaseModel, Field
import os
import re
import json
from typing import Dict, List, Optional, Tuple, Any
from config import AI_CONFIG, COMPANY_QUALIFICATIONS
from utils.log import log
import time
from datetime import datetime, timedelta
from collections import deque
from utils.db import get_db, TenderProject, ProjectStatus, update_project, get_company_qualifications, get_class_a_certificates, get_class_b_rules

# 定义输出验证模型
class ExtractedRequirements(BaseModel):
    """提取的项目资质要求模型"""
    requirements: Any = Field(..., description="项目的详细资质要求")
    is_valid: bool = Field(..., description="提取结果是否有效")
    
    def __init__(self, **data):
        # 确保requirements始终是字符串格式
        if 'requirements' in data:
            req = data['requirements']
            if isinstance(req, (dict, list)):
                data['requirements'] = json.dumps(req, ensure_ascii=False, indent=2)
            elif not isinstance(req, str):
                data['requirements'] = str(req)
        super().__init__(**data)

class ComparisonResult(BaseModel):
    """资质比对结果模型"""
    analysis: Any = Field(..., description="比对分析详情")
    final_decision: str = Field(..., description="最终判定：客观分满分或客观分不满分")
    matched_qualifications: List[str] = Field(default_factory=list, description="匹配的资质")
    missing_qualifications: List[str] = Field(default_factory=list, description="缺失的资质")
    
    def __init__(self, **data):
        # 确保analysis始终是字符串格式
        if 'analysis' in data:
            ana = data['analysis']
            if isinstance(ana, (dict, list)):
                data['analysis'] = json.dumps(ana, ensure_ascii=False, indent=2)
            elif not isinstance(ana, str):
                data['analysis'] = str(ana)
        # 确保final_decision始终是字符串格式
        if 'final_decision' in data and data['final_decision'] and not isinstance(data['final_decision'], str):
            data['final_decision'] = str(data['final_decision'])
        super().__init__(**data)

# 请求频率控制器
class RateLimiter:
    """请求频率控制器，用于控制AI API调用频率"""
    def __init__(self, max_requests_per_hour=40, min_interval_seconds=90, burst_allowance=5):
        self.max_requests_per_hour = max_requests_per_hour
        self.min_interval_seconds = min_interval_seconds
        self.burst_allowance = burst_allowance
        self.request_times = deque()  # 存储最近1小时的请求时间
        self.last_request_time = None
        
    def wait_if_needed(self):
        """如果需要，等待直到可以发送请求"""
        now = datetime.now()
        
        # 清理1小时前的请求记录
        one_hour_ago = now - timedelta(hours=1)
        while self.request_times and self.request_times[0] < one_hour_ago:
            self.request_times.popleft()
        
        # 检查是否超过每小时限制
        current_hour_count = len(self.request_times)
        if current_hour_count >= self.max_requests_per_hour:
            # 计算需要等待的时间（等待最早的请求过期）
            oldest_request = self.request_times[0]
            wait_until = oldest_request + timedelta(hours=1)
            wait_seconds = (wait_until - now).total_seconds()
            if wait_seconds > 0:
                log.warning(f"达到每小时请求限制（{self.max_requests_per_hour}），等待 {wait_seconds:.1f} 秒...")
                time.sleep(wait_seconds)
                # 重新清理
                now = datetime.now()
                one_hour_ago = now - timedelta(hours=1)
                while self.request_times and self.request_times[0] < one_hour_ago:
                    self.request_times.popleft()
        
        # 检查最小间隔
        if self.last_request_time:
            elapsed = (now - self.last_request_time).total_seconds()
            if elapsed < self.min_interval_seconds:
                wait_seconds = self.min_interval_seconds - elapsed
                log.info(f"请求间隔过短，等待 {wait_seconds:.1f} 秒...")
                time.sleep(wait_seconds)
        
        # 记录本次请求
        self.last_request_time = datetime.now()
        self.request_times.append(self.last_request_time)
        
        log.debug(f"当前小时请求数: {len(self.request_times)}/{self.max_requests_per_hour}")

# 直接使用AI的原始回答，不进行额外翻译处理
# 加载提示词模板
def load_prompt_template(prompt_path):
    """从文件加载提示词模板"""
    log.debug(f"正在加载提示词文件: {prompt_path}")
    if not os.path.exists(prompt_path):
        raise FileNotFoundError(f"提示词文件不存在：{prompt_path}")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            content = f.read()
        log.debug(f"提示词文件加载成功，长度: {len(content)} 字符")
        return content
    except Exception as e:
        log.error(f"读取提示词文件失败: {str(e)}")
        raise

# 初始化AI模型
class AIAnalyzer:
    def __init__(self, model_type=None):
        # 初始化LLM（只支持Ollama）
        ollama_config = AI_CONFIG["ollama"]
        
        # 选择模型类型：如果传入了model_type参数，则使用传入的值，否则使用配置文件中的默认值
        self.model_type = model_type or ollama_config["default_model"]
        
        # 根据模型类型选择对应的配置
        if self.model_type == "local":
            model_config = ollama_config["local_model"]
        elif self.model_type == "cloud":
            model_config = ollama_config["cloud_model"]
        else:
            raise ValueError(f"无效的模型类型：{self.model_type}，仅支持 'local' 或 'cloud'")
        
        log.info(f"当前使用模型类型: {self.model_type}，模型名称: {model_config['model_name']}")
        
        # 显示CUDA配置信息
        cuda_enabled = model_config.get("cuda", False)
        num_gpu = 1 if cuda_enabled else 0
        log.info(f"CUDA加速配置: {'启用' if cuda_enabled else '禁用'}, num_gpu: {num_gpu}")
        
        # 检查Ollama服务是否可用（使用更短的超时时间，避免阻塞）
        base_url = model_config.get("base_url", "http://localhost:11434")
        log.info(f"正在连接Ollama服务: {base_url}")
        
        try:
            import requests
            # 测试Ollama服务是否可用（使用短超时，避免阻塞页面加载）
            test_url = f"{base_url}/api/tags"
            log.debug(f"测试Ollama连接: {test_url}")
            # 使用更短的超时时间（2秒），避免阻塞
            response = requests.get(test_url, timeout=2)
            if response.status_code == 200:
                log.info("Ollama服务连接成功")
            else:
                log.warning(f"Ollama服务响应异常，状态码: {response.status_code}")
        except requests.Timeout:
            log.warning(f"Ollama服务连接超时，将在首次使用时重试（服务可能未启动或网络较慢）")
        except Exception as e:
            log.warning(f"无法连接到Ollama服务: {str(e)[:100]}，将在首次使用时重试（可能是服务未启动或网络问题）")
        
        # 初始化Ollama模型
        log.info("正在初始化Ollama模型对象...")
        try:
            self.llm = Ollama(
                model=model_config["model_name"],
                temperature=model_config.get("temperature", 0.05),
                num_gpu=num_gpu,  # 启用CUDA加速
                timeout=300,  # 增加超时时间
                keep_alive="60m",  # 延长模型保持时间
                base_url=base_url  # Ollama服务地址
            )
            log.info(f"Ollama模型对象创建成功")
        except Exception as e:
            log.warning(f"使用GPU初始化Ollama失败: {str(e)[:100]}")
            log.info("将尝试使用CPU模式重新初始化")
            # 强制使用CPU模式
            try:
                self.llm = Ollama(
                    model=model_config["model_name"],
                    temperature=model_config.get("temperature", 0.05),
                    num_gpu=0,  # 明确使用CPU
                    timeout=300,  # 增加超时时间
                    keep_alive="60m",  # 延长模型保持时间
                    base_url=base_url  # Ollama服务地址
                )
                log.info(f"Ollama模型已使用CPU模式初始化成功")
            except Exception as e2:
                log.error(f"Ollama模型初始化完全失败: {str(e2)}")
                raise
        
        # 初始化输出解析器
        # 注意：对于Ollama，我们使用字符串输出解析器，因为它可能不会严格遵循JSON格式
        self.extract_parser = StrOutputParser()
        self.compare_parser = StrOutputParser()
        
        # 加载提示词模板
        log.info("正在加载提示词模板...")
        try:
            extract_prompt_path = AI_CONFIG["extract_prompt_path"]
            log.debug(f"提取提示词路径: {extract_prompt_path}")
            extract_template = load_prompt_template(extract_prompt_path)
            self.extract_prompt = PromptTemplate(
                input_variables=["content"],
                template=extract_template + "\n\n请严格按照上述格式输出结果，不要添加任何额外内容。"
            )
            log.debug("提取提示词模板加载完成")
        except Exception as e:
            log.error(f"加载提取提示词模板失败: {str(e)}")
            raise
        
        try:
            compare_prompt_path = AI_CONFIG["compare_prompt_path"]
            log.debug(f"比对提示词路径: {compare_prompt_path}")
            compare_template = load_prompt_template(compare_prompt_path)
            self.compare_prompt = PromptTemplate(
                input_variables=["project_requirements", "company_qualifications"],
                template=compare_template + "\n\n请严格按照上述格式输出结果，不要添加任何额外内容。"
            )
            log.debug("比对提示词模板加载完成")
        except Exception as e:
            log.error(f"加载比对提示词模板失败: {str(e)}")
            raise
        
        # 加载服务类判断提示词模板
        try:
            service_check_prompt_path = AI_CONFIG.get("service_check_prompt_path")
            if service_check_prompt_path and os.path.exists(service_check_prompt_path):
                log.debug(f"服务类判断提示词路径: {service_check_prompt_path}")
                service_check_template = load_prompt_template(service_check_prompt_path)
                self.service_check_prompt = PromptTemplate(
                    input_variables=["content"],
                    template=service_check_template + "\n\n请严格按照上述格式输出结果，不要添加任何额外内容。"
                )
                # 构建服务类判断链（使用JSON解析器）
                self.service_check_parser = JsonOutputParser()
                self.service_check_chain = self.service_check_prompt | self.llm | self.service_check_parser
                log.debug("服务类判断提示词模板加载完成")
            else:
                log.warning("服务类判断提示词模板路径未配置或文件不存在，将跳过服务类判断")
                self.service_check_chain = None
        except Exception as e:
            log.warning(f"加载服务类判断提示词模板失败: {str(e)}，将跳过服务类判断")
            self.service_check_chain = None
        
        # 构建链
        log.info("正在构建AI处理链...")
        self.extract_chain = self.extract_prompt | self.llm | self.extract_parser
        self.compare_chain = self.compare_prompt | self.llm | self.compare_parser
        log.info("AI处理链构建完成")
        
        # 延迟加载公司资质（不在初始化时加载，避免卡住）
        # 改为在需要时才格式化，提高初始化速度
        self.company_qual_str = None
        
        # 初始化请求频率控制
        rate_config = AI_CONFIG.get("rate_limiting", {})
        if rate_config.get("enable", False):
            self.rate_limiter = RateLimiter(
                max_requests_per_hour=rate_config.get("max_requests_per_hour", 40),
                min_interval_seconds=rate_config.get("min_interval_seconds", 90),
                burst_allowance=rate_config.get("burst_allowance", 5)
            )
            log.info(f"请求频率控制已启用：每小时最多{rate_config.get('max_requests_per_hour', 40)}个请求，最小间隔{rate_config.get('min_interval_seconds', 90)}秒")
        else:
            self.rate_limiter = None
            log.info("请求频率控制已禁用")
        
        log.info("AIAnalyzer初始化完成")

    def _format_company_qualifications(self):
        """格式化公司资质为字符串（从数据库获取动态资质，包括A类证书库和B类规则库）"""
        try:
            log.info("开始格式化公司资质信息...")
            from utils.db import get_db, get_company_qualifications, get_class_a_certificates, get_class_b_rules
            
            # 每次调用时重新获取数据库连接
            log.debug("正在获取数据库连接...")
            db = next(get_db())
            log.debug("数据库连接获取成功")
            
            qual_lines = []
            
            # 1. 添加公司资质信息
            log.debug("正在查询公司资质信息...")
            db_qualifications = get_company_qualifications(db)
            log.debug(f"公司资质查询完成，共 {len(db_qualifications)} 个类别")
            for category, quals in db_qualifications.items():
                qual_lines.append(f"【{category}】")
                for qual in quals:
                    # 去除字符串中的多余空格（包括全角空格）
                    clean_qual = re.sub(r'\s+', ' ', qual).strip()
                    clean_qual = re.sub(r'\u3000', ' ', clean_qual).strip()
                    qual_lines.append(f"- {clean_qual}")
                qual_lines.append("")
            
            # 2. 添加A类证书库信息
            qual_lines.append("【A类证书库】")
            log.debug("正在查询A类证书库信息...")
            class_a_certificates = get_class_a_certificates(db)
            log.debug(f"A类证书查询完成，共 {len(class_a_certificates)} 个证书")
            if class_a_certificates:
                for cert in class_a_certificates:
                    cert_info = f"证书名称: {cert.certificate_name}, 认证标准: {cert.certificate_number}"
                    if cert.issuing_authority:
                        cert_info += f", 查询机构: {cert.issuing_authority}"
                    if cert.valid_from and cert.valid_until:
                        cert_info += f", 有效期: {cert.valid_from.strftime('%Y-%m-%d')}至{cert.valid_until.strftime('%Y-%m-%d')}"
                    if cert.certificate_type:
                        cert_info += f", 证书类型: {cert.certificate_type}"
                    qual_lines.append(f"- {cert_info}")
                qual_lines.append("")
            else:
                qual_lines.append("- 暂无A类证书信息")
                qual_lines.append("")
            
            # 3. 添加B类规则库信息
            qual_lines.append("【B类规则库】")
            log.debug("正在查询B类规则库信息...")
            class_b_rules = get_class_b_rules(db)
            log.debug(f"B类规则查询完成，共 {len(class_b_rules)} 个规则")
            if class_b_rules:
                for rule in class_b_rules:
                    rule_info = f"规则名称: {rule.rule_name}, 触发条件: {rule.trigger_condition}, 结论: {rule.conclusion}"
                    if rule.rule_type:
                        rule_info += f", 规则类型: {rule.rule_type}"
                    qual_lines.append(f"- {rule_info}")
                qual_lines.append("")
            else:
                # 添加默认规则
                default_rules = [
                    "规则名称: 产品检测报告全具备, 触发条件: 要求提供产品检测报告, 结论: 完全满足",
                    "规则名称: 非政府人员证书全具备, 触发条件: 要求提供非政府部门颁发的人员证书, 结论: 完全满足",
                    "规则名称: 类似项目业绩全满足, 触发条件: 要求提供类似项目业绩, 结论: 完全满足"
                ]
                for rule in default_rules:
                    qual_lines.append(f"- {rule}")
                qual_lines.append("")
            
            # 如果所有信息都为空，使用默认配置
            if len(qual_lines) <= 3:  # 只有分类标题
                from config import COMPANY_QUALIFICATIONS as DEFAULT_QUALIFICATIONS
                for category, quals in DEFAULT_QUALIFICATIONS.items():
                    qual_lines.append(f"【{category}】")
                    for qual in quals:
                        qual_lines.append(f"- {qual}")
                    qual_lines.append("")
            
            # 关闭数据库连接
            db.close()
            
            result = "\n".join(qual_lines).strip()
            log.info(f"公司资质格式化完成，总长度：{len(result)} 字符")
            return result
        except Exception as e:
            log.error(f"格式化公司资质失败：{str(e)}", exc_info=True)
            # 失败时使用默认配置
            from config import COMPANY_QUALIFICATIONS as DEFAULT_QUALIFICATIONS
            qual_lines = []
            for category, quals in DEFAULT_QUALIFICATIONS.items():
                qual_lines.append(f"【{category}】")
                for qual in quals:
                    qual_lines.append(f"- {qual}")
                qual_lines.append("")
            return "\n".join(qual_lines).strip()

    def _translate_text(self, text):
        """直接返回原始文本，不进行额外翻译处理"""
        return text
    
    def preprocess_text(self, text):
        """
        预处理文本以提高性能，大幅减少发送给AI的文本长度
        
        优化策略：
        1. 更精确的关键内容提取
        2. 减少上下文保留范围
        3. 移除冗余内容
        4. 限制最大文本长度
        """
        import re
        
        # 获取预处理配置
        preprocess_config = AI_CONFIG.get("preprocessing", {})
        max_text_length = preprocess_config.get("max_text_length", 15000)
        context_before = preprocess_config.get("context_before", 1000)
        context_after = preprocess_config.get("context_after", 1000)
        extract_range = preprocess_config.get("extract_range", 6000)
        enable_aggressive = preprocess_config.get("enable_aggressive_compression", True)
        remove_redundant = preprocess_config.get("remove_redundant_content", True)
        min_score_table_length = preprocess_config.get("min_score_table_length", 2000)
        
        original_length = len(text)
        
        # 1. 移除冗余内容（页眉、页脚、重复标题等）
        if remove_redundant:
            # 移除常见的页眉页脚模式
            text = re.sub(r'第\s*\d+\s*页\s*共\s*\d+\s*页', '', text)
            text = re.sub(r'页\s*码[:：]\s*\d+', '', text)
            # 移除重复的章节标题（连续出现3次以上）
            lines = text.split('\n')
            cleaned_lines = []
            prev_line = None
            repeat_count = 0
            for line in lines:
                stripped = line.strip()
                if stripped and stripped == prev_line:
                    repeat_count += 1
                    if repeat_count < 3:  # 允许重复2次
                        cleaned_lines.append(line)
                else:
                    repeat_count = 0
                    cleaned_lines.append(line)
                    prev_line = stripped
            text = '\n'.join(cleaned_lines)
        
        # 2. 智能识别并添加表格标记（增强评分表识别）
        # 2.1 处理已有的表格标记（先保护已有标记）
        text = text.replace('[表格开始]', '|||表格开始|||')
        text = text.replace('[表格结束]', '|||表格结束|||')
        text = text.replace('|||表格开始|||', '[表格开始]')
        text = text.replace('|||表格结束|||', '[表格结束]')
        
        # 2.2 自动识别评分表格式（特殊格式，如带特殊字符的编号）
        score_table_pattern = r'(\u0007\d+(?:\.\d+)*.*?)(?=\u0007\d|\Z)'
        matches = list(re.finditer(score_table_pattern, text, re.DOTALL))
        
        if matches:
            log.info("检测到评分表格式（特殊字符格式），自动添加表格标记")
            table_start_pos = matches[0].start()
            table_end_pos = matches[-1].end()
            text = text[:table_start_pos] + '[表格开始]' + text[table_start_pos:table_end_pos] + '[表格结束]' + text[table_end_pos:]
        else:
            # 2.3 如果没有表格标记，尝试识别制表符分隔的表格结构（评分表常见格式）
            # 评分表通常包含：序号/评分项/评分标准/分值等列，用制表符分隔
            # 使用与后面一致的评分关键词
            score_keywords_in_table = ['评分', '分值', '得分', '标准', '权重', '评审', '评标', '评分办法', 
                                      '评标办法', '评分标准', '评标标准', '评分项', '评分表']
            lines = text.split('\n')
            
            # 检测连续的行是否包含制表符且包含评分相关关键词
            table_candidates = []
            in_table = False
            table_start_idx = -1
            
            for i, line in enumerate(lines):
                # 检查是否是表格行（包含制表符且至少2个字段）
                has_tabs = '\t' in line and line.count('\t') >= 1
                has_score_keyword = any(kw in line for kw in score_keywords_in_table)
                
                if has_tabs:
                    if not in_table:
                        # 检查是否可能是表格开头（包含关键词或数字编号）
                        if has_score_keyword or re.search(r'^\d+[.\s]', line.strip()):
                            in_table = True
                            table_start_idx = i
                    # 如果已经在表格中，继续
                else:
                    # 遇到非表格行
                    if in_table:
                        # 检查是否是表格结束（空行或非表格内容的段落）
                        if line.strip() and not (re.search(r'^\d+[.\s]', line.strip()) and i - table_start_idx < 20):
                            # 可能是表格结束，但如果不是太短，可能还在表格中
                            if i - table_start_idx >= 3:  # 至少3行才认为是表格
                                table_candidates.append((table_start_idx, i - 1))
                            in_table = False
                            table_start_idx = -1
                        elif not line.strip():  # 空行，可能是表格结束
                            if i - table_start_idx >= 2:  # 至少2行
                                table_candidates.append((table_start_idx, i - 1))
                            in_table = False
                            table_start_idx = -1
            
            # 处理最后一个表格
            if in_table and len(lines) - table_start_idx >= 2:
                table_candidates.append((table_start_idx, len(lines) - 1))
            
            # 如果有候选表格且文档中没有表格标记，添加标记
            if table_candidates and '[表格开始]' not in text:
                log.info(f"检测到 {len(table_candidates)} 个可能的表格结构（制表符格式），添加表格标记")
                # 从后往前添加标记，避免位置偏移
                for start_idx, end_idx in reversed(table_candidates):
                    # 重新组合文本
                    lines[start_idx] = '[表格开始]\n' + lines[start_idx]
                    lines[end_idx] = lines[end_idx] + '\n[表格结束]'
                text = '\n'.join(lines)
            elif table_candidates:
                log.info(f"检测到 {len(table_candidates)} 个可能的表格结构，但已有表格标记，跳过")
        
        # 3. 压缩空格和换行符
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            if line.strip():
                cleaned_line = re.sub(r'([^\u0007\s])\s+', r'\1 ', line)
                cleaned_line = re.sub(r'\s+([^\u0007\s])', r' \1', cleaned_line)
                cleaned_lines.append(cleaned_line)
        text = '\n'.join(cleaned_lines)
        text = re.sub(r'\n+', '\n', text)
        
        # 4. 检查是否包含评分表格标记
        has_score_table = '[表格开始]' in text and '[表格结束]' in text
        
        # 5. 定义关键词（扩展关键词列表，提高识别率）
        score_keywords = ['评分办法', '评标办法', '评分标准', '评标标准', '评标办法前附表', 
                         '评审办法和评分标准', '评分内容', '评审标准', '分值', '得分', '评分项',
                         '评分细则', '评分表', '评审表', '打分表', '评分要素', '评分因素',
                         '评分项目', '评分依据', '评审要素', '评审因素']
        priority_qualification_keywords = ['特定资格条件', '资格条件', '特定 资格条件', '资质要求', 
                                          '资格条件证明材料', '申请人的资格要求']
        other_qualification_keywords = ['企业资质', '人员资质', '业绩要求', '设备要求']
        
        # 6. 优先处理包含评分表格的情况（增强：确保表格内容完整保留）
        if has_score_table:
            log.info("检测到评分表格标记，优先保留表格内容")
            
            # 找到所有表格的位置
            table_starts = []
            table_ends = []
            start_pos = 0
            while True:
                table_start = text.find('[表格开始]', start_pos)
                if table_start == -1:
                    break
                table_end = text.find('[表格结束]', table_start)
                if table_end == -1:
                    break
                table_starts.append(table_start)
                table_ends.append(table_end + len('[表格结束]'))
                start_pos = table_end + len('[表格结束]')
            
            if table_starts and table_ends:
                first_table_start = min(table_starts)
                last_table_end = max(table_ends)
                
                # 优化：扩大上下文范围，确保表格前后的重要说明不丢失
                # 评分表前后通常有重要的说明文字，需要保留更多上下文
                expanded_context_before = context_before * 1.5  # 增加50%的前置上下文
                expanded_context_after = context_after * 1.5    # 增加50%的后置上下文
                
                start_pos = max(0, int(first_table_start - expanded_context_before))
                end_pos = min(len(text), int(last_table_end + expanded_context_after))
                
                processed_text = text[start_pos:end_pos]
                log.info(f"提取表格区域：位置 {start_pos}-{end_pos}，长度 {len(processed_text)} 字符")
            else:
                processed_text = text
        else:
            # 先检查是否包含评分相关关键词（优先级最高）
            has_score_info = any(keyword in text for keyword in score_keywords)
            
            if has_score_info:
                # 标记所有评分关键词的位置
                score_positions = []
                for keyword in score_keywords:
                    start = 0
                    while start < len(text):
                        pos = text.find(keyword, start)
                        if pos == -1:
                            break
                        score_positions.append((pos, keyword))
                        start = pos + 1
                
                if score_positions:
                    score_positions.sort()
                    
                    # 优先查找文档后半部分的评分关键词（通常更详细）
                    # 但也要考虑前半部分可能也有重要信息
                    last_quarter_pos = len(text) * 3 // 4
                    late_score_positions = [pos for pos, kw in score_positions if pos > last_quarter_pos]
                    
                    if late_score_positions:
                        # 后半部分有关键词，优先提取后半部分
                        last_pos = max(late_score_positions)
                        start_pos = max(0, last_pos - context_before)
                        end_pos = min(len(text), last_pos + extract_range)
                        processed_text = text[start_pos:end_pos]
                        
                        # 如果前半部分也有关键词，尝试合并（但不超过max_text_length）
                        early_score_positions = [pos for pos, kw in score_positions if pos <= last_quarter_pos]
                        if early_score_positions and len(processed_text) < max_text_length:
                            # 检查是否可以包含前半部分的关键内容
                            first_early_pos = min(early_score_positions)
                            early_start = max(0, first_early_pos - 500)  # 前半部分只保留少量上下文
                            early_end = min(len(text), first_early_pos + 2000)  # 前半部分只提取2000字符
                            
                            # 如果合并后不超过限制，则合并
                            if early_end < start_pos:  # 确保不重叠
                                combined_length = (early_end - early_start) + len(processed_text)
                                if combined_length <= max_text_length:
                                    early_content = text[early_start:early_end]
                                    processed_text = early_content + '\n\n' + processed_text
                                    log.info(f"合并了前半部分和后半部分的评分内容")
                    else:
                        # 使用第一个和最后一个关键词之间的内容（扩大范围确保完整）
                        # 优化：增加提取范围，确保评分表内容完整
                        expanded_extract_range = extract_range * 1.2  # 增加20%的提取范围
                        start_pos = max(0, score_positions[0][0] - int(context_before * 1.2))
                        last_keyword = score_positions[-1]
                        end_pos = min(len(text), last_keyword[0] + len(last_keyword[1]) + int(expanded_extract_range))
                        processed_text = text[start_pos:end_pos]
                        log.info(f"基于关键词提取评分内容：位置 {start_pos}-{end_pos}，长度 {len(processed_text)} 字符")
                else:
                    processed_text = text
            else:
                # 如果没有评分信息，使用所有关键词
                all_keywords = score_keywords + other_qualification_keywords + priority_qualification_keywords
                has_qualification_info = any(keyword in text for keyword in all_keywords)
                
                if has_qualification_info:
                    keyword_positions = []
                    for keyword in all_keywords:
                        start = 0
                        while start < len(text):
                            pos = text.find(keyword, start)
                            if pos == -1:
                                break
                            keyword_positions.append((pos, keyword))
                            start = pos + 1
                    
                    if keyword_positions:
                        keyword_positions.sort()
                        start_pos = keyword_positions[0][0]
                        last_keyword = keyword_positions[-1]
                        end_pos = min(len(text), last_keyword[0] + len(last_keyword[1]) + extract_range)
                        processed_text = text[start_pos:end_pos]
                    else:
                        processed_text = text
                else:
                    processed_text = text
        
        # 7. 如果启用智能压缩且文本仍然过长，进一步压缩（但优先保证评分表完整）
        if enable_aggressive and len(processed_text) > max_text_length:
            log.info(f"文本仍然过长（{len(processed_text)}字符），启用智能压缩模式（优先保证评分表完整）")
            
            # 优先策略：检查是否包含评分表相关内容
            has_score_table_markers = '[表格开始]' in processed_text and '[表格结束]' in processed_text
            has_score_keywords_in_text = any(kw in processed_text for kw in score_keywords)
            
            if has_score_table_markers:
                # 策略1：如果包含表格标记，提取所有表格并保留必要的上下文
                table_contents = []
                table_contexts = []  # 存储每个表格的上下文
                start_pos = 0
                while True:
                    table_start = processed_text.find('[表格开始]', start_pos)
                    if table_start == -1:
                        break
                    table_end = processed_text.find('[表格结束]', table_start)
                    if table_end == -1:
                        break
                    
                    # 提取表格内容
                    table_content = processed_text[table_start:table_end + len('[表格结束]')]
                    table_contents.append(table_content)
                    
                    # 提取表格前后的上下文（每个表格保留500字符上下文）
                    context_start = max(0, table_start - 500)
                    context_end = min(len(processed_text), table_end + len('[表格结束]') + 500)
                    context = processed_text[context_start:context_end]
                    table_contexts.append(context)
                    
                    start_pos = table_end + len('[表格结束]')
                
                # 合并所有表格和上下文
                if table_contents:
                    # 如果表格总长度在合理范围内，保留所有表格
                    total_table_length = sum(len(t) for t in table_contents)
                    if total_table_length <= max_text_length:
                        # 使用表格上下文（包含表格和上下文）
                        processed_text = '\n\n'.join(table_contexts)
                    else:
                        # 如果表格太多，优先保留表格内容，减少上下文
                        temp_text = ''
                        for table in table_contents:
                            if len(temp_text) + len(table) <= max_text_length:
                                temp_text += table + '\n\n'
                            else:
                                # 如果当前表格加上去会超限，检查是否可以截断当前表格
                                remaining_space = max_text_length - len(temp_text)
                                if remaining_space >= min_score_table_length:
                                    # 保留当前表格的一部分
                                    temp_text += table[:remaining_space]
                                break
                        processed_text = temp_text.strip()
                    log.info(f"提取了 {len(table_contents)} 个表格，总长度: {len(processed_text)} 字符")
            
            elif has_score_keywords_in_text:
                # 策略2：如果包含评分关键词但没有表格标记，保留关键词周围更大范围的内容
                keyword_pattern = '|'.join(score_keywords + priority_qualification_keywords)
                matches = list(re.finditer(keyword_pattern, processed_text))
                
                if matches:
                    # 找到所有关键词的位置范围
                    first_match = matches[0]
                    last_match = matches[-1]
                    
                    # 扩大提取范围，确保包含完整的评分内容
                    start_pos = max(0, first_match.start() - context_before)
                    end_pos = min(len(processed_text), last_match.end() + extract_range)
                    
                    # 如果范围仍然超过限制，优先保留关键词密集的区域
                    if end_pos - start_pos > max_text_length:
                        # 找到关键词最密集的区域
                        keyword_density = {}
                        for match in matches:
                            center = match.start()
                            for i in range(max(0, center - 1000), min(len(processed_text), center + 1000)):
                                keyword_density[i] = keyword_density.get(i, 0) + 1
                        
                        # 找到密度最高的区域
                        if keyword_density:
                            max_density_pos = max(keyword_density.items(), key=lambda x: x[1])[0]
                            start_pos = max(0, max_density_pos - max_text_length // 2)
                            end_pos = min(len(processed_text), start_pos + max_text_length)
                    
                    processed_text = processed_text[start_pos:end_pos]
                    log.info(f"基于关键词提取，范围: {start_pos}-{end_pos}, 长度: {len(processed_text)} 字符")
            
            # 如果仍然过长，最后的安全截断（但尽量保留评分相关内容）
            if len(processed_text) > max_text_length:
                # 再次检查关键词位置，从第一个关键词开始截取
                keyword_pattern = '|'.join(score_keywords + priority_qualification_keywords)
                matches = list(re.finditer(keyword_pattern, processed_text))
                if matches:
                    start_pos = matches[0].start()
                    processed_text = processed_text[start_pos:start_pos + max_text_length]
                    log.warning(f"文本被截断到 {max_text_length} 字符（从第一个关键词开始）")
                else:
                    # 最后的手段：直接截取前N个字符
                    processed_text = processed_text[:max_text_length]
                    log.warning(f"文本被截断到 {max_text_length} 字符（无关键词，直接截取）")
        
        compression_ratio = (1 - len(processed_text) / original_length) * 100 if original_length > 0 else 0
        log.info(f"文本预处理完成，原始长度: {original_length}, 处理后长度: {len(processed_text)}, 压缩率: {compression_ratio:.1f}%")
        
        return processed_text

    def extract_requirements(self, evaluation_content):
        """提取项目资质要求（使用压缩后的文本）"""
        try:
            log.info(f"开始从标书文本中提取资质要求（压缩模式）")
            
            # 请求频率控制
            if self.rate_limiter:
                self.rate_limiter.wait_if_needed()
            
            # 预处理文本（如果启用预处理优化）
            preprocess_config = AI_CONFIG.get("preprocessing", {})
            enable_preprocessing = preprocess_config.get("enable_preprocessing", True)  # 默认启用预处理
            
            if enable_preprocessing:
                content = self.preprocess_text(evaluation_content)
                log.info(f"预处理后文本长度: {len(content)} 字符（原始长度: {len(evaluation_content)} 字符）")
            else:
                content = evaluation_content
                log.info(f"预处理已禁用，使用完整文本，长度: {len(content)} 字符")
            
            # 执行LLM调用（添加重试机制）
            max_retries = 3
            retry_count = 0
            result = None
            
            while retry_count < max_retries:
                try:
                    result = self.extract_chain.invoke({"content": content})
                    break  # 成功则退出重试循环
                except Exception as invoke_error:
                    retry_count += 1
                    error_msg = str(invoke_error)
                    
                    # 检查是否是超时或连接错误（可重试的错误）
                    is_retryable = any(keyword in error_msg.lower() for keyword in [
                        'timeout', 'timed out', 'connection', 'network', 
                        'connection error', 'connection refused', '503', '429'
                    ])
                    
                    if retry_count < max_retries and is_retryable:
                        wait_time = retry_count * 2  # 递增等待时间：2秒、4秒、6秒
                        log.warning(f"AI提取请求失败（可重试错误），{wait_time}秒后重试（{retry_count}/{max_retries}）：{error_msg[:100]}")
                        time.sleep(wait_time)
                        continue
                    else:
                        # 不可重试的错误或达到最大重试次数
                        log.error(f"AI提取资质要求失败（{retry_count}/{max_retries}）：{error_msg}")
                        raise
            
            # 验证提取结果
            if not result:
                log.warning("AI提取的资质要求无效，可能提取不完整")
                return ""
            
            # 降低长度要求，确保即使提取结果较短也能保存
            result = result.strip()
            if len(result) < 50:
                log.warning("AI提取的资质要求过短，可能提取不完整")
                # 不直接返回空字符串，允许保存较短的结果
            
            
            log.info(f"资质要求提取完成，结果长度: {len(result)} 字符")
            log.debug(f"资质要求提取结果：{result}")
            return result
        except Exception as e:
            log.error(f"AI提取资质要求失败：{str(e)}")
            raise
    
    def is_service_project(self, evaluation_content):
        """判断项目是否是服务类项目
        
        Args:
            evaluation_content: 项目解析内容
            
        Returns:
            tuple: (is_service: bool, reason: str) 如果是服务类返回True，否则返回False
        """
        try:
            # 如果服务类判断链未初始化，返回False（默认不是服务类）
            if not hasattr(self, 'service_check_chain') or self.service_check_chain is None:
                log.debug("服务类判断功能未启用，默认返回False（非服务类）")
                return False, "服务类判断功能未启用"
            
            log.info("开始判断项目是否是服务类项目")
            
            # 请求频率控制
            if self.rate_limiter:
                self.rate_limiter.wait_if_needed()
            
            # 限制内容长度，避免过长（取前5000字符应该足够判断）
            content = evaluation_content[:5000] if len(evaluation_content) > 5000 else evaluation_content
            
            # 执行LLM调用（添加重试机制）
            max_retries = 3
            retry_count = 0
            result = None
            
            while retry_count < max_retries:
                try:
                    result = self.service_check_chain.invoke({"content": content})
                    break  # 成功则退出重试循环
                except Exception as invoke_error:
                    retry_count += 1
                    error_msg = str(invoke_error)
                    
                    # 检查是否是超时或连接错误（可重试的错误）
                    is_retryable = any(keyword in error_msg.lower() for keyword in [
                        'timeout', 'timed out', 'connection', 'network', 
                        'connection error', 'connection refused', '503', '429'
                    ])
                    
                    if retry_count < max_retries and is_retryable:
                        wait_time = retry_count * 2  # 递增等待时间：2秒、4秒、6秒
                        log.warning(f"服务类判断请求失败（可重试错误），{wait_time}秒后重试（{retry_count}/{max_retries}）：{error_msg[:100]}")
                        time.sleep(wait_time)
                        continue
                    else:
                        # 不可重试的错误或达到最大重试次数
                        log.error(f"服务类判断失败（{retry_count}/{max_retries}）：{error_msg}")
                        # 如果判断失败，默认返回False（非服务类），避免误删项目
                        return False, f"判断失败：{error_msg[:100]}"
            
            # 解析结果
            if not result:
                log.warning("服务类判断结果为空，默认返回False（非服务类）")
                return False, "判断结果为空"
            
            # 处理结果（可能是字典或字符串）
            if isinstance(result, dict):
                is_service = result.get("is_service", False)
                reason = result.get("reason", "未提供理由")
            elif isinstance(result, str):
                # 尝试解析JSON字符串
                try:
                    result_dict = json.loads(result)
                    is_service = result_dict.get("is_service", False)
                    reason = result_dict.get("reason", "未提供理由")
                except json.JSONDecodeError:
                    # 如果解析失败，尝试从字符串中提取
                    is_service = "true" in result.lower() or "是" in result or "服务" in result
                    reason = result if len(result) < 200 else result[:200]
            else:
                log.warning(f"服务类判断结果格式异常：{type(result)}，默认返回False（非服务类）")
                return False, "判断结果格式异常"
            
            log.info(f"服务类判断完成：is_service={is_service}，理由：{reason}")
            return bool(is_service), str(reason)
            
        except Exception as e:
            log.error(f"服务类判断失败：{str(e)}")
            # 判断失败时默认返回False（非服务类），避免误删项目
            return False, f"判断异常：{str(e)[:100]}"
    
    def has_qualification_keywords(self, evaluation_content):
        """检查项目公告内容是否包含资质相关关键词
        
        Args:
            evaluation_content: 项目解析内容（公告内容）
            
        Returns:
            tuple: (has_keywords: bool, matched_keywords: list) 
                   如果包含资质关键词返回True和匹配到的关键词列表，否则返回False和空列表
        """
        if not evaluation_content:
            return False, []
        
        # 资质相关关键词列表
        qualification_keywords = [
            "资质",
            "许可证",
            "认证",
            "备案",
            "执业资格",
            "许可",
            "等级证书"
        ]
        
        # 转换为字符串并转为小写以便匹配
        content = str(evaluation_content).lower()
        matched_keywords = []
        
        # 检查每个关键词
        for keyword in qualification_keywords:
            if keyword in content:
                matched_keywords.append(keyword)
        
        has_keywords = len(matched_keywords) > 0
        
        if has_keywords:
            log.info(f"项目包含资质关键词：{matched_keywords}")
        else:
            log.debug("项目不包含资质关键词")
        
        return has_keywords, matched_keywords
    
    def extract_requirements_fulltext(self, evaluation_content):
        """提取项目资质要求（使用全文本，不压缩）"""
        try:
            log.info(f"开始从标书文本中提取资质要求（全文本模式，不压缩）")
            log.info(f"原始文本长度: {len(evaluation_content)} 字符")
            
            # 请求频率控制
            if self.rate_limiter:
                self.rate_limiter.wait_if_needed()
            
            # 不进行预处理压缩，直接使用原始文本
            # 只做基本的清理（移除页眉页脚等冗余内容）
            import re
            content = evaluation_content
            
            # 只移除明显的冗余内容，不进行大幅压缩
            if True:  # 可以配置是否移除冗余
                # 移除常见的页眉页脚模式
                content = re.sub(r'第\s*\d+\s*页\s*共\s*\d+\s*页', '', content)
                content = re.sub(r'页\s*码[:：]\s*\d+', '', content)
                # 压缩重复的换行符
                content = re.sub(r'\n+', '\n', content)
            
            log.info(f"清理后文本长度: {len(content)} 字符（全文本模式，未压缩）")
            
            # 执行LLM调用（添加重试机制）
            max_retries = 3
            retry_count = 0
            result = None
            
            while retry_count < max_retries:
                try:
                    result = self.extract_chain.invoke({"content": content})
                    break  # 成功则退出重试循环
                except Exception as invoke_error:
                    retry_count += 1
                    error_msg = str(invoke_error)
                    
                    # 检查是否是超时或连接错误（可重试的错误）
                    is_retryable = any(keyword in error_msg.lower() for keyword in [
                        'timeout', 'timed out', 'connection', 'network', 
                        'connection error', 'connection refused', '503', '429'
                    ])
                    
                    if retry_count < max_retries and is_retryable:
                        wait_time = retry_count * 2  # 递增等待时间：2秒、4秒、6秒
                        log.warning(f"AI提取请求失败（可重试错误），{wait_time}秒后重试（{retry_count}/{max_retries}）：{error_msg[:100]}")
                        time.sleep(wait_time)
                        continue
                    else:
                        # 不可重试的错误或达到最大重试次数
                        log.error(f"AI提取资质要求失败（{retry_count}/{max_retries}）：{error_msg}")
                        raise
            
            # 验证提取结果
            if not result:
                log.warning("AI提取的资质要求无效，可能提取不完整")
                return ""
            
            result = result.strip()
            if len(result) < 50:
                log.warning("AI提取的资质要求过短，可能提取不完整")
            
            log.info(f"全文本模式资质要求提取完成，结果长度: {len(result)} 字符")
            log.debug(f"资质要求提取结果：{result}")
            return result
        except Exception as e:
            log.error(f"AI全文本提取资质要求失败：{str(e)}")
            raise
    
    def identify_score_types(self, requirements):
        """从提取的要求中识别客观分和主观分"""
        try:
            if not requirements:
                log.warning("无提取的要求，无法进行主客观分识别")
                return {"objective_scores": [], "subjective_scores": []}
            
            log.info(f"开始识别主客观分")
            
            # 使用正则表达式尝试识别结构化的评分项目
            import re
            
            # 初始化结果
            score_types = {
                "objective_scores": [],
                "subjective_scores": []
            }
            
            # 获取价格关键词列表（统一管理）
            price_keywords = self._get_price_keywords()
            
            # 1. 首先扫描所有行，优先识别价格相关条目（最高优先级）
            lines = requirements.split('\n')
            price_related_lines = []
            other_lines = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 最高优先级：如果包含价格/报价相关关键词，必须归类为主观分
                if self._is_price_related(line):
                    price_related_lines.append(line)
                    log.info(f"[价格检测] 检测到价格相关关键词，将项目归类为主观分：{line[:150]}")
                else:
                    other_lines.append(line)
            
            # 将所有价格相关条目直接加入主观分
            score_types["subjective_scores"].extend(price_related_lines)
            
            # 2. 对非价格相关条目进行分类
            for line in other_lines:
                # 检查是否明确标记了客观分（但已排除价格相关）
                if '客观分' in line or '可得分' in line or '直接判断' in line:
                    # 再次检查（双重保险）
                    if not self._is_price_related(line):
                        score_types["objective_scores"].append(line)
                    else:
                        score_types["subjective_scores"].append(line)
                        log.info(f"[双重检查] 发现标记为客观分但包含价格关键词，移出到主观分：{line[:150]}")
                # 检查是否明确标记了主观分
                elif '主观分' in line or '主观判断' in line or '酌情给分' in line:
                    score_types["subjective_scores"].append(line)
            
            # 3. 如果没有明确标记，使用关键词识别
            if not score_types["objective_scores"] and not score_types["subjective_scores"]:
                for line in other_lines:
                    # 客观分关键词
                    objective_keywords = ['证书', '检测报告', '业绩', '复印件', '原件', '提供', '具有', '包含', '数量', '年限']
                    # 主观分关键词
                    subjective_keywords = ['先进性', '合理性', '创新性', '清晰度', '优、良、中、差', '酌情', '综合评价']
                    
                    # 再次确认不是价格相关（三重保险）
                    if self._is_price_related(line):
                        score_types["subjective_scores"].append(line)
                        log.info(f"[三重检查] 发现价格相关条目，移出到主观分：{line[:150]}")
                        continue
                    
                    # 检查客观分关键词
                    if any(keyword in line for keyword in objective_keywords):
                        score_types["objective_scores"].append(line)
                    # 检查主观分关键词
                    elif any(keyword in line for keyword in subjective_keywords):
                        score_types["subjective_scores"].append(line)
            
            # 3. 后处理：检查客观分中是否有价格相关项目，如果有则移出到主观分
            objective_scores_filtered = []
            for item in score_types["objective_scores"]:
                if self._is_price_related(item):
                    score_types["subjective_scores"].append(item)
                    log.info(f"从客观分中移出价格相关项目到主观分：{item[:100]}")
                else:
                    objective_scores_filtered.append(item)
            score_types["objective_scores"] = objective_scores_filtered
            
            log.info(f"主客观分识别完成：客观分{len(score_types['objective_scores'])}项，主观分{len(score_types['subjective_scores'])}项")
            log.debug(f"客观分项目：{score_types['objective_scores']}")
            log.debug(f"主观分项目：{score_types['subjective_scores']}")
            
            return score_types
        except Exception as e:
            log.error(f"主客观分识别失败：{str(e)}")
            return {"objective_scores": [], "subjective_scores": []}
    
    def parse_tender_method(self, requirements):
        """从提取的资质要求中解析招标方式"""
        try:
            if not requirements:
                return None
            
            log.info(f"开始解析招标方式")
            
            # 检查是否包含【招标方式】部分
            if "【招标方式】" in requirements:
                # 提取【招标方式】部分的内容
                tender_method_section = requirements.split("【招标方式】")[1]
                # 找到下一个分类标记
                next_category = None
                for category in ["【企业资质】", "【人员资质】", "【设备要求】", "【业绩要求】", "【其他要求】"]:
                    if category in tender_method_section:
                        next_category = category
                        break
                
                if next_category:
                    tender_method = tender_method_section.split(next_category)[0].strip()
                else:
                    tender_method = tender_method_section.strip()
                
                # 去除可能的前缀（如"- "）
                if tender_method.startswith("-"):
                    tender_method = tender_method[1:].strip()
                
                log.info(f"解析到招标方式：{tender_method}")
                return tender_method
            
            # 如果没有明确的招标方式分类，尝试从文本中提取关键词
            requirements_lower = requirements.lower()
            
            # 常见的招标方式关键词
            tender_methods = {
                "最低价中标": ["最低价", "最低价中标", "经评审的最低投标价"],
                "综合评分法": ["综合评分", "综合评分法"],
                "竞争性谈判": ["竞争性谈判"],
                "竞争性磋商": ["竞争性磋商"],
                "询价": ["询价"],
                "单一来源": ["单一来源"]
            }
            
            # 检查是否包含特定招标方式关键词
            for method_name, keywords in tender_methods.items():
                if any(keyword in requirements_lower for keyword in keywords):
                    log.info(f"通过关键词识别到招标方式：{method_name}")
                    return method_name
            
            log.info("未识别到明确的招标方式")
            return None
            
        except Exception as e:
            log.error(f"解析招标方式失败：{str(e)}")
            return None

    def _parse_objective_scores(self, ai_result: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        从AI返回结果中解析客观分总满分和可得分（排除价格相关条目）
        
        返回: (总满分, 可得分, 丢分) 如果解析失败则返回 (None, None, None)
        """
        try:
            import re
            
            # 首先从客观分条目中重新计算，确保排除价格分
            total_score = 0.0
            attainable_score = 0.0
            
            # 查找所有客观分条目（排除价格相关）
            objective_item_patterns = [
                r'【客观分条目\d+[：:](.*?)（满分[：:]\s*(\d+(?:\.\d+)?)\s*分）',
                r'【客观分条目\d+[：:](.*?)\(满分[：:]\s*(\d+(?:\.\d+)?)\s*分\)',
                r'【客观分条目\d+[：:](.*?)（分值[：:]\s*(\d+(?:\.\d+)?)\s*分）',
                r'【客观分条目\d+[：:](.*?)\(分值[：:]\s*(\d+(?:\.\d+)?)\s*分\)',
            ]
            
            # 使用集合跟踪已处理的条目，避免重复计算
            # 使用匹配位置范围作为唯一标识，更准确地识别重复条目
            processed_ranges = set()  # 存储 (start_pos, end_pos) 元组
            objective_items = []
            
            # 先收集所有匹配项，然后按位置排序去重
            all_matches = []
            for pattern in objective_item_patterns:
                matches = re.finditer(pattern, ai_result, re.DOTALL)
                for match in matches:
                    match_start = match.start()
                    match_end = match.end()
                    item_desc = match.group(1).strip()
                    item_score = float(match.group(2))
                    
                    # 提取条目编号（如果存在）
                    entry_match = re.search(r'【客观分条目(\d+)', match.group(0))
                    entry_num = entry_match.group(1) if entry_match else '0'
                    
                    all_matches.append({
                        'start': match_start,
                        'end': match_end,
                        'desc': item_desc,
                        'score': item_score,
                        'entry_num': entry_num,
                        'full_match': match.group(0)
                    })
            
            # 按起始位置排序
            all_matches.sort(key=lambda x: x['start'])
            
            # 去重：如果两个匹配的位置重叠超过80%，认为是同一个条目
            for match in all_matches:
                match_start = match['start']
                match_end = match['end']
                
                # 检查是否与已处理的条目重叠
                is_duplicate = False
                for processed_start, processed_end in processed_ranges:
                    # 计算重叠度
                    overlap_start = max(match_start, processed_start)
                    overlap_end = min(match_end, processed_end)
                    if overlap_start < overlap_end:
                        overlap_length = overlap_end - overlap_start
                        match_length = match_end - match_start
                        overlap_ratio = overlap_length / match_length if match_length > 0 else 0
                        # 如果重叠度超过80%，认为是重复
                        if overlap_ratio > 0.8:
                            is_duplicate = True
                            log.debug(f"跳过重复的客观分条目（重叠度{overlap_ratio:.2%}）：条目{match['entry_num']} - {match['desc'][:50]}（{match['score']}分）")
                            break
                
                if is_duplicate:
                    continue
                
                # 检查是否是价格相关条目
                if not self._is_price_related(match['desc']):
                    objective_items.append({
                        'desc': match['desc'],
                        'score': match['score'],
                        'full_match': match['full_match'],
                        'start_pos': match_start
                    })
                    # 标记这个位置范围已处理
                    processed_ranges.add((match_start, match_end))
                    log.debug(f"添加客观分条目：条目{match['entry_num']} - {match['desc'][:50]}（{match['score']}分）")
                else:
                    log.warning(f"[价格检测] 在客观分条目中发现价格相关条目，已排除：{match['desc'][:100]}（{match['score']}分）")
                    # 价格相关条目也要标记为已处理，避免被其他模式重复匹配
                    processed_ranges.add((match_start, match_end))
            
            # 如果从条目中找到了分数，继续查找可得分
            if objective_items:
                # 直接从条目列表中计算总满分，确保准确性
                total_score = sum(item['score'] for item in objective_items)
                
                # 记录所有条目的详细信息，用于调试
                log.info(f"[客观分计算] 共找到 {len(objective_items)} 个客观分条目，开始计算总分...")
                item_scores = [item['score'] for item in objective_items]
                log.info(f"[客观分计算] 各条目分数：{item_scores}，总和：{total_score}分")
                log.info(f"[客观分计算] 开始计算可得分，初始可得分：{attainable_score}分")
                
                # 查找每个条目的匹配结论
                for item in objective_items:
                    # 在条目附近查找匹配结论
                    item_start = ai_result.find(item['full_match'])
                    if item_start != -1:
                        # 查找该条目对应的分析部分
                        section_end = ai_result.find('【客观分条目', item_start + len(item['full_match']))
                        if section_end == -1:
                            section_end = len(ai_result)
                        section = ai_result[item_start:section_end]
                        
                        # 优先检查"不满足"，如果明确是"不满足"，则不得分
                        # 检查"不满足"的模式
                        not_satisfied_patterns = [
                            r'匹配结论[：:]\s*不满足',
                            r'匹配结论[：:]\s*不\s*满足',
                            r'结论[：:]\s*不满足',
                            r'结论[：:]\s*不\s*满足',
                        ]
                        
                        # 检查"满足"的模式
                        satisfied_patterns = [
                            r'匹配结论[：:]\s*满足',
                            r'结论[：:]\s*满足',
                        ]
                        
                        is_not_satisfied = False
                        is_satisfied = False
                        
                        # 先检查是否不满足
                        for pattern in not_satisfied_patterns:
                            if re.search(pattern, section):
                                is_not_satisfied = True
                                break
                        
                        # 如果不满足，直接跳过
                        if is_not_satisfied:
                            log.debug(f"客观分条目不可得分（不满足）：{item['desc'][:50]}（{item['score']}分）")
                            continue
                        
                        # 再检查是否满足
                        for pattern in satisfied_patterns:
                            if re.search(pattern, section):
                                is_satisfied = True
                                break
                        
                        # 如果满足，则加分
                        if is_satisfied:
                            attainable_score += item['score']
                            log.debug(f"客观分条目可得分（满足）：{item['desc'][:50]}（{item['score']}分）")
                        else:
                            # 如果既没有"满足"也没有"不满足"，默认不满足（不得分）
                            log.debug(f"客观分条目不可得分（未找到明确结论）：{item['desc'][:50]}（{item['score']}分）")
                
                if total_score > 0:
                    loss_score = total_score - attainable_score
                    log.info(f"[客观分计算] 计算完成：总满分={total_score}分，可得分={attainable_score}分，失分={loss_score}分（已排除价格分）")
                    log.info(f"[客观分计算] 验证：总满分({total_score}) - 可得分({attainable_score}) = 失分({loss_score})")
                    return total_score, attainable_score, loss_score
            
            # 如果从条目中没找到，回退到原来的解析方式（但需要验证是否包含价格分）
            log.debug("未能从客观分条目中提取分数，尝试从AI结果中解析")
            total_patterns = [
                r'客观分总满分[：:]\s*(\d+(?:\.\d+)?)\s*分',
                r'客观分总满分[：:]\s*\[(\d+(?:\.\d+)?)\]\s*分',
                r'客观分总满分\s*[：:]\s*(\d+(?:\.\d+)?)\s*分',
                r'总满分[：:]\s*(\d+(?:\.\d+)?)\s*分',
                r'总满分[：:]\s*\[(\d+(?:\.\d+)?)\]\s*分',
                r'总满分\s*[：:]\s*(\d+(?:\.\d+)?)\s*分',
            ]
            
            attainable_patterns = [
                r'客观分可得分[：:]\s*(\d+(?:\.\d+)?)\s*分',
                r'客观分可得分[：:]\s*\[(\d+(?:\.\d+)?)\]\s*分',
                r'客观分可得分\s*[：:]\s*(\d+(?:\.\d+)?)\s*分',
                r'可得分[：:]\s*(\d+(?:\.\d+)?)\s*分',
                r'可得分[：:]\s*\[(\d+(?:\.\d+)?)\]\s*分',
                r'可得分\s*[：:]\s*(\d+(?:\.\d+)?)\s*分',
            ]
            
            total_score = None
            attainable_score = None
            
            # 尝试匹配总满分
            for pattern in total_patterns:
                match = re.search(pattern, ai_result)
                if match:
                    try:
                        total_score = float(match.group(1))
                        break
                    except ValueError:
                        continue
            
            # 尝试匹配可得分
            for pattern in attainable_patterns:
                match = re.search(pattern, ai_result)
                if match:
                    try:
                        attainable_score = float(match.group(1))
                        break
                    except ValueError:
                        continue
            
            # 如果都解析成功，计算丢分
            if total_score is not None and attainable_score is not None:
                loss_score = total_score - attainable_score
                log.warning(f"使用AI给出的客观分数值（可能包含价格分，建议检查）：总满分={total_score}分，可得分={attainable_score}分")
                return total_score, attainable_score, loss_score
            
            log.debug(f"未能完整解析客观分：总满分={total_score}, 可得分={attainable_score}")
            return None, None, None
            
        except Exception as e:
            log.warning(f"解析客观分失败：{str(e)}")
            return None, None, None
    
    def _get_price_keywords(self):
        """获取价格相关关键词列表（统一管理，提高复用性）"""
        return ['价格', '报价', '投标报价', '价格分', '报价分', '价格评审', '价格评分', 
                '价格响应', '报价响应', '价格合理性', '价格优势', '价格竞争力', 
                '投标价格', '报价金额', '价格因素', '价格部分', '报价部分', '投标价']
    
    def _is_price_related(self, text: str) -> bool:
        """判断文本是否包含价格相关关键词（严格检查，不区分大小写）"""
        if not text:
            return False
        text_str = str(text).lower() if isinstance(text, str) else str(text).lower()
        keywords = self._get_price_keywords()
        # 去重并转换为小写进行比较
        keywords_lower = [kw.lower() for kw in set(keywords)]
        result = any(keyword in text_str for keyword in keywords_lower)
        if result:
            log.debug(f"[价格检测] 文本包含价格关键词：{text[:100]}")
        return result
    
    def _calculate_loss_score_from_analysis(self, ai_result: str) -> Optional[float]:
        """
        直接从AI分析结果中统计"不满足"条目的失分总和（排除价格相关条目）
        
        返回: 失分总和，如果解析失败则返回 None
        """
        try:
            import re
            
            loss_score = 0.0
            
            # 添加调试日志
            log.debug(f"开始统计失分，AI结果长度：{len(ai_result)}字符")
            
            # 检查是否包含客观分条目标记
            has_objective_items = '【客观分条目' in ai_result or '客观分条目' in ai_result
            if not has_objective_items:
                log.warning("AI结果中未找到客观分条目标记，尝试其他格式解析")
            
            # 分割分析结果，找到每个客观分条目的分析部分
            # 支持多种格式：【客观分条目X】或【客观分条目X：】或客观分条目X
            objective_sections = []
            
            # 方式1：尝试标准格式【客观分条目X】
            sections1 = re.split(r'(?=【客观分条目\d+)', ai_result)
            if len(sections1) > 1:
                objective_sections = sections1
                log.debug(f"使用标准格式分割，找到{len(sections1)}个部分")
            else:
                # 方式2：尝试其他格式（如"客观分条目1："）
                sections2 = re.split(r'(?=客观分条目\d+[：:])', ai_result)
                if len(sections2) > 1:
                    objective_sections = sections2
                    log.debug(f"使用替代格式分割，找到{len(sections2)}个部分")
                else:
                    # 方式3：尝试查找所有包含"不满足"的部分
                    log.debug("未找到标准格式，尝试查找包含'不满足'的部分")
                    # 使用更宽泛的匹配
                    all_sections = re.split(r'(?=【客观分|客观分|【主观分|===)', ai_result)
                    objective_sections = [s for s in all_sections if '客观分' in s or '不满足' in s]
                    log.debug(f"使用宽泛匹配，找到{len(objective_sections)}个相关部分")
            
            for section in objective_sections:
                if not section.strip():
                    continue
                
                # 放宽检查条件：只要包含"客观分"或"不满足"就处理
                if '客观分' not in section and '不满足' not in section:
                    continue
                
                # 检查是否是价格相关条目，如果是则跳过（价格条目不应该计入客观分失分）
                if self._is_price_related(section):
                    log.debug(f"跳过价格相关条目，不计入客观分失分：{section[:100]}")
                    continue
                
                # 查找"匹配结论：[满足/不满足]"
                # 使用正则表达式更精确地匹配"匹配结论：不满足"或"匹配结论： 不满足"
                conclusion_patterns = [
                    r'匹配结论[：:]\s*不满足',
                    r'匹配结论[：:]\s*满足.*?不满足',  # 处理"满足...不满足"的情况
                ]
                
                is_not_satisfied = False
                for pattern in conclusion_patterns:
                    if re.search(pattern, section):
                        is_not_satisfied = True
                        break
                
                # 如果没找到明确的"匹配结论：不满足"，尝试查找"不满足"关键词
                if not is_not_satisfied:
                    conclusion_pos = section.find('匹配结论')
                    not_satisfied_pos = section.find('不满足')
                    
                    if conclusion_pos != -1 and not_satisfied_pos != -1 and not_satisfied_pos > conclusion_pos:
                        # 确保"不满足"在"匹配结论"之后，且距离不太远
                        if not_satisfied_pos - conclusion_pos < 500:  # 增加到500字符内
                            # 检查"不满足"前后是否有"满足"，避免误判
                            context_before = section[max(0, not_satisfied_pos-100):not_satisfied_pos]
                            context_after = section[not_satisfied_pos:min(len(section), not_satisfied_pos+50)]
                            # 如果"不满足"前后没有"满足"，或者明确是"不满足"
                            if ('满足' not in context_before or '不满足' in context_before) and '满足' not in context_after[:20]:
                                is_not_satisfied = True
                                log.debug(f"通过关键词匹配找到不满足条目：{section[:150]}")
                    elif not_satisfied_pos != -1 and conclusion_pos == -1:
                        # 如果没有"匹配结论"标记，但有"不满足"，且不在价格相关条目中
                        # 检查上下文，确保是判定结果
                        context = section[max(0, not_satisfied_pos-100):min(len(section), not_satisfied_pos+100)]
                        if '判定' in context or '结论' in context or '满足' in context:
                            is_not_satisfied = True
                            log.debug(f"通过上下文匹配找到不满足条目（无匹配结论标记）：{section[:150]}")
                
                if is_not_satisfied:
                    log.debug(f"找到不满足的条目，开始提取满分：{section[:200]}")
                    # 找到不满足的条目，提取其满分
                    # 先尝试从条目标题中提取
                    title_score_patterns = [
                        r'【客观分条目\d+[：:].*?（满分[：:]\s*(\d+(?:\.\d+)?)\s*分）',
                        r'【客观分条目\d+[：:].*?\(满分[：:]\s*(\d+(?:\.\d+)?)\s*分\)',
                        r'【客观分条目\d+[：:].*?（分值[：:]\s*(\d+(?:\.\d+)?)\s*分）',
                        r'【客观分条目\d+[：:].*?\(分值[：:]\s*(\d+(?:\.\d+)?)\s*分\)',
                        r'【客观分条目\d+[：:].*?满分[：:]\s*(\d+(?:\.\d+)?)\s*分',  # 无括号的情况
                    ]
                    
                    score_found = False
                    for pattern in title_score_patterns:
                        score_match = re.search(pattern, section[:800])  # 增加查找范围到800字符
                        if score_match:
                            try:
                                score = float(score_match.group(1))
                                loss_score += score
                                log.debug(f"从标题中找到不满足条目的满分，失分：{score}分，条目：{section[:100]}")
                                score_found = True
                                break
                            except (ValueError, IndexError):
                                continue
                    
                    # 如果标题中没找到，在分析部分中查找"满分：X分"或"分值：X分"
                    if not score_found:
                        score_patterns = [
                            r'满分[：:]\s*(\d+(?:\.\d+)?)\s*分',
                            r'分值[：:]\s*(\d+(?:\.\d+)?)\s*分',
                            r'\(满分[：:]\s*(\d+(?:\.\d+)?)\s*分\)',
                            r'（满分[：:]\s*(\d+(?:\.\d+)?)\s*分）',
                        ]
                        
                        for pattern in score_patterns:
                            score_matches = re.findall(pattern, section)
                            if score_matches:
                                try:
                                    # 取第一个匹配的分数（通常是该条目的满分）
                                    score = float(score_matches[0])
                                    loss_score += score
                                    log.debug(f"从分析部分中找到不满足条目的满分，失分：{score}分，条目：{section[:100]}")
                                    score_found = True
                                    break
                                except (ValueError, IndexError):
                                    continue
                    
                    if not score_found:
                        log.warning(f"未找到不满足条目的满分，条目：{section[:300]}")
                        # 尝试更宽泛的匹配：查找任何数字+分
                        wide_pattern = r'(\d+(?:\.\d+)?)\s*分'
                        wide_matches = re.findall(wide_pattern, section[:500])
                        if wide_matches:
                            try:
                                # 取最大的分数（通常是满分）
                                scores = [float(m) for m in wide_matches]
                                max_score = max(scores)
                                loss_score += max_score
                                log.info(f"使用宽泛匹配找到分数，失分：{max_score}分，条目：{section[:150]}")
                            except (ValueError, IndexError):
                                log.debug(f"宽泛匹配也失败，条目：{section[:200]}")
            
            if loss_score > 0:
                log.info(f"从分析结果中统计的失分总和：{loss_score}分（已排除价格相关条目）")
                return loss_score
            else:
                log.warning(f"未找到不满足的条目或无法提取失分。AI结果前500字符：{ai_result[:500]}")
                # 尝试查找是否有"不满足"关键词
                if '不满足' in ai_result:
                    log.warning("AI结果中包含'不满足'关键词，但未能提取失分，可能是格式问题")
                return None
                
        except Exception as e:
            log.warning(f"统计失分失败：{str(e)}")
            import traceback
            log.debug(f"统计失分失败详细错误：{traceback.format_exc()}")
            return None
    
    def compare_qualifications(self, project_requirements):
        """比对公司与项目资质，支持基于评分表的比对"""
        try:
            log.debug("开始AI资质比对")
            # 每次比对前重新获取最新资质，确保使用最新数据
            latest_qual_str = self._format_company_qualifications()
            
            # 执行AI比对（添加重试机制）
            max_retries = 3
            retry_count = 0
            result = None
            
            while retry_count < max_retries:
                try:
                    result = self.compare_chain.invoke({
                        "project_requirements": project_requirements,
                        "company_qualifications": latest_qual_str
                    })
                    break  # 成功则退出重试循环
                except Exception as invoke_error:
                    retry_count += 1
                    error_msg = str(invoke_error)
                    
                    # 检查是否是超时或连接错误（可重试的错误）
                    is_retryable = any(keyword in error_msg.lower() for keyword in [
                        'timeout', 'timed out', 'connection', 'network', 
                        'connection error', 'connection refused', '503', '429'
                    ])
                    
                    if retry_count < max_retries and is_retryable:
                        wait_time = retry_count * 2  # 递增等待时间：2秒、4秒、6秒
                        log.warning(f"AI比对请求失败（可重试错误），{wait_time}秒后重试（{retry_count}/{max_retries}）：{error_msg[:100]}")
                        time.sleep(wait_time)
                        continue
                    else:
                        # 不可重试的错误或达到最大重试次数
                        log.error(f"AI比对失败（{retry_count}/{max_retries}）：{error_msg}")
                        raise
            
            # 验证结果
            if not result or len(result.strip()) < 50:
                log.warning("AI比对结果无效或过短，可能比对不完整，判定为推荐参与")
                return "", "推荐参与"
            
            # 提取AI返回的最终判定
            final_decision = "未判定"
            
            # 尝试从AI结果中提取最终判定
            result_lower = result.lower()
            # 清洗结果，移除可能存在的多余空格
            clean_result = result.replace(" ", "")
            if "客观分满分" in clean_result:
                final_decision = "推荐参与"
            elif "客观分不满分" in clean_result:
                final_decision = "不推荐参与"
            else:
                log.info("未从AI结果中提取到明确的最终判定")
            
            # 验证AI计算的客观分总分和可得分是否合理
            total_score, attainable_score, ai_loss_score = self._parse_objective_scores(result)
            
            # 直接从分析结果中统计"不满足"条目的失分，进行丢分阈值判断
            from config import OBJECTIVE_SCORE_CONFIG
            if OBJECTIVE_SCORE_CONFIG.get("enable_loss_score_adjustment", True):
                threshold = OBJECTIVE_SCORE_CONFIG.get("loss_score_threshold", 1.0)
                
                # 直接从分析结果中统计失分（不满足条目的满分总和）
                loss_score = self._calculate_loss_score_from_analysis(result)
                
                # 验证AI计算的客观分是否合理
                if total_score is not None and attainable_score is not None:
                    calculated_loss = total_score - attainable_score
                    log.info(f"AI计算的客观分：总满分={total_score}分，可得分={attainable_score}分，失分={calculated_loss}分")
                    
                    # 优先使用AI计算的失分，因为它更准确（基于总满分和可得分计算）
                    # 如果统计的失分和AI计算的失分差距较大，说明统计可能漏掉了某些条目
                    if loss_score is not None:
                        loss_diff = abs(calculated_loss - loss_score)
                        # 如果AI计算的失分更大，说明统计可能漏掉了某些条目，优先使用AI计算的失分
                        # 如果差距超过阈值的2倍，记录警告但使用较大的值
                        if calculated_loss > loss_score:
                            log.warning(f"⚠️ AI计算的失分({calculated_loss}分)大于统计的失分({loss_score}分)，可能统计漏掉了某些条目，使用AI计算的失分")
                            loss_score_to_use = calculated_loss
                        elif loss_diff > threshold * 2:
                            log.warning(f"⚠️ AI计算的失分({calculated_loss}分)与统计的失分({loss_score}分)差距较大({loss_diff}分)，使用较大的值进行判断")
                            loss_score_to_use = max(calculated_loss, loss_score)
                        else:
                            # 差距不大，使用统计的失分（更精确，已排除价格分）
                            loss_score_to_use = loss_score
                    else:
                        # 如果无法统计失分，使用AI计算的失分
                        loss_score_to_use = calculated_loss if calculated_loss > 0 else None
                        log.warning(f"无法从分析结果中统计失分，使用AI计算的失分：{loss_score_to_use}分")
                else:
                    loss_score_to_use = loss_score
                
                if loss_score_to_use is not None:
                    # 确定失分来源说明
                    if total_score is not None and attainable_score is not None and calculated_loss == loss_score_to_use:
                        loss_source = "AI计算的失分（总满分-可得分）"
                    elif loss_score == loss_score_to_use:
                        loss_source = "从分析结果中直接统计不满足条目的失分"
                    else:
                        loss_source = "综合判断（优先使用AI计算的失分）"
                    
                    log.info(f"客观分失分统计：失分={loss_score_to_use}分（{loss_source}），阈值={threshold}分")
                    
                    # 如果失分≤阈值，且AI判定为"客观分不满分"，则改为"推荐参与"
                    # 使用 round() 处理浮点数精度问题，确保比较准确
                    loss_score_rounded = round(loss_score_to_use, 2)
                    threshold_rounded = round(threshold, 2)
                    
                    log.info(f"丢分阈值判断：失分={loss_score_to_use}分(四舍五入后={loss_score_rounded}分)，阈值={threshold}分(四舍五入后={threshold_rounded}分)，当前判定={final_decision}")
                    
                    # 简化逻辑：失分 > 阈值 → 不推荐；失分 ≤ 阈值 → 如果AI判定为不推荐，改为推荐
                    if loss_score_rounded > threshold_rounded:
                        # 失分超过阈值，即使AI判定为推荐，也应该改为不推荐
                        if final_decision == "推荐参与" or "客观分满分" in clean_result:
                            old_decision = final_decision
                            final_decision = "不推荐参与"
                            adjustment_note = f"\n\n【失分阈值验证说明】\n"
                            adjustment_note += f"- 客观分失分统计：{loss_score_to_use}分（{loss_source}）\n"
                            adjustment_note += f"- 配置的丢分阈值：{threshold}分\n"
                            adjustment_note += f"- 判定结果：虽然AI判定为\"推荐参与\"，但由于失分({loss_score_to_use}分)超过阈值({threshold}分)，系统判定为\"不推荐参与\"\n"
                            result = result + adjustment_note
                            log.warning(f"⚠️ 失分({loss_score_rounded}分)超过阈值({threshold_rounded}分)，已从\"{old_decision}\"调整为\"不推荐参与\"")
                    elif loss_score_rounded <= threshold_rounded and final_decision == "不推荐参与":
                        old_decision = final_decision
                        final_decision = "推荐参与"
                        # 在比对结果中添加说明
                        adjustment_note = f"\n\n【丢分阈值调整说明】\n"
                        adjustment_note += f"- 客观分失分统计：{loss_score_to_use}分（{loss_source}）\n"
                        adjustment_note += f"- 配置的丢分阈值：{threshold}分\n"
                        adjustment_note += f"- 判定结果：虽然AI判定为\"客观分不满分\"，但由于失分({loss_score_to_use}分)≤阈值({threshold}分)，系统自动调整为\"推荐参与\"\n"
                        result = result + adjustment_note
                        log.info(f"✅ 丢分阈值调整成功：失分{loss_score_to_use}分(四舍五入后={loss_score_rounded}分)≤阈值{threshold}分(四舍五入后={threshold_rounded}分)，已从\"{old_decision}\"调整为\"{final_decision}\"")
                        log.info(f"✅ 调整后的final_decision值：{final_decision}，即将返回此值")
                    else:
                        log.debug(f"失分阈值判断：失分={loss_score_to_use}分(四舍五入后={loss_score_rounded}分)，阈值={threshold}分(四舍五入后={threshold_rounded}分)，当前判定={final_decision}，无需调整")
                else:
                    log.info("未能从分析结果中统计失分，跳过丢分阈值调整")
            
            log.debug(f"资质比对结果：{result}")
            log.info(f"最终判定：{final_decision}")
            
            return result, final_decision
        except Exception as e:
            log.error(f"AI资质比对失败：{str(e)}")
            raise
    
    def _extract_exclusion_requirements(self, project_requirements: str) -> list:
        """从项目要求中提取排除式筛选条件"""
        exclusion_keywords = ['排除', '非', '除了', '不是', '不包括', '禁止', '不得', 
                            '国家机构颁发', '颁发机构', '不接受', '禁止', '无']
        exclusion_requirements = []
        
        if not project_requirements:
            return exclusion_requirements
        
        # 按行分割项目要求
        lines = project_requirements.split('\n')
        
        for line in lines:
            line = line.strip()
            # 跳过空行和分类标题
            if not line or line.startswith('【') and line.endswith('】'):
                continue
            
            # 检查是否包含排除式关键词
            if any(keyword in line for keyword in exclusion_keywords):
                exclusion_requirements.append(line)
        
        return exclusion_requirements
    
    def _extract_fuzzy_requirements(self, project_requirements: str) -> list:
        """从项目要求中提取模糊式筛选条件"""
        fuzzy_keywords = ['业绩', '场地', '检测报告', '加分', '能力', '经验', '相关', 
                         '证明', '办公场所', '仓库', '安装', '施工经验', '类似项目']
        fuzzy_requirements = []
        
        if not project_requirements:
            return fuzzy_requirements
        
        # 按行分割项目要求
        lines = project_requirements.split('\n')
        
        for line in lines:
            line = line.strip()
            # 跳过空行和分类标题
            if not line or line.startswith('【') and line.endswith('】'):
                continue
            
            # 检查是否包含模糊式关键词
            if any(keyword in line for keyword in fuzzy_keywords):
                fuzzy_requirements.append(line)
        
        return fuzzy_requirements
    
    def _extract_certificate_requirements(self, project_requirements: str) -> list:
        """从项目要求中提取权威机构证书要求"""
        # 证书相关关键词（包括人员职称、技术认证）
        certificate_keywords = ['证书', '认证', '资质证书', '许可证', '执照', '资格证',
                              '工程师', '中级工程师', '高级工程师', '职称', '专业职称',
                              '执业资格', '职业资格', '技术资格', 'OCP', 'DCA', '认证工程师',
                              '数据库认证', '技术认证', '专业认证', '资格认证', '持证上岗', '专业资格']
        # 权威机构相关关键词
        authority_keywords = ['权威机构', '政府', '部门管理', '国家机构', '颁发机构',
                            '国家', '住建部', '环保部门', '质量监督', '监督检验',
                            '国家机关', '部门颁发', '政府部门', '行政部门', '备案',
                            '人事部门', '人力资源和社会保障', '人社部门', '职称评审委员会',
                            'Oracle', '达梦', '厂商', '官方', '原厂', '授权机构']
        # 认证体系相关关键词（特殊处理）
        certification_system_keywords = ['三体系认证', '职业健康安全管理体系', '环境管理体系', '质量管理体系',
                                       '认证体系', '体系认证']
        certificate_requirements = []
        
        if not project_requirements:
            return certificate_requirements
        
        # 按行分割项目要求
        lines = project_requirements.split('\n')
        
        for line in lines:
            line = line.strip()
            # 跳过空行和分类标题
            if not line or line.startswith('【') and line.endswith('】'):
                continue
            
            # 如果是培训相关的要求，跳过（培训证书满足要求，无需权威机构）
            if '培训' in line and '证书' in line:
                continue
            
            # 检查是否同时包含证书相关关键词和权威机构相关关键词
            has_certificate = any(cert_key in line for cert_key in certificate_keywords)
            has_authority = any(auth_key in line for auth_key in authority_keywords)
            
            # 特殊处理认证体系要求
            has_certification_system = any(system_key in line for system_key in certification_system_keywords)
            
            # 特殊处理人员职称要求：比如"专业中级工程师"、"负责人需要具备中级职称"等
            has_personnel_title = (('人员' in line or '负责人' in line or '项目经理' in line) and 
                                   any(title in line for title in ['工程师', '中级工程师', '高级工程师', '职称']))
            
            # 特殊处理关键人员的专业资格证书要求，但不包括培训证书
            has_key_personnel_certificate = (('项目负责人' in line or '技术人员' in line or '项目经理' in line) and 
                                            any(cert_key in line for cert_key in ['证书', '资格证', '持证上岗', '专业资格', '职称']) and
                                            '培训' not in line)
            
            # 只有当明确要求权威机构或属于特殊处理的情况才添加
            if (has_certificate and has_authority) or has_certification_system or has_personnel_title or has_key_personnel_certificate:
                certificate_requirements.append(line)
        
        return certificate_requirements
    
    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的语义相似度（使用Ollama embedding）
        
        返回: 相似度分数（0-1之间），1表示完全相同，0表示完全不同
        """
        try:
            import requests
            import numpy as np
            from config import AI_CONFIG
            
            # 获取Ollama配置
            ollama_config = AI_CONFIG.get("ollama", {})
            base_url = ollama_config.get("cloud_model", {}).get("base_url", "http://localhost:11434")
            
            # 使用Ollama的embedding API
            # 尝试使用支持中文的embedding模型（如nomic-embed-text）
            embedding_model = "nomic-embed-text"  # 或者使用其他支持中文的模型
            
            # 获取text1的embedding
            response1 = requests.post(
                f"{base_url}/api/embeddings",
                json={"model": embedding_model, "prompt": text1},
                timeout=10
            )
            if response1.status_code != 200:
                log.warning(f"获取text1的embedding失败，回退到关键词匹配")
                return 0.0
            
            embedding1 = np.array(response1.json()["embedding"])
            
            # 获取text2的embedding
            response2 = requests.post(
                f"{base_url}/api/embeddings",
                json={"model": embedding_model, "prompt": text2},
                timeout=10
            )
            if response2.status_code != 200:
                log.warning(f"获取text2的embedding失败，回退到关键词匹配")
                return 0.0
            
            embedding2 = np.array(response2.json()["embedding"])
            
            # 计算余弦相似度
            dot_product = np.dot(embedding1, embedding2)
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            
            # 将相似度从[-1, 1]映射到[0, 1]
            similarity = (similarity + 1) / 2
            
            return float(similarity)
            
        except Exception as e:
            log.warning(f"语义相似度计算失败：{str(e)}，回退到关键词匹配")
            return 0.0
    
    def match_class_b_rules(self, objective_score_items):
        """对客观分条目进行B类规则匹配（支持语义匹配）"""
        try:
            from utils.db import get_class_b_rules
            from config import AI_CONFIG
            
            if not objective_score_items:
                log.info("无客观分条目，跳过B类规则匹配")
                return []
            
            log.info(f"开始进行B类规则匹配，共 {len(objective_score_items)} 个客观分条目")
            
            # 获取所有启用的B类规则
            class_b_rules = get_class_b_rules(self.db)
            if not class_b_rules:
                log.info("B类规则库为空，跳过规则匹配")
                return []
            
            # 检查是否启用语义匹配
            use_semantic_match = AI_CONFIG.get("rule_matching", {}).get("use_semantic_match", True)
            semantic_threshold = AI_CONFIG.get("rule_matching", {}).get("semantic_threshold", 0.7)  # 语义相似度阈值
            
            # 进行规则匹配（改进：优先匹配更精确的规则）
            matched_results = []
            for item in objective_score_items:
                matched_rule = None
                best_similarity = 0.0
                
                # 按规则优先级排序：排除类规则优先，然后是其他规则
                sorted_rules = sorted(class_b_rules, key=lambda r: (0 if '排除' in r.rule_name or '排除类' in (r.rule_type or '') else 1, r.id))
                
                for rule in sorted_rules:
                    is_matched = False
                    similarity_score = 0.0
                    
                    # 优先使用语义匹配
                    if use_semantic_match:
                        try:
                            similarity_score = self._calculate_semantic_similarity(item, rule.trigger_condition)
                            if similarity_score >= semantic_threshold:
                                is_matched = True
                                log.debug(f"语义匹配成功：条目与规则'{rule.rule_name}'的相似度为{similarity_score:.3f}")
                        except Exception as e:
                            log.debug(f"语义匹配失败（规则'{rule.rule_name}'），回退到关键词匹配：{str(e)}")
                            # 不修改use_semantic_match，继续尝试其他规则的语义匹配
                    
                    # 如果语义匹配未成功，回退到关键词匹配
                    if not is_matched:
                        # 方式1：简单关键词匹配（用于短触发条件）
                        trigger_words = rule.trigger_condition.split()
                        if len(trigger_words) <= 5:  # 短触发条件使用关键词匹配
                            if any(keyword in item for keyword in trigger_words if len(keyword) > 1):
                                is_matched = True
                        
                        # 方式2：包含关键短语匹配（用于长触发条件）
                        if not is_matched:
                            # 提取关键短语（连续的中文词汇）
                            import re
                            # 查找关键短语：能效标识网、备案公告、政府官方网站等
                            key_phrases = re.findall(r'[\u4e00-\u9fa5]{3,}', rule.trigger_condition)
                            if key_phrases:
                                # 检查条目中是否包含这些关键短语
                                for phrase in key_phrases:
                                    if phrase in item:
                                        is_matched = True
                                        break
                        
                        # 方式3：特殊关键词组合匹配
                        if not is_matched:
                            # 检查是否包含"备案"+"网"或"备案"+"公告"等组合
                            if '备案' in rule.trigger_condition and '备案' in item:
                                # 进一步检查是否涉及政府官方网站
                                gov_keywords = ['能效标识网', '备案公告', '政府官方网站', '官方网站', '备案查询', '可查询验证']
                                if any(kw in item for kw in gov_keywords) and any(kw in rule.trigger_condition for kw in gov_keywords):
                                    is_matched = True
                            
                            # 方式4：承诺相关关键词匹配（处理"提供说明和承诺"等情况）
                            if not is_matched:
                                commitment_keywords = ['承诺', '承诺响应', '提供承诺', '提供说明和承诺', '承诺文件', '承诺书', '书面承诺', '说明和承诺']
                                if any(kw in rule.trigger_condition for kw in commitment_keywords):
                                    # 检查条目中是否包含任何承诺相关的关键词
                                    if any(kw in item for kw in commitment_keywords):
                                        is_matched = True
                                        log.debug(f"通过承诺关键词匹配：条目包含承诺相关关键词，匹配规则：{rule.rule_name}")
                    
                    if is_matched:
                        # 如果使用语义匹配，选择相似度最高的规则
                        if use_semantic_match and similarity_score > best_similarity:
                            matched_rule = rule
                            best_similarity = similarity_score
                        elif not use_semantic_match:
                            # 关键词匹配时，选择第一个匹配的规则
                            matched_rule = rule
                            break
                
                if matched_rule:
                    matched_results.append({
                        "item": item,
                        "matched_rule": {
                            "rule_name": matched_rule.rule_name,
                            "trigger_condition": matched_rule.trigger_condition,
                            "conclusion": matched_rule.conclusion,
                            "rule_type": matched_rule.rule_type
                        },
                        "is_matched": True,
                        "similarity_score": best_similarity if use_semantic_match else None
                    })
                else:
                    matched_results.append({
                        "item": item,
                        "matched_rule": None,
                        "is_matched": False,
                        "similarity_score": None
                    })
            
            log.info(f"B类规则匹配完成，共匹配到 {sum(1 for r in matched_results if r['is_matched'])} 个条目")
            return matched_results
        except Exception as e:
            log.error(f"B类规则匹配失败：{str(e)}")
            return []
    
    def match_quantitative_objective_scores(self, objective_score_items):
        """对量化客观分条目进行匹配"""
        try:
            from utils.db import get_class_a_certificates, get_class_b_rules
            
            if not objective_score_items:
                log.info("无客观分条目，跳过量化客观分匹配")
                return []
            
            log.info(f"开始进行量化客观分匹配，共 {len(objective_score_items)} 个客观分条目")
            
            # 获取A类证书和B类规则
            class_a_certificates = get_class_a_certificates(self.db)
            class_b_rules = get_class_b_rules(self.db)
            
            # 进行量化匹配
            matched_results = []
            for item in objective_score_items:
                match_result = {
                    "item": item,
                    "is_quantitative": False,
                    "certificate_count": 0,
                    "required_count": 0,
                    "is_matched": False,
                    "matched_type": ""
                }
                
                # 检查是否是量化评分项
                import re
                
                # 匹配数量要求（如"每提供一个XX证书得1分，最高5分"）
                count_pattern = r'每提供一个(.*?)得\d+分，最高(\d+)分'
                match = re.search(count_pattern, item)
                
                if match:
                    match_result["is_quantitative"] = True
                    certificate_type = match.group(1).strip()
                    match_result["required_count"] = int(match.group(2))
                    
                    # 检查是否属于A类证书
                    if any(certificate_type in cert.certificate_type for cert in class_a_certificates):
                        # 统计符合条件的A类证书数量
                        match_result["certificate_count"] = sum(1 for cert in class_a_certificates if certificate_type in cert.certificate_type)
                        match_result["is_matched"] = match_result["certificate_count"] >= match_result["required_count"]
                        match_result["matched_type"] = "A类证书"
                    
                    # 检查是否属于B类规则覆盖
                    else:
                        for rule in class_b_rules:
                            if any(keyword in item for keyword in rule.trigger_condition.split(' ')) and "全具备" in rule.conclusion:
                                match_result["is_matched"] = True
                                match_result["matched_type"] = "B类规则"
                                break
                
                matched_results.append(match_result)
            
            log.info(f"量化客观分匹配完成")
            return matched_results
        except Exception as e:
            log.error(f"量化客观分匹配失败：{str(e)}")
            return []

    def run(self):
        """执行AI分析（批量处理已解析项目）

        说明：
        - 独立于 Streamlit 单项目分析使用场景；
        - 在内部安全地获取并关闭数据库会话，避免 self.db 未初始化导致崩溃；
        - 出现单个项目异常时，不中断全局流程，而是记录错误并继续下一个项目。
        """
        from utils.db import get_db  # 延迟导入以避免潜在循环依赖

        # 为当前 run 调用单独创建数据库会话
        db = next(get_db())
        self.db = db

        try:
            # 查询待分析的项目
            projects = db.query(TenderProject).filter(
                TenderProject.status == ProjectStatus.PARSED
            ).all()

            log.info(f"待分析项目数：{len(projects)}")
            for project in projects:
                try:
                    if not project.evaluation_content:
                        raise ValueError("项目解析内容为空，无法进行分析")

                    log.info(f"开始分析项目：{project.project_name}（ID：{project.id}）")
                    
                    # 检查原始内容
                    if not project.evaluation_content:
                        raise ValueError("项目解析内容为空，无法进行分析")
                    
                    original_content_length = len(project.evaluation_content)
                    log.info(f"原始内容长度：{original_content_length}字符")
                    
                    # 检查原始内容是否包含评分表关键词
                    score_keywords = ['评分', '评标', '分值', '得分', '评分办法', '评标办法', '评分标准', '评标标准']
                    has_score_keywords_in_original = any(kw in project.evaluation_content for kw in score_keywords)
                    log.info(f"原始内容是否包含评分表关键词：{has_score_keywords_in_original}")
                    
                    # 1. 提取资质要求（包含所有要求）
                    # 优先使用压缩模式，如果提取失败或内容过短，使用全文本模式
                    log.info("尝试使用压缩模式提取评分表...")
                    project_requirements = self.extract_requirements(project.evaluation_content)
                    extract_length = len(project_requirements) if project_requirements else 0
                    log.info(f"压缩模式提取结果长度：{extract_length}字符")
                    
                    # 检查提取结果：如果提取的内容太短（<50字符）或没有找到评分表关键词，使用全文本模式重试
                    if not project_requirements or len(project_requirements.strip()) < 50:
                        log.warning(f"压缩模式提取失败或内容过短（{extract_length}字符），尝试使用全文本模式")
                        project_requirements = self.extract_requirements_fulltext(project.evaluation_content)
                        extract_length = len(project_requirements) if project_requirements else 0
                        log.info(f"全文本模式提取结果长度：{extract_length}字符")
                    
                    # 检查是否包含评分表关键词
                    if project_requirements:
                        has_score_keywords = any(kw in project_requirements for kw in score_keywords)
                        log.info(f"提取结果是否包含评分表关键词：{has_score_keywords}")
                        
                        if not has_score_keywords and has_score_keywords_in_original:
                            log.warning(f"提取结果中未找到评分表关键词，但原始内容中包含，尝试使用全文本模式重新提取")
                            project_requirements_fulltext = self.extract_requirements_fulltext(project.evaluation_content)
                            # 如果全文本模式提取到了评分表关键词，使用全文本模式的结果
                            if project_requirements_fulltext:
                                has_score_keywords_fulltext = any(kw in project_requirements_fulltext for kw in score_keywords)
                                if has_score_keywords_fulltext:
                                    log.info(f"全文本模式成功提取到评分表内容（{len(project_requirements_fulltext)}字符），使用全文本模式结果")
                                    project_requirements = project_requirements_fulltext
                                else:
                                    log.warning(f"全文本模式也未找到评分表关键词，可能评分表提取失败")
                    else:
                        log.error(f"提取结果为空")
                    
                    # 检查是否提取到评分表
                    score_table_not_found = False
                    if not project_requirements or len(project_requirements.strip()) < 50:
                        score_table_not_found = True
                        log.warning(f"AI提取的资质要求无效或过短（{len(project_requirements) if project_requirements else 0}字符），可能未找到评分表")
                    elif "未找到评分办法表格" in project_requirements or "未找到评分表" in project_requirements:
                        score_table_not_found = True
                        log.warning("AI明确返回：未找到评分办法表格")
                    
                    # 如果提取不到评分表，判定为"推荐参与"
                    if score_table_not_found:
                        log.info("提取不到评分表，根据规则判定为：推荐参与")
                        final_decision = "推荐参与"
                        comparison_result = f"""
【比对说明】
未找到评分表，根据系统规则判定为：推荐参与

【说明】
由于无法从标书中提取到有效的评分表内容，无法进行客观分分析，系统判定为推荐参与该项目。
"""
                        # 更新项目状态
                        update_project(db, project.id, {
                            "ai_extracted_text": project_requirements if project_requirements else "",
                            "project_requirements": project_requirements if project_requirements else "",
                            "comparison_result": comparison_result,
                            "final_decision": final_decision,
                            "status": ProjectStatus.COMPARED,
                            "objective_scores": json.dumps([]),
                            "subjective_scores": json.dumps([]),
                            "objective_score_decisions": json.dumps([])
                        })
                        log.info(f"项目分析完成（未找到评分表，判定为推荐参与）：{project.project_name}")
                        continue
                    
                    # 2. 解析招标方式
                    tender_method = self.parse_tender_method(project_requirements)
                    
                    # 3. 识别主客观分
                    score_types = self.identify_score_types(project_requirements)
                    
                    # 3.5. 最终检查：确保价格相关条目被移出客观分（四重保险）
                    objective_scores_filtered = []
                    moved_count = 0
                    for item in score_types["objective_scores"]:
                        if self._is_price_related(item):
                            score_types["subjective_scores"].append(item)
                            moved_count += 1
                            log.warning(f"[最终检查] 发现价格相关条目仍在客观分中，立即移出到主观分：{item[:150]}")
                        else:
                            objective_scores_filtered.append(item)
                    score_types["objective_scores"] = objective_scores_filtered
                    
                    if moved_count > 0:
                        log.warning(f"[最终检查] 共移出{moved_count}个价格相关条目到主观分")
                    
                    # 记录最终的主客观分数量
                    log.info(f"[最终统计] 客观分{len(score_types['objective_scores'])}项，主观分{len(score_types['subjective_scores'])}项")
                    
                    # 输出客观分列表供调试（检查是否还有价格相关）
                    if score_types["objective_scores"]:
                        log.debug(f"[客观分列表] {score_types['objective_scores']}")
                        # 再次验证客观分中是否还有价格相关条目
                        for item in score_types["objective_scores"]:
                            if self._is_price_related(item):
                                log.error(f"[严重错误] 客观分中仍存在价格相关条目：{item[:150]}")
                    if score_types["subjective_scores"]:
                        log.debug(f"[主观分列表] {score_types['subjective_scores']}")
                    
                    # 4. 对客观分条目进行匹配判定
                    objective_score_items = score_types["objective_scores"]
                    objective_score_decisions = []
                    all_scores_attainable = True
                    
                    if objective_score_items:
                        # 执行B类规则匹配
                        class_b_matched_results = self.match_class_b_rules(objective_score_items)
                        
                        # 执行量化客观分匹配
                        quantitative_matched_results = self.match_quantitative_objective_scores(objective_score_items)
                        
                        # 合并匹配结果并判定每个客观分条目的得分情况
                        for i, item in enumerate(objective_score_items):
                            # 检查是否通过B类规则匹配
                            b_rule_matched = False
                            if i < len(class_b_matched_results) and class_b_matched_results[i]["is_matched"]:
                                b_rule_matched = True
                            
                            # 检查是否通过量化匹配
                            quantitative_matched = False
                            if i < len(quantitative_matched_results) and quantitative_matched_results[i]["is_matched"]:
                                quantitative_matched = True
                            
                            # 判定该条目是否可得分
                            is_attainable = b_rule_matched or quantitative_matched
                            if not is_attainable:
                                all_scores_attainable = False
                            
                            # 记录判定结果
                            objective_score_decisions.append({
                                "item": item,
                                "is_attainable": is_attainable,
                                "decision_reason": "B类规则匹配" if b_rule_matched else ("量化匹配" if quantitative_matched else "未匹配到A类证书且无B类规则覆盖")
                            })
                    
                    # 5. 确定项目推荐决策
                    if all_scores_attainable:
                        final_decision = "推荐参与"
                    else:
                        final_decision = "不推荐参与"
                    
                    # 6. 生成比对结果
                    comparison_result = f"""
【比对说明】
{'所有客观分条目均可得分，推荐参与该项目' if all_scores_attainable else '存在客观分条目不可得分，不推荐参与该项目'}

【客观分条目分析】
{chr(10).join([f"{i+1}. {item['item']} - {'可得分' if item['is_attainable'] else '不可得分'} ({item['decision_reason']})" for i, item in enumerate(objective_score_decisions)]) if objective_score_decisions else '无客观分条目'}
"""
                    
                    # 7. 更新项目状态
                    update_project(db, project.id, {
                        "ai_extracted_text": project_requirements,  # 保存AI提取的原始文本
                        "project_requirements": project_requirements,  # 保存所有资质要求
                        "tender_method": tender_method,
                        "comparison_result": comparison_result,  # 保存比对结果
                        "final_decision": final_decision,  # 更新判定结果
                        "status": ProjectStatus.COMPARED,  # 标记为已完成分析
                        "objective_scores": json.dumps(score_types["objective_scores"]),  # 保存客观分列表
                        "subjective_scores": json.dumps(score_types["subjective_scores"]),  # 保存主观分列表
                        "objective_score_decisions": json.dumps(objective_score_decisions)  # 保存客观分判定结果
                    })
                    log.info(f"项目分析完成：{project.project_name}")
                except Exception as e:
                    error_msg = str(e)[:500]
                    update_project(db, project.id, {
                        "status": ProjectStatus.ERROR,
                        "error_msg": error_msg
                    })
                    log.error(f"项目分析失败：ID={project.id}，错误：{error_msg}")
                    continue
        finally:
            # 确保数据库会话被正确关闭
            try:
                db.close()
            except Exception:
                pass
    
    def _filter_company_qualifications(self, requirements):
        """过滤掉企业资质要求部分，只保留其他所有要求"""
        if not requirements:
            return requirements
        
        log.info("开始过滤企业资质要求")
        
        # 如果不包含【企业资质】部分，直接返回原始要求
        if "【企业资质】" not in requirements:
            return requirements
        
        # 使用正则表达式匹配并移除【企业资质】部分
        # 匹配【企业资质】开始，直到下一个分类标记或文档结束
        import re
        filtered_requirements = re.sub(r'【企业资质】.*?(?=【招标方式】|【人员资质】|【设备要求】|【业绩要求】|【其他要求】|$)', '', requirements, flags=re.DOTALL)
        
        log.info("企业资质要求过滤完成")
        log.debug(f"过滤后的要求：{filtered_requirements}")
        
        return filtered_requirements

if __name__ == "__main__":
    analyzer = AIAnalyzer()
    analyzer.run()