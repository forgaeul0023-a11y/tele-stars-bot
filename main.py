import os
import json
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_BASE = os.getenv("WEBHOOK_BASE")
WEBHOOK_PATH = "/webhook"
PORT = int(os.getenv("PORT", 10000))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# 🔧 상품 목록을 외부 JSON에서 로드
def load_products():
    with open("products.json", "r", encoding="utf-8") as f:
        return json.load(f)

PRODUCTS = load_products()

# 공통 결제 송장 생성 함수
async def send_product_invoice(chat_id: int, item_id: str, product: dict):
    pay_builder = InlineKeyboardBuilder()
    pay_builder.button(text=f"⭐ Pay {product['price']} Stars", pay=True)
    await bot.send_invoice(
        chat_id=chat_id, title=product["title"], description=product["desc"],
        payload=item_id, provider_token="", currency="XTR",
        prices=[types.LabeledPrice(label="Amount", amount=product["price"])],
        reply_markup=pay_builder.as_markup()
    )

# 1. /start 명령어 (딥링크 처리)
@dp.message(Command("start"))
async def start_handler(message: types.Message, command: CommandObject):
    if command.args and command.args in PRODUCTS:
        item_id = command.args
        product = PRODUCTS[item_id]
        asyncio.create_task(send_product_invoice(message.chat.id, item_id, product))
        return
    return

# 관리자용 상품 목록
@dp.message(Command("menu", "buy"))
async def menu_handler(message: types.Message):
    builder = InlineKeyboardBuilder()
    for item_id, info in PRODUCTS.items():
        builder.button(text=f"{info['title']} ({info['price']}⭐)", callback_data=f"select_{item_id}")
    builder.adjust(1)
    await message.answer("🛒 **[Admin Menu] Product List:**", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("select_"))
async def process_product_selection(callback_query: types.CallbackQuery):
    item_id = callback_query.data.replace("select_", "")
    product = PRODUCTS.get(item_id)
    if not product:
        await callback_query.answer("Product not found.")
        return
    await send_product_invoice(callback_query.message.chat.id, item_id, product)
    await callback_query.answer()

@dp.pre_checkout_query()
async def checkout_handler(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query_id=pre_checkout_query.id, ok=True)

# 결제 성공 → 압축파일 직접 전송
@dp.message(F.successful_payment)
async def success_handler(message: types.Message):
    payment_info = message.successful_payment
    bought_item_id = payment_info.invoice_payload
    product = PRODUCTS.get(bought_item_id)

    if not product:
        await message.answer("Payment successful, but product not found.")
        return

    await message.answer(
        f"🎉 **Payment for [{product['title']}] completed!**\n"
        f"💰 {payment_info.total_amount} Stars ⭐\n\n"
        f"📦 Sending your file..."
    )

    if product.get("file_id"):
        try:
            caption = f"📦 {product['title']}\n"
            if product.get("password"):
                caption += f"🔑 PW: {product['password']}\n"
            caption += "⚠️ Keep this file safe."
            await bot.send_document(
                chat_id=message.chat.id,
                document=product["file_id"],
                caption=caption
            )
        except Exception:
            await message.answer("⚠️ File send failed. Please contact the admin.")
    else:
        await message.answer("⚠️ Product file is not set. Please contact the admin.")

# 🔧 file_id 추출용 핸들러 (압축파일 + 영상 둘 다)
@dp.message(F.document)
async def get_document_id(message: types.Message):
    d = message.document
    await message.answer(
        f"📦 {d.file_name}\n"
        f"size: {d.file_size}\n"
        f"`{d.file_id}`",
        parse_mode="Markdown"
    )

@dp.message(F.video)
async def get_video_id(message: types.Message):
    v = message.video
    await message.answer(
        f"🎬 {v.file_name}\n"
        f"size: {v.file_size}\n"
        f"`{v.file_id}`",
        parse_mode="Markdown"
    )

async def on_startup(bot: Bot):
    await bot.set_webhook(f"{WEBHOOK_BASE}{WEBHOOK_PATH}")

def main():
    dp.startup.register(on_startup)
    app = web.Application()
    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    web.run_app(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
