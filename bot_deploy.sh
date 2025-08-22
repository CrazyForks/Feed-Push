#!/bin/bash

# 主菜单
while true; do
    clear
    echo -e "\033[92m>RSS推送机器人<\033[0m"
    echo -e "\033[92mAuthor：Rational\033[0m"
    echo "请选择操作:"
    echo "1. 安装脚本"
    echo "2. 管理相关配置"
    echo "3. 卸载脚本"
    echo "4. 查看服务状态"
    echo "5. 退出"
    read -p "请输入操作编号: " action

    # 检查用户输入
    case $action in
      1)
        # 完全安装脚本
        echo "正在进行完全安装..."
        
        # 检查是否为 root 用户
        if [ "$(id -u)" != "0" ]; then
            echo "请使用 sudo 或 root 权限运行此脚本！"
            exit 1
        fi

        # 更新系统
        echo "更新系统..."
        apt update && apt upgrade -y

        # 安装 Python 及工具
        echo "安装 Python3 和 pip..."
        apt install python3 python3-pip python3-venv wget -y

        # 创建项目目录
        echo "创建项目目录 /home/Python_project/telegram_rss_bot..."
        mkdir -p /home/Python_project/telegram_rss_bot && cd /home/Python_project/telegram_rss_bot

        # 创建虚拟环境
        echo "创建 Python 虚拟环境..."
        python3 -m venv venv

        # 激活虚拟环境
        source venv/bin/activate

        # 安装依赖
        echo "安装所需的 Python 库..."
        pip install python-telegram-bot[ext,job-queue] feedparser requests

        # 下载 Python 脚本
        echo "下载 telegram_rss_bot.py 脚本..."
        wget -O telegram_rss_bot.py https://raw.githubusercontent.com/ecouus/Feed-Push/refs/heads/main/telegram_rss_bot.py

        # 检查下载是否成功
        if [ ! -f "telegram_rss_bot.py" ]; then
            echo "错误：无法下载 telegram_rss_bot.py 脚本"
            exit 1
        fi

        # 获取用户输入
        echo "请输入 Telegram Bot Token（通过@BotFather创建）:"
        read TELEGRAM_BOT_TOKEN
        echo "请输入管理员的 Telegram 用户 ID (可通过@userinfobot获取):"
        read ROOT_ID
        echo "请输入更新间隔时间（秒，默认为 300）："
        read INTERVAL
        INTERVAL=${INTERVAL:-300}  # 默认值为 300
        
        # 询问是否启用白名单
        echo "请输入白名单群组 ID（如果不启用白名单，直接回车）："
        read WHITELIST_GROUP_ID
        
        if [ -z "$WHITELIST_GROUP_ID" ]; then
            # 如果没有输入群组ID，默认设置为 false
            WHITELIST_GROUP_ID="false"
            # 关闭白名单
            ENABLE_GROUP_VERIFY="False"
        else
            # 如果输入了群组ID，开启白名单
            ENABLE_GROUP_VERIFY="True"
        fi
        
        # 创建环境变量文件
        echo "创建环境变量配置文件..."
        cat <<EOF > .env
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
ROOT_ID=$ROOT_ID
WHITELIST_GROUP_ID=$WHITELIST_GROUP_ID
ENABLE_GROUP_VERIFY=$ENABLE_GROUP_VERIFY
UPDATE_INTERVAL=$INTERVAL
EOF

        # 创建 systemd 服务文件
        echo "创建 systemd 服务文件..."
        cat <<EOF > /etc/systemd/system/telegram_rss_bot.service
[Unit]
Description=Telegram RSS Bot
After=network.target

[Service]
User=root
WorkingDirectory=/home/Python_project/telegram_rss_bot
Environment=TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
Environment=ROOT_ID=$ROOT_ID
Environment=WHITELIST_GROUP_ID=$WHITELIST_GROUP_ID
Environment=ENABLE_GROUP_VERIFY=$ENABLE_GROUP_VERIFY
Environment=UPDATE_INTERVAL=$INTERVAL
ExecStart=/home/Python_project/telegram_rss_bot/venv/bin/python /home/Python_project/telegram_rss_bot/telegram_rss_bot.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

        # 重新加载 systemd 配置
        systemctl daemon-reload

        # 启动服务并设置开机启动
        echo "启动 Telegram RSS Bot 服务..."
        systemctl start telegram_rss_bot
        systemctl enable telegram_rss_bot

        # 检查服务状态
        sleep 3
        if systemctl is-active --quiet telegram_rss_bot; then
            echo "✅ 部署完成，Bot 已成功启动并运行。"
        else
            echo "❌ 服务启动失败，请检查日志："
            systemctl status telegram_rss_bot
        fi

        ;;

      2)
        # 管理配置
        echo "进入配置管理模式..."
        
        # 检查服务是否存在
        if [ ! -f "/etc/systemd/system/telegram_rss_bot.service" ]; then
            echo "错误：未找到已安装的服务，请先安装脚本。"
            read -p "按 Enter 返回主菜单..."
            continue
        fi
        
        echo "请输入你想修改的配置项："
        echo "1. 修改 Telegram Bot Token"
        echo "2. 修改管理员 ID"
        echo "3. 修改更新间隔时间"
        echo "4. 修改白名单群组 ID"
        echo "5. 修改进群验证启用状态"
        echo "6. 查看当前配置"
        read -p "请输入操作编号: " config_action

        case $config_action in
          1)
            echo "请输入新的 Telegram Bot Token:"
            read NEW_TELEGRAM_BOT_TOKEN
            # 更新服务文件
            sed -i "s|Environment=TELEGRAM_BOT_TOKEN=.*|Environment=TELEGRAM_BOT_TOKEN=$NEW_TELEGRAM_BOT_TOKEN|g" /etc/systemd/system/telegram_rss_bot.service
            # 更新环境变量文件
            if [ -f "/home/Python_project/telegram_rss_bot/.env" ]; then
                sed -i "s|TELEGRAM_BOT_TOKEN=.*|TELEGRAM_BOT_TOKEN=$NEW_TELEGRAM_BOT_TOKEN|g" /home/Python_project/telegram_rss_bot/.env
            fi
            echo "✅ Telegram Bot Token 已更新"
            ;;
          2)
            echo "请输入新的管理员 ID:"
            read NEW_ROOT_ID
            # 更新服务文件
            sed -i "s|Environment=ROOT_ID=.*|Environment=ROOT_ID=$NEW_ROOT_ID|g" /etc/systemd/system/telegram_rss_bot.service
            # 更新环境变量文件
            if [ -f "/home/Python_project/telegram_rss_bot/.env" ]; then
                sed -i "s|ROOT_ID=.*|ROOT_ID=$NEW_ROOT_ID|g" /home/Python_project/telegram_rss_bot/.env
            fi
            echo "✅ 管理员 ID 已更新"
            ;;
          3)
            echo "请输入新的更新间隔时间（秒）："
            read NEW_INTERVAL
            # 更新服务文件
            sed -i "s|Environment=UPDATE_INTERVAL=.*|Environment=UPDATE_INTERVAL=$NEW_INTERVAL|g" /etc/systemd/system/telegram_rss_bot.service
            # 更新环境变量文件
            if [ -f "/home/Python_project/telegram_rss_bot/.env" ]; then
                sed -i "s|UPDATE_INTERVAL=.*|UPDATE_INTERVAL=$NEW_INTERVAL|g" /home/Python_project/telegram_rss_bot/.env
            fi
            echo "✅ 更新间隔时间已更新"
            ;;
          4)
            echo "请输入新的白名单群组 ID（输入 false 禁用白名单）:"
            read NEW_WHITELIST_GROUP_ID
            # 更新服务文件
            sed -i "s|Environment=WHITELIST_GROUP_ID=.*|Environment=WHITELIST_GROUP_ID=$NEW_WHITELIST_GROUP_ID|g" /etc/systemd/system/telegram_rss_bot.service
            # 更新环境变量文件
            if [ -f "/home/Python_project/telegram_rss_bot/.env" ]; then
                sed -i "s|WHITELIST_GROUP_ID=.*|WHITELIST_GROUP_ID=$NEW_WHITELIST_GROUP_ID|g" /home/Python_project/telegram_rss_bot/.env
            fi
            echo "✅ 白名单群组 ID 已更新"
            ;;
          5)
            # 获取当前状态
            CURRENT_VERIFY=$(grep "Environment=ENABLE_GROUP_VERIFY=" /etc/systemd/system/telegram_rss_bot.service | cut -d'=' -f3)
            echo "当前进群验证启用状态：$CURRENT_VERIFY"

            # 修改 ENABLE_GROUP_VERIFY 状态
            echo "请输入新的进群验证启用状态 (True/False):"
            read NEW_ENABLE_GROUP_VERIFY
            
            # 验证输入
            if [[ "$NEW_ENABLE_GROUP_VERIFY" != "True" && "$NEW_ENABLE_GROUP_VERIFY" != "False" ]]; then
                echo "❌ 无效输入，请输入 True 或 False"
                continue
            fi
            
            # 更新服务文件
            sed -i "s|Environment=ENABLE_GROUP_VERIFY=.*|Environment=ENABLE_GROUP_VERIFY=$NEW_ENABLE_GROUP_VERIFY|g" /etc/systemd/system/telegram_rss_bot.service
            # 更新环境变量文件
            if [ -f "/home/Python_project/telegram_rss_bot/.env" ]; then
                sed -i "s|ENABLE_GROUP_VERIFY=.*|ENABLE_GROUP_VERIFY=$NEW_ENABLE_GROUP_VERIFY|g" /home/Python_project/telegram_rss_bot/.env
            fi
            echo "✅ 进群验证状态已更新"
            ;;
          6)
            echo "📋 当前配置信息："
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            if [ -f "/etc/systemd/system/telegram_rss_bot.service" ]; then
                echo "Bot Token: $(grep "Environment=TELEGRAM_BOT_TOKEN=" /etc/systemd/system/telegram_rss_bot.service | cut -d'=' -f3 | sed 's/^.*\(.\{8\}\)$/***\1/')"
                echo "管理员 ID: $(grep "Environment=ROOT_ID=" /etc/systemd/system/telegram_rss_bot.service | cut -d'=' -f3)"
                echo "更新间隔: $(grep "Environment=UPDATE_INTERVAL=" /etc/systemd/system/telegram_rss_bot.service | cut -d'=' -f3) 秒"
                echo "白名单群组 ID: $(grep "Environment=WHITELIST_GROUP_ID=" /etc/systemd/system/telegram_rss_bot.service | cut -d'=' -f3)"
                echo "进群验证: $(grep "Environment=ENABLE_GROUP_VERIFY=" /etc/systemd/system/telegram_rss_bot.service | cut -d'=' -f3)"
            else
                echo "❌ 未找到配置文件"
            fi
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            read -p "按 Enter 继续..."
            continue
            ;;
          *)
            echo "无效的操作选项!"
            continue
            ;;
        esac

        # 重新加载并重启服务
        echo "重新加载配置并重启服务..."
        systemctl daemon-reload
        systemctl restart telegram_rss_bot
        
        # 检查服务状态
        sleep 3
        if systemctl is-active --quiet telegram_rss_bot; then
            echo "✅ 配置修改完成，服务已重启！"
        else
            echo "❌ 服务重启失败，请检查日志："
            systemctl status telegram_rss_bot
        fi
        ;;

      3)
        # 卸载脚本
        echo "⚠️  确认要卸载 RSS 推送机器人吗？这将删除所有相关文件和配置。"
        read -p "输入 'yes' 确认卸载: " confirm
        
        if [ "$confirm" != "yes" ]; then
            echo "取消卸载操作"
            read -p "按 Enter 返回主菜单..."
            continue
        fi
        
        echo "正在卸载脚本..."
        
        # 停止并禁用服务
        systemctl stop telegram_rss_bot 2>/dev/null
        systemctl disable telegram_rss_bot 2>/dev/null
        rm -f /etc/systemd/system/telegram_rss_bot.service
        systemctl daemon-reload

        # 删除项目目录
        rm -rf /home/Python_project/telegram_rss_bot

        # 询问是否删除 Python 环境
        echo "是否同时卸载 Python 相关软件包？(y/n)"
        read -p "注意：这可能影响其他 Python 项目: " remove_python
        
        if [ "$remove_python" = "y" ] || [ "$remove_python" = "Y" ]; then
            apt remove --purge python3 python3-pip python3-venv wget -y
            apt autoremove -y
            apt clean
        fi

        echo "✅ 卸载完成！"
        ;;

      4)
        # 查看服务状态
        echo "📊 服务状态信息："
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        if systemctl is-active --quiet telegram_rss_bot; then
            echo "🟢 服务状态: 运行中"
        else
            echo "🔴 服务状态: 已停止"
        fi
        
        if systemctl is-enabled --quiet telegram_rss_bot; then
            echo "🟢 开机启动: 已启用"
        else
            echo "🔴 开机启动: 已禁用"
        fi
        
        echo ""
        echo "📋 详细状态:"
        systemctl status telegram_rss_bot
        
        echo ""
        echo "📝 最近日志 (最新20行):"
        journalctl -u telegram_rss_bot -n 20 --no-pager
        
        echo ""
        echo "可用操作:"
        echo "1. 启动服务: systemctl start telegram_rss_bot"
        echo "2. 停止服务: systemctl stop telegram_rss_bot"
        echo "3. 重启服务: systemctl restart telegram_rss_bot"
        echo "4. 查看完整日志: journalctl -u telegram_rss_bot -f"
        ;;

      5)
        # 退出脚本
        echo "退出脚本..."
        break
        ;;

      *)
        echo "无效的操作选项!"
        ;;
    esac

    # 返回主菜单前等待
    read -p "按 Enter 返回主菜单..."
done
