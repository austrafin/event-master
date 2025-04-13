import csv
import os
from argparse import ArgumentParser
from typing import Callable, TypeVar, TypedDict, cast
from datetime import date, time, datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Flowable,
)


class EventBase(TypedDict):
    name: str
    date: date
    start_time: time
    end_time: time
    place: str


class Person(TypedDict):
    name: str
    group: str


class Event(EventBase):
    people: list[Person]


class EventPersonal(EventBase):
    group: str


class PersonalSchedule(TypedDict):
    person: str
    events: tuple[EventPersonal, ...]


type Events = dict[tuple[str, date, time, time, str], Event]

type EventsByDate = dict[str, list[EventBase]]

type SchedulesByPerson = dict[str, list[EventPersonal]]

type EventRow = tuple[str | Paragraph, ...]

type PDFContent = list[Flowable]


Schedule = TypeVar("Schedule", bound=EventBase)

DATE_FORMAT = "%d/%m/%Y"

TIME_FORMAT = "%H.%M"

PAGE_MARGIN = 30

FONT_SIZE = 8

styles = getSampleStyleSheet()
spacer = Spacer(1, 12)
table_style = TableStyle(
    (
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), FONT_SIZE),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    )
)
date_style = ParagraphStyle(
    name="Date",
    parent=styles["Heading2"],
    keepWithNext=True,
)


def get_paragraph(text: str) -> Paragraph:
    return Paragraph(
        text,
        ParagraphStyle(
            name="TableCell",
            parent=styles["Normal"],
            fontSize=FONT_SIZE,
        ),
    )


def get_datetime(date: str) -> datetime:
    return datetime.strptime(date, f"{DATE_FORMAT} {TIME_FORMAT}")


def get_events_sorted_by_time(
    events: list[Schedule],
) -> list[Schedule]:
    return sorted(
        events,
        key=lambda event: (event["date"], event["start_time"]),
    )


def add_event(
    event_name: str,
    events_by_name: Events,
    person: str,
    group: str,
    event_date: date,
    start_time: time,
    end_time: time,
    place: str,
):
    key = (event_name, event_date, start_time, end_time, place)
    person_and_group: Person = {"name": person, "group": group}

    if key not in events_by_name:
        events_by_name[key] = {
            "name": event_name,
            "date": event_date,
            "start_time": start_time,
            "end_time": end_time,
            "place": place,
            "people": [person_and_group],
        }
        return

    existing_event = events_by_name[key]

    existing_event["people"].append(person_and_group)


def add_personal_event(
    event_name: str,
    schedules_by_person: SchedulesByPerson,
    person: str,
    group: str,
    event_date: date,
    start_time: time,
    end_time: time,
    place: str,
):
    personal_event: EventPersonal = {
        "name": event_name,
        "date": event_date,
        "start_time": start_time,
        "end_time": end_time,
        "place": place,
        "group": group,
    }

    if person in schedules_by_person:
        schedules_by_person[person].append(personal_event)
    else:
        schedules_by_person[person] = [personal_event]


def get_schedules(
    input_file: str,
) -> tuple[tuple[Event, ...], tuple[PersonalSchedule, ...]]:
    events_by_name: Events = {}
    schedules_by_person: SchedulesByPerson = {}

    with open(input_file, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)

        if reader.fieldnames:
            reader.fieldnames = [
                header.lstrip("\ufeff") for header in reader.fieldnames
            ]

        for row in reader:
            event_datetime = get_datetime(row["Start time"])
            event_date = event_datetime.date()
            start_time = event_datetime.time()
            end_time = get_datetime(row["End time"]).time()
            place = row["Place"]
            person = row["Person"]
            group = row["Group"]
            event_name = row["Event"]

            add_event(
                event_name,
                events_by_name,
                person,
                group,
                event_date,
                start_time,
                end_time,
                place,
            )
            add_personal_event(
                event_name,
                schedules_by_person,
                person,
                group,
                event_date,
                start_time,
                end_time,
                place,
            )

    return (
        tuple(events_by_name.values()),
        tuple(
            {
                "person": person,
                "events": tuple(get_events_sorted_by_time(events)),
            }
            for person, events in schedules_by_person.items()
        ),
    )


def get_date(date: date) -> str:
    return date.strftime(DATE_FORMAT)


def get_time(time: time) -> str:
    return time.strftime(TIME_FORMAT)


def get_events_by_date(events: tuple[EventBase, ...]) -> EventsByDate:
    events_by_date: EventsByDate = {}

    for event in events:
        date_str = get_date(event["date"])

        if date_str not in events_by_date:
            events_by_date[date_str] = []

        events_by_date[date_str].append(event)

    for date_str, events_grouped in events_by_date.items():
        events_by_date[date_str] = get_events_sorted_by_time(events_grouped)

    return events_by_date


def get_event_duration(event: EventBase) -> str:
    return f"{get_time(event['start_time'])} - {get_time(event['end_time'])}"


def build_schedule_pdf(
    title: str,
    events_by_date: dict[str, list[Schedule]],
    get_event: Callable[[EventBase], tuple[EventRow, ...]],
    col_widths: tuple[int, ...],
) -> PDFContent:
    elements: PDFContent = [Paragraph(title, styles["Title"]), spacer]

    for date_str, events_on_same_date in events_by_date.items():
        elements.append(Paragraph(date_str, date_style))

        table_data = tuple(
            row for event in events_on_same_date for row in get_event(event)
        )

        if not table_data:
            continue

        table = Table(table_data, colWidths=col_widths)

        table.setStyle(table_style)
        elements.extend((table, spacer))

    return elements


def get_person_in_event(
    index: int,
    event: EventBase,
    person: Person,
) -> EventRow:
    if index == 0:
        duration = get_event_duration(event)
        name = event["name"]
        place = event["place"]
    else:
        duration = ""
        name = ""
        place = ""

    return (
        duration,
        name,
        get_paragraph(person["name"]),
        get_paragraph(person["group"]),
        place,
    )


def build_overall_schedule_pdf(events: tuple[Event, ...]) -> PDFContent:
    def get_event(event: EventBase) -> tuple[EventRow, ...]:
        event = cast(Event, event)

        # Include an empty row for spacing
        return tuple(
            get_person_in_event(i, event, person)
            for i, person in enumerate(event["people"])
        ) + ((),)

    return build_schedule_pdf(
        "Aikataulu",
        get_events_by_date(events),
        get_event,
        (80, 174, 90, 100, 80),
    )


def build_personal_schedule_pdf(
    person_name: str, events: tuple[EventPersonal, ...]
) -> PDFContent:
    def get_event(event: EventBase) -> tuple[EventRow, ...]:
        event = cast(EventPersonal, event)

        return (
            (
                get_event_duration(event),
                get_paragraph(event["name"]),
                get_paragraph(event["group"]),
                event["place"],
            ),
        )

    return build_schedule_pdf(
        person_name, get_events_by_date(events), get_event, (80, 225, 120, 100)
    )


def create_pdf(elements: PDFContent, output_path: str):
    SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=PAGE_MARGIN,
        rightMargin=PAGE_MARGIN,
    ).build(elements)


if __name__ == "__main__":
    parser = ArgumentParser()

    parser.add_argument("input_filepath", type=str)
    parser.add_argument("output_folder", type=str)

    args = parser.parse_args()
    all_events, personal_schedules = get_schedules(args.input_filepath)

    os.makedirs(args.output_folder, exist_ok=True)

    create_pdf(
        build_overall_schedule_pdf(all_events),
        os.path.join(args.output_folder, "schedule.pdf"),
    )

    for schedule in personal_schedules:
        person = schedule["person"]

        create_pdf(
            build_personal_schedule_pdf(person, schedule["events"]),
            os.path.join(args.output_folder, f"{person}.pdf"),
        )
