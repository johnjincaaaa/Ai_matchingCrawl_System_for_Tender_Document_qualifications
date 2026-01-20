import base64
import requests
import ddddocr




def getVerificationCode():
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Authorization": "Bearer 5f6c90f7bf0561293f048da6b2958e4a",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://www.hzlscgfw.cn",
        "Pragma": "no-cache",
        "Referer": "https://www.hzlscgfw.cn/pageVerify.html",
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
        "sid": "6B6C450DD6114A3D91F404001D9AECF8",
        "HWWAFSESID": "3569e762748b0b1ec8",
        "HWWAFSESTIME": "1768788769793",
        "noOauthRefreshToken": "84980a8a79443c10c253aa16d113ecc5",
        "noOauthAccessToken": "5f6c90f7bf0561293f048da6b2958e4a",
        "oauthClientId": "admin",
        "oauthPath": "http://127.0.0.1:8080/EpointWebBuilder",
        "oauthLoginUrl": "http://127.0.0.1:1112/membercenter/login.html?redirect_uri=",
        "oauthLogoutUrl": ""
    }
    url = "https://www.hzlscgfw.cn/EpointWebBuilder/rest/frontAppNotNeedLoginAction/getVerificationCode"
    data = {
        "params": "{\"width\":\"100\",\"height\":\"40\",\"codeNum\":\"4\",\"interferenceLine\":\"1\",\"codeGuid\":\"\"}"
    }
    response = requests.post(url, headers=headers, cookies=cookies, data=data)

    # print(response.json())
    print(response)
    a = {}
    base64_image_data = response.json().get('custom').get('imgCode')
    verificationCodeGuid = response.json().get('custom').get('verificationCodeGuid')
    verificationCodeValue = response.json().get('custom').get('verificationCodeValue')
    a['imgCode'] = base64_image_data
    a['verificationCodeGuid'] = verificationCodeGuid
    a['verificationCodeValue'] = verificationCodeValue
    return a

def base64_to_jpg(base64_str, output_file="output.jpg"):
    """
    将Base64格式图片转换并保存为本地jpg文件
    :param base64_str: 原始Base64图片字符串（包含data:image/jpg;base64,前缀）
    :param output_file: 输出本地文件名称
    """
    try:
        # 步骤1：剥离Base64数据前缀（data:image/jpg;base64,），只保留核心编码数据
        # 分割前缀与核心数据，取分割后的第2部分
        base64_data = base64_str.split(",")[1]

        # 步骤2：对核心Base64数据进行解码（转为二进制字节流）
        image_bytes = base64.b64decode(base64_data)

        # 步骤3：将二进制字节流写入本地文件，保存为jpg图片
        with open(output_file, "wb") as f:  # wb模式：以二进制写入，避免图片损坏
            f.write(image_bytes)

        print(f"图片转换成功！已保存为：{output_file}")


        # 初始化识别器
        ocr = ddddocr.DdddOcr()

        # 读取图片文件（假设图片保存为 captcha.png）
        with open('output.jpg', 'rb') as f:
            img_bytes = f.read()

        # 识别验证码
        result = ocr.classification(img_bytes)

        # 输出识别结果
        print("识别结果：", result)

        return result

    except Exception as e:
        print(f"图片转换失败：{e}")
        return False

def download(verificationCode,verificationGuid):

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        # "Content-Type": "multipart/form-data; boundary=----WebKitFormBoundaryA4i0355DZABbHO7t",
        "Origin": "https://www.hzlscgfw.cn",
        "Pragma": "no-cache",
        "Referer": "https://www.hzlscgfw.cn/EpointWebBuilder/pages/webbuildermis/attach/downloadztbattach?attachGuid=b1b921ed-5693-44c0-93b4-056223dbc02a&appUrlFlag=ztb001&siteGuid=7eb5f7f1-9041-43ad-8e13-8fcb82ea831a&verificationCode=mepe&verificationGuid=9507a936-4ac4-4612-9165-bae341311776",
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
        "sid": "BDA129A1FF844D97931048C06E71C91C",
        "HWWAFSESID": "3569e762748b0b1ec8",
        "HWWAFSESTIME": "1768788769793",
        "noOauthRefreshToken": "84980a8a79443c10c253aa16d113ecc5",
        "noOauthAccessToken": "5f6c90f7bf0561293f048da6b2958e4a",
        "oauthClientId": "admin",
        "oauthPath": "http://127.0.0.1:8080/EpointWebBuilder",
        "oauthLoginUrl": "http://127.0.0.1:1112/membercenter/login.html?redirect_uri=",
        "oauthLogoutUrl": ""
    }
    url = "https://www.hzlscgfw.cn/EpointWebBuilder/pages/webbuildermis/attach/ztbAttachDownloadAction.action"
    params = {
        "cmd": "getContent",
        "attachGuid": "b1b921ed-5693-44c0-93b4-056223dbc02a",
        "appUrlFlag": "ztb001",
        "siteGuid": "7eb5f7f1-9041-43ad-8e13-8fcb82ea831a",
        "verificationCode": verificationCode,
        "verificationGuid": verificationGuid
    }
    data = '------WebKitFormBoundaryA4i0355DZABbHO7t--\\r\\n'.encode('unicode_escape')
    response = requests.post(url, headers=headers, cookies=cookies, params=params, data=data)

    print(response.text)
    print(response)


if __name__ == '__main__':

    data = getVerificationCode()
    image_code = base64_to_jpg(data.get('imgCode'))
    download(verificationCode=image_code,verificationGuid=data.get('verificationCodeGuid'))