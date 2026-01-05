"""
Общие клавиатуры для бота
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database.models import SubscriptionStatus
from datetime import datetime


def get_main_menu_keyboard(is_paid: bool = False) -> ReplyKeyboardMarkup:
    """Главное меню"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💬 Начать диалог")],
            [KeyboardButton(text="📚 История диалогов"), KeyboardButton(text="⚙️ Настройки")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Напишите сообщение..."
    )
    
    if not is_paid:
        keyboard.keyboard.append([KeyboardButton(text="💎 Подписка")])
    
    return keyboard


def get_subscription_keyboard(is_active: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для подписки"""
    if is_active:
        buttons = [
            [InlineKeyboardButton(text="✅ Подписка активна", callback_data="subscription_info")]
        ]
    else:
        buttons = [
            [InlineKeyboardButton(text="💎 Купить подписку", callback_data="buy_subscription")],
            [InlineKeyboardButton(text="ℹ️ Подробнее", callback_data="subscription_info")]
        ]
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_conversations_keyboard(conversations: list, page: int = 0, per_page: int = 10) -> InlineKeyboardMarkup:
    """Клавиатура со списком диалогов"""
    buttons = []
    
    start = page * per_page
    end = start + per_page
    page_conversations = conversations[start:end]
    
    for conv in page_conversations:
        title = conv.get("title", f"Диалог #{conv.get('id', '?')}")
        if len(title) > 50:
            title = title[:47] + "..."
        buttons.append([
            InlineKeyboardButton(
                text=title,
                callback_data=f"conversation_{conv.get('id')}"
            )
        ])
    
    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"conversations_page_{page-1}"))
    if end < len(conversations):
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"conversations_page_{page+1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура настроек"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
        ]
    )

