"""
Обработчики платежей через Telegram Payments
"""
from aiogram import Router, F, Bot
from aiogram.types import PreCheckoutQuery, Message, SuccessfulPayment
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from services.telegram_payments import payment_service
import logging

router = Router()
logger = logging.getLogger(__name__)


@router.pre_checkout_query()
async def process_pre_checkout(
    pre_checkout_query: PreCheckoutQuery,
    bot: Bot,
    session: AsyncSession
):
    """Обработка запроса перед оплатой"""
    await payment_service.process_pre_checkout(
        pre_checkout_query=pre_checkout_query,
        bot=bot,
        session=session
    )


@router.message(F.successful_payment)
async def process_successful_payment(
    message: Message,
    payment: SuccessfulPayment,
    session: AsyncSession,
    state: FSMContext
):
    """Обработка успешного платежа"""
    await payment_service.process_successful_payment(
        message=message,
        payment=payment,
        session=session
    )

