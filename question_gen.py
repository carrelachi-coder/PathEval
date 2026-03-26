import json
try:
    from openai_api import openai_completion
except ImportError:
    from .openai_api import openai_completion
def process_description(description):
    """
    简化版处理流程：
    1. LLM 负责提取并拆解成短句列表 (JSON List)
    2. Python 负责将其包装成 QA 格式
    """
    prompt = """
    作为一个病理学专家，请处理以下病理描述。

    任务目标：
    从文本中提取用于验证生成的病理图像（HE染色）是否准确的视觉特征。

    处理步骤：
    1. **提取范围**：仅关注“镜下所见/显微镜观察”以及描述细胞/组织形态的段落。
    2. **排除内容**：剔除基本资料（年龄、性别）、影像结果（CT、MRI、超声、内镜）、大体检查（肉眼所见）、免疫组化结果、以及疾病定义的科普性文字。
    3. **合并去重**：将提取到的信息合并，如果“诊断”和“镜下所见”描述了同一个特征，请合并它们，不要重复。
    4. **拆解（关键步骤）**：将整理后的描述拆解为独立的、不可再分的**短句**列表。每一个短句必须是一个可以在显微镜下观察到的视觉事实。

    输入示例：
    Description: 鼻息肉：鼻息肉是鼻腔和鼻窦黏膜的慢性炎症性病变，主要根据组织形态学分为水肿型、纤维增生型等，其中水肿型最常见，特征为间质水肿及嗜酸性粒细胞浸润。诊断依据：常表现为鼻塞、多发性手术史；镜下上皮被覆假复层纤毛柱状上皮，间质显著水肿。基本资料：男，66岁，曾多次接受鼻息肉手术。大体检查：灰粉质细组织4块，总大小2厘米×2厘米×0.5厘米。镜下所见：肿物呈息肉样，被覆假复层纤毛柱状上皮，伴间质水肿和嗜酸性粒细胞浸润。病理诊断：鼻息肉，伴大量嗜酸性粒细胞浸润。根据上述信息，请生成一份经 HE 染色的真实病理图像。

    思考过程：仅提取镜下所见/显微镜观察的内容：肿物呈息肉样，被覆假复层纤毛柱状上皮，伴间质水肿和嗜酸性粒细胞浸润。将其拆解为4个独立特征：1. 肿物整体呈息肉样结构；2.表面被覆假复层纤毛柱状上皮；3.间质可见显著水肿；4.可见嗜酸性粒细胞浸润。
    输出示例（严格 JSON 字符串列表）：
    [
        "肿物整体呈息肉样结构",
        "表面被覆假复层纤毛柱状上皮",
        "间质可见显著水肿",
        "可见嗜酸性粒细胞浸润"
    ]

    现在请处理以下描述：
    Description: {description}
    """
    prompt = prompt.replace("{description}", description)

    # 2. 调用 API
    resp_text = openai_completion(prompt)
    
    # 3. 解析 JSON 列表
    # 尝试清洗返回的文本，防止模型输出 ```json ... ``` 包裹的内容
    clean_text = resp_text.strip()
    
    # 使用正则去除 Markdown 代码块标记 (```json ... ```)
    # 这样更稳健，不用担心第一行是不是 json 或者是空行
    import re
    code_block_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    match = re.search(code_block_pattern, clean_text, re.IGNORECASE)
    if match:
        clean_text = match.group(1)
    
    try:
        # 尝试修复常见的 JSON 截断问题 (虽然模型通常会输出完整)
        # 如果是字符串列表 ["...", "...] 缺了引号或括号，这里很难完美修复
        # 但我们至少可以打印出来调试
        statements = json.loads(clean_text)
        
        # 兼容性处理：模型有时候返回 ["str1", "str2"] 而不是 [{"statement": "str1"}]
        # 我们在这里统一转换成 dict 列表格式
        final_list = []
        if isinstance(statements, list):
            for item in statements:
                if isinstance(item, str):
                    final_list.append({"statement": item})
                elif isinstance(item, dict) and "statement" in item:
                    final_list.append(item)
        
        return final_list
        
    except json.JSONDecodeError:
        print(f"JSON 解析失败，原始返回: {resp_text}")
        return []

    # 4. 将短句转换为评测用的 QA 格式
    # 既然这些都是从描述中提取的“事实”，那么 Answer 默认为“是”
    qa_list = []
    
    for statement in statements:
       

        qa_item = {
           
            "statement":statement # 保留原始陈述，方便后续使用
        }
        qa_list.append(qa_item)

    return qa_list
