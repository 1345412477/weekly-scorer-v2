import sys
sys.path.insert(0, 'c:/Users/13454/Projects/weekly-scorer-v2/backend')
from app.services.wechat_parser import parse_attendance_excel
records, employees = parse_attendance_excel('c:/Users/13454/Projects/weekly-scorer-v2/test/上下班打卡_日报_20260720-20260723.xlsx')
print(f'员工数: {len(employees)}, 记录数: {len(records)}')
for r in records[:10]:
    print({k: v for k, v in r.items() if k not in ('author_name', 'record_date')})
    print(f"  author_name={r.get('author_name')}, status_len={len(r.get('attendance_status') or '')}, status={r.get('attendance_status')}")
