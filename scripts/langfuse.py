import os
from langfuse import Langfuse

class LangfuseConnector():
    def __init__(self, public_api_key=None, secret_api_key=None, api_url=None, headers=None):
        self.api_key = public_api_key
        self.api_url = api_url

        # get keys for your project from https://cloud.langfuse.com
        os.environ["LANGFUSE_PUBLIC_KEY"] = public_api_key
        os.environ["LANGFUSE_SECRET_KEY"] = secret_api_key

        self.langfuse = Langfuse()

    def get_prompt(self, name):
        # Get the prompt from the Langfuse API
        try:
            prompt = self.langfuse.get_prompt(name, label="latest")
        #Exception not found
        except Exception as e:
            prompt = self.langfuse.get_prompt("default", label="latest", cache_ttl_seconds=0)
        return prompt
        
    def update_prompt(self, name, updated_prompt, production=True):

        prompt_original_format = [{"role": t[0], "content": t[1]} for t in updated_prompt]

        # Replace all "{" and "}" brackets with "{{" and "}}"
        prompt_final = []
        for item in prompt_original_format:
            role = item["role"]
            content = item["content"].replace("{", "{{").replace("}", "}}")
            prompt_final.append({"role": role, "content": content})

        response = self.langfuse.create_prompt(  # added response assignment
            name=name,  # stejný název = nová verze
            type="chat",
            prompt=prompt_final,  # updated to use prompt_final
            labels=["production"] if production else ["staging"]  # můžeš přidat např. i "staging"
        )
        return response

