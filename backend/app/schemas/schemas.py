"""Pydantic Schemas"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any
from datetime import date


class LoginRequest(BaseModel):
    model_config = {"extra": "allow"}
    username: str
    password: str


# ── 部门 ──
class DepartmentCreate(BaseModel):
    model_config = {"extra": "allow"}
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = ""


class DepartmentUpdate(BaseModel):
    model_config = {"extra": "allow"}
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None


class DepartmentResponse(BaseModel):
    model_config = {"extra": "allow"}
    id: str
    name: str
    description: str
    created_at: Optional[str] = None


# ── 人员 ──
class PersonCreate(BaseModel):
    model_config = {"extra": "allow"}
    name: str = Field(..., min_length=1, max_length=50)
    department_id: Optional[str] = None
    department_name: Optional[str] = ""
    position: Optional[str] = ""
    email: Optional[str] = ""

    @field_validator("name", mode="before")
    @classmethod
    def name_not_empty(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            raise ValueError("姓名不能为空")
        return v.strip() if isinstance(v, str) else v


class PersonUpdate(BaseModel):
    model_config = {"extra": "allow"}
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    position: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("name", mode="before")
    @classmethod
    def name_not_empty(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            raise ValueError("姓名不能为空")
        return v.strip() if isinstance(v, str) else v

    @field_validator("department_id", "department_name", "position", "email", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v


class PersonResponse(BaseModel):
    model_config = {"extra": "allow"}
    id: str
    name: str
    department_id: Optional[str] = None
    department_name: str
    position: str
    email: str
    is_active: bool
    created_at: Optional[str] = None


# ── 评分维度 ──
class DimensionConfig(BaseModel):
    model_config = {"extra": "allow"}
    name: str = Field(..., min_length=1, max_length=50, description="维度名称")
    full_score: float = Field(..., gt=0, le=100, description="满分")
    highest_score: Optional[float] = Field(None, ge=0, description="最高分")
    lowest_score: Optional[float] = Field(None, ge=0, description="最低分")
    evaluation_content: str = Field("", max_length=500, description="考核内容")

    @field_validator("name", mode="before")
    @classmethod
    def name_must_present(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            raise ValueError("维度名称不能为空")
        return v.strip()

    @field_validator("full_score", mode="before")
    @classmethod
    def score_must_be_valid(cls, v):
        if v is None or v == "":
            raise ValueError("满分不能为空")
        try:
            fv = float(v)
            if fv <= 0 or fv > 100:
                raise ValueError("满分必须在 0 到 100 之间")
            return fv
        except (TypeError, ValueError) as e:
            if isinstance(e, ValueError) and "满分" in str(e):
                raise
            raise ValueError(f"满分必须是有效数字: {v}")

    @field_validator("highest_score", "lowest_score", mode="before")
    @classmethod
    def optional_score_valid(cls, v):
        if v is None or v == "":
            return None
        try:
            fv = float(v)
            if fv < 0:
                raise ValueError("分数不能为负数")
            return fv
        except (TypeError, ValueError) as e:
            if isinstance(e, ValueError) and "不能为负" in str(e):
                raise
            raise ValueError(f"必须是数字: {v}")

    @property
    def weight(self) -> float:
        """兼容旧代码的 weight 属性"""
        return self.full_score


# ── 配置 ──
class ConfigResponse(BaseModel):
    model_config = {"extra": "allow"}
    id: Optional[str] = None
    name: str = "默认配置"
    dimensions: List[DimensionConfig] = []
    total_full_score: float = 0  # 自动计算：各维度满分之和
    grade_thresholds: dict = {"优": 45, "良": 38, "一般": 33, "差": 28}
    prompt_template: str = ""
    min_content_length: int = 50

    def model_post_init(self, __context) -> None:
        """自动计算总满分"""
        self.total_full_score = sum(d.full_score for d in self.dimensions)


class ConfigUpdate(BaseModel):
    model_config = {"extra": "allow"}
    name: Optional[str] = None
    dimensions: Optional[List[DimensionConfig]] = None
    grade_thresholds: Optional[dict] = None
    prompt_template: Optional[str] = None
    min_content_length: Optional[int] = None

    @field_validator("prompt_template", mode="before")
    @classmethod
    def prompt_empty_str_ok(cls, v):
        return v if v is not None else ""

    @field_validator("min_content_length", mode="before")
    @classmethod
    def min_length_valid(cls, v):
        if v is None or v == "":
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            raise ValueError("min_content_length 必须是整数")

    @property
    def total_full_score(self) -> float:
        """自动计算总满分"""
        if self.dimensions:
            return sum(d.full_score for d in self.dimensions)
        return 0


class TestScoreRequest(BaseModel):
    model_config = {"extra": "allow"}
    content: str
    dimensions: Optional[List[DimensionConfig]] = None
    prompt_template: Optional[str] = None


# ── 模板 ──
class TemplateField(BaseModel):
    model_config = {"extra": "allow"}
    key: str
    label: str
    type: str = "text"  # text / textarea / number
    required: bool = True
    placeholder: Optional[str] = ""


class TemplateCreate(BaseModel):
    model_config = {"extra": "allow"}
    name: str
    description: Optional[str] = ""
    content: str
    fields: Optional[List[TemplateField]] = []
    is_default: bool = False


class TemplateUpdate(BaseModel):
    model_config = {"extra": "allow"}
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    fields: Optional[List[TemplateField]] = None
    is_default: Optional[bool] = None


class TemplateResponse(BaseModel):
    model_config = {"extra": "allow"}
    id: str
    name: str
    description: str
    content: str
    fields: List[Any]
    is_default: bool
    created_at: Optional[str] = None


# ── 周报 ──
class ReportCreate(BaseModel):
    model_config = {"extra": "allow"}
    author_name: str = "匿名"
    department: Optional[str] = ""
    person_id: Optional[str] = None
    department_id: Optional[str] = None
    content: str
    week_start: Optional[date] = None
    week_end: Optional[date] = None
    template_id: Optional[str] = None


class ReportResponse(BaseModel):
    model_config = {"extra": "allow"}
    id: str
    author_name: str
    department: str
    person_id: Optional[str] = None
    department_id: Optional[str] = None
    week_start: str
    week_end: str
    content: str
    status: str
    total_score: Optional[float] = None
    grade: Optional[str] = None
    submit_time: Optional[str] = None
    score_time: Optional[str] = None
    created_at: Optional[str] = None


class ScoreDetail(BaseModel):
    model_config = {"extra": "allow"}
    name: str
    score: float
    max: float
    weight: float
    comment: Optional[str] = ""


class ReportDetailResponse(ReportResponse):
    dimension_scores: List[ScoreDetail] = []
    ai_comment: Optional[str] = None
    ai_suggestion: Optional[str] = None


class ReportListResponse(BaseModel):
    model_config = {"extra": "allow"}
    items: List[ReportResponse]
    total: int
    page: int
    size: int


# ── 排行榜 ──
class LeaderboardItem(BaseModel):
    model_config = {"extra": "allow"}
    rank: int
    author_name: str
    department: str
    avg_score: float
    total_score: float
    report_count: int
    latest_grade: Optional[str] = None


class LeaderboardResponse(BaseModel):
    model_config = {"extra": "allow"}
    rankings: List[LeaderboardItem]
    period: str
    total_reports: int
