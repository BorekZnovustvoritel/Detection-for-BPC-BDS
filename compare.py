from typing import List

import definitions
import scan
from scan import Report, Project, JavaFile, JavaClass, JavaMethod, JavaVariable, JavaParameter, JavaStatementBlock
from definitions import threshold, table_width
import pandas as pd

types_to_compare = {Project, JavaFile, JavaClass, JavaMethod, JavaVariable, JavaParameter, JavaStatementBlock}


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


def create_excel(reports: List[Report]):
    excel_handler = ExcelHandler('Output.xlsx')
    dict_of_projects = dict()
    for report in reports:
        if report.first.name not in dict_of_projects:
            dict_of_projects.update({report.first.name: len(dict_of_projects.keys()) + 1})
        if report.second.name not in dict_of_projects:
            dict_of_projects.update({report.second.name: len(dict_of_projects.keys()) + 1})
        detail_name = f"report-{dict_of_projects[report.first.name]}-{dict_of_projects[report.second.name]}"
        excel_handler.heatmap_sheet.write_url(dict_of_projects[report.first.name], dict_of_projects[report.second.name],
                                              f"internal:'{detail_name}'!A1:B2", string=f"{report.probability}",
                                              cell_format=excel_handler.get_format(report.probability))
        excel_handler.heatmap_sheet.write_url(dict_of_projects[report.second.name], dict_of_projects[report.first.name],
                                              f"internal:'{detail_name}'!A1:B2", string=f"{report.probability}",
                                              cell_format=excel_handler.get_format(report.probability))
        excel_handler.create_detail_sheet(report, detail_name)
    max_name_length = max([len(n) for n in dict_of_projects.keys()])
    for project_name in dict_of_projects.keys():
        excel_handler.heatmap_sheet.write(0, dict_of_projects[project_name],
                                          project_name, excel_handler.top_label_format)
        excel_handler.heatmap_sheet.write(dict_of_projects[project_name], 0,
                                          project_name, excel_handler.left_label_format)
    excel_handler.heatmap_sheet.set_column(0, 0, max_name_length)
    excel_handler.heatmap_sheet.set_column(1, len(dict_of_projects.keys()), 5)
    excel_handler.heatmap_sheet.set_row(0, max_name_length)
    excel_handler.write()


class ExcelHandler:
    def __init__(self, name: str):
        self.name = name
        self.writer = pd.ExcelWriter(name, engine='xlsxwriter')
        self.workbook = self.writer.book
        self.heatmap_sheet = self.workbook.add_worksheet("Heatmap")
        self.green_format = self.workbook.add_format({'bg_color': '#76FF71'})
        self.yellow_format = self.workbook.add_format({'bg_color': '#E7FF71'})
        self.red_format = self.workbook.add_format({'bg_color': '#FF7171'})
        self.top_label_format = self.workbook.add_format({'bold': True})
        self.top_label_format.set_rotation(90)
        self.left_label_format = self.workbook.add_format({'bold': True})

    def get_format(self, score: int):
        if score <= 33:
            return self.green_format
        if score <= 67:
            return self.yellow_format
        return self.red_format

    def create_detail_sheet(self, report: Report, sheet_name: str):
        dataframe = pd.DataFrame(self.report_tree_to_list_of_lists(report))
        dataframe.to_excel(self.writer, sheet_name=sheet_name)

    def report_tree_to_list_of_lists(self, report: Report, indent: int = 0) -> List[List]:
        if not definitions.print_whole_tree and report.probability < definitions.threshold:
            return []
        list_of_lists = [[None for _ in range(indent)] +
                         [type(report.first).__name__, report.first.name, report.second.name] +
                         [None for _ in range(table_width - indent - 3)] + [report.probability]]
        for child in report.child_reports:
            list_of_lists.extend(self.report_tree_to_list_of_lists(child, indent + 1))
        return list_of_lists

    def write(self):
        self.writer.close()

