"""宁波市阳光采购服务平台配置"""

import time
import os
import requests
from utils.log import log

# execjs 将在运行时动态导入（不在模块导入时检查，避免需要重启应用）
# 这样可以支持在运行时安装 PyExecJS 后立即生效
EXECJS_AVAILABLE = None  # None 表示尚未检查

PLATFORM_NAME = "宁波市阳光采购服务平台"
PLATFORM_CODE = "ningbo"

BASE_URL = "https://ygcg.nbcqjy.org:8071"
API_BASE_URL = "https://ygcg.nbcqjy.org:8072"
API_LIST_URL = f"{API_BASE_URL}/api/ProjectInfo/GetList"
API_FILE_URL = f"{API_BASE_URL}/api/File/GetFileByType"
API_DOWNLOAD_BASE_URL = f"{API_BASE_URL}/files"
API_LOGIN_URL = f"{API_BASE_URL}/api/Account/Login"

# 登录配置
LOGIN_ACCOUNT = "13376851006"
LOGIN_PASSWORD = "Wzy123888!"

# 获取login.js文件路径（生产代码位置）
# login.js 位于: spider/platforms/ningbo/js/login.js
# 注意：不再使用 crawl_tests 目录中的文件，所有必需文件都在生产代码位置
_CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
# _CONFIG_DIR = spider/platforms/ningbo

# 生产代码位置的 login.js
LOGIN_JS_PATH = os.path.join(_CONFIG_DIR, "js", "login.js")
LOGIN_JS_PATH = os.path.abspath(LOGIN_JS_PATH)

# 验证文件是否存在
if not os.path.exists(LOGIN_JS_PATH):
    log.error(
        f"❌ login.js 文件不存在于生产代码位置: {LOGIN_JS_PATH}\n"
        f"请确保以下文件存在于正确位置：\n"
        f"  - spider/platforms/ningbo/js/login.js\n"
        f"  - spider/platforms/ningbo/js/package.json\n"
        f"  - spider/platforms/ningbo/js/node_modules/（已安装依赖）\n"
        f"项目不再使用 crawl_tests 目录中的文件。"
    )
else:
    log.debug(f"✓ 使用生产代码位置的 login.js: {LOGIN_JS_PATH}")


def get_access_token() -> str:
    """
    动态获取access_token
    
    参考 login.py 的实现方式
    
    Returns:
        access_token字符串，失败返回空字符串
    """
    global EXECJS_AVAILABLE
    
    try:
        # 运行时动态导入 execjs（支持运行时安装后立即生效）
        if EXECJS_AVAILABLE is None or not EXECJS_AVAILABLE:
            try:
                import execjs
                EXECJS_AVAILABLE = True
                log.debug("成功导入 execjs 模块")
            except ImportError as e:
                EXECJS_AVAILABLE = False
                import sys
                python_path = sys.executable
                log.error(
                    f"execjs 模块未安装，无法获取 access_token。\n"
                    f"当前 Python 路径: {python_path}\n"
                    f"请在该 Python 环境中安装: pip install PyExecJS\n"
                    f"或使用: {python_path} -m pip install PyExecJS"
                )
                return ""
        
        # 确保 execjs 已导入
        import execjs
        
        # 检查是否有可用的 JavaScript 运行时
        try:
            runtime = execjs.get()
            if not runtime:
                log.error("未找到可用的 JavaScript 运行时。PyExecJS 需要 Node.js 或其他 JavaScript 运行时。")
                return ""
            log.debug(f"使用 JavaScript 运行时: {runtime.name}")
        except Exception as e:
            log.error(f"获取 JavaScript 运行时失败: {str(e)}")
            return ""
        
        # 读取login.js文件
        with open(LOGIN_JS_PATH, 'r', encoding='utf-8') as f:
            js_data = f.read()
        
        # 编译并执行JS函数加密密码
        # 设置工作目录为 login.js 所在目录，以便 Node.js 能找到 node_modules
        login_js_dir = os.path.dirname(LOGIN_JS_PATH)
        original_cwd = os.getcwd()
        try:
            os.chdir(login_js_dir)  # 切换到 login.js 所在目录
            js_compiled = execjs.compile(js_data)
            encrypted_password = js_compiled.call('a')
        finally:
            os.chdir(original_cwd)  # 恢复原工作目录
        
        # 准备登录请求头
        login_headers = {
            'accept': '*/*',
            'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'access_token': 'null',
            'cache-control': 'no-cache',
            'content-type': 'application/json',
            'origin': 'https://ygcg.nbcqjy.org:8071',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': 'https://ygcg.nbcqjy.org:8071/',
            'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
        }
        
        # 准备登录请求数据
        json_data = {
            'account': LOGIN_ACCOUNT,
            'password': encrypted_password,
            'v': int(time.time()),
        }
        
        # 发送登录请求
        response = requests.post(API_LOGIN_URL, headers=login_headers, json=json_data, timeout=15)
        response.raise_for_status()
        
        result = response.json()
        
        # 检查登录是否成功
        if isinstance(result, dict) and result.get("code") == 1:
            access_token = result.get("data", "")
            if access_token:
                log.info(f"成功获取access_token（长度: {len(access_token)}）")
                return access_token
            else:
                log.warning("登录成功但access_token为空")
                return ""
        else:
            error_msg = result.get("msg", "未知错误")
            log.error(f"登录失败: code={result.get('code')}, msg={error_msg}")
            return ""
            
    except FileNotFoundError:
        log.error(f"找不到login.js文件: {LOGIN_JS_PATH}")
        return ""
    except Exception as e:
        log.error(f"获取access_token失败: {str(e)}", exc_info=True)
        return ""


# 请求头（获取列表和文件URL使用）
HEADERS_LIST = {
    'accept': 'application/json, text/javascript, */*; q=0.01',
    'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'access_token': '',  # 将在运行时动态获取
    'cache-control': 'no-cache',
    'origin': 'https://ygcg.nbcqjy.org:8071',
    'pragma': 'no-cache',
    'priority': 'u=1, i',
    'referer': 'https://ygcg.nbcqjy.org:8071/',
    'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
}

# 在模块加载时初始化access_token（可选，如果失败不影响模块导入）
try:
    _initial_access_token = get_access_token()
    if _initial_access_token:
        HEADERS_LIST['access_token'] = _initial_access_token
    else:
        log.warning("初始化时获取access_token失败，请确保在spider运行时重新获取")
except Exception as e:
    log.warning(f"初始化access_token时出错（不影响模块导入）: {str(e)}")

# 请求头（下载文件使用）
HEADERS_DOWNLOAD = {
    'accept': '*/*',
    'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'cache-control': 'no-cache',
    'origin': 'https://ygcg.nbcqjy.org:8071',
    'pragma': 'no-cache',
    'priority': 'u=1, i',
    'referer': 'https://ygcg.nbcqjy.org:8071/',
    'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
}

# Cookie（如果需要）
COOKIES = {}

# 默认请求参数
DEFAULT_LIST_PARAMS = {
    'pageIndex': '1',
    'pageSize': '10',
    '_v': str(int(time.time() * 1000)),
}

# 获取文件URL的默认参数
DEFAULT_FILE_PARAMS = {
    'TypeId': '020101,030101',  # 文件类型ID
    'SectId': '',
    'isPub': '1',
    'pageIndex': '1',
    'pageSize': '10',
    '_v': str(int(time.time() * 1000)),
}

# 平台配置
PLATFORM_CONFIG = {
    "name": PLATFORM_NAME,
    "code": PLATFORM_CODE,
    "base_url": BASE_URL,
    "api_base_url": API_BASE_URL,
    "api_list_url": API_LIST_URL,
    "api_file_url": API_FILE_URL,
    "api_download_base_url": API_DOWNLOAD_BASE_URL,
    "headers_list": HEADERS_LIST,
    "headers_download": HEADERS_DOWNLOAD,
    "cookies": COOKIES,
    "default_list_params": DEFAULT_LIST_PARAMS,
    "default_file_params": DEFAULT_FILE_PARAMS,
    "max_pages": 50,
    "page_size": 10,
    "request_interval": 2,
}
