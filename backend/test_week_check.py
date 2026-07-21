from app.services.document_parser import parse_multi_week_excel, get_current_week

data = parse_multi_week_excel(r"C:\Users\13454\Projects\weekly-scorer-v2\test\唐珩-2026年7月第2周周报20260719.xlsx")
print(f"Weeks found: {len(data)}")
latest = data[-1]
print(f"Latest week_start: {latest.get('week_start')}")
print(f"Latest week_end: {latest.get('week_end')}")

cm, cs = get_current_week()
print(f"Current Monday: {cm}")
print(f"week_start is None: {latest.get('week_start') is None}")
print(f"Match: {latest.get('week_start') == cm}")
