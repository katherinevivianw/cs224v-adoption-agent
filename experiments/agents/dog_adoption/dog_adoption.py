import asyncio
import os
import random
from uuid import uuid4
import requests
import json
import yaml

from suql.agent import postprocess_suql

from worksheets.agent import Agent
from worksheets.environment import get_genie_fields_from_ws
from worksheets.interface_utils import conversation_loop
from worksheets.knowledge import SUQLKnowledgeBase, SUQLParser, SUQLReActParser

with open("model_config.yaml", "r") as config:
    model_config = yaml.safe_load(config)

# Define your APIs
class AdoptionSearch:
    def __init__(self):
        self.base_url = 'https://api-staging.adoptapet.com/search/'
        self.key = 'hg4nsv85lppeoqqixy3tnlt3k8lj6o0c'
        self.api_version = '3'
        self.output_format = 'json'
        self.species = 'dog'

    def get_search_form(self):
        """
        Fetches the search form data for the specified species, including breed listings.
        """
        url = f"{self.base_url}search_form"
        params = {
            'v': self.api_version,
            'key': self.key,
            'output': self.output_format,
            'species': self.species
        }
        headers = {
            'Accept': 'application/json'
        }

        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()
    
    def get_breed_id(self, breed_str):
        search_form = self.get_search_form()
        breed_id_dict = search_form["breed_id"]

        for breed in breed_id_dict:
            if breed["label"] == breed_str:
                return breed["value"]

        return '-1'
    
    def get_adoption_listings(self, city_or_zip, breed_str="", geo_range="50", sex="", age=""):
        """
        Searches for pets based on provided criteria and returns a list of pets.
        """
        url = f"{self.base_url}pet_search"
        breed_id = self.get_breed_id(breed_str)
        
        params = {
            'v': self.api_version,
            'key': self.key,
            'output': self.output_format,
            'city_or_zip': city_or_zip,
            'geo_range': geo_range,
            'species': self.species,
            'breed_id': breed_id,
            'sex': sex,
            'age': age,
        }
        headers = {
            'Accept': 'application/json; charset=UTF8'
        }

        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            return response.json().get("pets")
        else:
            response.raise_for_status()
    
    def get_processed_adoption_listings(self, city_or_zip, breed_str="", geo_range="50", sex="", age=""):
        """
        Processes the JSON API response into a list of dictionaries.
        """
        processed_adoption_listings = []
        dogs = self.get_adoption_listings(city_or_zip, breed_str, geo_range, sex, age)
        print(dogs)
        
        for dog in dogs:
            pet_info = {
                "pet_id": dog.get("pet_id"),
                "pet_name": dog.get("pet_name"),
                "age": dog.get("age"),
                "sex": dog.get("sex"),
                "size": dog.get("size"),
                "primary_breed": dog.get("primary_breed"),
                "secondary_breed": dog.get("secondary_breed"),
                "location": f"{dog.get('addr_city', '')}, {dog.get('addr_state_code', '')}",
                "large_results_photo_url": dog.get("large_results_photo_url"),
            }
            processed_adoption_listings.append(pet_info)

        return processed_adoption_listings
    
    def get_adoption_listing_details(self, pet_id):
        url = f"{self.base_url}limited_pet_details"

        params = {
            'v': self.api_version,
            'key': self.key,
            'output': self.output_format,
            'pet_id': pet_id,
        }
        headers = {
            'Accept': 'application/json; charset=UTF8'
        }

        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            pet = response.json()["pet"]
            return json.dumps(pet)
        else:
            response.raise_for_status()


adoption_search_client = AdoptionSearch()

# Define path to the prompts
current_dir = os.path.dirname(os.path.realpath(__file__))
prompt_dir = os.path.join(current_dir, "prompts")

# Define Knowledge Base
suql_knowledge = SUQLKnowledgeBase(
    llm_model_name="together_ai/meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo", 
    tables_with_primary_keys={"dog_breeds": "name"},
    database_name="postgres",
    embedding_server_address="http://127.0.0.1:8509",
    source_file_mapping={
        "dog_adoption_general_info.txt": os.path.join(current_dir, "dog_adoption_general_info.txt")
    },
    db_host="127.0.0.1", # database host
    db_port="5433", # database port
    postprocessing_fn=postprocess_suql,
    result_postprocessing_fn=None,
    #api_base="https://ovaloairesourceworksheet.openai.azure.com/",
    api_version="2024-08-01-preview",
)

# Define the SUQL React Parser
suql_react_parser = SUQLReActParser(
    llm_model_name="llama-3.1-70b-instruct",
    example_path=os.path.join(current_dir, "examples.txt"),
    instruction_path=os.path.join(current_dir, "instructions.txt"),
    table_schema_path=os.path.join(current_dir, "table_schema.txt"),
    knowledge=suql_knowledge,
)

# Define the agent
dog_adoption_bot = Agent(
    botname="Dog Adoption Assistant",
    description="You are a dog adoption assistant. You can help future dog owners with deciding a dog breed suited to their needs and finding nearby adoption postings",
    prompt_dir=prompt_dir,
    starting_prompt="""Hello! I'm the Dog Adoption Assistant. I can help you with :
    - Finding a suitable dog breed with your preferred characteristics (e.g. low shedding)
    - Searching for dog adoption listings nearby. 
    - Asking me any question related to a specific dog breed.

    How can I help you today? 
    """,
    args={"model": model_config},
    api=[adoption_search_client.get_processed_adoption_listings],
    knowledge_base=suql_knowledge,
    knowledge_parser=suql_react_parser,
).load_from_gsheet(
    gsheet_id="12fiyfwVRN5IHh_qIZnN7FfonB4lzkBvhUtedXzdur0k",
)

# Run the conversation loop
if __name__ == "__main__":
    asyncio.run(conversation_loop(dog_adoption_bot, "dog_adoption_bot.json"))
