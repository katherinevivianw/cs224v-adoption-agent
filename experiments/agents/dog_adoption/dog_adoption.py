import asyncio
import os
import random
from uuid import uuid4
import requests

from suql.agent import postprocess_suql

from worksheets.agent import Agent
from worksheets.environment import get_genie_fields_from_ws
from worksheets.interface_utils import conversation_loop
from worksheets.knowledge import SUQLKnowledgeBase, SUQLParser, SUQLReActParser

# Define your APIs
class AdoptionSearch:
    def __init__(self):
        self.base_url = 'https://api-staging.adoptapet.com/search/'
        self.key = 'hg4nsv85lppeoqqixy3tnlt3k8lj6o0c'
        self.api_version = '2'
        self.output_format = 'json'
        self.species = 'dog'

    def get_search_form(self):
        """
        Fetches the search form data for the specified species, including breed listings.
        """
        url = f"{self.base_url}search_form"
        params = {
            'v': self.api_version,
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
    
    def get_breed_id(breed_str):
        pass
    
    def get_adoption_listings(self, city_or_zip, geo_range, breed_str="", sex="", age=""):
        """
        Searches for pets based on provided criteria and returns a list of pets.
        """
        url = f"{self.base_url}pet_search"
        breed_id = get_breed_id(breed_str)
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
            return response.json()
        else:
            response.raise_for_status()
    
    def format_adoption_listings(self, city_or_zip, geo_range, breed_id="", sex="", age=""):
        """
        Processes the JSON API response into a list of dictionaries.
        """
        processed_adoption_listings = []
        dogs = self.get_adoption_listings(city_or_zip, geo_range, breed_id, sex, age)
        
        for dog in dogs:
            pet_info = {
                "pet_id": dog.get("pet_id"),
                "pet_name": dog.get("pet_name"),
                "age": dog.get("age"),
                "sex": dog.get("sex"),
                "size": dog.get("size"),
                "primary_breed": dog.get("primary_breed"),
                #"secondary_breed": dog.get("secondary_breed"),
                "location": f"{dog.get('addr_city', '')}, {dog.get('addr_state_code', '')}",
                #"details_url": dog.get("details_url"),
                #"photo_url": dog.get("results_photo_url"),
                #"large_photo_url": dog.get("large_results_photo_url"),
            }
            processed_adoption_listings.append(pet_info)

        return processed_adoption_listings

adoption_search_client = AdoptionSearch()

# Define path to the prompts

current_dir = os.path.dirname(os.path.realpath(__file__))
prompt_dir = os.path.join(current_dir, "prompts")

# Define Knowledge Base
suql_knowledge = SUQLKnowledgeBase(
    llm_model_name="azure/gpt-4o",
    tables_with_primary_keys={"dog_breeds": "Name"},
    database_name="dog_breeds",
    embedding_server_address="http://127.0.0.1:8509",
    source_file_mapping={
        "dog_adoption_general_info.txt": os.path.join(current_dir, "dog_adoption_general_info.txt")
    },
    postprocessing_fn=postprocess_suql,
    result_postprocessing_fn=None,
    api_base="https://ovaloairesourceworksheet.openai.azure.com/",
    api_version="2024-08-01-preview",
)

# Define the SUQL React Parser
suql_react_parser = SUQLReActParser(
    llm_model_name="gpt-4o",
    example_path=os.path.join(current_dir, "examples.txt"),
    instruction_path=os.path.join(current_dir, "instructions.txt"),
    table_schema_path=os.path.join(current_dir, "table_schema.txt"),
    knowledge=suql_knowledge,
)

# Define the agent
dog_adoption_bot = Agent(
    botname="Dog Adoption Assistant",
    description="You are a dog adoptionassistant. You can help future dog owners with deciding a dog breed suited to their needs and finding nearby adoption postings",
    prompt_dir=prompt_dir,
    starting_prompt="""Hello! I'm the Dog Adoption Assistant. I can help you with :
- Finding a suitable dog breed: just say find me dog breeds
- Searching for dog adoption listings nearby. 
- Asking me any question related to dog breeds and adopting a new dog.

How can I help you today? 
""",
    args={},
    api=[adoption_search_client.get_adoption_listings, adoption_search_client.get_pet_details],
    knowledge_base=suql_knowledge,
    knowledge_parser=suql_react_parser,
).load_from_gsheet(
    gsheet_id="12fiyfwVRN5IHh_qIZnN7FfonB4lzkBvhUtedXzdur0k", # TODO
)

# Define the SUQL React Parser
suql_react_parser = SUQLReActParser(
    llm_model_name="gpt-4o",
    example_path=os.path.join(current_dir, "examples.txt"),
    instruction_path=os.path.join(current_dir, "instructions.txt"),
    table_schema_path=os.path.join(current_dir, "table_schema.txt"),
    knowledge=suql_knowledge,
)

# Run the conversation loop
asyncio.run(conversation_loop(dog_adoption_bot, "dog_adoption_bot.json"))
