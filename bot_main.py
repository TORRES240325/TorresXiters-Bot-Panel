import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import func
from db_models import Usuario, Producto, Key, get_session
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('TOKEN', '8570947665:AAFUqtimxOzs-KPhqavl53N9RRxi21bb4RM')
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

LOGIN_KEY, BUY_CATEGORY, BUY_PRODUCT = range(3)

def get_keyboard_main(is_logged_in):
    """Genera el teclado principal (Diseño idéntico al solicitado)."""
    if is_logged_in:
        keyboard = [
            [KeyboardButton("🛒 Comprar Keys")],
            [KeyboardButton("👤 Mi Cuenta"), KeyboardButton("🚀 Cerrar Sesión")]
        ]
    else:
        keyboard = [
            [KeyboardButton("🔒 Iniciar Sesión"), KeyboardButton("➕ Registrarse")]
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra el mensaje de bienvenida y menú (IDÉNTICO AL DISEÑO)."""
    user_id_telegram = update.effective_user.id
    
    with get_session() as session_db:
        usuario = session_db.query(Usuario).filter_by(telegram_id=user_id_telegram).first() 

    is_logged = usuario is not None

    if is_logged:
        await update.message.reply_text("👋 ¡Bienvenido al Bot de Keys!", reply_markup=get_keyboard_main(True))
    else:
        welcome_message_english = (
            "✨ **Welcome to the Control Panel**\n"
            "You're almost in. Choose how you want to continue:\n\n"
            "🔸 Login — if you already have an account.\n"
            "🔹 Create Account — if you're new.\n\n"
            "We're glad to see you here!"
        )
        await update.message.reply_text(welcome_message_english, parse_mode='Markdown', reply_markup=get_keyboard_main(False))
    return ConversationHandler.END

async def ask_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Pide al usuario que ingrese las credenciales."""
    await update.message.reply_text(
        "Ingresa tus credenciales en formato:\n\n"
        "**USUARIO CLAVE**\n\n"
        "Ejemplo: juan 12345",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup([['❌ Cancelar']], resize_keyboard=True, one_time_keyboard=True)
    )
    return LOGIN_KEY

async def handle_login_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Procesa el login_key y la contraseña ingresada (CON LOGIN ROBUSTO)."""
    text = update.message.text
    
    if text == "❌ Cancelar":
        await update.message.reply_text("Sesión cancelada.", reply_markup=get_keyboard_main(False))
        return ConversationHandler.END

    parts = text.split()
    
    session_db = get_session()
    try:
        # CORRECCIÓN DE FORMATO (Si el usuario solo pone una palabra)
        if len(parts) != 2:
            await update.message.reply_text("❌ Formato incorrecto. Debes usar: `USUARIO CLAVE`", parse_mode='Markdown')
            return LOGIN_KEY

        username, login_key_input = parts
        user_id_telegram = update.effective_user.id
        
        # BÚSQUEDA ROBUSTA Y CASO-INSENSITIVA (SOLUCIÓN FINAL DE LOGIN)
        usuario = session_db.query(Usuario).filter(
            func.lower(Usuario.username) == func.lower(username), 
            Usuario.login_key == login_key_input
        ).first()

        if usuario:
            usuario.telegram_id = user_id_telegram 
            session_db.commit()

            await update.message.reply_text("✅ ¡Has sido autorizado exitosamente!", reply_markup=get_keyboard_main(True))
            return ConversationHandler.END
        else:
            await update.message.reply_text(
                "Login failed. Invalid Login Key. Please try again or type /start to go to the main menu."
            )
            return LOGIN_KEY
    except Exception as e:
        logger.error(f"Error en handle_login_key: {e}")
        session_db.rollback()
        await update.message.reply_text("Ha ocurrido un error inesperado. Intenta de nuevo o usa /start.")
        return ConversationHandler.END
    finally:
        session_db.close()

# --- Rutas de Compra (Se mantienen) ---

async def logout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id_telegram = update.effective_user.id
    with get_session() as session_db:
        usuario = session_db.query(Usuario).filter_by(telegram_id=user_id_telegram).first()
        if usuario:
            usuario.telegram_id = None
            session_db.commit()
    await update.message.reply_text("Sesión cerrada.", reply_markup=get_keyboard_main(False))

async def show_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id_telegram = update.effective_user.id
    with get_session() as session_db:
        usuario = session_db.query(Usuario).filter_by(telegram_id=user_id_telegram).first()
    if usuario:
        account_message = (f"👤 **Tu Cuenta**:\n" f"• Login: `{usuario.username}`\n" f"• Saldo: `${usuario.saldo:.2f}`\n")
        keyboard = [[InlineKeyboardButton("💰 Canjear código promocional", callback_data="redeem"), InlineKeyboardButton("📜 Historial de Compras", callback_data="history")], [InlineKeyboardButton("⬆️ Historial de Recargas", callback_data="topup_history")]]
        await update.message.reply_text(account_message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("Por favor, inicia sesión primero.", reply_markup=get_keyboard_main(False))

async def show_buy_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    telegram_id = update.effective_user.id
    db_session = get_session()
    try:
        usuario = db_session.query(Usuario).filter_by(telegram_id=telegram_id).first()
        if not usuario: return await update.message.reply_text("❌ Debes iniciar sesión para comprar."), ConversationHandler.END

        categories = db_session.query(Producto.categoria).join(Key, Producto.id == Key.producto_id).filter(Key.estado == 'available').distinct().all()

        if not categories: await update.message.reply_text("No hay keys disponibles en stock. Intenta más tarde.", reply_markup=get_keyboard_main(True)); return ConversationHandler.END

        keyboard = [[KeyboardButton(c[0])] for c in categories]; keyboard.append([KeyboardButton("❌ Cancelar Compra")]); context.user_data['user_id'] = usuario.id
        await update.message.reply_text("Selecciona una categoría:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return BUY_CATEGORY
    finally: db_session.close()

async def handle_category_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    category = update.message.text
    if category == "❌ Cancelar Compra": return await start(update, context)
    if category == "« Volver a Categorías": return await show_buy_menu(update, context)

    db_session = get_session()
    try:
        productos_con_stock = db_session.query(Producto, func.count(Key.id).label('available_stock')).join(Key, Producto.id == Key.producto_id).filter(Producto.categoria == category, Key.estado == 'available').group_by(Producto.id).all()

        if not productos_con_stock: await update.message.reply_text(f"❌ No se encontraron productos en la categoría: **{category}**", parse_mode='Markdown'); return BUY_CATEGORY

        keyboard_buttons = []
        for producto, stock in productos_con_stock:
            button_text = f"{producto.nombre} - ${producto.precio:.2f} (Stock: {stock})"
            keyboard_buttons.append([KeyboardButton(button_text)])

        keyboard_buttons.append([KeyboardButton("« Volver a Categorías")])
        await update.message.reply_text(f"Productos en **{category}**:", parse_mode='Markdown', reply_markup=ReplyKeyboardMarkup(keyboard_buttons, resize_keyboard=True))
        return BUY_PRODUCT
    finally: db_session.close()

async def handle_final_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    user_id_telegram = update.effective_user.id
    if text == "« Volver a Categorías": return await show_buy_menu(update, context)

    session_db = get_session()
    try:
        parts = text.rsplit(' - $', 1); product_name = parts[0].strip()
        price = float(parts[1].split('(')[0].strip().replace('$', '').replace(',', '.'))
        
        usuario = session_db.query(Usuario).filter_by(telegram_id=user_id_telegram).first()
        producto = session_db.query(Producto).filter_by(nombre=product_name).first()

        if not usuario or not producto: raise Exception("User or Product not found.")

        if usuario.saldo < price: await update.message.reply_text(f"❌ Saldo insuficiente. Tu saldo es: ${usuario.saldo:.2f}", reply_markup=get_keyboard_main(True)); return ConversationHandler.END

        available_key = session_db.query(Key).filter_by(producto_id=producto.id, estado='available').with_for_update(nowait=True).first() 

        if not available_key: await update.message.reply_text(f"❌ Producto agotado. No hay claves disponibles para {producto.nombre}.", reply_markup=get_keyboard_main(True)); return ConversationHandler.END

        usuario.saldo -= price; available_key.estado = 'used'; available_key.usuario_id = usuario.id; session_db.commit()
        
        final_message = (f"🎉 **COMPRA EXITOSA!**\n\n🔐 Tu Key/Licencia: `{available_key.licencia}`\n💰 Nuevo Saldo: ${usuario.saldo:.2f}")
        await update.message.reply_text(final_message, parse_mode='Markdown', reply_markup=get_keyboard_main(True))
        return ConversationHandler.END

    except Exception as e:
        session_db.rollback(); logger.error(f"Error CRÍTICO en la transacción: {e}")
        await update.message.reply_text("Error procesando la compra.", reply_markup=get_keyboard_main(True))
        return ConversationHandler.END
    finally: session_db.close()


def main() -> None:
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex("^👤 Mi Cuenta$"), show_account))
    application.add_handler(MessageHandler(filters.Regex("^🚀 Cerrar Sesión$"), logout_handler))
    application.add_handler(MessageHandler(filters.Regex("^➕ Registrarse$"), lambda u, c: u.message.reply_text("Para crear una cuenta, contacta a un administrador.", reply_markup=get_keyboard_main(False))))
    
    login_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔒 Iniciar Sesión$"), ask_login)],
        states={
            LOGIN_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_login_key)]
        },
        fallbacks=[CommandHandler("start", start), MessageHandler(filters.Regex("^❌ Cancelar$"), lambda u, c: start(u,c))],
    )
    application.add_handler(login_conv_handler)
    
    buy_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🛒 Comprar Keys$"), show_buy_menu)],
        states={
            BUY_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category_selection)],
            BUY_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_final_purchase)],
        },
        fallbacks=[CommandHandler("start", start), MessageHandler(filters.Regex("^❌ Cancelar Compra$"), lambda u, c: start(u,c))],
        per_user=True,
    )
    application.add_handler(buy_conv_handler)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()