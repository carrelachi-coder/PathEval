#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化版：批量处理 + 缓存 + 更好的错误处理
基于您的openai_api.py进行修改
"""

import pandas as pd
import json
import os
import time
import hashlib
import pickle
import ast
from tqdm import tqdm
from typing import List, Tuple, Dict, Set, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# 导入您的openai_api模块
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from openai_api import openai_completion

# 配置
DATA_FILE = "data.csv"
BACKUP_FILE = "data.csv.backup"
OUTPUT_FILE = "data_filtered.csv"
CACHE_FILE = "question_check_cache.pkl"
BATCH_SIZE = 20  # 批量处理大小
MAX_WORKERS = 3  # 并发数

# 加载环境变量
load_dotenv()

# ==================== 辅助函数 ====================
def parse_questions_string(questions_str: Any) -> List[str]:
    """
    统一的questions解析函数
    
    参数:
        questions_str: 可能是字符串、列表或其他类型
        
    返回:
        问题字符串列表
    """
    if pd.isna(questions_str) or questions_str is None:
        return []
    
    # 转换为字符串
    s = str(questions_str).strip()
    
    # 如果已经是空字符串
    if not s or s == 'nan':
        return []
    
    # 如果看起来是JSON数组
    if s.startswith('[') and s.endswith(']'):
        # 尝试JSON解析
        try:
            data = json.loads(s)
            if isinstance(data, list):
                return [str(q).strip() for q in data if str(q).strip()]
        except json.JSONDecodeError:
            # 尝试ast.literal_eval
            try:
                data = ast.literal_eval(s)
                if isinstance(data, list):
                    return [str(q).strip() for q in data if str(q).strip()]
            except (SyntaxError, ValueError):
                # 尝试简单的字符串分割
                s = s[1:-1]  # 去掉方括号
                if s:
                    # 分割逗号，但要注意处理嵌套结构
                    questions = []
                    current = ''
                    in_quote = False
                    quote_char = None
                    
                    for char in s:
                        if char in ['"', "'"]:
                            if not in_quote:
                                in_quote = True
                                quote_char = char
                            elif quote_char == char:
                                in_quote = False
                            else:
                                current += char
                        elif char == ',' and not in_quote:
                            q = current.strip().strip("\"'")
                            if q:
                                questions.append(q)
                            current = ''
                        else:
                            current += char
                    
                    # 添加最后一个
                    if current:
                        q = current.strip().strip("\"'")
                        if q:
                            questions.append(q)
                    
                    return questions
                else:
                    return []
    
    # 如果只是单个字符串（不是列表格式）
    return [s] if s else []

def extract_unique_questions(df: pd.DataFrame) -> Set[str]:
    """从DataFrame中提取所有唯一的问题"""
    all_questions = set()
    
    for _, row in df.iterrows():
        questions_str = row.get('questions', '[]')
        questions = parse_questions_string(questions_str)
        all_questions.update(questions)
    
    return all_questions

# ==================== 主类 ====================
class QuestionFilter:
    def __init__(self, api_key=None):
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.cache = self.load_cache()
        
    def load_cache(self) -> Dict[str, Tuple[bool, str]]:
        """加载缓存"""
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"⚠️ 加载缓存失败: {e}，重新创建缓存")
                return {}
        return {}
    
    def save_cache(self):
        """保存缓存"""
        try:
            with open(CACHE_FILE, 'wb') as f:
                pickle.dump(self.cache, f)
        except Exception as e:
            print(f"⚠️ 保存缓存失败: {e}")
    
    def get_cache_key(self, question: str) -> str:
        """生成缓存键"""
        return hashlib.md5(question.encode('utf-8')).hexdigest()
    
    def check_single_question(self, question: str) -> Tuple[bool, str]:
        """检查单个问题（带缓存）"""
        cache_key = self.get_cache_key(question)
        
        # 检查缓存
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # 调用API
        try:
            is_valid, reason = self._call_gpt4_single(question)
            result = (is_valid, reason)
            self.cache[cache_key] = result
            self.save_cache()
            return result
        except Exception as e:
            print(f"❌ 检查问题失败 '{question[:50]}...': {e}")
            # 失败时默认保留（保守策略）
            return (True, f"API调用失败: {str(e)}")
    
    def batch_check_questions(self, questions: List[str]) -> Dict[str, Tuple[bool, str]]:
        """
        批量检查问题
        返回: {question: (is_valid, reason)}
        """
        if not questions:
            return {}
        
        print(f"📊 开始检查 {len(questions)} 个问题...")
        
        # 使用多线程并发处理
        results = {}
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # 提交任务
            future_to_question = {
                executor.submit(self.check_single_question, q): q 
                for q in questions
            }
            
            # 收集结果
            completed = 0
            for future in tqdm(as_completed(future_to_question), 
                             total=len(questions), 
                             desc="检查问题"):
                question = future_to_question[future]
                try:
                    is_valid, reason = future.result()
                    results[question] = (is_valid, reason)
                    completed += 1
                    
                    # 显示进度
                    if completed % 10 == 0:
                        valid_count = sum(1 for v, _ in results.values() if v)
                        invalid_count = completed - valid_count
                        print(f"  进度: {completed}/{len(questions)}, "
                              f"有效: {valid_count}, 无效: {invalid_count}")
                    
                except Exception as e:
                    print(f"❌ 处理问题 '{question[:50]}...' 失败: {e}")
                    results[question] = (True, f"处理失败: {str(e)}")
        
        return results
    
    def _call_gpt4_single(self, question: str, max_retries: int = 3) -> Tuple[bool, str]:
        """调用GPT-4检查单个问题（带重试机制）"""
        prompt = f"""你是一位病理学专家。请判断以下描述是否是在显微镜下可以直接观察到的病理特征。

判断标准：
✅ **符合**（显微镜下可观察）：细胞形态、组织结构、染色特征、细胞类型、微观结构
❌ **不符合**（非显微镜特征）：大小描述、程度判断、大体检查、临床特征、影像学特征

注意：如果核心特征是显微镜可观察的，即使带有"明显"、"显著"等程度词，也算符合。

请判断："{question}"

请严格按照以下JSON格式回答：
{{
    "is_valid": true/false,
    "reason": "判断理由（一句话）"
}}"""
        
        for attempt in range(max_retries):
            try:
                # 使用您的openai_completion函数
                response = openai_completion(
                    prompt, 
                    engine=self.engine, 
                    max_tokens=200, 
                    temperature=0
                )
                
                if not response:
                    raise ValueError("API返回空响应")
                
                content = response.strip()
                
                # 提取JSON
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    json_str = content.split("```")[1].split("```")[0].strip()
                else:
                    json_str = content
                
                # 解析JSON
                data = json.loads(json_str)
                is_valid = bool(data.get("is_valid", True))
                reason = str(data.get("reason", ""))
                
                return is_valid, reason
                
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON解析失败，响应内容: {content[:100] if 'content' in locals() else 'N/A'}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"  JSON解析失败，{wait_time}秒后重试 ({attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    raise ValueError(f"GPT返回的JSON格式无效: {e}")
                    
            except Exception as e:
                error_msg = str(e)
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"⚠️ API调用失败，{wait_time}秒后重试 ({attempt+1}/{max_retries}): {error_msg[:100]}")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"API调用失败，已重试{max_retries}次: {error_msg}")

# ==================== 主函数 ====================
def main():
    print("=" * 60)
    print("开始过滤 questions（基于您的openai_api.py优化版）")
    print("=" * 60)
    
    # 1. 读取数据
    print(f"📖 正在读取 {DATA_FILE}...")
    try:
        df = pd.read_csv(DATA_FILE)
    except FileNotFoundError:
        print(f"❌ 文件 {DATA_FILE} 不存在")
        return
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return
    
    print(f"   数据: {len(df)} 行")
    
    # 2. 备份原文件
    print(f"💾 正在备份到 {BACKUP_FILE}...")
    try:
        df.to_csv(BACKUP_FILE, index=False, encoding='utf-8-sig')
        print(f"   ✅ 备份完成")
    except Exception as e:
        print(f"❌ 备份失败: {e}")
        return
    
    # 3. 提取所有唯一的问题
    print(f"\n🔍 正在提取所有唯一的问题...")
    all_questions = extract_unique_questions(df)
    print(f"   找到 {len(all_questions)} 个唯一问题")
    
    if len(all_questions) == 0:
        print("⚠️ 没有找到任何问题，请检查数据格式")
        return
    
    # 显示前5个问题作为示例
    print(f"   示例问题:")
    for i, q in enumerate(list(all_questions)[:5]):
        print(f"     {i+1}. {q}")
    
    # 4. 初始化过滤器
    print(f"\n🤖 初始化GPT过滤器...")
    try:
        filter = QuestionFilter()
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        return
    
    # 5. 批量检查问题
    print(f"\n🔬 开始检查问题有效性...")
    print(f"   注意: 这可能需要一些时间，请耐心等待")
    
    # 先测试少量问题
    test_questions = list(all_questions)[:5]
    print(f"\n🧪 先测试前5个问题...")
    test_results = filter.check_single_question(test_questions[0])
    print(f"   测试结果: {test_questions[0]}")
    print(f"   是否有效: {test_results[0]}, 理由: {test_results[1]}")
    
    # 确认是否继续
    response = input("\n✅ 测试成功！是否继续处理所有问题？(y/n): ").strip().lower()
    if response != 'y':
        print("👋 已停止处理")
        return
    
    # 处理所有问题
    results = filter.batch_check_questions(list(all_questions))
    
    # 6. 统计结果
    valid_questions = {q for q, (is_valid, _) in results.items() if is_valid}
    invalid_questions = [(q, reason) for q, (is_valid, reason) in results.items() if not is_valid]
    
    print(f"\n" + "=" * 60)
    print("📊 检查结果统计")
    print("=" * 60)
    print(f"   总问题数: {len(all_questions)}")
    print(f"   ✅ 保留: {len(valid_questions)}")
    print(f"   ❌ 删除: {len(invalid_questions)}")
    
    if invalid_questions:
        print(f"\n   被删除的问题列表（前20个）:")
        for i, (q, reason) in enumerate(invalid_questions[:20]):
            print(f"   {i+1:2d}. {q[:80]}...")
            print(f"       理由: {reason}")
    
    # 7. 过滤数据
    print(f"\n🔄 正在过滤数据...")
    
    def filter_row_questions(questions_str):
        """过滤单行的问题"""
        questions = parse_questions_string(questions_str)
        filtered = [q for q in questions if q in valid_questions]
        return json.dumps(filtered, ensure_ascii=False) if filtered else "[]"
    
    # 添加进度条
    tqdm.pandas(desc="过滤行数据")
    df['questions'] = df['questions'].progress_apply(filter_row_questions)
    
    # 8. 统计前后对比
    print(f"\n📈 统计对比:")
    
    # 计算原始问题总数
    original_total = 0
    for _, row in pd.read_csv(BACKUP_FILE).iterrows():
        questions = parse_questions_string(row.get('questions', '[]'))
        original_total += len(questions)
    
    # 计算过滤后问题总数
    filtered_total = 0
    for _, row in df.iterrows():
        questions = parse_questions_string(row.get('questions', '[]'))
        filtered_total += len(questions)
    
    print(f"   原始问题总数: {original_total}")
    print(f"   过滤后问题总数: {filtered_total}")
    print(f"   删除问题总数: {original_total - filtered_total}")
    
    # 9. 保存结果
    print(f"\n💾 正在保存结果到 {OUTPUT_FILE}...")
    try:
        df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
        print(f"   ✅ 保存完成")
    except Exception as e:
        print(f"❌ 保存失败: {e}")
        return
    
    # 10. 最终统计
    print(f"\n" + "=" * 60)
    print("✅ 处理完成！")
    print("=" * 60)
    print(f"   输入文件: {DATA_FILE}")
    print(f"   输出文件: {OUTPUT_FILE}")
    print(f"   备份文件: {BACKUP_FILE}")
    print(f"   缓存文件: {CACHE_FILE}")
    print(f"\n   原始数据行数: {len(df)}")
    if original_total > 0:
        removal_rate = ((original_total - filtered_total) / original_total * 100)
        print(f"   过滤比例: {removal_rate:.1f}%")
    else:
        print(f"   原始问题总数为0，无法计算过滤比例")
    
    # 11. 保存统计信息
    stats = {
        "total_unique_questions": len(all_questions),
        "valid_questions": len(valid_questions),
        "invalid_questions": len(invalid_questions),
        "original_total_questions": original_total,
        "filtered_total_questions": filtered_total,
        "removed_questions": original_total - filtered_total,
        "removal_rate": (original_total - filtered_total) / original_total if original_total > 0 else 0
    }
    
    with open("filter_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    print(f"\n📄 统计信息已保存到 filter_stats.json")

if __name__ == "__main__":
    main()