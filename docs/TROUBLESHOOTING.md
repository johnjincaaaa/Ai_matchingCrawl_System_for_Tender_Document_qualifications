# 故障排查指南

## 问题：项目无缘无故中止 / 平台选择中缺少杭州市平台

### 解决方案

#### 1. 完全重启Streamlit应用

**步骤：**
1. 停止当前运行的Streamlit（在终端按 `Ctrl+C`）
2. 等待几秒确保进程完全退出
3. 清理Python缓存（可选）：
   ```bash
   # Windows PowerShell
   Get-ChildItem -Path . -Include __pycache__ -Recurse -Directory | Remove-Item -Recurse -Force
   ```
4. 重新启动Streamlit：
   ```bash
   streamlit run app.py
   ```

#### 2. 检查导入日志

启动Streamlit后，在终端日志中查找：
- ✅ `注册爬虫: zhejiang (浙江省政府采购网)` 
- ✅ `注册爬虫: hangzhou (杭州市公共资源交易网)`

如果只看到第一个，说明杭州市爬虫导入失败。

#### 3. 验证平台注册

在Python交互环境中测试：
```python
import sys
sys.path.insert(0, '.')
from spider import SpiderManager

# 查看已注册的平台
print("已注册平台:", SpiderManager.list_spiders())

# 应该输出: ['zhejiang', 'hangzhou']
```

#### 4. 检查文件结构

确保以下文件存在：
```
spider/
├── __init__.py
├── base_spider.py
├── spider_manager.py
├── tender_spider.py
└── platforms/
    ├── __init__.py          ← 确保此文件存在
    └── hangzhou/
        ├── __init__.py
        ├── config.py
        ├── request_handler.py
        └── spider.py
```

#### 5. 常见错误及解决方法

**错误1：ModuleNotFoundError: No module named 'spider.platforms'**
- **原因**：`spider/platforms/__init__.py` 文件不存在
- **解决**：已创建此文件，重启应用

**错误2：平台选择中只显示"全部"和"浙江省政府采购网"**
- **原因**：杭州市爬虫未正确注册或导入失败
- **解决**：
  1. 检查 `spider/platforms/hangzhou/__init__.py` 文件是否存在
  2. 检查 `spider/__init__.py` 中的导入是否正确
  3. 重启Streamlit应用

**错误3：应用启动时报错然后停止**
- **原因**：导入错误导致应用崩溃
- **解决**：
  1. 查看终端错误信息
  2. 检查所有导入语句是否正确
  3. 确保所有依赖文件存在

#### 6. 手动验证平台注册

创建测试脚本 `test_platforms.py`：
```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '.')

print("=" * 50)
print("测试平台注册")
print("=" * 50)

try:
    # 1. 导入spider包
    import spider
    print("✓ spider包导入成功")
    
    # 2. 导入SpiderManager
    from spider import SpiderManager
    print("✓ SpiderManager导入成功")
    
    # 3. 查看已注册平台
    platforms = SpiderManager.list_all_spider_info()
    print(f"\n已注册平台数量: {len(platforms)}")
    for p in platforms:
        print(f"  - {p['code']}: {p['name']}")
    
    # 4. 测试get_available_platforms函数
    from app import get_available_platforms
    available = get_available_platforms()
    print(f"\nget_available_platforms返回: {available}")
    
    if 'hangzhou' in available:
        print("\n✓ 杭州市平台已成功注册！")
    else:
        print("\n✗ 杭州市平台未注册！")
        print("请检查导入日志")
        
except Exception as e:
    print(f"\n✗ 错误: {str(e)}")
    import traceback
    traceback.print_exc()
```

运行测试：
```bash
python test_platforms.py
```

### 快速修复清单

- [ ] 已创建 `spider/platforms/__init__.py` 文件
- [ ] 已重启Streamlit应用
- [ ] 检查终端日志确认两个平台都已注册
- [ ] 清除浏览器缓存并刷新页面
- [ ] 验证 `get_available_platforms()` 函数返回正确的平台列表

### 如果问题仍然存在

1. **查看完整错误日志**：
   - 在终端中查看Streamlit的完整输出
   - 查找以 `ERROR` 或 `Traceback` 开头的行

2. **检查Python环境**：
   ```bash
   python --version
   pip list | grep streamlit
   ```

3. **尝试手动导入**：
   ```python
   python -c "from spider.platforms.hangzhou import HangZhouTenderSpider; print(HangZhouTenderSpider.PLATFORM_CODE)"
   ```

4. **联系支持**：提供完整的错误日志和终端输出
