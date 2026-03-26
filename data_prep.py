import pandas as pd
import os
import json
import urllib.request
import urllib.error
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from question_gen import process_description

# 1. 配置信息
excel_path = "评估数据v2.xlsx"
base_cos_url = "https://pathological-ai-1391583084.cos.ap-beijing.myqcloud.com"

# 模型列表
models = ['flux2', 'gemini', 'hunyuan', 'openai', 'pathldm', 'qwen', 'seedream']

def get_image_url(model, prompt_id):
    filename = f"image_{model}_{prompt_id}.png"
    if model=="gemini":
        filename = f"Image_gemini_{prompt_id}.png"
    if model=="seedream":
        filename = f"image_seedream_{prompt_id}.jpg"
    return f"{base_cos_url}/{model}/{filename}"

def check_url_exists(row_data):
    """
    检查 URL 是否有效（发送 HEAD 请求）
    返回: (True/False, row_data)
    """
    url = row_data['image_path']
    try:
        # 使用 HEAD 请求，只获取响应头，不下载内容，速度快
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                return True, row_data
    except Exception:
        pass
    return False, row_data

def main():
    # 2. 读取 Excel
    print(f"正在读取 {excel_path} ...")
    df = pd.read_excel(excel_path, header=None) # 假设无表头或第一行就是数据
    #df = df.iloc[10:13]
    total_rows = len(df)
    print(f"Excel 共 {total_rows} 行，开始生成候选数据...")

    prompt_qa_cache = {}
    candidate_rows = []

    # 3. 第一步：生成所有候选数据（先不检查 URL）
    for index, row in tqdm(df.iterrows(), total=total_rows, desc="解析 Prompt"):
        prompt_id = index + 1
        prompt_text = str(row.iloc[-1]).strip()
        disease_text = str(row.iloc[1]).strip()
        
        # 生成 QA
        if prompt_text in prompt_qa_cache:
            questions_json = prompt_qa_cache[prompt_text]
        else:
            try:
                # 注意：这里改用 process_description
                qa_list = process_description(prompt_text)
                
                # 提取 statement 字段作为问题
                questions_only = [item['statement'] for item in qa_list if 'statement' in item]
                
                # 保存为 JSON
                questions_json = json.dumps(questions_only, ensure_ascii=False)
                prompt_qa_cache[prompt_text] = questions_json
            except Exception as e:
                print(f"QA生成出错: {e}")
                questions_json = "[]"

        # 为 7 个模型生成候选行
        for model in models:
            image_url = get_image_url(model, prompt_id)
            unique_id = f"{prompt_id}_{model}"
            
            new_row = {
                'id': unique_id,
                'prompt_idx': prompt_id,
                'image_path': image_url,
                'model': model,
                'disease': disease_text,
                'prompt': prompt_text,
                'questions': questions_json
            }
            candidate_rows.append(new_row)

    print(f"\n生成的候选数据共 {len(candidate_rows)} 条，正在并发检查图片有效性（这可能需要几分钟）...")

    # 4. 第二步：并发检查 URL 有效性
    final_rows = []
    # 开启 50 个线程并发检查
    with ThreadPoolExecutor(max_workers=50) as executor:
        # 提交所有任务
        future_to_url = {executor.submit(check_url_exists, row): row for row in candidate_rows}
        
        # 使用 tqdm 显示进度
        for future in tqdm(as_completed(future_to_url), total=len(candidate_rows), desc="检查链接"):
            is_valid, row = future.result()
            if is_valid:
                final_rows.append(row)
            # else: print(f"跳过无效图片: {row['image_path']}") # 可选：打印跳过的图片

    # 5. 排序（可选，按 Prompt ID 排序）
    final_rows.sort(key=lambda x: int(x['prompt_idx']))

    # 6. 保存结果
    cols = ['id', 'prompt_idx', 'image_path', 'model', 'disease', 'prompt', 'questions']
    final_df = pd.DataFrame(final_rows, columns=cols)
    
    output_csv = 'data.csv'
    final_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
    
    print(f"\n处理完成！")
    print(f"原始计划: {len(candidate_rows)} 条")
    print(f"实际有效: {len(final_df)} 条 (剔除了 {len(candidate_rows) - len(final_df)} 条不存在的图片)")
    print(f"已生成 {output_csv}")

if __name__ == "__main__":
    main()
