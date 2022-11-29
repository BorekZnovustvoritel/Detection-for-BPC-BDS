from typing import List

from detection.definitions import print_whole_tree
from detection.thresholds import print_threshold
from detection.scan import Report, Project, JavaFile, JavaClass, JavaMethod, NotFound
import pandas as pd

types_to_compare = {Project, JavaFile, JavaClass, JavaMethod}


def print_path(report: Report, indent: int = 0) -> str:
    if (
        type(report.first) not in types_to_compare
        or type(report.second) not in types_to_compare
    ):
        return ""
    string = (
        f"{indent * '|     '}\\ Type: {type(report.first).__name__}, "
        f"names: {report.first.name}, {report.second.name}, score: {report.probability}\n"
    )
    if report.probability > print_threshold:
        for child_report in report.child_reports:
            string += print_path(child_report, indent + 1)
    pass
    return string


def create_excel(reports: List[Report]):
    excel_handler = ExcelHandler("Output.xlsx")
    dict_of_projects = dict()
    for report in reports:
        if report.first.name not in dict_of_projects:
            dict_of_projects.update(
                {report.first.name: len(dict_of_projects.keys()) + 1}
            )
        if report.second.name not in dict_of_projects:
            dict_of_projects.update(
                {report.second.name: len(dict_of_projects.keys()) + 1}
            )
        detail_name = f"report-{dict_of_projects[report.first.name]}-{dict_of_projects[report.second.name]}"
        excel_handler.heatmap_sheet.write_url(
            dict_of_projects[report.first.name],
            dict_of_projects[report.second.name],
            f"internal:'{detail_name}'!A1:B2",
            string=f"{report.probability}",
            cell_format=excel_handler.get_format(report.probability),
        )
        excel_handler.heatmap_sheet.write_url(
            dict_of_projects[report.second.name],
            dict_of_projects[report.first.name],
            f"internal:'{detail_name}'!A1:B2",
            string=f"{report.probability}",
            cell_format=excel_handler.get_format(report.probability),
        )
        excel_handler.create_detail_sheet(report, detail_name)
    max_name_length = max([len(n) for n in dict_of_projects.keys()])
    for project_name in dict_of_projects.keys():
        excel_handler.heatmap_sheet.write(
            0,
            dict_of_projects[project_name],
            project_name,
            excel_handler.top_label_format,
        )
        excel_handler.heatmap_sheet.write(
            dict_of_projects[project_name], 0, project_name, excel_handler.label_format
        )
    excel_handler.heatmap_sheet.set_column(0, 0, max_name_length)
    excel_handler.heatmap_sheet.set_column(1, len(dict_of_projects.keys()), 5)
    excel_handler.heatmap_sheet.set_row(0, 6 * max_name_length)
    excel_handler.write()


class ExcelHandler:
    def __init__(self, name: str):
        self.name = name
        self.writer = pd.ExcelWriter(name, engine="xlsxwriter")
        self.workbook = self.writer.book
        self.heatmap_sheet = self.workbook.add_worksheet("Heatmap")
        self.green_format = self.workbook.add_format({"bg_color": "#76FF71"})
        self.yellow_format = self.workbook.add_format({"bg_color": "#E7FF71"})
        self.red_format = self.workbook.add_format({"bg_color": "#FF7171"})
        self.top_label_format = self.workbook.add_format({"bold": True})
        self.top_label_format.set_rotation(90)
        self.label_format = self.workbook.add_format({"bold": True})

    def get_format(self, score: int):
        if not isinstance(score, int):
            return None
        if score <= 70:
            return self.green_format
        if score <= 85:
            return self.yellow_format
        return self.red_format

    def create_detail_sheet(self, report: Report, sheet_name: str):
        table_of_reports = self.report_tree_to_list_of_lists(report)
        table_width = max(len(row) for row in table_of_reports)
        sheet = self.workbook.add_worksheet(sheet_name)
        column_lengths = {i: 0 for i in range(table_width)}
        for row_idx, row in enumerate(table_of_reports):
            is_first = True
            for col_idx, cell_value in enumerate(row):
                if cell_value is None:
                    continue
                if isinstance(cell_value, int):
                    sheet.write(
                        row_idx,
                        table_width - 1,
                        cell_value,
                        self.get_format(cell_value),
                    )
                    break
                if is_first:
                    sheet.write(row_idx, col_idx, cell_value, self.label_format)
                    is_first = False
                else:
                    sheet.write(row_idx, col_idx, cell_value)
                if isinstance(cell_value, str) and column_lengths.get(col_idx, 0) < len(
                    cell_value
                ):
                    column_lengths.update({col_idx: len(cell_value)})

        for col_idx in column_lengths.keys():
            sheet.set_column(col_idx, col_idx, column_lengths[col_idx])

    def report_tree_to_list_of_lists(
        self, report: Report, indent: int = 0
    ) -> List[List]:
        if (
                not print_whole_tree
                and report.probability < print_threshold
        ) or (
            type(report.first) not in types_to_compare
            and type(report.second) not in types_to_compare
        ):
            return []
        list_of_lists = [
            [None for _ in range(indent)]
            + [
                type(report.first).__name__
                if not isinstance(report.first, NotFound)
                else type(report.second).__name__,
                report.first.name,
                report.second.name,
                report.probability,
            ]
        ]
        for child in report.child_reports:
            list_of_lists.extend(self.report_tree_to_list_of_lists(child, indent + 1))
        return list_of_lists

    def write(self):
        self.writer.close()
