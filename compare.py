from typing import List

from scan import Report, Project, JavaFile, JavaClass, JavaMethod, JavaVariable, JavaParameter, JavaStatementBlock
from definitions import threshold
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


def create_heat_map(reports: List[Report]) -> pd.DataFrame:
    dataset = pd.DataFrame()
    for report in reports:
        dataset.at[report.first.name, report.first.name] = "-"
        dataset.at[report.second.name, report.second.name] = "-"
        dataset.at[report.first.name, report.second.name] = report.probability
        dataset.at[report.second.name, report.first.name] = report.probability
    return dataset


def create_excel(heatmap: pd.DataFrame) -> str:
    writer = pd.ExcelWriter('Output.xlsx', engine='xlsxwriter')
    heatmap.to_excel(writer, sheet_name='Heatmap')
    workbook = writer.book
    green_format = workbook.add_format({'bg_color': '#76FF71'})
    yellow_format = workbook.add_format({'bg_color': '#E7FF71'})
    red_format = workbook.add_format({'bg_color': '#FF7171'})
    worksheet = writer.sheets['Heatmap']
    last_cell_coord = len(heatmap.columns)
    worksheet.conditional_format(1, 1, last_cell_coord, last_cell_coord, {'type': 'cell',
                                                                          'criteria': 'between',
                                                                          'minimum': 0,
                                                                          'maximum': 33,
                                                                          'format': green_format})
    worksheet.conditional_format(1, 1, last_cell_coord, last_cell_coord, {'type': 'cell',
                                                                          'criteria': 'between',
                                                                          'minimum': 34,
                                                                          'maximum': 66,
                                                                          'format': yellow_format})
    worksheet.conditional_format(1, 1, last_cell_coord, last_cell_coord, {'type': 'cell',
                                                                          'criteria': 'between',
                                                                          'minimum': 67,
                                                                          'maximum': 100,
                                                                          'format': red_format})
    writer.close()
