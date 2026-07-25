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

# RSA 公钥（与 js/login.js 里 jsencrypt 使用的同一把公钥；SPKI/DER 的 base64 形式）。
# jsencrypt 采用 RSA PKCS#1 v1.5 填充，可用 Python cryptography 完全复现，
# 从而在打包成 exe 后无需终端机安装 Node.js。
RSA_PUBLIC_KEY_B64 = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAvAKBZE0Ez4lIlFFO1MO2i/RZVKgHMox"
    "TyVM/WZoiIZRDWV6TzdKYAikE6yb/7nBg4b9NcU0NxmwSTihHngD9n9EDOhYc2IpRsJLjTqd4sgt"
    "65cE5IeIQiymNZrg6ck8xOLldSeMMSC2fz3UneTIoXunj3rPWgCEwmwYLx2nlh+GUh4lIuV4Lrbp"
    "ySe1DYUkrLeW2CMnFg4Kd+OjSrd3niJ/v92ZJFGYYBS1fkdZPpvHEAM2yk7oSTGsuZx4/lSCngjO"
    "+yxs7ppxj5ta57XX6iZPV1baRUmWirU/G+s7HtyVx5Jo2r4hUVjhTnKTvEBK14IsK3dqqXJTabkR"
    "VKVP5qwIDAQAB"
)


def _encrypt_password_py(password: str):
    """用 Python cryptography 复现 jsencrypt 的 RSA(PKCS#1 v1.5) 加密。

    成功返回 base64 密文字符串；库不可用或出错时返回 None（由调用方回退 execjs）。
    """
    try:
        import base64
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives.serialization import load_der_public_key

        pub = load_der_public_key(base64.b64decode(RSA_PUBLIC_KEY_B64))
        ciphertext = pub.encrypt(password.encode("utf-8"), padding.PKCS1v15())
        return base64.b64encode(ciphertext).decode("ascii")
    except Exception as e:  # 缺 cryptography / 解析失败等
        log.debug(f"Python RSA 加密不可用，将回退 execjs: {e}")
        return None

# 获取login.js文件路径（生产代码位置）
# login.js 位于: spider/platforms/ningbo/js/login.js
# 注意：不再使用 crawl_tests 目录中的文件，所有必需文件都在生产代码位置
_CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
# _CONFIG_DIR = spider/platforms/ningbo

# 生产代码位置的 login.js
LOGIN_JS_PATH = os.path.join(_CONFIG_DIR, "js", "login.js")
LOGIN_JS_PATH = os.path.abspath(LOGIN_JS_PATH)

# login.js 仅在 Python RSA 加密不可用时作为 execjs 后备使用；缺失不再当作错误。
if not os.path.exists(LOGIN_JS_PATH):
    log.debug(f"login.js 不存在（仅 execjs 后备需要）: {LOGIN_JS_PATH}，将优先使用 Python RSA 加密")
else:
    log.debug(f"✓ execjs 后备可用 login.js: {LOGIN_JS_PATH}")


def get_access_token() -> str:
    """
    动态获取access_token
    
    参考 login.py 的实现方式
    
    Returns:
        access_token字符串，失败返回空字符串
    """
    global EXECJS_AVAILABLE

    try:
        # 优先用 Python(cryptography) 复现 jsencrypt 的 RSA 加密——打包成 exe 后
        # 终端机无需安装 Node.js。失败再回退到 execjs + login.js（开发环境）。
        encrypted_password = _encrypt_password_py(LOGIN_PASSWORD)

        if not encrypted_password:
            log.info("Python RSA 不可用，回退 execjs + login.js 获取加密密码")
            # 运行时动态导入 execjs（支持运行时安装后立即生效）
            try:
                import execjs
                EXECJS_AVAILABLE = True
            except ImportError:
                EXECJS_AVAILABLE = False
                log.error(
                    "Python RSA 加密不可用，且 execjs 未安装，无法获取 access_token。"
                    "请安装 cryptography（推荐）或 PyExecJS + Node.js。"
                )
                return ""

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
