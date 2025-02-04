﻿import json
import ollama
import os
from typing import Callable
from datetime import datetime
from langchain_ollama import ChatOllama
from ollama import ChatResponse
from ..AiAssistant.Functions.Holidays import Holiday  # type: ignore
from ..AiAssistant.Functions.Holidays.HolidayService import HolidayService  # type: ignore

class Assistant:
    def __init__(self, model_name: str = "llama3.2", use_online_sources: bool = False):
        self.use_online_sources = use_online_sources
        self.model_name = model_name
        self.__holiday_service = HolidayService(from_online_source=use_online_sources)
        self.__initialized_model = self.__config_model()


    def get_ai_output(self, prompt: str) -> str:
        time_context = f"[Metadata: Data e hora atual: " + datetime.now().strftime("%d/%B/%Y %H:%M:%S") + "]\n---\n"
        return self.__run_llm(time_context + prompt)



    @staticmethod
    def __get_tools() -> str:
        dir_path = os.path.dirname(os.path.realpath(__file__))
        file_path = os.path.join(dir_path, 'tools.json')
        file_content: str
        with open(file_path, 'r') as file:
            file_content = file.read()

        tools = json.loads(file_content)["tools"]
        return tools



    def __get_response_from_model(self, prompt_input: str) -> ChatResponse:
        response = ollama.chat(
            model=self.model_name,
            messages=[
                {
                    "role": "user",
                    "content": prompt_input,
                },
            ],
        )

        return response


    def __config_model(self) -> ChatOllama:
        model: ChatOllama = ChatOllama(model=self.model_name, format="json")
        tools = self.__get_tools()
        model = model.bind_tools(tools)  # type: ignore
        return model


    def __run_llm(self, prompt_input) -> str:
        functions: dict[str, Callable[[str, int, int], list[Holiday]]] = {
            "get_holidays": self.__holiday_service.get_holidays
        }

        try:
            generic_error_message = "Não foi possível encontrar uma resposta para a pergunta"
            result = self.__initialized_model.invoke(prompt_input)
            if not result:
                raise ValueError("Resultado não encontrado")

            tool_calls = result.tool_calls  # type: ignore
            if not tool_calls:
                raise ValueError("Chamadas de função não encontradas")

            # Function calls
            # Referencia: https://github.com/msamylea/Llama3_Function_Calling
            for tool_call in tool_calls:
                function_name: str = tool_call.get('name')
                function_parameters: dict[str, str] = tool_call.get('args')

                if not function_parameters or not function_name:
                    raise ValueError("Argumentos ou nome da função não encontrados")

                function = (functions.get(function_name))

                # Feriados
                if function_name == "get_holidays":
                    state: str | None = function_parameters.get('state')
                    year_as_str: str | None = function_parameters.get('year')
                    month_as_str: str | None = function_parameters.get('month')
                    year: int | None = int(year_as_str) if year_as_str else None
                    month: int | None = int(month_as_str) if month_as_str else None
                    if state and year and month:
                        holidays_list: list[Holiday] = function(state, year, month)  # type: ignore

                        if holidays_list.__len__() == 0:
                            return "Nenhum feriado foi encontrado"

                        re_input = ("Dada essa pergunta: '" + prompt_input + "', os feriados são: "
                                    + str(holidays_list)
                                    + ". Responda a pergunta de forma resumida e direta e como se estivesse conversando oralmente."
                                    )

                        chat_response = self.__get_response_from_model(re_input)
                        if isinstance(chat_response.message.content, str):
                            return chat_response.message.content
                        else:
                            return generic_error_message


            # Resposta genérica
            chat_response = self.__get_response_from_model(prompt_input)
            if isinstance(chat_response.message.content, str):
                return chat_response.message.content
            else:
                return generic_error_message

        except Exception as e:
            print(f"Erro ao tentar responder: {e}")
            return "Desculpe, parece que houve um erro ao tentar responder. O que acha de reformular a pergunta?"
