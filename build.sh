#!/bin/bash

# ===================================
#  NodeSeek Bot Docker 管理工具
# ===================================

# === 配置 ===
# 定义镜像名称、容器名称和环境变量文件路径
IMAGE_NAME="nodeseek-bot-image"
CONTAINER_NAME="nodeseek-bot"
ENV_FILE=".env"
# 定义颜色代码，用于输出美化
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# === 工具函数 ===

# -----------------------------------
# 显示主菜单
# -----------------------------------
function show_menu() {
    clear # 清屏，使菜单更清晰
    echo -e "${BLUE}===================================${NC}"
    echo -e "${BLUE}  NodeSeek Bot Docker 管理工具   ${NC}"
    echo -e "${BLUE}===================================${NC}"
    echo -e "1. ${GREEN}启动容器${NC}"
    echo -e "2. ${GREEN}重启容器${NC}"
    echo -e "3. ${RED}停止容器${NC}"
    echo -e "4. ${BLUE}查看容器状态${NC}"
    echo -e "5. ${BLUE}查看容器日志${NC}"
    echo -e "6. ${YELLOW}重新构建镜像并启动${NC}"
    echo -e "7. ${YELLOW}修改 .env 配置文件${NC}"
    echo -e "8. ${RED}删除容器和镜像${NC}"
    echo -e "9. ${GREEN}清理未使用的 Docker 数据${NC}"
    echo -e "10. ${RED}!!! 彻底清空 Docker (危险操作) !!!${NC}"
    echo -e "q. ${NC}退出"
    echo -e "${BLUE}===================================${NC}"
}

# -----------------------------------
# 启动容器
# -----------------------------------
function start_container() {
    echo -e "\n--- 正在启动容器... ---${NC}"
    if docker compose up -d; then
        echo -e "--- ${GREEN}容器 ${CONTAINER_NAME} 已成功启动。${NC}"
    else
        echo -e "--- ${RED}容器启动失败，请检查日志。${NC}"
    fi
}

# -----------------------------------
# 重新构建镜像并启动
# -----------------------------------
function rebuild_image() {
    echo -e "\n--- 正在重新构建镜像并启动... ---${NC}"
    echo -e "   * 停止并删除现有容器...${NC}"
    docker compose down --remove-orphans
    
    echo -e "   * 构建 Docker 镜像: ${IMAGE_NAME}...${NC}"
    if docker build --network=host -t $IMAGE_NAME .; then
        echo -e "   --- ${GREEN}镜像构建成功。${NC}"
        echo -e "   * 启动新容器...${NC}"
        if docker compose up -d; then
            echo -e "   --- ${GREEN}容器已重新启动。${NC}"
        else
            echo -e "   --- ${RED}新容器启动失败。${NC}"
        fi
    else
        echo -e "   --- ${RED}镜像构建失败。${NC}"
    fi
}

# -----------------------------------
# 停止容器
# -----------------------------------
function stop_container() {
    echo -e "\n--- 正在停止容器... ---${NC}"
    if docker compose down; then
        echo -e "--- ${GREEN}容器 ${CONTAINER_NAME} 已成功停止。${NC}"
    else
        echo -e "--- ${RED}容器停止失败或容器未运行。${NC}"
    fi
}

# -----------------------------------
# 删除容器和镜像
# -----------------------------------
function remove_container() {
    echo -e "\n--- 正在删除容器和镜像... ---${NC}"
    docker compose down 2>/dev/null
    
    echo -e "   * 删除容器 ${CONTAINER_NAME}...${NC}"
    if docker rm -f $CONTAINER_NAME &>/dev/null; then
        echo -e "   --- ${GREEN}容器 ${CONTAINER_NAME} 已删除。${NC}"
    else
        echo -e "   --- ${YELLOW}容器 ${CONTAINER_NAME} 未找到或无法删除。${NC}"
    fi

    echo -e "   * 删除镜像 ${IMAGE_NAME}...${NC}"
    if docker rmi $IMAGE_NAME &>/dev/null; then
        echo -e "   --- ${GREEN}镜像 ${IMAGE_NAME} 已删除。${NC}"
    else
        echo -e "   --- ${YELLOW}镜像 ${IMAGE_NAME} 未找到或无法删除。${NC}"
    fi
    echo -e "--- ${GREEN}删除操作完成。${NC}"
}

# -----------------------------------
# 查看容器日志
# -----------------------------------
function view_logs() {
    echo -e "\n--- 正在查看容器 ${CONTAINER_NAME} 日志 (按 Ctrl+C 退出)... ---${NC}"
    if docker logs -f $CONTAINER_NAME; then
        echo -e "--- ${YELLOW}日志查看结束。${NC}"
    else
        echo -e "--- ${RED}无法获取日志，请确认容器名称是否正确或容器是否运行。${NC}"
    fi
}

# -----------------------------------
# 查看容器状态
# -----------------------------------
function container_status() {
    echo -e "\n--- 容器状态: ---${NC}"
    if docker ps -a | grep -q $CONTAINER_NAME; then
        docker ps -a | grep $CONTAINER_NAME
    else
        echo -e "--- ${YELLOW}未找到名为 ${CONTAINER_NAME} 的容器。${NC}"
    fi
}

# -----------------------------------
# 清理未使用的 Docker 数据
# -----------------------------------
function prune_docker() {
    echo -e "\n--- 正在清理未使用的 Docker 资源 (包括停止的容器、未使用的网络、悬空镜像)... ---${NC}"
    read -p "此操作会删除一些可能不再需要的资源。是否继续？(y/N): " confirm_prune
    if [[ "$confirm_prune" =~ ^[Yy]$ ]]; then
        if docker system prune -f; then
            echo -e "--- ${GREEN}清理完成。${NC}"
        else
            echo -e "--- ${RED}清理失败，请检查 Docker 服务。${NC}"
        fi
    else
        echo -e "--- ${YELLOW}清理操作已取消。${NC}"
    fi
}

# -----------------------------------
# 修改 .env 配置文件
# -----------------------------------
function edit_env() {
    echo -e "\n--- 正在编辑 .env 配置文件... ---${NC}"
    if [ ! -f "$ENV_FILE" ]; then
        echo -e "--- ${YELLOW}未找到 ${ENV_FILE} 文件，已为您创建空白文件。${NC}"
        touch "$ENV_FILE"
    fi

    echo -e "\n${BLUE}当前 ${ENV_FILE} 配置:${NC}"
    echo -e "${BLUE}-----------------------------------${NC}"
    cat "$ENV_FILE"
    echo -e "${BLUE}-----------------------------------${NC}"

    read -p "请输入要修改或添加的键 (如 TG_BOT_TOKEN)，按 Enter 跳过并退出: " key
    if [ -z "$key" ]; then
        echo -e "--- ${YELLOW}未进行任何修改，已退出。${NC}"
        return
    fi

    read -p "请输入 ${key} 的新值: " value

    if grep -q "^${key}=" "$ENV_FILE"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
        echo -e "--- ${GREEN}已更新键: ${key}=${value}${NC}"
    else
        echo -e "${key}=${value}" >> "$ENV_FILE"
        echo -e "--- ${GREEN}已添加键: ${key}=${value}${NC}"
    fi

    echo -e "\n${BLUE}修改后的 ${ENV_FILE} 配置:${NC}"
    echo -e "${BLUE}-----------------------------------${NC}"
    cat "$ENV_FILE"
    echo -e "${BLUE}-----------------------------------${NC}"
    echo -e "--- ${YELLOW}请注意：修改 .env 后，您可能需要重新启动容器（选项 1 或 2）才能使新配置生效。${NC}"
}

# -----------------------------------
# 彻底清空 Docker（危险操作）
# -----------------------------------
function reset_docker() {
    echo -e "\n${RED}!!! 警告：此操作会删除 Docker 内所有容器、镜像、网络、卷及缓存数据，无法恢复！ !!!${NC}"
    read -p "是否确认彻底清空 Docker？请键入 'yes' 继续: " confirm
    if [[ "$confirm" == "yes" ]]; then
        echo -e "\n--- 正在彻底清空 Docker... ---${NC}"
        echo -e "   * 停止所有运行中的容器...${NC}"
        docker stop $(docker ps -aq) 2>/dev/null || echo -e "   - 没有运行中的容器需要停止。${NC}"
        echo -e "   * 删除所有容器...${NC}"
        docker rm -f $(docker ps -aq) 2>/dev/null || echo -e "   - 没有容器需要删除。${NC}"
        echo -e "   * 删除所有镜像...${NC}"
        docker rmi -f $(docker images -q) 2>/dev/null || echo -e "   - 没有镜像需要删除。${NC}"
        echo -e "   * 清理所有网络...${NC}"
        docker network prune -f &>/dev/null
        echo -e "   * 清理所有卷...${NC}"
        docker volume prune -f &>/dev/null
        echo -e "   * 执行系统深度清理...${NC}"
        docker system prune -af --volumes &>/dev/null
        echo -e "--- ${GREEN}Docker 已被彻底清空。${NC}"
    else
        echo -e "--- ${YELLOW}已取消清空操作。${NC}"
    fi
}

# -----------------------------------
# 重启容器
# -----------------------------------
function restart_container() {
    echo -e "\n--- 正在重启容器 ${CONTAINER_NAME}... ---${NC}"
    if docker compose restart; then
        echo -e "--- ${GREEN}容器 ${CONTAINER_NAME} 已成功重启。${NC}"
    else
        echo -e "--- ${RED}容器重启失败，请检查容器状态或日志。${NC}"
        echo -e "   提示: 如果容器未运行，重启会失败。您可以尝试先启动容器 (选项 1)。${NC}"
    fi
}


# === 主循环 ===
while true; do
    show_menu
    read -p "$(echo -e "${YELLOW}请选择操作: ${NC}")" choice

    case "$choice" in
        1) start_container ;;
        2) restart_container ;;
        3) stop_container ;;
        4) container_status ;;
        5) view_logs ;;
        6) rebuild_image ;;
        7) edit_env ;;
        8) remove_container ;;
        9) prune_docker ;;
        10) reset_docker ;;
        q|Q) echo -e "\n--- ${BLUE}已退出。感谢使用！${NC}\n"; exit 0 ;;
        *) echo -e "\n--- ${RED}无效选项，请输入 1-10 或 q。${NC}" ;;
    esac

    echo -e "\n${BLUE}按任意键继续...${NC}"
    read -n 1 -s
done
