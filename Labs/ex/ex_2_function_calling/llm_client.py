from openai import OpenAI


def create_client():
    # /api/v1,/api/chat/completions
    client = OpenAI(
        base_url="http://172.10.0.2:8080/api/v1",
        api_key="sk-f60ffbf03ede457987a23650b8b11763" 
        #api_key="sk-cebd4fabff5f4b5d8434795173832ba9"
    )

    return client