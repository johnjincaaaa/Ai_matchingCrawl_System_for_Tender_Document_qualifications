import requests
import json

def get_url(page):
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Origin": "https://ygcg.sxjypt.com",
        "Pragma": "no-cache",
        "Referer": "https://ygcg.sxjypt.com/home",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "sec-ch-ua": "\"Google Chrome\";v=\"143\", \"Chromium\";v=\"143\", \"Not A(Brand\";v=\"24\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\""
    }
    url = "https://ygcg.sxjypt.com/siteapi/api/Portal/GetBulletinList"
    data = {
        "InfoTypeId": "D01",
        "classID": "21",
        "pageIndex": page,  # 这个是页数
        "pageSize": 8
    }
    data = json.dumps(data, separators=(',', ':'))
    response = requests.post(url, headers=headers, data=data)

    print(response.json())
    print(response)

    # bulletinTitle是文件名，'publishDate': '2026-01-16T10:58:44.53'是发布时间，平台是绍兴市阳光采购服务平台,bulletinId是文件下载标识
def download(bulletinId):
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Referer": "https://ygcg.sxjypt.com/detail?bulletinId=5d8c8f59-1d40-49d7-a18a-2146646f653b",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "sec-ch-ua": "\"Google Chrome\";v=\"143\", \"Chromium\";v=\"143\", \"Not A(Brand\";v=\"24\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\""
    }
    url = f"https://ygcg.sxjypt.com/fileserver/api/download/{bulletinId}"
    response = requests.get(url, headers=headers)

    # print(response.text)
    print(response)
    with open('doc.pdf', 'wb') as f:
        f.write(response.content)



if __name__ == '__main__':
    get_url(1)
    download(20260119145502310)