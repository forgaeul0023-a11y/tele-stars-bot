import os
import json
import time
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
WEBHOOK_BASE = os.getenv("WEBHOOK_BASE")
WEBHOOK_PATH = "/webhook"
PORT = int(os.getenv("PORT", 10000))

bot = Bot(token=BOT_TOKEN, api_version="10.3")
dp = Dispatcher()

def load_products():
    with open("products.json", "r", encoding="utf-8") as f:
        return json.load(f)

PRODUCTS = load_products()

def save_order(chat_id: int, item_id: str):
    try:
        with open("orders.json", "a", encoding="utf-8") as f:
            f.write(json.dumps({"c": chat_id, "i": item_id, "t": int(time.time())}) + "\n")
    except Exception:
        pass
    asyncio.create_task(bot.send_message(ADMIN_ID, f"🧾 {chat_id} / {item_id}"))

async def send_product_invoice(chat_id: int, item_id: str, product: dict):
    pay_builder = InlineKeyboardBuilder()
    pay_builder.button(text=f"⭐ Pay {product['price']} Stars", pay=True)
    description = (
        product["desc"]
        + "\n\n※ Digital goods are non-refundable after payment."
        + "\nResend available for non-delivery or malfunction."
        + "\nBy paying, you agree to the above."
    )
    await bot.send_invoice(
        chat_id=chat_id, title=product["title"], description=description,
        payload=item_id, provider_token="", currency="XTR",
        prices=[types.LabeledPrice(label="Amount", amount=product["price"])],
        reply_markup=pay_builder.as_markup()
    )

@dp.message(Command("start"))
async def start_handler(message: types.Message, command: CommandObject):
    if command.args and command.args in PRODUCTS:
        item_id = command.args
        product = PRODUCTS[item_id]
        asyncio.create_task(send_product_invoice(message.chat.id, item_id, product))
    else:
        await bot.send_message(
            chat_id=message.chat.id,
            text="🛒 **Welcome to our shop!**\n\nUse /menu to browse products.",
            reply_markup=types.ReplyKeyboardRemove(),
            protect_content=True
        )
    return

@dp.message(Command("menu", "buy"))
async def menu_handler(message: types.Message):
    builder = InlineKeyboardBuilder()
    for item_id, info in PRODUCTS.items():
        builder.button(text=f"{info['title']} ({info['price']}⭐)", callback_data=f"select_{item_id}")
    builder.adjust(1)
    await message.answer("🛒 Product List:", reply_markup=builder.as_markup())

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

    if not product:
        await message.answer("Payment successful, but product not found.")
        return

    save_order(message.chat.id, bought_item_id)

    await message.answer(
        f"🎉 **Payment for [{product['title']}] completed!**\n"
        f"💰 {payment_info.total_amount} Stars ⭐\n"
        f"※ Non-refundable · /resend if not received\n\n"
        f"📦 Sending your file..."
    )

    if product.get("file_id"):
        caption = f"📦 {product['title']}\n"
        if product.get("password"):
            caption += f"🔑 PW: {product['password']}\n"
        caption += "⚠️ Keep this file safe."
        try:
            await bot.send_document(
                chat_id=message.chat.id,
                document=product["file_id"],
                caption=caption,
                protect_content=True
            )
        except Exception:
            try:
                await asyncio.sleep(2)
                await bot.send_document(
                    chat_id=message.chat.id,
                    document=product["file_id"],
                    caption=caption,
                    protect_content=True
                )
            except Exception:
                await message.answer("⚠️ File send failed. Please /resend or contact the admin.")
    else:
        await message.answer("⚠️ Product file is not set. Please contact the admin.")

@dp.message(Command("resend"))
async def resend_handler(message: types.Message):
    last = None
    try:
        with open("orders.json", encoding="utf-8") as f:
            for line in f:
                o = json.loads(line)
                if o["c"] == message.chat.id:
                    last = o
    except FileNotFoundError:
        pass
    if not last:
        await message.answer("⚠️ No record found. Please contact the admin.")
        return
    product = PRODUCTS.get(last["i"])
    if product and product.get("file_id"):
        await bot.send_document(
            chat_id=message.chat.id,
            document=product["file_id"],
            protect_content=True
        )
    else:
        await message.answer("⚠️ No file to resend. Please contact the admin.")

@dp.message(F.document, F.from_user.id == ADMIN_ID)
async def get_document_id(message: types.Message):
    d = message.document
    await message.answer(
        f"📦 {d.file_name}\n"
        f"size: {d.file_size}\n"
        f"{d.file_id}"
    )

@dp.message(F.video, F.from_user.id == ADMIN_ID)
async def get_video_id(message: types.Message):
    v = message.video
    await message.answer(
        f"🎬 {v.file_name}\n"
        f"size: {v.file_size}\n"
        f"{v.file_id}"
    )

async def health(request):
    return web.Response(text="ok")

async def on_startup(bot: Bot):
    await bot.set_webhook(f"{WEBHOOK_BASE}{WEBHOOK_PATH}")

def main():
    dp.startup.register(on_startup)
    app = web.Application()
    app.router.add_get("/health", health)
    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    web.run_app(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
