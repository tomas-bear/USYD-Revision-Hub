#!/usr/bin/env python3
"""Export public-ready revision PDFs from the private production workspace.

The private USYD-past-papers workspace contains raw source materials, generated
intermediate files, and internal production scripts. This exporter copies only
final-root, student-facing PDFs into this public repository and regenerates the
course index pages.
"""

from __future__ import annotations

import argparse
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path


DOCS_URL = "https://docs.qq.com/sheet/DRmNoZWp1V1dHY0Nu?tab=ss_52nz0g&viewId=vFP6At"
ISSUES_URL = "https://github.com/tomas-bear/USYD-Revision-Hub/issues"


@dataclass(order=True)
class Course:
    code: str
    title: str
    area: str
    source_dir: Path
    cheatsheets: list[Path] = field(default_factory=list)
    practices: list[Path] = field(default_factory=list)


AREA_LABELS = {
    "BUSS-QBUS": "Business / Analytics",
    "COMP-INFO-DATA-SOFT": "Computer Science / Data / IT",
    "ECMT-ECON-ECOS": "Economics / Econometrics",
    "ELEC": "Engineering",
    "FINC-ACCT-MKTG": "Finance / Accounting / Marketing",
    "MATH-STAT-CHEM-PHYS": "Math / Stats / Science",
    "OTHERS": "Other",
}

TITLE_OVERRIDES = {
    "ECON1002": "Introductory Macroeconomics",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path("/home/bear/projects/USYD-past-papers"),
        help="Private production workspace root.",
    )
    parser.add_argument(
        "--public-root",
        type=Path,
        default=Path.cwd(),
        help="Public GitHub repository root.",
    )
    parser.add_argument(
        "--semester",
        default="26s1",
        help="Semester tag to export, for example 26s1.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove generated course folders before exporting.",
    )
    return parser.parse_args()


def course_code_and_title(course_dir: Path) -> tuple[str, str]:
    name = course_dir.name
    codes = re.findall(r"[A-Z]{4}\d{4}", name.upper())
    code = "-".join(codes) if codes else name.split()[0].upper()
    title = name
    for part in codes:
        title = re.sub(rf"\b{re.escape(part)}\b", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title).strip()
    title = title.strip(" -")
    return code, TITLE_OVERRIDES.get(code, title or code)


def is_final_root_pdf(path: Path, semester: str) -> bool:
    if path.suffix.lower() != ".pdf":
        return False
    if path.parent.name != "final":
        return False
    lower_name = path.name.lower()
    return (
        f"_{semester.lower()}_" in lower_name
        and (
            "cheatsheet" in lower_name
            or "final-practice" in lower_name
        )
    )


def collect_courses(source_root: Path, semester: str) -> dict[str, Course]:
    courses: dict[str, Course] = {}

    for pdf in sorted(source_root.glob("*/**/final/*.pdf")):
        if not is_final_root_pdf(pdf, semester):
            continue

        course_dir = pdf.parent.parent
        top_dir = pdf.relative_to(source_root).parts[0]
        code, title = course_code_and_title(course_dir)
        course = courses.setdefault(
            code,
            Course(
                code=code,
                title=title,
                area=AREA_LABELS.get(top_dir, top_dir),
                source_dir=course_dir,
            ),
        )

        if "cheatsheet" in pdf.name.lower():
            course.cheatsheets.append(pdf)
        elif "final-practice" in pdf.name.lower():
            course.practices.append(pdf)

    return dict(sorted(courses.items()))


def reset_generated_courses(public_root: Path) -> None:
    courses_root = public_root / "courses"
    if courses_root.exists():
        shutil.rmtree(courses_root)
    courses_root.mkdir(parents=True, exist_ok=True)


def copy_pdfs(public_root: Path, courses: dict[str, Course]) -> None:
    for course in courses.values():
        course_root = public_root / "courses" / course.code
        cheatsheet_root = course_root / "cheatsheets"
        practice_root = course_root / "practice"
        cheatsheet_root.mkdir(parents=True, exist_ok=True)
        practice_root.mkdir(parents=True, exist_ok=True)

        for source in course.cheatsheets:
            target = cheatsheet_root / source.name
            shutil.copy2(source, target)
        for source in course.practices:
            target = practice_root / source.name
            shutil.copy2(source, target)


def rel_link(path: Path) -> str:
    return str(path).replace(" ", "%20")


def render_course_readme(course: Course) -> str:
    lines = [
        f"# {course.code} {course.title}",
        "",
        f"Area: {course.area}",
        "",
        "Public, student-facing revision materials from USYD Revision Hub.",
        "",
        f"Full tracker and update requests: [Tencent Docs]({DOCS_URL})",
        "",
        "## Files",
        "",
    ]

    if course.cheatsheets:
        lines.extend(["### Cheatsheets", ""])
        for pdf in sorted(course.cheatsheets, key=lambda p: p.name.lower()):
            local = Path("cheatsheets") / pdf.name
            lines.append(f"- [{pdf.name}]({rel_link(local)})")
        lines.append("")

    if course.practices:
        lines.extend(["### Practice", ""])
        for pdf in sorted(course.practices, key=lambda p: p.name.lower()):
            local = Path("practice") / pdf.name
            lines.append(f"- [{pdf.name}]({rel_link(local)})")
        lines.append("")

    lines.extend(
        [
            "## Notes",
            "",
            "- These files are independent revision materials and are not official University of Sydney documents.",
            "- Always follow your unit outline, Canvas instructions, and academic integrity requirements.",
            f"- Found an error or want to contribute? Use [GitHub Issues]({ISSUES_URL}) or [Tencent Docs]({DOCS_URL}).",
            "",
        ]
    )
    return "\n".join(lines)


def render_courses_index(courses: dict[str, Course]) -> str:
    lines = [
        "# Course Index",
        "",
        f"Full update tracker: [Tencent Docs]({DOCS_URL})",
        "",
        "| Area | Course | Cheatsheet | Practice | Status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for course in courses.values():
        course_link = f"[`{course.code}`](./{course.code}/)"
        title = course.title
        cheatsheet = "Yes" if course.cheatsheets else "-"
        practice = "Yes" if course.practices else "-"
        status = "Ready" if course.cheatsheets and course.practices else "Partial"
        lines.append(f"| {course.area} | {course_link} {title} | {cheatsheet} | {practice} | {status} |")
    lines.append("")
    return "\n".join(lines)


def render_root_readme(courses: dict[str, Course], semester: str) -> str:
    total_cheatsheets = sum(len(course.cheatsheets) for course in courses.values())
    total_practices = sum(len(course.practices) for course in courses.values())
    lines = [
        "# USYD Revision Hub",
        "",
        '<p align="center">',
        '  <img src="./assets/readme-hero.jpg" alt="USYD Revision Hub preview banner" width="100%" />',
        "</p>",
        "",
        '<p align="center">',
        f'  <a href="{DOCS_URL}"><strong>Tencent Docs Index</strong></a> ·',
        '  <a href="./courses/"><strong>Course Directory</strong></a> ·',
        f'  <a href="{ISSUES_URL}"><strong>Report an Issue</strong></a>',
        "</p>",
        "",
        "悉尼大学复习资料公开索引。这里放的是筛选过的公开版 revision materials：cheatsheets、final practice PDFs、课程目录和更新入口。",
        "",
        f"> 完整资料状态、缺失课程申请、微信更新提醒：打开 [Tencent Docs Index]({DOCS_URL})。",
        "",
        "## Start Here",
        "",
        "| Need | Link |",
        "| --- | --- |",
        f"| 查看完整资料表、更新状态、微信入口 | [Tencent Docs Index]({DOCS_URL}) |",
        "| 按课程代码找 PDF | [Course Directory](./courses/) |",
        f"| 反馈错误或申请补充课程 | [GitHub Issues]({ISSUES_URL}) |",
        "",
        "## Snapshot",
        "",
        f"Current public export for `{semester}`: **{len(courses)} courses**, **{total_cheatsheets} cheatsheets**, and **{total_practices} final-practice PDFs**.",
        "",
        '<p align="center">',
        '  <img src="./assets/preview-cheatsheet.jpg" width="45%" alt="Cheatsheet PDF preview" />',
        '  <img src="./assets/preview-practice.jpg" width="45%" alt="Practice PDF preview" />',
        "</p>",
        "",
        "| Material | What it is for |",
        "| --- | --- |",
        "| Cheatsheets | Compact formulas, definitions, concept maps, and high-frequency exam reminders. |",
        "| Final Practice | Original final-style questions for timed revision and topic checks. |",
        "| Course Index | One folder per unit code, with direct PDF download links. |",
        "| Tencent Docs | Live tracker for updates, missing courses, and WeChat contact. |",
        "",
        "## Course List",
        "",
        "| Area | Course | Cheatsheet | Practice |",
        "| --- | --- | --- | --- |",
    ]

    for course in courses.values():
        course_link = f"[`{course.code}`](./courses/{course.code}/)"
        cheatsheet = "Yes" if course.cheatsheets else "-"
        practice = "Yes" if course.practices else "-"
        lines.append(f"| {course.area} | {course_link} {course.title} | {cheatsheet} | {practice} |")

    lines.extend(
        [
            "",
            f"See the folder index in [Course Directory](./courses/) or the live tracker in [Tencent Docs]({DOCS_URL}).",
            "",
            "## How To Use",
            "",
            "1. Open [Course Directory](./courses/) and find your unit code.",
            "2. Download the available cheatsheet or final practice PDF.",
            "3. Use these materials together with your official unit outline, Canvas material, lecture notes, and tutorial work.",
            f"4. For latest status, missing courses, or WeChat update reminders, open [Tencent Docs]({DOCS_URL}).",
            "",
            "## Tencent Docs / WeChat",
            "",
            f"The live tracker is maintained in [Tencent Docs]({DOCS_URL}).",
            "",
            "For WeChat update reminders, contribution feedback, and missing-course requests, scan the QR code below.",
            "",
            '<p align="center">',
            '  <img src="./assets/wechat-qr.jpg" width="260" alt="WeChat QR code for USYD Revision Hub" />',
            "</p>",
            "",
            "## Public Sharing Policy",
            "",
            "This repository is for legal, independent revision. It is not a dump of raw course files.",
            "",
            "Included materials should be one of:",
            "",
            "- Original revision summaries or practice questions",
            "- Public resource indexes",
            "- Materials that are allowed to be shared publicly",
            "",
            "Do not upload:",
            "",
            "- Canvas-only lecture slides, tutorial sheets, solutions, recordings, or marking guides without permission",
            "- Current assignments, quizzes, exams, or answers",
            "- Unauthorized past paper originals or sample solutions",
            "- Other students' notes, code, submissions, or personal information",
            "- Anything intended for cheating, impersonation, or assessment misconduct",
            "",
            "## Academic Integrity & Copyright",
            "",
            "This repository is an independent student-made revision index and is not affiliated with, endorsed by, or maintained by the University of Sydney.",
            "",
            "Use these materials for study and revision only. Always follow your unit coordinator's instructions, the University of Sydney Academic Integrity Policy, and copyright requirements.",
            "",
            "If you are a copyright owner, instructor, or original author and believe something should not be public, please open an issue with the file path. After review, the material can be removed, replaced with a link, or updated with proper attribution.",
            "",
            "## License",
            "",
            "Unless otherwise stated, original text in this repository is shared under CC BY-NC-SA 4.0.",
            "",
            "Third-party and university materials remain the property of their respective rights holders and are not automatically covered by this license.",
            "",
        ]
    )
    return "\n".join(lines)


def write_indexes(public_root: Path, courses: dict[str, Course], semester: str) -> None:
    for course in courses.values():
        course_root = public_root / "courses" / course.code
        (course_root / "README.md").write_text(render_course_readme(course), encoding="utf-8")

    (public_root / "courses" / "README.md").write_text(render_courses_index(courses), encoding="utf-8")
    (public_root / "README.md").write_text(render_root_readme(courses, semester), encoding="utf-8")


def main() -> None:
    args = parse_args()
    public_root = args.public_root.resolve()
    source_root = args.source_root.resolve()

    if args.clean:
        reset_generated_courses(public_root)
    else:
        (public_root / "courses").mkdir(parents=True, exist_ok=True)

    courses = collect_courses(source_root, args.semester)
    if not courses:
        raise SystemExit(f"No public-ready PDFs found for semester {args.semester} in {source_root}")

    copy_pdfs(public_root, courses)
    write_indexes(public_root, courses, args.semester)

    print(f"Exported {len(courses)} courses to {public_root}")
    print(f"Cheatsheets: {sum(len(course.cheatsheets) for course in courses.values())}")
    print(f"Practice PDFs: {sum(len(course.practices) for course in courses.values())}")


if __name__ == "__main__":
    main()
