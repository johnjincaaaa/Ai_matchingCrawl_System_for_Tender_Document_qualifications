"""测试湖州市平台下载功能"""

import sys
import os

# 添加项目根目录到path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from spider.platforms.huzhou.utils import auto_get_sid, get_verification_code_with_ocr, DDDDOCR_AVAILABLE, DRISSIONPAGE_AVAILABLE
from spider.platforms.huzhou.request_handler import download_file
import requests
from utils.log import log

def test_download():
    """测试下载流程"""
    
    # 测试用的详情页URL和attachGuid（从demo文件中获取）
    test_url = "https://www.hzlscgfw.cn/jyxx/001001/001001002/001001002001/20260119/424c0b25-09d5-479f-905d-92e8f9528dbb.html"
    test_attach_guid = "2406d981-6d40-4500-bb65-6ded437bb906"
    
    log.info("=" * 60)
    log.info("开始测试湖州市平台下载功能")
    log.info("=" * 60)
    
    # 检查依赖
    if not DRISSIONPAGE_AVAILABLE:
        log.error("DrissionPage未安装，请运行: pip install DrissionPage")
        return
    
    if not DDDDOCR_AVAILABLE:
        log.error("ddddocr未安装，请运行: pip install ddddocr")
        return
    
    # 步骤1：自动获取sid
    log.info("\n[步骤1] 自动获取sid...")
    sid = auto_get_sid(test_url)
    
    if not sid:
        log.error("❌ 获取sid失败")
        return
    
    log.info(f"✅ 获取sid成功: {sid}")
    
    # 步骤2：获取验证码
    log.info("\n[步骤2] 获取并识别验证码...")
    verification_info = get_verification_code_with_ocr(sid)
    
    if not verification_info:
        log.error("❌ 获取验证码失败")
        return
    
    verification_code = verification_info.get("code")
    verification_guid = verification_info.get("guid")
    
    log.info(f"✅ 验证码: {verification_code}")
    log.info(f"✅ Guid: {verification_guid}")
    
    # 步骤3：立即下载（验证码获取后必须立即使用）
    log.info("\n[步骤3] 立即下载文件...")
    
    save_path = os.path.join(os.path.dirname(__file__), "test_download.pdf")
    
    # 创建session
    session = requests.Session()
    
    # 调用下载函数（download_file 返回 dict: {"success", "is_captcha_error", "error_msg"}）
    result = download_file(
        session=session,
        attach_guid=test_attach_guid,
        save_path=save_path,
        verification_code=verification_code,
        verification_guid=verification_guid,
        sid=sid,
        headers=None,
        cookies=None
    )
    success = bool(result.get("success"))
    if not success:
        log.error(f"下载返回失败: {result.get('error_msg')}")

    if success and os.path.exists(save_path):
        file_size = os.path.getsize(save_path)
        log.info(f"\n🎉 下载成功！")
        log.info(f"📁 文件路径: {save_path}")
        log.info(f"📏 文件大小: {file_size / 1024:.2f} KB")
        
        # 验证是否为有效的PDF
        with open(save_path, 'rb') as f:
            header = f.read(4)
            if header == b'%PDF':
                log.info("✅ 文件验证：有效的PDF文件")
            else:
                log.warning(f"⚠️ 文件验证：不是标准PDF文件（文件头: {header}）")
    else:
        log.error("\n❌ 下载失败")
    
    session.close()
    
    log.info("\n" + "=" * 60)
    log.info("测试完成")
    log.info("=" * 60)

if __name__ == '__main__':
    test_download()
