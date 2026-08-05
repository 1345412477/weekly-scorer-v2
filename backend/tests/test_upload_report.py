"""周报上传功能综合测试

覆盖场景：
1. 文件格式验证（支持/不支持的格式）
2. 人员部门自动匹配
3. 周报时间识别与分类（本周/补周报/未来周报/无法识别）
4. 确认时间后重新上传
5. 空内容和无效文件
6. 特殊字符文件名
7. AI 评分集成
8. 数据持久化验证
"""
import os
import tempfile
from datetime import date, datetime, timedelta

import pytest
import pytest_asyncio

from tests.conftest import make_excel_file, make_docx_file, make_empty_file, get_current_week


@pytest.mark.asyncio
class TestFileFormatValidation:
    """文件格式验证测试"""

    async def test_upload_xlsx_success(self, client, seed_scoring_config, seed_ai_model, seed_persons):
        """上传 .xlsx 文件成功"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)
            f.name_created = f.name

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("test_report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"person_id": "person-1"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["report_id"]
            assert data["total_score"] is None  # 异步评分，响应时还未完成
            assert data["scoring_status"] == "pending"
        finally:
            os.unlink(f.name)

    async def test_upload_docx_success(self, client, seed_scoring_config):
        """上传 .docx 文件被拒绝（按规范仅允许 .xlsx）"""
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            make_docx_file(f.name)
            f.name_created = f.name

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("test_report.docx", fh, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                )
            assert resp.status_code == 400
            assert "不支持的文件格式" in resp.json()["detail"]
        finally:
            os.unlink(f.name)

    async def test_upload_unsupported_format_txt(self, client):
        """上传 .txt 文件被拒绝"""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("This is a test report")
            f.name_created = f.name

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("test_report.txt", fh, "text/plain")},
                )
            assert resp.status_code == 400
            assert "不支持的文件格式" in resp.json()["detail"]
        finally:
            os.unlink(f.name)

    async def test_upload_unsupported_format_csv(self, client):
        """上传 .csv 文件被拒绝"""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            f.write("name,dept\n张三,技术部")
            f.name_created = f.name

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("test.csv", fh, "text/csv")},
                )
            assert resp.status_code == 400
        finally:
            os.unlink(f.name)

    async def test_upload_unsupported_format_image(self, client):
        """上传图片文件被拒绝"""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False, mode="wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
            f.name_created = f.name

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("screenshot.png", fh, "image/png")},
                )
            assert resp.status_code == 400
        finally:
            os.unlink(f.name)


@pytest.mark.asyncio
class TestPersonDepartmentAutoMatch:
    """人员部门自动匹配测试"""

    async def test_upload_with_person_auto_fill_department(self, client, admin_headers, seed_persons, seed_scoring_config):
        """选择人员后自动填充部门信息"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"person_id": "person-1"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["report_id"]

            detail_resp = await client.get(f"/api/v1/reports/{data['report_id']}", headers=admin_headers)
            detail = detail_resp.json()
            assert detail["author_name"] == "张三"
            assert detail["department"] == "技术部"
            assert detail["person_id"] == "person-1"
            assert detail["department_id"] == "dept-tech"
        finally:
            os.unlink(f.name)

    async def test_upload_with_person_no_department(self, client, admin_headers, seed_persons, seed_scoring_config):
        """人员没有关联部门时，department 为空"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"person_id": "person-4"},
                )
            assert resp.status_code == 200

            detail_resp = await client.get(f"/api/v1/reports/{resp.json()['report_id']}", headers=admin_headers)
            detail = detail_resp.json()
            assert detail["author_name"] == "赵六"
            assert detail["person_id"] == "person-4"
        finally:
            os.unlink(f.name)

    async def test_upload_filename_auto_detect_success(self, client, admin_headers, seed_persons, seed_scoring_config):
        """文件名匹配人员库时，无需传 person_id 也能自动识别"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("张三-2026年7月第1周周报20260706.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["author_name"] == "张三"
            assert data["department"] == "技术部"
            assert data["auto_detected"] is True
        finally:
            os.unlink(f.name)

    async def test_upload_without_person_rejected(self, client, admin_headers, seed_scoring_config, seed_persons):
        """不选择人员且文件名无法匹配人员库时，按规范拒绝上传"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"author_name": "测试用户", "department": "测试部"},
                )
            assert resp.status_code == 400
            assert "系统中无员工信息" in resp.json()["detail"]
        finally:
            os.unlink(f.name)

    async def test_upload_without_person_rejected_anonymous(self, client, admin_headers, seed_scoring_config, seed_persons):
        """不传任何人员信息且文件名无法匹配人员库时，按规范拒绝上传（不兜底匿名）"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                )
            assert resp.status_code == 400
            assert "系统中无员工信息" in resp.json()["detail"]
        finally:
            os.unlink(f.name)


@pytest.mark.asyncio
class TestTimeClassification:
    """周报时间识别与分类测试"""

    async def test_current_week_report_type_normal(self, client, seed_scoring_config, seed_persons):
        """本周周报识别为 normal"""
        monday, sunday = get_current_week()
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(
                f.name,
                last_week_title=f"本周工作内容：{monday.strftime('%Y.%m.%d')}-{sunday.strftime('%Y.%m.%d')}",
            )

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"person_id": "person-1"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["report_type"] == "normal"
            assert data["week_diff"] == 0
            assert data["week_start"]
            assert data["week_end"]
        finally:
            os.unlink(f.name)

    async def test_last_week_report_type_catch_up(self, client, seed_scoring_config, seed_ai_model, seed_persons):
        """上周周报识别为 catch_up"""
        monday, sunday = get_current_week()
        last_monday = monday - timedelta(days=7)
        last_sunday = sunday - timedelta(days=7)

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(
                f.name,
                last_week_title=f"上周工作内容：{last_monday.strftime('%Y.%m.%d')}-{last_sunday.strftime('%Y.%m.%d')}",
                this_week_title=f"本周工作计划：{monday.strftime('%Y.%m.%d')}-{sunday.strftime('%Y.%m.%d')}",
            )

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"person_id": "person-1"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["report_type"] == "catch_up"
            assert data["week_diff"] >= 1
            assert "补周报" in data["message"]
        finally:
            os.unlink(f.name)

    async def test_3_weeks_ago_report_type_catch_up(self, client, seed_scoring_config, seed_persons):
        """3周前的周报识别为 catch_up，week_diff=3"""
        monday, sunday = get_current_week()
        target_monday = monday - timedelta(days=21)
        target_sunday = sunday - timedelta(days=21)

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(
                f.name,
                last_week_title=f"上周工作内容：{target_monday.strftime('%Y.%m.%d')}-{target_sunday.strftime('%Y.%m.%d')}",
                this_week_title=f"本周工作计划：{target_monday.strftime('%Y.%m.%d')}-{target_sunday.strftime('%Y.%m.%d')}",
            )

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"person_id": "person-1"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["report_type"] == "catch_up"
            assert data["week_diff"] >= 3
        finally:
            os.unlink(f.name)

    async def test_future_week_report_rejected(self, client, seed_scoring_config, seed_persons):
        """未来周报被拒绝提交"""
        monday, sunday = get_current_week()
        future_monday = monday + timedelta(days=14)
        future_sunday = sunday + timedelta(days=14)

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(
                f.name,
                last_week_title=f"上周工作内容：{future_monday.strftime('%Y.%m.%d')}-{future_sunday.strftime('%Y.%m.%d')}",
                this_week_title=f"本周工作计划：{future_monday.strftime('%Y.%m.%d')}-{future_sunday.strftime('%Y.%m.%d')}",
            )

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"person_id": "person-1"},
                )
            assert resp.status_code == 400
            assert "未来" in resp.json()["detail"]
        finally:
            os.unlink(f.name)

    async def test_no_date_report_falls_back_to_current_week(self, client, seed_scoring_config, seed_persons):
        """无法识别时间的周报兜底为本周，并重新分类为 normal"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(
                f.name,
                last_week_title="上周工作内容",
                this_week_title="本周工作计划",
            )

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"person_id": "person-1"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["needs_confirmation"] is False
            assert data["report_type"] == "normal"
            monday, _ = get_current_week()
            assert data["week_start"] == monday.isoformat()
        finally:
            os.unlink(f.name)

    async def test_confirmed_week_start_end_override(self, client, seed_scoring_config, seed_persons):
        """用户手动确认时间后，覆盖文件中的日期"""
        monday, sunday = get_current_week()
        last_monday = monday - timedelta(days=7)
        last_sunday = sunday - timedelta(days=7)

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={
                        "person_id": "person-1",
                        "confirmed_week_start": last_monday.isoformat(),
                        "confirmed_week_end": last_sunday.isoformat(),
                    },
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["week_start"] == last_monday.isoformat()
            assert data["week_end"] == last_sunday.isoformat()
        finally:
            os.unlink(f.name)


@pytest.mark.asyncio
class TestEdgeCases:
    """边界情况测试"""

    async def test_upload_empty_excel_content_rejected(self, client, seed_scoring_config):
        """空 Excel 文件（无周报内容）被拒绝"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_empty_file(f.name, ".xlsx")

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("empty.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                )
            assert resp.status_code == 400
            assert "内容为空" in resp.json()["detail"]
        finally:
            os.unlink(f.name)

    async def test_special_characters_in_filename(self, client, admin_headers, seed_scoring_config, seed_persons):
        """文件名包含特殊字符"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("周报（2026）-张三@技术部.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"person_id": "person-1"},
                )
            assert resp.status_code == 200
            detail = await client.get(f"/api/v1/reports/{resp.json()['report_id']}", headers=admin_headers)
            assert detail.json()["original_filename"] == "周报（2026）-张三@技术部.xlsx"
        finally:
            os.unlink(f.name)

    async def test_chinese_characters_in_content(self, client, seed_scoring_config, seed_ai_model, seed_persons):
        """周报内容包含中文特殊字符"""
        monday, sunday = get_current_week()
        last_monday = monday - timedelta(days=7)
        last_sunday = sunday - timedelta(days=7)

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(
                f.name,
                last_week_rows=[
                    [1, "项目《智能》系统", "完成「AI」算法优化，处理了100+条数据", "张三", "已完成90%，剩余部分需@李四协助"],
                    [2, "测试（v2.0）", "修复了3个bug：①登录异常 ②数据丢失 ③界面卡顿", "张三", "全部修复完成"],
                ],
                this_week_rows=[
                    [1, "核心系统", "计划完成5个模块的集成测试", "张三", "预期产出：测试报告"],
                ],
            )

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"person_id": "person-1"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_score"] is None  # 异步评分
        finally:
            os.unlink(f.name)

    async def test_content_preview_truncation(self, client, seed_scoring_config, seed_persons):
        """长内容返回截断的预览"""
        long_rows = [
            [i, f"项目{i}", f"这是第{i}个项目的工作内容，包含大量详细描述" * 10, "张三", f"完成{100-i}%"]
            for i in range(1, 21)
        ]

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name, last_week_rows=long_rows)

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"person_id": "person-1"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["content_preview"]) <= 303
        finally:
            os.unlink(f.name)

    async def test_upload_report_persists_in_database(self, client, admin_headers, seed_scoring_config, seed_ai_model, seed_persons):
        """上传的周报正确持久化到数据库"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"person_id": "person-1"},
                )
            assert resp.status_code == 200
            report_id = resp.json()["report_id"]

            detail_resp = await client.get(f"/api/v1/reports/{report_id}", headers=admin_headers)
            assert detail_resp.status_code == 200
            detail = detail_resp.json()
            assert detail["id"] == report_id
            assert detail["author_name"] == "张三"
            assert detail["department"] == "技术部"
            assert detail["status"] == "submitted"  # 异步评分，初始状态为 submitted
            assert detail["content"]
            assert detail["submit_time"]

            list_resp = await client.get("/api/v1/reports", headers=admin_headers)
            assert list_resp.status_code == 200
            items = list_resp.json()["items"]
            assert any(r["id"] == report_id for r in items)
        finally:
            os.unlink(f.name)

    async def test_upload_file_saved_to_disk(self, client, admin_headers, seed_scoring_config, seed_persons):
        """上传的文件正确保存到磁盘"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"person_id": "person-1"},
                )
            assert resp.status_code == 200
            report_id = resp.json()["report_id"]

            detail_resp = await client.get(f"/api/v1/reports/{report_id}", headers=admin_headers)
            saved_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "uploads", f"{report_id}.xlsx"
            )
            assert os.path.exists(saved_path)

            if os.path.exists(saved_path):
                os.remove(saved_path)
        finally:
            os.unlink(f.name)

    async def test_original_filename_preserved(self, client, admin_headers, seed_scoring_config, seed_persons):
        """原始文件名被正确保存"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        original_name = "我的周报_2026年第23周.xlsx"
        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": (original_name, fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"person_id": "person-1"},
                )
            assert resp.status_code == 200

            detail_resp = await client.get(f"/api/v1/reports/{resp.json()['report_id']}", headers=admin_headers)
            assert detail_resp.json()["original_filename"] == original_name
        finally:
            os.unlink(f.name)


@pytest.mark.asyncio
class TestAIScoringIntegration:
    """AI 评分集成测试"""

    async def test_upload_triggers_scoring(self, client, seed_scoring_config, seed_ai_model, seed_persons):
        """上传后自动触发评分"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"person_id": "person-1"},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_score"] is None  # 异步评分
            assert data["scoring_status"] == "pending"
        finally:
            os.unlink(f.name)

    async def test_scoring_dimensions_in_detail(self, client, admin_headers, seed_scoring_config, seed_ai_model, seed_persons, mock_ai_score):
        """评分详情包含各维度分数（异步评分后查询）"""
        # 上传后手动触发评分（因为后台异步任务使用真实DB，测试中直接调用）
        from app.services.scoring import trigger_scoring
        from tests.conftest import TestSessionLocal

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"person_id": "person-1"},
                )
            report_id = resp.json()["report_id"]

            # 手动触发评分
            async with TestSessionLocal() as db:
                await trigger_scoring(report_id, db)

            detail_resp = await client.get(f"/api/v1/reports/{report_id}", headers=admin_headers)
            detail = detail_resp.json()
            assert detail["total_score"] is not None
            assert detail["ai_comment"] is not None
            assert isinstance(detail["total_score"], (int, float))
        finally:
            os.unlink(f.name)

    async def test_report_status_after_upload(self, client, admin_headers, seed_scoring_config, seed_ai_model, seed_persons, mock_ai_score):
        """上传并评分后状态为 scored"""
        from app.services.scoring import trigger_scoring
        from tests.conftest import TestSessionLocal

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"person_id": "person-1"},
                )
            report_id = resp.json()["report_id"]

            # 手动触发评分
            async with TestSessionLocal() as db:
                await trigger_scoring(report_id, db)

            detail_resp = await client.get(f"/api/v1/reports/{report_id}", headers=admin_headers)
            assert detail_resp.json()["status"] == "scored"
        finally:
            os.unlink(f.name)


@pytest.mark.asyncio
class TestListAndDetail:
    """列表和详情测试"""

    async def test_list_reports_after_upload(self, client, admin_headers, seed_scoring_config, seed_persons):
        """上传后能在列表中看到"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        try:
            with open(f.name, "rb") as fh:
                await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"person_id": "person-1"},
                )

            list_resp = await client.get("/api/v1/reports", headers=admin_headers)
            assert list_resp.status_code == 200
            data = list_resp.json()
            assert data["total"] >= 1
            assert len(data["items"]) >= 1
            assert data["page"] == 1
        finally:
            os.unlink(f.name)

    async def test_report_detail_has_all_fields(self, client, admin_headers, seed_scoring_config, seed_persons):
        """详情包含所有必要字段"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"person_id": "person-1"},
                )
            report_id = resp.json()["report_id"]

            detail_resp = await client.get(f"/api/v1/reports/{report_id}", headers=admin_headers)
            detail = detail_resp.json()

            required_fields = [
                "id", "author_name", "department", "week_start", "week_end",
                "content", "status", "report_type", "week_diff",
                "total_score", "grade", "dimension_scores",
                "submit_time",
            ]
            for field in required_fields:
                assert field in detail, f"Missing field: {field}"
        finally:
            os.unlink(f.name)

    async def test_nonexistent_report_returns_404(self, client, admin_headers):
        """查询不存在的周报返回 404"""
        resp = await client.get("/api/v1/reports/nonexistent-id", headers=admin_headers)
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestRBACPermissions:
    """RBAC 权限测试"""

    async def test_unauthenticated_reports_list_returns_401(self, client):
        """未登录访问周报列表返回 401"""
        resp = await client.get("/api/v1/reports")
        assert resp.status_code == 401

    async def test_unauthenticated_config_returns_401(self, client):
        """未登录访问配置返回 401"""
        resp = await client.get("/api/v1/config")
        assert resp.status_code == 401

    async def test_admin_can_access_reports_list(self, client, admin_headers):
        """管理员登录后可访问周报列表"""
        resp = await client.get("/api/v1/reports", headers=admin_headers)
        assert resp.status_code == 200

    async def test_unauthenticated_leaderboard_succeeds(self, client):
        """未登录访问排行榜成功"""
        resp = await client.get("/api/v1/leaderboard")
        assert resp.status_code == 200

    async def test_unauthenticated_create_and_submit_draft_succeeds(self, client, seed_scoring_config):
        """未登录创建草稿并提交成功"""
        create_resp = await client.post(
            "/api/v1/reports",
            json={
                "author_name": "匿名用户",
                "department": "测试部",
                "content": "本周完成需求开发、问题修复和联调验证，下周继续推进测试与上线准备。",
            },
        )
        assert create_resp.status_code == 200
        report_id = create_resp.json()["id"]

        submit_resp = await client.post(f"/api/v1/reports/{report_id}/submit")
        assert submit_resp.status_code == 200
        assert submit_resp.json()["report_id"] == report_id


@pytest.mark.asyncio
class TestBatchDeleteSafety:
    """批量删除周报时，不得误删其他员工/其他周的周评记录"""

    async def test_batch_delete_only_removes_matching_aggregates(
        self, client, admin_headers, db, seed_persons
    ):
        from datetime import date
        from sqlalchemy import select
        from app.models.models import WeeklyReport, WeeklyAggregate

        r1 = WeeklyReport(
            id="r1",
            author_name="张三",
            department="技术部",
            person_id="person-1",
            department_id="dept-tech",
            week_start=date(2026, 7, 6),
            week_end=date(2026, 7, 12),
            content="本周工作内容",
            status="scored",
        )
        r2 = WeeklyReport(
            id="r2",
            author_name="李四",
            department="产品部",
            person_id="person-2",
            department_id="dept-product",
            week_start=date(2026, 7, 13),
            week_end=date(2026, 7, 19),
            content="本周工作内容",
            status="scored",
        )
        db.add_all([r1, r2])
        await db.commit()

        agg1 = WeeklyAggregate(
            id="agg1",
            person_id="person-1",
            author_name="张三",
            department="技术部",
            department_id="dept-tech",
            week_start=date(2026, 7, 6),
            week_end=date(2026, 7, 12),
            composite_score=80,
        )
        agg2 = WeeklyAggregate(
            id="agg2",
            person_id="person-2",
            author_name="李四",
            department="产品部",
            department_id="dept-product",
            week_start=date(2026, 7, 13),
            week_end=date(2026, 7, 19),
            composite_score=90,
        )
        db.add_all([agg1, agg2])
        await db.commit()

        resp = await client.post(
            "/api/v1/reports/batch-delete",
            json=["r1"],
            headers=admin_headers,
        )
        assert resp.status_code == 200

        deleted = (
            await db.execute(select(WeeklyAggregate).where(WeeklyAggregate.id == "agg1"))
        ).scalar_one_or_none()
        assert deleted is None

        # 关键断言：李四第 2 周的周评不能被误删
        remaining = (
            await db.execute(select(WeeklyAggregate).where(WeeklyAggregate.id == "agg2"))
        ).scalar_one_or_none()
        assert remaining is not None


@pytest.mark.asyncio
class TestReportDeadlinePenalty:
    """周报迟交扣5分、补交记0分（方案B：以提交时间与期限计算）"""

    async def test_deadline_penalties(self, db, monkeypatch, seed_scoring_config):
        from app.models.models import WeeklyReport, ReportScore
        from app.services.scoring import trigger_scoring
        from sqlalchemy import select

        async def fake_score(content, author_name, department, prompt_template="", db=None):
            return {
                "total_score": 28.0,
                "grade": "差",
                "comment": "基础评语",
                "suggestion": "改进建议",
                "dimension_scores": [
                    {"name": "工作反馈深度", "score": 7, "max": 12, "comment": "一般"}
                ],
                "raw": "{}",
            }

        monkeypatch.setattr("app.services.scoring.score_report", fake_score)

        week_start = date(2026, 6, 1)  # 周一
        week_end = date(2026, 6, 7)
        reports = [
            WeeklyReport(
                id="ok-report",
                author_name="张三",
                department="技术部",
                week_start=week_start,
                week_end=week_end,
                content="正常周报内容",
                status="submitted",
                submit_time=datetime(2026, 6, 2, 10, 0, 0),  # 期限内
            ),
            WeeklyReport(
                id="late-report",
                author_name="李四",
                department="产品部",
                week_start=week_start,
                week_end=week_end,
                content="迟交周报内容",
                status="submitted",
                submit_time=datetime(2026, 6, 9, 10, 0, 0),  # 超过正常期限、未超过补交期限
            ),
            WeeklyReport(
                id="catchup-report",
                author_name="王五",
                department="技术部",
                week_start=week_start,
                week_end=week_end,
                content="补交周报内容",
                status="submitted",
                submit_time=datetime(2026, 6, 16, 10, 0, 0),  # 超过补交期限
            ),
        ]
        db.add_all(reports)
        await db.commit()

        for report in reports:
            await trigger_scoring(report.id, db)

        result = await db.execute(
            select(ReportScore).where(ReportScore.report_id.in_(["ok-report", "late-report", "catchup-report"]))
        )
        scores = {s.report_id: s for s in result.scalars().all()}

        assert float(scores["ok-report"].total_score) == 28.0
        assert float(scores["late-report"].total_score) == 23.0
        assert "迟交" in (scores["late-report"].ai_comment or "")
        assert float(scores["catchup-report"].total_score) == 0.0
        assert scores["catchup-report"].dimension_scores == []
        assert "补交" in (scores["catchup-report"].ai_comment or "")
