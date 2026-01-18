import requests

def get_doc_url(page:int):

    cookies = {
        'userGuid': '777375320',
        'oauthClientId': 'wzds',
        'oauthPath': 'http://127.0.0.1:8080/EpointWebBuilder',
        'oauthLoginUrl': 'http://127.0.0.1:1112/membercenter/login.html?redirect_uri=',
        'oauthLogoutUrl': '',
        'noOauthRefreshToken': '6bc3742e938397f6942afa30f1416428',
        'noOauthAccessToken': '2e14d7582cfc33b3198100d441ee2859',
        'arialoadData': 'false',
    }

    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Origin': 'https://hcl.jxcqgs.cn',
        'Pragma': 'no-cache',
        'Referer': 'https://hcl.jxcqgs.cn/jyxx/001001/001001003/trade.html',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        # 'Cookie': 'userGuid=777375320; oauthClientId=wzds; oauthPath=http://127.0.0.1:8080/EpointWebBuilder; oauthLoginUrl=http://127.0.0.1:1112/membercenter/login.html?redirect_uri=; oauthLogoutUrl=; noOauthRefreshToken=6bc3742e938397f6942afa30f1416428; noOauthAccessToken=2e14d7582cfc33b3198100d441ee2859; arialoadData=false',
    }

    data = '{"token":"","pn":0,"rn":10,"sdt":"","edt":"","wd":"","inc_wd":"","exc_wd":"","fields":"titlenew","cnum":"005","sort":"{\\"webdate\\":\\"0\\"}","ssort":"title","cl":200,"terminal":"","condition":[{"fieldName":"bidmethodcode","isLike":true,"likeType":2,"equal":"公"}],"time":[],"highlights":"","statistics":null,"unionCondition":[{"fieldName":"categorynum","isLike":true,"likeType":2,"equal":"001001002001"},{"fieldName":"categorynum","isLike":true,"likeType":2,"equal":"001002002001"}],"accuracy":"","noParticiple":"1","searchRange":null,"isBusiness":"1"}'.encode()
    # data = '{"token":"","pn":10,"rn":10,"sdt":"","edt":"","wd":"","inc_wd":"","exc_wd":"","fields":"titlenew","cnum":"005","sort":"{\\"webdate\\":\\"0\\"}","ssort":"title","cl":200,"terminal":"","condition":[{"fieldName":"bidmethodcode","isLike":true,"likeType":2,"equal":"公"}],"time":[],"highlights":"","statistics":null,"unionCondition":[{"fieldName":"categorynum","isLike":true,"likeType":2,"equal":"001001002001"},{"fieldName":"categorynum","isLike":true,"likeType":2,"equal":"001002002001"}],"accuracy":"","noParticiple":"1","searchRange":null,"isBusiness":"1"}'.encode()
    # pn 中0是第一页，10是第二页，以此类推
    response = requests.post(
        'https://hcl.jxcqgs.cn/inteligentsearch/rest/esinteligentsearch/getFullTextDataNew',
        cookies=cookies,
        headers=headers,
        data=data,
    )
    print(response.json())
    """
    返回json数据中，categoryname是平台，title是文件名，，https://hcl.jxcqgs.cn + linkurl  是招标文件发布详情页
    """

def get_download_doc_uid(url):


    cookies = {
        'userGuid': '777375320',
        'oauthClientId': 'wzds',
        'oauthPath': 'http://127.0.0.1:8080/EpointWebBuilder',
        'oauthLoginUrl': 'http://127.0.0.1:1112/membercenter/login.html?redirect_uri=',
        'oauthLogoutUrl': '',
        'noOauthRefreshToken': '6bc3742e938397f6942afa30f1416428',
        'noOauthAccessToken': '2e14d7582cfc33b3198100d441ee2859',
        'arialoadData': 'false',
    }

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'Referer': 'https://hcl.jxcqgs.cn/jyxx/001001/001001003/trade.html',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        # 'Cookie': 'userGuid=777375320; oauthClientId=wzds; oauthPath=http://127.0.0.1:8080/EpointWebBuilder; oauthLoginUrl=http://127.0.0.1:1112/membercenter/login.html?redirect_uri=; oauthLogoutUrl=; noOauthRefreshToken=6bc3742e938397f6942afa30f1416428; noOauthAccessToken=2e14d7582cfc33b3198100d441ee2859; arialoadData=false',
    }

    response = requests.get(
        url=url,
        # url='https://hcl.jxcqgs.cn/jyxx/001001/001001003/001001003001/20260105/3ccd0d4f-ce4d-40eb-9018-c0b87d82ecf4.html',
        cookies=cookies,
        headers=headers,
    )
    # print(response.text)
    """
    找到attachGuid（如：d0079ee6-c81f-4f19-97f8-0b5583544cad）并返回
    <a onclick="ztbfjyz('/EpointWebBuilder/pages/webbuildermis/attach/downloadztbattach?attachGuid=d0079ee6-c81f-4f19-97f8-0b5583544cad&appUrlFlag=ztb001&siteGuid=7eb5f7f1-9041-43ad-8e13-8fcb82ea831a','1','1')" data-title="招标文件正文.pdf" id="attachName">招标文件正文.pdf</a>
    
    """
    import re
    pattern = r'attachGuid=([0-9a-fA-F-]{36})'
    # 执行匹配（只需要找到第一个匹配项即可，符合需求）
    result = re.search(pattern, response.text)

    # 返回匹配结果，匹配成功返回attachGuid，否则返回None
    print(result.group(1) if result else None)
    return result.group(1) if result else None



from q import download_doc



if __name__ == '__main__':
    # get_doc_url(1)
    attachGuid = get_download_doc_uid(url='https://hcl.jxcqgs.cn/jyxx/001001/001001002/001001002001/20260116/17711905-bdd2-414c-b2c5-71b423bb9e5c.html')
    # 这个validateCode应该没有时效性，可以只用这一个而不用重复调用q.py的滑块算法来得到
    download_doc(validateCode="blockpuzzle@1323af89-d52d-4962-ada2-5f68a79ec31e@fcbdc4b5-a72e-4491-b0f3-1095a19c5d36",attachGuid=attachGuid)






















