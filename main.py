import logging
from typing import Any
from src.agent.capability import MatchingCapability
from src.agent.base import BotAgent
from src.agent.io_interface import (
    SynchronousTTT,
    SharedValue,
)
from src.system_conf import (
    REPEAT_PROMPT,
    DYNAMIC_INTERRUPTION,
)
import os
import json
from src.main import AgentWorker
import asyncio
from src.agent.capability_worker import CapabilityWorker

from geopy.geocoders import Nominatim
import requests


STEP_ONE = "Which specific location are you interested in knowing the weather for?"
STEP_TWO = "Are you sure"


class CheckWeatherCapability(MatchingCapability):
    worker: AgentWorker = None
    capability_worker: CapabilityWorker = None
    weather_report: str = ""

    @classmethod
    def register_capability(cls) -> "MatchingCapability":
        with open(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        ) as file:
            data = json.load(file)
        return cls(
            unique_name=data["unique_name"],
            matching_hotwords=data["matching_hotwords"],
        )

    def get_location(self, answer: str):
        geolocator = Nominatim(user_agent="my_user_agent")
        loc = geolocator.geocode(answer)

        result = requests.get(
            f"https://api.open-meteo.com/v1/forecast?latitude={loc.latitude}&longitude={loc.longitude}&current=temperature_2m,wind_speed_10m,relative_humidity_2m,apparent_temperature",
        )
        result = result.json()

        temperature = result.get("current").get("temperature_2m")
        humidity = result.get("current").get("relative_humidity_2m")
        wind_speed = result.get("current").get("wind_speed_10m")
        apparent_temperature = result.get("current").get("apparent_temperature")

        weather_report = f"Temperature in {answer} is {temperature}° Celsius. "
        weather_report += f"Feels like {apparent_temperature}° Celsius. "
        weather_report += f"Humidity is {humidity}%. "
        weather_report += f"Wind speed is {wind_speed}km/h."

        self.weather_report = weather_report

        return True

    async def first_setup(self, location: str, interrupt_str: SharedValue):
        if location == "":
            questions = {
                "name": STEP_ONE,
                # "get_weather": STEP_TWO,
            }

            handlers = {
                "name": self.get_location,
                # "get_weather": self.get_weather_results,
            }

            kwargs = {}

            for q, prompt in questions.items():
                while True:
                    logging.debug("Capability: Prompt: " + prompt)
                    answer = await self.capability_worker.run_io_loop(
                        prompt,
                        interrupt_str,
                    )

                    logging.debug(f"User answer: {answer}")

                    if answer is None:
                        used_prompt = REPEAT_PROMPT
                        continue

                    if q in kwargs:
                        res = handlers[q](answer=answer, **kwargs[q])

                    # elif q == "name":
                    #     res = await handlers[q](answer)
                    else:
                        res = handlers[q](answer)

                    if res is None:
                        used_prompt = REPEAT_PROMPT
                        continue

                    break
        else:
            await self.get_location(location)

        self.worker.user_is_finished_speak_event.set()
        self.worker.user_is_speaking_event.clear()

        await self.capability_worker.speak(self.weather_report, interrupt_str)
        # await self.capability_worker.speak(CAPABILITY_RESUME_PROMPT, interrupt_str)

        await asyncio.sleep(1)

        self.capability_worker.resume_normal_flow()

        os.environ[DYNAMIC_INTERRUPTION] = "True"

    def call(
        self,
        msg: str,
        agent: BotAgent,
        text_respond: SynchronousTTT,
        speak_respond: None,
        audio: str,
        worker: AgentWorker,
        meta: dict[str, Any],
        interrupt_str: SharedValue,
    ):
        os.environ[DYNAMIC_INTERRUPTION] = "False"

        self.worker = worker
        self.capability_worker = CapabilityWorker(self.worker)

        self.worker.capability_event.set()

        location = ""
        # if msg.find(" in ") != -1:
        #     location = msg.split(" in ")[1]

        asyncio.create_task(self.first_setup(location, interrupt_str))
