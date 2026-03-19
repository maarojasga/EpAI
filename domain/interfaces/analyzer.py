"""
Interface for telemetry analysis modules.
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from domain.entities.observation import Observation
from domain.entities.alert import Alert


class IAnalyzer(ABC):
    @abstractmethod
    def analyze(self, observation: Observation) -> List[Alert]:
        """
        Processes a single observation and returns a list of detected alerts.
        """
        pass

    @abstractmethod
    def get_state(self, patient_id: str) -> dict:
        """
        Returns the current state of the analyzer for a specific patient.
        """
        pass
