import logging
from loguru import logger
import os
from config import LOG_CONFIG

# 移除默认日志配置
logger.remove()

# 配置日志输出（文件+控制台），添加过滤器过滤WebSocket和ScriptRunContext错误
def filter_websocket_errors(record):
    """过滤WebSocket和ScriptRunContext相关错误"""
    message = str(record["message"]).lower()
    if any(keyword in message for keyword in [
        'websocketclosederror', 'websocket closed',
        'streamclosederror', 'stream is closed',
        'task exception was never retrieved',
        'tornado.websocket', 'tornado.iostream',
        'missing scriptruncontext', 'this warning can be ignored when running in bare mode'
    ]):
        return False
    return True

# 配置日志输出（文件+控制台）
logger.add(
    sink=LOG_CONFIG["file_name"],
    level=LOG_CONFIG["level"],
    rotation=LOG_CONFIG["rotation"],
    retention=LOG_CONFIG["retention"],
    filter=filter_websocket_errors,  # 添加过滤器
    # 移除 encoding 参数（loguru 0.7.2 不支持）
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} | {message}"
)

# 控制台输出
logger.add(
    sink=logging.StreamHandler(),
    level=LOG_CONFIG["level"],
    filter=filter_websocket_errors,  # 添加过滤器
    # 移除 encoding 参数（控制台输出无需指定编码）
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)

# 对外暴露logger
log = logger