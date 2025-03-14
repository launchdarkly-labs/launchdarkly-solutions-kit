import chromadb
import json
import logging
from chromadb.config import Settings
from typing import List, Dict, Any
from tqdm import tqdm  
import os

class LaunchDarklyPolicySimilarityService:
    """
    Service for analyzing similarities between LaunchDarkly custom role policies.
    
    This service converts policies to human-readable text representations and uses
    semantic embeddings to find similar policies. It provides methods for:
    - Adding custom roles to the analysis collection
    - Finding similar policies based on semantic similarity
    - Converting policies to readable text
    
    The service uses ChromaDB for storing and querying embeddings, with options
    for persistent storage and force refresh of the collection.
    
    Attributes:
        logger: Logger instance for this class
        client: ChromaDB client (persistent or in-memory)
        collection: ChromaDB collection for storing policy embeddings
        output_file: Path to save policy similarity results
        embedding_func: Function for generating embeddings
    """
    def __init__(self, embedding_func, collection_name:str="launchdarkly_policies", force:bool=False, persist:bool=False, path:str="./data", output_file:str="policies.json"):
        """
        Initialize the policy similarity service with sentence transformer
        
        This service analyzes LaunchDarkly custom role policies to find similarities
        between them using semantic embeddings. It converts policy statements to
        human-readable sentences and uses vector similarity to identify similar policies.
        
        Args:
            embedding_func: Sentence transformer embedding function
            collection_name (str): Name of the ChromaDB collection (default: "launchdarkly_policies")
            force (bool): Whether to force recreate the collection (default: False)
            persist (bool): Whether to use persistent storage (default: False)
            path (str): Path to store persistent embeddings (default: "./data")
            output_file (str): Path to save policy similarity results (default: "policies.json")
        """
        self.logger = logging.getLogger(__name__)
        
        # Only set anonymized_telemetry in ChromaDB settings
        chroma_settings = Settings(
            anonymized_telemetry=False
        )
        self.output_file = output_file
      
        if persist:
            self.logger.debug(f"Using persistent client at {path}")
            self.client = chromadb.PersistentClient(path=path, settings=chroma_settings)
        else:
            self.logger.debug("Using in-memory client")
            self.client = chromadb.Client(settings=chroma_settings)
        
        self.embedding_function = embedding_func
        self.collection_name = collection_name
        
        if force:
            try:
                self.logger.info(f"Deleting collection {self.collection_name}")
                self.client.delete_collection(name=self.collection_name)
            except Exception as e:
                self.logger.debug(f"Error deleting collection: {e}")
                pass

        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_function
        )
        self.logger.debug(f"Initialized collection: {self.collection}")

   

    def policy_to_sentences(self, policy: List[Dict[str, Any]]) -> str:
        """
        Convert a complete policy (list of statements) to readable text
        
        Transforms a LaunchDarkly policy (consisting of multiple statements) into
        a human-readable text representation that can be embedded for similarity analysis.
        Each statement is converted to a sentence and joined with a separator.
        
        Args:
            policy (List[Dict]): List of policy statements
            
        Returns:
            str: Human readable description of the entire policy with statements
                 separated by "| NEXT STATEMENT |"
        """
        statement_sentences = []
        self.logger.debug(f"policy_to_sentences() policy={policy}")
        for statement in policy:
            sentence = f"{self.statement_to_sentence(statement)}."
            
            statement_sentences.append(sentence)
        
        # print(f"policy_to_sentences()statement_sentences: {statement_sentences}")
        return "| NEXT STATEMENT | ".join(statement_sentences)
    def _format_actions(self, actions_list:List[str], is_not_actions:bool=False) -> str:
        message =""

        if "*" in actions_list:
            return  "all action"  
        
        if is_not_actions:
            message= f"any action except these actions {', '.join(sorted(actions_list))}"
        else:
            message = f"only these actions {', '.join(sorted(actions_list))}"

        # print(f"_format_actions() is_not_actions={is_not_actions} message: {message}")
        return message

 
        
    def _format_resources(self, resources_list: List[str], is_not_resources: bool = False) -> str:
        
        resource_sentences = {}

        for resource in resources_list:
            
            resource_parts = resource.split(":")
            if len(resource_parts) > 1 and 'proj/' in resource_parts[0] and 'env/' in resource_parts[1]:
                if '{critical' in resource_parts[1]:
                    if len(resource_parts) > 2:
                        resource_parts[1] = resource_parts[1] + ':' + resource_parts[2]
                        resource_parts.pop(2)

            
            resource_group = {}
            for part in resource_parts:
            
                if part in ["acct"]:
                    resource_type = "acct"
                    resource_name = "*"
                else:
                    resource_type, resource_name = part.split("/", 1)
                
                resource_group[resource_type] = [] if resource_type not in resource_group else resource_group[resource_type]
                resource_group[resource_type].append(resource_name)
        
            for resource_type, resource_names in resource_group.items():

                if ";" in resource_names[0]:
                    resource_name, resource_tag = resource_names[0].split(';')
                else:
                    resource_name = resource_names[0]
                    resource_tag = None

                if resource_type not in resource_sentences:
                    resource_id = {
                        "proj": "project",
                        "env": "environment",
                        "acct": "account"
                    }.get(resource_type, resource_type)

                    
                    # print(f"resource_type={resource_type} resource_name={resource_name} resource_tag={resource_tag}")
                    if "*" in resource_name:
                        if resource_type == "env" and resource_tag is not None and 'critical' in resource_tag:
                            critical_value = resource_tag.split(':')[1].lower()
                            critical_bool = "true" in critical_value
                            critical_TF = "critical" if critical_bool else "non-critical"
                            resource_sentences[resource_type] = f"all {critical_TF} {resource_id}s"

                        elif len(resource_name) == 1:
                            resource_sentences[resource_type] = f"all {resource_id}s"
                        else:
                            resource_sentences[resource_type] = f"only these {resource_id}s {resource_name}"
                    else:
                        if is_not_resources and resource_type == "env":
                            resource_sentences[resource_type] = f"all {resource_id}s except {resource_name}"
                        else:
                            resource_sentences[resource_type] = f"only these {resource_id}s {resource_name}"
                elif "any" not in resource_sentences[resource_type]:
                    resource_sentences[resource_type] += f", {resource_name}"

                if resource_tag is not None and resource_type != "env":
                    resource_sentences[resource_type] += f" with tags {resource_tag}"
        # Build final message with appropriate prepositions
        message = ""
        for resource_type, resource_sentence in resource_sentences.items():
            
            if resource_type in ["proj", "env", "code-reference-repository"]:
                message += " in"
            elif resource_type in ["flag", "member", "service-token", "team", "pending-request",
                                    "application", "domain-verification", 
                                    "integration", "relay-proxy-config", "webhook"]:
                message += " for"
            else:
                message += " with"
            message += f" {resource_sentence}"
        
            # print(f"_format_resources() message: {message}, resource_type: {resource_type}, resource_sentence: {resource_sentence}")
        return message.strip()


    def statement_to_sentence(self, statement: Dict[str, Any]) -> str:
    
        try:
            # print (f"statement_to_sentence() statement: {statement}")
            parts = {}
            parts["effect"] = statement.get("effect", "").lower() if "effect" in statement else None
            
            parts["actions"] = self._format_actions(statement.get("actions", []), is_not_actions=False) if "actions" in statement else None

            parts["notActions"] = self._format_actions(statement.get("notActions", []), is_not_actions=True) if "notActions" in statement else None

            parts["resources"] = self._format_resources(statement.get("resources", []), is_not_resources=False) if "resources" in statement else None
            parts["notResources"] = self._format_resources(statement.get("notResources", []), is_not_resources=True) if "notResources" in statement else None

            # print(f"parts: {parts}")

            actions_sentence = parts['actions'] if parts['actions'] else parts['notActions'] 
            resources_sentence = parts['resources'] if parts['resources'] else parts['notResources']
            sentence = f"{parts['effect']} {actions_sentence} {resources_sentence}"
        except Exception as e:
            self.logger.error(f"statement_to_sentence() statement: {statement}")
            self.logger.error(f"Error converting statement to sentence: {e}")
            sentence = ""
        
        return sentence

    

    def delete_collection(self):
        """
        Delete the current collection
        
        Removes the ChromaDB collection containing policy embeddings.
        Useful when needing to rebuild the collection from scratch.
        """
        self.client.delete_collection(self.collection_name)

    def add_custom_role(self, role: Dict[str, Any]) -> None:
        """
        Add a custom role to the collection
        
        Processes a LaunchDarkly custom role, extracts its policy, converts it to
        a sentence representation, and adds it to the ChromaDB collection with metadata.
        
        Args:
            role (Dict): Custom role object from LaunchDarkly API containing:
                - key: Role identifier
                - name: Role name
                - description: Role description
                - policy: List of policy statements
        """
        self.logger.debug(f"add_custom_role() role: start")
        policy = role['policy']
        policy_id = role['key']
        policy_name = role['name']
        policy_description = role['description']
        sentence = self.policy_to_sentences(policy)
        self.logger.debug(f"Adding role {policy_id}: {sentence}")
        
        
        
        metadata = {
            "policy_id": policy_id,
            "policy_key": role['key'],
            "policy_name": policy_name,
            "policy_description": policy_description,
            "sentence": sentence,
            "policy": json.dumps(policy),
            "statement_count": len(policy),
            "total_resources": sum(len(stmt.get("resources", [])) for stmt in policy),
            "total_not_resources": sum(len(stmt.get("notResources", [])) for stmt in policy),
            "total_actions": sum(len(stmt.get("actions", [])) for stmt in policy),
            "total_not_actions": sum(len(stmt.get("notActions", [])) for stmt in policy),
            "has_role_attributes": any("${roleAttribute" in r for stmt in policy for r in stmt.get("resources", [])),
            "total_teams_assigned": role['total_teams'],
            "total_members_assigned": role['total_members'],
            "teams_assigned":  ",".join([f"{m}" for m in role['teams']]),
            "members_assigned": ",".join([f"{m}" for m in role['members']]),
            "is_assigned": role['is_assigned']
        }
        # Add to collection if it doesn't exist, otherwise update
        self.collection.upsert(
            documents=[sentence],
            metadatas=[metadata],
            ids=[policy_id]
        )

        self.logger.debug(f"add_custom_role() role: end")

    def _calculate_similarity_score(self, distance: float) -> float:
        """
        Calculate similarity score from distance metric.
        
        Converts ChromaDB's distance metric (0-2 range) to a similarity score (0-1 range).
        
        The division by 2 is necessary, the distance metric ranges from 0 to 2,
        we want to normalize it to a 0-1 range before subtracting from 1 to convert 
        from a distance to a similarity score.

        A distance of 0 becomes similarity of 1.0 (100% similar)
        A distance of 2 becomes similarity of 0.0 (0% similar) 
        A distance of 1 becomes similarity of 0.5 (50% similar)

        Args:
            distance (float): Distance metric from ChromaDB (0-2 range)
            
        Returns:
            float: Similarity score (0-1 range)
        """
        return 1 - (distance / 2)
    
    def _parse_policy_data(self, results: Dict[str, Any], idx: int, similarity: float) -> Dict[str, Any]:
        """
        Create a policy data dictionary from query results for a given index.
        
        Formats ChromaDB query results into a structured dictionary containing
        policy data and metadata for easier consumption by the report generator.
        
        Args:
            results (Dict[str, Any]): Query results from ChromaDB
            idx (int): Index of the result to process
            similarity (float): Calculated similarity score
            
        Returns:
            Dict[str, Any]: Formatted policy data dictionary containing:
                - id: Policy identifier
                - policy: The policy JSON
                - policy_name: Name of the policy
                - policy_description: Description of the policy
                - similarity_score: Calculated similarity score
                - metadata: Additional metadata about the policy
        """
        return {
            'id': results['ids'][0][idx],
            'policy': results['metadatas'][0][idx]['policy'],
            'policy_name': results['metadatas'][0][idx]['policy_name'],
            'policy_description': results['metadatas'][0][idx]['policy_description'],
            'similarity_score': similarity,
            'metadata': {
                'policy_id': results['metadatas'][0][idx]['policy_id'],
                'policy_key': results['metadatas'][0][idx]['policy_key'],
                'policy_name': results['metadatas'][0][idx]['policy_name'],
                'policy_description': results['metadatas'][0][idx]['policy_description'],
                'sentence': results['metadatas'][0][idx]['sentence'],
                'statement_count': results['metadatas'][0][idx]['statement_count'],
                'total_resources': results['metadatas'][0][idx]['total_resources'],
                'total_not_resources': results['metadatas'][0][idx]['total_not_resources'],
                'total_actions': results['metadatas'][0][idx]['total_actions'],
                'total_not_actions': results['metadatas'][0][idx]['total_not_actions'],
                'has_role_attributes': results['metadatas'][0][idx]['has_role_attributes'],
                "total_teams_assigned": results['metadatas'][0][idx]['total_teams_assigned'],
                "total_members_assigned": results['metadatas'][0][idx]['total_members_assigned'],
                "teams_assigned": results['metadatas'][0][idx]['teams_assigned'],
                "members_assigned": results['metadatas'][0][idx]['members_assigned'],
                "is_assigned": results['metadatas'][0][idx]['is_assigned']
            }
        }
    
    def run_query(self, query_sentence: str, policy_id: str, n_results: int = 3, min_similarity: float = 0.5) -> List[Dict[str, Any]]:
        """
        Run a similarity query against the policy collection
        
        Queries the ChromaDB collection for policies similar to the provided query sentence,
        excluding the policy with the given ID from results.
        
        Args:
            query_sentence (str): The sentence representation of the policy to query
            policy_id (str): ID of the policy to exclude from results
            n_results (int): Maximum number of results to return (default: 3)
            min_similarity (float): Minimum similarity threshold (default: 0.5)
            
        Returns:
            List[Dict[str, Any]]: List of similar policies with metadata and similarity scores
        """
        results = self.collection.query(
            query_texts=[query_sentence]
            ,where={'policy_id': {'$ne': policy_id }}
            ,n_results=n_results
        )   
        policies=[]
        for idx, distance in enumerate(results['distances'][0]):
            similarity = self._calculate_similarity_score(distance)
            
            if similarity >= min_similarity:
                policy_data = self._parse_policy_data(results, idx, similarity)
                policies.append(policy_data)

    
        
        return policies
    
    def run_query_standalone(self, query_policy: List[Dict[str, Any]], n_results: int = 3, min_similarity: float = 0.5) -> List[Dict[str, Any]]:
        self.logger.info(f"Running query: [{query_policy}]")
        self.logger.info(f"N results: [{n_results}]")
        self.logger.info(f"Min similarity: [{min_similarity}]")
        self.logger.warning("Running query in standalone mode.")

        query_sentence = self.policy_to_sentences(query_policy)

        results = self.collection.query(
            query_texts=[query_sentence],
            n_results=n_results
        )
          
        policies=[]
        for idx, distance in enumerate(results['distances'][0]):
            similarity = self._calculate_similarity_score(distance)
            
            if similarity >= min_similarity:
                policy_data = self._parse_policy_data(results, idx, similarity)
                policies.append({'name': policy_data['policy_name'],
                                 'key': policy_data['metadata']['policy_key'],
                                  'description': policy_data['policy_description'], 
                                  'similarity': similarity
                                  })

    
        
        return policies
    
    def find_similar_policies(
        self, 
        query_policy: List[Dict[str, Any]], 
        policy_id: str,
        n_results: int = 3,
        min_similarity: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Find similar policies to the query policy
        
        Converts a policy to a sentence representation and finds similar policies
        in the collection based on semantic similarity.
        
        Args:
            query_policy (List[Dict]): Policy to compare against
            policy_id (str): ID of the policy to exclude from results
            n_results (int): Maximum number of results to return (default: 3)
            min_similarity (float): Minimum similarity threshold (default: 0.5)
            
        Returns:
            List[Dict[str, Any]]: List of similar policies with metadata and similarity scores
        """
        query_sentence = self.policy_to_sentences(query_policy)
        self.logger.debug(f"Finding similar policies for {policy_id}: {query_sentence}")
        similar_policies = self.run_query(query_sentence, policy_id, n_results, min_similarity)
        self.logger.debug(f"Found {len(similar_policies)} similar policies")
        return similar_policies

    def update_collection(self, roles: List[Dict[str, Any]], desc: str = "Processing policies") -> None:
        """
        Process a list of roles with a progress bar
        
        Args:
            roles: List of custom role objects from LaunchDarkly
            desc: Description for the progress bar (default: "Processing policies")
        """
        for role in tqdm(roles, desc=desc):
            self.add_custom_role(role)
    
    def process_collection(self, data: Dict[str, Any], max_results: int = 3, min_similarity: float = 0.5) -> Dict[str, Any]:
        policies = {}
        self.logger.info(f"Finding similar policies... min_similarity={min_similarity}")
        for role in tqdm(data["roles"], desc="Analyzing similarities"):
            similar_policies = self.find_similar_policies(
                query_policy=role["policy"],
                policy_id=role["key"], 
                n_results=max_results,
                min_similarity=min_similarity
            )
            policies[role["key"]] = similar_policies

        # Check if all policies have empty similar_policies lists
        all_empty = all(len(similar) == 0 for similar in policies.values())
        if all_empty:
            self.logger.info("No matching similarities found between policies.")
            return 0
        else:
            self.logger.info(f"Found {len(policies)} policies with similarities")
    
        output_dir = os.path.dirname(self.output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            
        with open(self.output_file, "w") as f:
            json.dump(policies, f)  

        self.logger.info(f"Policies saved to {self.output_file}")

        return policies