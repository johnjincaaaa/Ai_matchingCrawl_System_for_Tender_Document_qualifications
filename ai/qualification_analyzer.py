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
import threading
from datetime import datetime, timedelta
from collections import deque
from utils.db import get_db, TenderProject, ProjectStatus, update_project, get_company_qualifications, get_class_a_certificates, get_class_b_rules


# 价格/报价类关键词：这类条目属主观分，不计入客观分统计（与"客观分总满分"口径一致）
_PRICE_KEYWORDS_RE = re.compile(r'价格|报价')

# 通用管理体系认证的规范化别名 -> 归一标识。用于"真实持证豁免"确定性判定：
# 公司A类库若真实持有对应体系证书，则评分项即便要求 cnca.cn 查询验证，核验也能通过，
# 不应被"政府官方网站备案排除规则"误杀为0分。
_SYSTEM_CERT_ALIASES = {
    "quality": ["质量管理体系", "iso9001", "iso 9001", "9001"],
    "environment": ["环境管理体系", "iso14001", "iso 14001", "14001"],
    "occupational": ["职业健康安全", "职业健康", "iso45001", "iso 45001", "45001"],
    "itsm": ["信息技术服务管理体系", "信息技术服务管理", "iso20000", "iso 20000", "iso/iec 20000", "20000"],
    "infosec": ["信息安全管理体系", "信息安全管理", "iso27001", "iso 27001", "iso/iec 27001", "27001"],
}

# 专业范围硬限定信号：评分项要求"认证范围须覆盖某具体专业领域"时，通用体系证书未必覆盖，
# 不能确定性豁免（交由AI/人工判定），故命中这些信号的条目不自动救回。
_SCOPE_RESTRICTION_RE = re.compile(
    r'认证范围|范围包含|范围涵盖|范围需|范围须|范围应|范围含|覆盖.{0,8}(服务|业务|领域|生产|销售|制造)'
)

# 公司【没有】的证书信号：要求段命中任一即说明该条目要的不是（或不只是）通用体系认证，
# 不适用真实持证豁免。涵盖：具体产品/能效认证、其他体系、个人资质、业绩、检测报告等。
_NON_HELD_CERT_RE = re.compile(
    r'节能产品|环境标志产品|环保产品|绿色产品|能效|3c|ccc|强制性认证|'
    r'食品安全管理体系|haccp|知识产权管理体系|能源管理体系|保密|隐私信息|业务连续性|'
    r'售后服务认证|服务认证|碳中和|软件著作权|软件产品|检测报告|型式检验|'
    r'职称|建造师|工程师|执业资格|注册.{0,4}师|社保|业绩|中标|合同复印件|行政许可|经营许可'
)

# 抽取"项目要求分析"段（要求到底是什么），避免被"匹配过程分析"里 AI 顺带提及的
# 通用体系认证名（如"公司有ISO14001但不能替代环境标志产品认证"）误导。
_REQUIRE_SECTION_RE = re.compile(
    r'项目要求(?:分析)?[：:].*?(?=\n\s*2[．.、]|匹配过程分析|$)', re.S
)


def _held_system_cert_keys(held_cert_names):
    """把公司A类库证书名列表归一为体系标识集合（quality/environment/...）。"""
    joined = " ".join(held_cert_names).lower()
    keys = set()
    for key, aliases in _SYSTEM_CERT_ALIASES.items():
        if any(a in joined for a in aliases):
            keys.add(key)
    return keys


def _block_requires_only_held_certs(block, held_keys):
    """判断某客观分条目块是否属于"真实持证豁免"情形。

    返回 True 的条件（全部满足）：
    1. 条目【要求段】要求的是通用管理体系认证（要求段命中至少一个体系别名）；
       —— 只看"项目要求分析"段，不扫整块，避免被"匹配过程分析"里 AI 顺带提到的
          体系认证名（如"公司有ISO14001但不能替代环境标志产品认证"）误判；
    2. 要求段未出现公司没有的证书信号（节能/环境标志产品、能效、食品安全体系、
       个人职称、业绩、检测报告等）——避免把"产品认证/混合缺证"误救；
    3. 要求段命中的体系认证，全部落在公司真实持有的 held_keys 内；
    4. 未出现专业范围硬限定（认证范围须覆盖IDC/无线电/垃圾清运/软件开发等）。

    命中即视为：该条目所需证书公司真实持有、cnca 核验可通过，应判满足。
    """
    # 只在"项目要求分析"段内判断；抽取失败则退回用整块（保守：后续 _NON_HELD 会再拦一道）
    m_req = _REQUIRE_SECTION_RE.search(block)
    scope_text = m_req.group(0) if m_req else block
    low = scope_text.lower()

    # 要求段出现公司没有的证书信号 -> 不是纯体系认证要求，不救回
    if _NON_HELD_CERT_RE.search(low):
        return False

    # 要求段存在专业范围硬限定 -> 不确定覆盖，不自动救回
    if _SCOPE_RESTRICTION_RE.search(scope_text):
        return False

    # 要求段出现了哪些体系认证（具体别名）
    mentioned = set()
    for key, aliases in _SYSTEM_CERT_ALIASES.items():
        if any(a in low for a in aliases):
            mentioned.add(key)
    if mentioned:
        # 命中具体体系别名：要求的体系认证必须全部是公司真实持有的
        return mentioned.issubset(held_keys)

    # 要求段未写具体证书名，但出现"X类/多类(管理)体系认证"这类泛指表述
    # （且上方已确认无 NON_HELD 信号）-> 视为纯通用体系认证要求，公司5张体系证书可覆盖，救回
    if re.search(r'(体系认证|管理体系)', low) and \
       re.search(r'[一二三四五六两多几]\s*类|[一二三四五六两多几]\s*个|每提供|每类|多类|各类', low):
        return True

    return False  # 要求段不是体系认证类条目，不适用本豁免


def _postcheck_objective_score(comparison_result, held_cert_names=None):
    """对AI比对结果做后校验，返回 (逐条累加的可得分, 逐条累加满分, 被强制置0的矛盾条目列表, 客观分条目数, 被豁免救回的条目列表)。

    校验四类模型不可靠之处：
    1. 排除规则自检=是 但综合判定却是"满足" -> 强制该条目置0（矛盾条目）
    2. 模型自己写的"客观分可得分"汇总可能算错 -> 用逐条累加值代替
    3. 模型有时把价格/报价条目错列为客观分条目 -> 累加时跳过，避免gain虚高、丢分被抹平
    4. 【真实持证豁免】模型把"公司真实持有的通用体系认证"因要求cnca查询而误触发排除判0
       -> 当条目所需体系证书公司确实持有、且无专业范围硬限定时，救回为满分（防批量误杀）
    """
    held_keys = _held_system_cert_keys(held_cert_names or [])

    # 按"【客观分条目N：...】"切分为条目块（主观分说明块不含"综合判定"，天然被跳过）
    blocks = re.split(r'(?=【客观分条目\s*\d+)', comparison_result)
    total_gain = 0.0      # 逐条累加的可得分（已排除价格类条目）
    total_full = 0.0      # 逐条累加的满分（已排除价格类条目，供参考）
    conflicts = []        # 触发排除规则却判满足的条目名
    rescued = []          # 因真实持证豁免被救回的条目名
    item_count = 0        # 客观分条目数（0则说明未提取到任何评分项）

    for block in blocks:
        m_head = re.match(r'【客观分条目\s*\d+[：:]\s*([^】]*)】', block)
        if not m_head:
            continue  # 非条目块（如评分项列表、最终判定）跳过
        item_name = m_head.group(1).strip()
        item_count += 1

        # 价格/报价条目属主观分，客观分总满分已将其排除；此处也必须跳过，否则gain虚高
        if _PRICE_KEYWORDS_RE.search(item_name):
            continue

        # 该条目满分：优先取"满分：X分"，否则用"可得分数"上限推断
        m_full = re.search(r'满分[：: ]*([0-9]+\.?[0-9]*)\s*分?', block)
        full_score = float(m_full.group(1)) if m_full else 0.0

        # 综合判定里的"可得分数"（已改为单一数字，但兼容旧的"X分/0分"）
        m_gain = re.search(r'可得分数[：: ]*([0-9]+\.?[0-9]*)', block)
        gain_score = float(m_gain.group(1)) if m_gain else 0.0

        # 排除规则自检字段；无该字段时，退回用文本是否出现"触发...排除规则"判断
        m_self = re.search(r'排除规则自检[：: ]*([是否])', block)
        if m_self:
            excluded = (m_self.group(1) == '是')
        else:
            excluded = bool(re.search(r'触发[^，。\n]*排除规则', block))

        # 【真实持证豁免】优先级最高：触发排除且判0，但所需体系证书公司真实持有 -> 救回满分
        if excluded and gain_score <= 0 and held_keys and \
                _block_requires_only_held_certs(block, held_keys):
            gain_score = full_score
            rescued.append(item_name)
        # 矛盾修正：触发排除却给了分（且未被豁免救回）-> 强制置0
        elif excluded and gain_score > 0:
            conflicts.append(item_name)
            gain_score = 0.0

        total_gain += gain_score
        total_full += full_score

    return total_gain, total_full, conflicts, item_count, rescued


def _parse_objective_full_score(comparison_result, fallback=0.0):
    """解析"客观分总满分"数值，兼容算式写法。

    只认【真正的总满分声明行】——即"客观分总满分"后面（允许中文冒号/空格）
    **紧跟数字或算式**的行，例如：
        客观分总满分：4分
        客观分总满分：3 + 4 + 15 = 22分
        - 客观分总满分：**67分**（...）
    而【拒绝】"客观分总满分"后面紧跟中文说明的解释句，例如：
        客观分总满分 = 所有客观分条目的满分相加，已排除...（报价评分40分已归入主观分）
    否则解释句里夹带的无关数字（如"报价评分40分"的40）会被误当成总满分，
    导致丢分虚高、把"满分可参与"误判成"不推荐"。

    多个合法声明行时取**最接近 fallback（逐条累加满分）的那个**：逐条累加满分是
    最可靠的基准，模型汇总行只用来兜底/补正，避免再次被离群值带偏。
    解析全部失败时返回 fallback。
    """
    vals = []
    # 冒号后允许若干空白/加粗星号，然后【必须紧跟数字】才认定是声明行
    for m_line in re.finditer(r'客观分总满分\s*[：:]\s*\**\s*(?=[0-9])([^\n]*)', comparison_result):
        line = m_line.group(1)
        # 优先取 "= N分" 的最终结果（N 可能被 ** 包裹）
        m_eq = re.search(r'=\s*\**\s*([0-9]+\.?[0-9]*)\s*\**\s*分?', line)
        if m_eq:
            try:
                vals.append(float(m_eq.group(1)))
                continue
            except ValueError:
                pass
        # 没有等号时，若是"a + b + c"形式则对加数求和
        addends = re.findall(r'([0-9]+\.?[0-9]*)\s*(?=\+)|(?<=\+)\s*([0-9]+\.?[0-9]*)', line)
        if '+' in line and addends:
            try:
                flat = [float(a or b) for a, b in addends]
                if flat:
                    vals.append(sum(flat))
                    continue
            except ValueError:
                pass
        # 退回：取该行第一个数字（此时行首已确保是数字）
        m_num = re.match(r'\s*([0-9]+\.?[0-9]*)', line)
        if m_num:
            try:
                vals.append(float(m_num.group(1)))
            except ValueError:
                pass
    if not vals:
        return fallback
    # 逐条累加满分(fallback)是最可靠基准。合法声明行里可能仍混入离群大值
    # （如算式误解析、或声明行本身写错），用 fallback 做上界保护：
    # 只接受"不超过 fallback 合理倍数(1.5×+2)"的声明值，取其中最大者；
    # 若全部被判离群，则直接用 fallback。fallback 不可用(<=0)时退回取max。
    if fallback and fallback > 0:
        cap = fallback * 1.5 + 2  # 容忍模型汇总略高于逐条累加（价格项口径等小差异）
        sane = [v for v in vals if v <= cap]
        return max(sane) if sane else fallback
    return max(vals)


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
        self.bid_security_chain = None

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
            self.bid_security_parser = JsonOutputParser()

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
        self.bid_security_chain = None

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
            self.bid_security_parser = JsonOutputParser()

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
        self.bid_security_chain = None

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
            self.bid_security_parser = JsonOutputParser()

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
    """请求频率限制器，防止API调用过于频繁。

    线程安全：多线程并发分析时会被多个worker同时调用，计数/更新需在锁内保证原子，
    否则多个线程可能同时通过检查、突破每小时上限。sleep 放在锁外，避免并发线程串行排队。
    """
    def __init__(self, max_requests_per_hour=40, min_interval_seconds=90, burst_allowance=5):
        self.max_requests_per_hour = max_requests_per_hour
        self.min_interval_seconds = min_interval_seconds
        self.burst_allowance = burst_allowance

        # 记录请求时间的队列，用于计算每小时请求数
        self.request_times = deque()

        # 最后一次请求时间，用于计算请求间隔
        self.last_request_time = 0

        # 保护 request_times / last_request_time 的并发访问
        self._lock = threading.Lock()

    def wait_for_rate_limit(self):
        """等待直到可以发送请求（线程安全）。"""
        # 循环直到本线程拿到一个合法的发送额度：每次在锁内判断需要等待多久，
        # 到锁外 sleep，再回到锁内复核，避免 sleep 期间其他线程改变状态导致超限。
        while True:
            with self._lock:
                current_time = time.time()

                # 移除一小时前的请求记录
                while self.request_times and current_time - self.request_times[0] > 3600:
                    self.request_times.popleft()

                wait_time = 0.0
                # 检查每小时请求数是否超过限制
                if len(self.request_times) >= self.max_requests_per_hour:
                    wait_time = max(wait_time, 3600 - (current_time - self.request_times[0]))
                    log.info(f"请求频率限制：每小时请求数已达上限({self.max_requests_per_hour})，需要等待 {wait_time:.1f} 秒")

                # 检查请求间隔是否满足最小间隔
                if current_time - self.last_request_time < self.min_interval_seconds:
                    interval_wait = self.min_interval_seconds - (current_time - self.last_request_time)
                    if interval_wait > wait_time:
                        wait_time = interval_wait
                        log.info(f"请求频率限制：请求间隔过小，需要等待 {wait_time:.1f} 秒")

                if wait_time <= 0:
                    # 额度可用：登记本次请求时间后返回
                    now = time.time()
                    self.request_times.append(now)
                    self.last_request_time = now
                    return

            # 锁外等待，让出机会给其他线程；醒来后回到循环顶部复核
            time.sleep(wait_time)

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

        # 加载投标保证金语义判断链（如果配置了）
        bid_security_prompt_path = AI_CONFIG.get("bid_security_prompt_path")
        if bid_security_prompt_path and os.path.exists(bid_security_prompt_path):
            bid_security_template = load_prompt_template(bid_security_prompt_path)
            bid_security_prompt = PromptTemplate(
                input_variables=["content"],
                template=bid_security_template + "\n\n请严格按照上述格式输出结果，不要添加任何额外内容。"
            )
            self.current_service.bid_security_chain = bid_security_prompt | self.current_service.llm | self.current_service.bid_security_parser
        else:
            self.current_service.bid_security_chain = None
            log.warning("投标保证金判断提示词模板未配置或不存在，将回退到关键词过滤")

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

    def check_bid_security_ai(self, evaluation_content, project_name=None):
        """用AI语义理解判断项目是否【要求投标保证金】。

        相比关键词匹配，可正确识别"不需要/免收/不要求投标保证金"等否定表述，
        并区分投标保证金与履约保证金、质量保证金/质保金（后者不拦截）。

        Returns:
            tuple: (need: bool, reason: str)。need=True 表示需要投标保证金。
            判断失败或功能不可用时返回 (False, 原因)，避免误杀项目。
        """
        try:
            from config import AI_CONFIG
            if not AI_CONFIG.get("bid_security_check", {}).get("enable", False):
                return False, "投标保证金语义判断功能已禁用"

            if not hasattr(self, 'current_service') or not self.current_service or \
               not hasattr(self.current_service, 'bid_security_chain') or self.current_service.bid_security_chain is None:
                return False, "投标保证金语义判断链未初始化"

            log.info("开始AI语义判断项目是否要求投标保证金")

            if hasattr(self, 'rate_limiter') and self.rate_limiter:
                self.rate_limiter.wait_for_rate_limit()

            text = (project_name or "") + "\n" + (evaluation_content or "")
            # 投标保证金相关表述通常在文件前部，取前6000字符足够判断
            content = text[:6000] if len(text) > 6000 else text

            max_retries = 3
            retry_count = 0
            result = None
            while retry_count < max_retries:
                try:
                    result = self.current_service.bid_security_chain.invoke({"content": content})
                    break
                except Exception as invoke_error:
                    retry_count += 1
                    error_msg = str(invoke_error)
                    is_retryable = any(k in error_msg.lower() for k in [
                        'timeout', 'timed out', 'connection', 'network', '503', '429'
                    ])
                    if retry_count < max_retries and is_retryable:
                        wait_time = retry_count * 2
                        log.warning(f"投标保证金判断请求失败（可重试），{wait_time}秒后重试（{retry_count}/{max_retries}）：{error_msg[:100]}")
                        time.sleep(wait_time)
                        continue
                    else:
                        log.error(f"投标保证金判断失败（{retry_count}/{max_retries}）：{error_msg}")
                        return False, f"判断失败：{error_msg[:100]}"

            if not result:
                log.warning("投标保证金判断结果为空，默认放行（不拦截）")
                return False, "判断结果为空"

            if isinstance(result, dict):
                need = result.get("need", False)
                reason = result.get("reason", "未提供理由")
            elif isinstance(result, str):
                try:
                    result_dict = json.loads(result)
                    need = result_dict.get("need", False)
                    reason = result_dict.get("reason", "未提供理由")
                except json.JSONDecodeError:
                    # 兜底：字符串里明确出现 true/需要 才算需要，避免误判
                    low = result.lower()
                    need = ('"need": true' in low) or ('need=true' in low)
                    reason = result if len(result) < 200 else result[:200]
            else:
                log.warning(f"投标保证金判断结果格式异常：{type(result)}，默认放行")
                return False, "判断结果格式异常"

            log.info(f"投标保证金语义判断完成：need={need}，理由：{reason}")
            return bool(need), str(reason)

        except Exception as e:
            log.error(f"投标保证金语义判断异常：{str(e)}")
            # 判断异常时默认放行（不拦截），避免误杀
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
                import re

                # 加载公司A类库真实持有的证书名（用于"真实持证豁免"后校验，防批量误杀）
                held_cert_names = []
                try:
                    _db = next(get_db())
                    try:
                        held_cert_names = [c.certificate_name for c in get_class_a_certificates(_db)]
                    finally:
                        _db.close()
                except Exception as _e:
                    log.warning(f"加载A类证书库用于后校验失败（跳过豁免）：{_e}")

                # 【后校验】逐条累加得分（已排除价格类条目） + 真实持证豁免救回 + 修正矛盾条目
                pc_gain, pc_full, conflicts, item_count, rescued = _postcheck_objective_score(
                    comparison_result, held_cert_names
                )
                if rescued:
                    log.info(f"真实持证豁免：救回{len(rescued)}个被误触发排除规则的体系认证条目：{rescued}")
                if conflicts:
                    log.warning(f"检测到{len(conflicts)}个矛盾条目（触发排除规则却判满足），已强制置0：{conflicts}")

                # 客观分总满分：优先取模型汇总行，兼容"总满分：3 + 4 + 5 = 12分"这类算式
                # （旧正则只捕获第一个操作数，会把总满分严重低估，导致丢分被抹平误判推荐）
                total_score = _parse_objective_full_score(comparison_result, fallback=pc_full)

                # 客观分可得分：以逐条累加值为权威，不信任模型自己写的汇总数字
                gain_score = pc_gain
                loss_score = max(total_score - gain_score, 0.0)

                threshold = OBJECTIVE_SCORE_CONFIG.get("loss_score_threshold", 1.0)
                conflict_note = ""
                if rescued:
                    conflict_note += f"\n- 真实持证豁免（公司A类库真实持有对应体系认证，cnca可查，救回为满足）：{('、'.join(rescued))}"
                if conflicts:
                    conflict_note += f"\n- 已修正矛盾条目（触发排除规则却判满足，强制置0）：{('、'.join(conflicts))}"
                if item_count == 0:
                    # 未提取到任何客观分评分项（多为非招标正文/附件），不能因“丢分0≤阈值”误判推荐
                    final_decision = "未判定"
                    comparison_result += f"\n\n【AI最终判断说明】\n- 未提取到任何客观分评分项，无法进行客观分判定\n- 最终判断：未判定（建议人工复核，可能非招标正文）"
                elif total_score <= 0:
                    # 有客观分条目却拿不到总满分（模型漏写汇总行），此时丢分恒为0会误判推荐，
                    # 故标记为未判定交人工，避免假阳性
                    final_decision = "未判定"
                    comparison_result += f"\n\n【AI最终判断说明】\n- 客观分可得分（逐条累加校验）：{gain_score}分\n- 无法确定客观分总满分（模型未给出有效汇总），无法计算丢分\n- 最终判断：未判定（建议人工复核）"
                elif loss_score <= threshold:
                    # 丢分≤阈值，改为"推荐参与"
                    final_decision = "推荐参与"
                    comparison_result += f"\n\n【AI最终判断说明】\n- 客观分可得分（逐条累加校验）：{gain_score}分\n- 丢分：{loss_score}分\n- 阈值：{threshold}分\n- 最终判断：推荐参与{conflict_note}"
                else:
                    # 丢分>阈值，改为"不推荐参与"
                    final_decision = "不推荐参与"
                    comparison_result += f"\n\n【AI最终判断说明】\n- 客观分可得分（逐条累加校验）：{gain_score}分\n- 丢分：{loss_score}分\n- 阈值：{threshold}分\n- 最终判断：不推荐参与{conflict_note}"
            
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

            # 前置过滤：非招标文件 → 不调AI（确定性过滤，省token）
            try:
                from utils.pre_filter import check_non_tender, check_bid_security
                _nt_hit, _nt_reason = check_non_tender(project.project_name, project.file_path)
                if _nt_hit:
                    log.info(f"⏭️ 项目 {tender_id} {_nt_reason}，跳过AI分析并排除")
                    update_project(db, tender_id, {"status": ProjectStatus.EXCLUDED, "error_msg": _nt_reason})
                    return project
                _content = getattr(project, "evaluation_content", None) or project.content
                # 投标保证金：优先AI语义判断（正确区分"不需要投标保证金"及履约/质量保证金）；
                # 未启用或不可用时回退关键词过滤
                if AI_CONFIG.get("bid_security_check", {}).get("enable", False):
                    _bs_hit, _bs_reason = self.check_bid_security_ai(_content, project.project_name)
                else:
                    _bs_hit, _bs_reason = check_bid_security(_content, project.project_name)
                if _bs_hit:
                    log.info(f"⏭️ 项目 {tender_id} {_bs_reason}，中断分析并设为不推荐")
                    update_project(db, tender_id, {
                        "status": ProjectStatus.EXCLUDED, "final_decision": "不推荐", "error_msg": f"需要投标保证金：{_bs_reason}",
                    })
                    return project
            except Exception as _e:
                log.warning(f"前置过滤调用失败，跳过该过滤继续分析：{_e}")

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
