"""政采云：解析已下载的xlsx记录表，去重入库"""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timedelta
from typing import List, Optional

import openpyxl

from config import FILES_DIR, ZCY_CONFIG
from utils.db import ProjectStatus, TenderProject, save_project
from utils.log import log

XLSX_NAME = "文件链接记录.xlsx"


import re

# 政采云文件名常带发布/定标日期，如「（2026.1.28定）招标文件--xxx.doc」
_FILENAME_DATE_RE = re.compile(r"[（(]\s*(\d{4})[.\-/年](\d{1,2})[.\-/月](\d{1,2})")


def _parse_publish_time(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _publish_time_from_filename(file_name: str) -> Optional[datetime]:
    """从政采云文件名中提取真实发布/定标日期（如「（2026.1.28定）...」）。"""
    if not file_name:
        return None
    m = _FILENAME_DATE_RE.search(file_name)
    if not m:
        return None
    try:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return datetime(year, month, day)
    except ValueError:
        return None


def _parse_region_parts(region_text: str) -> tuple:
    """解析「浙江省衢州市江山市」→ (省, 市, 区县描述)。"""
    text = (region_text or "").strip()
    if not text:
        return "浙江省", "未知", "未知"

    province = "浙江省"
    rest = text[3:] if text.startswith("浙江省") else text
    import re
    parts = re.findall(r"[^省市]+[市区县]", rest)
    if len(parts) >= 2:
        return province, parts[0], parts[1]
    if len(parts) == 1:
        return province, parts[0], parts[0]
    if "市" in rest:
        city = rest.split("市", 1)[0] + "市"
        district = rest[len(city) :].strip() or city
        return province, city, district
    return province, "未知", text or "未知"


def _safe_filename(name: str, max_len: int = 80) -> str:
    safe = name
    for ch in ['\\', '/', ':', '*', '?', '"', '<', '>', '|', '\n', '\r', '\t']:
        safe = safe.replace(ch, "_")
    return safe[:max_len] if safe else "unnamed"


def _find_xlsx(output_dir: str) -> str:
    direct = os.path.join(output_dir, XLSX_NAME)
    if os.path.isfile(direct):
        return direct
    import glob
    candidates = glob.glob(os.path.join(output_dir, "*.xlsx"))
    if not candidates:
        raise FileNotFoundError(f"未在 {output_dir} 找到 {XLSX_NAME}")
    chosen = max(candidates, key=os.path.getmtime)
    if len(candidates) > 1:
        log.warning(
            f"目录中存在多个 xlsx（{len(candidates)} 个），未找到标准名「{XLSX_NAME}」，"
            f"按最近修改时间选用: {os.path.basename(chosen)}。若发布时间异常请确认该表是否为最新。"
        )
    return chosen


def _load_xlsx_rows(xlsx_path: str) -> List[dict]:
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        return []

    headers = [str(h).strip() if h is not None else "" for h in rows[0]]
    col_map = {
        "项目编号": "project_code",
        "文件名": "file_name",
        "下载链接": "download_url",
        "下载时间": "download_time",
        "城市/地区": "region",
        "招标类型": "tender_type",
    }
    idx = {name: headers.index(name) for name in col_map if name in headers}
    missing = [k for k in col_map if k not in idx]
    if missing:
        raise ValueError(f"xlsx 缺少列: {missing}，当前表头: {headers}")

    records = []
    for row in rows[1:]:
        if not row or all(cell is None or str(cell).strip() == "" for cell in row):
            continue
        item = {}
        for cn, key in col_map.items():
            i = idx[cn]
            item[key] = row[i] if i < len(row) else None
        records.append(item)
    return records


def ingest_downloaded_files(
    db,
    daily_limit: Optional[int] = None,
    days_before: Optional[int] = None,
    output_dir: Optional[str] = None,
) -> List[TenderProject]:
    """解析三方程序输出目录的xlsx记录表，去重入库。"""
    output_dir = output_dir or ZCY_CONFIG["output_dir"]
    if not os.path.isdir(output_dir):
        raise FileNotFoundError(f"政采云输出目录不存在: {output_dir}")

    xlsx_path = _find_xlsx(output_dir)
    log.info(f"读取政采云记录表: {xlsx_path}")
    records = _load_xlsx_rows(xlsx_path)

    allowed_ext = set(ZCY_CONFIG["supported_extensions"])
    earliest_date = None
    if days_before is not None and days_before > 0:
        earliest_date = datetime.now().date() - timedelta(days=days_before)

    existing_ids = {
        row[0]
        for row in db.query(TenderProject.project_id)
        .filter(TenderProject.project_id.isnot(None))
        .all()
    }

    projects: List[TenderProject] = []
    ingested = 0

    for rec in records:
        if daily_limit is not None and ingested >= daily_limit:
            log.info(f"已达到入库上限 {daily_limit}，停止导入")
            break

        file_name = (rec.get("file_name") or "").strip()
        project_code = (rec.get("project_code") or "").strip()
        if not file_name or not project_code:
            continue

        ext = os.path.splitext(file_name)[1].lower()
        if ext not in allowed_ext:
            continue

        # 发布时间优先取文件名中的真实日期（如「（2026.1.28定）...」），
        # 其次回退到 xlsx 的「下载时间」列（下载时间并非真实发布时间，仅作兜底）。
        publish_time = _publish_time_from_filename(file_name)
        if not publish_time:
            publish_time = _parse_publish_time(rec.get("download_time"))
        if not publish_time:
            log.warning(f"跳过无有效发布时间的记录: {project_code} / {file_name}")
            continue

        if earliest_date and publish_time.date() < earliest_date:
            continue

        src_path = os.path.join(output_dir, project_code, file_name)
        if not os.path.isfile(src_path):
            log.warning(f"文件不存在，跳过: {src_path}")
            continue

        unique_id = f"{project_code}::{file_name}"
        if unique_id in existing_ids:
            log.debug(f"已入库，跳过: {unique_id}")
            continue

        region_full = (rec.get("region") or "").strip()
        province, city, district = _parse_region_parts(region_full)
        site_region = district if district and district != "未知" else city

        dest_name = _safe_filename(f"ZCY_{project_code}_{file_name}")
        if not dest_name.lower().endswith(ext):
            dest_name += ext
        dest_path = os.path.join(FILES_DIR, dest_name)

        if os.path.abspath(src_path) != os.path.abspath(dest_path):
            shutil.copy2(src_path, dest_path)

        download_url = (rec.get("download_url") or "").strip()
        project_data = {
            "project_name": file_name,
            "site_name": f"浙江省政府采购网-{site_region}",
            "publish_time": publish_time,
            "download_url": download_url or f"zcy-local://{project_code}/{file_name}",
            "project_id": unique_id,
            "region": region_full or site_region,
            "file_path": dest_path,
            "file_format": ext.lstrip("."),
            "status": ProjectStatus.DOWNLOADED,
        }

        try:
            saved = save_project(db, project_data)
            projects.append(saved)
            existing_ids.add(unique_id)
            ingested += 1
            log.info(
                f"政采云入库 [{ingested}]: {file_name} | {region_full} | {publish_time.strftime('%Y-%m-%d')}"
            )
        except Exception as exc:
            log.error(f"政采云入库失败 {unique_id}: {exc}")

    log.info(f"政采云xlsx解析完成，本次新入库 {len(projects)} 个标书文件")
    return projects


def run_zcy_external_spider(
    db,
    daily_limit: Optional[int] = None,
    days_before: Optional[int] = None,
) -> List[TenderProject]:
    """
    政采云：解析已下载的xlsx记录表，去重入库。
    """
    output_dir = ZCY_CONFIG["output_dir"]
    log.info("=" * 50)
    log.info("政采云：解析xlsx记录表 + 去重入库模式")
    log.info(f"输出目录: {output_dir}")
    log.info("=" * 50)

    return ingest_downloaded_files(
        db,
        daily_limit=daily_limit,
        days_before=days_before,
        output_dir=output_dir,
    )
