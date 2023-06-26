#This script is a work in progress to eventually feed into an AWS lambda integration that responds to transgene plasmid registration. Once receiving the event, 
#the script auto-annotates from a Regex feature library, then uses the start and end position of the Regex annotation to define the index of a recombinant viral 
#payload to create and register. After registering the RVP, the script autofills parts on the sequence.


import json
import os
import random 
import string
import json
import time

from dataclasses import dataclass, field
from typing import Any, Dict
from dataclasses_json import config
import benchling_sdk.models as Models
import benchling_api_client.api as api
from benchling_sdk.benchling import Benchling
from benchling_sdk.auth.client_credentials_oauth2 import ClientCredentialsOAuth2
from benchling_sdk.helpers.serialization_helpers import fields
from benchling_api_client.models.naming_strategy import NamingStrategy
from benchling_api_client.benchling_client import BenchlingApiClient
from benchling_sdk.errors import BenchlingError

##### DEFINE App Access
app_client_id = os.environ.get('APP_CLIENT_ID')
app_client_secret = os.environ.get('APP_CLIENT_SECRET')
tenant_url = os.environ.get('TENANT_URL')

def lambda_handler(event, context=''):
    auth_method = ClientCredentialsOAuth2(
            client_id=app_client_id,
            client_secret=app_client_secret,
            token_url=tenant_url+"/api/v2/token"
            )

    benchling = Benchling(url=tenant_url, auth_method=auth_method)

    ## DEFINE VARIABLES
    #get feature library id
    lib_list = benchling.feature_libraries.list(name_includes = 'Regex')
    for page in lib_list:
        for lib in page:
            feature_lib_id = lib.id

    
    plasmid_folder = event["detail"]["entity"]["folderId"] 
    plasmid_name = event["detail"]["entity"]["name"]
    project_id = (benchling.folders.get_by_id(plasmid_folder)).project_id

    reg_id = event["detail"]["entity"]["registryId"] 
    sequence_id = event["detail"]["entity"]["id"] 
    plasmid_schema_id = event["detail"]["entity"]["schema"]["id"]
    get_RVP_folder = (benchling.folders.list(name_includes = 'RVPs'))
    for page in get_RVP_folder:
        for folder in page:
            RVP_folder = folder.id
    RVP_schema_id = os.environ.get('RVP_SCHEMA_ID')

   

# ANNOTATE PLASMID
    def auto_annotate_RVP(benchling, sequence_id, feature_lib_id):   
        payload = Models.AutoAnnotateDnaSequences(
            dna_sequence_ids = [sequence_id],
            feature_library_ids = [feature_lib_id]
        )
        auto_ann = benchling.dna_sequences.auto_annotate(payload)
        task_id = auto_ann.task_id
        completed_task = benchling.tasks.wait_for_task(task_id)
        print("Ann Status: ", completed_task.status)
        completed_task = benchling.tasks.wait_for_task(task_id)
    auto_annotate_RVP(benchling, sequence_id, feature_lib_id)

    def getNewSequenceAndCreatePart(benchling, sequence_id):

        sequence_info = benchling.dna_sequences.get_by_id(sequence_id)
        ann_list = sequence_info.annotations
        str_ann = []
        for i in range(len(ann_list)):
            str_ann.append(str(ann_list[i]))
        find_regex = [s for s in str_ann if 'Regex' in s]
        
        attributes_list = str(find_regex).split(",") #.DnaAnnotation.start
       
        

        rvp_start = int(attributes_list[4][7:])
        rvp_end = int(attributes_list[1][5:])
        RVP_bases = sequence_info.bases[rvp_start:rvp_end]
        
        RVP_name = sequence_info.name + " RVP"
        
        
       # Structure RVP to create
        RVP_to_create = Models.DnaSequenceCreate(
                folder_id = RVP_folder,
                schema_id = RVP_schema_id,
                bases = RVP_bases,
                is_circular = False,
                registry_id = reg_id,
                naming_strategy = NamingStrategy.NEW_IDS,
                name = RVP_name)
      
        print("New RVP Name: " + RVP_name)
    
        create_RVP = benchling.dna_sequences.create(RVP_to_create)
        
    getNewSequenceAndCreatePart(benchling, sequence_id)

    def autofillParts(benchling, sequence_id):
        seq_ids = [sequence_id]
        n = 1
        maximum_delay = 20
        task_id = ''
        while len(task_id) < 5:
            try:
                autofill_RVP = benchling.dna_sequences.autofill_parts(seq_ids)
                task_id = autofill_RVP.task_id
                
            except BenchlingError:
                constant_factor = random.uniform(0, 1)
                delay_time = 2 ** n + constant_factor

                if delay_time > maximum_delay:
                    delay_time = maximum_delay

                time.sleep(delay_time)
                n += 1
       
        print("Autofill Parts Task ID: ", task_id)
       
        completed_task = benchling.tasks.wait_for_task(task_id)
        print("Autofill Parts Status: ", completed_task.status)
       

    autofillParts(benchling, sequence_id)
    return({"status": "20X", "message":"SUCCESS"})
