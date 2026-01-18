import requests

def get_doc_id(current:int):
    # 返回的json数据中 tenderName是文件名，createTime是发布时间，id是文件doc_id(返回多个)
    cookies = {
        'ASP.NET_SessionId': 'rixjwgu3jck4hddflnwp01ax',
    }

    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'Referer': 'https://ggzy.hzctc.hangzhou.gov.cn/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
        'jy-random-key': '523-3-7752-1314',
        'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        # 'Cookie': 'ASP.NET_SessionId=rixjwgu3jck4hddflnwp01ax',
    }

    params = {
        'size': '10',
        'current': str(current),
        'area': '0',
        'tradeType': '5',
        'afficheType': '21',
    }

    response = requests.get(
        'https://ggzy.hzctc.hangzhou.gov.cn/api/portal/affiche/list',
        params=params,
        cookies=cookies,
        headers=headers,
    )
    print(response.json())

def find_download_id(doc_id:str):

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Referer": "https://ggzy.hzctc.hangzhou.gov.cn/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "jy-random-key": "523-3-7752-1314",
        "sec-ch-ua": "\"Google Chrome\";v=\"143\", \"Chromium\";v=\"143\", \"Not A(Brand\";v=\"24\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\""
    }
    cookies = {
        "ASP.NET_SessionId": "rixjwgu3jck4hddflnwp01ax"
    }
    url = "https://ggzy.hzctc.hangzhou.gov.cn/api/portal/affiche/find"
    params = {
        # "id": "2cd1e656f3c93c6626d81449ec31edfa"
        "id": doc_id
    }
    response = requests.get(url, headers=headers, cookies=cookies, params=params)

    print(response.json())
    print(response)
    # list的第一次是招标文件id即fileServiceId

def download_id(fileServiceId):
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Referer": "https://ggzy.hzctc.hangzhou.gov.cn/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "jy-random-key": "523-3-7752-1314",
        "sec-ch-ua": "\"Google Chrome\";v=\"143\", \"Chromium\";v=\"143\", \"Not A(Brand\";v=\"24\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\""
    }
    cookies = {
        "ASP.NET_SessionId": "rixjwgu3jck4hddflnwp01ax"
    }
    url = "https://ggzy.hzctc.hangzhou.gov.cn/api/file/download/" + fileServiceId
    response = requests.get(url, headers=headers, cookies=cookies)
    with open(fileServiceId, "wb") as f:
        f.write(response.content)
    print(response)


if __name__ == '__main__':
    # find_download_id('2cd1e656f3c93c6626d81449ec31edfa')
    download_id('5d2df4e608c5cbf3ca8335fbeba51d1e')