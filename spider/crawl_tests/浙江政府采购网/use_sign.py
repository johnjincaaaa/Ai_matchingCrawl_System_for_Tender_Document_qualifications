import requests
import time

from sign import generate_sign_headers

PROJECT_CODE = "330902268240010000012-ZSQHCG-2026-002-2"

COOKIES = {
    "districtCode": "339900",
    "districtName": "%E6%B5%99%E6%B1%9F%E7%9C%81%E6%9C%AC%E7%BA%A7",
    "_zcy_log_client_uuid": "0162b800-cba3-11f0-b797-33fe226cb7f4",
    "districtType": "010100",
    "aid": "500101",
    "Production_uid": "10008527321",
    "user_type": "0202",
    "tenant_code": "330899",
    "institution_id": "144969701165056",
    "searchTraceId": "98258f85-bc80-4284-834b-3a202918bc82",
    "platform_code": "zcy",
    "Production_platform_code": "zcy",
    "Production_lib": "2000002",
    "uid": "10008527321",
    "SESSION": "MGZjZGVhNzMtM2I4Ny00OTJmLThkNmEtNGFlOThjM2QzZGI0",
    "acw_tc": "76b20f6717832367358544517e38b39d83279e609ce984f0248fbeeab97236",
    "ssxmod_itna": "1-YqAxcDBDyDgjK0Ki7G77DuKY4DIMP4x0dGMD3qiQGgDYq7=GFKDCx7IO3eFr3PmSxcYihi=5QBxhqNDlr2GYDSxD=7DK4GT_GrD2b3iW020T3t5nG4NqcG0exe4tOM/o5IyXVjK_yiQQHkXxKzB2w4_D0aDmKDUxWb_Dii7x0rD0eDPxDYDG4FD7PDoxDr_3oDjjOApzSIa84DKx0kDY5DwORIDYPDWxDFk9hxCjgpbDDCDiyjYV3DixiazRxDB2x9CArIWDi3kbS_c8R63HqEWi2ID7v3DlpxUHQRX5N5fbSgEy=TatMjDBQD0IUeawUcQleLQpmSIYD4TGnbnGYDePfrt7i58qxe2DGDeKGKAD5f2H8wx7D570DboNlBdH4D8_5Ci=ELI_Gpw0sxmGkRGYWewB_P3NKfK3Bwwoe=BhYE5VYY3iQeGpiA_QGx2rEK7DgCDY2wDfK7WQ=ADSE_2Wvkr=dhq4D",
    "ssxmod_itna2": "1-YqAxcDBDyDgjK0Ki7G77DuKY4DIMP4x0dGMD3qiQGgDYq7=GFKDCx7IO3eFr3PmSxcYihi=5QBxhwYD=o4_0pQ7iD03WK7B3e_YD05QPcUtiraGzrQA3e9_hmFdQeCtN0d0f0S7ydp9RG0OeB5PSPnOCBpa0nF=cByhv2imRWa5zavpAOApela1Kbx5e8EhYD8aLhFAZayfy6IFc7Gs4R0O3BaOjcHrvgLGK_F=6a5vw1Qm18YWG692yxqPKK=7VapcTkKQwhKQBt1s0YvhqZjz_RDPG=Kj6qlyaLSsHNlBPWPUsdBM89QhSmaBmGYyOGminww75xDmy_PyzyAmevmuMK089Ts3BE/_aj97Qv_bFsFaoXb_4Y3wGHn_c/7aAqzbHsIvPi79UmUI5IFu0mFOQmxQm4BDPfx4GunjAGAccKun8ugQAK18yRgymuDpKwzvB4pbRn3anHcviUFtaijB08YGOGGK/betmOBWKLM1GSM3Aec8=dyxZwqLEIlKpfT10nnGK/fMpWSDilGj5FpIPaPd2cMQ9p/4w2eGrqvoFtpOYNEcecaBi6D5Hf_xlObuhxnaHh=M7GCQROfatSm8tqMDHAIYqGL4jGYttKghAfh4jbmkTn2T1WTYL6/B0YNP_AG9hiDqprLu2264GqcF62kqdvYr/PqlokNzhU4xmV8iDpGNFQqVaPPcrciy5cQD6rDbP/rAiDgulOF5pxSGFxeUDliiQWMmrB5PPH0DdwBo7vqcAzARthPs2rhPy2A0qdxQ34KxNBqDxnaWe0lxxRAYekNrN34CGDD",
}

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
    f"?timestamp={url_ts}&projectNameOrProjectCode={PROJECT_CODE}"
)

sign_headers = generate_sign_headers(
    "GET",
    sign_path,
    uid=COOKIES["Production_uid"],
    timestamp_ms=timestamp_ms,
)

headers = {**HEADERS_BASE, **{k: v for k, v in sign_headers.items() if k.startswith("X-")}}

url = "https://www.zcygov.cn/api/biz-tender/tender-center/acquirePurFile/precisionSearch"
params = {
    "timestamp": url_ts,
    "projectNameOrProjectCode": PROJECT_CODE,
}

print("签名原文:")
print(repr(sign_headers["_sign_string"]))
print()
print("X-Nonce:", headers["X-Nonce"])
print("X-Timestamp:", headers["X-Timestamp"])
print("X-Sign:", headers["X-Sign"])
print()

response = requests.get(url, headers=headers, cookies=COOKIES, params=params)
print(response.text)
print(response)
