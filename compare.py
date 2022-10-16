from scan import Report, Project, JavaFile, JavaClass, JavaMethod, JavaVariable
from definitions import treshold


types_to_compare = {Project, JavaFile, JavaClass, JavaMethod, JavaVariable}


def print_path(report: Report, indent: int = 0) -> str:
    if type(report.first) not in types_to_compare or type(report.second) not in types_to_compare:
        return ""
    string = f"{indent * '|     '}\\ Type: {type(report.first).__name__}, " \
             f"names: {report.first.name}, {report.second.name}, score: {report.probability}\n"
    if report.probability > treshold:
        for child_report in report.child_reports:
            string += print_path(child_report, indent + 1)
    pass
    return string


if __name__ == "__main__":
    proj1 = Project("/home/lmayo/Dokumenty/baklazanka/java_test/Projekt_BDS_4/")
    proj2 = Project("/home/lmayo/Dokumenty/baklazanka/java_test/Projekt_BDS_3/")
    cmp = proj1.compare(proj2)
    print(
        print_path(
            cmp
        )
    )

