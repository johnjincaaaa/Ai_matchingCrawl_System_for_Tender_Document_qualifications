from DrissionPage import ChromiumPage
import time
page = ChromiumPage()
page.get('https://b.zhengcaiyun.cn/luban/detail?parentId=550016&articleId=XTT9QQn1hfBOMzheDC5yFA==&utm=luban.luban-PC-39075.1024-pc-wsg-secondLevelPage-front.15.abda5d908d7911f191d5efb913d616b7')

time.sleep(3)
# ========== 选择器自行替换 ==========
slider_btn = page.ele('#aliyunCaptcha-sliding-slider')  # 滑块按钮（拖动的小圆块）
slider_track = page.ele('#aliyunCaptcha-sliding-text') # 滑动轨道

# 获取轨道总宽度，滑动距离 = 轨道宽度 - 滑块自身宽度
track_box = slider_track.rect
btn_box = slider_btn.rect
move_distance = 900

# 动作链：按住 → 右移 → 松开
page.actions.hold(slider_btn).right(move_distance).release()




input('dowj:')


