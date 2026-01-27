import base64
import requests
import ddddocr
from DrissionPage import ChromiumPage
from DrissionPage import ChromiumOptions
import time


def geturl():

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Referer": "https://lsygcg.com/jyxx/001001/001001002/001001002001/3.html",
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
        "oauthClientId": "demoClient",
        "oauthPath": "http://127.0.0.1:8080/EpointWebBuilder",
        "oauthLoginUrl": "http://127.0.0.1:1112/membercenter/login.html?redirect_uri=",
        "oauthLogoutUrl": "",
        "noOauthRefreshToken": "79f0056bcd671f2d1ad10e91c4ee140e",
        "noOauthAccessToken": "bbf030178b23eba77a9747357caa70f2"
    }
    url = "https://lsygcg.com/jyxx/001001/001001002/001001002001/sec.html"
    response = requests.get(url, headers=headers, cookies=cookies)

    print(response.text)
    print(response)

    """
     <div class="wb-data-infor">
                                    <a href="/jyxx/001001/001001002/001001002001/20260119/424c0b25-09d5-479f-905d-92e8f9528dbb.html" target="_blank" title="安吉县交通建设工程有限公司拌合楼沥青碎石（石灰岩）供应商采购项目（第六次）">[安吉县]<font color='#FF0000'>[正在报名]</font>安吉县交通建设工程有限公司拌合楼沥青碎石（石灰岩）供应商采购项目（第六次）</a>
                                </div>
                                <span class="wb-data-date">2026/01/19</span>

    title是文件名   href中的 https://lsygcg.com +/jyxx/001001/001001002/001001002001/20260119/424c0b25-09d5-479f-905d-92e8f9528dbb.html 是文件详情地址


     <span class="wb-data-date">2026/01/19</span> 对应的这个是发布时间

    """


def get_attachGuid_from_url(url):
    # url是上面函数拼接的，如：https://lsygcg.com/jyxx/001001/001001002/001001002001/20260113/e1907b12-a287-45b9-86a4-6d60a159fac0.html

    import requests

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Referer": "https://lsygcg.com/jyxx/001001/001001002/001001002001/sec.html",
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
    url = "https://lsygcg.com/jyxx/001001/001001002/001001002001/20260113/e1907b12-a287-45b9-86a4-6d60a159fac0.html"
    response = requests.get(url, headers=headers)

    print(response.text)
    print(response)

    # # 返回的html数据里面含有attachGuid用于下载标书文件，找到招标文件中文pdf中的attachGuid=2406d981-6d40-4500-bb65-6ded437bb906


def auto_get_sid(url):
    # 初始化浏览器（极简写法，适配所有DrissionPage版本）

    options = ChromiumOptions()
    # options.headless()
    page = ChromiumPage()
    try:
        # 1. 打开页面并等待完全加载
        print("🔍 正在加载目标页面...")
        page.get(url)
        time.sleep(3)  # 超长等待，适配旧版加载慢的问题
        print("✅ 页面加载完成")

        # 2. 自动定位并点击下载链接
        print("\n🔍 开始定位下载链接...")
        # 获取所有a标签，遍历匹配关键词
        link = page.ele('@title=招标文件正文.pdf')
        print(link, 'wdwdw')
        link.click()

        time.sleep(3)

        print("\n🔍 开始定位验证码输入框...")
        put = page.ele('@id=yzm')

        if put:
            # 输入验证码
            put.input('adwd')
            time.sleep(1)
            print(f"✅ 自动输入验证码")

            # 4. 自动定位并点击确认按钮
            confirm_btn = page.ele('@class=layui-layer-btn0')

            if confirm_btn:
                confirm_btn.click()
                time.sleep(2)
                print("✅ 自动点击确认按钮")
            else:
                print("⚠️ 未自动找到确认按钮！")

        # 5. 提取sid
        print("\n🔍 开始提取sid...")
        # 旧版DrissionPage兼容写法
        cookies = page.cookies()
        cookie_dict = {}
        if isinstance(cookies, list):
            for c in cookies:
                cookie_dict[c.get('name')] = c.get('value')
        else:
            cookie_dict = cookies

        sid = cookie_dict.get('sid')
        if sid:
            print(f"\n🎉 全自动化提取sid成功！")
            print(f"✅ sid：{sid}")
            print(f"✅ Cookie字符串：sid={sid}")
            success = True
        else:
            print("\n❌ 未提取到sid，但操作已完成！")
            print("📌 当前所有Cookie：")
            for k, v in cookie_dict.items():
                if k and v:
                    print(f"   {k} = {v}")

    except Exception as e:
        print(f"\n❌ 自动化操作出错：{str(e)}")

        # 出错后仍尝试提取sid
        cookies = page.cookies()
        cookie_dict = {}
        if isinstance(cookies, list):
            for c in cookies:
                cookie_dict[c.get('name')] = c.get('value')
        else:
            cookie_dict = cookies
        sid = cookie_dict.get('sid')
        if sid:
            print(f"\n🎉 提取sid成功：{sid}")
            success = True
    page.quit()
    return sid


def getVerificationCode(sid):
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Authorization": "Bearer 3de949139690d85d287dd91f10a50840",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",

    }
    cookies = {
        "sid": sid,
        # "HWWAFSESID": "4c8ac79bbb7f0e44b6",
        # "HWWAFSESTIME": "1769263260008",
        # "noOauthRefreshToken": "fd011020c28c092ce97b01434d905273",
        # "noOauthAccessToken": "f0e883640b3a465f4b8dc78b00fbd318",
        "oauthClientId": "admin",
        "oauthPath": "http://127.0.0.1:8080/EpointWebBuilder",
        "oauthLoginUrl": "http://127.0.0.1:1112/membercenter/login.html?redirect_uri=",
        "oauthLogoutUrl": ""
    }
    url = "https://lsygcg.com/EpointWebBuilder/rest/frontAppNotNeedLoginAction/getVerificationCode"
    data = {
        "params": "{\"width\":\"100\",\"height\":\"40\",\"codeNum\":\"4\",\"interferenceLine\":\"1\",\"codeGuid\":\"\"}"
    }
    response = requests.post(url, headers=headers, cookies=cookies, data=data)
    a = {}
    base64_image_data = response.json().get('custom').get('imgCode')
    verificationCodeGuid = response.json().get('custom').get('verificationCodeGuid')
    verificationCodeValue = response.json().get('custom').get('verificationCodeValue')
    a['imgCode'] = base64_image_data
    a['verificationCodeGuid'] = verificationCodeGuid
    a['verificationCodeValue'] = verificationCodeValue
    return a


def base64_to_jpg(base64_str, output_file="output.jpg"):
    try:
        if "," in base64_str:
            base64_data = base64_str.split(",")[1]
        else:
            base64_data = base64_str
        image_bytes = base64.b64decode(base64_data)
        with open(output_file, "wb") as f:
            f.write(image_bytes)
        print(f"验证码图片已保存为：{output_file}")
        ocr = ddddocr.DdddOcr()
        with open(output_file, 'rb') as f:
            img_bytes = f.read()
        result = ocr.classification(img_bytes)
        print(f"验证码识别结果：{result}")
        return result
    except Exception as e:
        print(f"验证码识别失败：{e}")
        return None


def download_pdf(verificationCode, verificationGuid, attachGuid, sid):

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Type": "multipart/form-data; boundary=----WebKitFormBoundaryXD323ilkjsRlOQc3",
        "Origin": "https://lsygcg.com",
        "Pragma": "no-cache",
        "Referer": "https://lsygcg.com/EpointWebBuilder/pages/webbuildermis/attach/downloadztbattach?attachGuid=6322928c-ed86-47cd-a8c9-4a30a48e91a1&appUrlFlag=ztb001&siteGuid=7eb5f7f1-9041-43ad-8e13-8fcb82ea831a&verificationCode=rfcw&verificationGuid=e2117802-2260-4df4-8385-a416a3cffd59",
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
        "noOauthRefreshToken": "79f0056bcd671f2d1ad10e91c4ee140e",
        "noOauthAccessToken": "bbf030178b23eba77a9747357caa70f2",
        "sid": sid,
        "oauthClientId": "demoClient",
        "oauthPath": "http://127.0.0.1:8080/EpointWebBuilder",
        "oauthLoginUrl": "http://127.0.0.1:1112/membercenter/login.html?redirect_uri=",
        "_CSRFCOOKIE": "404CADFBBC0AFD3BDD5E10B0AD2B5EB53791996F",
        "EPTOKEN": "404CADFBBC0AFD3BDD5E10B0AD2B5EB53791996F",
        "oauthLogoutUrl": ""
    }
    url = "https://lsygcg.com/EpointWebBuilder/pages/webbuildermis/attach/ztbAttachDownloadAction.action"
    params = {
        "cmd": "getContent",
        "attachGuid": attachGuid,
        "appUrlFlag": "ztb001",
        "siteGuid": "7eb5f7f1-9041-43ad-8e13-8fcb82ea831a",
        "verificationCode": verificationCode,
        "verificationGuid": verificationGuid
    }
    data = '------WebKitFormBoundaryXD323ilkjsRlOQc3--\\r\\n'.encode('unicode_escape')

    params = {
        "cmd": "getContent",
        "attachGuid": attachGuid,
        "appUrlFlag": "ztb001",
        "siteGuid": "7eb5f7f1-9041-43ad-8e13-8fcb82ea831a",
        "verificationCode": verificationCode,
        "verificationGuid": verificationGuid
    }
    response = requests.post(url, headers=headers, cookies=cookies, params=params, data=data)



    with open('doc.pdf', 'wb') as f:
        f.write(response.content)
        print(response.text)
        print(response.status_code)
        print(response.headers)


if __name__ == '__main__':
    geturl()
    get_attachGuid_from_url(1)

    try:
        sid = auto_get_sid(
            url='https://lsygcg.com/jyxx/001001/001001002/001001002001/20260113/e1907b12-a287-45b9-86a4-6d60a159fac0.html')
        verification_data = getVerificationCode(sid)
        verification_code = base64_to_jpg(verification_data.get('imgCode'))
        print(f"验证码: {verification_code}")

        download_pdf(
            verificationCode=verification_code,
            verificationGuid=verification_data.get('verificationCodeGuid'),
            attachGuid='6322928c-ed86-47cd-a8c9-4a30a48e91a1',
            sid=sid
        )
    except Exception as e:
        print(f"程序执行出错: {e}")








