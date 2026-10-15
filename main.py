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
    "item_001": {"title": "01", "desc": "Would you like to purchase 01!", "price": 250, "link": "https://gofile.io", "success_msg": "PW:FGW002301"},
    "item_002": {"title": "02", "desc": "Would you like to purchase 02?", "price": 250, "link": "https://example.com", "success_msg": "PW:FGW002302"},
    "item_003": {"title": "03", "desc": "Would you like to purchase 03?", "price": 250, "link": "https://example.com", "success_msg": "Pw:FGW002303"},
    "item_004": {"title": "04", "desc": "Would you like to purchase 04?", "price": 300, "link": "https://example.com", "success_msg": "Pw:FGW002304"},
    "item_005": {"title": "05", "desc": "Would you like to purchase 05?", "price": 300, "link": "https://example.com", "success_msg": "Pw:FGW002305"},
    "item_006": {"title": "06", "desc": "Would you like to purchase 06?", "price": 400, "link": "https://example.com", "success_msg": "Pw:FGW002306"},
    "item_007": {"title": "05", "desc": "Would you like to purchase 07?", "price": 150, "link": "https://example.com", "success_msg": "Pw:FGW002307"},
    "item_008": {"title": "08", "desc": "Would you like to purchase 08?", "price": 150, "link": "https://example.com", "success_msg": "Pw:FGW002308"},
    "item_009": {"title": "09", "desc": "Would you like to purchase 09?", "price": 150, "link": "https://example.com", "success_msg": "Pw:FGW002309"},
    "item_010": {"title": "10", "desc": "Would you like to purchase 10?", "price": 150, "link": "https://example.com", "success_msg": "Pw:FGW002310"},
    "item_011": {"title": "11", "desc": "Would you like to purchase 11?", "price": 150, "link": "https://example.com", "success_msg": "Pw:FGW002311"},
    "item_012": {"title": "12", "desc": "Would you like to purchase 12?", "price": 150, "link": "https://example.com", "success_msg": "Pw:FGW002312"},
    "item_013": {"title": "13", "desc": "Would you like to purchase 13?", "price": 150, "link": "https://example.com", "success_msg": "Pw:FGW002313"}
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

# 1. /start 명령어 처리 (★개별 상품 링크 입장만 허용하도록 전면 수정)
@dp.message(Command("start"))
async def start_handler(message: types.Message, command: CommandObject):
    # 홍보 링크 뒤에 상품 코드(예: item_001)가 완벽하게 매칭되어 들어온 경우
    if command.args and command.args in PRODUCTS:
        item_id = command.args
        product = PRODUCTS[item_id]
        await send_product_invoice(message.chat.id, item_id, product) # 즉시 개별 결제창만 팝업
        return

    # ★ 중요: 그냥 /start를 치거나 봇을 처음 켠 사용자는 전체 목록을 띄우지 않고 완전히 무시합니다.
    # (유저에게 혼란을 주지 않기 위해 봇이 아예 묵비권을 행사하거나 아무 반응을 하지 않게 만듭니다.)
    return

# 혹시 모를 관리자용 검증 명령어로 변경 (주소 추출용 백업 명령어)
@dp.message(Command("menu", "buy"))
async def menu_handler(message: types.Message):
    # 사장님이 테스트해볼 때를 위해 /menu를 치면 목록이 나오게 최소한의 안전장치만 남겨둠
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
