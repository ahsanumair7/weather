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

class WeatherCapability(MatchingCapability):
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
            if self.worker.language != "" or self.worker.language != "english":
                self.weather_report += "Reply in language: %s"%self.worker.language
                self.weather_report = self.capability_worker.text_to_text_response(self.weather_report, self.worker.agent_memory.full_message_history)

            return True

        except Exception as e:
            self.weather_report = "An error occurred while fetching the weather data. Please try again."
            return False

    async def first_setup(self):
        # msg = self.worker.final_user_input

        msg = await self.capability_worker.wait_for_complete_transcription()
        
        # Extract location from user message using text-to-text response
        location_prompt = f"""
        Based on the user message, extract the location/city name they are asking about.
        
        Examples:
        - "What's the weather in New York?" -> New York
        - "How's the weather in London today?" -> London
        - "Weather for Tokyo" -> Tokyo
        - "Tell me about the weather in Paris" -> Paris
        - "What's the weather like?" -> ASK
        
        If no specific location is mentioned, return "ASK".
        If a location is mentioned, return only the location name.
        
        User message: {msg}
        """
        
        location = self.capability_worker.text_to_text_response(location_prompt, 
                                                              self.worker.agent_memory.full_message_history)

        if location == "ASK":
            # Ask user for location if not specified
            await self.capability_worker.speak(STEP_ONE)
            user_response = await self.capability_worker.user_response()
            
            if user_response is None:
                self.weather_report = "I didn't catch that. Please try again."
            else:
                res = self.get_location(user_response)
                if not res:
                    self.weather_report = "Incorrect location, please try again."
        else:
            # Use the extracted location
            res = self.get_location(location)
            if not res:
                self.weather_report = "Incorrect location, please try again."

        # Speak the weather report (or error message) once
        await self.capability_worker.speak(self.weather_report)
        self.worker.session_tasks.sleep(1)
        self.capability_worker.resume_normal_flow()

    def call(
        self,
        worker: AgentWorker,
    ):
        self.worker = worker
        self.capability_worker = CapabilityWorker(self.worker)
        self.worker.session_tasks.create(self.first_setup())
