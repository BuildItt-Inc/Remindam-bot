"""Interactive WhatsApp flow engine.

Messages use Twilio Content Templates for native buttons/lists.
Free-text input is needed for:
- Medication name
- Dosage
- Reminder time
"""

import logging
from datetime import time as dt_time

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.medication import ItemType, MedicationForm
from app.models.user import User
from app.schemas.medication import MedicationCreate, MedicationScheduleCreate
from app.services.medication import medication_service
from app.services.message_types import (
    Button,
    ButtonMsg,
    ListMsg,
    ListRow,
    ListSection,
    Msg,
    TextMsg,
)
from app.services.payment_service import payment_service
from app.services.subscription_service import subscription_service

logger = logging.getLogger(__name__)


# ── Pre-built menus ──


def main_menu(
    body: str = "", is_premium: bool = False, is_standard: bool = False
) -> ListMsg:
    """The main menu as a native WhatsApp list, dynamically showing upgrade options."""
    if is_premium:
        content_sid = settings.CT_MAIN_MENU_PREMIUM
    elif is_standard:
        content_sid = settings.CT_MAIN_MENU_STANDARD
    else:
        content_sid = settings.CT_MAIN_MENU_FREE

    return ListMsg(
        body=body or "What would you like to do?",
        button_text="Open Menu",
        title="Main Menu",
        sections=[],
        content_sid=content_sid,
        content_variables={"1": body or "What would you like to do?"},
    )


MEDICATION_FORM_MENU = ListMsg(
    body="What form is your medication?",
    button_text="Select Form",
    title="Medication Form",
    sections=[
        ListSection(
            title="Select one",
            rows=[
                ListRow(id="form_tablet", title="💊 Tablet"),
                ListRow(id="form_capsule", title="💊 Capsule"),
                ListRow(id="form_syrup", title="🥤 Syrup"),
                ListRow(id="form_inhaler", title="🫁 Inhaler"),
                ListRow(id="form_injection", title="💉 Injection"),
                ListRow(id="form_cream", title="🧴 Cream / Ointment"),
                ListRow(id="form_drops", title="💧 Drops"),
                ListRow(id="form_custom", title="✏️ Other (type it)"),
            ],
        )
    ],
    content_sid=settings.CT_MEDICATION_FORM,
)

FORM_ID_MAP = {
    "form_tablet": MedicationForm.TABLET,
    "form_capsule": MedicationForm.CAPSULE,
    "form_syrup": MedicationForm.SYRUP,
    "form_inhaler": MedicationForm.INHALER,
    "form_injection": MedicationForm.INJECTION,
    "form_cream": MedicationForm.CREAM,
    "form_drops": MedicationForm.DROPS,
}

EXERCISE_TYPE_MENU = ListMsg(
    body="What type of exercise?",
    button_text="Select Exercise",
    title="Exercise Type",
    sections=[
        ListSection(
            title="Select one",
            rows=[
                ListRow(id="ex_running", title="🏃 Running"),
                ListRow(id="ex_walking", title="🚶 Walking"),
                ListRow(id="ex_gym", title="🏋️ Gym Workout"),
                ListRow(id="ex_yoga", title="🧘 Yoga"),
                ListRow(id="ex_swimming", title="🏊 Swimming"),
                ListRow(id="ex_cycling", title="🚴 Cycling"),
                ListRow(id="ex_custom", title="✏️ Other (type it)"),
            ],
        )
    ],
    content_sid=settings.CT_EXERCISE_TYPE,
)

EXERCISE_ID_MAP = {
    "ex_running": "Running",
    "ex_walking": "Walking",
    "ex_gym": "Gym Workout",
    "ex_yoga": "Yoga",
    "ex_swimming": "Swimming",
    "ex_cycling": "Cycling",
}

EXERCISE_DURATION_MENU = ListMsg(
    body="How long is your session?",
    button_text="Select Duration",
    title="Exercise Duration",
    sections=[
        ListSection(
            title="Select one",
            rows=[
                ListRow(id="dur_15", title="⏱ 15 minutes"),
                ListRow(id="dur_30", title="⏱ 30 minutes"),
                ListRow(id="dur_45", title="⏱ 45 minutes"),
                ListRow(id="dur_60", title="⏱ 1 hour"),
                ListRow(id="dur_90", title="⏱ 1.5 hours"),
            ],
        )
    ],
)

DURATION_ID_MAP = {
    "dur_15": "15 minutes",
    "dur_30": "30 minutes",
    "dur_45": "45 minutes",
    "dur_60": "1 hour",
    "dur_90": "1.5 hours",
}

WATER_AMOUNT_MENU = ListMsg(
    body="How much water per intake?",
    button_text="Select Amount",
    title="Water Amount",
    sections=[
        ListSection(
            title="Select one",
            rows=[
                ListRow(
                    id="water_250",
                    title="250ml",
                    description="1 glass",
                ),
                ListRow(
                    id="water_500",
                    title="500ml",
                    description="2 glasses",
                ),
                ListRow(
                    id="water_750",
                    title="750ml",
                    description="3 glasses",
                ),
                ListRow(
                    id="water_1000",
                    title="1 litre",
                    description="4 glasses",
                ),
                ListRow(
                    id="water_custom",
                    title="✏️ Custom amount",
                    description="Type your own amount",
                ),
            ],
        )
    ],
    content_sid=settings.CT_WATER_AMOUNT,
)

WATER_AMOUNT_ID_MAP = {
    "water_250": "250ml",
    "water_500": "500ml",
    "water_750": "750ml",
    "water_1000": "1 litre",
}

WATER_INTERVAL_MENU = ListMsg(
    body="How often should I remind you?",
    button_text="Select Interval",
    title="Reminder Interval",
    sections=[
        ListSection(
            title="Select one",
            rows=[
                ListRow(id="int_1", title="⏰ Every 1 hour"),
                ListRow(id="int_2", title="⏰ Every 2 hours"),
                ListRow(id="int_3", title="⏰ Every 3 hours"),
                ListRow(id="int_4", title="⏰ Every 4 hours"),
                ListRow(id="int_custom", title="✏️ Custom interval"),
            ],
        )
    ],
    content_sid=settings.CT_WATER_INTERVAL,
)

WATER_INTERVAL_ID_MAP = {
    "int_1": (1, "every 1 hour"),
    "int_2": (2, "every 2 hours"),
    "int_3": (3, "every 3 hours"),
    "int_4": (4, "every 4 hours"),
}


def _limit_reached_msg() -> ButtonMsg:
    return ButtonMsg(
        body=(
            "🚫 *Limit Reached*\n\n"
            "Your Standard subscription / Free Trial only allows up to 5 active reminders in total.\n\n"
            "Please upgrade to Premium for unlimited reminders!"
        ),
        buttons=[
            Button(id="menu_upgrade_premium", text="⭐ Premium"),
            Button(id="go_menu", text="🏠 Menu"),
        ],
        content_sid=settings.CT_LIMIT_REACHED,
    )


def _premium_required_msg() -> ButtonMsg:
    return ButtonMsg(
        body=(
            "🔒 This feature is available to our *Subscribers* only.\n\n"
            "Please upgrade your plan to unlock "
            "exercise reminders, water intake tracking, "
            "and comprehensive adherence reports! ⭐"
        ),
        buttons=[
            Button(id="menu_upgrade_standard", text="⭐ Standard"),
            Button(id="menu_upgrade_premium", text="⭐ Premium"),
            Button(id="go_menu", text="🏠 Menu"),
        ],
        content_sid=settings.CT_PREMIUM_REQUIRED,
    )


def _trial_expired_msg() -> ButtonMsg:
    return ButtonMsg(
        body=(
            "⏰ Your *24-hour free trial* has ended.\n\n"
            "To continue using Remindam, please choose a plan:"
        ),
        buttons=[
            Button(id="menu_upgrade_standard", text="⭐ Standard"),
            Button(id="menu_upgrade_premium", text="⭐ Premium"),
        ],
        content_sid=settings.CT_TRIAL_EXPIRED,
    )


class FlowService:
    """Manages the interactive button-based conversational flow."""

    async def _get_upgrade_msg(
        self, db: AsyncSession, user: User, target_plan: str
    ) -> Msg:
        """Generate a dynamic upgrade message with a unique Paystack link."""
        # Placeholder email for Paystack (requires an email)
        email = f"{user.profile.whatsapp_number.replace('+', '')}@remindam.com"

        amount = settings.SUBSCRIPTION_AMOUNT_PREMIUM_KOBO
        if target_plan == "standard":
            amount = settings.SUBSCRIPTION_AMOUNT_STANDARD_KOBO

        url = await payment_service.initialize_transaction(
            db,
            user_id=user.id,
            email=email,
            amount_kobo=amount,
        )

        link_text = (
            f"Link: {url}"
            if url
            else "_Error generating payment link. Please try again later._"
        )

        if target_plan == "standard":
            body_text = (
                "⭐ *Upgrade to Remindam Standard*\n\n"
                "Get access to:\n"
                "✅ Up to 5 Active Reminders\n\n"
                f"💰 Only *₦{amount // 100}/month*\n\n"
                "To subscribe, make a payment via *Paystack*:\n"
                f"{link_text}\n\n"
                "You'll be activated automatically once payment is confirmed."
            )
        else:
            body_text = (
                "⭐ *Upgrade to Remindam Premium*\n\n"
                "Get access to:\n"
                "✅ Unlimited Reminders\n"
                "✅ Exercise Reminders 🏃\n"
                "✅ Water Intake Reminders 💧\n"
                "✅ Weekly & Monthly Reports 📊\n\n"
                f"💰 Only *₦{amount // 100}/month*\n\n"
                "To subscribe, make a payment via *Paystack*:\n"
                f"{link_text}\n\n"
                "You'll be activated automatically once payment is confirmed."
            )

        return TextMsg(body=body_text)

    async def handle(
        self,
        db: AsyncSession,
        user: User,
        state: str,
        data: dict,
        body: str,
    ) -> tuple[Msg, str | None, dict | None]:
        """Process user input and return (message, next_state, data).

        Returns:
            message: Structured message to send
            next_state: New state (None = clear/idle)
            state_data: Data to persist for the next step
        """
        # Global: go back to menu (not allowed during T&C acceptance)
        if (
            body in ("go_menu", "menu", "0", "back", "cancel")
            and state != "terms_accept"
        ):
            sub = await subscription_service.get_user_subscription(db, user.id)
            is_premium = sub.plan == "premium" if sub else False
            is_standard = sub.plan == "standard" if sub else False
            return main_menu(is_premium=is_premium, is_standard=is_standard), None, None

        # Global: Interactive Reminder Actions
        if body.startswith("take_"):
            return await self._handle_taken(db, user, body)
        if body.startswith("snooze_"):
            return await self._handle_snooze(db, user, body)
        if body.startswith("skip_"):
            return await self._handle_skip(db, user, body)

        handler = getattr(self, f"_s_{state}", None)
        if handler:
            return await handler(db, user, data, body)

        sub = await subscription_service.get_user_subscription(db, user.id)
        is_premium = sub.plan == "premium" if sub else False
        is_standard = sub.plan == "standard" if sub else False
        return main_menu(is_premium=is_premium, is_standard=is_standard), None, None

    # ── TERMS & CONDITIONS ──

    async def _s_terms_accept(
        self, db: AsyncSession, user: User, data: dict, body: str
    ) -> tuple[Msg, str | None, dict | None]:
        """Gate new users until they accept T&C."""
        from datetime import UTC, datetime

        if body == "terms_agree":
            user.terms_accepted_at = datetime.now(UTC)
            await db.commit()

            # Send welcome message
            welcome = TextMsg(
                body=(
                    "👋 *Welcome to Remindam!*\n\n"
                    "I'm your health reminder assistant.\n\n"
                    "You have a *24-hour free trial* to try "
                    "setting up reminders (up to 5).\n\n"
                    "After that, upgrade to continue:\n"
                    "⭐ *Standard (₦500/mo)* — 5 active reminders\n"
                    "⭐ *Premium (₦1200/mo)* — Unlimited + Reports"
                ),
            )
            from app.services.whatsapp_service import whatsapp_service

            await whatsapp_service.send(
                user.profile.whatsapp_number, welcome, db=db, user_id=user.id
            )

            sub = await subscription_service.get_user_subscription(db, user.id)
            is_premium = sub.plan == "premium" if sub else False
            is_standard = sub.plan == "standard" if sub else False
            return (
                main_menu(
                    body="Tap Open Menu to get started! 🎉",
                    is_premium=is_premium,
                    is_standard=is_standard,
                ),
                None,
                None,
            )

        # User declined or sent something else — re-prompt
        return (
            ButtonMsg(
                body=(
                    "⚠️ You must accept the Terms & Conditions to use Remindam.\n\n"
                    "Your data is handled securely under NDPR guidelines."
                ),
                buttons=[
                    Button(id="terms_agree", text="✅ I Agree"),
                    Button(id="terms_decline", text="❌ I Decline"),
                ],
            ),
            "terms_accept",
            None,
        )

    # ── MAIN MENU ──

    async def _s_idle(
        self, db: AsyncSession, user: User, data: dict, body: str
    ) -> tuple[Msg, str | None, dict | None]:
        is_trial = subscription_service.is_trial_active(user)
        sub = await subscription_service.get_user_subscription(db, user.id)
        is_premium = sub.plan == "premium" if sub else False
        is_standard = sub.plan == "standard" if sub else False
        has_sub = sub is not None
        trial_expired = not is_trial and not has_sub

        if body == "menu_medication":
            if trial_expired:
                return _trial_expired_msg(), "idle", None

            can_add = await subscription_service.can_add_reminder(db, user)
            if not can_add:
                return _limit_reached_msg(), "idle", None

            body_text = (
                "What is the *name* of your medication?\n\n"
                "_Type the name (e.g. Paracetamol)_"
            )
            return (
                ButtonMsg(
                    body=body_text,
                    buttons=[
                        Button(id="back", text="⬅️ Back"),
                        Button(id="go_menu", text="🏠 Main Menu"),
                    ],
                    content_sid=settings.CT_BACK_MENU,
                    content_variables={"1": body_text},
                ),
                "med_name",
                None,
            )

        if body == "menu_exercise":
            if trial_expired:
                return _trial_expired_msg(), "idle", None

            can_add = await subscription_service.can_add_reminder(db, user)
            if not can_add:
                return _limit_reached_msg(), "idle", None
            return EXERCISE_TYPE_MENU, "exercise_type", None

        if body == "menu_water":
            if trial_expired:
                return _trial_expired_msg(), "idle", None

            can_add = await subscription_service.can_add_reminder(db, user)
            if not can_add:
                return _limit_reached_msg(), "idle", None
            return WATER_AMOUNT_MENU, "water_amount", None

        if body == "menu_reminders":
            return await self._show_reminders(db, user)

        if body == "menu_delete":
            return await self._start_delete_flow(db, user)

        if body == "menu_report":
            if not is_premium:
                return _premium_required_msg(), "idle", None
            return await self._generate_report(db, user, report_type="weekly")

        if body == "menu_report_monthly":
            if not is_premium:
                return _premium_required_msg(), "idle", None
            return await self._generate_report(db, user, report_type="monthly")

        if body == "menu_profile":
            return await self._show_profile_menu(db, user)

        if body.startswith("menu_upgrade"):
            target_plan = "premium" if "premium" in body else "standard"
            msg = await self._get_upgrade_msg(db, user, target_plan)
            return msg, None, None

        return main_menu(is_premium=is_premium, is_standard=is_standard), None, None

    # ── MEDICATION FLOW ──

    async def _s_med_name(
        self, db: AsyncSession, user: User, data: dict, body: str
    ) -> tuple[Msg, str | None, dict | None]:
        name = body.strip()
        if not _is_valid_custom_text(name):
            body_text = (
                "❌ Please enter a valid medication name "
                "(at least 2 characters).\n\n"
                "_Type the name (e.g. Paracetamol)_"
            )
            return (
                ButtonMsg(
                    body=body_text,
                    buttons=[
                        Button(id="back", text="⬅️ Back"),
                        Button(id="go_menu", text="🏠 Main Menu"),
                    ],
                    content_sid=settings.CT_BACK_MENU,
                    content_variables={"1": body_text},
                ),
                "med_name",
                None,
            )
        return (
            MEDICATION_FORM_MENU,
            "med_form",
            {"name": name.title(), "_prev_state": "med_name"},
        )

    async def _s_med_form(
        self, db: AsyncSession, user: User, data: dict, body: str
    ) -> tuple[Msg, str | None, dict | None]:
        if body == "back":
            body_text = (
                "What is the *name* of your medication?\n\n"
                "_Type the name (e.g. Paracetamol)_"
            )
            return (
                ButtonMsg(
                    body=body_text,
                    buttons=[
                        Button(id="back", text="⬅️ Back"),
                        Button(id="go_menu", text="🏠 Main Menu"),
                    ],
                    content_sid=settings.CT_BACK_MENU,
                    content_variables={"1": body_text},
                ),
                "med_name",
                None,
            )
        if body == "form_custom":
            body_text = "Type the form of your medication (e.g. powder, patch, spray):"
            return (
                ButtonMsg(
                    body=body_text,
                    buttons=[
                        Button(id="back", text="⬅️ Back"),
                        Button(id="go_menu", text="🏠 Main Menu"),
                    ],
                    content_sid=settings.CT_BACK_MENU,
                    content_variables={"1": body_text},
                ),
                "med_form_custom",
                data,
            )
        form = FORM_ID_MAP.get(body)
        if not form:
            return MEDICATION_FORM_MENU, "med_form", data

        data["form"] = str(form)
        form_val = getattr(form, "value", str(form))

        if form_val in ("tablet", "capsule"):
            prompt = f"How many {form_val}s should I remind you to take?"
        elif form_val == "syrup":
            prompt = "How many spoons (or ml) should I remind you to take?"
        elif form_val == "drops":
            prompt = "How many drops should I remind you to take?"
        elif form_val == "inhaler":
            prompt = "How many puffs should I remind you to take?"
        elif form_val == "injection":
            prompt = "What is the dosage for the injection (e.g. 1 vial, 10ml)?"
        else:
            prompt = "How much should I remind you to apply (e.g. 1 scoop, pea-sized)?"

        return (
            ButtonMsg(
                body=prompt,
                buttons=[
                    Button(id="back", text="⬅️ Back"),
                    Button(id="go_menu", text="🏠 Main Menu"),
                ],
                content_sid=settings.CT_BACK_MENU,
                content_variables={"1": prompt},
            ),
            "med_dosage",
            data,
        )

    async def _s_med_form_custom(
        self, db: AsyncSession, user: User, data: dict, body: str
    ) -> tuple[Msg, str | None, dict | None]:
        """Handle custom medication form free-text."""
        if body == "back":
            return MEDICATION_FORM_MENU, "med_form", data
        custom_form = body.strip()
        if not _is_valid_custom_text(custom_form):
            body_text = "❌ Please type a valid form (e.g. powder, patch):"
            return (
                ButtonMsg(
                    body=body_text,
                    buttons=[
                        Button(id="back", text="⬅️ Back"),
                        Button(id="go_menu", text="🏠 Main Menu"),
                    ],
                    content_sid=settings.CT_BACK_MENU,
                    content_variables={"1": body_text},
                ),
                "med_form_custom",
                data,
            )
        data["form"] = custom_form
        data["_prev_state"] = "med_form"
        body_text = f"How much *{custom_form}* should I remind you to take?"
        return (
            ButtonMsg(
                body=body_text,
                buttons=[
                    Button(id="back", text="⬅️ Back"),
                    Button(id="go_menu", text="🏠 Main Menu"),
                ],
                content_sid=settings.CT_BACK_MENU,
                content_variables={"1": body_text},
            ),
            "med_dosage",
            data,
        )

    async def _s_med_dosage(
        self, db: AsyncSession, user: User, data: dict, body: str
    ) -> tuple[Msg, str | None, dict | None]:
        if body == "back":
            return MEDICATION_FORM_MENU, "med_form", {"name": data.get("name", "")}

        # Validate numeric dosage — cap at 10 for tablets/capsules
        dosage_text = body.strip()
        form_val = data.get("form", "")
        if form_val in ("tablet", "capsule"):
            try:
                num = int(dosage_text)
                if num < 1 or num > 10:
                    body_text = (
                        "⚠️ That seems too high. Please enter a number "
                        "between *1 and 10*.\n\n"
                        "_If your doctor prescribed more, please confirm with them._"
                    )
                    return (
                        ButtonMsg(
                            body=body_text,
                            buttons=[
                                Button(id="back", text="⬅️ Back"),
                                Button(id="go_menu", text="🏠 Main Menu"),
                            ],
                            content_sid=settings.CT_BACK_MENU,
                            content_variables={"1": body_text},
                        ),
                        "med_dosage",
                        data,
                    )
            except ValueError:
                pass  # Allow free-text for non-standard dosages

        data["dosage"] = dosage_text
        data["_prev_state"] = "med_dosage"
        body_text = (
            "What *time* should I remind you?\n\n"
            "_Type the time (e.g. 8:00am or 2:30pm)_"
        )
        return (
            ButtonMsg(
                body=body_text,
                buttons=[
                    Button(id="back", text="⬅️ Back"),
                    Button(id="go_menu", text="🏠 Main Menu"),
                ],
                content_sid=settings.CT_BACK_MENU,
                content_variables={"1": body_text},
            ),
            "med_time",
            data,
        )

    async def _s_med_time(
        self, db: AsyncSession, user: User, data: dict, body: str
    ) -> tuple[Msg, str | None, dict | None]:
        if body == "back":
            form_val = data.get("form", "")
            prompt = f"How many {form_val}s should I remind you to take?"
            return (
                ButtonMsg(
                    body=prompt,
                    buttons=[
                        Button(id="back", text="⬅️ Back"),
                        Button(id="go_menu", text="🏠 Main Menu"),
                    ],
                    content_sid=settings.CT_BACK_MENU,
                    content_variables={"1": prompt},
                ),
                "med_dosage",
                data,
            )

        parsed = _parse_time(body)
        if not parsed:
            body_text = (
                "I couldn't understand that time.\n"
                "Please enter like *8:00am* or *2:30pm*."
            )
            return (
                ButtonMsg(
                    body=body_text,
                    buttons=[
                        Button(id="back", text="⬅️ Back"),
                        Button(id="go_menu", text="🏠 Main Menu"),
                    ],
                    content_sid=settings.CT_BACK_MENU,
                    content_variables={"1": body_text},
                ),
                "med_time",
                data,
            )

        try:
            med = MedicationCreate(
                name=data["name"],
                item_type=ItemType.MEDICATION,
                medication_form=data.get("form"),
                dosage=data.get("dosage"),
                times_per_day=1,
                schedules=[MedicationScheduleCreate(scheduled_time=parsed)],
            )
            await medication_service.create_medication(db, user_id=user.id, obj_in=med)
            time_str = parsed.strftime("%I:%M %p")
            dosage = data.get("dosage", "")
            dosage_str = f" ({dosage})" if dosage else ""
            body_text = (
                f"✅ *{data['name']}*{dosage_str} saved!\n"
                f"⏰ Daily reminder at *{time_str}*."
            )
            return (
                ButtonMsg(
                    body=body_text,
                    buttons=[Button(id="go_menu", text="🏠 Main Menu")],
                    content_sid=settings.CT_GO_MENU,
                    content_variables={"1": body_text},
                ),
                None,
                None,
            )
        except ValueError as e:
            return (
                ButtonMsg(
                    body=str(e),
                    buttons=[Button(id="go_menu", text="🏠 Main Menu")],
                ),
                None,
                None,
            )

    # ── EXERCISE FLOW ──

    async def _s_exercise_type(
        self, db: AsyncSession, user: User, data: dict, body: str
    ) -> tuple[Msg, str | None, dict | None]:
        if body == "ex_custom":
            body_text = "Type the name of your exercise (e.g. Pilates, Jump Rope):"
            return (
                ButtonMsg(
                    body=body_text,
                    buttons=[
                        Button(id="back", text="⬅️ Back"),
                        Button(id="go_menu", text="🏠 Main Menu"),
                    ],
                    content_sid=settings.CT_BACK_MENU,
                    content_variables={"1": body_text},
                ),
                "exercise_type_custom",
                {},
            )
        exercise = EXERCISE_ID_MAP.get(body)
        if not exercise:
            return EXERCISE_TYPE_MENU, "exercise_type", data
        return (
            EXERCISE_DURATION_MENU,
            "exercise_duration",
            {"name": exercise, "_prev_state": "exercise_type"},
        )

    async def _s_exercise_type_custom(
        self, db: AsyncSession, user: User, data: dict, body: str
    ) -> tuple[Msg, str | None, dict | None]:
        if body == "back":
            return EXERCISE_TYPE_MENU, "exercise_type", data
        name = body.strip()
        if not _is_valid_custom_text(name):
            body_text = "❌ Please type a valid exercise name:"
            return (
                ButtonMsg(
                    body=body_text,
                    buttons=[
                        Button(id="back", text="⬅️ Back"),
                        Button(id="go_menu", text="🏠 Main Menu"),
                    ],
                    content_sid=settings.CT_BACK_MENU,
                    content_variables={"1": body_text},
                ),
                "exercise_type_custom",
                data,
            )
        return (
            EXERCISE_DURATION_MENU,
            "exercise_duration",
            {"name": name.title(), "_prev_state": "exercise_type"},
        )

    async def _s_exercise_duration(
        self, db: AsyncSession, user: User, data: dict, body: str
    ) -> tuple[Msg, str | None, dict | None]:
        if body == "back":
            return EXERCISE_TYPE_MENU, "exercise_type", {}
        duration = DURATION_ID_MAP.get(body)
        if not duration:
            return EXERCISE_DURATION_MENU, "exercise_duration", data
        data["duration"] = duration
        data["_prev_state"] = "exercise_duration"
        body_text = (
            "What *time* should I remind you?\n\n"
            "_Type the time (e.g. 6:00am or 5:30pm)_"
        )
        return (
            ButtonMsg(
                body=body_text,
                buttons=[
                    Button(id="back", text="⬅️ Back"),
                    Button(id="go_menu", text="🏠 Main Menu"),
                ],
                content_sid=settings.CT_BACK_MENU,
                content_variables={"1": body_text},
            ),
            "exercise_time",
            data,
        )

    async def _s_exercise_time(
        self, db: AsyncSession, user: User, data: dict, body: str
    ) -> tuple[Msg, str | None, dict | None]:
        if body == "back":
            return EXERCISE_DURATION_MENU, "exercise_duration", data
        parsed = _parse_time(body)
        if not parsed:
            body_text = (
                "I couldn't understand that time.\n"
                "Please enter like *6:00am* or *5:30pm*."
            )
            return (
                ButtonMsg(
                    body=body_text,
                    buttons=[
                        Button(id="back", text="⬅️ Back"),
                        Button(id="go_menu", text="🏠 Main Menu"),
                    ],
                    content_sid=settings.CT_BACK_MENU,
                    content_variables={"1": body_text},
                ),
                "exercise_time",
                data,
            )

        try:
            med = MedicationCreate(
                name=data["name"],
                item_type=ItemType.EXERCISE,
                dosage=data["duration"],
                times_per_day=1,
                schedules=[MedicationScheduleCreate(scheduled_time=parsed)],
            )
            await medication_service.create_medication(db, user_id=user.id, obj_in=med)
            time_str = parsed.strftime("%I:%M %p")
            body_text = (
                f"✅ *{data['name']}* ({data['duration']}) saved!\n"
                f"⏰ Daily reminder at *{time_str}*."
            )
            return (
                ButtonMsg(
                    body=body_text,
                    buttons=[Button(id="go_menu", text="🏠 Main Menu")],
                    content_sid=settings.CT_GO_MENU,
                    content_variables={"1": body_text},
                ),
                None,
                None,
            )
        except ValueError as e:
            return (
                ButtonMsg(
                    body=str(e),
                    buttons=[Button(id="go_menu", text="🏠 Main Menu")],
                ),
                None,
                None,
            )

    # ── WATER INTAKE FLOW ──

    async def _s_water_amount(
        self, db: AsyncSession, user: User, data: dict, body: str
    ) -> tuple[Msg, str | None, dict | None]:
        if body == "water_custom":
            body_text = "Type your custom water amount (e.g. 350ml, 1.5 litres):"
            return (
                ButtonMsg(
                    body=body_text,
                    buttons=[
                        Button(id="back", text="⬅️ Back"),
                        Button(id="go_menu", text="🏠 Main Menu"),
                    ],
                    content_sid=settings.CT_BACK_MENU,
                    content_variables={"1": body_text},
                ),
                "water_amount_custom",
                {},
            )
        amount = WATER_AMOUNT_ID_MAP.get(body)
        if not amount:
            return WATER_AMOUNT_MENU, "water_amount", data
        return (
            WATER_INTERVAL_MENU,
            "water_interval",
            {"amount": amount, "_prev_state": "water_amount"},
        )

    async def _s_water_amount_custom(
        self, db: AsyncSession, user: User, data: dict, body: str
    ) -> tuple[Msg, str | None, dict | None]:
        if body == "back":
            return WATER_AMOUNT_MENU, "water_amount", data
        amount = body.strip()
        if not _is_valid_custom_text(amount):
            body_text = "❌ Please type a valid amount (e.g. 350ml):"
            return (
                ButtonMsg(
                    body=body_text,
                    buttons=[
                        Button(id="back", text="⬅️ Back"),
                        Button(id="go_menu", text="🏠 Main Menu"),
                    ],
                    content_sid=settings.CT_BACK_MENU,
                    content_variables={"1": body_text},
                ),
                "water_amount_custom",
                data,
            )
        return (
            WATER_INTERVAL_MENU,
            "water_interval",
            {"amount": amount, "_prev_state": "water_amount"},
        )

    async def _s_water_interval(
        self, db: AsyncSession, user: User, data: dict, body: str
    ) -> tuple[Msg, str | None, dict | None]:
        if body == "back":
            return WATER_AMOUNT_MENU, "water_amount", {}
        if body == "int_custom":
            body_text = "How many hours between each reminder? (e.g. 1.5, 2, 3):"
            return (
                ButtonMsg(
                    body=body_text,
                    buttons=[
                        Button(id="back", text="⬅️ Back"),
                        Button(id="go_menu", text="🏠 Main Menu"),
                    ],
                    content_sid=settings.CT_BACK_MENU,
                    content_variables={"1": body_text},
                ),
                "water_interval_custom",
                data,
            )
        interval_info = WATER_INTERVAL_ID_MAP.get(body)
        if not interval_info:
            return WATER_INTERVAL_MENU, "water_interval", data

        hours_gap, label = interval_info

        # Generate schedules every N hours from 7am to 9pm
        schedules = []
        hour = 7
        while hour <= 21:
            schedules.append(MedicationScheduleCreate(scheduled_time=dt_time(hour, 0)))
            hour += hours_gap

        try:
            med = MedicationCreate(
                name="Water Intake",
                item_type=ItemType.WATER_INTAKE,
                dosage=data["amount"],
                times_per_day=len(schedules),
                schedules=schedules,
            )
            await medication_service.create_medication(db, user_id=user.id, obj_in=med)
            time_list = ", ".join(
                s.scheduled_time.strftime("%I:%M %p") for s in schedules
            )
            body_text = (
                f"✅ *Water Intake* ({data['amount']}) saved!\n"
                f"⏰ Reminders {label}:\n{time_list}"
            )
            return (
                ButtonMsg(
                    body=body_text,
                    buttons=[Button(id="go_menu", text="🏠 Main Menu")],
                    content_sid=settings.CT_GO_MENU,
                    content_variables={"1": body_text},
                ),
                None,
                None,
            )
        except ValueError as e:
            return (
                ButtonMsg(
                    body=str(e),
                    buttons=[Button(id="go_menu", text="🏠 Main Menu")],
                ),
                None,
                None,
            )

    async def _s_water_interval_custom(
        self, db: AsyncSession, user: User, data: dict, body: str
    ) -> tuple[Msg, str | None, dict | None]:
        """Handle custom water reminder interval."""
        if body == "back":
            return WATER_INTERVAL_MENU, "water_interval", data
        try:
            hours_gap = float(body.strip())
            if hours_gap < 0.5 or hours_gap > 12:
                body_text = "⚠️ Please enter a value between 0.5 and 12 hours:"
                return (
                    ButtonMsg(
                        body=body_text,
                        buttons=[
                            Button(id="back", text="⬅️ Back"),
                            Button(id="go_menu", text="🏠 Main Menu"),
                        ],
                        content_sid=settings.CT_BACK_MENU,
                        content_variables={"1": body_text},
                    ),
                    "water_interval_custom",
                    data,
                )
        except ValueError:
            body_text = "❌ Please enter a number (e.g. 1.5, 2, 3):"
            return (
                ButtonMsg(
                    body=body_text,
                    buttons=[
                        Button(id="back", text="⬅️ Back"),
                        Button(id="go_menu", text="🏠 Main Menu"),
                    ],
                    content_sid=settings.CT_BACK_MENU,
                    content_variables={"1": body_text},
                ),
                "water_interval_custom",
                data,
            )

        label = f"every {hours_gap:g} hour{'s' if hours_gap != 1 else ''}"
        schedules = []
        hour = 7.0
        while hour <= 21:
            h = int(hour)
            m = int((hour - h) * 60)
            schedules.append(MedicationScheduleCreate(scheduled_time=dt_time(h, m)))
            hour += hours_gap

        try:
            med = MedicationCreate(
                name="Water Intake",
                item_type=ItemType.WATER_INTAKE,
                dosage=data.get("amount", "custom"),
                times_per_day=len(schedules),
                schedules=schedules,
            )
            await medication_service.create_medication(db, user_id=user.id, obj_in=med)
            time_list = ", ".join(
                s.scheduled_time.strftime("%I:%M %p") for s in schedules
            )
            body_text = (
                f"✅ *Water Intake* ({data.get('amount', 'custom')}) saved!\n"
                f"⏰ Reminders {label}:\n{time_list}"
            )
            return (
                ButtonMsg(
                    body=body_text,
                    buttons=[Button(id="go_menu", text="🏠 Main Menu")],
                    content_sid=settings.CT_GO_MENU,
                    content_variables={"1": body_text},
                ),
                None,
                None,
            )
        except ValueError as e:
            return (
                ButtonMsg(
                    body=str(e),
                    buttons=[Button(id="go_menu", text="🏠 Main Menu")],
                ),
                None,
                None,
            )

    # ── HELPERS ──

    async def _start_delete_flow(
        self, db: AsyncSession, user: User
    ) -> tuple[Msg, str | None, dict | None]:
        meds = await medication_service.get_user_medications(db, user_id=user.id)
        if not meds:
            return (
                ButtonMsg(
                    body="📝 You have no active reminders to delete.",
                    buttons=[
                        Button(id="menu_medication", text="💊 Add Medication"),
                        Button(id="go_menu", text="🏠 Main Menu"),
                    ],
                ),
                "idle",
                None,
            )

        rows = []
        for m in meds:
            rows.append(ListRow(id=f"del_{m.id}", title=f"🗑️ {m.name}"))

        return (
            ListMsg(
                body="Which reminder would you like to delete?",
                button_text="Select Reminder",
                title="Delete Reminder",
                sections=[ListSection(title="Active Reminders", rows=rows)],
            ),
            "delete_confirm",
            None,
        )

    async def _s_delete_confirm(
        self, db: AsyncSession, user: User, data: dict, body: str
    ) -> tuple[Msg, str | None, dict | None]:
        if not body.startswith("del_"):
            return await self._start_delete_flow(db, user)

        med_id = body.split("_", 1)[1]
        from uuid import UUID

        from app.models.medication import Medication

        try:
            target_med_id = UUID(med_id)
        except Exception:
            return await self._start_delete_flow(db, user)

        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        query = (
            select(Medication)
            .options(selectinload(Medication.schedules))
            .where(Medication.id == target_med_id)
        )
        result = await db.execute(query)
        med = result.scalars().first()

        if not med or med.user_id != user.id or not med.is_active:
            return await self._start_delete_flow(db, user)

        # Soft delete the medication and its schedules
        med.is_active = False
        schedule_ids = []
        for s in med.schedules:
            s.is_active = False
            schedule_ids.append(s.id)

        # Also clean up pending ReminderLogs
        if schedule_ids:
            from sqlalchemy import update

            from app.models.reminder import ReminderLog

            await db.execute(
                update(ReminderLog)
                .where(ReminderLog.schedule_id.in_(schedule_ids))
                .where(ReminderLog.status == "pending")
                .values(status="cancelled")
            )
        await db.commit()

        return (
            ButtonMsg(
                body=f"✅ *{med.name}* reminder has been deleted successfully.",
                buttons=[Button(id="go_menu", text="🏠 Main Menu")],
                content_sid=settings.CT_GO_MENU,
                content_variables={
                    "1": f"✅ *{med.name}* reminder has been deleted successfully."
                },
            ),
            "delete_confirm",
            None,
        )

    async def _handle_taken(
        self, db: AsyncSession, user: User, body: str
    ) -> tuple[Msg, str | None, dict | None]:
        """Handle '✅ Taken' / '✅ Done' button click."""
        reminder_id_str = body.replace("take_", "")
        from datetime import UTC, datetime
        from uuid import UUID

        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.models.medication import MedicationSchedule
        from app.models.reminder import ReminderLog

        try:
            reminder_id = UUID(reminder_id_str)
        except Exception:
            return TextMsg(body="❌ Invalid reminder reference."), "idle", None

        # Load reminder with medication info for the message
        query = (
            select(ReminderLog)
            .options(
                selectinload(ReminderLog.schedule).selectinload(
                    MedicationSchedule.medication
                )
            )
            .where(ReminderLog.id == reminder_id, ReminderLog.user_id == user.id)
        )
        result = await db.execute(query)
        reminder = result.scalars().first()

        if not reminder:
            return TextMsg(body="❌ Reminder not found."), "idle", None

        if reminder.status in ("taken", "missed"):
            return (
                TextMsg(
                    body=f"📝 This reminder for *{reminder.schedule.medication.name}* was already marked as {reminder.status}."
                ),
                "idle",
                None,
            )

        # Update status
        reminder.status = "taken"
        reminder.responded_at = datetime.now(UTC)
        await db.commit()

        return (
            ButtonMsg(
                body=f"✅ Great job! Your reminder for *{reminder.schedule.medication.name}* is marked as complete. Keep it up! 💪",
                buttons=[Button(id="go_menu", text="🏠 Menu")],
                content_sid=settings.CT_GO_MENU,
                content_variables={
                    "1": f"✅ Great job! Your reminder for *{reminder.schedule.medication.name}* is marked as complete. Keep it up! 💪"
                },
            ),
            "idle",
            None,
        )

    async def _handle_snooze(
        self, db: AsyncSession, user: User, body: str
    ) -> tuple[Msg, str | None, dict | None]:
        """Handle '⏰ Snooze' button click."""
        reminder_id_str = body.replace("snooze_", "")
        from datetime import UTC, datetime, timedelta
        from uuid import UUID

        from sqlalchemy import select

        from app.models.reminder import ReminderLog

        try:
            reminder_id = UUID(reminder_id_str)
        except Exception:
            return TextMsg(body="❌ Invalid reminder reference."), "idle", None

        query = select(ReminderLog).where(
            ReminderLog.id == reminder_id, ReminderLog.user_id == user.id
        )
        result = await db.execute(query)
        reminder = result.scalars().first()

        if not reminder:
            return TextMsg(body="❌ Reminder not found."), "idle", None

        # Reschedule for 3 minutes from now
        reminder.status = "pending"
        reminder.scheduled_for = datetime.now(UTC) + timedelta(minutes=3)
        await db.commit()

        return (
            TextMsg(
                body="⏰ Okay, I've snoozed it. I'll remind you again in 3 minutes!"
            ),
            "idle",
            None,
        )

    async def _handle_skip(
        self, db: AsyncSession, user: User, body: str
    ) -> tuple[Msg, str | None, dict | None]:
        """Handle '❌ Skip' button click."""
        reminder_id_str = body.replace("skip_", "")
        from datetime import UTC, datetime
        from uuid import UUID

        from sqlalchemy import select

        from app.models.reminder import ReminderLog

        try:
            reminder_id = UUID(reminder_id_str)
        except Exception:
            return TextMsg(body="❌ Invalid reminder reference."), "idle", None

        query = select(ReminderLog).where(
            ReminderLog.id == reminder_id, ReminderLog.user_id == user.id
        )
        result = await db.execute(query)
        reminder = result.scalars().first()

        if not reminder:
            return TextMsg(body="❌ Reminder not found."), "idle", None

        if reminder.status in ("taken", "missed"):
            return (
                TextMsg(
                    body=f"📝 This reminder was already marked as {reminder.status}."
                ),
                "idle",
                None,
            )

        # Update status
        reminder.status = "missed"
        reminder.responded_at = datetime.now(UTC)
        await db.commit()

        return (
            TextMsg(body="Got it. I've marked this reminder as skipped. 📝"),
            "idle",
            None,
        )

    async def _show_reminders(
        self, db: AsyncSession, user: User
    ) -> tuple[Msg, str | None, dict | None]:
        meds = await medication_service.get_user_medications(db, user_id=user.id)
        if not meds:
            return (
                ButtonMsg(
                    body="📝 You have no active reminders.",
                    buttons=[
                        Button(id="menu_medication", text="💊 Add Medication"),
                        Button(id="go_menu", text="🏠 Main Menu"),
                    ],
                ),
                "idle",
                None,
            )

        icons = {
            "medication": "💊",
            "exercise": "🏃",
            "water_intake": "💧",
        }
        lines = ["📝 *Your Active Reminders*\n"]
        for m in meds:
            icon = icons.get(m.item_type, "📌")
            dosage = f" ({m.dosage})" if m.dosage else ""
            times = ", ".join(
                s.scheduled_time.strftime("%I:%M %p")
                for s in m.schedules
                if s.is_active
            )
            lines.append(f"{icon} *{m.name}*{dosage}\n   ⏰ {times}")

        body_text = "\n".join(lines)
        return (
            ButtonMsg(
                body=body_text,
                buttons=[Button(id="go_menu", text="🏠 Main Menu")],
                content_sid=settings.CT_GO_MENU,
                content_variables={"1": body_text},
            ),
            "idle",
            None,
        )

    async def _generate_report(
        self, db: AsyncSession, user: User, report_type: str = "weekly"
    ) -> tuple[Msg, str | None, dict | None]:
        from datetime import UTC, datetime, timedelta

        from app.services.adherence_service import adherence_service

        user_name = "User"
        if user.profile and user.profile.first_name:
            user_name = user.profile.first_name
            if user_name.strip().lower() == "new":
                user_name = "User"

        now = datetime.now(UTC)
        days_back = 7 if report_type == "weekly" else 30
        start = now - timedelta(days=days_back)

        result = await adherence_service.generate_report(
            db,
            user_id=user.id,
            user_name=user_name,
            report_type=report_type,
            period_start=start,
            period_end=now,
        )

        if "error" in result:
            return _premium_required_msg(), "idle", None

        msg = result.get(
            "whatsapp_message",
            "No data available for this period.",
        )

        return (
            ButtonMsg(
                body=msg,
                buttons=[Button(id="go_menu", text="🏠 Main Menu")],
                content_sid=settings.CT_GO_MENU,
                content_variables={"1": msg},
            ),
            "idle",
            None,
        )

    async def _show_profile_menu(
        self, db: AsyncSession, user: User
    ) -> tuple[Msg, str | None, dict | None]:
        name = user.profile.first_name
        if not name or name.lower() == "new":
            name = "_(Not set)_"

        return (
            ButtonMsg(
                body=(
                    f"👤 *Your Profile*\n\n"
                    f"🏷️ *Name:* {name}\n"
                    f"📱 *WhatsApp:* {user.profile.whatsapp_number}\n"
                    f"🌍 *Timezone:* {user.profile.timezone or 'UTC'}\n\n"
                    "Would you like to update your name?"
                ),
                buttons=[
                    Button(id="update_name", text="✏️ Update Name"),
                    Button(id="go_menu", text="🏠 Main Menu"),
                ],
                content_sid=settings.CT_PROFILE_MENU,
                content_variables={
                    "1": str(name),
                    "2": str(user.profile.whatsapp_number),
                    "3": str(user.profile.timezone or "UTC"),
                },
            ),
            "profile_menu",
            None,
        )

    async def _s_profile_menu(
        self, db: AsyncSession, user: User, data: dict, body: str
    ) -> tuple[Msg, str | None, dict | None]:
        b = body.lower()
        if b == "update_name" or b in (
            "yes",
            "y",
            "update",
            "change",
            "edit",
            "update name",
        ):
            body_text = "What should I call you? Please type your first name:"
            return (
                ButtonMsg(
                    body=body_text,
                    buttons=[
                        Button(id="go_menu", text="🏠 Main Menu"),
                    ],
                    content_sid=settings.CT_GO_MENU,
                    content_variables={"1": body_text},
                ),
                "update_name",
                None,
            )
        elif b == "go_menu" or b in ("no", "n", "menu", "main menu", "nah"):
            from app.services.subscription_service import subscription_service

            is_prem = await subscription_service.has_active_subscription(
                db, user.id, "premium"
            )
            is_std = await subscription_service.has_active_subscription(
                db, user.id, "standard"
            )
            return main_menu(is_premium=is_prem, is_standard=is_std), "idle", None
        elif b == "legal_privacy" or b in (
            "legal",
            "privacy",
            "disclaimer",
            "policy",
            "terms",
        ):
            body_text = (
                "⚖️ *Legal & Privacy Information*\n\n"
                "• Medical Disclaimer: "
                + f"{settings.BASE_URL}/legal/disclaimer.html\n"
                "• Terms of Service: " + f"{settings.BASE_URL}/legal/terms.html\n"
                "• Privacy Policy: " + f"{settings.BASE_URL}/legal/privacy.html\n\n"
                "ReminDAM is a reminder tool and not a substitute for medical advice."
            )
            return (
                ButtonMsg(
                    body=body_text,
                    buttons=[Button(id="go_menu", text="🏠 Main Menu")],
                    content_sid=settings.CT_GO_MENU,
                    content_variables={"1": body_text},
                ),
                None,
                None,
            )

        return await self._show_profile_menu(db, user)

    async def _s_update_name(
        self, db: AsyncSession, user: User, data: dict, body: str
    ) -> tuple[Msg, str | None, dict | None]:
        name = body.strip()
        if not name or len(name) < 2:
            body_text = "❌ Please enter a valid name (at least 2 characters):"
            return (
                ButtonMsg(
                    body=body_text,
                    buttons=[Button(id="go_menu", text="🏠 Main Menu")],
                    content_sid=settings.CT_GO_MENU,
                    content_variables={"1": body_text},
                ),
                "update_name",
                None,
            )

        # Update the profile
        user.profile.first_name = name
        await db.commit()

        return (
            ButtonMsg(
                body=f"✨ Nice to meet you, *{name}*! I've updated your profile.",
                buttons=[Button(id="go_menu", text="🏠 Main Menu")],
                content_sid=settings.CT_GO_MENU,
                content_variables={
                    "1": f"✨ Nice to meet you, *{name}*! I've updated your profile."
                },
            ),
            "idle",
            None,
        )


def _is_valid_custom_text(text: str) -> bool:
    """Validate that custom input is not gibberish (alphanumeric and reasonable length)."""
    import re

    if not text or len(text) < 2 or len(text) > 40:
        return False
    # Must contain at least one letter (prevents entering just numbers or symbols)
    if not re.search(r"[a-zA-Z]", text):
        return False
    return True


def _parse_time(text: str) -> dt_time | None:
    """Best-effort parse of common time formats."""
    import re

    text = text.strip().lower().replace(".", ":")

    # Format 1: 24-hour e.g. "14:30" or "09:44"
    match = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        if 0 <= h <= 23 and 0 <= m <= 59:
            return dt_time(h, m)

    # Format 2: 12-hour with minutes e.g. "9:44pm", "09:44 am"
    match = re.match(r"^(\d{1,2}):(\d{2})\s*(am|pm)$", text)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        period = match.group(3)
        if period == "pm" and h != 12:
            h += 12
        if period == "am" and h == 12:
            h = 0
        if 0 <= h <= 23 and 0 <= m <= 59:
            return dt_time(h, m)

    # Format 3: 12-hour without minutes e.g. "9pm", "9 am"
    match = re.match(r"^(\d{1,2})\s*(am|pm)$", text)
    if match:
        h = int(match.group(1))
        period = match.group(2)
        if period == "pm" and h != 12:
            h += 12
        if period == "am" and h == 12:
            h = 0
        if 0 <= h <= 23:
            return dt_time(h, 0)

    return None


flow_service = FlowService()
