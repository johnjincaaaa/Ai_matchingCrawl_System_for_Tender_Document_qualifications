# -*- coding: utf-8 -*-
"""进AI前的前置过滤：确定性判断，不调用AI，节省时间与token。

两类过滤：
1. 非招标文件（中标结果/更正/答疑/终止/合同/验收公告、图纸/工程量清单/报名资料等）→ 跳过分析
2. 需要投标保证金的项目 → 中断分析、直接设为不推荐

原则（防误杀真招标）：
- 结果/流程类标记只匹配标题（project_name），不扫正文全文
- 附件类标记匹配文件名 + 标题
- 保证金检测带否定词豁免（"免收/不收取保证金"等）
"""

from config import PRE_FILTER_CONFIG


def check_non_tender(project_name=None, file_path=None):
    """判断是否为非招标文件。返回 (是否命中: bool, 命中原因: str)。"""
    cfg = PRE_FILTER_CONFIG.get("non_tender_filter", {})
    if not cfg.get("enable", False):
        return False, ""

    title = (project_name or "")
    fname = (file_path or "")

    # 结果/流程类：只在标题里找
    for kw in cfg.get("title_keywords", []):
        if kw in title:
            return True, f"非招标文件（标题含“{kw}”）"

    # 附件类：文件名或标题里找
    for kw in cfg.get("filename_keywords", []):
        if kw in fname or kw in title:
            return True, f"非招标文件（含“{kw}”）"

    return False, ""


def check_bid_security(content=None, project_name=None):
    """判断项目是否需要【投标】保证金。返回 (是否需要: bool, 原因: str)。

    仅投标保证金拦截；履约保证金、质量保证金/质保金等不受影响。
    逻辑：
    1. 否定表述（免收/不收取投标保证金）优先豁免；
    2. 命中 strong_keywords（投标保证金等）→ 直接判定需要；
    3. 泛化关键词“保证金”：逐处回看前缀，若被 exempt_prefixes（履约/质量等）
       修饰则跳过，否则视为投标保证金。
    """
    cfg = PRE_FILTER_CONFIG.get("bid_security_filter", {})
    if not cfg.get("enable", False):
        return False, ""

    text = (project_name or "") + "\n" + (content or "")

    # 否定豁免优先
    for neg in cfg.get("negation_keywords", []):
        if neg in text:
            return False, ""

    # 明确的投标保证金关键词 → 直接命中
    for kw in cfg.get("strong_keywords", []):
        if kw in text:
            return True, f"项目需要投标保证金（含“{kw}”）"

    # 泛化“保证金”：逐处检查前缀，排除履约/质量等非投标类
    generic = cfg.get("generic_keyword", "")
    if generic:
        exempt_prefixes = cfg.get("exempt_prefixes", [])
        window = cfg.get("prefix_window", 6)
        start = 0
        while True:
            idx = text.find(generic, start)
            if idx == -1:
                break
            prefix = text[max(0, idx - window):idx]
            if not any(p in prefix for p in exempt_prefixes):
                # 未被豁免前缀修饰 → 视为投标保证金
                return True, f"项目需要投标保证金（含“{generic}”）"
            start = idx + len(generic)

    return False, ""

