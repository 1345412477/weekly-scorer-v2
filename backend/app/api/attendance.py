"""考勤打卡 Excel 上传 API（管理员端使用）

支持两种上传模式：
- mode=append（默认）：追加写入，保留旧数据，适合分多次上传
- mode=replace：先清空本次文件覆盖到的周范围内的旧考勤记录，再写入新数据，
  适合"发现文件上传错了想重传"的场景。

每次成功上传会在 data_upload_logs 表记录一条日志，前端可据此
展示"本周是否已上传"的状态提示。
"""
import os
import uuid
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, delete

from app.database import get_db
from app.models.models import AttendanceRecord, Person, DataUploadLog
from app.core.auth import require_admin
from app.services.wechat_parser import parse_attendance_excel
from app.utils.time_utils import bj_now

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/attendance", tags=["考勤打卡"])

UPLOAD_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "attendance")
)
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _get_current_week_range(today: Optional[date] = None):
    """返回 (week_start, week_end) —— 本周周一~周日。"""
    today = today or date.today()
    # weekday(): 周一=0, 周日=6
    offset = today.weekday()
    week_start = today - timedelta(days=offset)
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


@router.post("/upload")
async def upload_attendance(
    file: UploadFile = File(...),
    mode: str = Query("append", description="append 追加 / replace 覆盖本周旧数据"),
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """上传企业微信考勤 Excel，写入 attendance_records.

    mode=replace 时，会先删除数据库中 week_start 落在本次文件覆盖的周范围内的旧考勤记录。
    """
    if mode not in ("append", "replace"):
        raise HTTPException(status_code=400, detail="mode 仅支持 append 或 replace")

    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".xlsx", ".xlsm"):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx / .xlsm 格式")

    saved_name = f"{uuid.uuid4()}{ext}"
    saved_path = os.path.join(UPLOAD_DIR, saved_name)

    try:
        content = await file.read()
        with open(saved_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存文件失败: {e}")

    try:
        records, employees = parse_attendance_excel(saved_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析 Excel 失败: {e}")

    if not records:
        raise HTTPException(status_code=400, detail="未解析到任何考勤记录，请检查表头格式")

    # 从解析结果推断本次文件覆盖的周范围
    week_starts = []
    for r in records:
        ws = r.get("week_start")
        if ws:
            week_starts.append(ws)
    if week_starts:
        min_week_start = min(week_starts)
        max_week_start = max(week_starts)
    else:
        # 解析失败时退回"本周"
        min_week_start, _ = _get_current_week_range()
        max_week_start = min_week_start
    # 对应的 week_end = week_start + 6 days
    week_end_for_log = max_week_start + timedelta(days=6) if isinstance(max_week_start, date) else None

    # replace 模式：先删除旧记录
    deleted_count = 0
    if mode == "replace":
        try:
            del_q = delete(AttendanceRecord).where(
                and_(
                    AttendanceRecord.week_start >= min_week_start,
                    AttendanceRecord.week_start <= max_week_start,
                )
            )
            result = await db.execute(del_q)
            deleted_count = int(result.rowcount or 0)
            logger.info(f"[attendance replace] 已删除 {deleted_count} 条旧考勤记录（week_start: {min_week_start}~{max_week_start}）")
        except Exception as e:
            logger.warning(f"[attendance replace] 删除旧记录失败: {e}")

    inserted = 0
    matched_names = set()
    unmatched_names = set()
    skipped_non_person = 0

    for r in records:
        author_name = r.get("author_name", "")
        person = None
        try:
            res = await db.execute(select(Person).where(Person.name == author_name).limit(1))
            person = res.scalar_one_or_none()
        except Exception as e:
            logger.warning(f"匹配人员失败: {e}")

        if person:
            matched_names.add(author_name)
            person_id = person.id
            department = person.department_name or ""
            department_id = person.department_id or ""
        else:
            skipped_non_person += 1
            unmatched_names.add(author_name)
            continue

        rec = AttendanceRecord(
            id=str(uuid.uuid4()),
            person_id=person_id,
            author_name=author_name,
            department=department,
            department_id=department_id,
            record_date=r.get("record_date"),
            week_start=r.get("week_start"),
            week_end=r.get("week_end"),
            check_in_time=r.get("check_in_time"),
            check_out_time=r.get("check_out_time"),
            check_in_location=r.get("check_in_location"),
            check_out_location=r.get("check_out_location"),
            work_duration_hours=r.get("work_duration_hours"),
            attendance_status=r.get("attendance_status"),
            notes=r.get("notes"),
            source_file=file.filename,
        )
        db.add(rec)
        inserted += 1

    # 写上传日志
    admin_username = None
    if admin and hasattr(admin, "username"):
        admin_username = admin.username
    matched_count = len(matched_names)
    log = DataUploadLog(
        id=str(uuid.uuid4()),
        data_type="attendance",
        week_start=min_week_start,
        week_end=week_end_for_log or (max_week_start + timedelta(days=6)),
        filename=file.filename,
        record_count=inserted,
        employees_matched=matched_count,
        uploaded_by=admin_username,
        mode=mode,
        created_at=bj_now(),
    )
    db.add(log)

    await db.commit()

    return {
        "message": "考勤数据上传成功（覆盖模式）" if mode == "replace" else "考勤数据上传成功",
        "mode": mode,
        "week_start": min_week_start.isoformat(),
        "week_end": (week_end_for_log or (max_week_start + timedelta(days=6))).isoformat(),
        "total_records": inserted,
        "employees_matched": matched_count,
        "employees_skipped": skipped_non_person,
        "employees_unmatched": sorted(unmatched_names),
        "replaced_old_count": deleted_count,
    }


@router.get("/status")
async def get_attendance_status(
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """返回考勤数据上传状态：本周是否已上传 + 最近一次上传信息。"""
    week_start, week_end = _get_current_week_range()

    # 查本周内是否有上传日志
    q = select(DataUploadLog).where(
        and_(
            DataUploadLog.data_type == "attendance",
            DataUploadLog.week_start >= week_start - timedelta(days=1),
            DataUploadLog.week_start <= week_end + timedelta(days=1),
        )
    ).order_by(DataUploadLog.created_at.desc())

    result = await db.execute(q)
    logs = result.scalars().all()

    last_upload = None
    if logs:
        last = logs[0]
        last_upload = {
            "week_start": last.week_start.isoformat(),
            "week_end": last.week_end.isoformat(),
            "filename": last.filename,
            "record_count": last.record_count,
            "employees_matched": last.employees_matched,
            "mode": last.mode,
            "uploaded_at": last.created_at.isoformat() if last.created_at else None,
            "uploaded_by": last.uploaded_by,
        }

    # 直接查考勤记录数，作为"是否真有数据"的兜底判断
    count_q = select(func.count()).select_from(AttendanceRecord).where(
        and_(
            AttendanceRecord.week_start >= week_start,
            AttendanceRecord.week_start <= week_end,
        )
    )
    records_count = (await db.execute(count_q)).scalar() or 0

    # 覆盖的员工数
    emp_q = select(func.count(func.distinct(AttendanceRecord.author_name))).where(
        and_(
            AttendanceRecord.week_start >= week_start,
            AttendanceRecord.week_start <= week_end,
        )
    )
    employees_count = (await db.execute(emp_q)).scalar() or 0

    return {
        "current_week_start": week_start.isoformat(),
        "current_week_end": week_end.isoformat(),
        "uploaded_this_week": bool(logs) or records_count > 0,
        "records_count": records_count,
        "employees_count": employees_count,
        "last_upload": last_upload,
    }


@router.post("/cancel")
async def cancel_attendance_upload(
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """取消本周考勤上传——删除本周的考勤记录和上传日志。"""
    week_start, week_end = _get_current_week_range()

    # 删除本周考勤记录
    del_records = delete(AttendanceRecord).where(
        and_(
            AttendanceRecord.week_start >= week_start,
            AttendanceRecord.week_start <= week_end,
        )
    )
    r1 = await db.execute(del_records)
    deleted_records = int(r1.rowcount or 0)

    # 删除本周上传日志
    del_logs = delete(DataUploadLog).where(
        and_(
            DataUploadLog.data_type == "attendance",
            DataUploadLog.week_start >= week_start - timedelta(days=1),
            DataUploadLog.week_start <= week_end + timedelta(days=1),
        )
    )
    r2 = await db.execute(del_logs)
    deleted_logs = int(r2.rowcount or 0)

    await db.commit()
    logger.info(
        f"[attendance cancel] 本周考勤数据已取消：删除 {deleted_records} 条记录 + {deleted_logs} 条日志"
        f"（周范围: {week_start}~{week_end}）"
    )

    return {
        "message": "本周考勤上传已取消",
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "deleted_records": deleted_records,
        "deleted_logs": deleted_logs,
    }


@router.get("")
async def list_attendance(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    author_name: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """列出考勤记录（调试/查看用）"""
    q = select(AttendanceRecord)
    count_q = select(func.count()).select_from(AttendanceRecord)
    if author_name:
        q = q.where(AttendanceRecord.author_name.contains(author_name))
        count_q = count_q.where(AttendanceRecord.author_name.contains(author_name))
    q = q.order_by(AttendanceRecord.record_date.desc())

    total = (await db.execute(count_q)).scalar() or 0
    result = await db.execute(q.offset((page - 1) * size).limit(size))
    items = result.scalars().all()

    def to_dict(r):
        return {
            "id": r.id,
            "author_name": r.author_name,
            "department": r.department or "",
            "record_date": r.record_date.isoformat() if r.record_date else None,
            "week_start": r.week_start.isoformat() if r.week_start else None,
            "week_end": r.week_end.isoformat() if r.week_end else None,
            "check_in_time": r.check_in_time,
            "check_out_time": r.check_out_time,
            "check_in_location": r.check_in_location,
            "check_out_location": r.check_out_location,
            "work_duration_hours": float(r.work_duration_hours) if r.work_duration_hours else None,
            "attendance_status": r.attendance_status,
        }

    return {"items": [to_dict(r) for r in items], "total": total, "page": page, "size": size}
