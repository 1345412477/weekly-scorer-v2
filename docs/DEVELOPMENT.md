# 周报评分系统 · 开发文档

> 版本：2.0（严格文件名校验版）
> 更新日期：2026年6月11日

---

## 1. 核心业务目标

* 员工 **必须严格按照模板编写周报，并按规范命名；系统通过 **文件名自动识别提交人**，在人员库中精确匹配，无匹配或无部门则拒绝上传。

## 2. 文件命名规范（严格执行）

**格式：`提交人名字-YYYY年MM月第N周周报YYYYMMDD.xlsx

**示例：

```
张三-2026年6月第2周周报20260614.xlsx
```

**规则：

* 文件扩展名为 `.xlsx`（仅支持 xlsx，不支持 xls/docx/pdf）。
* 「姓名在「-」为分隔符。
* 首段必须为 **2–15 位中文姓名（仅允许中文）。
* 「-」为英文减号；兼容全角「—」自动替换为英文「-」。

## 3. 核心数据流与 API 调用流程

```
用户上传文件
    │
    ├─ 前端校验（.vue）
    │   └─ 文件扩展名必须为 .xlsx
    │
    ├─ POST /api/v1/reports/upload
    │   ├─ 校验扩展名：仅允许 xlsx（reports.py upload_report）
    │   ├─ 解析文件名 → extract_author_from_filename(original_filename)
    │   │   └─ 返回 (candidate_name, hint)
    │   │       └─ 姓名识别失败 → HTTP 400：「文件名不符合规范」
    │   │
    │   ├─ persons 表精确匹配 person.name == candidate_name
    │   │   ├─ 未命中 persons → HTTP 400：「系统中无员工信息：XXX
    │   │   └─ person.department_name 为空 → HTTP 400：「系统中无员工信息：XXX（未配置部门）
    │   │
    │   ├─ parse_report(file_path) → 解析 Excel 内容
    │   ├─ 写入 weekly_reports（author_name/department/person_id/department_id）
    │   └─ trigger_scoring → AI 评分
    │
    └─ 返回前端：姓名/部门/得分/评语/建议
```

## 4. 修改清单

### 4.1 后端

| 文件 | 改动 | 说明 |
|---|---|---|
| `backend/app/services/document_parser.py | `SUPPORTED_EXTENSIONS = {".xlsx"}` | 仅支持 xlsx |
| `backend/app/services/document_parser.py` | 新增 `extract_author_from_filename()` | 从文件名解析首段中文姓名（强校验 |
| `backend/app/services/document_parser.py` | 删除 `_parse_docx`/`_parse_pdf` 等 | 删除不再使用的解析函数 |
| `backend/app/api/reports.py` | `extract_author_and_match_department()` 重写 | 以 `original_filename` 为唯一入口识别 + persons 精确匹配 + 强部门必填 |
| `backend/app/api/reports.py` | `upload_report()` 改造 | 未识别/无部门 → HTTP 400 拒登并删除临时文件 |

### 4.2 前端

| 文件 | 改动 |
|---|---|
| `frontend/src/views/PublicHome.vue` | `acceptFormats = '.xlsx'`，上传提示文案修改为仅支持 .xlsx 及命名规范 |
| `frontend/src/views/WriteReport.vue` | 同上 |

## 5. 后端改造详情

### 5.1 `SUPPORTED_EXTENSIONS`

```python
SUPPORTED_EXTENSIONS = {".xlsx"}  # 只允许 xlsx
```

### 5.2 `extract_author_from_filename()`

定义位置：`backend/app/services/document_parser.py`

```python
def extract_author_from_filename(original_filename: str) -> tuple[str | None, str]:
    """
    从文件名解析提交人姓名。
    格式：「提交人名字-YYYY年MM月第N周周报YYYYMMDD.xlsx」
    返回 (candidate_name, hint_msg)
    - hint_msg = "" 表示成功
    """
    stem = os.path.splitext(original_filename)[0].strip()
    stem = stem.replace("—", "-")  # 兼容全角
    if "-" not in stem:
        return None, "文件名不符合规范"
    parts = [p for p in stem.split("-") if p.strip()]
    candidate = parts[0].strip()
    if not re.fullmatch(r"[\u4e00-\u9fa5]{2,15}", candidate):
        return None, "文件名首段必须为中文姓名"
    return candidate, ""
```

### 5.3 `extract_author_and_match_department()`

定义位置：`backend/app/api/reports.py`

**输入：`original_filename, db

**流程：

1. 调用 `extract_author_from_filename()` 解析姓名。
2. 在 persons 表精确匹配 `person.name == candidate_name。
3. 命中但无 `matched_person.department_name 为空 → detected=False。
4. 未命中 → detected=False。

**返回：

```
(name, department, person_id, department_id, detected)
```

**改造点：`file_path`/`parsed_content` 参数已移除，因为识别逻辑完全迁移到文件名，不再从文件内容识别。

### 5.4 `upload_report()`

**核心改动：

* docstring 更新为「仅支持 .xlsx」。
* `person_id 未指定时，强制从文件名识别；未命中 persons 或部门缺失 → HTTP 400 并删除临时文件。

```python
if not person_id:
    detected_name, detected_dept, detected_person_id, detected_dept_id, detected = (
        await extract_author_and_match_department(original_filename, db)
    )
    if not detected:
        os.remove(file_path)
        raise HTTPException(400, f"系统中无员工信息：{detected_name}")
    if not detected_dept:
        os.remove(file_path)
        raise HTTPException(400, f"系统中无员工信息：{detected_name}（未配置部门）")
    author_name = detected_name
    department = detected_dept
    person_id = detected_person_id
    department_id = detected_dept_id
```

## 6. 数据库模型依赖

```sql
-- 核心表：
* persons：人员库（必须为每位员工一条记录，person.name 精确匹配。
* departments：部门表。

weekly_reports：周报记录（author_name/department/person_id/department_id）
report_scores：评分结果
```

**persons 表约定：
* `name`：字符串，精确匹配文件名首段。
* `department_name`：必填（非空），不允许空部门（无部门的员工不允许上传）。
* `department_id`：可空（为便于关联 departments 表主键。

## 7. 前端改造详情

### 7.1 PublicHome.vue

* `acceptFormats = '.xlsx'（input accept 属性）

* 拖拽 `onDrop` 校验：`/\.xlsx$/`

* 提示文案：「仅支持 .xlsx 格式，文件名需为「姓名-YYYY年MM月第N周周报YYYYMMDD.xlsx」

### 7.2 WriteReport.vue

同上，保持一致。

## 8. 接口契约

### POST `/api/v1/reports/upload

**请求：

* `file`（form-data，仅 .xlsx）

**响应：

成功（HTTP 200）：
```json
{
  "message": "本周周报上传成功",
  "report_id": "uuid",
  "week_start": "2026-06-08",
  "week_end": "2026-06-14",
  "author_name": "张三",
  "department": "研发部",
  "person_id": "uuid",
  "department_id": "uuid",
  "total_score": 31.0,
  "grade": "差",
  "dimension_scores": [...],
  "ai_comment": "...",
  "ai_suggestion": "...",
  "auto_detected": true
}
```

失败（HTTP 400）：
```json
{ "detail": "系统中无员工信息：XXX" }
{ "detail": "不支持的文件格式: .docx，仅支持 .xlsx 文件" }
{ "detail": "文件名不符合规范..." }
```

## 9. 测试用例

| 用例 | 输入 | 预期 |
|---|---|---|
| TC-001 | 符合规范 + persons 命中 | `张三-2026年6月第2周周报20260614.xlsx，张三在 persons 中，部门为研发部 |
| TC-002 | persons 未命中 | `李四-2026年6月第2周周报20260614.xlsx，李四不在 persons 中 → HTTP 400 |
| TC-003 | 无部门的员工 | `王五-2026年6月第2周周报20260614.xlsx，王五在 persons 但 department_name 为空 → HTTP 400 |
| TC-004 | 非 xlsx 扩展名 | `张三-2026年6月第2周周报20260614.docx → HTTP 400 |
| TC-005 | 姓名非中文 | `zhang3-2026年6月第2周周报20260614.xlsx → HTTP 400 |
| TC-006 | 文件名无「-」 | `张三周报20260614.xlsx → HTTP 400 |
| TC-007 | 文件名仅后缀名但姓名超长 | `张三丰XXXXX（超 15 位中文）...xlsx → HTTP 400 |
| TC-008 | 文件名含全角「—」 | `张三—2026年6月第2周周报20260614.xlsx → 自动兼容为英文「-」，正常识别 |

## 10. 操作说明

* 旧版 `extract_author_and_match_department(file_path, original_filename, parsed_content, db)` 中不再接受四个参数，现改为 `(original_filename, db)` 两个。旧函数签名已变更；调用方 `reports.py` 中 `upload_report` 已同步修改。

* 旧版从文件内容识别（metadata 读取、工作项「汇报人列）均已停用，改为仅从文件名识别。

* 旧版 docx / pdf 解析函数保留为 `_parse_docx`/`_extract_dates_from_docx` 等已从 `document_parser.py` 移除（原位置已停用。

* 前端不再使用 `from app.services.document_parser.SUPPORTED_EXTENSIONS` 仅包含 `.xlsx`。

## 11. 异常提示

* 用户在前端显示：
- 拖拽或点击上传的文件格式不符合规范时：
- 后端返回中文错误信息：`系统中无员工信息：XXX，请联系管理员添加员工；或：`系统中无员工信息：XXX（未配置部门）。

* 前端 toast 消息由 `reports.py` 在 `upload_report` 中通过 `toast.add({ severity: 'error', summary: msg, life: 4000 })` 展示。

---

**文档结束。
