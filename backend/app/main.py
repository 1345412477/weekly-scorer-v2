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

from app.database import init_db
from app.config import get_settings
from app.api import auth, config, templates, reports, leaderboard, departments, persons
from app.api import weeklysummary, attendance, chat, weekly_aggregates, business_summary, ai_models, assessment
from app.utils.logger import log_api_request, log_info, log_error

settings = get_settings()


def get_cors_origins():
    return [origin.strip() for origin in settings.CORS_ALLOW_ORIGINS.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_info("启动智友辰周任务汇总系统...")
    await init_db()
    await seed_default_data()
    # 启动后台定时聚合评分调度器
    try:
        from app.core.task_queue import init_scheduler, shutdown_scheduler
        await init_scheduler()
        log_info("定时聚合评分调度器已就绪")
    except Exception as e:
        log_info(f"调度器初始化失败（不影响核心功能）: {e}")
    log_info("系统初始化完成")
    yield
    try:
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
    return {"status": "ok", "version": settings.APP_VERSION}


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
