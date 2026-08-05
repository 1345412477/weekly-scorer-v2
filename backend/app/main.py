"""智友辰周任务汇总系统 - FastAPI 主入口"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException as FastAPIHTTPException
from contextlib import asynccontextmanager
from starlette.responses import JSONResponse
import os
import time
import asyncio

from app.database import init_db
from app.config import get_settings
from app.api import auth, config, templates, reports, leaderboard, departments, persons
from app.api import weeklysummary, attendance, chat, weekly_aggregates, business_summary, ai_models, assessment
from app.utils.logger import log_api_request, log_info, log_error

settings = get_settings()

# 启动状态标记：后台初始化完成后设为 True
_startup_ready = False


def get_cors_origins():
    return [origin.strip() for origin in settings.CORS_ALLOW_ORIGINS.split(",") if origin.strip()]


async def _run_background_init():
    """后台执行所有初始化，不阻塞服务启动"""
    global _startup_ready
    try:
        log_info("后台初始化开始...")
        await init_db()
        await seed_default_data()
        try:
            from app.core.task_queue import init_scheduler
            await init_scheduler()
            log_info("定时聚合评分调度器已就绪")
        except Exception as e:
            log_info(f"调度器初始化失败（不影响核心功能）: {e}")
        _startup_ready = True
        log_info("系统初始化完成")
    except Exception as e:
        log_error(f"后台初始化失败: {e}")
        _startup_ready = True  # 标记为 ready，避免 health 一直返回初始化中


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_info("启动智友辰周任务汇总系统...")
    # 立即启动后台初始化，不阻塞 lifespan yield
    asyncio.create_task(_run_background_init())
    yield
    try:
        from app.core.task_queue import shutdown_scheduler
        await shutdown_scheduler()
    except Exception:
        pass
    log_info("系统关闭")


app = FastAPI(
    title="智友辰周任务汇总系统",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """请求日志中间件"""
    start_time = time.time()
    method = request.method
    path = request.url.path
    
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as e:
        status_code = 500
        raise
    finally:
        duration_ms = (time.time() - start_time) * 1000
        log_api_request(path, method, status_code, duration_ms)
    
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """验证异常处理 - 保留 Pydantic 原生 errors，前端可解析字段级别错误"""
    try:
        body_bytes = await request.body()
        body_text = body_bytes.decode("utf-8", errors="replace") if body_bytes else "(empty)"
    except Exception:
        body_text = "(unreadable)"
    errors = []
    for error in exc.errors():
        errors.append({"loc": list(error["loc"]), "msg": error["msg"], "type": error.get("type", "")})
    # 打印到后端日志，便于在现场精准定位哪一个字段缺失
    print(f"[VALIDATION_ERROR] {request.method} {request.url.path} | body={body_text} | errors={errors}")
    return JSONResponse(
        status_code=400,
        content={"detail": errors}
    )


@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    """显式 HTTPException（如 401/403/404）统一为 JSON 响应，避免 FastAPI 默认 HTML"""
    detail = exc.detail if isinstance(exc.detail, (str, list, dict)) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """兜底异常处理器：任何未捕获异常返回 JSON 500，而不是 FastAPI 默认 HTML 页面"""
    detail = str(exc)
    if len(detail) > 300:
        detail = detail[:300] + "..."
    log_error(f"[UNHANDLED] {request.method} {request.url.path} -> {type(exc).__name__}: {detail}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"服务器内部错误：{detail}",
            "type": type(exc).__name__,
        },
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(config.router)
app.include_router(templates.router)
app.include_router(reports.router)
app.include_router(leaderboard.router)
app.include_router(departments.router)
app.include_router(persons.router)
app.include_router(weeklysummary.router)
app.include_router(attendance.router)
app.include_router(chat.router)
app.include_router(weekly_aggregates.router)
app.include_router(business_summary.router)
app.include_router(ai_models.router)
app.include_router(assessment.router)

# 员工端首页联合上传接口（周报 + 一周小结，统一使用周报识别姓名）
from app.api.upload_unified import router as upload_unified_router
app.include_router(upload_unified_router)

# 管理端统一评分入口（所有上传均在此处集中评分）
from app.api.scoring_run import router as scoring_run_router
app.include_router(scoring_run_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION, "ready": _startup_ready}


# 静态文件 (前端构建产物)
dist_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "frontend", "dist"))
if os.path.exists(dist_path):
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=os.path.join(dist_path, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        requested_path = os.path.abspath(os.path.join(dist_path, full_path))
        if requested_path.startswith(dist_path + os.sep) and os.path.isfile(requested_path):
            return FileResponse(requested_path)
        return FileResponse(os.path.join(dist_path, "index.html"))


async def seed_default_data():
    """初始化默认数据"""
    from app.database import async_session
    from app.core.auth import ensure_default_admin
    from app.models.models import ScoringConfig, ReportTemplate
    from sqlalchemy import select
    import uuid

    async with async_session() as db:
        await ensure_default_admin(db)
        # 默认评分配置
        result = await db.execute(select(ScoringConfig).limit(1))
        if not result.scalar_one_or_none():
            default_config = ScoringConfig(
                id=str(uuid.uuid4()),
                name="默认评分配置",
                dimensions=[
                    {"name": "工作反馈深度", "full_score": 14, "evaluation_content": "问题发现+分析+解决方案"},
                    {"name": "进度节点明确", "full_score": 13, "evaluation_content": "项目是否有明确进度/节点"},
                    {"name": "计划可行性", "full_score": 10, "evaluation_content": "下周计划是否具体可执行"},
                    {"name": "工作连续性", "full_score": 13, "evaluation_content": "是否承接上周计划且有闭环"},
                ],
                grade_thresholds={"优": 45, "良": 38, "一般": 33, "差": 28},
                summary_prompt='你是一位专业的沟通评分专家。请对员工的一周小结进行评分（满分20分）。\n\n## 扣分规则\n- 工作会话次数 >= 300：不扣分\n- 300 > 工作会话次数 >= 200：扣5分\n- 200 > 工作会话次数 >= 100：扣10分\n- 工作会话次数 < 100：扣15分\n- 最晚时间在晚上6点（18:00）之前：扣5分\n\n一周小结得分 = max(0, 20 - 以上扣分总和)\n\n## 输出要求\n请严格以 JSON 格式返回，不要额外文字：\n{"score": 一周小结得分(0-20), "comment": "简短点评（说明扣分原因）"}',
                business_summary_prompt='你是一位资深的项目管理分析师，擅长从周报中提炼项目全景、归并子任务、识别重点项目并评估进度。\n\n## 任务目标\n\n根据部门员工提交的周报内容，按**项目维度**进行高度归并，将零散的子任务/功能点/工作项聚类为完整的项目，区分**上周已完成**与**本周进行中**的项目。\n\n## 核心原则：先归并，再输出\n\n周报中的 `### N. xxx` 标题通常是**子任务或功能模块**，不是项目名。你必须将这些子任务归并到所属项目下。\n\n### 归并规则（必须严格遵守）\n\n1. **同一系统的子模块 → 归并为一个项目**\n   - 例：「AI评分引擎」「系统监控」「安全加固」「性能优化」→ 归并为「考勤评分系统」\n   - 例：「赢筑小程序」「消息推送」「性能优化」「单元测试」→ 归并为「赢筑小程序」\n   - 例：「前端开发」「代码优化」「Bug修复」→ 归并为所属项目名（如「考勤评分系统」或「赢筑小程序」）\n\n2. **同一客户/产品的不同工作 → 归并为一个项目**\n   - 例：「YY客户上线实施」「YY客户操作培训」「客户响应机制建设」→ 归并为「YY客户上线项目」\n   - 例：「XX客户运维支持」→ 归并为「XX客户运维项目」\n\n3. **同一产品生命周期的工作 → 归并为一个项目**\n   - 例：「产品规划」「用户调研」「原型设计」「需求文档」→ 归并为「产品规划与调研」\n\n4. **通用/杂项工作 → 归并为「基础建设与优化」**\n   - 例：「文档整理」「学习培训」「技术文档」「代码评审」→ 归并为「基础建设与优化」\n   - 这类工作通常不涉及具体项目交付，作为兜底分类\n\n5. **跨人员协作 → 必须合并为一条**\n   - 不同员工参与同一项目的不同模块，必须合并为一条项目记录，persons 列出所有参与者\n\n### 归并示例\n\n假设研发部有以下周报内容：\n- 员工A：### 1. AI评分引擎 / ### 2. 系统监控 / ### 3. 安全加固\n- 员工B：### 1. 考勤评分系统 / ### 2. 业务盘功能 / ### 3. 技术文档\n- 员工C：### 1. 前端开发 / ### 2. 代码优化 / ### 3. Bug修复\n\n正确归并结果（2个项目）：\n- 「考勤评分系统」：包含AI评分引擎、系统监控、安全加固、业务盘功能、前端开发、代码优化、Bug修复（A+B+C参与）\n- 「基础建设与优化」：包含技术文档（B参与）\n\n错误做法（7个独立项目）：\n- AI评分引擎、系统监控、安全加固、考勤评分系统、业务盘功能、前端开发、代码优化... ← 这是把子任务当项目\n\n## 输出格式\n\n请严格按照以下 JSON 格式输出，不要包含其他内容：\n\n```json\n{\n  "last_week_projects": [\n    {\n      "name": "项目名称",\n      "progress": 100,\n      "highlight": true,\n      "summary": "精炼描述",\n      "persons": ["张三", "李四"]\n    }\n  ],\n  "this_week_projects": [\n    {\n      "name": "项目名称",\n      "progress": 60,\n      "highlight": false,\n      "summary": "精炼描述",\n      "persons": ["张三"]\n    }\n  ]\n}\n```\n\n## 字段定义\n\n| 字段 | 说明 |\n|------|------|\n| **name** | 归并后的项目名称（不超过15字）。不是子任务名，是所属的系统/产品/客户项目名 |\n| **progress** | 进度百分比（0-100）。评估标准：已完成/已上线/已交付=100；联调/测试中=70-90；开发中=40-70；设计/调研中=10-30；未启动=0 |\n| **highlight** | 是否重点项目（true/false）。满足任一条件即为重点：①跨人员协作（≥2人）②核心业务/营收相关系统 ③涉及架构升级或技术攻坚 ④有明确里程碑交付 |\n| **summary** | 精炼描述（30-80字），必须包含：①做了什么 ②关键成果/数据 ③当前状态。避免空泛描述 |\n| **persons** | 参与该项目的所有人员姓名（去重） |\n\n## 输出约束\n\n1. 每个周期的项目数量控制在 **2-5个**，超过说明归并不够\n2. 禁止将子任务/功能模块作为独立项目输出\n3. 通用/杂项工作统一归入「基础建设与优化」\n4. 若某周期无有效项目信息，对应数组返回空数组 `[]`\n\n## 上下文信息\n\n- 部门名称：{department}\n- 统计周期：{week_label}\n\n## 员工周报内容\n\n{reports}\n\n请输出 JSON 格式的项目总结（先归并，再输出）：',
                min_content_length=50,
                is_active=True,
                report_prompt=(
                    '# 周报评分提示词\n\n请根据员工提交的周报在 28-40 分范围进行评分。\n\n## 评分维度\n\n### 1. 工作反馈深度（满分12分，最低分8分）\n评估员工对本周工作内容的总结深度和问题分析能力。\n- **高分标准（12分）**：不仅罗列工作内容，还能深入分析遇到的问题、产生的原因，并提出具体的解决方案或改进思路；有数据支撑或量化成果。\n- **中等标准（10分）**：对工作内容有基本总结，提及了部分问题但分析不够深入，解决方案较笼统。\n- **低分标准（8分）**：仅简单罗列工作内容，缺乏问题分析，未提及遇到的困难或解决思路。\n\n### 2. 进度节点明确（满分11分，最低分7分）\n评估员工对项目/任务进度的描述是否清晰、是否有明确的里程碑或时间节点。\n- **高分标准（11分）**：清晰描述各任务的当前进度（如百分比、完成阶段），标注关键里程碑和预期完成时间，进度描述具体可追踪。\n- **中等标准（9分）**：有进度描述但较笼统，如"进行中""已完成部分"，缺少具体时间节点。\n- **低分标准（7分）**：未提及进度或进度描述模糊，无法判断任务实际推进情况。\n\n### 3. 计划可行性（满分8分，最低分6分）\n评估员工对下周工作计划的描述是否具体、可执行、可验证。\n- **高分标准（8分）**：下周计划具体明确，包含可量化的目标、清晰的执行步骤和预期交付物，计划合理可落地。\n- **中等标准（7分）**：有下周计划但较笼统，如"继续推进XX项目"，缺少具体目标或执行细节。\n- **低分标准（6分）**：未提及下周计划，或计划过于空泛无法执行。\n\n### 4. 工作连续性（满分10分，最低分7分）\n评估员工本周工作是否承接上周计划，是否形成"计划→执行→结果→新计划"的闭环。\n- **高分标准（9分）**：本周工作明确承接上周计划，对上周未完成事项有跟进说明，形成完整的工作闭环；新计划与本周结果有逻辑关联。\n- **中等标准（8分）**：部分承接上周计划，但对未完成事项缺乏跟进，闭环不够完整。\n- **低分标准（7分）**：本周工作与上周计划无明显关联，或完全未提及上周计划的执行情况。\n\n## 等级划分\n- 优：35-40分\n- 良：31-34分\n- 一般：29-30分\n- 差：28分\n\n## 输出要求\n请以 JSON 格式返回：\n- dimension_scores（每项含name/score/max/comment）\n- total_score（各维度相加，范围28-40）\n- grade（优/良/一般/差）\n- comment（总体评语，100字以内）\n- suggestion（改进建议，具体可执行）\n\n## 周报内容\n{content}'
                ),
                attendance_prompt=(
                    '# 考勤评分提示词\n\n你是考勤评分专家。请根据员工本周的考勤打卡数据，按以下规则评分。\n\n## 评分规则（基础分 100 分，纯扣分制，最低 0 分；加班分在基础分之上累加，不设上限）\n\n1. 全勤判定（以周为单位，仅统计工作日；周六/周日休息日不计入）：\n   - 全勤：每个工作日都有上班和下班打卡，且无迟到、缺卡、请假等异常。\n   - 非全勤：本周内出现迟到、缺卡、请假、旷工等任一异常 → 扣 3 分（每周一次性）。\n   - 出差视为全勤，不扣分；状态文本包含「正常」（如 正常、正常(外出打卡)、正常(补卡)、正常(审批打卡)）均视为正常。\n\n2. 迟到：每次迟到扣 5 分（状态文本含「迟到」即计 1 次，迟到 1 分钟也扣）。\n3. 缺卡：工作日当天上班或下班任一时间缺失记 1 次缺卡，每次扣 5 分；\n   若当天上班与下班都缺失，只记 1 次缺卡（不重复计 2 次），并同时按非全勤扣 3 分。\n4. 请假、旷工等其他异常：计入非全勤扣 3 分；涉及缺卡的仍按规则 3 叠加扣分。\n5. 加班分（当日加班总时长不足 1 小时不计分；有加班时才有加班打卡数据）：\n   - 工作日：以下班打卡时间从 18:00 起计算加班时长，只有完整跨满区间才加分，跨满后按档累加：\n     - 加班满 1 小时（下班 ≥ 19:00）：加 2 分\n     - 加班满 2 小时（下班 ≥ 20:00）：再加 1 分\n     - 加班满 4 小时（下班 ≥ 22:00）：再加 1 分\n   - 非工作日（周六/周日，以当天有打卡记录为准）：\n     - 全天投入（上班到下班 ≥6 小时）加 3 分\n     - 半天投入（≥3 小时）加 2 分\n   - 示例：工作日下班 19:01 → 只加 2 分；下班 20:30 → 加 2+1=3 分；下班 22:10 → 加 2+1+1=4 分；下班 18:30（不足1小时）→ 0 分。\n\n## 输出要求\n请严格以 JSON 格式返回，不要额外文字：\n{"score": 最终得分(基础分-扣分+加班分，可超过100), "full_attendance": true/false, "late_count": 迟到次数, "missing_count": 缺卡次数, "overtime_points": 加班分, "comment": "简短点评（说明扣分与加班加分原因）"}'
                ),
                chat_prompt=(
                    '你是一位专业的沟通评分专家。请对员工的会话记录进行评分（满分80分）。\n\n## 扣分规则\n- 敏感词检测：每出现一次敏感词扣10分\n- 响应时间：\n  - 工作日（周一至周五）9:00-18:00：5分钟内回复不扣分，超过5分钟或不回复扣5分\n  - 非工作日（周六、周日）及其他非工作时间：10分钟内回复不扣分，超过10分钟或不回复扣5分\n\n会话记录得分 = max(0, 80 - 以上扣分总和)\n\n## 输出要求\n请严格以 JSON 格式返回，不要额外文字：\n{"score": 会话记录得分(0-80), "comment": "简短点评（说明扣分原因）"}'
                ),
                ocr_prompt=(
                    '你是一个精准的 OCR 解析助手。用户会上传一张「一周小结」的图片，\n请从图片内容中提取以下字段并严格以 JSON 格式输出：\n- author_name: 员工姓名（字符串）\n- work_session_count: 本周处理的工作会话次数（整数，**必须识别，例如「共 12 次会话」「12 次会话」「处理了 12 次会话」等字样中的数字）\n- total_minutes: 本周工作总耗时（分钟，整数；若无法识别则 null）\n- latest_time: 最晚工作时间原文（字符串，如「22:35」或「周一 22:35」）\n- week_start: 本周周一日期（YYYY-MM-DD；若图片未明确给出则填 null）\n- week_end: 本周周日日期（YYYY-MM-DD；若图片未明确给出则填 null）\n注意：\n- 必须严格输出 JSON，不要额外文字；\n- 若图片中没有姓名（例如仅有「一周小结」字样）则 work_session_count 必须返回 null，不要编造；\n- 只输出一个 JSON 对象，不要包含说明文字。'
                ),
            )
            db.add(default_config)

        # 默认模板
        result2 = await db.execute(select(ReportTemplate).limit(1))
        if not result2.scalar_one_or_none():
            default_template = ReportTemplate(
                id=str(uuid.uuid4()),
                name="标准周报模板",
                description="包含本周工作、下周计划、问题风险的标准模板",
                content="""## 本周工作内容

### 1. {项目名称}
- 工作内容：
- 完成情况：
- 产出/成果：

### 2. {项目名称}
- 工作内容：
- 完成情况：
- 产出/成果：

## 下周工作计划

### 1. {项目名称}
- 计划内容：
- 预期产出：

## 问题与风险
- 

## 需要协助的事项
- """,
                fields=[
                    {"key": "project", "label": "项目名称", "type": "text", "required": True, "placeholder": "输入项目名称"},
                    {"key": "work_content", "label": "工作内容", "type": "textarea", "required": True, "placeholder": "描述本周工作内容"},
                    {"key": "completion", "label": "完成情况", "type": "textarea", "required": True, "placeholder": "说明完成进度"},
                    {"key": "output", "label": "产出/成果", "type": "textarea", "required": False, "placeholder": "量化产出成果"},
                ],
                is_default=True,
            )
            db.add(default_template)

        await db.commit()
