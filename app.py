import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime
from PIL import Image
import json  # 确保导入 json

import requests
from io import BytesIO

# ==========================================
# 核心优化 1：给数据读取加上缓存装饰器
# 防止每次操作都重新读取硬盘 CSV，提升速度
# ==========================================
@st.cache_data
def load_data():
    """读取图像数据"""
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        # 确保 id 是字符串，防止后续匹配出错
        if 'id' in df.columns:
            df['id'] = df['id'].astype(str)
        return df
    return pd.DataFrame()

# 文件路径配置
DATA_FILE = "data_filtered.csv"

# 创建 results 目录
RESULTS_DIR = "results"
if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)

def get_user_eval_file(doctor_name):
    """根据用户名生成评估文件路径"""
    if not doctor_name:
        return ""
    # 简单的文件名清理，防止非法字符
    safe_name = "".join([c for c in doctor_name if c.isalnum() or c in (' ', '_', '-')]).strip()
    return os.path.join(RESULTS_DIR, f"evaluation_{safe_name}.csv")

# 设置页面配置
st.set_page_config(
    page_title="AI生成病理图像评估系统",
    page_icon="🔬",
    layout="wide"
)

def parse_questions(row):
    """
    解析 data.csv 中 questions 列的数据。
    该列应该是一个 JSON 字符串 (List[str])。
    但也可能是一个包含问号分隔的字符串（兼容旧数据）。
    """
    raw_val = row.get('questions', '[]')
    
    # 情况 1: 如果是空的
    if pd.isna(raw_val) or str(raw_val).strip() == "":
        return []
    
    text = str(raw_val).strip()
    
    # Robust cleanup: Replace full-width quotes and braces which break JSON parsing
    text_clean = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    
    # 情况 2: 尝试当做 JSON 解析 (这是我们 data_prep.py 生成的格式)
    try:
        import json
        parsed = json.loads(text_clean)
        if isinstance(parsed, list):
            questions = []
            for item in parsed:
                if isinstance(item, str):
                    questions.append(item)
                elif isinstance(item, dict) and 'question' in item:
                    questions.append(str(item['question']))
            return [q.strip() for q in questions if q.strip()]
    except Exception:
        pass # 解析失败，继续尝试其他格式
        
    # Try ast.literal_eval for Python-style lists (e.g. ['a', 'b'])
    try:
        import ast
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            questions = []
            for item in parsed:
                if isinstance(item, str):
                    questions.append(item)
                elif isinstance(item, dict) and 'question' in item:
                    questions.append(str(item['question']))
            return [q.strip() for q in questions if q.strip()]
    except:
        pass

    # 情况 3: 兼容旧格式（问号分隔）或 纯文本格式
    # 按照用户的需求：使用问号 ? 作为分隔符切割
    # 注意：中文问号 '？' 和英文问号 '?' 都可能存在
    # 统一替换中文问号为英文问号，方便切割
    text = text.replace('？', '?')
    
    if '?' in text:
        # 切割
        parts = text.split('?')
        
        question_list = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            # 补回问号（如果原来的分割导致问号丢失，通常 split 会丢掉分隔符）
            # 除非它已经有问号了（很少见）
            if not part.endswith('?'):
                part += '?'
                
            question_list.append(part)
        return question_list
        
    # Final fallback: return as single item list
    return [text]

def load_evaluations(doctor_name=None):
    """读取已有的评估数据，如果不存在则返回空DataFrame"""
    # 定义新的列结构
    columns = [
        "doctor_name", "image_id", 
        "score_histology", "score_cytology", "score_microenvironment", 
        "comment",
        "checked_features", 
        "qa_accuracy", # 新增：准确率
        "qa_correct_count", # 新增：勾选数
        "qa_total_count", # 新增：题目总数
        "timestamp"
    ]
    
    if not doctor_name:
        return pd.DataFrame(columns=columns)
        
    eval_file = get_user_eval_file(doctor_name)
    
    # 读取时强制 image_id 为字符串，防止 int/str 混淆
    if os.path.exists(eval_file):
        df = pd.read_csv(eval_file)
        if 'image_id' in df.columns:
            df['image_id'] = df['image_id'].astype(str)
        return df
    else:
        return pd.DataFrame(columns=columns)

def save_evaluation(evaluation_data):
    """保存或更新评估数据"""
    doctor_name = evaluation_data['doctor_name']
    df = load_evaluations(doctor_name)
    
    # 强制类型一致性
    current_img_id = str(evaluation_data['image_id'])
    
    # 检查是否已存在该医生对该图片的评估
    mask = (df['doctor_name'] == evaluation_data['doctor_name']) & (df['image_id'] == current_img_id)
    
    if mask.any():
        # 如果存在，则更新
        df.loc[mask, 'score_histology'] = evaluation_data['score_histology']
        df.loc[mask, 'score_cytology'] = evaluation_data['score_cytology']
        df.loc[mask, 'score_microenvironment'] = evaluation_data['score_microenvironment']
        df.loc[mask, 'comment'] = evaluation_data.get('comment', '')
        df.loc[mask, 'checked_features'] = evaluation_data.get('checked_features', '')
        df.loc[mask, 'qa_accuracy'] = evaluation_data.get('qa_accuracy', 0.0)
        df.loc[mask, 'qa_correct_count'] = evaluation_data.get('qa_correct_count', 0)
        df.loc[mask, 'qa_total_count'] = evaluation_data.get('qa_total_count', 0)
        df.loc[mask, 'timestamp'] = evaluation_data['timestamp']
    else:
        # 如果不存在，则追加
        new_row = pd.DataFrame([evaluation_data])
        if df.empty:
            df = new_row
        else:
            df = pd.concat([df, new_row], ignore_index=True)
            
    eval_file = get_user_eval_file(doctor_name)
    df.to_csv(eval_file, index=False, encoding='utf-8-sig')

@st.cache_data
def convert_df(df):
    return df.to_csv(index=False).encode('utf-8-sig')

@st.cache_data(show_spinner=False)
def load_image_from_url(url):
    """
    从 URL 加载图片并缓存结果
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))
        return image
    except Exception as e:
        st.error(f"Error loading image from URL: {e}")
        return None

def show_welcome_page():
    st.title("🔬 欢迎使用 AI 生成病理图像评估系统")
    st.markdown("---")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 📋 操作指南")
        st.info("""
        1. **输入姓名**：请在左侧边栏输入您的姓名。
        2. **开始评估**：点击下方的"开始评估"按钮进入任务。
        3. **评分标准**：在评估界面的滑块旁，**将鼠标悬停在 ❔ 图标上**，即可查看 1-5 分的详细评分标准。
        4. **特征勾选（Checklist）**：在右侧"特征符合度检查"区域，请仔细查看每个特征描述，**仅勾选在生成的病理图像中确实可以观察到的特征**。如果图像中没有该特征，请不要勾选。这将影响准确率计算。
        5. **重新评估**：如果您需要修改之前的评分，可以在侧边栏点击已完成的图片（绿色 ✅）进行重新评估。
        6. **下载结果**：**您可以全部评估完成后再下载**。评估完成后，请点击侧边栏底部的 **"⬇️ 下载评估数据 CSV"** 按钮，将结果文件保存并发送给研究人员。
        """)
        
        st.markdown("### 🔍 评估维度预览")
        st.markdown("""
        - **组织学结构 (Histology)**: 低倍镜下的整体观感，解剖学特征是否准确。
        - **细胞学特征 (Cytology)**: 高倍镜下的细节真实度，细胞核/质是否符合生物学规律。
        - **微环境 (Microenvironment)**: 细胞堆叠、极性及肿瘤-间质互动是否合理。
        """)

    with col2:
        st.markdown("### ⚠️ 注意事项")
        st.warning("""
        - 本次评估为**盲测**，您将无法看到生成该图像的 AI 模型名称。
        - 请保持客观，仅根据图像质量和提示词符合度进行评分。
        - **特征勾选要求**：请仔细观察图像，只勾选**确实能在显微镜下看到**的特征，不要勾选图像中不存在的特征。
        - **数据保存**：您的评估数据会自动保存，可以全部评估完成后再统一下载 CSV 文件。
        """)

    st.markdown("---")
    if st.button("🚀 开始评估", type="primary", use_container_width=True):
        st.session_state['show_home'] = False
        st.rerun()

def show_evaluation_page(df_images, df_evals, doctor_name, evaluated_ids):
    # --- 主界面逻辑 (保持完全不变) ---
    
    # 验证索引有效性
    if not (0 <= st.session_state['current_index'] < len(df_images)):
        st.error("索引越界，正在重置...")
        st.session_state['current_index'] = 0
        st.rerun()
        
    # 获取当前选中的图片数据
    current_image = df_images.iloc[st.session_state['current_index']]
    current_id = str(current_image['id'])
    
    # 检查是否是已评估图片，如果是，获取之前的评分
    previous_score = {}
    is_current_evaluated = current_id in evaluated_ids
    
    if is_current_evaluated:
        # 修正：使用 str 比较
        match_row = df_evals[(df_evals['doctor_name'] == doctor_name) & (df_evals['image_id'] == current_id)]
        if not match_row.empty:
            prev_eval = match_row.iloc[0]
            # 处理 checked_features
            prev_checked = prev_eval.get('checked_features', '')
            if pd.isna(prev_checked):
                prev_checked_list = []
            else:
                try:
                    import json
                    prev_checked_list = json.loads(str(prev_checked))
                    if not isinstance(prev_checked_list, list):
                        prev_checked_list = []
                except:
                    prev_checked_list = []

            previous_score = {
                'histology': int(prev_eval['score_histology']),
                'cytology': int(prev_eval['score_cytology']),
                'microenvironment': int(prev_eval['score_microenvironment']),
                'comment': prev_eval.get('comment', '') if pd.notna(prev_eval.get('comment', '')) else '',
                'checked_features': prev_checked_list
            }
            st.info(f"💡 您正在重新评估 **第 {st.session_state['current_index'] + 1} 张** 图片。之前的评分已自动加载。")
        else:
            # 异常情况处理
            is_current_evaluated = False
            
    if not is_current_evaluated:
        # 默认分
        previous_score = {
            'histology': 3, 
            'cytology': 3, 
            'microenvironment': 3, 
            'comment': '', 
            'checked_features': []
        }

    # 4. 界面布局
    st.subheader(f"📝 正在评估: 第 {st.session_state['current_index'] + 1} 张 - {current_image['disease']}")

    # 解析问题列表
    question_list = parse_questions(current_image)
    
    # 帮助文本定义
    help_histology = (
        "**核心：低倍镜下的整体观感**\n\n"
        "**1分 [非生物结构]**: 完全不可接受。图像呈现非生物特征，结构完全混乱。\n\n"
        "**2分 [器官错误]**: 生物学失真。看起来像细胞组织，但完全看不出是目标器官。\n\n"
        "**3分 [结构存疑]**: 似是而非。能看出是某种上皮或间叶组织，但病变结构模糊不清。\n\n"
        "**4分 [基本准确]**: 具诊断指向性。主要结构符合文字报告，背景器官特征基本吻合。\n\n"
        "**5分 [完全准确]**: 高度逼真。组织结构清晰、层次分明。病变结构典型。"
    )
    
    help_cytology = (
        "**核心：高倍镜下的细节真实度**\n\n"
        "**1分 [比例失调]**: 违反生物常识。细胞大小极度不均，核浆比完全错误。\n\n"
        "**2分 [涂抹/伪影]**: 无细胞形态。高倍镜下模糊一片，细胞核像噪点。\n\n"
        "**3分 [特征缺失]**: 通用型细胞。缺乏报告中描述的特异性，同质化严重。\n\n"
        "**4分 [特征吻合]**: 特异性呈现。能看到明显的异型性，关键特征与报告一致。\n\n"
        "**5分 [细节完美]**: 极高保真度。细胞核染色质纹理清晰，核膜清晰。"
    )
    
    help_microenvironment = (
        "**核心：细胞堆叠、极性及微环境互动**\n\n"
        "**1分 [物理堆叠]**: 无序混乱。细胞随意散落，甚至相互重叠，无组织极性。\n\n"
        "**2分 [缺乏极性]**: 排列错误。应该形成单层排列的变成了复层，缺乏紧密连接感。\n\n"
        "**3分 [孤立存在]**: 缺乏互动。肿瘤细胞成团，但缺乏纤维增生或炎性反应。\n\n"
        "**4分 [逻辑互动]**: 微环境合理。能看到细胞间的粘附性，有合理的间质反应。\n\n"
        "**5分 [生态系统]**: 高度复杂的互动。完美呈现“肿瘤-间质”对话，可见淋巴细胞浸润等。"
    )

    with st.form(key=f"eval_form_{current_id}"):
        # --- 优化布局：图片和评分控件并排显示，避免滚动 ---
        # 使用 [2.5, 2.5] 比例，左右两侧更平衡，图片区域稍大
        main_col1, main_col2 = st.columns([2.5, 2.5])
        
        # 左列：图片 + 病理信息（紧凑布局）
        with main_col1:
            st.markdown("### 🖼️ 病理图像")
            try:
                raw_path = current_image['image_path']
                # 增加图片高度，从350px增加到420px，让图片更清晰
                FIXED_HEIGHT = 420 
                
                display_src = raw_path
                if display_src.startswith("http") and "?" not in display_src:
                     # 尝试让腾讯云把图片高度限制在 800px 以内，提高清晰度
                     display_src = f"{raw_path}?imageMogr2/thumbnail/x800"

                st.markdown(
                    f"""
                    <div style="display: flex; justify-content: center; align-items: center; height: {FIXED_HEIGHT}px; background-color: #f0f2f6; border-radius: 5px; margin-bottom: 10px;">
                        <img src="{display_src}" 
                             style="max-height: {FIXED_HEIGHT}px; max-width: 100%; object-fit: contain;" 
                             alt="Pathology Image">
                    </div>
                    <div style="text-align: center; color: #666; font-size: 0.8em; margin-bottom: 15px;">
                        图片 #{st.session_state['current_index'] + 1}
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                # 病理信息（紧凑显示）
                with st.container(border=True):
                    st.markdown(f"**病种:** {current_image['disease']}")
                    st.caption(f"**提示词:** {current_image['prompt']}")
                
            except Exception as e:
                st.error(f"图片加载失败: {e}")
                st.info("请检查 data.csv 中的 image_path 路径是否正确。")

        # 右列：评分控件 + 复选框（主要操作区域）
        with main_col2:
            st.markdown("### 📊 评分与评估")
            
            # 评分量表部分
            st.markdown("**评分量表**")
            score_histology = st.slider("1. 组织学结构 (Histology Structure)", 1, 5, previous_score['histology'], help=help_histology)
            score_cytology = st.slider("2. 细胞学特征 (Cytology Features)", 1, 5, previous_score['cytology'], help=help_cytology)
            score_microenvironment = st.slider("3. 细胞间沟通/微环境 (Microenvironment)", 1, 5, previous_score['microenvironment'], help=help_microenvironment)
            
            st.markdown("---")
            
                    # --- 在 st.form 内部 ---
            st.markdown("**✅ 特征符合度检查**")

            checked_state = {} 

            if question_list:
                # 1. 先进行去重和清洗，同时保持顺序
                unique_questions = []
                seen = set()
                
                for q in question_list:
                    # 清洗数据：转字符串、去空格
                    if q is None: continue
                    text = str(q).strip()
                    if text == "": continue
                    
                    # 核心逻辑：如果这个文本没出现过，才加入列表
                    if text not in seen:
                        seen.add(text)
                        unique_questions.append(text)

                # 2. 遍历去重后的列表生成 Checkbox
                if unique_questions:
                    for i, safe_q_text in enumerate(unique_questions):
                        # 检查历史是否选中
                        is_checked = safe_q_text in previous_score['checked_features']
                        
                        # 生成 checkbox
                        # 注意：这里的 i 是去重后的索引，key 依然唯一且不会冲突
                        checked_state[safe_q_text] = st.checkbox(
                            safe_q_text, 
                            value=is_checked, 
                            key=f"chk_{current_id}_{i}" 
                        )
                else:
                    st.info("无有效特征")
            else:
                st.info("无特定特征")
            
            st.markdown("---")
            
            # 评论区域（缩小高度）
            comment = st.text_area("💬 备注/评论 (可选)", value=previous_score['comment'], height=80, placeholder="如果您觉得图像有其他具体问题，请在此评论...")
            
            # 提交按钮
            submit_button = st.form_submit_button(label="✅ 提交/更新评价", use_container_width=True, type="primary")

    if submit_button:
            # 收集勾选的特征
            final_checked_features = []
            if question_list:
                for q_text, is_checked in checked_state.items():
                    if is_checked:
                        final_checked_features.append(q_text)
            
            # 计算准确率
            correct_count = len(final_checked_features)
            total_count = len(question_list)
            accuracy = 0.0
            if total_count > 0:
                accuracy = round(correct_count / total_count, 2)

            # 5. 提交逻辑
            import json
            evaluation_data = {
                "doctor_name": doctor_name,
                "image_id": current_id,
                "score_histology": score_histology,
                "score_cytology": score_cytology,
                "score_microenvironment": score_microenvironment,
                "comment": comment,
                "checked_features": json.dumps(final_checked_features, ensure_ascii=False),
                "qa_accuracy": accuracy,
                "qa_correct_count": correct_count,
                "qa_total_count": total_count,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            save_evaluation(evaluation_data)
            st.toast(f"第 {st.session_state['current_index'] + 1} 张评价已保存！准确率: {accuracy*100}%", icon="✅")
            
            # 自动跳转逻辑
            next_index = -1
            
            # 1. 尝试找当前之后的未评估图片
            for i in range(st.session_state['current_index'] + 1, len(df_images)):
                if str(df_images.iloc[i]['id']) not in evaluated_ids:
                    next_index = i
                    break
            
            # 2. 如果后面没有，尝试找前面的未评估图片
            if next_index == -1:
                for i in range(0, st.session_state['current_index']):
                    if str(df_images.iloc[i]['id']) not in evaluated_ids:
                        next_index = i
                        break
            
            if next_index != -1:
                st.session_state['current_index'] = next_index
                time.sleep(0.5) # 稍微等待一下让 toast 显示
            else:
                if st.session_state['current_index'] < len(df_images) - 1:
                    st.session_state['current_index'] += 1
                else:
                    st.success("🎉 所有图片已评估完成！")
            
            st.rerun()

def show_admin_panel():
    """显示管理员面板，合并下载所有数据"""
    st.title("🔧 管理员面板")
    st.markdown("---")
    
    st.info(f"正在读取 `{RESULTS_DIR}` 目录下的所有评估文件...")
    
    # 1. 遍历结果文件
    all_files = [f for f in os.listdir(RESULTS_DIR) if f.startswith("evaluation_") and f.endswith(".csv")]
    
    if not all_files:
        st.warning("暂无任何评估数据文件。")
        return

    # 2. 合并数据
    df_list = []
    for filename in all_files:
        filepath = os.path.join(RESULTS_DIR, filename)
        try:
            df_temp = pd.read_csv(filepath)
            df_list.append(df_temp)
        except Exception as e:
            st.error(f"读取文件 {filename} 失败: {e}")
    
    if df_list:
        merged_df = pd.concat(df_list, ignore_index=True)
        
        st.success(f"成功合并 {len(df_list)} 个文件，共 {len(merged_df)} 条评估记录。")
        
        # 3. 显示预览
        st.subheader("📊 合并数据预览")
        st.dataframe(merged_df, use_container_width=True)
        
        # 4. 提供下载
        st.markdown("---")
        csv_data = convert_df(merged_df)
        st.download_button(
            label="⬇️ 下载合并后的总表 (all_evaluations_merged.csv)",
            data=csv_data,
            file_name=f"all_evaluations_merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            type="primary"
        )
    else:
        st.warning("没有有效的评估数据可合并。")

    # --- 危险操作区 ---
    st.markdown("---")
    with st.expander("☢️ 危险操作区 - Danger Zone"):
        st.warning("⚠️ 此区域的操作不可逆，请谨慎使用！")
        
        # 状态管理：是否显示二次确认
        if 'show_delete_confirm' not in st.session_state:
            st.session_state['show_delete_confirm'] = False
            
        if st.button("🔴 清空所有评估数据", type="primary"):
            st.session_state['show_delete_confirm'] = True
            
        if st.session_state['show_delete_confirm']:
            st.error("您确定要删除 `results/` 文件夹下的所有历史评估数据吗？此操作不可恢复！")
            
            # 简单的验证码机制
            confirm_code = st.text_input("请输入确认码 'DELETE' 以继续:", key="delete_confirm_input")
            
            col_d1, col_d2 = st.columns([1, 4])
            with col_d1:
                if st.button("💥 确认删除"):
                    if confirm_code == "DELETE":
                        # 执行删除逻辑
                        try:
                            # 1. 删除本地 CSV
                            deleted_count = 0
                            files = [f for f in os.listdir(RESULTS_DIR) if f.startswith("evaluation_") and f.endswith(".csv")]
                            for f in files:
                                os.remove(os.path.join(RESULTS_DIR, f))
                                deleted_count += 1
                            
                            st.success(f"已成功删除 {deleted_count} 个本地评估文件！页面将在 3 秒后刷新。")
                            # 清除状态
                            st.session_state['show_delete_confirm'] = False
                            time.sleep(3)
                            st.rerun()
                        except Exception as e:
                            st.error(f"删除失败: {e}")
                    else:
                        st.error("确认码错误，操作已取消。")
            
            with col_d2:
                if st.button("取消"):
                    st.session_state['show_delete_confirm'] = False
                    st.rerun()

def main():
    # 初始化 session state
    if 'show_home' not in st.session_state:
        st.session_state['show_home'] = True

    # 1. 侧边栏：输入医生姓名
    st.sidebar.header("👤 评估者信息")
    doctor_name = st.sidebar.text_input("请输入您的姓名", key="doctor_name_input")
    
    # 管理员模式开关
    is_admin_mode = False
    if doctor_name == "admin":
        is_admin_mode = st.sidebar.checkbox("🔧 管理员模式", value=False)
    
    # 增加回到首页按钮
    if st.sidebar.button("🏠 回到首页 / 操作说明"):
        st.session_state['show_home'] = True
        st.rerun()
    
    st.sidebar.info("请在评估每张图片时，仔细观察图像细节与描述的一致性。")

    # 检查是否输入了姓名
    if not doctor_name:
        st.title("🔬 AI生成病理图像评估系统")
        st.warning("⚠️ 请先在左侧边栏输入您的姓名以开始评估。")
        st.stop()  # 停止执行后续代码

    # --- 管理员模式路由 ---
    if is_admin_mode:
        show_admin_panel()
        st.stop() # 管理员模式下不显示后续的评估界面
        
    # 2. 读取数据 (已添加缓存)
    df_images = load_data()
    if df_images.empty:
        st.error(f"无法加载 {DATA_FILE}，请检查文件是否存在。")
        st.stop()

    # 确保 id 类型一致
    if 'id' in df_images.columns:
        df_images['id'] = df_images['id'].astype(str)

    df_evals = load_evaluations(doctor_name)
    
    # 获取该医生已经评估过的图片ID列表
    evaluated_ids = []
    if not df_evals.empty:
        evaluated_ids = df_evals[df_evals['doctor_name'] == doctor_name]['image_id'].unique().tolist()
    evaluated_ids = [str(i) for i in evaluated_ids]

    # 初始化 session state 中的 current_index
    if 'current_index' not in st.session_state:
        st.session_state['current_index'] = 0
        for idx, row in df_images.iterrows():
            if str(row['id']) not in evaluated_ids:
                st.session_state['current_index'] = idx
                break

    # ==========================================
    # 核心优化 2：侧边栏重构 (移除 Button Loop)
    # ==========================================
    st.sidebar.markdown("---")
    st.sidebar.header(f"📋 任务列表 ({len(df_images)} 张)")
    
    with st.sidebar:
        # 1. 构建下拉选项列表 (Options List)
        # 格式: "1. ✅ Prompt前几个字..."
        options = []
        for idx, row in df_images.iterrows():
            img_id = str(row['id'])
            is_evaluated = img_id in evaluated_ids
            status_icon = "✅" if is_evaluated else "⬜"
            
            # 截取 Prompt 方便预览，防止太长
            prompt_preview = str(row.get('prompt', 'Unknown'))[:15] + "..."
            
            # 组合成一个字符串
            option_str = f"{idx + 1}. {status_icon} {prompt_preview}"
            options.append(option_str)

        # 2. 使用 selectbox 代替 100 个 buttons
        # index 参数确保下拉框显示的总是当前图片
        selected_option = st.selectbox(
            "快速跳转 (选择图片)", 
            options, 
            index=st.session_state['current_index']
        )
        
        # 3. 检测下拉框变更，更新 index
        # 找到用户选中的那个选项在 list 中的位置
        new_index = options.index(selected_option)
        
        if new_index != st.session_state['current_index']:
            st.session_state['current_index'] = new_index
            st.session_state['show_home'] = False
            st.rerun()

        st.markdown("---")
        st.header("📥 结果下载")
        
        # 显示评估进度
        total_images = len(df_images)
        evaluated_count = len(evaluated_ids)
        progress = evaluated_count / total_images if total_images > 0 else 0
        
        st.caption(f"评估进度: {evaluated_count}/{total_images} ({progress*100:.1f}%)")
        st.progress(progress)
        
        # 实时读取数据
        df_download = load_evaluations(doctor_name)
        if not df_download.empty:
            st.info("💡 提示：您可以全部评估完成后再下载，数据会自动保存。")
            csv_data = convert_df(df_download)
            st.download_button(
                label="⬇️ 下载评估数据 CSV",
                data=csv_data,
                file_name=f"evaluation_{doctor_name}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
        else:
            st.info("暂无评估数据可下载")

    # --- 页面路由逻辑 ---
    if st.session_state['show_home']:
        show_welcome_page()
    else:
        show_evaluation_page(df_images, df_evals, doctor_name, evaluated_ids)

if __name__ == "__main__":
    main()