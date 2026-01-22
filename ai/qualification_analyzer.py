# 尝试导入OpenAI作为备用方案
try:
    from langchain_openai import ChatOpenAI
    from langchain_openai import OpenAIEmbeddings
except ImportError:
    ChatOpenAI = None
    OpenAIEmbeddings = None

# 尝试导入通义千问作为备用方案
try:
    from langchain_community.chat_models import QianfanChatEndpoint
    from langchain_community.embeddings import QianfanEmbeddingsEndpoint
except ImportError:
    QianfanChatEndpoint = None
    QianfanEmbeddingsEndpoint = None

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from abc import ABC, abstractmethod
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

# 定义AI服务提供商的抽象接口
class AIService(ABC):
    @abstractmethod
    def initialize(self, config):
        pass
    
    @abstractmethod
    def extract_requirements(self, content):
        pass
    
    @abstractmethod
    def compare_qualifications(self, project_requirements, company_qualifications):
        pass
    
    @abstractmethod
    def health_check(self):
        pass

# AI服务工厂
class AIServiceFactory:
    @staticmethod
    def create_service(provider, config):
        if provider == "openai" and ChatOpenAI:
            return OpenAIService()
        elif provider == "dashscope":
            # 检查ChatOpenAI是否可用
            if ChatOpenAI is None:
                log.error("创建DashScope服务失败: ChatOpenAI依赖不可用")
                return None
            return DashScopeService()
        elif provider == "qianfan" and QianfanChatEndpoint:
            return QianfanService()
        else:
            log.error(f"不支持的AI服务提供商: {provider} 或相关依赖未安装")
            return None



# OpenAI服务实现
class OpenAIService(AIService):
    def __init__(self):
        self.llm = None
        self.extract_chain = None
        self.compare_chain = None
        self.service_check_chain = None
        
    def initialize(self, config):
        if ChatOpenAI is None:
            log.warning("OpenAI依赖未安装")
            return False
            
        try:
            api_key = config.get("api_key")
            model_name = config.get("model_name", "gpt-3.5-turbo")
            
            if not api_key:
                log.error("OpenAI API密钥未配置")
                return False
                
            log.info(f"初始化OpenAI服务，模型: {model_name}")
            
            self.llm = ChatOpenAI(
                model=model_name,
                api_key=api_key,
                temperature=config.get("temperature", 0.05),
                max_tokens=config.get("max_tokens", 2000)
            )
            
            # 初始化解析器
            self.extract_parser = StrOutputParser()
            self.compare_parser = StrOutputParser()
            self.service_check_parser = JsonOutputParser()
            
            return True
        except Exception as e:
            log.error(f"OpenAI服务初始化失败: {str(e)}")
            return False
    
    def extract_requirements(self, content):
        if not self.extract_chain:
            raise RuntimeError("提取链未初始化")
        return self.extract_chain.invoke({"content": content})
    
    def compare_qualifications(self, project_requirements, company_qualifications):
        if not self.compare_chain:
            raise RuntimeError("比对链未初始化")
        return self.compare_chain.invoke({
            "project_requirements": project_requirements,
            "company_qualifications": company_qualifications
        })
    
    def health_check(self):
        try:
            response = self.llm.invoke("测试连接")
            return response is not None
        except Exception:
            return False

# 阿里云DashScope服务实现（兼容OpenAI接口）
class DashScopeService(AIService):
    def __init__(self):
        self.llm = None
        self.extract_chain = None
        self.compare_chain = None
        self.service_check_chain = None
        
    def initialize(self, config):
        if ChatOpenAI is None:
            log.warning("ChatOpenAI依赖未安装")
            return False
            
        try:
            api_key = config.get("api_key")
            model_name = config.get("model_name", "qwen-plus")
            base_url = config.get("base_url")
            
            if not api_key:
                log.error("DashScope API密钥未配置")
                return False
            
            if not base_url:
                log.error("DashScope Base URL未配置")
                return False
                
            log.info(f"初始化DashScope服务，模型: {model_name}")
            
            self.llm = ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=base_url,
                temperature=config.get("temperature", 0.05),
                max_tokens=config.get("max_tokens", 4000)
            )
            
            # 初始化解析器
            self.extract_parser = StrOutputParser()
            self.compare_parser = StrOutputParser()
            self.service_check_parser = JsonOutputParser()
            
            return True
        except Exception as e:
            log.error(f"DashScope服务初始化失败: {str(e)}")
            return False
    
    def extract_requirements(self, content):
        if not self.extract_chain:
            raise RuntimeError("提取链未初始化")
        return self.extract_chain.invoke({"content": content})
    
    def compare_qualifications(self, project_requirements, company_qualifications):
        if not self.compare_chain:
            raise RuntimeError("比对链未初始化")
        return self.compare_chain.invoke({
            "project_requirements": project_requirements,
            "company_qualifications": company_qualifications
        })
    
    def health_check(self):
        try:
            response = self.llm.invoke("测试连接")
            return response is not None
        except Exception:
            return False

# 通义千问服务实现
class QianfanService(AIService):
    def __init__(self):
        self.llm = None
        self.extract_chain = None
        self.compare_chain = None
        self.service_check_chain = None
        
    def initialize(self, config):
        if QianfanChatEndpoint is None:
            log.warning("通义千问依赖未安装")
            return False
            
        try:
            api_key = config.get("api_key")
            secret_key = config.get("secret_key")
            model_name = config.get("model_name", "ERNIE-Bot")
            
            if not api_key or not secret_key:
                log.error("通义千问API密钥或Secret Key未配置")
                return False
                
            log.info(f"初始化通义千问服务，模型: {model_name}")
            
            self.llm = QianfanChatEndpoint(
                qianfan_ak=api_key,
                qianfan_sk=secret_key,
                model=model_name,
                temperature=config.get("temperature", 0.05)
            )
            
            # 初始化解析器
            self.extract_parser = StrOutputParser()
            self.compare_parser = StrOutputParser()
            self.service_check_parser = JsonOutputParser()
            
            return True
        except Exception as e:
            log.error(f"通义千问服务初始化失败: {str(e)}")
            return False
    
    def extract_requirements(self, content):
        if not self.extract_chain:
            raise RuntimeError("提取链未初始化")
        return self.extract_chain.invoke({"content": content})
    
    def compare_qualifications(self, project_requirements, company_qualifications):
        if not self.compare_chain:
            raise RuntimeError("比对链未初始化")
        return self.compare_chain.invoke({
            "project_requirements": project_requirements,
            "company_qualifications": company_qualifications
        })
    
    def health_check(self):
        try:
            response = self.llm.invoke("测试连接")
            return response is not None
        except Exception:
            return False

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

# 辅助函数：加载提示词模板
def load_prompt_template(file_path):
    """从文件加载提示词模板"""
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"提示词模板文件未找到: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        log.error(f"加载提示词模板失败: {str(e)}")
        raise

# 请求频率限制器
class RateLimiter:
    """请求频率限制器，防止API调用过于频繁"""
    def __init__(self, max_requests_per_hour=40, min_interval_seconds=90, burst_allowance=5):
        self.max_requests_per_hour = max_requests_per_hour
        self.min_interval_seconds = min_interval_seconds
        self.burst_allowance = burst_allowance
        
        # 记录请求时间的队列，用于计算每小时请求数
        self.request_times = deque()
        
        # 最后一次请求时间，用于计算请求间隔
        self.last_request_time = 0
    
    def wait_for_rate_limit(self):
        """等待直到可以发送请求"""
        current_time = time.time()
        
        # 移除一小时前的请求记录
        while self.request_times and current_time - self.request_times[0] > 3600:
            self.request_times.popleft()
        
        # 检查每小时请求数是否超过限制
        if len(self.request_times) >= self.max_requests_per_hour:
            # 计算需要等待的时间
            wait_time = 3600 - (current_time - self.request_times[0])
            log.info(f"请求频率限制：每小时请求数已达上限({self.max_requests_per_hour})，需要等待 {wait_time:.1f} 秒")
            time.sleep(wait_time)
            # 等待后清空请求记录
            self.request_times.clear()
        
        # 检查请求间隔是否满足最小间隔
        if current_time - self.last_request_time < self.min_interval_seconds:
            wait_time = self.min_interval_seconds - (current_time - self.last_request_time)
            log.info(f"请求频率限制：请求间隔过小，需要等待 {wait_time:.1f} 秒")
            time.sleep(wait_time)
        
        # 更新请求记录
        self.request_times.append(time.time())
        self.last_request_time = time.time()

# AI分析器类
class AIAnalyzer:
    def __init__(self, model_type=None, provider=None):
        # 初始化服务提供商配置
        self.ai_providers = []
        self.current_provider_index = 0
        self.current_service = None
        
        # 加载所有可用的AI服务提供商配置
        self._load_providers_config()
        
        # 如果没有指定provider，则从AI_CONFIG中读取默认的provider
        if not provider:
            provider = AI_CONFIG.get("provider", "dashscope")
        
        # 尝试使用指定的provider
        provider_index = next((i for i, p in enumerate(self.ai_providers) if p["name"] == provider), None)
        if provider_index is not None:
            self.current_provider_index = provider_index
        else:
            log.warning(f"指定的AI服务提供商 '{provider}' 不可用，将使用默认提供商")
        
        # 初始化当前服务
        self._initialize_service()
        
        # 延迟加载公司资质
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
    
    def _load_providers_config(self):
        """加载所有可用的AI服务提供商配置"""
        # 从AI_CONFIG中加载所有服务提供商配置
        providers = []
        
        # 添加OpenAI配置
        if "openai" in AI_CONFIG and ChatOpenAI:
            providers.append({
                "name": "openai",
                "config": AI_CONFIG["openai"]
            })
        
        # 添加阿里云DashScope配置
        if "dashscope" in AI_CONFIG and ChatOpenAI:
            providers.append({
                "name": "dashscope",
                "config": AI_CONFIG["dashscope"]
            })
        
        # 添加通义千问配置
        if "qianfan" in AI_CONFIG and QianfanChatEndpoint:
            providers.append({
                "name": "qianfan",
                "config": AI_CONFIG["qianfan"]
            })
        
        if not providers:
            raise ValueError("没有可用的AI服务提供商配置")
        
        self.ai_providers = providers
        log.info(f"加载了{len(providers)}个AI服务提供商配置: {[p['name'] for p in providers]}")
    
    def _initialize_service(self):
        """初始化当前AI服务"""
        provider_info = self.ai_providers[self.current_provider_index]
        provider_name = provider_info["name"]
        provider_config = provider_info["config"]
        
        log.info(f"正在初始化{provider_name}服务...")
        
        # 使用服务工厂创建服务实例
        self.current_service = AIServiceFactory.create_service(provider_name, provider_config)
        
        if not self.current_service:
            log.error(f"创建{provider_name}服务实例失败")
            self._switch_service()  # 切换到下一个服务提供商
            return
        
        # 初始化服务
        if not self.current_service.initialize(provider_config):
            log.error(f"{provider_name}服务初始化失败")
            self._switch_service()  # 切换到下一个服务提供商
            return
        
        # 构建处理链
        self._build_processing_chains()
        
        log.info(f"{provider_name}服务初始化成功")
    
    def _build_processing_chains(self):
        """构建AI处理链"""
        log.info("正在构建AI处理链...")
        
        # 加载提示词模板
        extract_prompt_path = AI_CONFIG["extract_prompt_path"]
        compare_prompt_path = AI_CONFIG["compare_prompt_path"]
        
        extract_template = load_prompt_template(extract_prompt_path)
        compare_template = load_prompt_template(compare_prompt_path)
        
        # 创建提示词模板
        extract_prompt = PromptTemplate(
            input_variables=["content"],
            template=extract_template + "\n\n请严格按照上述格式输出结果，不要添加任何额外内容。"
        )
        
        compare_prompt = PromptTemplate(
            input_variables=["project_requirements", "company_qualifications"],
            template=compare_template + "\n\n请严格按照上述格式输出结果，不要添加任何额外内容。"
        )
        
        # 构建处理链
        self.current_service.extract_chain = extract_prompt | self.current_service.llm | self.current_service.extract_parser
        self.current_service.compare_chain = compare_prompt | self.current_service.llm | self.current_service.compare_parser
        
        # 加载服务类判断链（如果配置了）
        service_check_prompt_path = AI_CONFIG.get("service_check_prompt_path")
        if service_check_prompt_path and os.path.exists(service_check_prompt_path):
            service_check_template = load_prompt_template(service_check_prompt_path)
            service_check_prompt = PromptTemplate(
                input_variables=["content"],
                template=service_check_template + "\n\n请严格按照上述格式输出结果，不要添加任何额外内容。"
            )
            self.current_service.service_check_chain = service_check_prompt | self.current_service.llm | self.current_service.service_check_parser
        else:
            self.current_service.service_check_chain = None
            log.warning("服务类判断提示词模板未配置或不存在，将跳过服务类判断")
        
        log.info("AI处理链构建完成")
    
    def _switch_service(self):
        """切换到下一个AI服务提供商"""
        log.info("正在切换到下一个AI服务提供商...")
        
        # 尝试所有可用的服务提供商
        for i in range(1, len(self.ai_providers) + 1):
            next_index = (self.current_provider_index + i) % len(self.ai_providers)
            
            # 如果已经尝试了所有提供商，抛出异常
            if next_index == self.current_provider_index:
                raise RuntimeError("所有AI服务提供商均不可用")
            
            self.current_provider_index = next_index
            provider_name = self.ai_providers[next_index]["name"]
            
            log.info(f"尝试切换到{provider_name}服务...")
            
            # 初始化新服务
            try:
                self._initialize_service()
                if self.current_service and self.current_service.health_check():
                    log.info(f"成功切换到{provider_name}服务")
                    return
            except Exception as e:
                log.error(f"切换到{provider_name}服务失败: {str(e)}")
        
        # 如果所有服务都不可用
        raise RuntimeError("所有AI服务提供商均不可用")
    
    def _execute_with_fallback(self, func, *args, **kwargs):
        """使用备用服务执行函数"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # 检查当前服务是否可用
                if not self.current_service.health_check():
                    log.warning("当前AI服务不可用，正在切换服务...")
                    self._switch_service()
                
                # 执行函数
                return func(*args, **kwargs)
            except Exception as e:
                log.error(f"AI服务执行失败 (重试 {retry_count + 1}/{max_retries}): {str(e)}")
                retry_count += 1
                
                # 如果重试次数超过限制，切换服务
                if retry_count >= max_retries:
                    log.warning("重试次数已达上限，正在切换服务...")
                    self._switch_service()
                    retry_count = 0  # 重置重试计数器
                
                # 等待一段时间后重试
                time.sleep(2 ** retry_count)  # 指数退避
        
        raise RuntimeError("所有AI服务提供商均不可用")
    
    def _format_company_qualifications(self):
        """格式化公司资质为字符串"""
        try:
            log.info("开始格式化公司资质信息...")
            from utils.db import get_db, get_company_qualifications, get_class_a_certificates, get_class_b_rules
            
            db = next(get_db())
            qual_lines = []
            
            # 添加公司资质信息
            db_qualifications = get_company_qualifications(db)
            for category, quals in db_qualifications.items():
                qual_lines.append(f"【{category}】")
                for qual in quals:
                    clean_qual = re.sub(r'\s+', ' ', qual).strip()
                    clean_qual = re.sub(r'\u3000', ' ', clean_qual).strip()
                    qual_lines.append(f"- {clean_qual}")
                qual_lines.append("")
            
            # 添加A类证书库信息
            qual_lines.append("【A类证书库】")
            class_a_certificates = get_class_a_certificates(db)
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
            
            # 添加B类规则库信息
            qual_lines.append("【B类规则库】")
            class_b_rules = get_class_b_rules(db)
            if class_b_rules:
                for rule in class_b_rules:
                    rule_info = f"规则名称: {rule.rule_name}"
                    if rule.rule_type:
                        rule_info += f", 规则类型: {rule.rule_type}"
                    if rule.trigger_condition:
                        rule_info += f", 触发条件: {rule.trigger_condition[:100]}..."  # 限制长度
                    if rule.conclusion:
                        rule_info += f", 结论: {rule.conclusion[:100]}..."  # 限制长度
                    qual_lines.append(f"- {rule_info}")
                qual_lines.append("")
            else:
                qual_lines.append("- 暂无B类规则库信息")
                qual_lines.append("")
            
            # 生成最终的资质字符串
            self.company_qual_str = "\n".join(qual_lines).strip()
            log.info(f"公司资质信息格式化完成，共{len(qual_lines)}行")
            return self.company_qual_str
        except Exception as e:
            log.error(f"格式化公司资质信息失败: {str(e)}")
            # 如果从数据库加载失败，使用配置文件中的默认资质
            log.info("将使用配置文件中的默认公司资质")
            self.company_qual_str = COMPANY_QUALIFICATIONS
            return self.company_qual_str
    
    def is_service_project(self, evaluation_content):
        """判断项目是否是服务类项目
        
        Args:
            evaluation_content: 项目解析内容
            
        Returns:
            tuple: (is_service: bool, reason: str) 如果是服务类返回True，否则返回False
        """
        try:
            # 首先检查配置是否启用了服务类判断功能
            from config import AI_CONFIG
            if not AI_CONFIG.get("service_check", {}).get("enable", False):
                log.debug("服务类判断功能已禁用（需手动启用），默认返回False（非服务类）")
                return False, "服务类判断功能已禁用（需手动启用）"
                
            # 如果当前服务未初始化或服务类判断链未初始化，返回False（默认不是服务类）
            if not hasattr(self, 'current_service') or not self.current_service or \
               not hasattr(self.current_service, 'service_check_chain') or self.current_service.service_check_chain is None:
                log.debug("服务类判断功能未启用，默认返回False（非服务类）")
                return False, "服务类判断功能未启用"
            
            log.info("开始判断项目是否是服务类项目")
            
            # 请求频率控制
            if hasattr(self, 'rate_limiter') and self.rate_limiter:
                self.rate_limiter.wait_for_rate_limit()
            
            # 限制内容长度，避免过长（取前5000字符应该足够判断）
            content = evaluation_content[:5000] if len(evaluation_content) > 5000 else evaluation_content
            
            # 执行LLM调用（添加重试机制）
            max_retries = 3
            retry_count = 0
            result = None
            
            while retry_count < max_retries:
                try:
                    result = self.current_service.service_check_chain.invoke({"content": content})
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
                    import json
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
    
    def extract_requirements(self, content):
        """提取项目资质要求（转发到当前服务）
        
        Args:
            content: 项目内容
            
        Returns:
            提取的项目资质要求
        """
        try:
            if not hasattr(self, 'current_service') or not self.current_service:
                log.error("当前AI服务未初始化，无法提取项目资质要求")
                raise RuntimeError("当前AI服务未初始化")
            
            if not hasattr(self.current_service, 'extract_requirements'):
                log.error("当前AI服务不支持extract_requirements方法")
                raise RuntimeError("当前AI服务不支持extract_requirements方法")
            
            log.info("开始提取项目资质要求（转发到当前服务）")
            
            # 请求频率控制
            if hasattr(self, 'rate_limiter') and self.rate_limiter:
                self.rate_limiter.wait_for_rate_limit()
            
            # 限制内容长度，避免超出AI模型的输入长度限制
            # 从全局配置中读取可配置的最大长度，便于在模型支持长文本时关闭或放宽截断
            try:
                from config import AI_CONFIG  # 延迟导入避免循环依赖
                max_input_length = AI_CONFIG.get("preprocessing", {}).get("max_text_length", 30000)
            except Exception:
                max_input_length = 30000  # 回退到安全默认值
            if len(content) > max_input_length:
                log.warning(f"输入内容过长（{len(content)}字符），将截断为{max_input_length}字符")
                content = content[:max_input_length]
            
            # 使用当前服务执行提取
            return self._execute_with_fallback(
                self.current_service.extract_requirements,
                content
            )
            
        except Exception as e:
            log.error(f"提取项目资质要求失败：{str(e)}")
            raise
    
    def extract_project_requirements(self, content, tender_id=None):
        """提取项目资质要求"""
        log.info(f"开始提取项目资质要求 (tender_id: {tender_id})")
        
        try:
            # 检查请求频率限制
            if self.rate_limiter:
                self.rate_limiter.wait_for_rate_limit()
            
            # 限制内容长度，避免超出AI模型的输入长度限制
            try:
                from config import AI_CONFIG  # 延迟导入避免循环依赖
                max_input_length = AI_CONFIG.get("preprocessing", {}).get("max_text_length", 30000)
            except Exception:
                max_input_length = 30000
            if len(content) > max_input_length:
                log.warning(f"输入内容过长（{len(content)}字符），将截断为{max_input_length}字符")
                content = content[:max_input_length]
            
            # 使用当前服务执行提取
            result = self._execute_with_fallback(
                self.current_service.extract_requirements,
                content
            )
            
            # 验证提取结果
            extracted = ExtractedRequirements(requirements=result, is_valid=True)
            log.info(f"项目资质要求提取完成 (tender_id: {tender_id})")
            
            # 更新数据库中的项目状态
            if tender_id:
                db = next(get_db())
                update_project(db, tender_id, {
                    "status": ProjectStatus.ANALYZED,
                    "extracted_requirements": extracted.requirements,
                    "analysis_time": datetime.now()
                })
                log.info(f"已更新项目状态为ANALYZED (tender_id: {tender_id})")
            
            return extracted
        except Exception as e:
            log.error(f"提取项目资质要求失败 (tender_id: {tender_id}): {str(e)}")
            # 返回无效的提取结果
            return ExtractedRequirements(requirements="", is_valid=False)
    
    def compare_qualifications(self, project_requirements, company_qual_str=None):
        """比较项目要求与公司资质"""
        log.info("开始比较项目要求与公司资质")
        
        try:
            # 检查请求频率限制
            if self.rate_limiter:
                self.rate_limiter.wait_for_rate_limit()
            
            # 如果没有提供公司资质字符串，加载并格式化
            if not company_qual_str:
                company_qual_str = self._format_company_qualifications()
            
            # 限制内容长度，避免超出AI模型的输入长度限制
            try:
                from config import AI_CONFIG  # 延迟导入避免循环依赖
                max_input_length = AI_CONFIG.get("preprocessing", {}).get("max_text_length", 30000)
            except Exception:
                max_input_length = 30000

            # 单个输入参数的最大长度，默认取总长度的一半，避免某一端被截断过多
            max_single_input_length = max_input_length // 2
            
            # 对每个输入参数单独进行截断
            if len(project_requirements) > max_single_input_length:
                log.warning(f"项目要求过长（{len(project_requirements)}字符），将截断为{max_single_input_length}字符")
                project_requirements = project_requirements[:max_single_input_length]
            
            if len(company_qual_str) > max_single_input_length:
                log.warning(f"公司资质过长（{len(company_qual_str)}字符），将截断为{max_single_input_length}字符")
                company_qual_str = company_qual_str[:max_single_input_length]
            
            # 计算总长度
            total_length = len(project_requirements) + len(company_qual_str)
            
            if total_length > max_input_length:
                # 如果总长度超出限制，优先保留公司资质，截断项目要求
                project_max_length = max_input_length - len(company_qual_str)
                if project_max_length > 0:
                    log.warning(f"输入内容过长（总长度 {total_length} 字符），将进一步截断项目要求为 {project_max_length} 字符")
                    project_requirements = project_requirements[:project_max_length]
                else:
                    # 如果公司资质本身就超出了限制，也需要截断
                    company_qual_str = company_qual_str[:max_input_length // 2]
                    project_requirements = project_requirements[:max_input_length // 2]
                    log.warning(f"输入内容过长（总长度 {total_length} 字符），将截断公司资质和项目要求各为 {max_input_length // 2} 字符")
            
            # 使用当前服务执行比较，添加输入长度错误的处理
            try:
                result = self._execute_with_fallback(
                    self.current_service.compare_qualifications,
                    project_requirements,
                    company_qual_str
                )
            except Exception as e:
                error_msg = str(e)
                if "input length" in error_msg.lower() or "length" in error_msg.lower():
                    # 如果是输入长度错误，进行更严格的截断并重试
                    log.warning(f"AI服务返回输入长度错误，进行更严格的截断：{error_msg[:100]}")
                    
                    # 进一步减少输入长度
                    stricter_max_length = 20000
                    if len(project_requirements) > stricter_max_length:
                        log.warning(f"项目要求过长，将进一步截断为{stricter_max_length}字符")
                        project_requirements = project_requirements[:stricter_max_length]
                    
                    if len(company_qual_str) > stricter_max_length:
                        log.warning(f"公司资质过长，将进一步截断为{stricter_max_length}字符")
                        company_qual_str = company_qual_str[:stricter_max_length]
                    
                    # 再次尝试执行比较
                    log.info("使用截断后的输入重试AI服务调用")
                    result = self._execute_with_fallback(
                        self.current_service.compare_qualifications,
                        project_requirements,
                        company_qual_str
                    )
                else:
                    # 其他错误，直接抛出
                    raise
            
            log.info("项目要求与公司资质比较完成")
            
            # 确保返回二元组 (comparison_result, final_decision)
            if isinstance(result, tuple) and len(result) == 2:
                # 如果已经是二元组，直接返回
                comparison_result, final_decision = result
            else:
                # 如果不是二元组，将其作为比较结果，设置默认决策
                comparison_result = result
                final_decision = "通过"  # 默认决策为通过
            
            # 应用失分阈值调整，确保AI判断为最终判断
            from config import OBJECTIVE_SCORE_CONFIG
            if OBJECTIVE_SCORE_CONFIG.get("enable_loss_score_adjustment", True):
                # 优先从“客观分总满分 / 客观分可得分”中计算丢分；找不到时再尝试正则匹配“丢分/失分”
                loss_score = 0.0
                import re

                # 1. 通过总分和得分计算丢分
                total_match = re.search(r'客观分总满分[：: ]*([0-9]+\.?[0-9]*)分', comparison_result)
                gain_match = re.search(r'客观分可得分[：: ]*([0-9]+\.?[0-9]*)分', comparison_result)
                if total_match and gain_match:
                    try:
                        total_score = float(total_match.group(1))
                        gain_score = float(gain_match.group(1))
                        loss_score = max(total_score - gain_score, 0.0)
                    except ValueError:
                        loss_score = 0.0

                # 2. 如果上面未算出丢分，再尝试匹配“丢分/失分 X 分”模式
                if loss_score == 0.0:
                    loss_match = re.search(r'[丢失]分.*?([0-9]+\.?[0-9]*)分', comparison_result)
                    if loss_match:
                        try:
                            loss_score = float(loss_match.group(1))
                        except ValueError:
                            loss_score = 0.0

                threshold = OBJECTIVE_SCORE_CONFIG.get("loss_score_threshold", 1.0)
                if loss_score <= threshold:
                    # 丢分≤阈值，改为"推荐参与"
                    final_decision = "推荐参与"
                    comparison_result += f"\n\n【AI最终判断说明】\n- 丢分：{loss_score}分\n- 阈值：{threshold}分\n- 最终判断：推荐参与"
                else:
                    # 丢分>阈值，改为"不推荐参与"
                    final_decision = "不推荐参与"
                    comparison_result += f"\n\n【AI最终判断说明】\n- 丢分：{loss_score}分\n- 阈值：{threshold}分\n- 最终判断：不推荐参与"
            
            log.info(f"AI最终判断：{final_decision}")
            return comparison_result, final_decision
        except Exception as e:
            log.error(f"比较项目要求与公司资质失败: {str(e)}")
            raise
    
    def analyze_tender_project(self, tender_id):
        """分析单个招标项目的资质要求并进行匹配"""
        log.info(f"开始分析招标项目 (tender_id: {tender_id})")
        
        try:
            # 获取项目信息
            db = next(get_db())
            project = db.query(TenderProject).filter_by(id=tender_id).first()
            
            if not project:
                log.error(f"招标项目不存在 (tender_id: {tender_id})")
                return None
            
            # 检查项目状态
            if project.status in [ProjectStatus.ANALYZED, ProjectStatus.MATCHED]:
                log.info(f"项目已分析或已匹配，跳过分析 (tender_id: {tender_id}, status: {project.status})")
                return project
            
            # 提取项目资质要求
            log.info(f"正在提取项目资质要求 (tender_id: {tender_id})")
            extracted = self.extract_project_requirements(project.content, tender_id)
            
            if not extracted.is_valid:
                log.error(f"项目资质要求提取失败 (tender_id: {tender_id})")
                update_project(db, tender_id, {
                    "status": ProjectStatus.FAILED,
                    "error_message": "项目资质要求提取失败"
                })
                return None
            
            # 比较项目要求与公司资质
            log.info(f"正在比较项目要求与公司资质 (tender_id: {tender_id})")
            comparison_result, final_decision = self.compare_qualifications(extracted.requirements)
            
            # 更新项目信息
            update_project(db, tender_id, {
                "status": ProjectStatus.MATCHED,
                "comparison_result": comparison_result,
                "final_decision": final_decision
            })
            
            log.info(f"招标项目分析完成 (tender_id: {tender_id})")
            return project
        except Exception as e:
            log.error(f"分析招标项目失败 (tender_id: {tender_id}): {str(e)}")
            # 更新项目状态为失败
            db = next(get_db())
            update_project(db, tender_id, {
                "status": ProjectStatus.FAILED,
                "error_message": str(e)
            })
            return None
    
    def analyze_unprocessed_projects(self):
        """分析所有未处理的招标项目"""
        log.info("开始分析所有未处理的招标项目")
        
        try:
            db = next(get_db())
            unprocessed_projects = db.query(TenderProject).filter(
                TenderProject.status == ProjectStatus.UNPROCESSED
            ).all()
            
            log.info(f"找到{len(unprocessed_projects)}个未处理的招标项目")
            
            processed_count = 0
            failed_count = 0
            
            for project in unprocessed_projects:
                try:
                    if self.analyze_tender_project(project.id):
                        processed_count += 1
                    else:
                        failed_count += 1
                    
                    # 每处理5个项目休息一下
                    if processed_count % 5 == 0:
                        log.info(f"已处理{processed_count}个项目，休息30秒...")
                        time.sleep(30)
                except Exception as e:
                    log.error(f"处理项目失败 (tender_id: {project.id}): {str(e)}")
                    failed_count += 1
            
            log.info(f"未处理项目分析完成：成功{processed_count}个，失败{failed_count}个")
            return {
                "processed": processed_count,
                "failed": failed_count,
                "total": len(unprocessed_projects)
            }
        except Exception as e:
            log.error(f"分析未处理项目失败: {str(e)}")
            raise
