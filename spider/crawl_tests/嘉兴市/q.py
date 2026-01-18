import requests

def get_pic_bg():


    cookies = {
        'userGuid': '777375320',
        'noOauthAccessToken': '2e14d7582cfc33b3198100d441ee2859',
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
        'Referer': 'https://hcl.jxcqgs.cn/EpointWebBuilder/frame/pages/login/pageVerify.html',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        # 'Cookie': 'userGuid=777375320; noOauthAccessToken=2e14d7582cfc33b3198100d441ee2859; userGuid=777375320; oauthClientId=wzds; oauthPath=http://127.0.0.1:8080/EpointWebBuilder; oauthLoginUrl=http://127.0.0.1:1112/membercenter/login.html?redirect_uri=; oauthLogoutUrl=; noOauthRefreshToken=6bc3742e938397f6942afa30f1416428; noOauthAccessToken=2e14d7582cfc33b3198100d441ee2859; arialoadData=false',
    }

    data = {
        'step': 'get',
        'captchaType': 'blockpuzzle',
    }

    response = requests.post(
        'https://hcl.jxcqgs.cn/EpointWebBuilder/rest/shellcaptcha/initAndCheckCaptcha',
        cookies=cookies,
        headers=headers,
        data=data,
    )
    print(response.json())
    """
    return 
                captchaID: "aec7c88f-bc61-4fd5-a7c3-e24db545682d"  ## 成功后的查询操作key 对应verifyCodeId
                captchaType
                : 
                "blockpuzzle"
                errorMsg
                : 
                null
                jigsawImageBase64
                : 
                "iVBORw0KGgoAAAANSUhEUgAAAFoAAAEsCAYAAABDpKRqAAAed
                originalImageBase64
                : 
                "iVBORw0KGgoAAAANSUhEUgAAAlgAAAEsCAIAAACQX1rBAACAA
                success
                : 
                true
    """


def download_pic_bg(base64_pic:str):
    import base64
    from PIL import Image
    from io import BytesIO

    # 替换为完整的 Base64 编码字符串
    full_base64_str = base64_pic

    # 解码并保存图片
    img_data = base64.b64decode(full_base64_str)
    img = Image.open(BytesIO(img_data))
    img.save("decoded_image.png")
    img.show()

def verify_pic_bg():
    cookies = {
        'userGuid': '777375320',
        'noOauthAccessToken': '2e14d7582cfc33b3198100d441ee2859',
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
        'Referer': 'https://hcl.jxcqgs.cn/EpointWebBuilder/frame/pages/login/pageVerify.html',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        # 'Cookie': 'userGuid=777375320; noOauthAccessToken=2e14d7582cfc33b3198100d441ee2859; userGuid=777375320; oauthClientId=wzds; oauthPath=http://127.0.0.1:8080/EpointWebBuilder; oauthLoginUrl=http://127.0.0.1:1112/membercenter/login.html?redirect_uri=; oauthLogoutUrl=; noOauthRefreshToken=6bc3742e938397f6942afa30f1416428; noOauthAccessToken=2e14d7582cfc33b3198100d441ee2859; arialoadData=false',
    }

    data = {
        'verifyCodeId': 'aec7c88f-bc61-4fd5-a7c3-e24db545682d', ## 关联get_pic_bg
        'offsetX': '0.2660071942446043',
        'track': '[{"x":0,"y":1},{"x":3,"y":3},{"x":12,"y":5},{"x":23,"y":8},{"x":30,"y":8},{"x":32,"y":8},{"x":38,"y":8},{"x":49,"y":8},{"x":57,"y":8},{"x":68,"y":8},{"x":74,"y":8},{"x":77,"y":8},{"x":79,"y":8},{"x":81,"y":8},{"x":84,"y":8},{"x":87,"y":8}]',
        'step': 'check',
        'captchaType': 'blockpuzzle',
    }

    response = requests.post(
        'https://hcl.jxcqgs.cn/EpointWebBuilder/rest/shellcaptcha/initAndCheckCaptcha',
        cookies=cookies,
        headers=headers,
        data=data,
    )
    ## 成功返回查询validateCode

def download_doc(validateCode,attachGuid):
    import requests

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Type": "multipart/form-data; boundary=----WebKitFormBoundarylVD2CYR0WocyThqX",
        "Origin": "https://hcl.jxcqgs.cn",
        "Pragma": "no-cache",
        "Referer": "https://hcl.jxcqgs.cn/EpointWebBuilder/pages/webbuildermis/attach/downloadztbattach?attachGuid=d0079ee6-c81f-4f19-97f8-0b5583544cad&appUrlFlag=ztb001&siteGuid=7eb5f7f1-9041-43ad-8e13-8fcb82ea831a&verificationCode=blockpuzzle@1323af89-d52d-4962-ada2-5f68a79ec31e@fcbdc4b5-a72e-4491-b0f3-1095a19c5d36&verificationGuid=blockpuzzle@1323af89-d52d-4962-ada2-5f68a79ec31e@fcbdc4b5-a72e-4491-b0f3-1095a19c5d36",
        "Sec-Fetch-Dest": "iframe",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "sec-ch-ua": "\"Google Chrome\";v=\"143\", \"Chromium\";v=\"143\", \"Not A(Brand\";v=\"24\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\""
    }
    cookies = {
        "userGuid": "777375320",
        "noOauthAccessToken": "2e14d7582cfc33b3198100d441ee2859",
        "oauthClientId": "wzds",
        "oauthPath": "http://127.0.0.1:8080/EpointWebBuilder",
        "oauthLoginUrl": "http://127.0.0.1:1112/membercenter/login.html?redirect_uri=",
        "oauthLogoutUrl": "",
        "noOauthRefreshToken": "6bc3742e938397f6942afa30f1416428",
        "arialoadData": "false"
    }
    url = "https://hcl.jxcqgs.cn/EpointWebBuilder/pages/webbuildermis/attach/ztbAttachDownloadAction.action"
    params = {
        "cmd": "getContent",
        "attachGuid": attachGuid,
        # "ca4b274e-eabd-4746-9cf1-7026bbf512c4"
        "appUrlFlag": "ztb001",
        "siteGuid": "7eb5f7f1-9041-43ad-8e13-8fcb82ea831a",
        "verificationCode":validateCode,
        "verificationGuid":validateCode
        ## "blockpuzzle@1323af89-d52d-4962-ada2-5f68a79ec31e@fcbdc4b5-a72e-4491-b0f3-1095a19c5d36"
    }
    data = '------WebKitFormBoundarylVD2CYR0WocyThqX--\\r\\n'.encode('unicode_escape')
    response = requests.post(url, headers=headers, cookies=cookies, params=params, data=data)

    with open('doc.pdf', 'wb') as f:
        f.write(response.content)


if __name__ == '__main__':
    download_doc()