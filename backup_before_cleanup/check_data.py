import sqlite3
import json

conn = sqlite3.connect('weekly_scorer.db')
c = conn.cursor()

c.execute('SELECT dimension_scores FROM report_scores')
rows = c.fetchall()

all_ok = True
for i, row in enumerate(rows):
    dim_scores = json.loads(row[0])
    for ds in dim_scores:
        if ds['max'] == 50:
            print(f'记录{i}: {ds["name"]} 的max还是50')
            all_ok = False

if all_ok:
    print('所有记录的max值都已修复')
else:
    print('存在未修复的记录')

conn.close()
