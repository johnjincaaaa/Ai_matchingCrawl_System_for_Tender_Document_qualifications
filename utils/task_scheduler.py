#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时任务管理模块（基于Windows任务计划程序）
提供创建、查询、启用、禁用、删除定时任务的功能
"""

import subprocess
import json
import os
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from utils.log import log


class WindowsTaskScheduler:
    """Windows任务计划程序管理器"""
    
    TASK_NAME_PREFIX = "TenderSystem_AutoRun_"
    TASK_CONFIG_FILE = "task_schedules.json"
    
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_file = os.path.join(self.base_dir, self.TASK_CONFIG_FILE)
        self.python_exe = self._find_python_exe()
        self.script_path = os.path.join(self.base_dir, "auto_run_full_process.py")
        self._ensure_config_file()
    
    def _find_python_exe(self) -> str:
        """查找Python可执行文件路径"""
        try:
            # 尝试使用当前Python解释器
            import sys
            python_exe = sys.executable
            if os.path.exists(python_exe):
                return python_exe
        except:
            pass
        
        # 尝试常见路径
        common_paths = [
            r"C:\Python312\python.exe",
            r"C:\Python311\python.exe",
            r"C:\Python310\python.exe",
            r"C:\Program Files\Python312\python.exe",
            r"C:\Program Files\Python311\python.exe",
            r"C:\Program Files\Python310\python.exe",
            "python.exe",  # 如果在PATH中
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        
        # 如果都找不到，尝试通过命令查找
        try:
            result = subprocess.run(
                ["where", "python.exe"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split('\n')[0]
        except:
            pass
        
        return "python.exe"  # 默认值，假设在PATH中
    
    def _ensure_config_file(self):
        """确保配置文件存在"""
        if not os.path.exists(self.config_file):
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
    
    def _load_config(self) -> List[Dict]:
        """加载任务配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            log.error(f"加载任务配置失败: {e}")
        return []
    
    def _save_config(self, config: List[Dict]):
        """保存任务配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error(f"保存任务配置失败: {e}")
    
    def _run_schtasks(self, args: List[str]) -> Tuple[bool, str]:
        """执行schtasks命令"""
        try:
            cmd = ["schtasks"] + args
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                encoding='gbk'  # Windows中文环境使用GBK编码
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "命令执行超时"
        except Exception as e:
            return False, str(e)
    
    def create_task(self, task_id: str, schedule_time: str, daily_limit: int = 300, 
                   days_before: int = None, enabled: bool = True, enabled_platforms=None) -> Tuple[bool, str]:
        """
        创建定时任务
        
        Args:
            task_id: 任务ID（唯一标识）
            schedule_time: 执行时间，格式 "HH:MM" (24小时制)
            daily_limit: 每日爬取数量限制，默认300
            days_before: 时间间隔，爬取指定天数之前的文件（None或0表示只爬取当日文件）
            enabled: 是否启用
        
        Returns:
            (成功标志, 消息)
        """
        task_name = f"{self.TASK_NAME_PREFIX}{task_id}"
        
        # 解析时间
        try:
            hour, minute = map(int, schedule_time.split(':'))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                return False, "时间格式错误，请使用 HH:MM 格式（24小时制）"
        except:
            return False, "时间格式错误，请使用 HH:MM 格式（24小时制）"
        
        # 构建命令参数
        # 说明：
        # Windows 计划任务 schtasks 的 /TR 参数有 261 字符限制。
        # 直接拼接 `cmd.exe /c "cd ... && python ... --args"` 很容易超限，
        # 因此这里改为生成一个短的 .cmd 包装脚本，然后 /TR 只指向这个脚本。
        tasks_dir = os.path.join(self.base_dir, "tasks")
        os.makedirs(tasks_dir, exist_ok=True)

        wrapper_cmd = os.path.join(tasks_dir, f"run_{task_id}.cmd")
        days_before_value = days_before if days_before is not None else 0
        days_before_arg = f" --days-before {days_before_value}" if days_before_value > 0 else ""
        
        # 平台参数
        platforms_arg = ""
        if enabled_platforms:
            platforms_str = ",".join(enabled_platforms)
            platforms_arg = f" --enabled-platforms {platforms_str}"

        try:
            with open(wrapper_cmd, "w", encoding="utf-8") as f:
                f.write("@echo off\n")
                f.write(f'cd /d "{self.base_dir}"\n')
                f.write(f'"{self.python_exe}" "{self.script_path}" --daily-limit {daily_limit}{days_before_arg}{platforms_arg}\n')
        except Exception as e:
            return False, f"创建任务执行脚本失败: {e}"
        
        # 构建schtasks命令
        # 使用 /F 强制创建（如果已存在则覆盖）
        # 注意：schtasks不支持/WD参数，需要使用cmd.exe来设置工作目录
        # 使用cmd.exe /c来执行命令，并在其中切换工作目录
        # 格式：cmd.exe /c "cd /d 工作目录 && python 脚本 参数"
        # /TR 用最短形式，避免 261 字符限制
        python_cmd = f'cmd.exe /c ""{wrapper_cmd}""'
        cmd_args = [
            "/Create",
            "/TN", task_name,
            "/TR", python_cmd,
            "/SC", "DAILY",
            "/ST", schedule_time,
            "/F"  # 强制创建
        ]
        
        if not enabled:
            cmd_args.append("/DISABLE")
        
        success, output = self._run_schtasks(cmd_args)
        
        if success:
            # 保存配置
            config = self._load_config()
            task_config = {
                "task_id": task_id,
                "task_name": task_name,
                "schedule_time": schedule_time,
                "daily_limit": daily_limit,
                "days_before": days_before,
                "enabled": enabled,
                "enabled_platforms": enabled_platforms,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "wrapper_cmd": wrapper_cmd
            }
            
            # 检查是否已存在
            config = [t for t in config if t.get("task_id") != task_id]
            config.append(task_config)
            self._save_config(config)
            
            return True, f"定时任务创建成功：{task_name}"
        else:
            # 常见问题：/TR 参数超长（261字符限制）
            if "TR" in output and "261" in output:
                return False, f"创建定时任务失败：{output}\n\n建议：已自动采用 .cmd 包装脚本以缩短 /TR，但仍超长时请将项目目录移动到更短路径（如 D:\\tender\\）后重试。"
            return False, f"创建定时任务失败：{output}"
    
    def list_tasks(self) -> List[Dict]:
        """列出所有定时任务"""
        config = self._load_config()
        tasks = []
        
        for task_config in config:
            task_name = task_config.get("task_name", "")
            if not task_name:
                continue
            
            # 查询任务状态
            success, output = self._run_schtasks(["/Query", "/TN", task_name, "/FO", "LIST", "/V"])
            
            task_info = {
                "task_id": task_config.get("task_id"),
                "task_name": task_name,
                "schedule_time": task_config.get("schedule_time", ""),
                "daily_limit": task_config.get("daily_limit", 300),
                "days_before": task_config.get("days_before"),
                "created_at": task_config.get("created_at", ""),
                "exists": success,
                "status": "未知"
            }
            
            if success:
                # 解析任务状态
                if "状态:                   就绪" in output or "Status:                 Ready" in output:
                    task_info["status"] = "已启用"
                    task_info["enabled"] = True
                elif "状态:                   禁用" in output or "Status:                 Disabled" in output:
                    task_info["status"] = "已禁用"
                    task_info["enabled"] = False
                else:
                    task_info["status"] = "未知"
            else:
                task_info["status"] = "不存在"
                task_info["enabled"] = False
            
            tasks.append(task_info)
        
        return tasks
    
    def enable_task(self, task_id: str) -> Tuple[bool, str]:
        """启用定时任务"""
        config = self._load_config()
        task_config = next((t for t in config if t.get("task_id") == task_id), None)
        
        if not task_config:
            return False, "任务不存在"
        
        task_name = task_config.get("task_name")
        success, output = self._run_schtasks(["/Change", "/TN", task_name, "/ENABLE"])
        
        if success:
            # 更新配置
            task_config["enabled"] = True
            self._save_config(config)
            return True, f"任务已启用：{task_name}"
        else:
            return False, f"启用任务失败：{output}"
    
    def disable_task(self, task_id: str) -> Tuple[bool, str]:
        """禁用定时任务"""
        config = self._load_config()
        task_config = next((t for t in config if t.get("task_id") == task_id), None)
        
        if not task_config:
            return False, "任务不存在"
        
        task_name = task_config.get("task_name")
        success, output = self._run_schtasks(["/Change", "/TN", task_name, "/DISABLE"])
        
        if success:
            # 更新配置
            task_config["enabled"] = False
            self._save_config(config)
            return True, f"任务已禁用：{task_name}"
        else:
            return False, f"禁用任务失败：{output}"
    
    def delete_task(self, task_id: str) -> Tuple[bool, str]:
        """删除定时任务"""
        config = self._load_config()
        task_config = next((t for t in config if t.get("task_id") == task_id), None)
        
        if not task_config:
            return False, "任务不存在"
        
        task_name = task_config.get("task_name")
        
        # 删除Windows任务
        success, output = self._run_schtasks(["/Delete", "/TN", task_name, "/F"])
        
        # 删除参数文件
        args_file = task_config.get("args_file")
        if args_file and os.path.exists(args_file):
            try:
                os.remove(args_file)
            except:
                pass
        
        # 从配置中移除
        config = [t for t in config if t.get("task_id") != task_id]
        self._save_config(config)
        
        if success:
            return True, f"任务已删除：{task_name}"
        else:
            # 即使Windows任务删除失败，也从配置中移除
            return False, f"删除Windows任务失败：{output}（已从配置中移除）"
    
    def run_task_now(self, task_id: str) -> Tuple[bool, str]:
        """立即运行指定的任务（通过schtasks /Run）"""
        config = self._load_config()
        task_config = next((t for t in config if t.get("task_id") == task_id), None)
        
        if not task_config:
            return False, "任务不存在"
        
        task_name = task_config.get("task_name")
        success, output = self._run_schtasks(["/Run", "/TN", task_name])
        
        if success:
            return True, f"任务已启动：{task_name}，请查看日志了解执行情况"
        else:
            return False, f"启动任务失败：{output}"
    
    def test_task(self, daily_limit: int = 300, days_before: int = None, enabled_platforms=None) -> Tuple[bool, str]:
        """测试执行任务（立即运行一次）"""
        try:
            import sys
            script_path = os.path.join(self.base_dir, "auto_run_full_process.py")
            
            # 修改auto_run_full_process.py以支持命令行参数
            # 这里直接调用函数
            sys.path.insert(0, self.base_dir)
            from auto_run_full_process import run_full_process_cli
            
            # 在后台线程中执行
            import threading
            def run_task():
                try:
                    run_full_process_cli(daily_limit=daily_limit, days_before=days_before, enabled_platforms=enabled_platforms)
                except Exception as e:
                    log.error(f"测试任务执行失败: {e}")
            
            thread = threading.Thread(target=run_task, daemon=True)
            thread.start()
            
            return True, "测试任务已启动，请查看日志了解执行情况"
        except Exception as e:
            return False, f"启动测试任务失败：{str(e)}"
    
    def get_task_details(self, task_id: str) -> Tuple[bool, Dict]:
        """获取任务的详细信息"""
        config = self._load_config()
        task_config = next((t for t in config if t.get("task_id") == task_id), None)
        
        if not task_config:
            return False, {}
        
        task_name = task_config.get("task_name")
        success, output = self._run_schtasks(["/Query", "/TN", task_name, "/FO", "LIST", "/V"])
        
        if success:
            return True, {
                "task_config": task_config,
                "raw_output": output,
                "exists": True
            }
        else:
            return False, {
                "task_config": task_config,
                "raw_output": output,
                "exists": False
            }


if __name__ == "__main__":
    # 测试代码
    scheduler = WindowsTaskScheduler()
    print(f"Python路径: {scheduler.python_exe}")
    print(f"脚本路径: {scheduler.script_path}")
    
    # 测试创建任务
    # success, msg = scheduler.create_task("test_001", "14:30", daily_limit=300)
    # print(f"创建任务: {success}, {msg}")
    
    # 列出任务
    tasks = scheduler.list_tasks()
    print(f"\n当前任务列表:")
    for task in tasks:
        print(f"  - {task['task_name']}: {task['schedule_time']} ({task['status']})")

