"""数据模型"""
import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, Text, DateTime, Date, DECIMAL, Boolean, Integer, JSON, Index
from app.database import Base


class Department(Base):
    """部门信息"""
    __tablename__ = "departments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Person(Base):
    """人员信息"""
    __tablename__ = "persons"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(50), nullable=False)
    department_id = Column(String(36), nullable=True)
    department_name = Column(String(100), nullable=True, default="")
    position = Column(String(100), nullable=True, default="")
    email = Column(String(200), nullable=True, default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ScoringConfig(Base):
    """评分规则配置 - 全局唯一"""
    __tablename__ = "scoring_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, default="默认配置")
    dimensions = Column(JSON, nullable=False, default=list)
    # 示例: [{"name": "工作反馈深度", "full_score": 14, "highest_score": null, "lowest_score": null, "evaluation_content": "问题发现+分析+解决方案"}]
    grade_thresholds = Column(JSON, nullable=False, default=dict)
    # 示例: {"优": 45, "良": 38, "一般": 33, "差": 28}
    prompt_template = Column(Text, nullable=True, default="")
    min_content_length = Column(Integer, default=50)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ReportTemplate(Base):
    """周报模板"""
    __tablename__ = "report_templates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True, default="")
    content = Column(Text, nullable=False)  # 模板内容(Markdown)
    fields = Column(JSON, nullable=True, default=list)
    # 示例: [{"key": "project", "label": "项目名称", "type": "text", "required": true}, ...]
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WeeklyReport(Base):
    """周报记录"""
    __tablename__ = "weekly_reports"
    __table_args__ = (
        Index("idx_weekly_reports_status", "status"),
        Index("idx_weekly_reports_week_start", "week_start"),
        Index("idx_weekly_reports_person_id", "person_id"),
        Index("idx_weekly_reports_department", "department"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    author_name = Column(String(50), nullable=False, default="匿名")
    department = Column(String(50), nullable=True, default="")
    person_id = Column(String(36), nullable=True)
    department_id = Column(String(36), nullable=True)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    content = Column(Text, nullable=False)
    file_path = Column(String(500), nullable=True)
    original_filename = Column(String(200), nullable=True)
    template_id = Column(String(36), nullable=True)
    status = Column(String(20), default="draft")  # draft / submitted / scored
    report_type = Column(String(20), default="normal")  # normal / catch_up / unknown
    week_diff = Column(Integer, default=0)
    submit_time = Column(DateTime, nullable=True)
    score_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ReportScore(Base):
    """评分结果"""
    __tablename__ = "report_scores"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(String(36), nullable=False, unique=True, index=True)
    dimension_scores = Column(JSON, nullable=True, default=list)
    # 示例: [{"name": "工作闭环", "score": 85, "max": 100, "weight": 40, "comment": "..."}]
    total_score = Column(DECIMAL(5, 1), nullable=True)
    grade = Column(String(2), nullable=True)
    ai_comment = Column(Text, nullable=True)
    ai_suggestion = Column(Text, nullable=True)
    raw_response = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AdminUser(Base):
    """管理员账号"""
    __tablename__ = "admin_users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), nullable=False, unique=True, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(20), nullable=False, default="admin")
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class OperationLog(Base):
    """管理员敏感操作日志"""
    __tablename__ = "operation_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False)
    username = Column(String(50), nullable=False)
    action = Column(String(50), nullable=False)
    resource = Column(String(100), nullable=False)
    resource_id = Column(String(100), nullable=True, default="")
    detail = Column(JSON, nullable=True, default=dict)
    ip_address = Column(String(100), nullable=True, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
