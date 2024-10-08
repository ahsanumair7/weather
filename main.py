import asyncio
import json
import os
from src.agent.capability import MatchingCapability
from src.main import AgentWorker
from src.agent.capability_worker import CapabilityWorker
from geopy.geocoders import Nominatim
import requests

STEP_ONE = "Which specific location are you interested in knowing the weather for?"
STEP_TWO = "Are you sure"
REPEAT_PROMPT = "I'm sorry, I didn't get that. Please repeat that."

class NewWeatherCapability(MatchingCapability):
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
        
        try:
            loc = geolocator.geocode(answer)
            
            if loc is None:
                # Location not found
                self.weather_report = "Incorrect location, please try again."
                return False
            
            # Call the weather API with the location coordinates
            result = requests.get(
                f"https://api.open-meteo.com/v1/forecast?latitude={loc.latitude}&longitude={loc.longitude}&current=temperature_2m,wind_speed_10m,relative_humidity_2m,apparent_temperature",
            )
            result = result.json()

            # Extract weather data
            temperature = result.get("current", {}).get("temperature_2m")
            humidity = result.get("current", {}).get("relative_humidity_2m")
            wind_speed = result.get("current", {}).get("wind_speed_10m")
            apparent_temperature = result.get("current", {}).get("apparent_temperature")

            # If the API does not return weather data, handle the error gracefully
            if not temperature or not humidity or not wind_speed or not apparent_temperature:
                self.weather_report = "Unable to retrieve weather data, please try again later."
                return False

            # Construct the weather report
            self.weather_report = (
                f"Temperature in {answer} is {temperature}° Celsius. "
                f"Feels like {apparent_temperature}° Celsius. "
                f"Humidity is {humidity}%. "
                f"Wind speed is {wind_speed} km/h."
            )

            return True

        except Exception as e:
            self.weather_report = "An error occurred while fetching the weather data. Please try again."
            return False


    async def first_setup(self, location: str):
        if location == "":
            questions = {
                "name": STEP_ONE,
            }

            handlers = {
                "name": self.get_location,
            }

            for q, prompt in questions.items():
                used_prompt = prompt
                while True:
                    answer = await self.capability_worker.run_io_loop(used_prompt)

                    if answer is None:
                        used_prompt = REPEAT_PROMPT
                        continue

                    res = handlers[q](answer)
                    if res is False:  # This means the location was invalid or not found
                        used_prompt = REPEAT_PROMPT
                        continue  # Exit the loop if the location is invalid

                    if res:
                        break  # Exit the loop if the location was successfully processed
        else:
            res = self.get_location(location)
            if not res:
                self.weather_report = "Incorrect location, please try again."

        # Speak the weather report (or error message) once
        await self.capability_worker.speak(self.weather_report)
        await asyncio.sleep(1)
        self.capability_worker.resume_normal_flow()

    def call(
        self,
        worker: AgentWorker,
    ):
        self.worker = worker
        self.capability_worker = CapabilityWorker(self.worker)
        location = ""
        asyncio.create_task(self.first_setup(location))
