"""Add the booking calendar models (AppointmentType, AvailabilityRule,
AvailabilityException, Booking).

On Postgres, additionally install ``btree_gist`` and an EXCLUDE constraint
that prevents two confirmed bookings from overlapping on the same time range.
SQLite does not support EXCLUDE, so we guard that bit with vendor checks and
fall back to the application-level ``select_for_update`` overlap check.
"""
from __future__ import annotations

import uuid

import django.db.models.deletion
from django.db import migrations, models


def _install_postgres_exclude(apps, schema_editor) -> None:
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("CREATE EXTENSION IF NOT EXISTS btree_gist;")
    schema_editor.execute(
        """
        ALTER TABLE scheduling_booking
        ADD CONSTRAINT scheduling_booking_no_overlap
        EXCLUDE USING gist (
            tstzrange(start_at, end_at, '[)') WITH &&
        )
        WHERE (status = 'confirmed');
        """
    )


def _drop_postgres_exclude(apps, schema_editor) -> None:
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        "ALTER TABLE scheduling_booking DROP CONSTRAINT IF EXISTS scheduling_booking_no_overlap;"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0001_initial"),
        ("scheduling", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AppointmentType",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=120, unique=True)),
                (
                    "slug",
                    models.SlugField(blank=True, max_length=140, unique=True),
                ),
                (
                    "duration_minutes",
                    models.PositiveSmallIntegerField(
                        default=30,
                        help_text="Length of the meeting in minutes.",
                    ),
                ),
                (
                    "buffer_after_minutes",
                    models.PositiveSmallIntegerField(
                        default=0,
                        help_text="Padding after the meeting before another can start.",
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="Shown on the appointment-type picker.",
                    ),
                ),
                (
                    "location_instructions",
                    models.CharField(
                        blank=True,
                        help_text=(
                            "Free-form text describing how the meeting happens "
                            "(e.g. 'We will send a Google Meet link').'"
                        ),
                        max_length=240,
                    ),
                ),
                ("order", models.PositiveSmallIntegerField(default=100)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Appointment type",
                "verbose_name_plural": "Appointment types",
                "ordering": ["order", "name"],
            },
        ),
        migrations.CreateModel(
            name="AvailabilityRule",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "weekday",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, "Monday"),
                            (1, "Tuesday"),
                            (2, "Wednesday"),
                            (3, "Thursday"),
                            (4, "Friday"),
                            (5, "Saturday"),
                            (6, "Sunday"),
                        ],
                    ),
                ),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Availability rule",
                "verbose_name_plural": "Availability rules",
                "ordering": ["weekday", "start_time"],
            },
        ),
        migrations.CreateModel(
            name="AvailabilityException",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("start_at", models.DateTimeField()),
                ("end_at", models.DateTimeField()),
                ("reason", models.CharField(blank=True, max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Availability exception",
                "verbose_name_plural": "Availability exceptions",
                "ordering": ["start_at"],
            },
        ),
        migrations.CreateModel(
            name="Booking",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=120)),
                ("email", models.EmailField(max_length=254)),
                ("company", models.CharField(blank=True, max_length=120)),
                ("phone", models.CharField(blank=True, max_length=40)),
                ("notes", models.TextField(blank=True)),
                (
                    "start_at",
                    models.DateTimeField(help_text="UTC start of the meeting."),
                ),
                (
                    "end_at",
                    models.DateTimeField(
                        help_text="UTC end of the meeting (exclusive).",
                    ),
                ),
                (
                    "customer_timezone",
                    models.CharField(
                        blank=True,
                        help_text="IANA tz the customer booked in (e.g. America/New_York).",
                        max_length=80,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("confirmed", "Confirmed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="confirmed",
                        max_length=12,
                    ),
                ),
                (
                    "manage_token",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        help_text="Opaque token used by the customer manage/cancel page.",
                        unique=True,
                    ),
                ),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("cancel_reason", models.CharField(blank=True, max_length=200)),
                (
                    "ip_address",
                    models.GenericIPAddressField(blank=True, null=True),
                ),
                ("user_agent", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "appointment_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bookings",
                        to="scheduling.appointmenttype",
                    ),
                ),
                (
                    "rescheduled_from",
                    models.ForeignKey(
                        blank=True,
                        help_text="If this booking replaces another, the original it replaced.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="rescheduled_to",
                        to="scheduling.booking",
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        blank=True,
                        help_text="Optional consulting area the customer wants to discuss.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="bookings",
                        to="pages.service",
                    ),
                ),
            ],
            options={
                "verbose_name": "Booking",
                "verbose_name_plural": "Bookings",
                "ordering": ["-start_at"],
                "indexes": [
                    models.Index(
                        fields=["status", "start_at"],
                        name="scheduling__status_982cd9_idx",
                    ),
                    models.Index(
                        fields=["start_at", "end_at"],
                        name="scheduling__start_a_307982_idx",
                    ),
                ],
            },
        ),
        migrations.RunPython(
            _install_postgres_exclude,
            reverse_code=_drop_postgres_exclude,
        ),
    ]
