import requests
import json

def get_doc_url(page):
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": "https://www.ywygzc.com",
        "Pragma": "no-cache",
        "Referer": "https://www.ywygzc.com/jyxx/002001/second_page.html",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "sec-ch-ua": "\"Google Chrome\";v=\"143\", \"Chromium\";v=\"143\", \"Not A(Brand\";v=\"24\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\""
    }
    url = "https://www.ywygzc.com/inteligentsearch/rest/esinteligentsearch/getFullTextDataNew"
    data = {
        "token": "",
        "pn": 0,  # 这是页数，第一页为0，第二页为10，第三页为20，以此类推
        "rn": 10,
        "sdt": "",
        "edt": "",
        "wd": "",
        "inc_wd": "",
        "exc_wd": "",
        "fields": "title;infoa",
        "cnum": "077",
        "sort": "{\"ordernum\":0,\"webdate\":0}",
        "ssort": "title",
        "cl": 500,
        "terminal": "",
        "condition": [
            {
                "equal": "002001",
                "fieldName": "categorynum",
                "isLike": "true",
                "likeType": "2"
            }
        ],
        "time": None,
        "highlights": "content",
        "statistics": None,
        "unionCondition": None,
        "accuracy": "",
        "noParticiple": "",
        "searchRange": None,
        "isBusiness": "1"
    }
    data = json.dumps(data, separators=(',', ':'))
    response = requests.post(url, headers=headers, data=data)

    print(response.text)
    print(response)
"""
返回的json数据中infodate是发布时间，平台是义乌市阳光招标采购平台，linkurl如/jyxx/002001/002001002/002001002001/20260123/2c47fd94-6d81-4a0d-902d-13659d76e9f5.html
加上https://www.ywygzc.com，https://www.ywygzc.com/jyxx/002001/002001002/002001002001/20260123/2c47fd94-6d81-4a0d-902d-13659d76e9f5.html
就是文件详情页链接，title是文件名

"""

def get_doc(url):

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Referer": "https://www.ywygzc.com/jyxx/002001/second_page.html",
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
    url = "https://www.ywygzc.com/jyxx/002001/002001002/002001002001/20260122/f71315d4-bf8a-4fd4-aad3-203f99148468.html"
    response = requests.get(url, headers=headers)

    print(response.text)
    print(response)
    """
    <a class="sub-file-item file-docx" data-attachName="【终稿（阳光平台）】2026年度城建资源公司停车场所消控保安服务采购项目招标文件.doc" href="/hxepointwebbuilder/WebbuilderMIS/attach/downloadZtbAttach.jspx?attachGuid=2ad64248-5e83-4065-b291-d6ed82d59cf2&appUrlFlag=ztb002&siteGuid=953af23a-fbca-4465-8dd6-e06ee568aa24" target="_blank" download>
							    <div class="sub-file-title">
							        <span class="sub-file-name" title="【终稿（阳光平台）】2026年度城建资源公司停车场所消控保安服务采购项目招标文件.doc">【终稿（阳光平台）】2026年度城建资源公司停车场所消控保安服务采购项目招标文件.doc</span>
							    </div>
							    <div class="sub-file-info">
							        <span class="sub-file-size"></span>
							        <span class="sub-file-icon"></span>
							    </div>
							</a>
							
	在返回的html文件里面有文件下载链接，这里是/hxepointwebbuilder/WebbuilderMIS/attach/downloadZtbAttach.jspx?attachGuid=ba7c3d58-ecc2-425c-9ad7-9aea74029517&amp;appUrlFlag=ztb002&amp;siteGuid=953af23a-fbca-4465-8dd6-e06ee568aa24
	然后加上https://www.ywygzc.com/，就是完整链接https://www.ywygzc.com/hxepointwebbuilder/WebbuilderMIS/attach/downloadZtbAttach.jspx?attachGuid=2ad64248-5e83-4065-b291-d6ed82d59cf2&appUrlFlag=ztb002&siteGuid=953af23a-fbca-4465-8dd6-e06ee568aa24
    
    """

def download(doc_url):
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Referer": "https://www.ywygzc.com/jyxx/002001/second_page.html",
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
    response = requests.get(doc_url,headers=headers)
    with open('doc','wb') as f:
        f.write(response.content)

if __name__ == '__main__':
    get_doc_url(1)
    # get_doc('d')
    # download('https://www.ywygzc.com/hxepointwebbuilder/WebbuilderMIS/attach/downloadZtbAttach.jspx?attachGuid=2ad64248-5e83-4065-b291-d6ed82d59cf2&appUrlFlag=ztb002&siteGuid=953af23a-fbca-4465-8dd6-e06ee568aa24')
