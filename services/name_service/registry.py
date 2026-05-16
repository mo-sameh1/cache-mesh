import time
from shared.clock import LamportClock

class MembershipRegistry:
    def __init__(self):
        self.members={}
        self.clock=LamportClock()
        self.suspect_timeout=10
        self.unhealthy_timeout=20

    def register(self,payload):
        rid=payload["replica_id"]
        self.members[rid]={
            "replica_id":rid,
            "host":payload["host"],
            "port":payload["port"],
            "status":"healthy",
            "last_heartbeat":time.time(),
            "lamport":self.clock.tick()
        }
        return {"registered":True,"member":self.members[rid]}

    def heartbeat(self,payload):
        rid=payload["replica_id"]
        if rid in self.members:
            self.members[rid]["last_heartbeat"]=time.time()
            self.members[rid]["status"]="healthy"
            self.members[rid]["lamport"]=self.clock.tick()
        return {"accepted": rid in self.members}

    def _refresh(self):
        now=time.time()
        for m in self.members.values():
            diff=now-m["last_heartbeat"]
            if diff>self.unhealthy_timeout:
                m["status"]="unhealthy"
            elif diff>self.suspect_timeout:
                m["status"]="suspect"
            else:
                m["status"]="healthy"

    def members_list(self):
        self._refresh()
        return list(self.members.values())

    def healthy_members(self):
        self._refresh()
        return [m for m in self.members.values() if m["status"]=="healthy"]
