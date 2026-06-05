"""周报评分系统 v2 - FastAPI 主入口"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from starlette.responses import JSONResponse
import os
import time

from app.database import init_db
from app.api import config, templates, reports, leaderboard, departments, persons
from app.utils.logger import log_api_request, log_info


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_info("启动周报评分系统 v2...")
    await init_db()
    await seed_default_data()
    log_info("系统初始化完成")
    yield
    log_info("系统关闭")


app = FastAPI(
    title="周报评分系统 v2",
    version="2.0.0",
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
    """验证异常处理"""
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append(f"{field}: {error['msg']}")
    return JSONResponse(
        status_code=400,
        content={"detail": "请求参数验证失败", "errors": errors}
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(config.router)
app.include_router(templates.router)
app.include_router(reports.router)
app.include_router(leaderboard.router)
app.include_router(departments.router)
app.include_router(persons.router)

# 静态文件 (前端构建产物)
dist_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "frontend", "dist")
if os.path.exists(dist_path):
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=os.path.join(dist_path, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = os.path.join(dist_path, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(dist_path, "index.html"))


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


async def seed_default_data():
    """初始化默认数据"""
    from app.database import async_session
    from app.models.models import ScoringConfig, ReportTemplate
    from sqlalchemy import select
    import uuid

    async with async_session() as db:
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
