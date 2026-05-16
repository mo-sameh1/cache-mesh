import time
from shared.faults import FAULTS


class FaultService:

    @staticmethod
    def apply_faults():
        """
        Simulates distributed system failures.
        """

        if FAULTS["drop_heartbeat"]:
            return {
                "fault": "heartbeat dropped"
            }

        if FAULTS["pause_replica"]:
            time.sleep(10)

        if FAULTS["delay_seconds"] > 0:
            time.sleep(FAULTS["delay_seconds"])

        return {
            "fault": "none"
        }