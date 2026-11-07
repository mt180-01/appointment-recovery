import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from contract import (
    Appointment,
    AppointmentsOutput,
    BookBatchOutput,
    BookingOutput,
    Slot,
    SlotsOutput,
    Tool,
    WorkspaceOutput,
)
from verifier.calendar import CALENDAR, read_calendar
from verifier.fixture import APPOINTMENT_BY_ID, APPOINTMENTS, DISRUPTION, INITIAL, SLOT_BY_ID, SLOTS, eligible


def list_appointments(value, workspace):
    return AppointmentsOutput([Appointment(**row) for row in APPOINTMENTS])


def current_calendar(workspace):
    try:
        return read_calendar(workspace)
    except FileNotFoundError:
        return INITIAL.copy()


def list_slots(value, workspace):
    booked = current_calendar(workspace)
    occupied = set(booked.values())
    return SlotsOutput([Slot(**row) for row in SLOTS if row["slot_id"] not in occupied])


def save_bookings(bookings, workspace):
    booked = current_calendar(workspace)
    ids = [row.appointment_id for row in bookings]
    if not bookings or len(set(ids)) != len(ids):
        raise ValueError("Expected a nonempty batch with distinct appointment IDs")
    for value in bookings:
        appointment = APPOINTMENT_BY_ID.get(value.appointment_id)
        slot = SLOT_BY_ID.get(value.slot_id)
        if appointment is None or slot is None or not eligible(appointment, slot):
            raise ValueError("Unknown appointment, unknown slot, or ineligible slot")
        if booked.get(value.appointment_id) != value.slot_id:
            if value.appointment_id in booked or value.slot_id in booked.values():
                raise ValueError("Appointment or slot is already booked")
            booked[value.appointment_id] = value.slot_id
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=workspace, delete=False) as temporary:
        path = Path(temporary.name)
        try:
            json.dump(booked, temporary)
            temporary.close()
            os.replace(path, workspace / CALENDAR)
        finally:
            path.unlink(missing_ok=True)


def book_slot(value, workspace):
    save_bookings([value], workspace)
    return BookingOutput(value.appointment_id, value.slot_id)


def book_slots(value, workspace):
    save_bookings(value.bookings, workspace)
    return BookBatchOutput(value.bookings)


def checked(implementation):
    def call(value, workspace):
        if value.disruption_id != DISRUPTION:
            raise ValueError("Unknown disruption")
        return implementation(value, workspace)

    return call


def check_workspace(value, workspace):
    return WorkspaceOutput(clean=not (workspace / CALENDAR).exists())


IMPLEMENTATIONS = {
    Tool.CHECK: check_workspace,
    Tool.APPOINTMENTS: checked(list_appointments),
    Tool.SLOTS: checked(list_slots),
    Tool.BOOK: checked(book_slot),
    Tool.BOOK_BATCH: checked(book_slots),
}
