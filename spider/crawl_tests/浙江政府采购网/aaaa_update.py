import requests
import json
import time
def get_article_id(page):
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": "https://zfcg.czt.zj.gov.cn",
        "Pragma": "no-cache",
        "Referer": "https://zfcg.czt.zj.gov.cn/site/category?parentId=600007&childrenCode=ZcyAnnouncement",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "sec-ch-ua": "\"Google Chrome\";v=\"143\", \"Chromium\";v=\"143\", \"Not A(Brand\";v=\"24\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\""
    }
    cookies = {
        "_zcy_log_client_uuid": "3b7c1220-cba3-11f0-861e-89fd9d7f1874",
        "sensorsdata2015jssdkcross": "%7B%22distinct_id%22%3A%2219ac5ddd55cafc-07953edbd474964-26061b51-1327104-19ac5ddd55de53%22%2C%22first_id%22%3A%22%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E5%BC%95%E8%8D%90%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC%22%2C%22%24latest_referrer%22%3A%22https%3A%2F%2Fmiddle.zcygov.cn%2F%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTlhYzVkZGQ1NWNhZmMtMDc5NTNlZGJkNDc0OTY0LTI2MDYxYjUxLTEzMjcxMDQtMTlhYzVkZGQ1NWRlNTMifQ%3D%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%22%2C%22value%22%3A%22%22%7D%2C%22%24device_id%22%3A%2219ac5ddd55cafc-07953edbd474964-26061b51-1327104-19ac5ddd55de53%22%7D",
        "sensorsdata2015jssdksession": "%7B%22session_id%22%3A%2219ac5ddd56c127c01feaee172d4ce926061b51132710419ac5ddd56d1486%22%2C%22first_session_time%22%3A1764256241003%2C%22latest_session_time%22%3A1764256253533%7D",
        "arialoadData": "false",
        "SERVERID": "c0ff6b8d33817b41e83fdc318f702481|1769587118|1769586966"
    }
    url = "https://zfcg.czt.zj.gov.cn/portal/category"
    data = {
        "pageNo": 1, # 这是页数page
        "pageSize": 15,
        "categoryCode": "110-978863", # 非政府招标公告是categoryCode: "110-420383"
        "isGov": True,
        "excludeDistrictPrefix": [
            "90",
            "006011",
            "H0",
            "001111"
        ],
        "_t": int(time.time()*1000),
        # "publishDateBegin": "2023-01-28"
    }
    data = json.dumps(data, separators=(',', ':'))
    response = requests.post(url, headers=headers, cookies=cookies, data=data)

    print(response.json())
    print(response)

def get_download_url(articleId):
    import requests

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "sec-ch-ua": "\"Google Chrome\";v=\"143\", \"Chromium\";v=\"143\", \"Not A(Brand\";v=\"24\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\""
    }
    cookies = {
        "_zcy_log_client_uuid": "3b7c1220-cba3-11f0-861e-89fd9d7f1874",
        "sensorsdata2015jssdkcross": "%7B%22distinct_id%22%3A%2219ac5ddd55cafc-07953edbd474964-26061b51-1327104-19ac5ddd55de53%22%2C%22first_id%22%3A%22%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E5%BC%95%E8%8D%90%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC%22%2C%22%24latest_referrer%22%3A%22https%3A%2F%2Fmiddle.zcygov.cn%2F%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTlhYzVkZGQ1NWNhZmMtMDc5NTNlZGJkNDc0OTY0LTI2MDYxYjUxLTEzMjcxMDQtMTlhYzVkZGQ1NWRlNTMifQ%3D%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%22%2C%22value%22%3A%22%22%7D%2C%22%24device_id%22%3A%2219ac5ddd55cafc-07953edbd474964-26061b51-1327104-19ac5ddd55de53%22%7D",
        "sensorsdata2015jssdksession": "%7B%22session_id%22%3A%2219ac5ddd56c127c01feaee172d4ce926061b51132710419ac5ddd56d1486%22%2C%22first_session_time%22%3A1764256241003%2C%22latest_session_time%22%3A1764256253533%7D",
        "arialoadData": "false",
        "zcy_im_uuid": "8595f80b-cdfc-46c6-8eb3-9b69a534117f",
        "SERVERID": "599f0cf21dfe516b17a8fac76fcd4c39|1769588139|1769587628"
    }
    url = "https://zfcg.czt.zj.gov.cn/portal/detail"
    params = {
        "articleId": articleId,
        "timestamp": str(int(time.time()*1000))
    }
    response = requests.get(url, headers=headers, cookies=cookies, params=params)

    print(response.json())
    print(response)
    return response.json().get('result').get('data').get('attachmentVO').get('acquirePurFileDetailUrl')

import requests
from requests.exceptions import HTTPError, ConnectionError, Timeout, RequestException

def login():
    """政采云登录接口请求 - 优化版"""
    # -------------------------- 1. 可配置参数（按需修改）--------------------------
    USERNAME = "qy1234567"  # 登录用户名
    PASSWORD = "wqh284704256"    # 登录密码
    LOGIN_URL = "https://login.zcygov.cn/login"
    # 初始Cookie（接口要求的固定初始标识，会话会自动更新后续鉴权Cookie）

    # -------------------------- 2. 初始化会话（核心：自动维护Cookie）--------------------------
    session = requests.Session()

    # -------------------------- 3. 精简请求头（移除冗余，保留接口必需）--------------------------
    # 移除原代码中被files自动覆盖的Content-Type，保留浏览器标识、跨域、来源等核心头
    HEADERS = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Origin': 'https://login.zcygov.cn',
        'Referer': 'https://login.zcygov.cn/user-login/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0',
        'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Microsoft Edge";v="144"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
    }

    # -------------------------- 4. 接口固定参数（保留原请求所有特征）--------------------------
    # URL拼接参数
    PARAMS = {
        'current_uri': 'https://login.zcygov.cn/user-login/#/login',
    }
    # 加载初始Cookie到会话（后续登录响应的新Cookie会自动覆盖/追加）
    session.get(url='https://login.zcygov.cn/user-login/#/login', headers=HEADERS, timeout=15)

    # multipart/form-data 表单参数（files格式是requests模拟该类型的标准方式）
    FILES = {
        'platformCode': (None, 'zcy'),
        'loginType': (None, 'password'),
        'requestType': (None, 'async'),
        'username': (None, USERNAME),
        'password': (None, PASSWORD),
        'agreement': (None, 'general_login_agreement'),
    }

    try:
        # -------------------------- 5. 发送登录请求 --------------------------
        print("正在发起登录请求...")
        response = session.post(
            url=LOGIN_URL,
            params=PARAMS,
            headers=HEADERS,
            files=FILES,
            timeout=15  # 新增超时设置，避免无限等待
        )

        # 校验HTTP请求基础状态（4xx/5xx直接抛出异常）
        response.raise_for_status()

        # -------------------------- 6. 解析并打印响应（格式化+完整信息）--------------------------
        print("=" * 60)
        print(f"请求状态码：{response.status_code}")
        print(f"响应编码：{response.encoding or '未指定'}")
        print(f"登录接口原始响应：")
        # 尝试JSON格式化，失败则打印原始文本（适配接口不同返回格式）
        try:
            import json
            response_json = response.json()
            print(json.dumps(response_json, ensure_ascii=False, indent=2))
        except:
            print(response.text)
        print("=" * 60)

        # -------------------------- 7. 可选：返回会话对象（用于后续带Cookie请求）--------------------------
        return session

    # -------------------------- 8. 完善异常处理（精准定位问题）--------------------------
    except HTTPError as e:
        print(f"❌ HTTP请求错误：{e}，状态码：{response.status_code if 'response' in locals() else '未知'}")
    except ConnectionError:
        print("❌ 网络连接错误：请检查网络或目标地址是否可达")
    except Timeout:
        print("❌ 请求超时：服务器响应超过15秒，请稍后重试")
    except RequestException as e:
        print(f"❌ 请求异常：{str(e)}")
    except Exception as e:
        print(f"❌ 未知错误：{str(e)}")
    finally:
        # 可选：若无需后续使用会话，可在此关闭（建议后续请求完再关闭）
        # session.close()
        pass


def download(session: requests.Session,url):
    a = session.get(url=url)
    print(a.text)

    # 提交表单数据
    submit_url = "https://www.zcygov.cn/api/biz-tender/tender-center/acquirePurFile/submit"
    data = {
        "legalPerson": "王庆浩",
        "name": "衢州市乾元文化传媒有限公司",
        "contactAddress": "浙江省衢州市柯城区盈川西路2号1幢409室",
        "contactEmail": "2912492958@qq.com",
        "contactPhone": "15857012066",
        "contactName": "王庆浩",
        "projectId": url.split("/")[-1],
        "attachments": [],
        "needBilling": 1,
        "invoicinMethod": 2,
        "tabType": 0,
        "intentionItemList": [
            1
        ]
    }
    data = json.dumps(data, separators=(',', ':'))
    response = session.post(url=submit_url, data=data)

    print(response.text)
    print(response)

    # 获取下载链接

    get_Pur_file_url = "https://www.zcygov.cn/api/biz-tender/tender-center/acquirePurFile/getPurFile"
    params = {
        "timestamp": str(int(time.time()*1000)),
        "projectId": url.split("/")[-1],
    }
    response = session.get(get_Pur_file_url,params=params)

    print(response.text)
    """
    这里返回
    {"log$TraceId":"cf279cfb4d372cbc9b08c3b6adf93fe4",
    "result":[{"fileOssId":"1024FPA/undefined/339900/10009660460/20261/1fa68afe-1b58-4e61-97fc-21af135521a9.doc","fileUrl":"https://zcy-gov-open-doc.oss-cn-north-2-gov-1.aliyuncs.com/1024FPA/undefined/339900/10009660460/20261/1fa68afe-1b58-4e61-97fc-21af135521a9.doc",
    "index":1,"name":"（2026.1.28定）招标文件--“百年童忆，赴春之约”鲁迅纪念馆主题活动项目.doc"}],"success":true}
    fileUrl 就是文件下载链接，直接请求就能获取
    """


if __name__ == '__main__':
    # get_article_id(1)
    acquirePurFileDetailUrl = get_download_url('uJU+PnMhYk0lVCq8rgLw8Q==')
    print(acquirePurFileDetailUrl)
    login_session = login()
    if login_session:
        print(login_session)
        download(login_session,acquirePurFileDetailUrl)



