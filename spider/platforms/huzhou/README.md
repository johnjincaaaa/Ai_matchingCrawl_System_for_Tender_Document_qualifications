# 湖州市绿色采购服务平台爬虫配置说明

## 配置要求

湖州市平台下载文件需要两个关键参数：
1. **sid**（会话ID）- 从浏览器Cookie中获取
2. **verification_code**（验证码）- 通过API获取后OCR识别

## 配置方法

### 方法1：手动配置（推荐，最简单）

#### 步骤1：获取sid

1. 打开浏览器，访问湖州市平台任意项目详情页，例如：
   ```
   https://www.hzlscgfw.cn/jyxx/001001/001001002/001001002001/20260119/424c0b25-09d5-479f-905d-92e8f9528dbb.html
   ```

2. 点击"招标文件正文.pdf"链接（会弹出验证码输入框）

3. 打开浏览器开发者工具（F12），切换到"Application"或"存储"标签

4. 在Cookies中找到名为`sid`的Cookie，复制其值

5. 将sid值配置到 `config.py` 中的 `sid_fallback`：
   ```python
   "sid_fallback": "你复制的sid值",
   ```

#### 步骤2：配置验证码

验证码可以暂时使用任意4位数字（如"1234"），系统会在实际下载时自动获取新的验证码。

在 `config.py` 中配置：
```python
"verification_code_fallback": "1234",
```

**注意**：sid可能会过期，如果下载失败，需要重新获取sid。

### 方法2：自动获取（需要安装依赖）

如果希望系统自动获取sid和识别验证码，需要安装以下依赖：

```bash
pip install ddddocr DrissionPage
```

然后在 `config.py` 中启用：
```python
"ocr_enabled": True,
```

系统会自动：
1. 使用浏览器自动化获取sid
2. 获取验证码图片并使用OCR识别

**注意**：此方法需要浏览器环境，可能在某些服务器环境下无法使用。

## 配置文件位置

配置文件：`spider/platforms/huzhou/config.py`

需要修改的配置项：
```python
PLATFORM_CONFIG = {
    # ... 其他配置 ...
    "sid_fallback": "你的sid值",  # 手动配置
    "verification_code_fallback": "1234",  # 可以暂时使用任意值
    "ocr_enabled": False,  # 如需自动获取，设置为True并安装依赖
}
```

## 辅助工具

如果遇到问题，可以使用辅助工具函数手动获取：

```python
from spider.platforms.huzhou.utils import auto_get_sid_and_verification_code

# 获取sid和验证码
result = auto_get_sid_and_verification_code("详情页URL")
if result:
    print(f"sid: {result['sid']}")
    print(f"验证码: {result['verification_code']}")
```

## 常见问题

### Q: sid过期了怎么办？
A: sid有时效性，如果下载失败，需要重新访问详情页并点击下载链接，从浏览器Cookie中获取新的sid。

### Q: 验证码识别失败怎么办？
A: 可以暂时使用任意4位数字作为备用验证码，系统会在实际下载时尝试获取新的验证码。

### Q: 能否不使用浏览器自动化？
A: 可以，使用方法1手动配置sid即可，验证码可以暂时使用任意值。
