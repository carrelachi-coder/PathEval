import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime
from PIL import Image
import json
import requests
from io import BytesIO

# ==========================================
# 1. 路径配置 (最优先执行)
# ==========================================
# 获取当前脚本所在的绝对文件夹路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 拼接绝对路径
DATA_FILE = os.path.join(BASE_DIR, "data_filtered.csv")
RESULTS_DIR = os.path.join(BASE_DIR, "results")

# 自动创建结果目录
if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)

# ==========================================
# 2. 页面配置
# ==========================================
st.set_page_config(
    page_title="AI生成病理图像评估系统",
    page_icon="🔬",
    layout="wide"
)

# ==========================================
# 3. 数据加载函数
# ==========================================
@st.cache_data
def load_data():
    """读取图像数据（根据 prompt_idx 筛选）"""
    if os.path.exists(DATA_FILE):
        try:
            df = pd.read_csv(DATA_FILE)
            # 确保 id 是字符串
            if 'id' in df.columns:
                df['id'] = df['id'].astype(str)
            
            # 提取 prompt_idx 并筛选
            if 'prompt_idx' in df.columns:
                df = df[(df['prompt_idx'] >= 340) & (df['prompt_idx'] <= 459)].copy()
            else:
                try:
                    df['prompt_idx'] = df['id'].str.split('_').str[0].astype(int)
                    df = df[(df['prompt_idx'] >= 340) & (df['prompt_idx'] <= 459)].copy()
                except:
                    st.error("数据列 'id' 格式不正确，无法提取 prompt_idx")
                    return pd.DataFrame()
            
            # 重置索引
            df = df.reset_index(drop=True)
            return df
        except Exception as e:
            st.error(f"读取 CSV 失败: {e}")
            return pd.DataFrame()
    else:
        return pd.DataFrame()

def get_user_eval_file(doctor_name):
    """根据用户名生成评估文件路径"""
    if not doctor_name:
        return ""
    safe_name = "".join([c for c in doctor_name if c.isalnum() or c in (' ', '_', '-')]).strip()
    return os.path.join(RESULTS_DIR, f"evaluation_{safe_name}.csv")

# ==========================================
# 4. 辅助函数
# ==========================================
def parse_questions(row):
    raw_val = row.get('questions', '[]')
    if pd.isna(raw_val) or str(raw_val).strip() == "":
        return []
    
    text = str(raw_val).strip()
    text_clean = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    
    try:
        parsed = json.loads(text_clean)
        if isinstance(parsed, list):
            return [str(item) if isinstance(item, str) else str(item.get('question','')) for item in parsed]
    except: pass
        
    try:
        import ast
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return [str(item) if isinstance(item, str) else str(item.get('question','')) for item in parsed]
    except: pass

    text = text.replace('？', '?')
    if '?' in text:
        return [p.strip() + '?' for p in text.split('?') if p.strip()]
        
    return [text]

def load_evaluations(doctor_name=None):
    columns = [
        "doctor_name", "image_id", 
        "score_histology", "score_cytology", "score_microenvironment", 
        "comment", "checked_features", 
        "qa_accuracy", "qa_correct_count", "qa_total_count", "timestamp"
    ]
    
    if not doctor_name:
        return pd.DataFrame(columns=columns)
        
    eval_file = get_user_eval_file(doctor_name)
    
    if os.path.exists(eval_file):
        try:
            df = pd.read_csv(eval_file)
            if 'image_id' in df.columns:
                df['image_id'] = df['image_id'].astype(str)
            return df
        except:
            return pd.DataFrame(columns=columns)
    else:
        return pd.DataFrame(columns=columns)

def save_evaluation(evaluation_data):
    doctor_name = evaluation_data['doctor_name']
    df = load_evaluations(doctor_name)
    current_img_id = str(evaluation_data['image_id'])
    
    mask = (df['doctor_name'] == evaluation_data['doctor_name']) & (df['image_id'] == current_img_id)
    
    if mask.any():
        for key in evaluation_data:
            df.loc[mask, key] = evaluation_data[key]
    else:
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
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    except Exception as e:
        st.error(f"Error loading image from URL: {e}")
        return None

# ==========================================
# 5. 界面显示逻辑
# ==========================================
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
        4. **特征勾选**：请仔细观察图像，仅勾选确实存在的特征。
        5. **数据保存**：评估结果会自动保存，可随时下载。
        """)
    
    with col2:
        st.markdown("### ⚠️ 注意事项")
        st.warning("本次评估为盲测，请保持客观。")

    st.markdown("---")
    if st.button("🚀 开始评估", type="primary", use_container_width=True):
        st.session_state['show_home'] = False
        st.rerun()

def show_evaluation_page(df_images, df_evals, doctor_name, evaluated_ids):
    # 索引保护
    if not (0 <= st.session_state['current_index'] < len(df_images)):
        st.session_state['current_index'] = 0
        
    df_images_reset = df_images.reset_index(drop=True)
    current_image = df_images_reset.iloc[st.session_state['current_index']]
    current_id = str(current_image['id'])
    
    # 加载历史评分
    previous_score = {
        'histology': 3, 'cytology': 3, 'microenvironment': 3, 
        'comment': '', 'checked_features': []
    }
    is_current_evaluated = current_id in evaluated_ids
    
    if is_current_evaluated:
        match_row = df_evals[(df_evals['doctor_name'] == doctor_name) & (df_evals['image_id'] == current_id)]
        if not match_row.empty:
            prev_eval = match_row.iloc[0]
            try:
                prev_checked = json.loads(str(prev_eval.get('checked_features', '')))
                if not isinstance(prev_checked, list): prev_checked = []
            except:
                prev_checked = []

            previous_score = {
                'histology': int(prev_eval['score_histology']),
                'cytology': int(prev_eval['score_cytology']),
                'microenvironment': int(prev_eval['score_microenvironment']),
                'comment': prev_eval.get('comment', '') if pd.notna(prev_eval.get('comment', '')) else '',
                'checked_features': prev_checked
            }
            st.info(f"💡 您正在重新评估 **第 {st.session_state['current_index'] + 1} 张** 图片。")

    # 界面布局
    st.subheader(f"📝 正在评估: 第 {st.session_state['current_index'] + 1} 张 - {current_image.get('disease', '未知')}")
    question_list = parse_questions(current_image)
    
    # ==========================
    # 定义评分标准帮助文本
    # ==========================
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
        main_col1, main_col2 = st.columns([2.5, 2.5])
        
        with main_col1:
            st.markdown("### 🖼️ 病理图像")
            raw_path = current_image['image_path']
            display_src = f"{raw_path}?imageMogr2/thumbnail/x800" if raw_path.startswith("http") else raw_path
            st.image(display_src, caption=f"Prompt: {current_image.get('prompt', '')}", use_column_width=True)

        with main_col2:
            st.markdown("### 📊 评分与评估")
            # 这里的 help 参数就是显示问号提示的关键
            score_histology = st.slider("1. 组织学结构", 1, 5, previous_score['histology'], help=help_histology)
            score_cytology = st.slider("2. 细胞学特征", 1, 5, previous_score['cytology'], help=help_cytology)
            score_microenvironment = st.slider("3. 微环境", 1, 5, previous_score['microenvironment'], help=help_microenvironment)
            
            st.markdown("---")
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
            comment = st.text_area("备注", value=previous_score['comment'], height=80)
            submit_button = st.form_submit_button(label="✅ 提交/更新评价", type="primary")

    if submit_button:
        final_checked_features = [k for k, v in checked_state.items() if v]
        correct_count = len(final_checked_features)
        total_count = len(question_list)
        accuracy = round(correct_count / total_count, 2) if total_count > 0 else 0.0

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
        st.toast(f"保存成功！准确率: {accuracy*100}%", icon="✅")
        
        # 自动跳转下一张
        next_index = -1
        for i in range(st.session_state['current_index'] + 1, len(df_images)):
            if str(df_images.iloc[i]['id']) not in evaluated_ids:
                next_index = i
                break
        
        if next_index != -1:
            st.session_state['current_index'] = next_index
        elif st.session_state['current_index'] < len(df_images) - 1:
            st.session_state['current_index'] += 1
        else:
            st.success("🎉 所有图片已评估完成！")
            
        time.sleep(0.5)
        st.rerun()

def show_admin_panel():
    st.title("🔧 管理员面板")
    st.info(f"数据目录: {RESULTS_DIR}")
    # (省略部分管理员代码以保持简洁)

def main():
    if 'show_home' not in st.session_state:
        st.session_state['show_home'] = True

    # 注意：这里是你刚才代码中的标题，对应 Link 1 (>=459)
    st.sidebar.header("👤 Link 2 (340-459)")
    doctor_name = st.sidebar.text_input("请输入您的姓名", key="doctor_name_input")
    
    if doctor_name == "admin":
        if st.sidebar.checkbox("管理员模式"):
            show_admin_panel()
            return

    if st.sidebar.button("🏠 回到首页"):
        st.session_state['show_home'] = True
        st.rerun()

    if not doctor_name:
        st.title("🔬 AI生成病理图像评估系统")
        st.warning("⚠️ 请先在左侧边栏输入您的姓名。")
        st.stop()

    # 读取数据
    df_images = load_data()
    if df_images.empty:
        st.error(f"❌ 无法加载数据！请检查服务器上是否存在 {DATA_FILE}")
        st.stop()

    if 'id' in df_images.columns:
        df_images['id'] = df_images['id'].astype(str)

    df_evals = load_evaluations(doctor_name)
    evaluated_ids = []
    if not df_evals.empty:
        evaluated_ids = df_evals[df_evals['doctor_name'] == doctor_name]['image_id'].unique().tolist()
    evaluated_ids = [str(i) for i in evaluated_ids]

    if 'current_index' not in st.session_state:
        st.session_state['current_index'] = 0
        for idx, row in df_images.iterrows():
            if str(row['id']) not in evaluated_ids:
                st.session_state['current_index'] = idx
                break

    # 侧边栏任务列表
    st.sidebar.markdown("---")
    st.sidebar.header(f"📋 任务列表 ({len(df_images)} 张)")
    
    df_images_reset = df_images.reset_index(drop=True)
    options = []
    for idx, row in df_images_reset.iterrows():
        img_id = str(row['id'])
        status = "✅" if img_id in evaluated_ids else "⬜"
        prompt_txt = str(row.get('prompt', 'Unknown'))[:15]
        options.append(f"{idx + 1}. {status} {prompt_txt}...")

    current_idx = st.session_state.get('current_index', 0)
    if current_idx >= len(options): current_idx = 0
    
    if options:
        selected_option = st.sidebar.selectbox("快速跳转", options, index=current_idx)
        if selected_option:
            new_index = options.index(selected_option)
            if new_index != st.session_state['current_index']:
                st.session_state['current_index'] = new_index
                st.rerun()

    # 结果下载
    st.sidebar.markdown("---")
    if not df_evals.empty:
        csv_data = convert_df(df_evals)
        st.sidebar.download_button(
            label="⬇️ 下载评估结果",
            data=csv_data,
            file_name=f"eval_link1_{doctor_name}.csv",
            mime="text/csv"
        )

    if st.session_state['show_home']:
        show_welcome_page()
    else:
        show_evaluation_page(df_images, df_evals, doctor_name, evaluated_ids)

if __name__ == "__main__":
    main()