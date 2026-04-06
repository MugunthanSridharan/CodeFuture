import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
print(os.environ.get("GROQ_API_KEY"))
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
conversation_history = []

def listUserMessages() :
    while True:
        userInput = input("You    : ")
        if userInput.strip().lower() == "exit":
            print("Goodbye!")
            break
        else:
            response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # free model
            messages=[{"role": "user", "content": userInput}]
            )
        print(response.choices[0].message.content)
        conversation_history.append("You :"+userInput)
        conversation_history.append("AI  :"+response.choices[0].message.content)         
listUserMessages()
os.system('cls')
for messages in conversation_history :
    print(messages)
