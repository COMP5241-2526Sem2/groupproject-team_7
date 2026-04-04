FROM m.daocloud.io/docker.io/library/node:18-alpine

WORKDIR /app

# 复制package文件
COPY package*.json ./

# 安装依赖（跳过audit以加快速度）
RUN npm ci --legacy-peer-deps --prefer-offline --no-audit 2>/dev/null || npm install --legacy-peer-deps

# 复制源代码
COPY . .

# 设置环境变量
ENV REACT_APP_API_URL=/api
ENV WATCHPACK_POLLING=true

# 暴露开发服务器端口
EXPOSE 3000

# 启动开发服务器（自动代理/api到后端）
CMD ["npm", "start"]
