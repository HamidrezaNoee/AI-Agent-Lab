"""Bounded, sourced BI tool for one selected non-ProcessMaker BPMS adapter."""
from datetime import datetime,timezone

from . import bpms_registry


class BPMSBITools:
    def __init__(self,source_id):
        self.source_id=source_id
        self.meetings=[]
        self.complete=True
        self.modules={1,3}
        self.now=datetime.now(timezone.utc)
        self.evidence={}
        self.trace=[]

    def definitions(self):
        return [{"type":"function","name":"analyze_processes","strict":False,
                 "description":"Read the selected non-ProcessMaker BPMS through its AVAN v1 read-only adapter. Includes case counts, states, task delays and processes. Never infer business-form values. Dates use YYYY-MM-DD with exclusive end.",
                 "parameters":bpms_registry.BIFilter.model_json_schema()}]

    def execute(self,name,raw):
        if name!="analyze_processes":raise ValueError("Unsupported tool")
        filters=bpms_registry.BIFilter.model_validate(raw)
        args=bpms_registry.BIRequest(source_id=self.source_id,**filters.model_dump())
        result=bpms_registry.report(args)
        key="T:"+str(len(self.trace)+1)
        self.complete=self.complete and result["coverage_complete"]
        self.evidence[key]={"id":key,"title":"گزارش فرایندها · "+result["source_name"],
                            "result":result}
        self.trace.append({"tool":name,"source_id":key,
                           "filters":filters.model_dump(mode="json")})
        return {**result,"connector_id":result["source_id"],"source_id":key}
