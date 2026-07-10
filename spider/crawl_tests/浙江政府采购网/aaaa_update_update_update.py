import requests
import json
import time
from DrissionPage import ChromiumPage

from sign import generate_sign_headers

DOWNLOAD_HEADERS_BASE = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Referer": "https://www.zcygov.cn/bid-enroll/_procurement_/acquirepurfile/launch/7339389403230371895?type=4",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "sec-ch-ua": '"Google Chrome";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}


def build_signed_headers(session, method, sign_path, body="", timestamp_ms=None, extra_headers=None):
    """按当前时间戳生成带 X-Nonce / X-Timestamp / X-Sign 的请求头"""
    uid = session.cookies.get("Production_uid", "")
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)
    sign_headers = generate_sign_headers(
        method,
        sign_path,
        body=body,
        uid=uid,
        timestamp_ms=timestamp_ms,
    )
    headers = {
        **DOWNLOAD_HEADERS_BASE,
        **(extra_headers or {}),
        **{k: v for k, v in sign_headers.items() if k.startswith("X-")},
    }
    return headers, str(timestamp_ms // 1000), sign_headers.get("_sign_string", "")


def dumps_json(data) -> str:
    """与浏览器 JSON.stringify 一致：中文不转义、无多余空格"""
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


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
        "pageNo": 1,  # 这是页数page
        "pageSize": 15,
        "categoryCode": "110-978863",  # 非政府招标公告是categoryCode: "110-420383"
        "isGov": True,
        "excludeDistrictPrefix": [
            "90",
            "006011",
            "H0",
            "001111"
        ],
        "_t": int(time.time() * 1000),
        # "publishDateBegin": "2023-01-28"
    }
    data = json.dumps(data, separators=(',', ':'))
    response = requests.post(url, headers=headers, cookies=cookies, data=data)

    print(response.json())
    print(response)


def get_projectId(session, params):
    url = "https://www.zcygov.cn/api/biz-tender/tender-center/acquirePurFile/precisionSearch"

    response = session.get(url, params=params)

    print(response.text)
    print(response)
    try:
        return response.json().get('result')[0].get('projectId')
    except:
        return None


def login():


    # 初始化浏览器
    page = ChromiumPage()
    # 打开登录页
    page.get('https://login.zcygov.cn/login')
    # 等待页面渲染加载完成
    page.wait(1.5)

    # 1. 定位用户名输入框 <input id="username" name="username">
    page.ele('#username').input('qy1234567')
    time.sleep(0.3)

    # 2. 定位密码输入框 <input id="password" name="password" type="password">
    page.ele('#password').input('wqh284704256')
    time.sleep(0.3)

    # 3. 勾选复选框 <input type="checkbox" class="doraemon-checkbox-input">
    page.ele('.doraemon-checkbox-input').click()
    time.sleep(0.3)

    # 4. 点击登录按钮 <button class="doraemon-btn login-button">
    page.ele('text=登 录').click()
    # 等待登录跳转完成
    page.wait(5)
    # 等待菜单渲染完成再点击xpath元素
    page.wait(2)
    # 点击“获取采购文件”
    page.ele('xpath://ul[@class="data-screening-content"]/li[2]/div[2]/div[1]').click()
    # 可选：打印当前页面Cookie，后续接口直接复用
    page.wait(3)
    cookie_dict = page.cookies()
    print(cookie_dict)
    # 修复：返回cookie字典给主函数
    cookie_list = page.cookies()
    cookie_dict = {}
    for ck in cookie_list:
        cookie_dict[ck.get('name')] = ck.get('value')
    print('================login==================', cookie_dict)
    return cookie_dict


def download(session: requests.Session, projectID):
    # 验证域名安全
    verify_url = "https://www.zcygov.cn/api/biz-tender/tender-center/supplier/common/checkSupplierViolation"
    ts1 = int(time.time() * 1000)
    url_ts1 = str(ts1 // 1000)
    sign_path1 = (
        f"/api/biz-tender/tender-center/supplier/common/checkSupplierViolation"
        f"?timestamp={url_ts1}&projectId={projectID}&supplierId="
    )
    headers1, _, _ = build_signed_headers(session, "GET", sign_path1, timestamp_ms=ts1)
    params = {
        "timestamp": url_ts1,
        "projectId": projectID,
        "supplierId": ""
    }
    response = session.get(verify_url, headers=headers1, params=params)
    print('验证域名:', response, response.text)

    # 提交表单数据
    submit_url = "https://www.zcygov.cn/api/biz-tender/tender-center/acquirePurFile/submit"
    data = {
        "legalPerson": "王庆浩",
        "name": "衢州市乾元文化传媒有限公司",
        "contactAddress": "浙江省衢州市柯城区盈川西路2号1幢409室",
        "contactEmail": "2912492958@qq.com",
        "contactPhone": "15857012066",
        "contactName": "王庆浩",
        "projectId": str(projectID),  # 接口返回为字符串，需保持一致
        "attachments": [],
        "needBilling": 1,
        "invoicinMethod": 2,
        "tabType": 0,
        "intentionItemList": [1],
    }
    body = dumps_json(data)
    sign_path2 = "/api/biz-tender/tender-center/acquirePurFile/submit"
    ts2 = int(time.time() * 1000)
    headers2, _, sign_str2 = build_signed_headers(
        session,
        "POST",
        sign_path2,
        body=body,
        timestamp_ms=ts2,
        extra_headers={"Content-Type": "application/json;charset=UTF-8"},
    )
    print("提交表单签名原文:")
    print(repr(sign_str2))
    print("提交表单 body:")
    print(body)
    response = session.post(submit_url, headers=headers2, data=body.encode("utf-8"))
    response.encoding = "utf-8"
    print("提交表单：", response.text)
    submit_result = response.json()
    if not submit_result.get("success"):
        print(
            f"[排查提示] submit 失败 code={submit_result.get('code')} "
            f"message={submit_result.get('message')} traceId={submit_result.get('log$TraceId')}"
        )
        print("常见原因: 1) body 与签名不一致 2) 该项目已提交过 3) 表单字段/资质不符")
        return

    # 获取下载链接
    get_Pur_file_url = "https://www.zcygov.cn/api/biz-tender/tender-center/acquirePurFile/getPurFile"
    ts3 = int(time.time() * 1000)
    url_ts3 = str(ts3 // 1000)
    sign_path3 = (
        f"/api/biz-tender/tender-center/acquirePurFile/getPurFile"
        f"?timestamp={url_ts3}&projectId={projectID}"
    )
    headers3, _, _ = build_signed_headers(session, "GET", sign_path3, timestamp_ms=ts3)
    params = {
        "timestamp": url_ts3,
        "projectId": projectID
    }
    response = session.get(get_Pur_file_url, headers=headers3, params=params)

    print('下载结果：', response, response.text)

    """
    这里返回
    {"log$TraceId":"cf279cfb4d372cbc9b08c3b6adf93fe4",
    "result":[{"fileOssId":"1024FPA/undefined/339900/10009660460/20261/1fa68afe-1b58-4e61-97fc-21af135521a9.doc","fileUrl":"https://zcy-gov-open-doc.oss-cn-north-2-gov-1.aliyuncs.com/1024FPA/undefined/339900/10009660460/20261/1fa68afe-1b58-4e61-97fc-21af135521a9.doc",
    "index":1,"name":"（2026.1.28定）招标文件--“百年童忆，赴春之约”鲁迅纪念馆主题活动项目.doc"}],"success":true}
    fileUrl 就是文件下载链接，直接请求就能获取
    """


def get_download_articleId(articleId):
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Referer": "https://zfcg.czt.zj.gov.cn/site/detail?parentId=600007&articleId=35oztRwHQ01JYY8dulkEkQ%3D%3D",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "sec-ch-ua": "\"Not:A-Brand\";v=\"99\", \"Google Chrome\";v=\"145\", \"Chromium\";v=\"145\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\""
    }
    cookies = {
        "_zcy_log_client_uuid": "3b7c1220-cba3-11f0-861e-89fd9d7f1874",
        "sensorsdata2015jssdkcross": "%7B%22distinct_id%22%3A%2219ac5ddd55cafc-07953edbd474964-26061b51-1327104-19ac5ddd55de53%22%2C%22first_id%22%3A%22%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E5%BC%95%E8%8D%90%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC%22%2C%22%24latest_referrer%22%3A%22https%3A%2F%2Fmiddle.zcygov.cn%2F%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTlhYzVkZGQ1NWNhZmMtMDc5NTNlZGJkNDc0OTY0LTI2MDYxYjUxLTEzMjcxMDQtMTlhYzVkZGQ1NWRlNTMifQ%3D%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%22%2C%22value%22%3A%22%22%7D%2C%22%24device_id%22%3A%2219ac5ddd55cafc-07953edbd474964-26061b51-1327104-19ac5ddd55de53%22%7D",
        "sensorsdata2015jssdksession": "%7B%22session_id%22%3A%2219ac5ddd56c127c01feaee172d4ce926061b51132710419ac5ddd56d1486%22%2C%22first_session_time%22%3A1764256241003%2C%22latest_session_time%22%3A1764256253533%7D",
        "arialoadData": "false",
        "zcy_im_uuid": "1125735c-b54d-467a-b0db-0d8cdcb7a1ab",
        "SERVERID": "599f0cf21dfe516b17a8fac76fcd4c39|1772969247|1772969217"
    }
    url = "https://zfcg.czt.zj.gov.cn/portal/detail"
    params = {
        "articleId": articleId,
        "timestamp": str(int(time.time())),
    }
    response = requests.get(url, headers=headers, cookies=cookies, params=params)

    print(response.text)
    print(response)
    return response.json().get('result').get('data').get('projectCode')


if __name__ == '__main__':
    # get_article_id(1)  # 这是在首页的多个数据,先拿到articla_id 去到详情页，再从详情页拿到down_articlaId
    # 单个文件的下载
    # "articleId": "35oztRwHQ01JYY8dulkEkQ==",
    # down_articleId = get_download_articleId(articleId='uEBPPysBeVO69TPwwBIwHA==')
    # print(down_articleId)
    down_articleId = '330100262100010000010-ZJZC-2026-0600502'
    # 登录获取cookie字典
    cookie_info = login()
    # 修复：创建requests会话注入cookie，传给接口函数
    req_session = requests.Session()
    req_session.cookies.update(cookie_info)

    HEADERS_BASE = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Referer": "https://www.zcygov.cn/bid-enroll/_procurement_/acquirepurfile/list?_app_=zcy.procurement&budgetAmountTransition%5BminAmount%5D=&budgetAmountTransition%5BmaxAmount%5D=&pageNo=1&pageSize=10",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "sec-ch-ua": '"Google Chrome";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }

    timestamp_ms = int(time.time() * 1000)
    url_ts = str(timestamp_ms // 1000)

    # 签名用的 path 必须与实际请求 URL 的 path+query 完全一致
    sign_path = (
        f"/api/biz-tender/tender-center/acquirePurFile/precisionSearch"
        f"?timestamp={url_ts}&projectNameOrProjectCode={down_articleId}"
    )
    sign_headers = generate_sign_headers(
        "GET",
        sign_path,
        uid=cookie_info["Production_uid"],
        timestamp_ms=timestamp_ms,
    )

    headers = {**HEADERS_BASE, **{k: v for k, v in sign_headers.items() if k.startswith("X-")}}
    req_session.headers.update(headers)
    params1 = {
        "timestamp": url_ts,
        "projectNameOrProjectCode": down_articleId,
    }
    print("签名原文:")
    print(repr(sign_headers["_sign_string"]))
    print()
    print("X-Nonce:", headers["X-Nonce"])
    print("X-Timestamp:", headers["X-Timestamp"])
    print("X-Sign:", headers["X-Sign"])
    print()
    projectId = get_projectId(session=req_session, params=params1)
    print('=============', projectId)

    if projectId is not None:
        download(req_session, projectId)
