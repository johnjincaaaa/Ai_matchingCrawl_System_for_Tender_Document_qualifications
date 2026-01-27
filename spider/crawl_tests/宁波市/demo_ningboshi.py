import requests
import time


def get_doc():
    headers = {
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'access_token': 'FEE2D5DFD88F8CCFEE68E2DE786068D9CCF23C98C16F6C4C4E5D8FA91848150559F4D971C9D159CBA0A3C6234C1FF3D095B76D9592DC518B6A4220CF955421CBA2FD8A02C48458284E3C18857B84545C3176630EB72818C89E3BBBF788F06057F30F4F62D4CC84532FF58DAF65A41DA9C1320E5D81F7108EF39D72231EEF3BAC8EF7519B31E9CC45177055C7C69DA61F7B047774F03CD03E1F23886DB2EC022388EC41ACBBD7FE5473F2C6C9DC770C23AB5CB1FF00068487B114ABB240779E4BB504138903570596A7DBFEB03FB45199B65A8FB7B6F7E287A9814C5F69569441',
        'cache-control': 'no-cache',
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

    params = {
        'pageIndex': '1', # 1是第一页，2是第二页
        'pageSize': '10',
        '_v': '1768714627770',
    }

    response = requests.get('https://ygcg.nbcqjy.org:8072/api/ProjectInfo/GetList', params=params, headers=headers)
    print(response.json())
    # ZTBTypeName 选择“公开招标的项目” ， PrjName 是文件名，SignUpStartDate是发布时间，这是宁波市阳光采购服务平台，PrjId是文件标识用于get_download_url



def get_download_url(PrjId):

    headers = {
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'access_token': 'FEE2D5DFD88F8CCFEE68E2DE786068D9CCF23C98C16F6C4C4E5D8FA91848150559F4D971C9D159CBA0A3C6234C1FF3D095B76D9592DC518B6A4220CF955421CBA2FD8A02C48458284E3C18857B84545C3176630EB72818C89E3BBBF788F06057F30F4F62D4CC84532FF58DAF65A41DA9C1320E5D81F7108EF39D72231EEF3BAC8EF7519B31E9CC45177055C7C69DA61F70997F7230C609167CF61A72528995355B3EE06AE02B1211AB3F55897DC5A6684F6F6D6C9BF72FCB85AD1F2602731BE5DA826E3C37ADBF5E69664455AB9785801CEE167F25D1864A64F015C2D44DF5E6',
        'cache-control': 'no-cache',
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

    response = requests.get(
        f'https://ygcg.nbcqjy.org:8072/api/File/GetFileByType?TypeId=020101,030101&SectId=&PrjId={PrjId}&isPub=1&pageIndex=1&pageSize=10&_v={str(int(time.time()*1000))}',
        headers=headers,
    )
    print(response.json())
    #
    # https://ygcg.nbcqjy.org:8072/files/+ FileUrl 是文件下载url

def download(FileUrl):


    headers = {
        'accept': '*/*',
        'accept-language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'cache-control': 'no-cache',
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

    params = {
        'v': str(int(time.time()*1000)),
    }

    response = requests.get(

        # 注意  "FileUrl": "/MyUpfiles/2026/01/16/202211101116399516_相关材料_20260116163843851.doc",需要对中文进行编码
        url= 'https://ygcg.nbcqjy.org:8072/files/MyUpfiles/2026/01/15/T202109231936441054_%E6%8B%9B%E6%A0%87%E6%96%87%E4%BB%B6%E5%AE%9A%E7%A8%BF-%E5%AE%81%E6%B3%A2%E5%8D%8E%E6%B6%A6%E5%85%B4%E5%85%89%E7%87%83%E6%B0%94%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B82026%E5%B9%B4%E5%BA%A6%E7%9F%AD%E4%BF%A1%E6%81%AF%E4%B8%9A%E5%8A%A1%E6%9C%8D%E5%8A%A1%E9%A1%B9%E7%9B%AE(2)_20260115135333809.pdf?v=1768717631021',
        params=params,
        headers=headers,
    )
    print(response.status_code)
    print(len(response.text))
    with open('doc.pdf', 'wb') as f:
        f.write(response.content)


if __name__ == '__main__':
    get_download_url('M3302005195029567001')
    download('2')




