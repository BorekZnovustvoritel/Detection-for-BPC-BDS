from __future__ import annotations
from typing import List, Iterable, Optional

from detection.definitions import print_whole_tree, output_file_name, three_color
from detection.thresholds import print_threshold
from detection.java_scan import JavaProject, JavaFile, JavaClass, JavaMethod
from detection.py_scan import PythonProject, PythonFile, PythonClass, PythonFunction
from detection.abstract_scan import Report, NotFound, AbstractProject
import xlsxwriter

types_to_compare = {
    JavaProject,
    JavaFile,
    JavaClass,
    JavaMethod,
    PythonProject,
    PythonFile,
    PythonClass,
    PythonFunction,
}


def print_path(report: Report, indent: int = 0) -> str:
    """Long string output of the comparison result. Works with result from pairwise matching."""
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


def create_excel(
    reports: Iterable[Report],
    skipped: Iterable[str],
    not_handed: Iterable[str],
    filename: str = output_file_name,
):
    """Dump all results in xlsx file."""
    report_type_dict = dict()
    for report in reports:
        if not isinstance(report.first, AbstractProject):
            raise ValueError(
                f"Unable to to visualise values that are not descendants of {AbstractProject.__name__}"
            )
        if report.first.project_type not in report_type_dict.keys():
            report_type_dict.update({report.first.project_type: [report]})
        else:
            report_type_dict[report.first.project_type].append(report)
    excel_handler = ExcelHandler(filename, report_type_dict.keys())
    excel_handler.crete_overview(reports)
    for report_type in report_type_dict.keys():
        excel_handler.add_reports(report_type_dict[report_type], report_type)
        project_names = set(
            rep.first.name
            for rep in report_type_dict[report_type]
            if not rep.first.is_template
        )
        project_names.update(
            rep.second.name
            for rep in report_type_dict[report_type]
            if not rep.first.is_template
        )
        project_names = list(project_names)
        project_names.sort()
        excel_handler.add_note(f"{report_type} projects:", project_names)

    if skipped:
        excel_handler.add_note(
            "Projects not containing supported file formats:", skipped
        )
    if not_handed:
        excel_handler.add_note("Project solution not found in groups:", not_handed)
    excel_handler.write()


class ExcelHandler:
    """Class for encapsulation of xlsx manipulation."""

    def __init__(self, name: str, expected_types: Iterable[str]):
        """Parameter `name` is the file name."""
        self.name = name
        self.workbook = xlsxwriter.Workbook(name)
        self.overview_sheet = self.workbook.add_worksheet("Overview")
        self.heatmap_sheets = dict()
        for t in expected_types:
            self.heatmap_sheets.update({t: self.workbook.add_worksheet(f"{t} Heatmap")})
        self.green_format = self.workbook.add_format({"bg_color": "#76FF71"})
        self.yellow_format = self.workbook.add_format({"bg_color": "#E7FF71"})
        self.red_format = self.workbook.add_format({"bg_color": "#FF7171"})
        self.top_label_format = self.workbook.add_format({"bold": True})
        self.top_label_format.set_rotation(90)
        self.label_format = self.workbook.add_format({"bold": True})
        self.note_column = 0
        self.detail_sheet_no = 0
        self._row_no_for_notes = 6
        self._formatter = CellFormatter(self.workbook)

    def add_reports(self, reports: Iterable[Report], project_type: str):
        heatmap = self.heatmap_sheets[project_type]

        templates = set(r.first.name for r in reports if r.first.is_template)
        templates.update(r.second.name for r in reports if r.second.is_template)
        templates = list(templates)
        templates.sort()
        no_of_templates = len(templates)

        project_names = set(x.first.name for x in reports if not x.first.is_template)
        project_names.update(x.second.name for x in reports if not x.second.is_template)
        project_names = list(project_names)
        project_names.sort()
        no_of_projects = len(project_names)

        all_projects = templates + project_names
        dict_of_projects = dict()
        for idx, name in enumerate(all_projects):
            dict_of_projects.update({name: idx + 1})
        for report in reports:
            self._add_to_heatmap(
                heatmap,
                report,
                dict_of_projects[report.first.name],
                dict_of_projects[report.second.name],
                no_of_templates,
                no_of_projects,
            )
        max_name_length = max([len(n) for n in dict_of_projects.keys()])
        for project_name in project_names:
            best_match = max(
                filter(
                    lambda x: True
                    if x.first.name == project_name or x.second.name == project_name
                    else False,
                    reports,
                )
            )
            row = dict_of_projects[project_name] - no_of_templates
            if row > 0:
                heatmap.write(
                    row,
                    len(dict_of_projects.keys()) + 1,
                    best_match.first.name
                    if best_match.first.name != project_name
                    else best_match.second.name,
                )
        heatmap.write(
            0, len(dict_of_projects.keys()) + 1, "Best match:", self.label_format
        )
        for project_name in dict_of_projects.keys():
            heatmap.write(
                0,
                dict_of_projects[project_name],
                project_name,
                self.top_label_format,
            )
            row = dict_of_projects[project_name] - no_of_templates
            if row > 0:
                heatmap.write(row, 0, project_name, self.label_format)
        heatmap.write(1, no_of_templates + 1, "", self.get_format(None, "lt"))
        heatmap.write(
            no_of_projects,
            no_of_projects + no_of_templates,
            "",
            self.get_format(None, "dr"),
        )
        heatmap.set_column(0, 0, max_name_length)
        heatmap.set_column(
            len(dict_of_projects.keys()) + 1,
            len(dict_of_projects.keys()) + 1,
            max_name_length,
        )
        heatmap.set_column(1, len(dict_of_projects.keys()), 5)
        heatmap.set_row(0, 6 * max_name_length)

    def _single_add_to_heatmap(
        self, heatmap, row, col, score, detail_name, no_of_templates, no_of_projects
    ):
        if row > 0 and col > 0:
            borders = ""
            if row == 1:
                borders += "t"
            elif row == no_of_projects:
                borders += "d"
            if col == 1 or col == no_of_templates + 1:
                borders += "l"
            elif col == no_of_templates + no_of_projects:
                borders += "r"
            heatmap.write_url(
                row,
                col,
                f"internal:'{detail_name}'!A1:B2",
                string=f"{score}",
                cell_format=self.get_format(score, borders),
            )

    def _add_to_heatmap(
        self,
        heatmap,
        report: Report,
        first_idx: int,
        second_idx: int,
        no_of_templates: int,
        no_of_projects: int,
    ):
        detail_name = f"report-{self.detail_sheet_no}"
        self.detail_sheet_no += 1
        self._single_add_to_heatmap(
            heatmap,
            first_idx - no_of_templates,
            second_idx,
            report.probability,
            detail_name,
            no_of_templates,
            no_of_projects,
        )
        self._single_add_to_heatmap(
            heatmap,
            second_idx - no_of_templates,
            first_idx,
            report.probability,
            detail_name,
            no_of_templates,
            no_of_projects,
        )
        self.create_detail_sheet(report, detail_name)

    def get_format(self, score: Optional[int], borders_str: str = ""):
        """Helper method to determine color for the calculated value."""
        return self._formatter.get_format(score, borders_str)

    def create_detail_sheet(self, report: Report, sheet_name: str):
        """Adds one sheet to the xlsx file. This sheet contains pairwise comparison result."""
        table_of_reports = self.report_tree_to_list_of_lists(report)
        table_width = max([len(row) for row in table_of_reports] + [0])
        sheet = self.workbook.add_worksheet(sheet_name)
        column_lengths = {i: 0 for i in range(table_width - 1)}
        for row_idx, row in enumerate(table_of_reports):
            is_first = True
            for col_idx, cell_value in enumerate(row):
                if not cell_value and not isinstance(cell_value, int):
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
        """Helper method to create a table from pairwise comparison result."""
        if (not print_whole_tree and report.probability < print_threshold) or (
            type(report.first) not in types_to_compare
            and type(report.second) not in types_to_compare
        ):
            return []
        list_of_lists = [
            ["" for _ in range(indent)]
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

    def add_note(self, note_header: str, note_lines: Iterable[str]):
        row_num_to_write = self._row_no_for_notes
        self.overview_sheet.write(
            row_num_to_write, self.note_column, note_header, self.label_format
        )
        for line in note_lines:
            row_num_to_write += 1
            self.overview_sheet.write(row_num_to_write, self.note_column, line)
        needed_size = len(note_header)
        if note_lines:
            needed_size = max(needed_size, max([len(x) for x in note_lines]))
        self.overview_sheet.set_column(self.note_column, self.note_column, needed_size)
        self.note_column += 1

    def write(self):
        """Write the xlsx file."""
        self.workbook.close()

    def crete_overview(self, reports: Iterable[Report]):
        counter_dict = dict()
        _l = [i for i in range(0, 100, 10)]
        for idx, i in enumerate(_l[1:]):
            counter_dict.update({(_l[idx], i - 1): 0})
        counter_dict.update({(90, 100): 0})
        for report in reports:
            key = [
                k for k in counter_dict.keys() if k[0] <= report.probability <= k[1]
            ][0]
            counter_dict[key] += 1
        self.overview_sheet.write(0, 0, "Similarity score ranges", self.label_format)
        self.overview_sheet.write(1, 0, "Number of matches", self.label_format)
        self.overview_sheet.set_column(0, 0, 23)
        for idx, key in enumerate(counter_dict.keys()):
            self.overview_sheet.write(0, idx + 1, f"{key[0]}-{key[1]}")
            self.overview_sheet.write(1, idx + 1, counter_dict[key])
        chart = self.workbook.add_chart({"type": "column"})
        chart.add_series(
            {
                "categories": f"{self.overview_sheet.name}!$B$1:$K$1",
                "values": f"{self.overview_sheet.name}!$B$2:$K$2",
            }
        )
        chart.set_title({"name": "Histogram of the result"})
        chart.set_x_axis({"name": "Similarity score ranges"})
        chart.set_y_axis({"name": "Number of matches"})
        chart.set_legend({"none": True})
        self.overview_sheet.set_row_pixels(3, 288)
        self.overview_sheet.insert_chart("B4", chart)


class CellFormatter:
    def __init__(self, workbook: xlsxwriter.Workbook):
        self.workbook = workbook
        self.formats = dict()

    def get_format(self, score: Optional[int], borders_str: str = ""):
        allowed = {"t", "l", "d", "r"}
        borders_str = list(set(letter for letter in borders_str if letter in allowed))
        borders_str.sort()
        bg_color = ""
        if isinstance(score, int):
            bg_color = CellFormatter._score_to_color(score)
        key: str = f"{borders_str}|{bg_color}"
        form = self.formats.get(key, None)
        if form:
            return form
        form = self.workbook.add_format()
        if bg_color != "":
            form.set_bg_color(bg_color)
        if "t" in borders_str:
            form.set_top()
        if "l" in borders_str:
            form.set_left()
        if "d" in borders_str:
            form.set_bottom()
        if "r" in borders_str:
            form.set_right()
        self.formats.update({key: form})
        return form

    @staticmethod
    def _score_to_color(score: int) -> str:
        if three_color:
            if score <= 70:
                return "#76FF71"
            elif score <= 85:
                return "#E7FF71"
            else:
                return "#FF7171"
        else:
            category = score // 50
            shade_diff = score % 50
            if category == 0:
                red_str = hex(int(shade_diff * 255 / 50)).removeprefix("0x").upper()
                if len(red_str) == 1:
                    red_str = f"0{red_str}"
                return f"#{red_str}FF00"
            elif category == 1:
                green_string = hex(int((50 - shade_diff) * 255 / 50)).removeprefix("0x").upper()
                if len(green_string) == 1:
                    green_string = f"0{green_string}"
                return f"#FF{green_string}00"
            return "#FF0000"
