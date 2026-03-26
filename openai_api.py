import openai
import time, sys
import os
from dotenv import load_dotenv

load_dotenv()

def openai_completion(prompt, engine="deepseek-v3-1", max_tokens=700, temperature=0):
    base_url = os.getenv("OPENAI_BASE_URL")
    

    client = openai.OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"), 
        base_url=base_url)
    
    resp =  client.chat.completions.create(
        model=engine,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
        stop=["\n\n", "<|endoftext|>"]
        )
    
    if engine=="gpt-4o":
        resp = client.chat.completions.create(
            model=engine,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,  # GPT-4 支持更长的 token，建议设大一点
            temperature=temperature,
            # 2. 删除 stop=["\n\n"]，防止回答被意外截断
        )
    
    if isinstance(resp, str):
        return resp
    
    return resp.choices[0].message.content



