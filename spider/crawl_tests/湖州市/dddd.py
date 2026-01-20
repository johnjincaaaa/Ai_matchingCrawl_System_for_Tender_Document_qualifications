import requests

cookies = {
    'sid': 'BDA129A1FF844D97931048C06E71C91C',
    'HWWAFSESID': '3569e762748b0b1ec8',
    'HWWAFSESTIME': '1768788769793',
    'noOauthRefreshToken': '84980a8a79443c10c253aa16d113ecc5',
    'noOauthAccessToken': '5f6c90f7bf0561293f048da6b2958e4a',
    'oauthClientId': 'admin',
    'oauthPath': 'http://127.0.0.1:8080/EpointWebBuilder',
    'oauthLoginUrl': 'http://127.0.0.1:1112/membercenter/login.html?redirect_uri=',
    'oauthLogoutUrl': '',
}

headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Content-Type': 'multipart/form-data; boundary=----WebKitFormBoundaryZzpSDIoG9vBJuLO2',
    'Origin': 'https://www.hzlscgfw.cn',
    'Pragma': 'no-cache',
    'Referer': 'https://www.hzlscgfw.cn/EpointWebBuilder/pages/webbuildermis/attach/downloadztbattach?attachGuid=b1b921ed-5693-44c0-93b4-056223dbc02a&appUrlFlag=ztb001&siteGuid=7eb5f7f1-9041-43ad-8e13-8fcb82ea831a&verificationCode=r86r&verificationGuid=f58efb77-8e5a-48a9-a8ab-f4cc4de094a5',
    'Sec-Fetch-Dest': 'iframe',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
    'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    # 'Cookie': 'sid=BDA129A1FF844D97931048C06E71C91C; HWWAFSESID=3569e762748b0b1ec8; HWWAFSESTIME=1768788769793; noOauthRefreshToken=84980a8a79443c10c253aa16d113ecc5; noOauthAccessToken=5f6c90f7bf0561293f048da6b2958e4a; oauthClientId=admin; oauthPath=http://127.0.0.1:8080/EpointWebBuilder; oauthLoginUrl=http://127.0.0.1:1112/membercenter/login.html?redirect_uri=; oauthLogoutUrl=',
}

params = {
    'cmd': 'getContent',
    'attachGuid': 'b1b921ed-5693-44c0-93b4-056223dbc02a',
    'appUrlFlag': 'ztb001',
    'siteGuid': '7eb5f7f1-9041-43ad-8e13-8fcb82ea831a',
    'verificationCode': 'r86r',
    'verificationGuid': 'f58efb77-8e5a-48a9-a8ab-f4cc4de094a5',
}

data = '------WebKitFormBoundaryZzpSDIoG9vBJuLO2--\r\n'

response = requests.post(
    'https://www.hzlscgfw.cn/EpointWebBuilder/pages/webbuildermis/attach/ztbAttachDownloadAction.action',
    params=params,
    cookies=cookies,
    headers=headers,
    data=data,
)





import requests

cookies = {
    'sid': 'BDA129A1FF844D97931048C06E71C91C',
    'HWWAFSESID': '3569e762748b0b1ec8',
    'HWWAFSESTIME': '1768788769793',
    'noOauthRefreshToken': '84980a8a79443c10c253aa16d113ecc5',
    'noOauthAccessToken': '5f6c90f7bf0561293f048da6b2958e4a',
    'oauthClientId': 'admin',
    'oauthPath': 'http://127.0.0.1:8080/EpointWebBuilder',
    'oauthLoginUrl': 'http://127.0.0.1:1112/membercenter/login.html?redirect_uri=',
    'oauthLogoutUrl': '',
}

headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Content-Type': 'multipart/form-data; boundary=----WebKitFormBoundaryNJTVbpUnPPvrYA3q',
    'Origin': 'https://www.hzlscgfw.cn',
    'Pragma': 'no-cache',
    'Referer': 'https://www.hzlscgfw.cn/EpointWebBuilder/pages/webbuildermis/attach/downloadztbattach?attachGuid=b1b921ed-5693-44c0-93b4-056223dbc02a&appUrlFlag=ztb001&siteGuid=7eb5f7f1-9041-43ad-8e13-8fcb82ea831a&verificationCode=q3wb&verificationGuid=12c453f6-0322-4991-b3d6-6c6193490f75',
    'Sec-Fetch-Dest': 'iframe',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
    'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    # 'Cookie': 'sid=BDA129A1FF844D97931048C06E71C91C; HWWAFSESID=3569e762748b0b1ec8; HWWAFSESTIME=1768788769793; noOauthRefreshToken=84980a8a79443c10c253aa16d113ecc5; noOauthAccessToken=5f6c90f7bf0561293f048da6b2958e4a; oauthClientId=admin; oauthPath=http://127.0.0.1:8080/EpointWebBuilder; oauthLoginUrl=http://127.0.0.1:1112/membercenter/login.html?redirect_uri=; oauthLogoutUrl=',
}

params = {
    'cmd': 'getContent',
    'attachGuid': 'b1b921ed-5693-44c0-93b4-056223dbc02a',
    'appUrlFlag': 'ztb001',
    'siteGuid': '7eb5f7f1-9041-43ad-8e13-8fcb82ea831a',
    'verificationCode': 'q3wb',
    'verificationGuid': '12c453f6-0322-4991-b3d6-6c6193490f75',
}

data = '------WebKitFormBoundaryNJTVbpUnPPvrYA3q--\r\n'

response = requests.post(
    'https://www.hzlscgfw.cn/EpointWebBuilder/pages/webbuildermis/attach/ztbAttachDownloadAction.action',
    params=params,
    cookies=cookies,
    headers=headers,
    data=data,
)


