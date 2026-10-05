from fastapi import Depends
from .process_case_graph import FlowGraphQuery,load


def register(app,csrf):
 @app.post('/api/sources/{source_id}/secretary/flow-graph')
 def meeting_flow_graph(source_id:str,body:FlowGraphQuery,value=Depends(csrf)):
  from .production_app import _source_store_response
  return _source_store_response(source_id,lambda con,scope:load(con,scope,body),value[2])
