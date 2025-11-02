import telebot

# 🔑 Mets ici le token de ton bot (celui que t’a donné BotFather)
BOT_TOKEN = "8367632752:AAHz_AV4d7oFDJYqqbnBKIctNv3l26TMQq8"

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(func=lambda message: True)
def show_chat_id(message):
    print("🆔 Chat ID détecté :", message.chat.id, "| Utilisateur :", message.from_user.username)
    bot.reply_to(message, f"✅ Ton chat_id est : {message.chat.id}")

print("🤖 En attente d’un message...")
bot.polling()
