import json 
import requests
import time
import spacy
import re
nlp = spacy.load('en_core_web_md')
from rasa_nlu.training_data import load_data
from rasa_nlu.config import RasaNLUModelConfig
from rasa_nlu.model import Trainer
from rasa_nlu import config
from iexfinance.stocks import Stock

#Here are the token for using telegram and iexcloud
TOKEN_tel = "522719293:AAGpoWxbhpc7lOlXJjJonTZW2qwOV3A-lZ4"
TOKEN_iex = "pk_67c8dab7c8374c959d5359d6d566de0c"
URL = "https://api.telegram.org/bot{}/".format(TOKEN_tel)

#Rasa nlu is used for the Intention recognition for this project
#The training model is created via Chatito DSL
trainer = Trainer(config.load("config_spacy.yml"))
training_data = load_data('testing_dataset.json')
interpreter = trainer.train(training_data)

#Define the state for the state machine
#Three States are implemented in this project:initial,specification,final
INIT=0 
SPEC=1
FIN=2 

def get_url(url):
    response = requests.get(url)
    content = response.content.decode("utf8")
    return content

def get_json_from_url(url):
    content = get_url(url)
    js = json.loads(content)
    return js

def get_updates(offset=None):
    url = URL + "getUpdates?timeout=100"
    if offset:
        url += "&offset={}".format(offset)
    js = get_json_from_url(url)
    return js

def get_last_chat_id_and_text(updates):
    num_updates = len(updates["result"])
    last_update = num_updates - 1
    text = updates["result"][last_update]["message"]["text"]
    chat_id = updates["result"][last_update]["message"]["chat"]["id"]
    return (text, chat_id)

def get_last_update_id(updates):
    update_ids = []
    for update in updates["result"]:
        update_ids.append(int(update["update_id"]))
    return max(update_ids)

def send_message(text, chat_id):
    url = URL + "sendMessage?text={}&chat_id={}".format(text, chat_id)
    get_url(url)
    
# Use the regular expression to find the ticker/stock symbol in the message
def find_ticker(message):
    ticker = None
    ticker_pattern = re.compile("[A-Z]{3,}")
    ticker = ticker_pattern.findall(message)
    return ticker

#Get quote of the give orgnization from IEX cloud
def Gquote(ORG):
    Str=Stock('{}'.format(str(ORG)),token="{}".format(TOKEN_iex))
    quote=Str.get_quote()
    print(quote)
    return quote

#primary respond command, which reponse base on current state of the conversation
def respond(policy, state, message,text_id):
    print("test2")
    print(state)
    print(interpreter.parse(message)["intent"]["name"])
    (new_state, text) = policy[(state, interpreter.parse(message)["intent"]["name"])]
    send_message(text,text_id)
    return new_state

#The inital state policy is incomplete, this enables to fill in the policy with the message from user
def fill_policy(message,ORG):
#Initialize a partial template for the quote    
    quote={
 'latestPrice': 0,
 'latestVolume': 0,
 'marketCap': 0,
         }
    #Use the find_ticker to match ticker in the message
    if ORG==[] :
        NEW_ORG=find_ticker(message)
        if NEW_ORG != []:
            ORG=str(NEW_ORG[0])
    #chekcing whether there's a not ORG been searched
    NEW_ORG=find_ticker(message)
    if NEW_ORG !=[] and NEW_ORG != ORG and ORG !=[]:
    #subsitute the old ORG with the NEW_ORG   
        ORG=NEW_ORG[0]
        print(ORG)

    if ORG != []:
        try:
            quote=Gquote(ORG)
        except Exception as e:
            print("There's something wrong with ticker")
            print(e)
    #The state policy setup a general process of the dialogue.
    #State is initialized after two search or a new search is implied
    policy_rules = {
        (INIT, "greet"): (INIT, "Hi, my name is stookbot.I'm a Chatbot to help you look up stock market"),
        (INIT, "specORG"): (INIT, "What kind of quote do you want to look up?"),
        (INIT, "valuelookup"): (SPEC, "The marketcap of {} is {} USD.".format(ORG,quote["marketCap"])),
        (INIT, "volumelookup"): (SPEC, "The market volume of {} is {} USD.".format(ORG,quote["latestVolume"])),
        (INIT, "stocklookup"): (SPEC, "The stock price of {} is {} USD.".format(ORG,quote["latestPrice"])),
        (SPEC, "valuelookup"): (INIT, "OK,here it is.The market value of {} is {} USD.".format(ORG,quote["marketCap"])),
        (SPEC, "volumelookup"): (INIT, "OK,here it is.The market volume of {} is {} USD.".format(ORG,quote["latestVolume"])),
        (SPEC, "stocklookup"): (INIT, "OK,here it is.The stock price of {} is {} USD.".format(ORG,quote["latestPrice"])),
        (SPEC, "specORG"): (SPEC, "OK, what kind of quote do you need?"),
        (SPEC, "greet"):(INIT, "Nice to meet you,what stock information do you need?"),
        } 
    print (policy_rules)
    #A validation value is used to check where user has stated the ticker correctly
    if not ORG:
        val=0
    else: val=1 
    return policy_rules,ORG,val

def main():
    last_update_id = None
    state=INIT
    ORG = []
    while True:
        updates = get_updates(last_update_id)   
        if len(updates["result"]) > 0:
            #get the user id and message from telegram
            last_update_id = get_last_update_id(updates) + 1
            (message,text_id)=get_last_chat_id_and_text(updates)
            #The program start with filling the state policy
            (policy_rules,ORG,val)=fill_policy(message,ORG)
            if val==0 and state != INIT:    
                send_message("Please provide the ticker",text_id)
            else: 
                    state=respond(policy_rules, state, message,text_id) 
            time.sleep(0.5)


if __name__ == '__main__':
    main()