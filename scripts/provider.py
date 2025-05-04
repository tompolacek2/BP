# Create default class for LLM and generate methods for LLM

from langchain_groq import ChatGroq
from langchain.chat_models import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableConfig
from typing import Any
from langfuse.decorators import observe, langfuse_context
from langfuse.callback import CallbackHandler




class Provider():
    """
    Base class for LLM (Large Language Model)¨
    """

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize the LLM class.
        """
        self.llm = None
        pass
    
    @observe()
    def generate(self, langfuse, messages, user_id="") -> str:
        """
        Generate a response from the LLM.
        """

        prompt = ChatPromptTemplate.from_messages(
            messages
        )
        handler: CallbackHandler = CallbackHandler()

        formatted_messages = prompt.format_messages()
        handler.input = "\n".join(f"{m.type.upper()}: {m.content}" for m in formatted_messages)

        handler.user_id = user_id
        handler.tags = [str(user_id)]
        output_parser = StrOutputParser()
        chain = prompt | self.llm | output_parser

        return chain.invoke({"messages": messages}, config={"callbacks": [handler]})

    

class GroqProvider(Provider):
    """
    Groq class for LLM (Large Language Model)
    """

    available_models = [
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "meta-llama/llama-4-maverick-17b-128e-instruct",
        "llama-3.3-70b-versatile"
    ]

    def __init__(self, api_key, model) -> None:
        """
        Initialize the Groq class.
        """
        super().__init__(api_key=api_key, model=model)
        self.llm = ChatGroq(api_key=api_key, model=model)
        self.api_key = api_key
        self.model = model


class OpenRouterProvider(Provider):
    """
    OpenRouter class for LLM (Large Language Model)
    """

    available_models = [
        "google/gemini-2.5-pro-exp-03-25:free",
        "deepseek/deepseek-chat-v3-0324:free",
        "deepseek/deepseek-r1:free",
        "google/gemini-2.0-flash-exp:free",
        "nvidia/llama-3.1-nemotron-ultra-253b-v1:free"
    ]

    def __init__(self, api_key, model) -> None:
        """
        Initialize the OpenRouter class.
        """
        super().__init__(api_key=api_key, model=model)
        self.llm = ChatOpenAI(
            openai_api_base="https://openrouter.ai/api/v1",
            openai_api_key=api_key, 
            model_name=model, 
        )
        self.api_key = api_key
        self.model = model

class OpenAIProvider(Provider):
    """
    OpenAI class for LLM (Large Language Model)
    """
    available_models = [
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano"
    ]

    def __init__(self, api_key, model) -> None:
        """
        Initialize the OpenAI class.
        """
        super().__init__(api_key=api_key, model=model)
        self.llm = ChatOpenAI(
            openai_api_key=api_key, 
            model_name=model, 
        )
        self.api_key = api_key
        self.model = model

class GeminiProvider(Provider):
    """
    Gemini class for LLM (Large Language Model)
    """

    available_models = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-2.5-flash"
    ]

    def __init__(self, api_key, model) -> None:
        """
        Initialize the Gemini class.
        """
        super().__init__(api_key=api_key, model=model)
        self.llm = ChatGoogleGenerativeAI(
            google_api_key=api_key, 
            model_name=model, 
        )
        self.api_key = api_key
        self.model = model

class EinfraProvider(Provider):
    """
    Einfra class for LLM (Large Language Model)
    """

    available_models = [
        "llama3.3:latest",
        "llama-4-scout-17b-16e-instruct",
    ]

    def __init__(self, api_key, model) -> None:
        """
        Initialize the Einfra class.
        """
        super().__init__(api_key=api_key, model=model)
        self.llm = ChatOpenAI(
            openai_api_base="https://chat.ai.e-infra.cz/api",
            openai_api_key=api_key,
            model_name=model,
        )
        self.api_key = api_key
        self.model = model