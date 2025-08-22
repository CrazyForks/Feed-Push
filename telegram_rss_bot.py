from telegram.ext import Application, CommandHandler
from telegram.helpers import escape_markdown
import feedparser
import requests
import os
import json
import re

# 配置 - 从环境变量读取
CACHE_FILE = "./data/rss_cache3.txt"  # 本地缓存文件
USER_DATA_FILE = "./data/user_data.json"  # 存储用户规则和 RSS 源
ALLOWED_USERS_FILE = "./data/allowed_users.json"  # 存储白名单的文件
WHITELIST_STATUS_FILE = "./data/whitelist_status.json"  # 白名单模式状态文件

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ROOT_ID = int(os.getenv('ROOT_ID', 0))
WHITELIST_GROUP_ID = os.getenv('WHITELIST_GROUP_ID', '')
ENABLE_GROUP_VERIFY = os.getenv('ENABLE_GROUP_VERIFY', 'false').lower() == 'true'
UPDATE_INTERVAL = int(os.getenv('UPDATE_INTERVAL', 300))

# 确保数据目录存在
os.makedirs('data', exist_ok=True)

ENABLE_GROUP_VERIFY = False  # 控制是否开启进群验证

# 加载白名单
def load_allowed_users():
    if os.path.exists(ALLOWED_USERS_FILE):
        with open(ALLOWED_USERS_FILE, "r") as f:
            try:
                return set(json.load(f))
            except json.JSONDecodeError:
                return set()
    return set()


# 保存白名单
def save_allowed_users(users):
    with open(ALLOWED_USERS_FILE, "w") as f:
        json.dump(list(users), f)


def is_allowed_user(user_id):
    if not is_whitelist_enabled():
        return True
    allowed_users = load_allowed_users()
    return user_id in allowed_users


# 检查用户是否在特定群组中
async def is_user_in_group(user_id, context):
    # 如果白名单已关闭（WHITELIST_GROUP_ID = false），直接返回 True
    if WHITELIST_GROUP_ID == "false":
        return True
    
    # 如果进群验证关闭，直接返回 True
    if not ENABLE_GROUP_VERIFY:
        return True
        
    try:
        # 当 WHITELIST_GROUP_ID 为具体群组 ID 且开启进群验证时，检查用户是否在群组中
        member = await context.bot.get_chat_member(WHITELIST_GROUP_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Error checking if user {user_id} is in group: {e}")
        return False

# 添加切换进群验证的命令处理函数
async def toggle_group_verify(update, context):
    user_id = update.effective_user.id
    if user_id != ROOT_ID:
        await update.message.reply_text("只有管理员可以操作进群验证开关。")
        return

    if len(context.args) < 1 or context.args[0].lower() not in ["on", "off"]:
        await update.message.reply_text("请提供有效参数：/group_verify on 或 /group_verify off")
        return

    global ENABLE_GROUP_VERIFY
    ENABLE_GROUP_VERIFY = context.args[0].lower() == "on"
    status_text = "开启" if ENABLE_GROUP_VERIFY else "关闭"
    await update.message.reply_text(f"进群验证已{status_text}。")

# 白名单模式状态文件加载与保存
def load_whitelist_status():
    # 检查文件是否存在
    if os.path.exists(WHITELIST_STATUS_FILE):
        with open(WHITELIST_STATUS_FILE, "r") as f:
            try:
                # 尝试解析 JSON 内容并返回白名单启用状态，默认为 False
                return json.load(f).get("whitelist_enabled", False)
            except json.JSONDecodeError:
                # 如果文件内容有误，默认为 False（禁用）
                return False
    # 如果文件不存在，默认返回 False（禁用）
    return False

def save_whitelist_status(status):
    # 将状态保存到文件
    with open(WHITELIST_STATUS_FILE, "w") as f:
        json.dump({"whitelist_enabled": status}, f)

def is_whitelist_enabled():
    # 返回白名单启用状态
    return load_whitelist_status()


# 加载用户数据
def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "r") as f:
            return json.load(f)
    return {}


def save_user_data(user_data):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(user_data, f, indent=4)


# 用户注册
async def start(update, context):
    user_id = update.effective_user.id
    if not await is_user_in_group(user_id, context):
        await update.message.reply_text("官方群组：https://t.me/youdaolis")
        return

    if not is_allowed_user(user_id):
        await update.message.reply_text("抱歉，您没有权限使用此 Bot。")
        return

    chat_id = str(update.effective_chat.id)
    user_data = load_user_data()
    if chat_id not in user_data:
        user_data[chat_id] = {"rss_sources": []}
        save_user_data(user_data)
        await update.message.reply_text("欢迎！您已成功注册。请使用 /add_rss 添加 RSS 源。使用 /help 获取帮助。")
    else:
        await update.message.reply_text("您已注册！可以继续添加或管理 RSS 源和相关规则。使用 /help 获取帮助。")


# 添加 RSS 订阅源
async def add_rss(update, context):
    user_id = update.effective_user.id
    if not await is_user_in_group(user_id, context):
        await update.message.reply_text("官方群组：https://t.me/youdaolis")
        return

    if not is_allowed_user(user_id):
        await update.message.reply_text("抱歉，您没有权限使用此 Bot。")
        return

    chat_id = str(update.effective_chat.id)
    user_data = load_user_data()
    if chat_id not in user_data:
        await update.message.reply_text("请先使用 /start 注册。")
        return
    if len(context.args) < 1:
        await update.message.reply_text("请提供一个 RSS URL，例如：/add_rss https://rss.nodeseek.com")
        return

    rss_url = context.args[0].lower()
    for index, rss in enumerate(user_data[chat_id].get("rss_sources", [])):
        if rss["url"] == rss_url:
            existing_sources = "\n".join(
                f"{i + 1}、{r['url']}" for i, r in enumerate(user_data[chat_id]["rss_sources"])
            )
            await update.message.reply_text(
                f"RSS 源 '{rss_url}' 已经存在，当前已添加的源为：\n{existing_sources}"
            )
            return

    rss_data = {"url": rss_url, "keywords": [], "regex_patterns": [], "regex_keywords": []}
    user_data[chat_id]["rss_sources"].append(rss_data)
    save_user_data(user_data)

    existing_sources = "\n".join(
        f"{i + 1}、{r['url']}" for i, r in enumerate(user_data[chat_id]["rss_sources"])
    )
    await update.message.reply_text(
        f"RSS 订阅源 '{rss_url}' 已成功添加。\n\n当前已添加的 RSS 源：\n{existing_sources}"
    )


# 查看所有 RSS 源
async def list_rss(update, context):
    user_id = update.effective_user.id
    if not await is_user_in_group(user_id, context):
        await update.message.reply_text("官方群组：https://t.me/youdaolis ")
        return

    if not is_allowed_user(user_id):
        await update.message.reply_text("抱歉，您没有权限使用此 Bot。")
        return

    chat_id = str(update.effective_chat.id)
    user_data = load_user_data()

    if chat_id not in user_data or not user_data[chat_id]["rss_sources"]:
        await update.message.reply_text("您还没有添加任何 RSS 源。")
        return

    response = "已添加的 RSS 源：\n" + "\n".join(
        f"{i + 1}、{rss['url']}" for i, rss in enumerate(user_data[chat_id]["rss_sources"])
    )
    await update.message.reply_text(response)


# 查看特定 RSS 源的关键词
async def list_source(update, context):
    user_id = update.effective_user.id
    if not await is_user_in_group(user_id, context):
        await update.message.reply_text("官方群组：https://t.me/youdaolis")
        return

    if not is_allowed_user(user_id):
        await update.message.reply_text("抱歉，您没有权限使用此 Bot。")
        return

    chat_id = str(update.effective_chat.id)
    user_data = load_user_data()
    if len(context.args) < 1 or not context.args[0].isdigit():
        await update.message.reply_text("请提供一个源编号，例如：/list 1")
        return

    rss_index = int(context.args[0]) - 1
    if chat_id not in user_data or rss_index >= len(user_data[chat_id]["rss_sources"]):
        await update.message.reply_text("无效的源编号，请检查已添加的 RSS 源。")
        return

    rss = user_data[chat_id]["rss_sources"][rss_index]
    # 创建一个编号的关键词列表
    keywords = rss.get("keywords", [])
    if not keywords:
        formatted_keywords = "无"
    else:
        formatted_keywords = "\n".join(f"{i + 1}. {kw}" for i, kw in enumerate(keywords))

    # 显示正则表达式关键词
    regex_keywords = rss.get("regex_keywords", [])
    if not regex_keywords:
        formatted_regex = "无"
    else:
        formatted_regex = "\n".join(f"{i + 1}. {kw}" for i, kw in enumerate(regex_keywords))

    response = f"源 {rss_index + 1} ({rss['url']}) 的规则：\n\n普通关键词：\n{formatted_keywords}\n\n正则表达式：\n{formatted_regex}"
    await update.message.reply_text(response)


def create_regex_pattern(pattern_str):
    # 处理简单关键词
    if not any(c in pattern_str for c in "+-"):
        return f".*{re.escape(pattern_str)}.*"

    # 处理复杂模式
    parts = pattern_str.split("+")
    positive_patterns = []
    negative_patterns = []

    for part in parts:
        if not part:
            continue
        if "-" in part:
            neg_parts = part.split("-")
            if neg_parts[0]:  # 如果有正向匹配部分
                positive_patterns.append(f"(?=.*{re.escape(neg_parts[0])})")
            for neg_part in neg_parts[1:]:
                if neg_part:
                    negative_patterns.append(f"(?!.*{re.escape(neg_part)})")
        else:
            positive_patterns.append(f"(?=.*{re.escape(part)})")

    return "^" + "".join(negative_patterns + positive_patterns) + ".*$"

def validate_regex(pattern):
    try:
        re.compile(pattern)
        return True, None
    except re.error as e:
        return False, str(e)
    
# 添加关键词到特定 RSS 源
async def add(update, context):
    user_id = update.effective_user.id
    if not await is_user_in_group(user_id, context):
        await update.message.reply_text("官方群组：https://t.me/youdaolis")
        return

    if not is_allowed_user(user_id):
        await update.message.reply_text("抱歉，您没有权限使用此 Bot。")
        return

    chat_id = str(update.effective_chat.id)
    user_data = load_user_data()
    if len(context.args) < 2 or not context.args[0].isdigit():
        await update.message.reply_text(
            "请提供一个源编号和关键词，例如：\n"
            "/add 1 dmit 添加单个关键词\n"
            "/add 1 dmit vps hosting 添加多个关键词\n"
            "/add 1 +A+B-C +X-Y 添加多个复杂规则\n\n"
            "格式说明：\n"
            "+A+B 表示必须同时包含A和B\n"
            "+A-B 表示必须包含A但不能包含B\n"
            "多个关键词用空格分隔")
        return

    rss_index = int(context.args[0]) - 1
    if chat_id not in user_data or rss_index >= len(user_data[chat_id]["rss_sources"]):
        await update.message.reply_text("无效的源编号，请检查已添加的 RSS 源。")
        return

    # 确保必要的字段存在
    if "keywords" not in user_data[chat_id]["rss_sources"][rss_index]:
        user_data[chat_id]["rss_sources"][rss_index]["keywords"] = []
    if "regex_patterns" not in user_data[chat_id]["rss_sources"][rss_index]:
        user_data[chat_id]["rss_sources"][rss_index]["regex_patterns"] = []

    # 获取所有关键词（除了第一个参数，即源编号）
    patterns = context.args[1:]
    added_keywords = []

    for pattern in patterns:
        pattern = pattern.lower().strip()
        if pattern:  # 确保不是空字符串
            user_data[chat_id]["rss_sources"][rss_index]["keywords"].append(pattern)
            regex_pattern = create_regex_pattern(pattern)
            user_data[chat_id]["rss_sources"][rss_index]["regex_patterns"].append(regex_pattern)
            added_keywords.append(pattern)

    save_user_data(user_data)

    # 显示添加后的完整关键词列表
    keywords = user_data[chat_id]["rss_sources"][rss_index]["keywords"]
    keyword_list = "\n".join(f"{i + 1}. {kw}" for i, kw in enumerate(keywords))

    added_summary = "\n".join(f"• {kw}" for kw in added_keywords)
    await update.message.reply_text(
        f"已添加以下关键词到源 {rss_index + 1}：\n{added_summary}\n\n"
        f"当前的完整关键词列表：\n{keyword_list}"
    )


# 删除特定 RSS 源的关键词
async def rm(update, context):
    user_id = update.effective_user.id
    if not await is_user_in_group(user_id, context):
        await update.message.reply_text("官方群组：https://t.me/youdaolis")
        return

    if not is_allowed_user(user_id):
        await update.message.reply_text("抱歉，您没有权限使用此 Bot。")
        return

    chat_id = str(update.effective_chat.id)
    user_data = load_user_data()

    if len(context.args) < 2 or not context.args[0].isdigit():
        await update.message.reply_text(
            "请提供源编号和要删除的关键词序号，例如：\n"
            "/rm 1 2 删除单个关键词\n"
            "/rm 1 1 2 3 删除多个关键词")
        return

    rss_index = int(context.args[0]) - 1
    if chat_id not in user_data or rss_index >= len(user_data[chat_id]["rss_sources"]):
        await update.message.reply_text("无效的源编号，请检查已添加的 RSS 源。")
        return

    # 获取要删除的索引列表并排序（从大到小）
    try:
        indices = sorted([int(idx) - 1 for idx in context.args[1:]], reverse=True)
    except ValueError:
        await update.message.reply_text("请提供有效的关键词序号")
        return

    rss_source = user_data[chat_id]["rss_sources"][rss_index]

    # 首先同步 regex_patterns 和 keywords 的长度
    current_keywords = rss_source.get("keywords", [])
    current_patterns = rss_source.get("regex_patterns", [])

    # 确保 regex_patterns 和 keywords 长度一致
    while len(current_patterns) < len(current_keywords):
        kw = current_keywords[len(current_patterns)]
        if not any(c in kw for c in "+-"):
            current_patterns.append(f".*{kw}.*")
        else:
            current_patterns.append(create_regex_pattern(kw))

    current_patterns = current_patterns[:len(current_keywords)]

    if not current_keywords:
        await update.message.reply_text("当前没有可删除的关键词")
        return

    # 验证所有索引是否有效
    if any(idx < 0 or idx >= len(current_keywords) for idx in indices):
        current_list = "\n".join(f"{i + 1}. {kw}" for i, kw in enumerate(current_keywords))
        await update.message.reply_text(
            f"存在无效的关键词序号。当前的关键词列表：\n{current_list}")
        return

    # 记录要删除的关键词
    removed_keywords = []

    # 创建新的列表，排除要删除的索引
    new_keywords = []
    new_patterns = []

    for i in range(len(current_keywords)):
        if i in indices:
            removed_keywords.append(current_keywords[i])
        else:
            new_keywords.append(current_keywords[i])
            new_patterns.append(current_patterns[i])

    # 更新源数据
    rss_source["keywords"] = new_keywords
    rss_source["regex_patterns"] = new_patterns

    # 保存更新后的数据
    save_user_data(user_data)

    # 显示删除后的关键词列表
    if not new_keywords:
        updated_list = "当前没有关键词"
    else:
        updated_list = "\n".join(f"{i + 1}. {kw}" for i, kw in enumerate(new_keywords))

    removed_summary = "\n".join(f"• {kw}" for kw in removed_keywords)
    await update.message.reply_text(
        f"已删除以下关键词：\n{removed_summary}\n\n"
        f"当前的关键词列表：\n{updated_list}"
    )


# 删除指定 RSS 订阅源
async def rm_rss(update, context):
    user_id = update.effective_user.id
    if not await is_user_in_group(user_id, context):
        await update.message.reply_text("官方群组：https://t.me/youdaolis")
        return

    if not is_allowed_user(user_id):
        await update.message.reply_text("抱歉，您没有权限使用此 Bot。")
        return

    chat_id = str(update.effective_chat.id)
    user_data = load_user_data()

    if len(context.args) < 1 or not context.args[0].isdigit():
        await update.message.reply_text("请提供一个源编号，例如：/rm_rss 1")
        return

    rss_index = int(context.args[0]) - 1

    if chat_id not in user_data or rss_index >= len(user_data[chat_id]["rss_sources"]):
        await update.message.reply_text("无效的源编号，请检查已添加的 RSS 源。")
        return

    removed_rss = user_data[chat_id]["rss_sources"].pop(rss_index)
    save_user_data(user_data)

    await update.message.reply_text(f"RSS 源已删除：{removed_rss['url']}")

# 检查 RSS 并推送新内容
async def check_new_posts(context):
    print("Fetching RSS data...")
    cached_guids = load_cache()
    user_data = load_user_data()

    # 定义请求头
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml",
        "Referer": "https://www.google.com",
        "Accept-Language": "en-US,en;q=0.9",
    }

    for chat_id, data in user_data.items():
        rss_sources = data.get("rss_sources", [])
        for rss in rss_sources:
            rss_url = rss["url"]

            try:
                # 使用 requests 获取 RSS 数据
                print(f"Fetching RSS: {rss_url}")
                response = requests.get(rss_url, headers=headers, timeout=10)
                response.raise_for_status()  # 如果请求出错则抛出异常
                feed = feedparser.parse(response.content)  # 使用 feedparser 解析响应内容
            except requests.RequestException as e:
                print(f"Failed to fetch RSS: {rss_url}. Error: {e}")
                continue

            if not feed.entries:
                print(f"No entries found in RSS feed: {rss_url}")
                continue

            for entry in feed.entries:
                guid = entry.id if "id" in entry else entry.link

                if guid in cached_guids:
                    continue

                raw_title = entry.title.lower()
                title = escape_markdown(entry.title, version=2)
                link = escape_markdown(entry.link, version=2)

                # 标记是否已经匹配并发送
                message_sent = False

                # 使用正则表达式匹配（普通关键词生成的正则）
                regex_patterns = rss.get("regex_patterns", [])
                for pattern in regex_patterns:
                    try:
                        if re.search(pattern, raw_title, re.IGNORECASE):
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=f"*{title}*\n\n[查看详情]({link})",
                                parse_mode="MarkdownV2",
                            )
                            print(f"Message sent to {chat_id}: {raw_title}")

                            cached_guids.add(guid)
                            save_cache(cached_guids)
                            message_sent = True
                            break
                    except re.error as e:
                        print(f"Regex error: {e} for pattern: {pattern}")

                # 如果还没有匹配，检查正则表达式关键词
                if not message_sent:
                    regex_keywords = rss.get("regex_keywords", [])
                    for regex_pattern in regex_keywords:
                        try:
                            if re.search(regex_pattern, raw_title, re.IGNORECASE):
                                await context.bot.send_message(
                                    chat_id=chat_id,
                                    text=f"*{title}*\n\n[查看详情]({link})",
                                    parse_mode="MarkdownV2",
                                )
                                print(f"Message sent to {chat_id}: {raw_title} (matched regex: {regex_pattern})")
                                
                                cached_guids.add(guid)
                                save_cache(cached_guids)
                                break
                        except re.error as e:
                            print(f"Regex error: {e} for pattern: {regex_pattern}")

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return set(line.strip() for line in f)
    return set()

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        for guid in cache:
            f.write(f"{guid}\n")

# 添加正则表达式关键词
async def add_regex(update, context):
    user_id = update.effective_user.id
    if not await is_user_in_group(user_id, context):
        await update.message.reply_text("官方群组：https://t.me/youdaolis")
        return

    if not is_allowed_user(user_id):
        await update.message.reply_text("抱歉，您没有权限使用此 Bot。")
        return

    chat_id = str(update.effective_chat.id)
    user_data = load_user_data()
    if len(context.args) < 2 or not context.args[0].isdigit():
        await update.message.reply_text(
            "请提供源编号和正则表达式，例如：\n"
            "/add_regex 1 \\d+GB 匹配包含数字+GB的内容\n"
            "/add_regex 1 (VPS|服务器) 匹配包含VPS或服务器的内容\n"
            "/add_regex 1 ^优惠.* 匹配以'优惠'开头的内容\n\n"
            "注意：请确保正则表达式语法正确")
        return

    rss_index = int(context.args[0]) - 1
    if chat_id not in user_data or rss_index >= len(user_data[chat_id]["rss_sources"]):
        await update.message.reply_text("无效的源编号，请检查已添加的 RSS 源。")
        return

    # 确保字段存在
    if "regex_keywords" not in user_data[chat_id]["rss_sources"][rss_index]:
        user_data[chat_id]["rss_sources"][rss_index]["regex_keywords"] = []

    # 获取正则表达式
    regex_pattern = " ".join(context.args[1:])
    
    # 验证正则表达式
    is_valid, error_msg = validate_regex(regex_pattern)
    if not is_valid:
        await update.message.reply_text(f"正则表达式语法错误：{error_msg}\n请检查您的正则表达式语法。")
        return

    # 添加正则表达式
    user_data[chat_id]["rss_sources"][rss_index]["regex_keywords"].append(regex_pattern)
    save_user_data(user_data)

    # 显示结果
    regex_keywords = user_data[chat_id]["rss_sources"][rss_index]["regex_keywords"]
    regex_list = "\n".join(f"{i + 1}. {regex}" for i, regex in enumerate(regex_keywords))

    await update.message.reply_text(
        f"已添加正则表达式到源 {rss_index + 1}：\n• {regex_pattern}\n\n"
        f"当前的正则表达式列表：\n{regex_list}"
    )

# 删除正则表达式关键词
async def rm_regex(update, context):
    user_id = update.effective_user.id
    if not await is_user_in_group(user_id, context):
        await update.message.reply_text("官方群组：https://t.me/youdaolis")
        return

    if not is_allowed_user(user_id):
        await update.message.reply_text("抱歉，您没有权限使用此 Bot。")
        return

    chat_id = str(update.effective_chat.id)
    user_data = load_user_data()

    if len(context.args) < 2 or not context.args[0].isdigit():
        await update.message.reply_text(
            "请提供源编号和要删除的正则表达式序号，例如：\n"
            "/rm_regex 1 2 删除单个正则表达式\n"
            "/rm_regex 1 1 2 3 删除多个正则表达式")
        return

    rss_index = int(context.args[0]) - 1
    if chat_id not in user_data or rss_index >= len(user_data[chat_id]["rss_sources"]):
        await update.message.reply_text("无效的源编号，请检查已添加的 RSS 源。")
        return

    try:
        indices = sorted([int(idx) - 1 for idx in context.args[1:]], reverse=True)
    except ValueError:
        await update.message.reply_text("请提供有效的正则表达式序号")
        return

    rss_source = user_data[chat_id]["rss_sources"][rss_index]
    current_regex = rss_source.get("regex_keywords", [])

    if not current_regex:
        await update.message.reply_text("当前没有可删除的正则表达式")
        return

    if any(idx < 0 or idx >= len(current_regex) for idx in indices):
        current_list = "\n".join(f"{i + 1}. {regex}" for i, regex in enumerate(current_regex))
        await update.message.reply_text(
            f"存在无效的正则表达式序号。当前的正则表达式列表：\n{current_list}")
        return

    # 删除指定的正则表达式
    removed_regex = [current_regex[i] for i in sorted(indices)]
    for idx in indices:
        current_regex.pop(idx)

    save_user_data(user_data)

    # 显示结果
    if not current_regex:
        updated_list = "当前没有正则表达式"
    else:
        updated_list = "\n".join(f"{i + 1}. {regex}" for i, regex in enumerate(current_regex))

    removed_summary = "\n".join(f"• {regex}" for regex in removed_regex)
    await update.message.reply_text(
        f"已删除以下正则表达式：\n{removed_summary}\n\n"
        f"当前的正则表达式列表：\n{updated_list}"
    )

# 添加用户到白名单
async def add_user(update, context):
    user_id = update.effective_user.id
    if user_id != ROOT_ID:
        await update.message.reply_text("只有管理员可以操作白名单。")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("请提供要添加的用户 ID，例如：/add_user 123456789")
        return

    new_user_id = int(context.args[0])
    allowed_users = load_allowed_users()

    if new_user_id in allowed_users:
        await update.message.reply_text(f"用户 ID {new_user_id} 已在白名单中。")
        return

    allowed_users.add(new_user_id)
    save_allowed_users(allowed_users)
    await update.message.reply_text(f"用户 ID {new_user_id} 已成功添加到白名单。")

# 白名单开关
async def toggle_whitelist(update, context):
    user_id = update.effective_user.id
    if user_id != ROOT_ID:
        await update.message.reply_text("只有管理员可以操作白名单模式。")
        return

    if len(context.args) < 1 or context.args[0].lower() not in ["on", "off"]:
        await update.message.reply_text("请提供有效参数：/whitelist on 或 /whitelist off")
        return

    status = context.args[0].lower() == "on"
    save_whitelist_status(status)
    status_text = "开启" if status else "关闭"
    await update.message.reply_text(f"白名单模式已{status_text}。")

# 处理 /help 命令
async def help_command(update, context):
    user_id = update.effective_user.id
    if not await is_user_in_group(user_id, context):
        await update.message.reply_text("官方群组：https://t.me/youdaolis")
        return

    if not is_allowed_user(user_id):
        await update.message.reply_text("抱歉，您没有权限使用此 Bot。")
        return

    # 修复缩进：
    help_text = (
        "欢迎使用我们的 Telegram Bot！以下是可用命令的列表：\n"
        "/start - 注册与启动服务\n"
        "/help - 查看帮助信息\n"
        "/add_rss - 添加一个新的 RSS 源\n"
        "/list_rss - 列出所有已添加的 RSS 源\n"
        "/list - 查看特定 RSS 源的详细信息\n"
        "/add - 添加关键词到指定的 RSS 源\n"
        "/add_regex - 添加正则表达式到指定的 RSS 源\n"
        "  示例：\n"
        "  /add 1 C - 添加包含'C'的关键词\n"
        "  /add 1 +A+B - 添加同时包含'A'和'B'的关键词\n"
        "  /add 1 +A-B - 添加包含'A'但不包含'B'的关键词\n"
        "  /add_regex 1 \\d+GB - 添加匹配数字+GB的正则表达式\n"
        "/rm - 从指定的 RSS 源移除关键词\n"
        "/rm_regex - 从指定的 RSS 源移除正则表达式\n"
        "/rm_rss - 删除指定的 RSS 源\n"
        " \n"
        "管理员命令\n"
        "/add_user <用户ID> - 将用户添加到白名单(仅管理员可用)\n"
        "/group_verify <on/off> - 开启或关闭进群验证 (仅管理员可用)\n"
        "/whitelist <on/off> - 开启或关闭白名单模式(仅管理员可用)\n"
        "请依照指令格式进行操作，享受我们的服务！"
    )

    await update.message.reply_text(help_text)

# 主函数
def main():
    if not TELEGRAM_BOT_TOKEN:
        print("错误：未设置 TELEGRAM_BOT_TOKEN 环境变量")
        return
    
    if not ROOT_ID:
        print("错误：未设置 ROOT_ID 环境变量")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).connect_timeout(20).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add_rss", add_rss))
    application.add_handler(CommandHandler("list_rss", list_rss))
    application.add_handler(CommandHandler("list", list_source))
    application.add_handler(CommandHandler("add", add))
    application.add_handler(CommandHandler("rm", rm))
    application.add_handler(CommandHandler("rm_rss", rm_rss))
    application.add_handler(CommandHandler("add_user", add_user))
    application.add_handler(CommandHandler("whitelist", toggle_whitelist))
    application.add_handler(CommandHandler("group_verify", toggle_group_verify))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add_regex", add_regex))
    application.add_handler(CommandHandler("rm_regex", rm_regex))

    # 使用环境变量中的更新间隔
    application.job_queue.run_repeating(check_new_posts, interval=UPDATE_INTERVAL, first=0)

    print(f"Bot 启动成功，更新间隔：{UPDATE_INTERVAL} 秒")
    application.run_polling()
if __name__ == "__main__":
    main()
