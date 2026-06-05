import sqlite3
import json

dimensions = [
    {'name': '工作反馈深度', 'max_score': 14, 'weight': 28},
    {'name': '进度节点明确', 'max_score': 13, 'weight': 26},
    {'name': '计划可行性', 'max_score': 10, 'weight': 20},
    {'name': '工作连续性', 'max_score': 13, 'weight': 26},
]

dim_max_map = {d['name']: d['max_score'] for d in dimensions}

conn = sqlite3.connect('weekly_scorer.db')
c = conn.cursor()

c.execute('SELECT id, dimension_scores, total_score FROM report_scores')
rows = c.fetchall()

updated = 0
for row in rows:
    score_id, dim_scores_json, total_score = row
    dim_scores = json.loads(dim_scores_json)
    
    needs_fix = False
    new_scores = []
    for ds in dim_scores:
        name = ds['name']
        expected_max = dim_max_map.get(name, 100)
        
        if ds['max'] == 50 or ds['max'] != expected_max:
            needs_fix = True
            ds['max'] = expected_max
            
            # 转换分数
            ds['score'] = round(ds['score'] * expected_max / 50, 1)
            ds['score'] = min(ds['score'], expected_max)
        
        new_scores.append(ds)
    
    if needs_fix:
        new_total = sum(ds['score'] for ds in new_scores)
        
        # 应用约束
        if new_total < 28:
            scale = 28 / new_total
            for ds in new_scores:
                ds['score'] = round(min(ds['score'] * scale, ds['max']), 1)
            new_total = sum(ds['score'] for ds in new_scores)
        
        c.execute('UPDATE report_scores SET dimension_scores = ?, total_score = ? WHERE id = ?',
                 (json.dumps(new_scores), round(new_total, 1), score_id))
        updated += 1
        print(f'修复 ID {score_id}: {total_score} -> {round(new_total, 1)}')

conn.commit()
conn.close()
print(f'共修复 {updated} 条记录')
