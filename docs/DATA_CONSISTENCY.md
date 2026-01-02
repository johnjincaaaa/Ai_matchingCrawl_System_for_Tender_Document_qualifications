# 数据一致性规范文档

本文档定义了系统中各个模块之间数据字段的使用规范，确保数据的一致性。

## 1. 时间字段规范

### 1.1 publish_time（发布时间）

**定义**：项目在招标网站上的实际发布时间（从API获取）

**使用规范**：
- ✅ **必须使用** `publish_time` 用于：
  - 项目统计和筛选（当日项目、时间段筛选等）
  - 报告生成中的时间显示
  - 可视化图表的时间轴
  - 数据导出中的时间列

- ❌ **禁止使用** `create_time` 用于：
  - 项目统计和筛选（`create_time` 是系统爬取时间，不能代表项目发布时间）
  - 报告生成中的时间显示（除非 `publish_time` 为空作为备选）

**数据来源**：
- 爬虫模块从API的 `publishDate` 字段提取（13位毫秒时间戳，需转换为 datetime）
- 转换规则：`timestamp_ms // 1000` 得到秒级时间戳，再转换为 datetime

**示例代码**：
```python
# ✅ 正确：使用 publish_time
projects = db.query(TenderProject).filter(
    TenderProject.publish_time >= start_date,
    TenderProject.publish_time <= end_date
).all()

# ❌ 错误：使用 create_time 进行时间筛选
projects = db.query(TenderProject).filter(
    TenderProject.create_time >= start_date  # 错误！
).all()
```

### 1.2 create_time（创建时间）

**定义**：系统爬取并保存项目到数据库的时间

**使用规范**：
- 仅作为元数据信息显示（如项目详情页）
- 在 `publish_time` 为空时作为备选值（需标记警告）
- 不得用于业务逻辑筛选和统计

### 1.3 publish_timestamp（发布时间戳）

**定义**：API返回的原始时间戳（13位毫秒时间戳）

**使用规范**：
- 保存原始时间戳，用于数据修正和调试
- 当 `publish_time` 与 `create_time` 接近时，可用此字段重新计算正确的发布时间

## 2. 状态字段规范（ProjectStatus）

### 2.1 状态枚举定义

```python
class ProjectStatus(str, enum.Enum):
    PENDING = "待处理"      # 初始状态（已保存但未处理）
    DOWNLOADED = "已下载"    # 文件已下载完成
    PARSED = "已解析"        # 文件已解析完成
    COMPARED = "已比对"      # AI分析已完成
    ERROR = "异常"           # 处理过程中出错
```

### 2.2 状态转换流程

```
PENDING → DOWNLOADED → PARSED → COMPARED
              ↓           ↓
            ERROR      ERROR
```

**转换规则**：
1. **爬虫模块**：创建项目时设置 `status = ProjectStatus.DOWNLOADED`
2. **解析模块**：解析成功时设置为 `ProjectStatus.PARSED`，失败时设置为 `ProjectStatus.ERROR`
3. **AI分析模块**：分析完成时设置为 `ProjectStatus.COMPARED`，失败时设置为 `ProjectStatus.ERROR`

### 2.3 代码规范

**✅ 正确**：使用枚举类型
```python
from utils.db import ProjectStatus

project_data = {
    "status": ProjectStatus.DOWNLOADED  # 使用枚举
}

update_project(db, project_id, {
    "status": ProjectStatus.PARSED
})
```

**❌ 错误**：使用字符串字面量
```python
project_data = {
    "status": "DOWNLOADED"  # 错误！应使用枚举
}
```

## 3. final_decision 字段规范

### 3.1 可能取值

- `"推荐参与"` - 所有客观分条目均可得分
- `"不推荐参与"` - 存在客观分条目不可得分
- `"可以参与"` - 兼容旧值（等同于"推荐参与"）
- `"不可以参与"` - 兼容旧值（等同于"不推荐参与"）
- `"客观分满分"` - 兼容旧值（等同于"推荐参与"）
- `"客观分不满分"` - 兼容旧值（等同于"不推荐参与"）
- `"未判定"` - 初始状态或分析失败

### 3.2 判断逻辑一致性

**推荐参与的判断条件**（满足任一即可）：
- `final_decision in ["推荐参与", "可以参与", "客观分满分"]`

**不推荐参与的判断条件**（满足任一即可）：
- `final_decision in ["不推荐参与", "不可以参与", "客观分不满分"]`

**代码示例**：
```python
# ✅ 正确：使用列表包含所有兼容值
qualified_projects = db.query(TenderProject).filter(
    TenderProject.final_decision.in_([
        "推荐参与", 
        "可以参与", 
        "客观分满分"
    ])
).all()
```

## 4. JSON 字段规范

### 4.1 JSON 字段列表

- `objective_scores` - 客观分项目列表（JSON格式字符串）
- `subjective_scores` - 主观分项目列表（JSON格式字符串）
- `objective_score_decisions` - 客观分判定结果（JSON格式字符串）

### 4.2 序列化/反序列化规范

**保存时**（序列化）：
```python
import json

update_project(db, project_id, {
    "objective_scores": json.dumps(score_list, ensure_ascii=False),  # 不使用ASCII编码
    "subjective_scores": json.dumps(subjective_list, ensure_ascii=False)
})
```

**读取时**（反序列化）：
```python
import json

# 安全反序列化（处理可能的异常）
try:
    objective_scores = json.loads(project.objective_scores) if project.objective_scores else []
except (json.JSONDecodeError, TypeError):
    objective_scores = []
    log.warning(f"项目 {project.id} 的客观分数据格式错误")
```

### 4.3 数据格式规范

**objective_scores 格式**：
```json
["条目1", "条目2", "条目3"]
```

**objective_score_decisions 格式**：
```json
[
    {
        "item": "条目内容",
        "is_attainable": true,
        "decision_reason": "B类规则匹配"
    }
]
```

## 5. 字段命名规范

### 5.1 数据库字段命名

- 使用 snake_case（下划线分隔）
- 字段名应清晰表达含义
- 避免缩写（除非广泛使用的缩写）

**示例**：
- ✅ `publish_time` - 发布时间
- ✅ `project_name` - 项目名称
- ✅ `file_path` - 文件路径
- ❌ `pub_time` - 缩写不清晰
- ❌ `pname` - 缩写不清晰

### 5.2 模块间字段映射

确保各模块使用相同的字段名：

| 数据库字段 | 爬虫模块 | 解析模块 | AI分析模块 | 报告模块 | 可视化模块 |
|-----------|---------|---------|-----------|---------|-----------|
| `publish_time` | ✅ | - | - | ✅ | ✅ |
| `status` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `final_decision` | - | - | ✅ | ✅ | ✅ |
| `objective_scores` | - | - | ✅ | ✅ | ✅ |

## 6. 数据验证规范

### 6.1 必填字段验证

在 `save_project()` 函数中验证：
- `publish_time` - 必须存在且为有效的 datetime 对象
- `project_name` - 必须存在且不为空
- `project_id` - 必须存在且唯一

### 6.2 数据合理性验证

- **publish_time**：与当前时间的差值应合理（大于60秒，避免误用爬取时间）
- **publish_timestamp**：应为13位毫秒时间戳（范围：2000-01-01 至 2200-01-01）
- **status**：必须是有效的 ProjectStatus 枚举值

## 7. 模块职责划分

### 7.1 爬虫模块（spider/tender_spider.py）

**职责**：
- 从API提取项目数据
- 解析 `publishDate` 字段为 `publish_time`
- 保存项目时设置 `status = ProjectStatus.DOWNLOADED`

**数据字段**：
- `publish_time` - 从API时间戳转换
- `publish_timestamp` - 保存原始时间戳
- `status` - 设置为 `ProjectStatus.DOWNLOADED`

### 7.2 解析模块（parser/file_parser.py）

**职责**：
- 解析文件内容
- 更新 `evaluation_content` 字段
- 更新状态为 `ProjectStatus.PARSED` 或 `ProjectStatus.ERROR`

**不修改字段**：
- `publish_time` - 不应修改
- `publish_timestamp` - 不应修改

### 7.3 AI分析模块（ai/qualification_analyzer.py）

**职责**：
- 分析项目资质要求
- 生成比对结果
- 设置 `final_decision`
- 更新状态为 `ProjectStatus.COMPARED`

**数据字段**：
- `final_decision` - 设置为推荐/不推荐
- `objective_scores` - JSON序列化的客观分列表
- `subjective_scores` - JSON序列化的主观分列表
- `comparison_result` - 比对结果文本

### 7.4 报告模块（report/report_generator.py）

**职责**：
- 读取项目数据
- 使用 `publish_time` 进行时间筛选
- 使用 `final_decision` 进行结果筛选
- 反序列化JSON字段

**数据读取**：
- 优先使用 `publish_time`
- 仅在 `publish_time` 为空时使用 `create_time`（标记警告）

### 7.5 可视化模块（app.py）

**职责**：
- 显示项目数据
- 使用 `publish_time` 进行统计和筛选
- 使用 `final_decision` 进行结果筛选

**数据使用**：
- 统计功能必须使用 `publish_time`
- 筛选功能必须使用 `publish_time`
- 表格显示优先显示 `publish_time`

## 8. 检查清单

在修改代码前，请检查：

- [ ] 时间字段使用 `publish_time` 而非 `create_time`（用于业务逻辑）
- [ ] 状态字段使用 `ProjectStatus` 枚举而非字符串
- [ ] `final_decision` 判断包含所有兼容值
- [ ] JSON字段使用 `json.dumps()` 序列化，`json.loads()` 反序列化
- [ ] 字段名与数据库模型定义一致
- [ ] 数据验证逻辑符合规范
- [ ] 模块职责明确，不越权修改字段

## 9. 常见错误示例

### 错误1：使用 create_time 进行时间筛选
```python
# ❌ 错误
today_projects = db.query(TenderProject).filter(
    TenderProject.create_time >= start_of_day  # 错误！
).all()

# ✅ 正确
today_projects = db.query(TenderProject).filter(
    TenderProject.publish_time >= start_of_day  # 正确
).all()
```

### 错误2：使用字符串而非枚举
```python
# ❌ 错误
project_data = {"status": "DOWNLOADED"}

# ✅ 正确
from utils.db import ProjectStatus
project_data = {"status": ProjectStatus.DOWNLOADED}
```

### 错误3：final_decision 判断不完整
```python
# ❌ 错误（缺少兼容值）
if project.final_decision == "推荐参与":
    # 会漏掉 "可以参与" 和 "客观分满分"

# ✅ 正确
if project.final_decision in ["推荐参与", "可以参与", "客观分满分"]:
    # 包含所有兼容值
```

---

**最后更新时间**：2025-01-XX
**维护者**：开发团队

