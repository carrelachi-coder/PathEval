# 1. 选择基础镜像：我们要一个装好了 Python 3.9 的轻量级系统
FROM python:3.9-slim

# 2. 设置工作目录：在容器里创建一个叫 /app 的文件夹放你的代码
WORKDIR /app

# 3. 复制依赖文件：先把 requirements.txt 拷进去
COPY requirements.txt .

# 4. 安装依赖：让 Docker 在容器里运行 pip install
# (加上清华源会让下载速度飞快)
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 5. 复制所有代码：把当前目录下的所有文件（app.py, images等）都拷进容器
COPY . .

# 6. 暴露端口：告诉 Docker 这个容器要用 8501 端口
EXPOSE 8501

# 7. 启动命令：容器启动时自动运行这句话
# address=0.0.0.0 是必须的，否则你在外网打不开
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]