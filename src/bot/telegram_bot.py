"""Telegram 机器人实现."""

import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any

from loguru import logger
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src.config import get_settings
from src.models import Briefing, Paper, User, UserBriefing, UserState, get_db_session
from src.services.briefing_service import BriefingService
from src.services.paper_service import PaperService
from src.services.user_service import UserService

# 对话状态
SELECTING_FIELDS = 1
SETTING_LIMIT = 2
SETTING_HISTORY_DAYS = 3


class TelegramBot:
    """Telegram 机器人类."""

    def __init__(self):
        """初始化机器人."""
        self.settings = get_settings()
        self.application: Optional[Application] = None
        self.briefing_service = BriefingService()
        self.paper_service = PaperService()
        self.user_service = UserService()
        
        # 存储用户临时选择状态
        self._user_selections: Dict[str, List[int]] = {}

    async def initialize(self):
        """初始化机器人应用."""
        builder = Application.builder().token(self.settings.telegram_bot_token)

        # 配置代理（如果设置了）
        if self.settings.telegram_proxy_url:
            from telegram.request import HTTPXRequest
            request = HTTPXRequest(proxy_url=self.settings.telegram_proxy_url)
            builder = builder.request(request)
            logger.info(f"Using proxy for Telegram Bot: {self.settings.telegram_proxy_url}")

        self.application = builder.build()

        # 注册命令处理器
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("settings", self.cmd_settings))
        self.application.add_handler(CommandHandler("fields", self.cmd_fields))
        self.application.add_handler(CommandHandler("limit", self.cmd_limit))
        self.application.add_handler(CommandHandler("history", self.cmd_history))
        self.application.add_handler(CommandHandler("next", self.cmd_next))
        self.application.add_handler(CommandHandler("list", self.cmd_list))
        self.application.add_handler(CommandHandler("today", self.cmd_today))
        self.application.add_handler(CommandHandler("search", self.cmd_search))
        self.application.add_handler(CommandHandler("stats", self.cmd_stats))
        self.application.add_handler(CommandHandler("read", self.cmd_read))
        self.application.add_handler(CommandHandler("interested", self.cmd_interested))

        # 注册回调处理器
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))

        # 初始化研究领域
        self.user_service.init_research_fields()
        
        logger.info("Telegram bot initialized")

    async def start(self):
        """启动机器人."""
        if not self.application:
            await self.initialize()

        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

        logger.info("Telegram bot started")

    async def stop(self):
        """停止机器人."""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Telegram bot stopped")

    def _get_user_id(self, update: Update) -> str:
        """获取用户 ID."""
        return str(update.effective_user.id)

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /start 命令 - 用户注册流程."""
        user_id = self._get_user_id(update)
        user = update.effective_user
        
        # 获取或创建用户
        db_user = self.user_service.get_or_create_user(
            telegram_id=user_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )
        
        if not db_user.onboarding_completed:
            # 新用户，开始领域选择流程
            await self._start_field_selection(update, context)
        else:
            # 老用户，显示欢迎回来消息
            welcome_message = f"""
👋 欢迎回来，{user.first_name or '用户'}！

我是 **PaperNews**，您的学术论文追踪助手。

📚 **您的设置**:
• 订阅领域: {len(db_user.research_fields)} 个
• 每日推送: {db_user.daily_paper_limit} 篇
• 历史爬取: {db_user.crawl_history_days} 天

**快捷命令**:
/next - 获取下一条待读简报
/history - 查看历史简报
/settings - 修改设置
/help - 查看所有命令

祝您阅读愉快！🎉
            """
            await update.message.reply_text(welcome_message, parse_mode="Markdown")

    async def _start_field_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """开始领域选择流程."""
        user_id = self._get_user_id(update)
        self._user_selections[user_id] = []
        
        # 获取所有研究领域
        fields = self.user_service.get_research_fields()
        
        message = """
🎯 **首次使用设置**

请选择您感兴趣的研究领域（可多选）：

点击按钮选择/取消选择，完成后点击「✅ 完成选择」
        """
        
        keyboard = self._create_field_selection_keyboard(fields, [])
        
        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    def _create_field_selection_keyboard(
        self, 
        fields: List[Any], 
        selected_ids: List[int]
    ) -> InlineKeyboardMarkup:
        """创研究领域选择键盘."""
        keyboard = []
        
        for field in fields:
            prefix = "✅ " if field.id in selected_ids else "⬜ "
            keyboard.append([
                InlineKeyboardButton(
                    f"{prefix}{field.name_cn or field.name}",
                    callback_data=f"field_{field.id}"
                )
            ])
        
        # 添加完成按钮
        keyboard.append([
            InlineKeyboardButton("✅ 完成选择", callback_data="fields_done"),
            InlineKeyboardButton("❌ 取消", callback_data="fields_cancel")
        ])
        
        return InlineKeyboardMarkup(keyboard)

    async def cmd_fields(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /fields 命令 - 修改研究领域."""
        user_id = self._get_user_id(update)
        db_user = self.user_service.get_user_by_telegram_id(user_id)
        
        if not db_user:
            await update.message.reply_text("❌ 请先使用 /start 注册")
            return
        
        # 获取当前选择的领域
        current_field_ids = [f.id for f in db_user.research_fields]
        self._user_selections[user_id] = current_field_ids.copy()
        
        fields = self.user_service.get_research_fields()
        
        message = f"""
🎯 **修改研究领域**

当前已选择: {len(current_field_ids)} 个领域

点击按钮选择/取消选择，完成后点击「✅ 完成选择」
        """
        
        keyboard = self._create_field_selection_keyboard(fields, current_field_ids)
        
        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    async def cmd_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /settings 命令 - 查看/修改设置."""
        user_id = self._get_user_id(update)
        db_user = self.user_service.get_user_by_telegram_id(user_id)
        
        if not db_user:
            await update.message.reply_text("❌ 请先使用 /start 注册")
            return
        
        field_names = [f.name_cn or f.name for f in db_user.research_fields]
        
        message = f"""
⚙️ **您的设置**

📋 **订阅领域**: 
{chr(10).join(['• ' + name for name in field_names]) if field_names else '未设置'}

📊 **每日推送数量**: {db_user.daily_paper_limit} 篇
📅 **历史文章爬取**: {db_user.crawl_history_days} 天

**修改设置**:
/fields - 修改研究领域
/limit <数量> - 修改每日推送数量（1-50）
/history <天数> - 修改历史爬取天数（1-30）
        """
        
        await update.message.reply_text(message, parse_mode="Markdown")

    async def cmd_limit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /limit 命令 - 修改每日推送数量."""
        user_id = self._get_user_id(update)
        
        if not context.args:
            await update.message.reply_text(
                "📊 请提供每日推送数量（1-50）。\n"
                "示例: `/limit 10`"
            )
            return
        
        try:
            limit = int(context.args[0])
            if limit < 1 or limit > 50:
                raise ValueError("Limit out of range")
        except ValueError:
            await update.message.reply_text("❌ 无效的数量。请输入 1-50 之间的数字。")
            return
        
        success = self.user_service.update_user_settings(
            telegram_id=user_id,
            daily_paper_limit=limit
        )
        
        if success:
            await update.message.reply_text(f"✅ 每日推送数量已设置为 {limit} 篇")
        else:
            await update.message.reply_text("❌ 设置失败，请稍后重试")

    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /history 命令 - 修改历史爬取天数或查看历史简报."""
        user_id = self._get_user_id(update)
        
        # 如果有参数，修改历史爬取天数
        if context.args:
            try:
                days = int(context.args[0])
                if days < 1 or days > 30:
                    raise ValueError("Days out of range")
            except ValueError:
                await update.message.reply_text("❌ 无效的天数。请输入 1-30 之间的数字。")
                return
            
            success = self.user_service.update_user_settings(
                telegram_id=user_id,
                crawl_history_days=days
            )
            
            if success:
                await update.message.reply_text(f"✅ 历史文章爬取天数已设置为 {days} 天")
            else:
                await update.message.reply_text("❌ 设置失败，请稍后重试")
            return
        
        # 否则显示历史简报
        db_user = self.user_service.get_user_by_telegram_id(user_id)
        if not db_user:
            await update.message.reply_text("❌ 请先使用 /start 注册")
            return
        
        # 获取已发送的简报
        sent_briefings = self.briefing_service.get_user_sent_briefings(db_user, limit=10)
        
        if not sent_briefings:
            await update.message.reply_text("📭 暂无历史简报。使用 /next 获取新简报！")
            return
        
        await update.message.reply_text(f"📚 您的历史简报（最近 {len(sent_briefings)} 条）：")
        
        for ub in sent_briefings:
            message = self.briefing_service.format_briefing_for_telegram(ub)
            keyboard = self._create_user_briefing_keyboard(ub)
            
            try:
                await update.message.reply_text(
                    message,
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
            except Exception as e:
                logger.error(f"Error sending briefing: {e}")

    async def cmd_next(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /next 命令 - 获取下一条待读简报."""
        user_id = self._get_user_id(update)
        db_user = self.user_service.get_user_by_telegram_id(user_id)
        
        if not db_user:
            await update.message.reply_text("❌ 请先使用 /start 注册")
            return
        
        if not db_user.onboarding_completed:
            await update.message.reply_text("⚠️ 请先完成领域选择。使用 /fields 选择研究领域")
            return
        
        # 确保用户有简报分配
        pending = self.briefing_service.get_user_pending_briefings(db_user, limit=1)
        
        if not pending:
            # 尝试为用户创建新的简报关联
            self.briefing_service.create_user_briefings(db_user)
            pending = self.briefing_service.get_user_pending_briefings(db_user, limit=1)
        
        if not pending:
            await update.message.reply_text(
                "📭 暂无新的简报。\n"
                "系统会定期爬取新论文，请稍后再试！"
            )
            return
        
        # 发送简报
        user_briefing = pending[0]
        message = self.briefing_service.format_briefing_for_telegram(user_briefing)
        keyboard = self._create_user_briefing_keyboard(user_briefing)
        
        try:
            await update.message.reply_text(
                message,
                parse_mode="Markdown",
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
            
            # 标记为已发送
            self.briefing_service.mark_user_briefing_sent(user_briefing.id)
            
        except Exception as e:
            logger.error(f"Error sending briefing: {e}")
            await update.message.reply_text("❌ 发送简报失败，请稍后重试")

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /help 命令."""
        help_message = """
📖 **PaperNews 帮助**

**基本命令**:
/start - 开始使用机器人（注册/欢迎）
/help - 显示此帮助信息

**获取简报**:
/next - 获取下一条待读简报
/today - 查看今日待发送简报
/history - 查看历史简报

**搜索论文**:
/search <关键词> - 搜索论文标题和摘要
示例: `/search machine learning`

**设置**:
/settings - 查看当前设置
/fields - 修改研究领域
/limit <数量> - 修改每日推送数量（1-50）
/history <天数> - 修改历史爬取天数（1-30）

**管理阅读状态**:
/read <ID> - 标记简报为已读
/interested <ID> - 标记感兴趣的简报

**统计信息**:
/stats - 查看论文和简报统计

**提示**:
- 首次使用需要选择感兴趣的研究领域
- 简报按时间倒序推送（最新的优先）
- 可以标记感兴趣的论文以便后续查看
        """
        await update.message.reply_text(help_message, parse_mode="Markdown")

    async def cmd_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /list 命令 - 查看所有简报."""
        user_id = self._get_user_id(update)
        db_user = self.user_service.get_user_by_telegram_id(user_id)
        
        if not db_user:
            await update.message.reply_text("❌ 请先使用 /start 注册")
            return
        
        # 获取用户的简报（包括已发送和待发送）
        all_briefings = self.briefing_service.get_user_pending_briefings(db_user, limit=10)
        
        if not all_briefings:
            await update.message.reply_text("📭 暂无简报。使用 /next 获取新简报！")
            return
        
        await update.message.reply_text(f"📚 找到 {len(all_briefings)} 条简报：")
        
        for ub in all_briefings[:5]:  # 最多显示5条
            message = self.briefing_service.format_briefing_for_telegram(ub)
            keyboard = self._create_user_briefing_keyboard(ub)
            
            try:
                await update.message.reply_text(
                    message,
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
            except Exception as e:
                logger.error(f"Error sending briefing: {e}")

    async def cmd_today(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /today 命令."""
        user_id = self._get_user_id(update)
        db_user = self.user_service.get_user_by_telegram_id(user_id)
        
        if not db_user:
            await update.message.reply_text("❌ 请先使用 /start 注册")
            return
        
        pending = self.briefing_service.get_user_pending_briefings(db_user, limit=10)
        
        if not pending:
            await update.message.reply_text("📭 今日暂无待发送的简报。所有简报都已推送！")
            return
        
        await update.message.reply_text(f"📚 您有 {len(pending)} 条待读简报：")
        
        for ub in pending[:5]:  # 最多显示5条
            message = self.briefing_service.format_briefing_for_telegram(ub)
            keyboard = self._create_user_briefing_keyboard(ub)
            
            try:
                await update.message.reply_text(
                    message,
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
                
                # 标记为已发送
                self.briefing_service.mark_user_briefing_sent(ub.id)
                
            except Exception as e:
                logger.error(f"Error sending briefing: {e}")

    async def cmd_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /search 命令."""
        if not context.args:
            await update.message.reply_text(
                "🔍 请提供搜索关键词。\n示例: `/search machine learning`"
            )
            return

        query = " ".join(context.args)
        papers = self.paper_service.search_papers(query, limit=10)

        if not papers:
            await update.message.reply_text(f"🔍 未找到与 '{query}' 相关的论文。")
            return

        message = f"🔍 搜索 '{query}' 找到 {len(papers)} 篇论文：\n\n"

        for i, paper in enumerate(papers, 1):
            message += f"{i}. **{paper.title}**\n"
            message += f"   👥 {paper.authors[:50]}...\n"
            message += f"   🔗 [查看]({paper.source_url})\n\n"

        await update.message.reply_text(message, parse_mode="Markdown", disable_web_page_preview=True)

    async def cmd_read(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /read 命令."""
        if not context.args:
            await update.message.reply_text("📖 请提供用户简报 ID。\n示例: `/read 123`")
            return

        try:
            user_briefing_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ 无效的 ID。请提供数字。")
            return

        success = self.briefing_service.mark_user_briefing_read(user_briefing_id)
        
        if success:
            await update.message.reply_text(f"✅ 已将简报 #{user_briefing_id} 标记为已读。")
        else:
            await update.message.reply_text("❌ 标记失败，请检查 ID 是否正确。")

    async def cmd_interested(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /interested 命令."""
        if not context.args:
            await update.message.reply_text("⭐ 请提供用户简报 ID。\n示例: `/interested 123`")
            return

        try:
            user_briefing_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ 无效的 ID。请提供数字。")
            return

        success = self.briefing_service.mark_user_briefing_interested(user_briefing_id)
        
        if success:
            await update.message.reply_text(f"⭐ 已标记简报 #{user_briefing_id} 为感兴趣。")
        else:
            await update.message.reply_text("❌ 标记失败，请检查 ID 是否正确。")

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /stats 命令."""
        user_id = self._get_user_id(update)
        db_user = self.user_service.get_user_by_telegram_id(user_id)
        
        if not db_user:
            await update.message.reply_text("❌ 请先使用 /start 注册")
            return

        # 获取用户统计
        pending_count = len(self.briefing_service.get_user_pending_briefings(db_user))
        sent_briefings = self.briefing_service.get_user_sent_briefings(db_user, limit=1000)
        read_count = sum(1 for ub in sent_briefings if ub.is_read)
        interested_count = sum(1 for ub in sent_briefings if ub.is_interested)

        stats_message = f"""
📊 **您的统计信息**

**阅读数据**:
📭 待读简报: {pending_count}
✅ 已读简报: {read_count}
⭐ 感兴趣: {interested_count}

**设置信息**:
📋 订阅领域: {len(db_user.research_fields)} 个
📊 每日推送: {db_user.daily_paper_limit} 篇
📅 历史爬取: {db_user.crawl_history_days} 天

**研究领域**:
{chr(10).join(['• ' + (f.name_cn or f.name) for f in db_user.research_fields]) if db_user.research_fields else '未设置'}
        """

        await update.message.reply_text(stats_message, parse_mode="Markdown")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理回调查询."""
        query = update.callback_query
        await query.answer()

        data = query.data
        user_id = self._get_user_id(update)

        if data.startswith("field_"):
            # 处理领域选择
            await self._handle_field_selection(query, data, user_id)
        elif data == "fields_done":
            # 完成领域选择
            await self._handle_fields_done(query, user_id)
        elif data == "fields_cancel":
            # 取消领域选择
            await self._handle_fields_cancel(query, user_id)
        elif data.startswith("read_"):
            user_briefing_id = int(data.split("_")[1])
            await self._mark_briefing_read(user_id, user_briefing_id, query)
        elif data.startswith("interested_"):
            user_briefing_id = int(data.split("_")[1])
            await self._mark_briefing_interested(user_id, user_briefing_id, query)

    async def _handle_field_selection(self, query, data: str, user_id: str):
        """处理领域选择."""
        field_id = int(data.split("_")[1])
        
        # 获取当前选择
        selected = self._user_selections.get(user_id, [])
        
        # 切换选择状态
        if field_id in selected:
            selected.remove(field_id)
        else:
            selected.append(field_id)
        
        self._user_selections[user_id] = selected
        
        # 更新键盘
        fields = self.user_service.get_research_fields()
        keyboard = self._create_field_selection_keyboard(fields, selected)
        
        try:
            await query.edit_message_reply_markup(reply_markup=keyboard)
        except Exception as e:
            logger.debug(f"Keyboard update failed (likely unchanged): {e}")

    async def _handle_fields_done(self, query, user_id: str):
        """完成领域选择."""
        selected = self._user_selections.get(user_id, [])
        
        if not selected:
            await query.answer("请至少选择一个领域！", show_alert=True)
            return
        
        # 保存用户选择
        success = self.user_service.set_user_research_fields(user_id, selected)
        
        if success:
            # 清理临时状态
            del self._user_selections[user_id]
            
            fields = self.user_service.get_research_fields()
            selected_names = [
                f.name_cn or f.name 
                for f in fields 
                if f.id in selected
            ]
            
            await query.edit_message_text(
                f"✅ **设置完成！**\n\n"
                f"您选择了 {len(selected)} 个研究领域:\n"
                f"{chr(10).join(['• ' + name for name in selected_names])}\n\n"
                f"使用 /next 获取您的第一条简报！",
                parse_mode="Markdown"
            )
        else:
            await query.answer("设置失败，请重试", show_alert=True)

    async def _handle_fields_cancel(self, query, user_id: str):
        """取消领域选择."""
        if user_id in self._user_selections:
            del self._user_selections[user_id]
        
        await query.edit_message_text("❌ 已取消设置。使用 /fields 重新选择")

    async def _mark_briefing_read(self, user_id: str, user_briefing_id: int, query):
        """标记简报为已读."""
        success = self.briefing_service.mark_user_briefing_read(user_briefing_id)
        
        if success:
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(f"✅ 已标记简报 #{user_briefing_id} 为已读。")
        else:
            await query.answer("标记失败", show_alert=True)

    async def _mark_briefing_interested(self, user_id: str, user_briefing_id: int, query):
        """标记简报为感兴趣."""
        success = self.briefing_service.mark_user_briefing_interested(user_briefing_id)
        
        if success:
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(f"⭐ 已标记简报 #{user_briefing_id} 为感兴趣。")
        else:
            await query.answer("标记失败", show_alert=True)

    def _create_user_briefing_keyboard(self, user_briefing: UserBriefing) -> InlineKeyboardMarkup:
        """创建用户简报的内联键盘."""
        keyboard = [
            [
                InlineKeyboardButton("✅ 标记已读", callback_data=f"read_{user_briefing.id}"),
                InlineKeyboardButton("⭐ 感兴趣", callback_data=f"interested_{user_briefing.id}"),
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def send_daily_briefings(self):
        """发送每日简报给所有活跃用户."""
        if not self.application:
            logger.error("Bot not initialized")
            return

        # 获取所有活跃用户
        users = self.user_service.get_all_active_users()
        logger.info(f"Sending daily briefings to {len(users)} users")

        for user in users:
            try:
                # 确保用户有简报分配
                pending = self.briefing_service.get_user_pending_briefings(user)
                
                if not pending:
                    # 尝试为用户创建新的简报关联
                    self.briefing_service.create_user_briefings(user)
                    pending = self.briefing_service.get_user_pending_briefings(user)
                
                if not pending:
                    logger.info(f"No pending briefings for user {user.telegram_id}")
                    continue
                
                # 发送简报（限制数量）
                limit = min(user.daily_paper_limit, len(pending))
                to_send = pending[:limit]
                
                logger.info(f"Sending {len(to_send)} briefings to user {user.telegram_id}")
                
                for user_briefing in to_send:
                    try:
                        message = self.briefing_service.format_briefing_for_telegram(user_briefing)
                        keyboard = self._create_user_briefing_keyboard(user_briefing)

                        await self.application.bot.send_message(
                            chat_id=user.telegram_id,
                            text=message,
                            parse_mode="Markdown",
                            reply_markup=keyboard,
                            disable_web_page_preview=True,
                        )

                        # 标记为已发送
                        self.briefing_service.mark_user_briefing_sent(user_briefing.id)
                        logger.info(f"Sent briefing #{user_briefing.id} to user {user.telegram_id}")

                        # 避免发送过快
                        await asyncio.sleep(1)

                    except Exception as e:
                        logger.error(f"Error sending briefing to user {user.telegram_id}: {e}")

            except Exception as e:
                logger.error(f"Error processing user {user.telegram_id}: {e}")
