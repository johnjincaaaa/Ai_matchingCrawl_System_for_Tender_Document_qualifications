import requests
import json
def get_url():
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Referer": "https://qzygjy.com/",
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
        "oauthClientId": "echo",
        "oauthPath": "http://127.0.0.1:8080/EpointWebBuilder",
        "oauthLoginUrl": "http://127.0.0.1:1112/membercenter/login.html?redirect_uri=",
        "oauthLogoutUrl": "",
        "noOauthRefreshToken": "cc3114716b3f5283d734dac6b79034e3",
        "noOauthAccessToken": "608a72a70e23c454d9cd2bc8e3286c4c"
    }
    # 这是第一页，第二页是https://qzygjy.com/jyxx/001004/001004001/001004001001/2.html，以此类推
    url = "https://qzygjy.com/jyxx/001004/001004001/001004001001/sec.html"
    response = requests.get(url, headers=headers, cookies=cookies)

    response.encoding = "utf-8"
    print(response.text)
    print(response)

    """
     <div class="wb-data-infor">
                                    <a href="/jyxx/001004/001004001/001004001001/20260123/c8258eb1-cc17-45b0-a68d-6c78be53594e.html" target="_blank" title="湖镇镇沙田湖工业园区（沙湖路段）蒸汽管道采购"><font color='#FF0000'>[正在投标]</font><font color='#FF0000'>[龙游县]</font>湖镇镇沙田湖工业园区（沙湖路段）蒸汽管道采购</a>
                                </div>
    """
    # 返回数据里的href：  /jyxx/001004/001004001/001004001001/20260123/c8258eb1-cc17-45b0-a68d-6c78be53594e.html
    # https://qzygjy.com/jyxx/001004/001004001/001004001001/20260123/c8258eb1-cc17-45b0-a68d-6c78be53594e.html就是文件链接
    #<span class="wb-data-date">2026-01-23</span> 就是文件时间，title是文件名，平台是衢州市阳光交易服务平台

def get_attachGuid(url):
    import requests

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        "sec-ch-ua": "\"Not(A:Brand\";v=\"8\", \"Chromium\";v=\"144\", \"Google Chrome\";v=\"144\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\""
    }
    cookies = {
        "oauthClientId": "echo",
        "oauthPath": "http://127.0.0.1:8080/EpointWebBuilder",
        "oauthLoginUrl": "http://127.0.0.1:1112/membercenter/login.html?redirect_uri=",
        "oauthLogoutUrl": "",
        "noOauthRefreshToken": "cc3114716b3f5283d734dac6b79034e3",
        "noOauthAccessToken": "608a72a70e23c454d9cd2bc8e3286c4c"
    }
    url = "https://qzygjy.com/jyxx/001004/001004001/001004001001/20260128/f0c9651e-1672-4521-b22c-4635fbee3b6d.html"
    response = requests.get(url, headers=headers, cookies=cookies)
    response.encoding = "utf-8"
    print(response.text)
    print(response)
    """
    <div class="download">
								
							<a class="doc" href="javascript:void(0);" style="cursor:pointer" onclick="ztbfjyztest('/EpointWebBuilder/pages/webbuildermis/attach/downloadztbattach?attachGuid=b38136e6-2d84-48aa-a0c7-c6dd7116bf50&appUrlFlag=ztb001&siteGuid=7eb5f7f1-9041-43ad-8e13-8fcb82ea831a','1','1')"  title="招标文件正文.pdf" id="attachName">招标文件正文.pdf</a>
							
						
							<a class="doc" href="javascript:void(0);" style="cursor:pointer" onclick="ztbfjyztest('/EpointWebBuilder/pages/webbuildermis/attach/downloadztbattach?attachGuid=5eb2ddbc-783a-4cce-a823-c2cf43c7e8c7&appUrlFlag=ztb001&siteGuid=7eb5f7f1-9041-43ad-8e13-8fcb82ea831a','1','1')"  title="询比采购文件-浙江常山创安新材料科技有限公司脱硫脱硝环保系统采购.docx" id="attachName">询比采购文件-浙江常山创安新材料科技有限公司脱硫脱硝环保系统采购.docx</a>
							
						</div>
    
    
    """
    # 返回的html文件里面找到招标文件的attachGuid，这里是est('/EpointWebBuilder/pages/webbuildermis/attach/downloadztbattach?attachGuid=b38136e6-2d84-48aa-a0c7-c6dd7116bf50&appUrlFlag=ztb001&siteGuid=7eb5f7f1-9041-43ad-8e13-8fcb82ea831a','1','1')"  title="招标文件正文.pdf
    # b38136e6-2d84-48aa-a0c7-c6dd7116bf50




def initCaptcha():

    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://qzygjy.com",
        "Pragma": "no-cache",
        "Referer": "https://qzygjy.com/EWB-FRONT/frame/pages/login/pageVerify.html",
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
        "noOauthRefreshToken": "cc3114716b3f5283d734dac6b79034e3",
        "noOauthAccessToken": "608a72a70e23c454d9cd2bc8e3286c4c",
        "oauthClientId": "echo",
        "oauthPath": "http://127.0.0.1:8080/EpointWebBuilder",
        "oauthLoginUrl": "http://127.0.0.1:1112/membercenter/login.html?redirect_uri=",
        "oauthLogoutUrl": ""
    }
    url = "https://qzygjy.com/EWB-FRONT/rest/shellcaptcha/initAndCheckCaptcha"
    data = {
        "step": "get",
        "captchaType": "textclick"
    }
    response = requests.post(url, headers=headers, cookies=cookies, data=data)

    data = response.json()
    print(response.json())
    import base64
    from PIL import Image
    from io import BytesIO

    # 假设你的data是接口返回的字典（这里仅作示例，你替换为实际接口返回数据即可）
    # data = {"backpicImageBase64": "接口返回的完整Base64字符串"}

    # 获取Base64字符串
    base64_str = data.get("backpicImageBase64")

    # 检查Base64字符串是否为空
    if not base64_str:
        print("错误：未获取到有效的Base64字符串！")
    else:
        try:
            # 1. 解码Base64为二进制数据
            img_data = base64.b64decode(base64_str)
            # 2. 转换为图片对象
            img = Image.open(BytesIO(img_data))
            # 3. 调整图片宽度为310像素，保持宽高比
            original_width, original_height = img.size
            new_width = 310
            new_height = int(original_height * (new_width / original_width))
            img = img.resize((new_width, new_height))
            # 4. 保存调整后的图片
            img.save("backpic.png")
            print(f"图片处理成功！")

        except base64.binascii.Error as e:
            print(f"Base64解码失败：{e}（可能是字符串不完整/包含无效字符）")
        except Exception as e:
            print(f"图片处理失败：{e}")
    return {"captchaID": data.get("captchaID"),"clickWords": data.get("clickWords")}

def checkCaptcha(captchaID,clickWords:list):

    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://qzygjy.com",
        "Pragma": "no-cache",
        "Referer": "https://qzygjy.com/EWB-FRONT/frame/pages/login/pageVerify.html",
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
        "noOauthRefreshToken": "cc3114716b3f5283d734dac6b79034e3",
        "noOauthAccessToken": "608a72a70e23c454d9cd2bc8e3286c4c",
        "oauthClientId": "echo",
        "oauthPath": "http://127.0.0.1:8080/EpointWebBuilder",
        "oauthLoginUrl": "http://127.0.0.1:1112/membercenter/login.html?redirect_uri=",
        "oauthLogoutUrl": ""
    }
    url = "https://qzygjy.com/EWB-FRONT/rest/shellcaptcha/initAndCheckCaptcha"

    # # 手动输入坐标
    # print("\n" + "=" * 80)
    # print("请查看backpic.png图片，然后输入每个文字的坐标")
    # print("=" * 80)
    #
    # check_nodes = []
    # print(clickWords)
    # for i, word in enumerate(clickWords):
    #     while True:
    #         try:
    #             coord_input = input(f"请输入 '{word}' 的坐标（格式：x,y）：").strip()
    #             # 移除可能的括号和空格
    #             coord_input = coord_input.replace('(', '').replace(')', '').replace(' ', '')
    #             # 分割坐标
    #             parts = coord_input.split(',')
    #             if len(parts) != 2:
    #                 raise ValueError("坐标格式应为两个数字，用逗号分隔")
    #             x, y = map(int, parts)
    #             check_nodes.append(f'{{"x":{x},"y":{y}}}')
    #             break
    #         except ValueError as e:
    #             print(f"输入格式错误: {e}，请重新输入！")
    # print(check_nodes)
    # check_nodes_str = f"[{','.join(check_nodes)}]"
    # print(check_nodes_str)


    # 云码平台：0.016元/次

    import base64
    # www.jfbym.com  注册后登录去用户中心

    with open('backpic.png', 'rb') as f:
        b = base64.b64encode(f.read()).decode()  ## 图片二进制流base64字符串


    code_url = "http://api.jfbym.com/api/YmServer/customApi"
    _data = {
        ## 关于参数,一般来说有3个;不同类型id可能有不同的参数个数和参数名,找客服获取
        "token": "U3M3KPtPNOQmNJj_fIKOmRms0gxvHbZnOiRSetcDOJ8",
        "type": "88888",
        "image": b,
        "extra": ','.join(clickWords)
    }
    _headers = {
        "Content-Type": "application/json"
    }
    response :dict = requests.request("POST", code_url, headers=_headers, json=_data).json()
    print(response)
    """
    {'msg': '识别成功', 'code': 10000, 'data': {'code': 0, 'data': '199,49|94,121|99,49', 'time': 7.194594383239746, 'externel': 2, 'file_path': 'https://ali-jfb2024.oss-cn-chengdu.aliyuncs.com/jfb_upload/dabiao/2026/01/d758f8ac3fde686c084df91cb28544fa.png', 'order_unique_id': 'd758f8ac3fde686c084df91cb28544fa', 'reduce_score': 8, 'unique_code': 'd758f8ac3fde686c084df91cb28544fa'}}
    """
    coordinate = response.get('data').get('data').split('|')
    check_nodes = []
    for i in coordinate:
        i = i.split(',')
        x = int(i[0])
        y = int(i[1])
        check_nodes.append({'x': x, 'y': y})
    check_nodes_str = json.dumps(check_nodes)
    _data1 = {
        "verifyCodeId": captchaID,
        "checkNodes": check_nodes_str,
        "imgWidth": "310",
        "step": "check",
        "captchaType": "textclick"
    }
    response1 = requests.post(url, headers=headers, cookies=cookies, data=_data1)

    print(response1.text)
    print(response1)
    return response1.json().get("validateCode")

def download(valid,attachGuid):

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Type": "multipart/form-data; boundary=----WebKitFormBoundaryx17IciPvRg6OIOK9",
        "Origin": "https://qzygjy.com",
        "Pragma": "no-cache",
        "Referer": "https://qzygjy.com/EpointWebBuilder/pages/webbuildermis/attach/downloadztbattach?attachGuid=567198b7-b183-4814-8076-747a0c7ec47d&appUrlFlag=ztb001&siteGuid=7eb5f7f1-9041-43ad-8e13-8fcb82ea831a&verificationCode=textclick@aede7d41-344b-478f-95a7-aaec150f7a94@2069d7d7-380c-46dc-bb2e-478546fc0689&verificationGuid=textclick@aede7d41-344b-478f-95a7-aaec150f7a94@2069d7d7-380c-46dc-bb2e-478546fc0689",
        "Sec-Fetch-Dest": "iframe",
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
        "oauthClientId": "echo",
        "oauthPath": "http://127.0.0.1:8080/EpointWebBuilder",
        "oauthLoginUrl": "http://127.0.0.1:1112/membercenter/login.html?redirect_uri=",
        "oauthLogoutUrl": "",
        "noOauthRefreshToken": "cc3114716b3f5283d734dac6b79034e3",
        "noOauthAccessToken": "608a72a70e23c454d9cd2bc8e3286c4c"
    }
    url = "https://qzygjy.com/EpointWebBuilder/pages/webbuildermis/attach/ztbAttachDownloadAction.action"
    params = {
        "cmd": "getContent",
        "attachGuid": "567198b7-b183-4814-8076-747a0c7ec47d",
        "appUrlFlag": "ztb001",
        "siteGuid": "7eb5f7f1-9041-43ad-8e13-8fcb82ea831a",
        "verificationCode": valid,
        "verificationGuid": valid
    }
    data = '------WebKitFormBoundaryx17IciPvRg6OIOK9--\\r\\n'.encode('unicode_escape')
    response = requests.post(url, headers=headers, cookies=cookies, params=params, data=data)

    print(response.text)
    print(response)
    with open('doc.pdf', 'wb') as f:
        f.write(response.content)

if __name__ == '__main__':
    # get_url()
    get_attachGuid('w')
    # data = initCaptcha()
    # click_words :list= data.get('clickWords')
    # print(click_words)
    # valid_code = checkCaptcha(captchaID=data.get("captchaID"),clickWords=click_words)
    # download(valid_code,attachGuid=)