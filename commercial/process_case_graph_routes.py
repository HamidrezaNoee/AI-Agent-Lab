from fastapi import Depends
from .process_case_graph import FlowGraphQuery,FlowSnapshotQuery,load,snapshot


def register(app,csrf):
 @app.post('/api/sources/{source_id}/secretary/flow-graph')
 def meeting_flow_graph(source_id:str,body:FlowGraphQuery,value=Depends(csrf)):
  from .production_app import _source_store_response
  return _source_store_response(source_id,lambda con,scope:load(con,scope,body),value[2])

 @app.post('/api/sources/{source_id}/secretary/flow-graph/{case_uid}/snapshot')
 def meeting_flow_snapshot(source_id:str,case_uid:str,body:FlowSnapshotQuery,value=Depends(csrf)):
  from .production_app import _source_store_response
  return _source_store_response(source_id,lambda con,scope:snapshot(con,scope,case_uid,body),value[2])
