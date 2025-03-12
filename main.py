import csv
import os
from argparse import ArgumentParser
from typing import TypedDict
from datetime import date, time, datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
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


class Event(EventBase):
    groups: list[str]
    people: list[str]


class EventPersonal(EventBase):
    group: str


class PersonalSchedule(TypedDict):
    person: str
    events: list[EventPersonal]


type EventsByName = dict[str, Event]

type SchedulesByPerson = dict[str, list[EventPersonal]]

DATE_FORMAT = "%d/%m/%Y"

TIME_FORMAT = "%H.%M"

PAGE_MARGIN = 30

styles = getSampleStyleSheet()
spacer = Spacer(1, 12)
table_style = TableStyle(
    (
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    )
)


def get_datetime(date: str) -> datetime:
    return datetime.strptime(date, f"{DATE_FORMAT} {TIME_FORMAT}")


def add_event(
    event_name: str,
    events_by_name: EventsByName,
    person: str,
    group: str,
    event_date: date,
    start_time: time,
    end_time: time,
    place: str,
):
    if event_name not in events_by_name:
        events_by_name[event_name] = {
            "name": event_name,
            "date": event_date,
            "start_time": start_time,
            "end_time": end_time,
            "place": place,
            "groups": [group],
            "people": [person],
        }
        return

    existing_event = events_by_name[event_name]

    for key, new_value in (("people", person), ("groups", group)):
        if person not in existing_event[key]:
            existing_event[key].append(new_value)  # type: ignore

    existing_event["date"] = event_date

    if start_time < existing_event["start_time"]:
        existing_event["start_time"] = start_time

    if end_time > existing_event["end_time"]:
        existing_event["end_time"] = end_time


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
    events_by_name: EventsByName = {}
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
                "events": sorted(
                    events, key=lambda event: (event["date"], event["start_time"])
                ),
            }
            for person, events in schedules_by_person.items()
        ),
    )


def get_date(date: date) -> str:
    return date.strftime(DATE_FORMAT)


def get_time(time: time) -> str:
    return time.strftime(TIME_FORMAT)


def get_events_by_date(
    events: list[EventPersonal],
) -> dict[str, list[EventPersonal]]:
    events_by_date: dict[str, list[EventPersonal]] = {}

    for event in events:
        date_str = get_date(event["date"])

        if date_str not in events_by_date:
            events_by_date[date_str] = []

        events_by_date[date_str].append(event)

    return events_by_date


def build_pdf(person_name: str, events: list[EventPersonal]) -> list[Flowable]:
    elements: list[Flowable] = []

    elements.append(Paragraph(person_name, styles["Title"]))
    elements.append(spacer)

    for date_str, events in get_events_by_date(events).items():
        elements.append(Paragraph(date_str, styles["Heading2"]))

        table_data = [
            (
                f"{get_time(event['start_time'])} - {get_time(event['end_time'])}",
                Paragraph(event["name"]),
                event["group"],
                event["place"],
            )
            for event in events
        ]

        if not table_data:
            continue

        table = Table(table_data, colWidths=(80, 225, 120, 100))

        table.setStyle(table_style)
        elements.append(table)
        elements.append(spacer)

    return elements


def create_pdf(elements: list[Flowable], output_path: str):
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

    for schedule in personal_schedules:
        person = schedule["person"]

        create_pdf(
            build_pdf(person, schedule["events"]),
            os.path.join(args.output_folder, f"{person}.pdf"),
        )
