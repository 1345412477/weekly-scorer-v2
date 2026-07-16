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
from datetime import date, timedelta

import pytest
import pytest_asyncio

from tests.conftest import make_excel_file, make_docx_file, make_empty_file, get_current_week


@pytest.mark.asyncio
class TestFileFormatValidation:
    """文件格式验证测试"""

    async def test_upload_xlsx_success(self, client, seed_scoring_config, seed_ai_model):
        """上传 .xlsx 文件成功"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)
            f.name_created = f.name

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("test_report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
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

    async def test_upload_without_person_uses_form_data(self, client, admin_headers, seed_scoring_config):
        """不选择人员时，使用表单提交的 author_name 和 department"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"author_name": "测试用户", "department": "测试部"},
                )
            assert resp.status_code == 200

            detail_resp = await client.get(f"/api/v1/reports/{resp.json()['report_id']}", headers=admin_headers)
            detail = detail_resp.json()
            assert detail["author_name"] == "测试用户"
            assert detail["department"] == "测试部"
        finally:
            os.unlink(f.name)

    async def test_upload_default_author_is_anonymous(self, client, admin_headers, seed_scoring_config):
        """不传任何人员信息时，默认为匿名"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                )
            assert resp.status_code == 200

            detail_resp = await client.get(f"/api/v1/reports/{resp.json()['report_id']}", headers=admin_headers)
            assert detail_resp.json()["author_name"] == "匿名"
        finally:
            os.unlink(f.name)


@pytest.mark.asyncio
class TestTimeClassification:
    """周报时间识别与分类测试"""

    async def test_current_week_report_type_normal(self, client, seed_scoring_config):
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
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["report_type"] == "normal"
            assert data["week_diff"] == 0
            assert data["week_start"]
            assert data["week_end"]
        finally:
            os.unlink(f.name)

    async def test_last_week_report_type_catch_up(self, client, seed_scoring_config, seed_ai_model):
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
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["report_type"] == "catch_up"
            assert data["week_diff"] >= 1
            assert "补周报" in data["message"]
        finally:
            os.unlink(f.name)

    async def test_3_weeks_ago_report_type_catch_up(self, client, seed_scoring_config):
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
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["report_type"] == "catch_up"
            assert data["week_diff"] >= 3
        finally:
            os.unlink(f.name)

    async def test_future_week_report_rejected(self, client, seed_scoring_config):
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
                )
            assert resp.status_code == 400
            assert "未来" in resp.json()["detail"]
        finally:
            os.unlink(f.name)

    async def test_no_date_report_needs_confirmation(self, client, seed_scoring_config):
        """无法识别时间的周报标记 needs_confirmation"""
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
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["needs_confirmation"] is True
            assert data["report_type"] in ["unknown", "normal"]
        finally:
            os.unlink(f.name)

    async def test_confirmed_week_start_end_override(self, client, seed_scoring_config):
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

    async def test_special_characters_in_filename(self, client, admin_headers, seed_scoring_config):
        """文件名包含特殊字符"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("周报（2026）-张三@技术部.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                )
            assert resp.status_code == 200
            detail = await client.get(f"/api/v1/reports/{resp.json()['report_id']}", headers=admin_headers)
            assert detail.json()["original_filename"] == "周报（2026）-张三@技术部.xlsx"
        finally:
            os.unlink(f.name)

    async def test_chinese_characters_in_content(self, client, seed_scoring_config, seed_ai_model):
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
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_score"] is None  # 异步评分
        finally:
            os.unlink(f.name)

    async def test_content_preview_truncation(self, client, seed_scoring_config):
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
                )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["content_preview"]) <= 303
        finally:
            os.unlink(f.name)

    async def test_upload_report_persists_in_database(self, client, admin_headers, seed_scoring_config, seed_ai_model):
        """上传的周报正确持久化到数据库"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"author_name": "持久化测试", "department": "测试部"},
                )
            assert resp.status_code == 200
            report_id = resp.json()["report_id"]

            detail_resp = await client.get(f"/api/v1/reports/{report_id}", headers=admin_headers)
            assert detail_resp.status_code == 200
            detail = detail_resp.json()
            assert detail["id"] == report_id
            assert detail["author_name"] == "持久化测试"
            assert detail["department"] == "测试部"
            assert detail["status"] == "submitted"  # 异步评分，初始状态为 submitted
            assert detail["content"]
            assert detail["submit_time"]

            list_resp = await client.get("/api/v1/reports", headers=admin_headers)
            assert list_resp.status_code == 200
            items = list_resp.json()["items"]
            assert any(r["id"] == report_id for r in items)
        finally:
            os.unlink(f.name)

    async def test_upload_file_saved_to_disk(self, client, admin_headers, seed_scoring_config):
        """上传的文件正确保存到磁盘"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
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

    async def test_original_filename_preserved(self, client, admin_headers, seed_scoring_config):
        """原始文件名被正确保存"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        original_name = "我的周报_2026年第23周.xlsx"
        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": (original_name, fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                )
            assert resp.status_code == 200

            detail_resp = await client.get(f"/api/v1/reports/{resp.json()['report_id']}", headers=admin_headers)
            assert detail_resp.json()["original_filename"] == original_name
        finally:
            os.unlink(f.name)


@pytest.mark.asyncio
class TestAIScoringIntegration:
    """AI 评分集成测试"""

    async def test_upload_triggers_scoring(self, client, seed_scoring_config, seed_ai_model):
        """上传后自动触发评分"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_score"] is None  # 异步评分
            assert data["scoring_status"] == "pending"
        finally:
            os.unlink(f.name)

    async def test_scoring_dimensions_in_detail(self, client, admin_headers, seed_scoring_config, seed_ai_model):
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
                )
            report_id = resp.json()["report_id"]

            # 手动触发评分
            async with TestSessionLocal() as db:
                await trigger_scoring(report_id, db)

            detail_resp = await client.get(f"/api/v1/reports/{report_id}", headers=admin_headers)
            detail = detail_resp.json()
            assert detail["total_score"] is not None
            assert detail["dimension_scores"]
            assert len(detail["dimension_scores"]) == 3
            for dim in detail["dimension_scores"]:
                assert dim["name"]
                assert dim["score"] >= 0
                assert dim["max"] > 0
        finally:
            os.unlink(f.name)

    async def test_report_status_after_upload(self, client, admin_headers, seed_scoring_config, seed_ai_model):
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

    async def test_list_reports_after_upload(self, client, admin_headers, seed_scoring_config):
        """上传后能在列表中看到"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        try:
            with open(f.name, "rb") as fh:
                await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                )

            list_resp = await client.get("/api/v1/reports", headers=admin_headers)
            assert list_resp.status_code == 200
            data = list_resp.json()
            assert data["total"] >= 1
            assert len(data["items"]) >= 1
            assert data["page"] == 1
        finally:
            os.unlink(f.name)

    async def test_report_detail_has_all_fields(self, client, admin_headers, seed_scoring_config):
        """详情包含所有必要字段"""
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            make_excel_file(f.name)

        try:
            with open(f.name, "rb") as fh:
                resp = await client.post(
                    "/api/v1/reports/upload",
                    files={"file": ("report.xlsx", fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    data={"author_name": "详情测试", "department": "测试部"},
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
