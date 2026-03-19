"""
QualityIssue entity - maps to a row in tbDataQualityLog.
"""
from dataclasses import dataclass


@dataclass
class QualityIssue:
    entity_name: str      # table name
    field_name: str       # column name
    record_key: str       # row identifier hint
    rule_name: str        # check name
    old_value: str        # problematic value
    new_value: str = ""
    severity: str = "WARNING"     # INFO | WARNING | ERROR
    check_type: str = ""          # null_check | type_check | range_check | format_check | duplicate_check
    description: str = ""
