"""政采云：exe 下载与系统入库两条独立链路

一、exe 下载（run_zcy_download_pipeline，由 run_zcy_download.py 每日 19:00 定时跑）：
    gui_app.exe 获取当日项目编号 → 复制到剪贴板 → 政采云.exe 粘贴批量下载
    → 生成「下载记录.csv」+ 按编号建子文件夹 → 合并进「total_下载记录.csv」

二、系统入库（run_zcy_external_spider，供流程执行/定时爬取调用）：
    只读「total_下载记录.csv」，按数量/时间范围去重入库，完全不触发 exe。
"""

from __future__ import annotations

import csv
import glob
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from config import FILES_DIR, ZCY_CONFIG, ZCY_DISTRICT_MAP
from utils.db import ProjectStatus, TenderProject, save_project
from utils.log import log

try:
    import win32con
    import win32gui
except ImportError:  # pragma: no cover
    win32con = None
    win32gui = None

try:
    import pyperclip
except ImportError:  # pragma: no cover
    pyperclip = None


COMPLETION_STABLE_ROUNDS = 3  # CSV 大小连续 N 轮不变判定下载完成


# ============================================================
# 一、GUI 自动化底座（win32）
# ============================================================
def _require_win32() -> None:
    if not win32gui or not win32con:
        raise RuntimeError("需要 pywin32 才能进行 GUI 自动化，请安装: pip install pywin32")


def _find_window(partial_title: str) -> Optional[int]:
    """按标题子串查找可见窗口，返回 hwnd。找不到时打印所有可见窗口便于校正标题。"""
    if not win32gui:
        return None
    found: List[int] = []

    def _cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and partial_title in (win32gui.GetWindowText(hwnd) or ""):
            found.append(hwnd)
        return True

    win32gui.EnumWindows(_cb, None)
    if found:
        return found[0]

    log.debug(f"未找到标题含「{partial_title}」的窗口，列出所有可见窗口:")

    def _list_cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title:
                log.debug(f"  窗口: {title} (hwnd={hwnd})")
        return True

    win32gui.EnumWindows(_list_cb, None)
    return None


def _get_control_text(hwnd: int) -> str:
    """读取控件文字。Tkinter 控件 GetWindowText 常为空，回退 WM_GETTEXT。"""
    if not win32gui:
        return ""
    try:
        text = win32gui.GetWindowText(hwnd) or ""
        if text:
            return text
    except Exception:
        pass
    try:
        length = win32gui.SendMessage(hwnd, 0x000E, 0, 0)  # WM_GETTEXTLENGTH
        if length and int(length) > 0:
            buf = "\x00" * (int(length) + 1)
            win32gui.SendMessage(hwnd, 0x000D, int(length) + 1, buf)  # WM_GETTEXT
            return buf.rstrip("\x00")
    except Exception:
        pass
    return ""


def _enumerate_all_children(parent_hwnd: int) -> List[int]:
    """递归枚举所有子孙控件。"""
    result: List[int] = []
    if not win32gui:
        return result

    def _collect(hwnd: int):
        result.append(hwnd)
        try:
            win32gui.EnumChildWindows(hwnd, lambda h, _: _collect(h), None)
        except Exception:
            pass

    try:
        win32gui.EnumChildWindows(parent_hwnd, lambda h, _: _collect(h), None)
    except Exception:
        pass
    return result


def _find_child_by_text(parent_hwnd: int, text: str, partial: bool = False) -> Optional[int]:
    if not win32gui:
        return None
    for hwnd in _enumerate_all_children(parent_hwnd):
        label = _get_control_text(hwnd)
        if partial and text in label:
            return hwnd
        if not partial and label == text:
            return hwnd
    return None


def _get_control_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    if not win32gui:
        return None
    try:
        return win32gui.GetWindowRect(hwnd)
    except Exception:
        return None


def _click_button(hwnd: int) -> None:
    """点击按钮：优先 BM_CLICK，失败用坐标模拟。"""
    if not win32gui:
        return
    try:
        win32gui.SendMessage(hwnd, win32con.BM_CLICK, 0, 0)
        return
    except Exception as e:
        log.debug(f"BM_CLICK 失败，尝试坐标点击: {e}")
    rect = _get_control_rect(hwnd)
    if rect:
        cx, cy = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
        try:
            import win32api

            win32api.SetCursorPos((cx, cy))
            time.sleep(0.1)
            win32api.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
            win32api.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP
        except Exception as e2:
            log.warning(f"坐标点击也失败: {e2}")


def _find_button(hwnd: int, text: str) -> Optional[int]:
    btn = _find_child_by_text(hwnd, text)
    if not btn:
        btn = _find_child_by_text(hwnd, text, partial=True)
    return btn


def _click_button_by_text(hwnd: int, text: str) -> bool:
    btn = _find_button(hwnd, text)
    if not btn:
        log.warning(f"未找到按钮「{text}」")
        return False
    log.info(f"点击按钮「{text}」(hwnd={btn})")
    _click_button(btn)
    return True


def _normalize_window(hwnd: int, ref_size: Optional[Tuple[int, int]]) -> Tuple[int, int]:
    """把窗口调整到参考尺寸并置前，返回窗口左上角屏幕坐标 (left, top)。

    Tkinter 按钮无独立句柄/文字，只能靠坐标点击；先固定窗口尺寸，相对坐标才稳定。
    """
    if not win32gui:
        return (0, 0)
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.3)
        rect = win32gui.GetWindowRect(hwnd)
        if ref_size:
            win32gui.MoveWindow(hwnd, rect[0], rect[1], ref_size[0], ref_size[1], True)
            time.sleep(0.3)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.5)
    except Exception as e:
        log.warning(f"规范化窗口失败（继续按现状点击）: {e}")
    rect = win32gui.GetWindowRect(hwnd)
    return (rect[0], rect[1])


def _click_at_rel(hwnd: int, rel_xy: Tuple[int, int], ref_size: Optional[Tuple[int, int]]) -> None:
    """在窗口相对坐标 rel_xy 处点击（rel_xy 为相对窗口左上角的中心点）。"""
    import win32api

    left, top = _normalize_window(hwnd, ref_size)
    cx, cy = left + rel_xy[0], top + rel_xy[1]
    win32api.SetCursorPos((cx, cy))
    time.sleep(0.3)
    win32api.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
    win32api.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP
    log.debug(f"坐标点击 rel={rel_xy} -> screen=({cx},{cy})")
    time.sleep(0.3)


def _send_ctrl_key(vk: int) -> None:
    """发送 Ctrl+<vk> 组合键。"""
    import win32api

    win32api.keybd_event(0x11, 0, 0, 0)       # Ctrl down
    win32api.keybd_event(vk, 0, 0, 0)
    win32api.keybd_event(vk, 0, 0x0002, 0)    # key up
    win32api.keybd_event(0x11, 0, 0x0002, 0)  # Ctrl up
    time.sleep(0.1)


def _fill_field_at_rel(
    hwnd: int, rel_xy: Tuple[int, int], text: str, ref_size: Optional[Tuple[int, int]]
) -> None:
    """点击相对坐标处的输入框 → 全选清空 → 剪贴板粘贴 text。"""
    if pyperclip is None:
        raise RuntimeError("需要 pyperclip 才能粘贴文本，请安装: pip install pyperclip")
    _click_at_rel(hwnd, rel_xy, ref_size)
    time.sleep(0.2)
    _send_ctrl_key(0x41)  # Ctrl+A 全选
    pyperclip.copy(text)
    time.sleep(0.2)
    _send_ctrl_key(0x56)  # Ctrl+V 粘贴
    time.sleep(0.3)


def _set_edit_text(hwnd: int, text: str, use_clipboard: bool = False) -> None:
    """向输入框写文本。大文本（编号列表）优先用剪贴板 + Ctrl+V。"""
    if not win32gui:
        return
    if use_clipboard and pyperclip is not None:
        try:
            pyperclip.copy(text)
            time.sleep(0.2)
            win32gui.SetForegroundWindow(hwnd)
            win32gui.SendMessage(hwnd, win32con.WM_SETTEXT, 0, "")  # 先清空
            import win32api

            # Ctrl+A 全选后 Ctrl+V 粘贴
            for vk in (0x41,):  # 'A'
                win32api.keybd_event(0x11, 0, 0, 0)  # Ctrl down
                win32api.keybd_event(vk, 0, 0, 0)
                win32api.keybd_event(vk, 0, 0x0002, 0)
                win32api.keybd_event(0x11, 0, 0x0002, 0)
            time.sleep(0.1)
            win32api.keybd_event(0x11, 0, 0, 0)  # Ctrl down
            win32api.keybd_event(0x56, 0, 0, 0)  # 'V'
            win32api.keybd_event(0x56, 0, 0x0002, 0)
            win32api.keybd_event(0x11, 0, 0x0002, 0)
            time.sleep(0.2)
            return
        except Exception as e:
            log.debug(f"剪贴板粘贴失败，回退 WM_SETTEXT: {e}")
    try:
        win32gui.SendMessage(hwnd, win32con.WM_SETTEXT, 0, str(text))
    except Exception as e:
        log.warning(f"写输入框失败: {e}")


def _is_exe_process_running(exe_path: str) -> bool:
    """检查 exe 进程是否已在运行（防止重复启动堆叠）。"""
    exe_name = os.path.basename(exe_path)
    try:
        import psutil

        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info.get("name") == exe_name:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False
    except Exception:
        try:
            import subprocess

            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {exe_name}"],
                capture_output=True, text=True, timeout=10,
            )
            return exe_name.lower() in (result.stdout or "").lower()
        except Exception as exc:
            log.debug(f"检查进程失败（忽略）: {exc}")
            return False


def _ensure_exe_running(exe_path: str, window_title: str, wait_seconds: int = 30) -> int:
    """复用优先 + 防堆叠：已有窗口直接复用；进程在跑但窗口未就绪则等待；否则启动。"""
    _require_win32()
    hwnd = _find_window(window_title)
    if hwnd:
        log.info(f"检测到窗口「{window_title}」已存在，复用现有实例")
        return hwnd

    if not os.path.isfile(exe_path):
        raise FileNotFoundError(f"政采云程序不存在: {exe_path}，请确认已放入项目根目录")

    if _is_exe_process_running(exe_path):
        log.info(f"进程 {os.path.basename(exe_path)} 已在运行但窗口未就绪，等待窗口出现（不重复启动）")
    else:
        import subprocess

        subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path))
        log.info(f"已启动: {exe_path}")

    for _ in range(wait_seconds):
        time.sleep(1)
        hwnd = _find_window(window_title)
        if hwnd:
            return hwnd

    raise RuntimeError(f"启动后 {wait_seconds}s 内未找到窗口（标题含「{window_title}」）")


def _bring_to_front(hwnd: int) -> None:
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(1)
    except Exception as e:
        log.warning(f"设置窗口前景失败: {e}")


# ============================================================
# 二、EXE A：获取当日项目编号 → 剪贴板
# ============================================================
def fetch_project_codes() -> str:
    """驱动 gui_app.exe 获取当日项目编号并复制到剪贴板，返回编号字符串。"""
    _require_win32()
    if pyperclip is None:
        raise RuntimeError("需要 pyperclip 才能读取剪贴板，请安装: pip install pyperclip")

    cfg = ZCY_CONFIG["code_exe"]
    ref_size = cfg.get("ref_size")
    hwnd = _ensure_exe_running(cfg["path"], cfg["window_title"])

    # 清空剪贴板哨兵，便于判断复制是否真的写入了新内容
    sentinel = "__zcy_no_codes__"
    try:
        pyperclip.copy(sentinel)
    except Exception:
        pass

    # 坐标点击「获取当日项目编号」
    _click_at_rel(hwnd, cfg["fetch_button_xy"], ref_size)
    log.info("已点击获取当日项目编号，等待抓取完成...")

    # 抓取需要时间：轮询——每隔几秒点一次「复制全部项目编号」，直到剪贴板拿到非哨兵内容
    deadline = time.time() + ZCY_CONFIG["fetch_timeout"]
    codes = ""
    while time.time() < deadline:
        time.sleep(5)
        _click_at_rel(hwnd, cfg["copy_button_xy"], ref_size)
        time.sleep(1)
        try:
            clip = pyperclip.paste() or ""
        except Exception as e:
            log.debug(f"读剪贴板失败: {e}")
            continue
        if clip and clip != sentinel and clip.strip():
            codes = clip.strip()
            break

    if not codes:
        raise TimeoutError(f"{ZCY_CONFIG['fetch_timeout']}s 内未从剪贴板获取到项目编号")

    n = len([c for c in codes.replace(",", "\n").splitlines() if c.strip()])
    log.info(f"已获取当日项目编号 {n} 个")
    return codes


# ============================================================
# 三、EXE B：粘贴编号 → 批量下载 → 等待完成
# ============================================================
def _snapshot_csv_state(save_dir: str) -> Dict:
    """记录 下载记录.csv 与子文件夹的快照，用于判断触发后是否有新活动。"""
    csv_path = os.path.join(save_dir, ZCY_CONFIG["csv_name"])
    mtime = size = 0.0
    if os.path.isfile(csv_path):
        try:
            mtime = os.path.getmtime(csv_path)
            size = os.path.getsize(csv_path)
        except OSError:
            pass
    try:
        subdirs = len([d for d in os.listdir(save_dir) if os.path.isdir(os.path.join(save_dir, d))])
    except OSError:
        subdirs = 0
    return {"csv_path": csv_path, "mtime": mtime, "size": size, "subdirs": subdirs}


def trigger_batch_download(codes: str) -> None:
    """驱动 政采云.exe：填保存目录、粘贴编号、开始批量处理，并等待下载完成。"""
    _require_win32()
    cfg = ZCY_CONFIG["download_exe"]
    ref_size = cfg.get("ref_size")
    save_dir = ZCY_CONFIG["save_dir"]
    os.makedirs(save_dir, exist_ok=True)

    hwnd = _ensure_exe_running(cfg["path"], cfg["window_title"])

    # 填「保存目录」
    _fill_field_at_rel(hwnd, cfg["save_dir_xy"], os.path.abspath(save_dir), ref_size)
    log.info(f"已填入保存目录: {save_dir}")

    # 粘贴「项目编号」
    _fill_field_at_rel(hwnd, cfg["codes_xy"], codes, ref_size)
    log.info("已粘贴项目编号到下载工具")

    before = _snapshot_csv_state(save_dir)
    # 点击「开始批量处理」
    _click_at_rel(hwnd, cfg["start_button_xy"], ref_size)
    log.info("已点击开始批量处理，等待下载完成...")

    wait_for_download_complete(save_dir, before_state=before)


def wait_for_download_complete(save_dir: str, before_state: Optional[Dict] = None) -> None:
    """轮询 下载记录.csv：出现新活动后等待其大小稳定，判定下载完成。

    无活动快速失败：超过 no_activity_timeout 仍无新活动 → 判定 exe 未开始执行，抛错降级，
    不空转到 download_timeout。
    """
    timeout = ZCY_CONFIG["download_timeout"]
    no_activity_timeout = ZCY_CONFIG["no_activity_timeout"]
    csv_path = os.path.join(save_dir, ZCY_CONFIG["csv_name"])
    deadline = time.time() + timeout
    start = time.time()
    grace = 15
    last_size = -1
    stable = 0

    while time.time() < deadline:
        cur = _snapshot_csv_state(save_dir)
        # 是否有新活动：CSV 被更新/新建，或子文件夹增加
        has_activity = True
        if before_state:
            same = (
                cur["mtime"] == before_state["mtime"]
                and cur["size"] == before_state["size"]
                and cur["subdirs"] <= before_state["subdirs"]
            )
            has_activity = not same

        if not has_activity:
            elapsed = time.time() - start
            if elapsed < grace:
                time.sleep(5)
                continue
            if elapsed >= no_activity_timeout:
                raise TimeoutError(
                    f"触发后 {int(elapsed)}s 内下载记录无任何新活动，判定政采云下载工具未开始执行"
                    f"（检查编号是否粘贴成功/按钮是否点到/登录是否正常）"
                )
            log.warning(f"触发后 {int(elapsed)}s 内无新活动，继续等待（上限 {no_activity_timeout}s）")
            time.sleep(10)
            continue

        # 有活动：等待 CSV 大小稳定
        if os.path.isfile(csv_path):
            try:
                size = os.path.getsize(csv_path)
            except OSError:
                size = -1
            if size == last_size and size > 0:
                stable += 1
                if stable >= COMPLETION_STABLE_ROUNDS:
                    log.info(f"政采云下载完成（记录表稳定）: {csv_path}")
                    return
            else:
                stable = 0
                last_size = size
        time.sleep(10)

    log.warning(f"等待政采云下载达到上限 {timeout}s，按当前已下载内容继续解析")


# ============================================================
# 四、CSV 累积合并 + 解析入库
# ============================================================
CSV_HEADERS = ["项目编号", "文件名", "下载链接", "发布时间", "地区", "招标类型"]
_COL_MAP = {
    "项目编号": "project_code",
    "文件名": "file_name",
    "下载链接": "download_url",
    "发布时间": "publish_time",
    "地区": "district_code",
    "招标类型": "tender_type",
}


def _read_csv_rows(csv_path: str) -> List[dict]:
    """读 CSV（兼容 UTF-8 BOM），按表头映射为 dict 列表。"""
    if not os.path.isfile(csv_path):
        return []
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        rows = list(reader)
    if not rows:
        return []
    headers = [h.strip() for h in rows[0]]
    idx = {name: headers.index(name) for name in _COL_MAP if name in headers}
    missing = [k for k in _COL_MAP if k not in idx]
    if missing:
        raise ValueError(f"CSV 缺少列: {missing}，当前表头: {headers}")
    records = []
    for row in rows[1:]:
        if not row or all((c or "").strip() == "" for c in row):
            continue
        item = {key: (row[idx[cn]] if idx[cn] < len(row) else "") for cn, key in _COL_MAP.items()}
        records.append(item)
    return records


def merge_into_total(save_dir: str) -> str:
    """把本次 下载记录.csv 合并进 total_下载记录.csv（按 项目编号+文件名 去重刷新）。

    返回 total_下载记录.csv 路径。新行覆盖同键旧行，保留全部历史。
    """
    csv_path = os.path.join(save_dir, ZCY_CONFIG["csv_name"])
    total_path = os.path.join(save_dir, ZCY_CONFIG["total_csv_name"])

    def _key(r: List[str]) -> Tuple[str, str]:
        code = (r[0] if len(r) > 0 else "").strip()
        name = (r[1] if len(r) > 1 else "").strip()
        return code, name

    merged: Dict[Tuple[str, str], List[str]] = {}
    order: List[Tuple[str, str]] = []

    def _absorb(path: str):
        if not os.path.isfile(path):
            return
        with open(path, encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.reader(fh))
        for row in rows[1:] if rows else []:
            if not row or all((c or "").strip() == "" for c in row):
                continue
            k = _key(row)
            if not k[0] and not k[1]:
                continue
            if k not in merged:
                order.append(k)
            merged[k] = row  # 新行覆盖旧行（刷新）

    _absorb(total_path)  # 先历史
    _absorb(csv_path)    # 再本次（覆盖同键）

    with open(total_path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_HEADERS)
        for k in order:
            writer.writerow(merged[k])

    log.info(f"已累积合并记录表: {total_path}（共 {len(order)} 条历史记录）")
    return total_path


def _region_from_code(district_code: str) -> str:
    """区划码前4位 → 城市名；无匹配返回原码。"""
    code = (district_code or "").strip()
    if not code:
        return "未知"
    return ZCY_DISTRICT_MAP.get(code[:4], code)


def _parse_publish_time(value, fallback_path: Optional[str] = None) -> Optional[datetime]:
    """解析发布时间；CSV 常为空，回退文件 mtime，再回退当日。"""
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    if fallback_path and os.path.isfile(fallback_path):
        try:
            return datetime.fromtimestamp(os.path.getmtime(fallback_path))
        except OSError:
            pass
    return datetime.now()


def ingest_downloaded_files(
    db,
    daily_limit: Optional[int] = None,
    days_before: Optional[int] = None,
    save_dir: Optional[str] = None,
) -> List[TenderProject]:
    """解析 total_下载记录.csv，按数量/时间范围将 doc/docx/pdf 标书去重入库。

    仅读取记录表，不触发任何 exe（exe 下载由独立脚本 run_zcy_download.py 每日定时执行）。
    文件已在 save_dir 下，无需拷贝。
    """
    save_dir = save_dir or ZCY_CONFIG["save_dir"]
    if not os.path.isdir(save_dir):
        raise FileNotFoundError(f"政采云保存目录不存在: {save_dir}")

    total_path = os.path.join(save_dir, ZCY_CONFIG["total_csv_name"])
    records = _read_csv_rows(total_path)
    log.info(f"读取累积记录表: {total_path}，共 {len(records)} 条")

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

        src_path = os.path.join(save_dir, project_code, file_name)
        if not os.path.isfile(src_path):
            log.warning(f"文件不存在，跳过: {src_path}")
            continue

        publish_time = _parse_publish_time(rec.get("publish_time"), fallback_path=src_path)
        if earliest_date and publish_time.date() < earliest_date:
            continue

        unique_id = f"{project_code}::{file_name}"
        if unique_id in existing_ids:
            log.debug(f"已入库，跳过: {unique_id}")
            continue

        district_code = (rec.get("district_code") or "").strip()
        region = _region_from_code(district_code)

        download_url = (rec.get("download_url") or "").strip()
        project_data = {
            "project_name": file_name,
            "site_name": f"浙江省政府采购网-{region}",
            "publish_time": publish_time,
            "download_url": download_url or f"zcy-local://{project_code}/{file_name}",
            "project_id": unique_id,
            "region": region,
            "file_path": src_path,  # 已在 tender_files/zcy 下，直接指向，无需拷贝
            "file_format": ext.lstrip("."),
            "status": ProjectStatus.DOWNLOADED,
        }

        try:
            saved = save_project(db, project_data)
            projects.append(saved)
            existing_ids.add(unique_id)
            ingested += 1
            log.info(
                f"政采云入库 [{ingested}]: {file_name} | {region} | {publish_time.strftime('%Y-%m-%d')}"
            )
        except Exception as exc:
            log.error(f"政采云入库失败 {unique_id}: {exc}")

    log.info(f"政采云解析完成，本次新入库 {len(projects)} 个标书文件")
    return projects


# ============================================================
# 五、两个入口（彻底解耦）
#   A) run_zcy_download_pipeline() —— exe 下载，独立脚本每日 19:00 跑，不入库
#   B) run_zcy_external_spider()   —— 系统爬取，只读 total_下载记录.csv 入库，不碰 exe
# ============================================================
def run_zcy_download_pipeline() -> str:
    """【exe 下载入口，供 run_zcy_download.py 每日定时调用】
    获取当日编号(A) → 批量下载(B) → 合并进 total_下载记录.csv。不做入库。

    返回 total_下载记录.csv 路径。
    """
    save_dir = ZCY_CONFIG["save_dir"]
    os.makedirs(save_dir, exist_ok=True)
    log.info("=" * 50)
    log.info("政采云 exe 下载流水线：获取编号(A) → 批量下载(B) → 合并累积表")
    log.info(f"保存目录: {save_dir}")
    log.info("=" * 50)

    codes = fetch_project_codes()
    if not codes.strip():
        log.warning("未获取到当日项目编号，跳过下载")
    else:
        trigger_batch_download(codes)

    total_path = merge_into_total(save_dir)
    log.info("政采云 exe 下载流水线完成")
    return total_path


def run_zcy_external_spider(
    db,
    daily_limit: Optional[int] = None,
    days_before: Optional[int] = None,
    skip_gui: Optional[bool] = None,  # 已废弃，保留仅为向后兼容签名
) -> List[TenderProject]:
    """【系统入库入口，供流程执行/定时爬取调用】
    只读 total_下载记录.csv，按 daily_limit（数量）+ days_before（时间范围）去重入库。
    完全不触发 exe —— exe 下载由 run_zcy_download_pipeline() 独立每日定时执行。
    """
    save_dir = ZCY_CONFIG["save_dir"]
    log.info("=" * 50)
    log.info("政采云：读取累积记录表入库（不触发 exe）")
    log.info(f"保存目录: {save_dir} | 数量上限: {daily_limit} | 时间范围: {days_before} 天内")
    log.info("=" * 50)

    return ingest_downloaded_files(
        db, daily_limit=daily_limit, days_before=days_before, save_dir=save_dir
    )
