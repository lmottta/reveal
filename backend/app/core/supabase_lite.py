import os
from postgrest import SyncRequestBuilder

class SupabaseLiteClient:
    def __init__(self, url: str, key: str):
        self.rest_url = f"{url}/rest/v1"
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        self.key = key

    def table(self, table_name: str):
        # Postgrest-py usage:
        # builder = SyncRequestBuilder(url, headers=headers)
        # return builder.table(table_name) -> returns SyncQueryBuilder
        # But wait, postgrest-py usually works like:
        # client = PostgrestClient(url, headers=headers)
        # client.from_(table_name)...
        
        # Let's check installed version usage.
        # Assuming postgrest-py 0.10+
        return SyncRequestBuilder(self.rest_url, headers=self.headers).path(f"/{table_name}")

    def rpc(self, func_name: str, params: dict):
        return SyncRequestBuilder(self.rest_url, headers=self.headers).rpc(func_name, params)

def create_client(url: str, key: str):
    return SupabaseLiteClient(url, key)
