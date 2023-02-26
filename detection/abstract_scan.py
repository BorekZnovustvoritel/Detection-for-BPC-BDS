from __future__ import annotations

from abc import ABC, abstractmethod
from functools import total_ordering
from math import sqrt
from typing import List

from detection.definitions import thorough_scan
from detection.thresholds import skip_attr_list_threshold


@total_ordering
class Report:
    """Pairwise comparison result. Used as Model from the M-V-C architecture."""

    def __init__(
        self, probability: int, weight: int, first: ComparableEntity, second: ComparableEntity
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
            report.child_reports.extend(self.child_reports + other.child_reports)
        else:
            report.child_reports.extend(self.child_reports)
            report.child_reports.append(other)
        return report


class ComparableEntity(ABC):
    """Abstract object class for all the comparable parts of projects."""

    def __init__(self):
        self.name: str = ""

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.__dict__}>"

    @abstractmethod
    def compare(self, other: ComparableEntity) -> Report:
        """Compare two objects of the same class inherited from `JavaEntity`. Produces `Report` object."""
        pass

    def compare_parts(self, other: ComparableEntity, attr: str) -> Report:
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
            if not thorough_scan and (
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
                    self_val.compare(other_val) for other_val in other_attr_val
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
            report += self_attr_val.compare(other_attr_val)
        else:
            raise ValueError(
                f"Cannot compare attribute '{attr}' of instance of '{type(self)}'!"
            )
        return report


class NotFound(ComparableEntity):
    """Indicate that some part of the projects could not be matched to anything."""

    def compare(self, other: ComparableEntity) -> Report:
        return Report(0, 10, self, other)

    def __init__(self):
        super().__init__()
        self.name: str = "NOT FOUND"
