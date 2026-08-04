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
                min_content_length=50,
                is_active=True,
                report_prompt=(
                    "你是一位专业的工作报告评审专家。请根据评分维度对周报进行客观、公正的评分。\n\n"
                    "评分规则：\n"
                    "1. 每个维度按指定满分评分（各维度满分之和=50分）\n"
                    "2. 总分 = 各维度分数直接相加（范围0-50分）\n"
                    "3. 每个维度的分数不得超过该维度的满分\n"
                    "4. 每个维度必须给出具体分数和简短评价\n"
                    "5. 总体评语需指出优点和待改进点\n"
                    "6. 评分要客观，鼓励高质量、有量化数据的周报\n"
                    "7. 等级标准：优(≥45)、良(≥38)、一般(≥33)、差(≥28)\n"
                    "8. 严格按 JSON 格式返回结果"
                ),
                attendance_prompt=(
                    "# 考勤评分提示词\n\n"
                    "你是考勤评分专家。请根据员工本周的考勤打卡数据，按以下扣分制规则评分。\n\n"
                    "## 评分规则（总分 100 分，纯扣分制，最低 0 分）\n"
                    "1. 全勤判定（以周为单位，仅统计工作日；周六/周日休息日不计入）：\n"
                    "   - 全勤：每个工作日都有上班和下班打卡，且无迟到、缺卡、请假等异常。\n"
                    "   - 非全勤：本周内出现迟到、缺卡、请假、旷工等任一异常 → 扣 3 分（每周一次性）。\n"
                    "   - 出差视为全勤，不扣分；状态文本包含「正常」（如 正常、正常(外出打卡)、"
                    "正常(补卡)、正常(审批打卡)）均视为正常。\n"
                    "2. 迟到：每次迟到扣 5 分（状态文本含「迟到」即计 1 次，迟到 1 分钟也扣）。\n"
                    "3. 缺卡：工作日当天上班或下班任一时间缺失记 1 次缺卡，每次扣 10 分；\n"
                    "   若当天上班与下班都缺失，只记 1 次缺卡（不重复计 2 次），"
                    "并同时按非全勤扣 3 分。\n"
                    "4. 请假、旷工等其他异常：计入非全勤扣 3 分；涉及缺卡的仍按规则 3 叠加扣分。\n"
                    "5. 加班分（预留，当前版本不计算）：后续若提供加班时长，"
                    "将在 100 分基础上额外加分，本轮输出 score 仍为 0-100。\n\n"
                    "## 输出要求\n"
                    "请严格以 JSON 格式返回，不要额外文字：\n"
                    '{"score": 总分(0-100), "full_attendance": true/false, '
                    '"late_count": 迟到次数, "missing_count": 缺卡次数, '
                    '"comment": "简短点评（说明扣分原因）"}'
                ),
                chat_prompt=(
                    "你是一位专业的沟通评分专家。请对员工的沟通表现进行评分。\n\n"
                    "评分由两部分组成，独立评分后相加：\n"
                    "1. 一周小结评分（满分20分）：\n"
                    "   - 工作会话次数 >= 300：不扣分\n"
                    "   - 300 > 工作会话次数 >= 200：扣5分\n"
                    "   - 200 > 工作会话次数 >= 100：扣10分\n"
                    "   - 工作会话次数 < 100：扣15分\n"
                    "   - 最晚时间在晚上6点（18:00）之前：扣5分\n"
                    "   一周小结得分 = max(0, 20 - 以上扣分总和)\n\n"
                    "2. 会话记录评分（满分80分）：\n"
                    "   - 敏感词检测：每出现一次敏感词扣10分\n"
                    "   - 响应时间：\n"
                    "     - 工作日（周一至周五）9:00-18:00：5分钟内回复不扣分，超过5分钟或不回复扣5分\n"
                    "     - 非工作日、非工作时间：10分钟内回复不扣分，超过10分钟或不回复扣5分\n"
                    "   会话记录得分 = max(0, 80 - 以上扣分总和)\n\n"
                    "最终得分 = 一周小结得分 + 会话记录得分（0-100分）\n\n"
                    "## 输出要求\n"
                    '请严格以 JSON 格式返回，不要额外文字：\n'
                    '{"score": 总分(0-100), "summary_score": 一周小结得分(0-20), '
                    '"records_score": 会话记录得分(0-80), "comment": "简短点评（说明扣分原因）"}'
                ),
                ocr_prompt=(
                    "你是一个精准的 OCR 解析助手。用户会上传一张「一周小结」的图片，\n"
                    "请从图片内容中提取以下字段并严格以 JSON 格式输出：\n"
                    "- author_name: 员工姓名（字符串）\n"
                    "- work_session_count: 本周处理的工作会话次数（整数，必须识别）\n"
                    "- total_minutes: 本周工作总耗时（分钟，整数；若无法识别则 null）\n"
                    "- latest_time: 最晚工作时间原文（字符串，如「22:35」或「周一 22:35」）\n"
                    "- week_start: 本周周一日期（YYYY-MM-DD；若图片未明确给出则填 null）\n"
                    "- week_end: 本周周日日期（YYYY-MM-DD；若图片未明确给出则填 null）\n"
                    "注意：\n"
                    "- 必须严格输出 JSON，不要额外文字；\n"
                    "- 若图片中没有姓名则 work_session_count 必须返回 null，不要编造；\n"
                    "- 只输出一个 JSON 对象，不要包含说明文字。"
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
