import os
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

# [★Product Database] 10 Products
PRODUCTS = {
    "item_001": {"title": "Y-01 3:15", "desc": "🎵 Thank you for choosing Y-01!", "price": 1, "link": "https://gofile.io", "success_msg": "Enjoy the premium sound!"},
    "item_002": {"title": "R-01 2:46", "desc": "🔥 Ready to unlock R-01?", "price": 200, "link": "https://example.com", "success_msg": "Welcome to the R-01 premium club!"},
    "item_003": {"title": "G-01 2:56", "desc": "Would you like to purchase G-01?", "price": 200, "link": "https://example.com", "success_msg": "Here is your link for G-01:"},
    "item_004": {"title": "L-01 4:10", "desc": "Would you like to purchase L-01?", "price": 200, "link": "https://example.com", "success_msg": "Here is your link for L-01:"},
    "item_005": {"title": "Le-01 4:34", "desc": "Would you like to purchase Le-01?", "price": 200, "link": "https://example.com", "success_msg": "Here is your link for Le-01:"},
    "item_006": {"title": "W-01 7:04", "desc": "Would you like to purchase W-01?", "price": 250, "link": "https://example.com", "success_msg": "Here is your link for W-01:"},
    "item_007": {"title": "Y-02 0:55", "desc": "Would you like to purchase Y-02?", "price": 100, "link": "https://example.com", "success_msg": "Here is your link for Y-02:"},
    "item_008": {"title": "G-02 0:59", "desc": "Would you like to purchase G-02?", "price": 100, "link": "https://example.com", "success_msg": "Here is your link for G-02:"},
    "item_009": {"title": "G-03 0:59", "desc": "Would you like to purchase G-03?", "price": 100, "link": "https://example.com", "success_msg": "Here is your link for G-03:"},
    "item_010": {"title": "R-02 1:15", "desc": "Would you like to purchase R-02?", "price": 100, "link": "https://example.com", "success_msg": "Here is your link for R-02:"}
}

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

# 1. /start 명령어 처리 (★딥링크 상품 코드 감지 기능 주입 완료)
@dp.message(Command("start"))
async def start_handler(message: types.Message, command: CommandObject):
    # 주소 뒤에 상품 코드(예: item_001)가 붙어 들어온 경우
    if command.args and command.args in PRODUCTS:
        item_id = command.args
        product = PRODUCTS[item_id]
        await send_product_invoice(message.chat.id, item_id, product) # 즉시 개별 결제창 팝업
        return

    # 그냥 들어온 경우만 메뉴판 출력
    builder = InlineKeyboardBuilder()
    for item_id, info in PRODUCTS.items():
        builder.button(text=f"{info['title']} ({info['price']}⭐)", callback_data=f"select_{item_id}")
    builder.adjust(1)
    await message.answer("🛒 **Please select a digital product to purchase:**", reply_markup=builder.as_markup())

# 2. /menu, /buy 명령어 처리
@dp.message(Command("menu", "buy"))
async def menu_handler(message: types.Message):
    builder = InlineKeyboardBuilder()
    for item_id, info in PRODUCTS.items():
        builder.button(text=f"{info['title']} ({info['price']}⭐)", callback_data=f"select_{item_id}")
    builder.adjust(1)
    await message.answer("🛒 **Please select a digital product to purchase:**", reply_markup=builder.as_markup())

# 3. 유저가 메뉴판에서 버튼을 직접 눌렀을 때 처리
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

@dp.message(F.successful_payment)
async def success_handler(message: types.Message):
    payment_info = message.successful_payment
    bought_item_id = payment_info.invoice_payload
    product = PRODUCTS.get(bought_item_id)
    if product:
        await message.answer(f"🎉 **Payment for [{product['title']}] completed successfully!**\n💰 Total Amount: {payment_info.total_amount} Stars ⭐\n\n💬 {product['success_msg']}\n🔗 {product['link']}\n\n⚠️ Please keep this link safe.")

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
