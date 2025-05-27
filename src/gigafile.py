import traceback
from dotenv import load_dotenv
import os
from gigachat import GigaChat


load_dotenv()
giga_token = os.getenv("GIGA_CHAT_TOKEN")


def analyze_picture(file_data: bytes) -> str:
    
    try:
        giga = GigaChat(
            credentials=giga_token,
            verify_ssl_certs=False,
            model="GigaChat-2-Pro"
        )
        
        file = giga.upload_file(("file.png", file_data))
        file_id = file.id_
        result = giga.chat(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "Ты - эксперт-психолог, специализирующийся на профайлинге. Это фотография человека с аватарки в соцсети. Составь психотип человека с описанием его увлечений и предполагаемого возраста. Ответь только тезисами списком без объяснений",
                    "attachments": [file_id],
                }
            ],
            "temperature": 0.1
        })
        
        result_description = result.choices[0].message.content
        print(result_description)
        
        return result_description
    except Exception:
        print(traceback.format_exc())
    
    return None



#print(models)
#file = giga.upload_file(open("/Users/popovich/Documents/sber/gigachat/data/screen.png", "rb"))
#file_id = "c4e035c0-70cc-4a81-b051-80a91d0a0056"
#print(f"File uploaded: {file}")
#file_id = file.id_


if __name__ == '__main__':
    f = open("/Users/popovich/Documents/screen2.jpg", "rb")
    analyze_picture(f.read())
    