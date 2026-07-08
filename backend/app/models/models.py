"""数据模型"""
import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, Text, DateTime, Date, DECIMAL, Boolean, Integer, JSON, Index, UniqueConstraint
from app.database import Base
from app.utils.time_utils import bj_now


class Department(Base):
    """部门信息"""
    __tablename__ = "departments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True, default="")
    created_at = Column(DateTime, default=bj_now)


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
    created_at = Column(DateTime, default=bj_now)


class ScoringConfig(Base):
    """评分规则配置 - 全局唯一（v3：三项提示词 + 三项权重）"""
    __tablename__ = "scoring_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, default="默认配置")
    dimensions = Column(JSON, nullable=False, default=list)
    grade_thresholds = Column(JSON, nullable=False, default=dict)
    # 周报评分提示词（原 prompt_template，保留兼容字段）
    prompt_template = Column(Text, nullable=True, default="")
    # v3 新增：三项提示词
    report_prompt = Column(Text, nullable=True, default="")
    attendance_prompt = Column(Text, nullable=True, default="")
    chat_prompt = Column(Text, nullable=True, default="")
    # v4 新增：业务盘总结提示词
    business_summary_prompt = Column(Text, nullable=True, default="")
    # v3 新增：三项权重 JSON，默认 {"report": 1, "attendance": 1, "chat": 1}
    weights = Column(JSON, nullable=True, default=dict)
    min_content_length = Column(Integer, default=50)
    is_active = Column(Boolean, default=True)
    # AI 连接状态缓存（避免频繁检测产生 token 消耗）
    ai_connection_status = Column(Boolean, nullable=True)   # True=已连接 / False=连接失败 / None=未检测
    ai_connection_provider = Column(String(50), nullable=True)
    ai_connection_model = Column(String(100), nullable=True)
    ai_connection_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=bj_now)
    updated_at = Column(DateTime, default=bj_now, onupdate=bj_now)


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
    created_at = Column(DateTime, default=bj_now)
    updated_at = Column(DateTime, default=bj_now, onupdate=bj_now)


class WeeklyReport(Base):
    """周报记录"""
    __tablename__ = "weekly_reports"
    __table_args__ = (
        Index("idx_weekly_reports_status", "status"),
        Index("idx_weekly_reports_week_start", "week_start"),
        Index("idx_weekly_reports_person_id", "person_id"),
        Index("idx_weekly_reports_department", "department"),
        UniqueConstraint("author_name", "week_start", name="uq_weekly_reports_author_week"),
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
    created_at = Column(DateTime, default=bj_now)
    updated_at = Column(DateTime, default=bj_now, onupdate=bj_now)


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
    created_at = Column(DateTime, default=bj_now)


class AdminUser(Base):
    """管理员账号"""
    __tablename__ = "admin_users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), nullable=False, unique=True, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(20), nullable=False, default="admin")
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=bj_now)


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
    created_at = Column(DateTime, default=bj_now)


class WeeklySummary(Base):
    """一周小结（OCR 解析结果，作为沟通分辅助数据）"""
    __tablename__ = "weekly_summaries"
    __table_args__ = (
        Index("idx_weekly_summaries_week_start", "week_start"),
        Index("idx_weekly_summaries_person_id", "person_id"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    person_id = Column(String(36), nullable=True)
    author_name = Column(String(50), nullable=False)
    department = Column(String(50), nullable=True, default="")
    department_id = Column(String(36), nullable=True)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    work_session_count = Column(Integer, nullable=True)
    total_minutes = Column(Integer, nullable=True)
    latest_time = Column(String(100), nullable=True)
    latest_time_parsed = Column(DateTime, nullable=True)
    raw_ocr_text = Column(Text, nullable=True)
    source_file = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=bj_now)
    updated_at = Column(DateTime, default=bj_now, onupdate=bj_now)


class AttendanceRecord(Base):
    """考勤打卡记录（来自企业微信导出）"""
    __tablename__ = "attendance_records"
    __table_args__ = (
        Index("idx_attendance_person_week", "person_id", "week_start"),
        Index("idx_attendance_author_week", "author_name", "week_start"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    person_id = Column(String(36), nullable=True)
    author_name = Column(String(50), nullable=False)
    department = Column(String(50), nullable=True, default="")
    department_id = Column(String(36), nullable=True)
    record_date = Column(Date, nullable=False)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    check_in_time = Column(String(50), nullable=True)
    check_out_time = Column(String(50), nullable=True)
    check_in_location = Column(String(200), nullable=True)
    check_out_location = Column(String(200), nullable=True)
    work_duration_hours = Column(DECIMAL(5, 2), nullable=True)
    attendance_status = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    source_file = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=bj_now)
    updated_at = Column(DateTime, default=bj_now, onupdate=bj_now)


class ChatRecord(Base):
    """企业微信聊天记录（用于沟通评分）"""
    __tablename__ = "chat_records"
    __table_args__ = (
        Index("idx_chat_person_week", "person_id", "week_start"),
        Index("idx_chat_author_week", "author_name", "week_start"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    person_id = Column(String(36), nullable=True)
    author_name = Column(String(50), nullable=False)
    department = Column(String(50), nullable=True, default="")
    department_id = Column(String(36), nullable=True)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    message_date = Column(Date, nullable=True)
    conversation_topic = Column(String(200), nullable=True)
    counterparty = Column(String(100), nullable=True)
    message_count = Column(Integer, nullable=True, default=0)
    response_minutes = Column(DECIMAL(10, 2), nullable=True)
    content_summary = Column(Text, nullable=True)
    source_file = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=bj_now)
    updated_at = Column(DateTime, default=bj_now, onupdate=bj_now)


class WeeklyAggregate(Base):
    """周评综合表 - 汇总某员工某周的三项得分"""
    __tablename__ = "weekly_aggregates"
    __table_args__ = (
        Index("idx_aggregate_week_person", "week_start", "person_id"),
        Index("idx_aggregate_week_author", "week_start", "author_name"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    person_id = Column(String(36), nullable=True)
    author_name = Column(String(50), nullable=False)
    department = Column(String(50), nullable=True, default="")
    department_id = Column(String(36), nullable=True)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    report_score = Column(DECIMAL(5, 1), nullable=True)
    attendance_score = Column(DECIMAL(5, 1), nullable=True)
    chat_score = Column(DECIMAL(5, 1), nullable=True)
    composite_score = Column(DECIMAL(6, 2), nullable=True)

    # 评分状态：pending(待评分) / processing(评分中) / done(已完成) / manual(已手动覆盖)
    status = Column(String(20), nullable=False, default="pending")

    # 人工修改痕迹
    manual_override = Column(JSON, nullable=True, default=dict)
    modified_by = Column(String(50), nullable=True)
    modified_at = Column(DateTime, nullable=True)

    report_score_id = Column(String(36), nullable=True)
    summary_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=bj_now)
    updated_at = Column(DateTime, default=bj_now, onupdate=bj_now)


class ScoringSchedule(Base):
    """定时聚合评分配置 - 管理员设置的每日/每周评分时间"""
    __tablename__ = "scoring_schedule"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    enabled = Column(Boolean, default=True)
    hour = Column(Integer, default=3)  # 0-23
    minute = Column(Integer, default=0)  # 0-59
    # 'daily' 每天 / 'weekly' 按选中的星期
    recurrence = Column(String(16), default="daily")
    # 当 recurrence='weekly' 时生效：存储 0-6（周一到周日），逗号分隔，如 "0,2,4"
    # 为空字符串表示未选择
    weekdays = Column(String(32), default="")
    last_run_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=bj_now)
    updated_at = Column(DateTime, default=bj_now, onupdate=bj_now)


class DataUploadLog(Base):
    """数据上传日志 - 记录管理员每次上传考勤/聊天数据的元信息，
    用于页面提示"本周是否已上传"以及"支持覆盖式重传"。

    data_type: 'attendance' 考勤 / 'chat' 聊天记录
    """
    __tablename__ = "data_upload_logs"
    __table_args__ = (
        Index("idx_upload_log_type_week", "data_type", "week_start"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    data_type = Column(String(20), nullable=False)  # 'attendance' / 'chat'
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    filename = Column(String(255), nullable=True)
    record_count = Column(Integer, default=0)
    employees_matched = Column(Integer, default=0)
    uploaded_by = Column(String(100), nullable=True)  # 管理员用户名
    mode = Column(String(20), default="append")  # 'append' / 'replace'
    created_at = Column(DateTime, default=bj_now)


class DepartmentSummary(Base):
    """部门周总结 - 业务盘功能的核心数据表"""
    __tablename__ = "department_summaries"
    __table_args__ = (
        UniqueConstraint("department_id", "week_start", name="uq_dept_summary_week"),
        Index("idx_dept_summary_week", "week_start"),
        Index("idx_dept_summary_dept", "department_id"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    department_id = Column(String(36), nullable=False)
    department_name = Column(String(100), nullable=False)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    # 上周工作事项列表
    # 格式: [{"content": "事项内容", "highlight": false, "persons": ["张三", "李四"]}]
    last_week_summary = Column(JSON, nullable=True, default=list)
    # 本周工作事项列表
    # 格式: [{"content": "事项内容", "highlight": false, "persons": ["张三", "李四"]}]
    this_week_summary = Column(JSON, nullable=True, default=list)
    # 上周项目维度总结（业务盘卡片展示用）
    # 格式: [{"name": "项目名", "progress": 75, "highlight": true, "summary": "精炼描述", "persons": ["张三"]}]
    last_week_projects = Column(JSON, nullable=True, default=list)
    # 本周项目维度总结（业务盘卡片展示用）
    this_week_projects = Column(JSON, nullable=True, default=list)
    # 部门是否重点关注
    is_department_highlight = Column(Boolean, default=False)
    # 生成状态: pending/generating/done/failed
    status = Column(String(20), nullable=False, default="pending")
    # 失败原因
    error_message = Column(Text, nullable=True)
    # 生成时间
    generated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=bj_now)
    updated_at = Column(DateTime, default=bj_now, onupdate=bj_now)


class AIModel(Base):
    """AI 模型配置 - 支持自定义模型 ID、API Key 和 Base URL"""
    __tablename__ = "ai_models"
    __table_args__ = (
        Index("idx_ai_model_active", "is_active"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)  # 显示名称，如 "豆包 Pro"
    provider = Column(String(50), nullable=False)  # 厂商标识：mimo / ark / deepseek / openai / custom
    model_id = Column(String(200), nullable=False)  # 模型 ID，如 "doubao-seed-2.0-pro"
    api_key = Column(String(500), nullable=False)  # API Key
    base_url = Column(String(500), nullable=False)  # API Base URL
    is_active = Column(Boolean, default=False)  # 是否为当前使用的模型
    is_vision = Column(Boolean, default=False)  # 是否为视觉模型
    sort_order = Column(Integer, default=0)  # 排序权重
    created_at = Column(DateTime, default=bj_now)
    updated_at = Column(DateTime, default=bj_now, onupdate=bj_now)
