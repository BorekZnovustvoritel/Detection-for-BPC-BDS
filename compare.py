from scan import Report, Project, JavaFile, JavaClass, JavaMethod, JavaVariable, JavaType
from definitions import threshold


types_to_compare = {Project, JavaFile, JavaClass, JavaMethod, JavaVariable}


def print_path(report: Report, indent: int = 0) -> str:
    if type(report.first) not in types_to_compare or type(report.second) not in types_to_compare:
        return ""
    string = f"{indent * '|     '}\\ Type: {type(report.first).__name__}, " \
             f"names: {report.first.name}, {report.second.name}, score: {report.probability}\n"
    if report.probability > threshold:
        for child_report in report.child_reports:
            string += print_path(child_report, indent + 1)
    pass
    return string



