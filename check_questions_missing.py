#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 data_filtered.csv 中 questions 列是否有缺失值（空值）
"""

import pandas as pd
import json
import ast

DATA_FILE = "data_filtered.csv"

def parse_questions_string(questions_str):
    """解析 questions 字符串为列表"""
    if pd.isna(questions_str) or questions_str is None:
        return []
    
    s = str(questions_str).strip()
    if not s or s == 'nan' or s == '[]':
        return []
    
    # 尝试 JSON 解析
    if s.startswith('[') and s.endswith(']'):
        try:
            data = json.loads(s)
            if isinstance(data, list):
                return [str(q).strip() for q in data if str(q).strip()]
        except json.JSONDecodeError:
            try:
                data = ast.literal_eval(s)
                if isinstance(data, list):
                    return [str(q).strip() for q in data if str(q).strip()]
            except:
                return []
    
    return [s] if s else []

def check_missing_questions(df):
    """检查 questions 列中的缺失值"""
    print("=" * 60)
    print("检查 questions 列中的缺失值")
    print("=" * 60)
    
    total_rows = len(df)
    
    # 1. 检查 pandas 层面的缺失值
    null_count = df['questions'].isna().sum()
    print(f"\n📊 统计结果:")
    print(f"   总行数: {total_rows}")
    print(f"   pandas 检测到的空值 (NaN): {null_count} 行")
    
    # 2. 检查实际内容是否为空
    empty_rows = []
    rows_with_empty_list = []
    
    for idx, row in df.iterrows():
        questions_str = row.get('questions', '[]')
        
        # 检查是否是 pandas 的 NaN
        if pd.isna(questions_str):
            empty_rows.append({
                'row_index': idx,
                'id': row.get('id', 'N/A'),
                'reason': 'pandas NaN'
            })
            continue
        
        # 检查字符串是否为空或只有空列表
        s = str(questions_str).strip()
        if not s or s == 'nan' or s == '[]':
            rows_with_empty_list.append({
                'row_index': idx,
                'id': row.get('id', 'N/A'),
                'value': s,
                'reason': '空字符串或空列表'
            })
            continue
        
        # 解析并检查是否为空列表
        questions = parse_questions_string(questions_str)
        if len(questions) == 0:
            rows_with_empty_list.append({
                'row_index': idx,
                'id': row.get('id', 'N/A'),
                'value': s[:50] if len(s) > 50 else s,
                'reason': '解析后为空列表'
            })
    
    total_empty = len(empty_rows) + len(rows_with_empty_list)
    
    print(f"   实际为空的行数: {total_empty} 行")
    print(f"      - pandas NaN: {len(empty_rows)} 行")
    print(f"      - 空字符串/空列表: {len(rows_with_empty_list)} 行")
    print(f"   有内容的行数: {total_rows - total_empty} 行")
    
    if empty_rows:
        print(f"\n⚠️  发现 {len(empty_rows)} 行是 pandas NaN:")
        for i, item in enumerate(empty_rows[:10], 1):
            print(f"   {i}. 行 {item['row_index']} (id: {item['id']})")
        if len(empty_rows) > 10:
            print(f"   ... 还有 {len(empty_rows) - 10} 行")
    
    if rows_with_empty_list:
        print(f"\n⚠️  发现 {len(rows_with_empty_list)} 行是空字符串或空列表:")
        for i, item in enumerate(rows_with_empty_list[:10], 1):
            print(f"   {i}. 行 {item['row_index']} (id: {item['id']})")
            print(f"       值: '{item['value']}'")
            print(f"       原因: {item['reason']}")
        if len(rows_with_empty_list) > 10:
            print(f"   ... 还有 {len(rows_with_empty_list) - 10} 行")
    
    if total_empty == 0:
        print(f"\n✅ 没有发现缺失值！所有行都有 questions 内容。")
    else:
        # 保存报告
        if empty_rows or rows_with_empty_list:
            report_data = empty_rows + rows_with_empty_list
            report_df = pd.DataFrame(report_data)
            report_file = "questions_missing_report.csv"
            report_df.to_csv(report_file, index=False, encoding='utf-8-sig')
            print(f"\n   📄 详细报告已保存到: {report_file}")
    
    return total_empty

def main():
    print(f"📖 正在读取 {DATA_FILE}...")
    try:
        df = pd.read_csv(DATA_FILE)
        print(f"   成功读取 {len(df)} 行数据\n")
    except FileNotFoundError:
        print(f"❌ 文件 {DATA_FILE} 不存在")
        return
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return
    
    # 检查 questions 列
    if 'questions' not in df.columns:
        print("❌ 文件中没有 'questions' 列")
        return
    
    # 执行检查
    missing_count = check_missing_questions(df)
    
    print(f"\n" + "=" * 60)
    print("✅ 检查完成")
    print("=" * 60)
    
    if missing_count > 0:
        print(f"\n💡 建议: 发现 {missing_count} 行 questions 为空，可能需要检查过滤过程。")

if __name__ == "__main__":
    main()

