#from langgraph.graph import Graph, END, START
from typing import TypedDict, Annotated, List, Dict, Any, Union
import operator
#from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
#from langchain_core.prompts import ChatPromptTemplate
import pandas as pd
import json
from openai import OpenAI
import time
import traceback
import ast
from dotenv import load_dotenv
import os

from gigachat import GigaChat

api = "MDYyNTU3OTUtNzJmZC00YzIxLTgzZDEtNGRhYzYwOGY1YjZjOjFkOWZhZGIwLTQ5NTYtNDkzMi1hZGVhLTQyZjU0YThkOWUxMQ=="
giga = GigaChat(
    credentials=api,
    verify_ssl_certs=False,
    model="GigaChat-2-Pro"
)

models = giga.get_models()
#print(models)
#file = giga.upload_file(open("/Users/popovich/Documents/sber/gigachat/data/screen.png", "rb"))
file_id = "c4e035c0-70cc-4a81-b051-80a91d0a0056"
#print(f"File uploaded: {file}")

#file_id = file.id_
result = giga.chat(
    {
        "messages": [
            {
                "role": "user",
                "content": "Ты - эксперт-психолог, специализирующийся на профайлинге. Это фотография человека с аватарки в соцсети. Составь психотип человека с описанием его увлечений и предполагаемого возраста. Ответь только тезисами",
                "attachments": [file_id],
            }
        ],
        "temperature": 0.1
    }
)

print(result.choices[0].message.content)