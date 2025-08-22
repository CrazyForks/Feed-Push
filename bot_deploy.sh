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
    echo "4. 退出"
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
            # 如果没有输入群组ID，默认设置为 -123456
            WHITELIST_GROUP_ID="-123456"
            # 关闭白名单
            ENABLE_GROUP_VERIFY=False
            # 保存白名单状态为 False
            python3 -c "import json; json.dump({'whitelist_enabled': False}, open('whitelist_status.json', 'w'))"
        else
            # 如果输入了群组ID，开启白名单
            ENABLE_GROUP_VERIFY=True
            # 保存白名单状态为 True
            python3 -c "import json; json.dump({'whitelist_enabled': True}, open('whitelist_status.json', 'w'))"
        fi
        
        # 替换 Python 脚本中的占位符
        sed -i "s|TELEGRAM_BOT_TOKEN = \"Telegram_Bot_Token\"|TELEGRAM_BOT_TOKEN = \"$TELEGRAM_BOT_TOKEN\"|g" telegram_rss_bot.py
        sed -i "s|ROOT_ID = admin_id|ROOT_ID = $ROOT_ID|g" telegram_rss_bot.py
        sed -i "s|application.job_queue.run_repeating(check_new_posts, interval=300, first=0)|application.job_queue.run_repeating(check_new_posts, interval=$INTERVAL, first=0)|g" telegram_rss_bot.py
        sed -i "s|ENABLE_GROUP_VERIFY = False|ENABLE_GROUP_VERIFY = $ENABLE_GROUP_VERIFY|g" telegram_rss_bot.py
        sed -i "s|WHITELIST_GROUP_ID = group_id|WHITELIST_GROUP_ID = $WHITELIST_GROUP_ID|g" telegram_rss_bot.py

        # 创建 systemd 服务文件
        echo "创建 systemd 服务文件..."
        cat <<EOF > /etc/systemd/system/telegram_rss_bot.service
[Unit]
Description=Telegram RSS Bot
After=network.target

[Service]
User=root
WorkingDirectory=/home/Python_project/telegram_rss_bot
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

        echo "部署完成，Bot 应该已启动并运行。"

        ;;

      2)
        # 管理配置
        echo "进入配置管理模式..."
        echo "请输入你想修改的配置项："
        echo "1. 修改 Telegram Bot Token"
        echo "2. 修改管理员 ID"
        echo "3. 修改更新间隔时间"
        echo "4. 修改白名单群组 ID"
        echo "5. 修改进群验证启用状态"
        read -p "请输入操作编号: " config_action

        case $config_action in
          1)
            echo "请输入新的 Telegram Bot Token:"
            read TELEGRAM_BOT_TOKEN
            sed -i "s|TELEGRAM_BOT_TOKEN = .*|TELEGRAM_BOT_TOKEN = \"$TELEGRAM_BOT_TOKEN\"|g" /home/Python_project/telegram_rss_bot/telegram_rss_bot.py
            ;;
          2)
            echo "请输入新的管理员 ID:"
            read ROOT_ID
            sed -i "s|ROOT_ID = .*|ROOT_ID = $ROOT_ID|g" /home/Python_project/telegram_rss_bot/telegram_rss_bot.py
            ;;
          3)
            echo "请输入新的更新间隔时间（秒）："
            read INTERVAL
            sed -i "s|application.job_queue.run_repeating(check_new_posts, interval=.*)|application.job_queue.run_repeating(check_new_posts, interval=$INTERVAL, first=0)|g" /home/Python_project/telegram_rss_bot/telegram_rss_bot.py
            ;;
          4)
            echo "请输入新的白名单群组 ID:"
            read WHITELIST_GROUP_ID
            sed -i "s|WHITELIST_GROUP_ID = .*|WHITELIST_GROUP_ID = $WHITELIST_GROUP_ID|g" /home/Python_project/telegram_rss_bot/telegram_rss_bot.py
            ;;
          5)
            # 读取 Python 脚本中的 ENABLE_GROUP_VERIFY 配置
            ENABLE_GROUP_VERIFY=$(python3 -c "import telegram_rss_bot; print(telegram_rss_bot.ENABLE_GROUP_VERIFY)")

            echo "当前进群验证启用状态：$ENABLE_GROUP_VERIFY"

            # 修改 ENABLE_GROUP_VERIFY 状态
            echo "请输入新的进群验证启用状态 (True/False):"
            read NEW_ENABLE_GROUP_VERIFY
            # 更新 Python 脚本中的配置
            sed -i "s|ENABLE_GROUP_VERIFY = .*|ENABLE_GROUP_VERIFY = $NEW_ENABLE_GROUP_VERIFY|g" /home/Python_project/telegram_rss_bot/telegram_rss_bot.py

            ;;

          *)
            echo "无效的操作选项!"
            ;;
        esac

        # 提示修改完成
        echo "重启服务..."
        sudo systemctl restart telegram_rss_bot && sudo systemctl status telegram_rss_bot
        echo "配置修改完成！"
        ;;

      3)
        # 卸载脚本
        echo "正在卸载脚本..."
        
        # 停止并禁用服务
        sudo systemctl stop telegram_rss_bot
        sudo systemctl disable telegram_rss_bot
        sudo rm /etc/systemd/system/telegram_rss_bot.service
        sudo systemctl daemon-reload

        # 删除项目目录
        sudo rm -rf /home/Python_project/telegram_rss_bot

        # 卸载 Python 依赖
        sudo rm -rf /home/Python_project/telegram_rss_bot/venv

        # 删除软件包
        sudo apt remove --purge python3 python3-pip python3-venv wget -y
        sudo apt autoremove -y
        sudo apt clean

        # 清理日志文件
        sudo journalctl --vacuum-time=1s

        echo "卸载完成！"
        ;;

      4)
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
