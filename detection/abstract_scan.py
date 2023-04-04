from __future__ import annotations

from abc import ABC, abstractmethod
from functools import total_ordering
from math import sqrt
from typing import List, Dict, Type, Set

from detection.definitions import node_translation_dict
from detection.thresholds import skip_attr_list_threshold
from detection.utils import calculate_score_based_on_numbers


@total_ordering
class Report:
    """Pairwise comparison result. Creates a tree of bijective matches."""

    def __init__(
        self,
        probability: int,
        weight: int,
        first: ComparableEntity,
        second: ComparableEntity,
    ):
        self.probability: int = probability
        self.weight: int = weight
        self.first: ComparableEntity = first
        self.second: ComparableEntity = second
        self.child_reports: List[Report] = []

    def __lt__(self, other: Report):
        return (
            self.probability < other.probability
            if self.probability != other.probability
            else self.weight < other.weight
        )

    def __eq__(self, other: Report):
        return self.probability == other.probability and self.weight == other.weight

    def __repr__(self):
        return (
            f"< Report, probability: {self.probability}, comparing entities: {self.first.name}, "
            f"{self.second.name}, Child reports: {self.child_reports}>"
        )

    def __add__(self, other: Report):
        weight = self.weight + other.weight
        if weight == 0:
            weight = 1
        report = Report(
            (self.probability * self.weight + other.probability * other.weight)
            // weight,
            (self.weight + other.weight),
            self.first,
            self.second,
        )
        if isinstance(self.first, type(other.first)) or isinstance(
            self.second, type(other.second)
        ):
            report.child_reports.extend(self.child_reports)
            report.child_reports.extend(other.child_reports)
        else:
            report.child_reports.extend(self.child_reports)
            if other.first.visualise or other.second.visualise:
                report.child_reports.append(other)
        return report


class ComparableEntity(ABC):
    """Abstract object class for all the comparable parts of projects."""

    def __init__(self):
        self.name: str = ""
        self.visualise: bool = False

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.__dict__}>"

    @abstractmethod
    def compare(self, other: ComparableEntity, fast_scan: bool = False) -> Report:
        """Compare two objects of the same class inherited from `JavaEntity`. Produces `Report` object."""
        pass

    def compare_parts(
        self, other: ComparableEntity, attr: str, fast_scan: bool = False
    ) -> Report:
        """Helper method that compares comparable attributes of objects.
        This method is responsible for the hierarchical behavior of comparisons."""
        if not isinstance(other, type(self)):
            raise TypeError("Cannot compare different types of JavaEntity!")
        report = Report(0, 0, self, other)
        self_attr_val = getattr(self, attr, None)
        other_attr_val = getattr(other, attr, None)
        if self_attr_val is None:
            raise ValueError(
                f"Instance of '{type(self)}' does not have attribute '{attr}'!"
            )
        if isinstance(self_attr_val, List):
            if not self_attr_val or not other_attr_val:
                return Report(0, 0, self, other)
            if fast_scan and (
                1
                - sqrt(
                    abs(len(self_attr_val) - len(other_attr_val))
                    / (len(self_attr_val) + len(other_attr_val))
                )
                < skip_attr_list_threshold
            ):
                return Report(0, 10, self, other)
            matrix = []
            self_unused_vals = set(self_attr_val)
            other_unused_vals = set(other_attr_val)
            for self_val in self_attr_val:
                matrix.extend(
                    self_val.compare(other_val, fast_scan)
                    for other_val in other_attr_val
                )
            while matrix:
                max_report = max(matrix)
                self_unused_vals.remove(max_report.first)
                other_unused_vals.remove(max_report.second)
                matrix = list(
                    filter(
                        lambda x: False
                        if max_report.second == x.second or max_report.first == x.first
                        else True,
                        matrix,
                    )
                )
                report += max_report
            for unused in self_unused_vals:
                report += Report(0, 10, unused, NotFound())
            for unused in other_unused_vals:
                report += Report(0, 10, NotFound(), unused)
        elif isinstance(self_attr_val, ComparableEntity):
            report += self_attr_val.compare(other_attr_val, fast_scan)
        else:
            raise ValueError(
                f"Cannot compare attribute '{attr}' of instance of '{type(self)}'!"
            )
        return report


class AbstractProject(ComparableEntity, ABC):
    def __init__(self, project_type: str, template: bool):
        super().__init__()
        self.project_type = project_type
        self.is_template = template

    @abstractmethod
    def size(self) -> int:
        pass


class AbstractStatementBlock(ComparableEntity, ABC):
    def compare(self, other: AbstractStatementBlock, fast_scan: bool = False) -> Report:
        report = Report(0, 0, self, other)
        for node_type in self.parts:
            self_occurrences = self.parts[node_type]
            other_occurrences = other.parts.get(node_type, 0)
            if other_occurrences > 0:
                report += Report(
                    calculate_score_based_on_numbers(
                        self_occurrences, other_occurrences
                    ),
                    10,
                    self,
                    other,
                )
            else:
                backup_node_type = node_translation_dict.get(node_type, None)
                if backup_node_type is not None:
                    other_occurrences = other.parts.get(backup_node_type, 0)
                    if other_occurrences > 0:
                        report += Report(
                            calculate_score_based_on_numbers(
                                self_occurrences, other_occurrences
                            )
                            // 2,
                            10,
                            self,
                            other,
                        )
                else:
                    report += Report(0, 10, self, other)
        return report

    def __init__(self, statement, realm: Type):
        super().__init__()
        self.statement = statement
        self.realm = realm
        self.parts: Dict[Type, int] = self._tree_to_dict(statement)

    def _tree_to_dict(self, node) -> dict[Type, int]:
        ans: Dict[Type, int] = {}
        node_type = type(node)
        if node_type in ans.keys():
            ans.update({node_type: ans.get(node_type) + 1})
        else:
            ans.update({node_type: 1})
        for attribute in [a for a in dir(node) if not a.startswith("_")]:
            child = getattr(node, attribute, None)
            if not isinstance(child, self.realm):
                continue
            child_dict = self._tree_to_dict(child)
            for key in child_dict:
                if key in ans.keys():
                    ans.update({key: ans[key] + child_dict[key]})
                else:
                    ans.update({key: child_dict[key]})
        return ans

    def _search_for_types(self, statement, block_types: Set[Type]) -> Dict[Type, List]:
        """Go through AST and fetch subtrees rooted in specified node types.
        Parameter `statement` represents AST, `block_types` is set of searched node types.
        Returns dictionary structured as so: `{NodeType1: [subtree1, subtree2, ...], NodeType2: [...]}`"""
        ans = {}
        if not isinstance(statement, self.realm):
            return ans
        node_type = type(statement)
        if node_type in block_types:
            if node_type in ans.keys():
                ans.update(
                    {
                        node_type: ans[node_type]
                        + [
                            statement,
                        ]
                    }
                )
            else:
                ans.update(
                    {
                        node_type: [
                            statement,
                        ]
                    }
                )
        for attribute in getattr(statement, "attrs", []):
            child = getattr(statement, attribute, None)
            if isinstance(child, self.realm):
                dict_to_add = self._search_for_types(child, block_types)
                for key in dict_to_add:
                    if key in ans.keys():
                        ans.update({key: ans[key] + dict_to_add[key]})
                    else:
                        ans.update({key: dict_to_add[key]})
        return ans


class NotFound(ComparableEntity):
    """Indicate that some part of the projects could not be matched to anything."""

    def compare(self, other: ComparableEntity, fast_scan: bool = False) -> Report:
        return Report(0, 10, self, other)

    def __init__(self):
        super().__init__()
        self.name: str = "NOT FOUND"
