import requests

def geturl():
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Referer": "https://www.hzlscgfw.cn/jyxx/001001/001001002/001001002001/sec.html",
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
    cookies = {
        "HWWAFSESID": "3569e762748b0b1ec8",
        "HWWAFSESTIME": "1768788769793",
        "noOauthRefreshToken": "84980a8a79443c10c253aa16d113ecc5",
        "noOauthAccessToken": "5f6c90f7bf0561293f048da6b2958e4a",
        "oauthClientId": "admin",
        "oauthPath": "http://127.0.0.1:8080/EpointWebBuilder",
        "oauthLoginUrl": "http://127.0.0.1:1112/membercenter/login.html?redirect_uri=",
        "oauthLogoutUrl": ""
    }
    url = "https://www.hzlscgfw.cn/jyxx/001001/001001002/001001002001/sec.html"
    # sec 是第一页 ，https://www.hzlscgfw.cn/jyxx/001001/001001002/001001002001/2.html 是第二页，依次类推
    response = requests.get(url, headers=headers, cookies=cookies)

    print(response.text)
    print(response)

    """
     <div class="wb-data-infor">
                                    <a href="/jyxx/001001/001001002/001001002001/20260119/424c0b25-09d5-479f-905d-92e8f9528dbb.html" target="_blank" title="安吉县交通建设工程有限公司拌合楼沥青碎石（石灰岩）供应商采购项目（第六次）">[安吉县]<font color='#FF0000'>[正在报名]</font>安吉县交通建设工程有限公司拌合楼沥青碎石（石灰岩）供应商采购项目（第六次）</a>
                                </div>
                                <span class="wb-data-date">2026/01/19</span>
                                
    title是文件名   href中的 https://www.hzlscgfw.cn +/jyxx/001001/001001002/001001002001/20260119/424c0b25-09d5-479f-905d-92e8f9528dbb.html 是文件详情地址
    
    
     <span class="wb-data-date">2026/01/19</span> 对应的这个是发布时间
    
    """





