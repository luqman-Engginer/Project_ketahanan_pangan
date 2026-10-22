"""WTForms classes for FoodLoop ID."""
from app.forms.activity import ClaimStatusForm, CommentForm, WasteLogForm
from app.forms.auth import LoginForm, RegisterForm
from app.forms.inventory import InventoryItemForm
from app.forms.surplus import SurplusListingForm

__all__ = [
    "LoginForm",
    "RegisterForm",
    "InventoryItemForm",
    "SurplusListingForm",
    "ClaimStatusForm",
    "WasteLogForm",
    "CommentForm",
]

