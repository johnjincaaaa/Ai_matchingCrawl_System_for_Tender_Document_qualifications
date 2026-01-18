import requests
import time
import execjs

with open('login.js', 'r', encoding='utf-8') as f:
    data = f.read()
js_data = execjs.compile(data)
password = js_data.call('a')
print(password)
headers = {
    'accept': '*/*',
    'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'access_token': 'null',
    'cache-control': 'no-cache',
    'content-type': 'application/json',
    'origin': 'https://ygcg.nbcqjy.org:8071',
    'pragma': 'no-cache',
    'priority': 'u=1, i',
    'referer': 'https://ygcg.nbcqjy.org:8071/',
    'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
}

json_data = {
    'account': '13376851006',
    'password': password,
    'v': int(time.time()),
}

response = requests.post('https://ygcg.nbcqjy.org:8072/api/Account/Login', headers=headers, json=json_data)
print(response.status_code)
print(response.json())
"""
{'data': 'FEE2D5DFD88F8CCFEE68E2DE786068D9CCF23C98C16F6C4C4E5D8FA91848150559F4D971C9D159CBA0A3C6234C1FF3D095B76D9592DC518B6A4220CF955421CBA2FD8A02C48458284E3C18857B84545C3176630EB72818C89E3BBBF788F06057F30F4F62D4CC84532FF58DAF65A41DA9C1320E5D81F7108EF39D72231EEF3BAC8EF7519B31E9CC45177055C7C69DA61F70997F7230C609167CF61A7252899535E423900FF88A8529CA77B10495EF4AB018A4D357D47AA798B1451F09F20030DD3E328CC2565A2B4BEC17A100FD199333FFD4C4E0BB0537B098A70A2B6F04B74F', 'msg': '登录成功！', 'code': 1}
access_token 就是data，后续的操作都需要这个参数！！！！
"""

# Note: json_data will not be serialized by requests
# exactly as it was in the original request.
#data = '{"account":"13376851006","password":"b7TMMBqRGooqqYxAlGfs0RRbbHjD03qu/Uj9+AMrM10/BzCiSIN5n1Qm97DtEexox7HuS4oBYbVU1f33tMlhE/h790fLAkwij818SQ05B//n39UjsYqK5Xh/H7/1nhRAXg18TWkpSCnq2hfWcKgwaY0KXncRftdU2UPHHt9Bf3fq4Rc24naHII2lIHqztOqWJVF6sFJlVa9mUBIM0+IIjeEuLRb6O3PCVtZPZem6b6Pr4kZ83tzS43/qQOCUjo/lSmIxbOOjBm8VTwkef384QzHoy3stpELGTyVNK3BiFmxLLERtvT5SF+mxBzOXsRyMCfORogt944QQvJxYH2qzCw==","v":1768724096895}'
#response = requests.post('https://ygcg.nbcqjy.org:8072/api/Account/Login', headers=headers, data=data)
