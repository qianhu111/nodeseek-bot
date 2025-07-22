#!/bin/bash

# === 配置 ===
IMAGE_NAME="nodeseek-bot-image"
CONTAINER_NAME="nodeseek-bot"
ENV_FILE=".env"

# === 工具函数 ===
function show_menu() {
    echo "==================================="
    echo " 🐳 NodeSeek Bot Docker 管理工具 "
    echo "==================================="
    echo "1️⃣ 启动容器"
    echo "2️⃣ 重新构建镜像并启动"
    echo "3️⃣ 停止容器"
    echo "4️⃣ 删除容器和镜像"
    echo "5️⃣ 查看容器日志"
    echo "6️⃣ 查看容器状态"
    echo "7️⃣ 清理未使用的 Docker 数据"
    echo "8️⃣ 修改 .env 配置文件"
    echo "q️⃣ 退出"
    echo "==================================="
}

function start_container() {
    echo "🚀 启动容器..."
    docker compose up -d
    echo "✅ 容器已启动"
}

function rebuild_image() {
    echo "♻️ 重新构建镜像并启动..."
    docker compose down
    docker build --network=host -t $IMAGE_NAME .
    docker compose up -d
    echo "✅ 镜像已重新构建并启动"
}

function stop_container() {
    echo "🛑 停止容器..."
    docker compose down
    echo "✅ 容器已停止"
}

function remove_container() {
    echo "🔥 删除容器和镜像..."
    docker compose down
    docker rm -f $CONTAINER_NAME 2>/dev/null || echo "ℹ️ 容器未运行"
    docker rmi $IMAGE_NAME 2>/dev/null || echo "ℹ️ 镜像不存在"
    echo "✅ 容器和镜像已删除"
}

function view_logs() {
    echo "📜 正在查看容器日志 (按 Ctrl+C 退出)..."
    docker logs -f $CONTAINER_NAME
}

function container_status() {
    echo "📊 容器状态:"
    docker ps -a | grep $CONTAINER_NAME || echo "⚠️ 未找到 $CONTAINER_NAME 容器"
}

function prune_docker() {
    echo "🧹 清理未使用的 Docker 资源..."
    docker system prune -f
    echo "✅ 清理完成"
}

function edit_env() {
    if [ ! -f "$ENV_FILE" ]; then
        echo "⚠️ 未找到 $ENV_FILE 文件，已创建空白文件。"
        touch "$ENV_FILE"
    fi

    echo "当前 .env 配置:"
    echo "-----------------------------------"
    cat "$ENV_FILE"
    echo "-----------------------------------"
    echo "请输入要修改的键 (如 TG_BOT_TOKEN):"
    read -p "> " key
    echo "请输入新的值:"
    read -p "> " value

    if grep -q "^$key=" "$ENV_FILE"; then
        sed -i "s|^$key=.*|$key=$value|" "$ENV_FILE"
        echo "✅ 已更新 $key=$value"
    else
        echo "$key=$value" >> "$ENV_FILE"
        echo "✅ 已添加 $key=$value"
    fi

    echo "修改后的 .env:"
    echo "-----------------------------------"
    cat "$ENV_FILE"
    echo "-----------------------------------"
}

# === 主循环 ===
while true; do
    show_menu
    read -p "请选择操作: " choice

    case "$choice" in
        1) start_container ;;
        2) rebuild_image ;;
        3) stop_container ;;
        4) remove_container ;;
        5) view_logs ;;
        6) container_status ;;
        7) prune_docker ;;
        8) edit_env ;;
        q) echo "👋 已退出"; exit 0 ;;
        *) echo "❌ 无效选项，请输入 1-8 或 q" ;;
    esac

    echo ""  # 空行美化
done
