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
    """
          <div class="sub-file">
                    <div class="sub-file-title">附件：</div>
                    <div class="sub-file-list">
                        <a class="sub-file-item file-docx" data-attachName="[YWYGZC202604CG0015-1]义乌市恒风汽车服务有限公司五洲大道分公司2026年和乐餐厅食材供应链采购项目.XECF" href="/hxepointwebbuilder/WebbuilderMIS/attach/downloadZtbAttach.jspx?attachGuid=0521696b-3ec2-48f5-ae06-66f06218ee4a&appUrlFlag=ztb002&siteGuid=953af23a-fbca-4465-8dd6-e06ee568aa24" target="_blank" download>
                            <div class="sub-file-title">
                                <span class="sub-file-name" title="[YWYGZC202604CG0015-1]义乌市恒风汽车服务有限公司五洲大道分公司2026年和乐餐厅食材供应链采购项目.XECF">[YWYGZC202604CG0015-1]义乌市恒风汽车服务有限公司五洲大道分公司2026年和乐餐厅食材供应链采购项目.XECF</span>
                            </div>
                            <div class="sub-file-info">
                                <span class="sub-file-size"></span>
                                <span class="sub-file-icon"></span>
                            </div>
                        </a>
                        <a class="sub-file-item file-docx" data-attachName="答疑文件正文.pdf" href="/hxepointwebbuilder/WebbuilderMIS/attach/downloadZtbAttach.jspx?attachGuid=51fcf28e-df23-44b7-a5e9-d5ae42696df4&appUrlFlag=ztb002&siteGuid=953af23a-fbca-4465-8dd6-e06ee568aa24" target="_blank" download>
                            <div class="sub-file-title">
                                <span class="sub-file-name" title="答疑文件正文.pdf">答疑文件正文.pdf</span>
                            </div>
                            <div class="sub-file-info">
                                <span class="sub-file-size"></span>
                                <span class="sub-file-icon"></span>
                            </div>
                        </a>
                        <a class="sub-file-item file-docx" data-attachName="答疑说明文件.pdf" href="/hxepointwebbuilder/WebbuilderMIS/attach/downloadZtbAttach.jspx?attachGuid=79ef7805-bd7b-4e26-a51c-25b8bad8118f&appUrlFlag=ztb002&siteGuid=953af23a-fbca-4465-8dd6-e06ee568aa24" target="_blank" download>
                            <div class="sub-file-title">
                                <span class="sub-file-name" title="答疑说明文件.pdf">答疑说明文件.pdf</span>
                            </div>
                            <div class="sub-file-info">
                                <span class="sub-file-size"></span>
                                <span class="sub-file-icon"></span>
                            </div>
                        </a>
                        <a class="sub-file-item file-docx" data-attachName="答疑文件正文.docx" href="/hxepointwebbuilder/WebbuilderMIS/attach/downloadZtbAttach.jspx?attachGuid=b1cb7861-7d59-45f3-b0c2-ad8fe7a231b7&appUrlFlag=ztb002&siteGuid=953af23a-fbca-4465-8dd6-e06ee568aa24" target="_blank" download>
                            <div class="sub-file-title">
                                <span class="sub-file-name" title="答疑文件正文.docx">答疑文件正文.docx</span>
                            </div>
                            <div class="sub-file-info">
                                <span class="sub-file-size"></span>
                                <span class="sub-file-icon"></span>
                            </div>
                        </a>
                    </div>
                </div>
    
    也有返回这样的，只要拿到文件正文
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
# 这里文件后缀以实际获取到的为准
        f.write(response.content)

if __name__ == '__main__':
    get_doc_url(1)
    get_doc('d')
    download('https://www.ywygzc.com/hxepointwebbuilder/WebbuilderMIS/attach/downloadZtbAttach.jspx?attachGuid=2ad64248-5e83-4065-b291-d6ed82d59cf2&appUrlFlag=ztb002&siteGuid=953af23a-fbca-4465-8dd6-e06ee568aa24')
