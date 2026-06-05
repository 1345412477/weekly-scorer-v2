import sys
sys.path.insert(0, '.')

from app.services.ai_scorer import normalize_result, apply_score_constraints, calculate_weighted_score

def test_score_conversion():
    print("=" * 70)
    print("测试分数转换逻辑")
    print("=" * 70)
    
    dimensions = [
        {'name': '工作反馈深度', 'max_score': 14, 'weight': 28},
        {'name': '进度节点明确', 'max_score': 13, 'weight': 26},
        {'name': '计划可行性', 'max_score': 10, 'weight': 20},
        {'name': '工作连续性', 'max_score': 13, 'weight': 26},
    ]
    
    test_cases = [
        {
            'name': '测试1: AI返回满分50',
            'input': {
                'dimension_scores': [
                    {'name': '工作反馈深度', 'score': 50, 'max': 50},
                    {'name': '进度节点明确', 'score': 50, 'max': 50},
                    {'name': '计划可行性', 'score': 50, 'max': 50},
                    {'name': '工作连续性', 'score': 50, 'max': 50},
                ]
            },
            'expected_total': 50
        },
        {
            'name': '测试2: AI返回平均分40',
            'input': {
                'dimension_scores': [
                    {'name': '工作反馈深度', 'score': 40, 'max': 50},
                    {'name': '进度节点明确', 'score': 40, 'max': 50},
                    {'name': '计划可行性', 'score': 40, 'max': 50},
                    {'name': '工作连续性', 'score': 40, 'max': 50},
                ]
            },
            'expected_total': 40
        },
        {
            'name': '测试3: AI返回低分（触发最低分保障）',
            'input': {
                'dimension_scores': [
                    {'name': '工作反馈深度', 'score': 10, 'max': 50},
                    {'name': '进度节点明确', 'score': 10, 'max': 50},
                    {'name': '计划可行性', 'score': 10, 'max': 50},
                    {'name': '工作连续性', 'score': 10, 'max': 50},
                ]
            },
            'expected_total': 28
        },
        {
            'name': '测试4: 真实周报数据',
            'input': {
                'dimension_scores': [
                    {'name': '工作反馈深度', 'score': 42, 'max': 50},
                    {'name': '进度节点明确', 'score': 45, 'max': 50},
                    {'name': '计划可行性', 'score': 38, 'max': 50},
                    {'name': '工作连续性', 'score': 35, 'max': 50},
                ]
            },
            'expected_total': None
        },
        {
            'name': '测试5: 分差超过22分（触发分差压缩）',
            'input': {
                'dimension_scores': [
                    {'name': '工作反馈深度', 'score': 50, 'max': 50},
                    {'name': '进度节点明确', 'score': 50, 'max': 50},
                    {'name': '计划可行性', 'score': 5, 'max': 50},
                    {'name': '工作连续性', 'score': 5, 'max': 50},
                ]
            },
            'expected_total': None
        },
    ]
    
    for i, tc in enumerate(test_cases):
        print(f"\n--- {tc['name']} ---")
        print("输入（AI返回数据）：")
        for ds in tc['input']['dimension_scores']:
            print(f"  {ds['name']}: score={ds['score']}, max={ds['max']}")
        
        result = normalize_result(tc['input'], dimensions)
        
        print("\n输出（转换后数据）：")
        for ds in result['dimension_scores']:
            print(f"  {ds['name']}: score={ds['score']}, max={ds['max']}")
        
        print(f"\n总分: {result['total_score']}")
        
        if tc['expected_total'] is not None:
            if result['total_score'] == tc['expected_total']:
                print(f"✓ 预期: {tc['expected_total']}, 实际: {result['total_score']}")
            else:
                print(f"✗ 预期: {tc['expected_total']}, 实际: {result['total_score']}")
        
        scores = [ds['score'] for ds in result['dimension_scores']]
        diff = max(scores) - min(scores)
        print(f"分差: {diff:.1f}")
        print(f"最低分保障(≥28): {'✓' if result['total_score'] >= 28 else '✗'}")
        print(f"分差控制(≤22): {'✓' if diff <= 22 else '✗'}")

if __name__ == '__main__':
    test_score_conversion()
